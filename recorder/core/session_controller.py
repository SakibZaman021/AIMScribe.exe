"""
Session Controller
Handles auto start/stop logic when triggers come from CMED.
If already recording, stops current session and starts new one.

Key changes:
- Uses patient_id as session_id for simplicity
- Forwards recordings to AIMS LAB server to save space on doctor's PC
- Includes force reset for crash recovery
"""
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass

from core.recorder import AudioRecorder, get_recorder
from core.simple_splitter import SimpleSplitter, ClipInfo
from core.clip_uploader import AsyncClipUploader, UploadResult
from core.file_forwarder import FileForwarder

logger = logging.getLogger(__name__)


@dataclass
class SessionContext:
    """Context for a recording session"""
    patient_id: str
    patient_name: str
    age: str
    gender: str
    doctor_id: str
    hospital_id: str
    health_screening: Dict[str, Any]
    # Webhook URLs for CMED integration
    ner_webhook_url: str = ""
    status_webhook_url: str = ""


@dataclass
class SessionState:
    """Current session state"""
    is_recording: bool = False
    session_id: Optional[str] = None  # Now same as patient_id
    patient_id: Optional[str] = None
    patient_name: Optional[str] = None
    start_time: Optional[datetime] = None
    context: Optional[SessionContext] = None


