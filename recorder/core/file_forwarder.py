"""
File Forwarder
Forwards audio files to AIMS LAB server after recording completes.
This frees up space on the doctor's PC.
"""
import logging
import asyncio
import aiohttp
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ForwardResult:
    """Result of file forwarding"""
    success: bool
    message: str
    remote_path: Optional[str] = None


class FileForwarder:
    """
    Forwards audio files to AIMS LAB server.
    After successful forwarding, deletes local copy to save space.
    """

    def __init__(self, aimslab_server_url: str = "http://localhost:7000"):
        self.aimslab_server_url = aimslab_server_url
        self._http_session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        if self._http_session is None or self._http_session.closed:
            self._http_session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=300)  # 5 min timeout for large files
            )
        return self._http_session

    async def close(self):
        """Close HTTP session"""
        if self._http_session and not self._http_session.closed:
            await self._http_session.close()

    async def check_server_health(self) -> bool:
        """Check if AIMS LAB server is reachable"""
        try:
            session = await self._get_session()
            async with session.get(f"{self.aimslab_server_url}/health") as response:
                return response.status == 200
        except Exception as e:
            logger.warning(f"AIMS LAB server not reachable: {e}")
            return False

    async def forward_recording(
        self,
        file_path: Path,
        patient_id: str,
        patient_name: str = "",
        recording_date: str = "",
        delete_after_success: bool = True
    ) -> ForwardResult:
        """
        Forward a recording file to AIMS LAB server.

        Args:
            file_path: Path to the recording file
            patient_id: Patient ID
            patient_name: Patient name
            recording_date: Recording date
            delete_after_success: If True, delete local file after successful upload

        Returns:
            ForwardResult with success status
        """
        if not file_path.exists():
            return ForwardResult(
                success=False,
                message=f"File not found: {file_path}"
            )

        try:
            session = await self._get_session()

            # Prepare multipart form data
            data = aiohttp.FormData()
            data.add_field(
                'file',
                open(file_path, 'rb'),
                filename=file_path.name,
                content_type='audio/wav'
            )
            data.add_field('patient_id', patient_id)
            data.add_field('patient_name', patient_name)
            data.add_field('recording_date', recording_date)

            file_size_mb = file_path.stat().st_size / (1024 * 1024)
            logger.info(f"Forwarding recording to AIMS LAB: {file_path.name} ({file_size_mb:.2f} MB)")

            async with session.post(
                f"{self.aimslab_server_url}/receive-recording",
                data=data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    remote_path = result.get("file_path", "")

                    logger.info(f"Recording forwarded successfully: {remote_path}")

                    # Delete local file to save space on doctor's PC
                    if delete_after_success:
                        try:
                            file_path.unlink()
                            logger.info(f"Deleted local file: {file_path}")
                        except Exception as e:
                            logger.warning(f"Failed to delete local file: {e}")

                    return ForwardResult(
                        success=True,
                        message="Recording forwarded to AIMS LAB server",
                        remote_path=remote_path
                    )
                else:
                    error_text = await response.text()
                    logger.error(f"Forward failed: {response.status} - {error_text}")
                    return ForwardResult(
                        success=False,
                        message=f"Server error: {response.status}"
                    )

        except aiohttp.ClientError as e:
            logger.error(f"Connection error forwarding recording: {e}")
            return ForwardResult(
                success=False,
                message=f"Connection error: {e}"
            )
        except Exception as e:
            logger.error(f"Error forwarding recording: {e}")
            return ForwardResult(
                success=False,
                message=str(e)
            )

    async def forward_clip(
        self,
        file_path: Path,
        patient_id: str,
        clip_index: int,
        delete_after_success: bool = True
    ) -> ForwardResult:
        """
        Forward a clip file to AIMS LAB server.
        """
        if not file_path.exists():
            return ForwardResult(
                success=False,
                message=f"File not found: {file_path}"
            )

        try:
            session = await self._get_session()

            data = aiohttp.FormData()
            data.add_field(
                'file',
                open(file_path, 'rb'),
                filename=file_path.name,
                content_type='audio/wav'
            )
            data.add_field('patient_id', patient_id)
            data.add_field('clip_index', str(clip_index))

            logger.info(f"Forwarding clip {clip_index} to AIMS LAB: {file_path.name}")

            async with session.post(
                f"{self.aimslab_server_url}/receive-clip",
                data=data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    remote_path = result.get("file_path", "")

                    if delete_after_success:
                        try:
                            file_path.unlink()
                            logger.debug(f"Deleted local clip: {file_path}")
                        except Exception as e:
                            logger.warning(f"Failed to delete local clip: {e}")

                    return ForwardResult(
                        success=True,
                        message="Clip forwarded",
                        remote_path=remote_path
                    )
                else:
                    error_text = await response.text()
                    return ForwardResult(
                        success=False,
                        message=f"Server error: {response.status}"
                    )

        except Exception as e:
            logger.error(f"Error forwarding clip: {e}")
            return ForwardResult(
                success=False,
                message=str(e)
            )

    async def create_session_in_backend(
        self,
        patient_id: str,
        patient_name: str,
        age: str,
        gender: str,
        doctor_id: str,
        hospital_id: str,
        health_screening: Dict[str, Any],
        recording_date: str,
        start_time: str
    ) -> Optional[str]:
        """
        Create a session in the AIMScribe backend via AIMS LAB server.
        Returns the backend session ID.
        """
        try:
            session = await self._get_session()

            payload = {
                "patient_id": patient_id,
                "patient_name": patient_name,
                "age": age,
                "gender": gender,
                "doctor_id": doctor_id,
                "hospital_id": hospital_id,
                "health_screening": health_screening,
                "recording_date": recording_date,
                "start_time": start_time
            }

            logger.info(f"Creating backend session for patient: {patient_id}")

            async with session.post(
                f"{self.aimslab_server_url}/create-session",
                json=payload
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    backend_session_id = result.get("backend_session_id")
                    logger.info(f"Backend session created: {backend_session_id}")
                    return backend_session_id
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to create backend session: {error_text}")
                    return None

        except Exception as e:
            logger.error(f"Error creating backend session: {e}")
            return None
