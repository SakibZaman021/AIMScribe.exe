"""
WebSocket Server for AIMScribe Recorder
Enables direct browser-to-local-app communication.

This is the industrial solution:
- CMED (browser) connects via WebSocket to localhost:5050
- Browser knows doctor_id (from CMED login)
- Browser sends commands with full context
- AIMScribe doesn't need login - it receives all info from browser
"""
import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, Set, Optional, Any
from dataclasses import dataclass, asdict

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


@dataclass
class RecorderStatus:
    """Current recorder status"""
    is_recording: bool
    session_id: Optional[str]
    patient_id: Optional[str]
    patient_name: Optional[str]
    doctor_id: Optional[str]
    hospital_id: Optional[str]
    duration_seconds: float
    connected_clients: int


class WebSocketManager:
    """
    Manages WebSocket connections from CMED (browser).

    Architecture:
    - Browser (CMED) connects to ws://localhost:5050/ws
    - Browser sends commands: start, stop, status
    - AIMScribe sends events: recording_started, clip_uploaded, ner_ready
    """

    def __init__(self):
        # Active WebSocket connections
        self._connections: Set[WebSocket] = set()

        # Session controller reference (set via set_controller)
        self._controller = None

        # Lock for thread safety
        self._lock = asyncio.Lock()

        logger.info("WebSocketManager initialized")

    def set_controller(self, controller):
        """Set the session controller reference"""
        self._controller = controller
        logger.info("Session controller linked to WebSocketManager")

    async def connect(self, websocket: WebSocket) -> bool:
        """
        Accept a new WebSocket connection.
        Only accepts connections from localhost for security.
        """
        # Security: Only allow localhost connections
        client_host = websocket.client.host if websocket.client else "unknown"

        if client_host not in ['127.0.0.1', 'localhost', '::1', '0.0.0.0']:
            logger.warning(f"Rejected WebSocket connection from: {client_host}")
            await websocket.close(code=4003, reason="Only localhost connections allowed")
            return False

        await websocket.accept()

        async with self._lock:
            self._connections.add(websocket)

        logger.info(f"WebSocket connected from {client_host}. Total: {len(self._connections)}")

        # Send initial status
        await self._send_status(websocket)

        return True

    async def disconnect(self, websocket: WebSocket):
        """Handle WebSocket disconnection"""
        async with self._lock:
            self._connections.discard(websocket)

        logger.info(f"WebSocket disconnected. Total: {len(self._connections)}")

    async def handle_message(self, websocket: WebSocket, data: str) -> Dict[str, Any]:
        """
        Handle incoming message from CMED browser.

        Commands:
        - start: Start recording with patient context
        - stop: Stop current recording
        - status: Get current status
        """
        try:
            message = json.loads(data)
            command = message.get('command', '').lower()

            logger.info(f"Received command: {command}")

            if command == 'start':
                return await self._handle_start(message)

            elif command == 'stop':
                return await self._handle_stop(message)

            elif command == 'status':
                return await self._handle_status()

            else:
                return {
                    "event": "error",
                    "error": f"Unknown command: {command}",
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON: {e}")
            return {
                "event": "error",
                "error": "Invalid JSON format",
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }

        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)
            return {
                "event": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }

    async def _handle_start(self, message: Dict) -> Dict[str, Any]:
        """Handle start recording command"""
        if self._controller is None:
            return {
                "event": "error",
                "error": "Controller not initialized",
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }

        # Extract session info from message
        session = message.get('session', {})
        health_screening = message.get('health_screening', {})
        callback = message.get('callback', {})

        # Import here to avoid circular imports
        from core.session_controller import SessionContext

        # Create session context from browser data
        context = SessionContext(
            patient_id=session.get('patient_id', ''),
            patient_name=session.get('patient_name', ''),
            age=str(session.get('age', '')),
            gender=session.get('gender', ''),
            doctor_id=session.get('doctor_id', 'UNKNOWN'),
            hospital_id=session.get('hospital_id', 'UNKNOWN'),
            health_screening=health_screening,
            ner_webhook_url=callback.get('ner_webhook_url', ''),
            status_webhook_url=callback.get('status_webhook_url', '')
        )

        logger.info(f"Starting recording for patient: {context.patient_id}")
        logger.info(f"Doctor: {context.doctor_id}, Hospital: {context.hospital_id}")

        # Start recording
        result = await self._controller.handle_trigger(context)

        # Build response
        response = {
            "event": "recording_started",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "session_id": result.get('session_id'),
            "patient_id": context.patient_id,
            "doctor_id": context.doctor_id,
            "hospital_id": context.hospital_id,
            "previous_session_stopped": result.get('previous_session_stopped', False)
        }

        # Broadcast to all connected clients
        await self.broadcast(response)

        return response

    async def _handle_stop(self, message: Dict) -> Dict[str, Any]:
        """Handle stop recording command"""
        if self._controller is None:
            return {
                "event": "error",
                "error": "Controller not initialized",
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }

        logger.info("Stopping recording")

        result = await self._controller.handle_stop()

        response = {
            "event": "recording_stopped",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "session_id": result.get('session_id'),
            "status": result.get('status'),
            "duration_seconds": result.get('duration_seconds', 0)
        }

        # Broadcast to all connected clients
        await self.broadcast(response)

        return response

    async def _handle_status(self) -> Dict[str, Any]:
        """Handle status request"""
        status = self._get_status()

        return {
            "event": "status",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            **asdict(status)
        }

    async def _send_status(self, websocket: WebSocket):
        """Send current status to a specific client"""
        status = self._get_status()

        message = {
            "event": "status",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            **asdict(status)
        }

        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.warning(f"Failed to send status: {e}")

    def _get_status(self) -> RecorderStatus:
        """Get current recorder status"""
        if self._controller is None:
            return RecorderStatus(
                is_recording=False,
                session_id=None,
                patient_id=None,
                patient_name=None,
                doctor_id=None,
                hospital_id=None,
                duration_seconds=0,
                connected_clients=len(self._connections)
            )

        ctrl_status = self._controller.get_status()

        return RecorderStatus(
            is_recording=ctrl_status.get('is_recording', False),
            session_id=ctrl_status.get('session_id'),
            patient_id=ctrl_status.get('patient_id'),
            patient_name=ctrl_status.get('patient_name'),
            doctor_id=ctrl_status.get('doctor_id'),
            hospital_id=ctrl_status.get('hospital_id'),
            duration_seconds=ctrl_status.get('duration_seconds', 0),
            connected_clients=len(self._connections)
        )

    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast message to all connected clients"""
        if not self._connections:
            return

        dead_connections = set()

        async with self._lock:
            for websocket in self._connections:
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    logger.warning(f"Failed to send to client: {e}")
                    dead_connections.add(websocket)

        # Clean up dead connections
        if dead_connections:
            async with self._lock:
                self._connections -= dead_connections

    async def send_event(self, event_type: str, data: Dict[str, Any]):
        """
        Send an event to all connected CMED clients.

        Use this to notify browser about:
        - clip_uploaded: A chunk was uploaded to backend
        - ner_ready: NER results available
        - error: Something went wrong
        """
        message = {
            "event": event_type,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            **data
        }

        await self.broadcast(message)
        logger.info(f"Broadcasted event: {event_type}")


# Global WebSocket manager instance
ws_manager = WebSocketManager()


def get_ws_manager() -> WebSocketManager:
    """Get the global WebSocket manager"""
    return ws_manager