class SessionController:
    """
    Controls recording sessions.

    Handles the logic:
    - If trigger received and NOT recording: Start new session
    - If trigger received and IS recording: Stop current, start new
    - session_id = patient_id (1 patient = 1 unique ID from CMED)
    - Forwards recordings to AIMS LAB server after completion
    """

    def __init__(
        self,
        backend_url: str = "http://localhost:6000",
        aimslab_server_url: str = "http://localhost:7000"
    ):
        self.backend_url = backend_url
        self.aimslab_server_url = aimslab_server_url

        # Current state
        self._state = SessionState()
        self._lock = asyncio.Lock()

        # Components
        self._recorder: Optional[AudioRecorder] = None
        self._splitter: Optional[SimpleSplitter] = None
        self._uploader: Optional[AsyncClipUploader] = None
        self._forwarder: Optional[FileForwarder] = None

        # Paths
        self.temp_clips_dir = Path("temp_clips")
        self.recordings_dir = Path("recordings")

        # Create directories
        self.temp_clips_dir.mkdir(parents=True, exist_ok=True)
        self.recordings_dir.mkdir(parents=True, exist_ok=True)

        # Initialize file forwarder
        self._forwarder = FileForwarder(aimslab_server_url=aimslab_server_url)

        logger.info(f"SessionController initialized")
        logger.info(f"  Backend URL: {backend_url}")
        logger.info(f"  AIMS LAB Server: {aimslab_server_url}")

    async def handle_trigger(self, context: SessionContext) -> Dict[str, Any]:
        """
        Handle trigger from CMED.

        If already recording: stop current session first.
        Then start new session with given context.

        session_id = patient_id (from CMED)

        Returns:
            {
                "session_id": str (same as patient_id),
                "status": "recording_started",
                "previous_session_stopped": bool
            }
        """
        async with self._lock:
            previous_stopped = False

            # If already recording, stop current session
            if self._state.is_recording:
                logger.info(f"Stopping current session for patient {self._state.patient_id}")
                await self._stop_current_session()
                previous_stopped = True

            # Start new session
            # session_id = patient_id
            session_id = await self._start_new_session(context)

            return {
                "session_id": session_id,  # Same as patient_id
                "status": "recording_started",
                "previous_session_stopped": previous_stopped,
                "patient_id": context.patient_id
            }

    async def handle_stop(self) -> Dict[str, Any]:
        """
        Handle explicit stop request.

        Returns:
            {
                "status": "stopped",
                "session_id": str,
                "recording_file": str,
                "forwarded_to_aimslab": bool
            }
        """
        async with self._lock:
            if not self._state.is_recording:
                return {
                    "status": "not_recording",
                    "session_id": None
                }

            session_id = self._state.session_id
            filepath, forwarded = await self._stop_current_session()

            return {
                "status": "stopped",
                "session_id": session_id,
                "recording_file": filepath,
                "forwarded_to_aimslab": forwarded
            }

    async def force_reset(self) -> Dict[str, Any]:
        """
        Force reset the controller state.

        Use this for crash recovery when CMED crashes and recorder
        is stuck in recording state.

        This forcefully stops all components and clears state.
        """
        logger.warning("FORCE RESET requested")

        try:
            # Force stop recorder if running
            if self._recorder:
                try:
                    self._recorder.stop_recording(str(self.recordings_dir))
                except:
                    pass

            # Force stop splitter
            if self._splitter:
                try:
                    self._splitter.stop()
                except:
                    pass

            # Force stop uploader
            if self._uploader:
                try:
                    await self._uploader.stop()
                except:
                    pass

        except Exception as e:
            logger.error(f"Error during force reset: {e}")

        # Clear state regardless of errors
        old_patient_id = self._state.patient_id
        self._state = SessionState()
        self._recorder = None
        self._splitter = None
        self._uploader = None

        # Reset recorder singleton
        AudioRecorder.reset_instance()

        logger.info("Force reset completed")

        return {
            "status": "reset_complete",
            "previous_patient_id": old_patient_id,
            "message": "Recorder state has been forcefully reset"
        }

    async def _start_new_session(self, context: SessionContext) -> Optional[str]:
        """
        Start a new recording session.

        session_id = patient_id (from CMED)
        """
        try:
            # Use patient_id as session_id
            session_id = context.patient_id

            # Reset recorder singleton
            AudioRecorder.reset_instance()

            # Initialize recorder
            self._recorder = get_recorder()
            self._recorder.set_session_info(
                patient_id=context.patient_id,
                doctor_id=context.doctor_id,
                hospital_id=context.hospital_id
            )

            # Initialize splitter
            self._splitter = SimpleSplitter(
                patient_id=context.patient_id,
                doctor_id=context.doctor_id,
                hospital_id=context.hospital_id,
                on_clip_ready=self._on_clip_ready,
                temp_dir=str(self.temp_clips_dir)
            )

            # Initialize uploader (uses patient_id as session identifier)
            self._uploader = AsyncClipUploader(
                backend_url=self.backend_url,
                patient_id=context.patient_id,
                doctor_id=context.doctor_id,
                hospital_id=context.hospital_id,
                patient_name=context.patient_name,
                patient_age=context.age,
                patient_gender=context.gender,
                health_screening=context.health_screening,
                ner_webhook_url=context.ner_webhook_url,
                status_webhook_url=context.status_webhook_url
            )

            logger.info(f"NER Webhook URL: {context.ner_webhook_url}")
            self._uploader.set_callbacks(
                on_upload_complete=self._on_upload_complete,
                on_session_created=self._on_session_created
            )

            # Connect recorder to splitter
            self._recorder.add_chunk_callback(self._splitter.process_chunk)

            # Start components
            start_time = datetime.now()
            self._splitter.start(start_time)
            await self._uploader.start()
            self._recorder.start_recording()

            # Update state
            self._state.is_recording = True
            self._state.session_id = session_id  # Same as patient_id
            self._state.patient_id = context.patient_id
            self._state.patient_name = context.patient_name
            self._state.start_time = start_time
            self._state.context = context

            logger.info(f"Session started for patient {context.patient_id}")
            logger.info(f"Session ID (patient_id): {session_id}")

            return session_id

        except Exception as e:
            logger.error(f"Failed to start session: {e}")
            await self._cleanup()
            return None

    async def _stop_current_session(self) -> tuple:
        """
        Stop the current recording session.

        Returns:
            (recording_filepath, forwarded_to_aimslab)
        """
        filepath = None
        forwarded = False

        try:
            # Stop recorder
            if self._recorder:
                if self._splitter:
                    self._recorder.remove_chunk_callback(self._splitter.process_chunk)
                filepath = self._recorder.stop_recording(str(self.recordings_dir))

            # Stop splitter (saves final clip)
            if self._splitter:
                self._splitter.stop()

            # Wait for uploads to complete
            if self._uploader:
                max_wait = 120
                waited = 0
                while self._uploader.is_busy() and waited < max_wait:
                    logger.info(f"Waiting for uploads... Queue: {self._uploader.get_queue_size()}")
                    await asyncio.sleep(2)
                    waited += 2

                if waited >= max_wait:
                    logger.warning("Upload wait timeout")
                else:
                    logger.info("All uploads completed")

                await self._uploader.stop()

            # Forward recording to AIMS LAB server
            if filepath and self._forwarder and self._state.context:
                logger.info(f"Forwarding recording to AIMS LAB server...")

                # Check if server is available
                if await self._forwarder.check_server_health():
                    result = await self._forwarder.forward_recording(
                        file_path=Path(filepath),
                        patient_id=self._state.patient_id,
                        patient_name=self._state.patient_name or "",
                        recording_date=self._state.start_time.strftime("%Y-%m-%d") if self._state.start_time else "",
                        delete_after_success=True  # Free up space on doctor's PC
                    )
                    forwarded = result.success

                    if forwarded:
                        logger.info(f"Recording forwarded to AIMS LAB: {result.remote_path}")
                    else:
                        logger.warning(f"Failed to forward recording: {result.message}")
                else:
                    logger.warning("AIMS LAB server not available, keeping local copy")

            logger.info(f"Session stopped. Recording: {filepath}, Forwarded: {forwarded}")

        except Exception as e:
            logger.error(f"Error stopping session: {e}")

        finally:
            await self._cleanup()

        return filepath, forwarded

    async def _cleanup(self):
        """Clean up session resources"""
        self._state = SessionState()
        self._recorder = None
        self._splitter = None
        self._uploader = None

    def _on_clip_ready(self, clip_info: ClipInfo):
        """Handle clip ready from splitter"""
        logger.info(f"Clip {clip_info.clip_number} ready")
        if self._uploader:
            self._uploader.queue_clip_sync(clip_info)

    def _on_upload_complete(self, result: UploadResult):
        """Handle upload complete"""
        if result.success:
            logger.info(f"Clip {result.clip_number} uploaded successfully")
        else:
            logger.warning(f"Clip {result.clip_number} upload failed: {result.error}")

    def _on_session_created(self, session_id: str):
        """Handle session creation callback from backend"""
        # Note: We use patient_id as session_id, but backend may have its own
        logger.info(f"Backend session created: {session_id}")

    def get_status(self) -> Dict[str, Any]:
        """Get current status"""
        return {
            "is_recording": self._state.is_recording,
            "session_id": self._state.session_id,  # Same as patient_id
            "patient_id": self._state.patient_id,
            "patient_name": self._state.patient_name,
            "start_time": self._state.start_time.isoformat() if self._state.start_time else None,
            "duration_seconds": self._recorder.get_duration() if self._recorder else 0
        }

    async def close(self):
        """Clean up resources"""
        if self._forwarder:
            await self._forwarder.close()
