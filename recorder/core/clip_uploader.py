"""
Async Clip Uploader Module
Uploads audio clips to R2 using presigned URLs from backend.

Flow:
1. POST /session/create → Create session on backend
2. POST /upload/request → Get presigned URL for clip
3. PUT to presigned URL → Upload clip directly to R2
4. POST /upload/complete → Notify backend to queue transcription
"""
import os
import asyncio
import logging
import hashlib
from datetime import datetime
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass

import aiohttp

from core.simple_splitter import ClipInfo
from config import config

logger = logging.getLogger(__name__)


@dataclass
class UploadResult:
    """Result of a clip upload"""
    success: bool
    clip_number: int
    job_id: Optional[str] = None
    object_key: Optional[str] = None
    error: Optional[str] = None


class AsyncClipUploader:
    """
    Async clip uploader - uses presigned URLs for secure R2 uploads.

    Security: No R2 credentials stored on client.
    Backend generates presigned URLs with 5-minute expiry.

    Session ID format: PatientID_DoctorID_HospitalID_YYYYMMDD
    R2 path: audio/{session_id}/clip_{number}.wav
    """

    def __init__(
        self,
        backend_url: str = None,
        patient_id: str = "",
        doctor_id: str = "",
        hospital_id: str = "",
        patient_name: str = "",
        patient_age: str = "",
        patient_gender: str = "",
        health_screening: Optional[Dict[str, Any]] = None,
        ner_webhook_url: str = "",
        status_webhook_url: str = "",
        api_key: str = "",
    ):
        self.backend_url = backend_url or config.backend.base_url
        self.api_prefix = config.backend.api_prefix
        self.patient_id = patient_id
        self.doctor_id = doctor_id
        self.hospital_id = hospital_id
        self.patient_name = patient_name
        self.patient_age = patient_age
        self.patient_gender = patient_gender
        self.health_screening = health_screening or {}
        self.ner_webhook_url = ner_webhook_url
        self.status_webhook_url = status_webhook_url
        self.api_key = api_key

        # Generate session_id: PatientID_DoctorID_HospitalID_Date
        date_str = datetime.now().strftime("%Y%m%d")
        self.session_id = f"{patient_id}_{doctor_id}_{hospital_id}_{date_str}"

        # Timeouts for backend calls
        self.timeout = aiohttp.ClientTimeout(total=30)
        self.upload_timeout = aiohttp.ClientTimeout(total=300)  # 5 min for file upload
        self.max_retries = 3
        self.retry_delay = 2.0

        # Session created flag (for first clip)
        self._session_created = False

        # Upload queue
        self._upload_queue: asyncio.Queue[ClipInfo] = asyncio.Queue()
        self._running = False
        self._upload_task: Optional[asyncio.Task] = None
        self._uploading = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        # HTTP session for backend calls
        self._http_session: Optional[aiohttp.ClientSession] = None

        # Callbacks
        self._on_upload_complete: Optional[Callable[[UploadResult], None]] = None
        self._on_session_created: Optional[Callable[[str], None]] = None

        logger.info(f"AsyncClipUploader initialized for patient={patient_id}")
        logger.info(f"Session ID: {self.session_id}")
        logger.info(f"Backend: {self.backend_url}")

    def _get_url(self, endpoint: str) -> str:
        """Build full URL for backend endpoint"""
        return f"{self.backend_url}{self.api_prefix}{endpoint}"

    def _get_headers(self) -> Dict[str, str]:
        """Get headers including API key if configured"""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    def _generate_idempotency_key(self, clip_number: int) -> str:
        """Generate idempotency key for retry-safe uploads"""
        # Hash of session_id + clip_number ensures same key on retry
        data = f"{self.session_id}:{clip_number}"
        return hashlib.sha256(data.encode()).hexdigest()[:32]

    async def start(self):
        """Start the async uploader"""
        if self._running:
            return

        self._loop = asyncio.get_running_loop()

        connector = aiohttp.TCPConnector(limit=10, limit_per_host=5)
        self._http_session = aiohttp.ClientSession(connector=connector)

        self._running = True
        self._upload_task = asyncio.create_task(self._upload_loop())

        logger.info("AsyncClipUploader started")

    async def stop(self):
        """Stop the async uploader"""
        self._running = False

        if self._upload_task:
            self._upload_task.cancel()
            try:
                await self._upload_task
            except asyncio.CancelledError:
                pass

        if self._http_session:
            await self._http_session.close()

        logger.info("AsyncClipUploader stopped")

    def set_callbacks(
        self,
        on_upload_complete: Optional[Callable[[UploadResult], None]] = None,
        on_session_created: Optional[Callable[[str], None]] = None
    ):
        """Set callback functions"""
        self._on_upload_complete = on_upload_complete
        self._on_session_created = on_session_created

    def queue_clip_sync(self, clip_info: ClipInfo):
        """Sync wrapper to queue clip (thread-safe)"""
        if self._loop is None:
            logger.error("Cannot queue clip - event loop not set")
            return

        def _put_clip():
            try:
                self._upload_queue.put_nowait(clip_info)
                logger.info(f"Queued clip {clip_info.clip_number} for upload")
            except asyncio.QueueFull:
                logger.warning(f"Upload queue full, clip {clip_info.clip_number} dropped")

        self._loop.call_soon_threadsafe(_put_clip)

    async def _upload_loop(self):
        """Main async upload loop"""
        logger.info("Upload loop STARTED")

        while self._running:
            try:
                try:
                    clip_info = await asyncio.wait_for(
                        self._upload_queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue

                logger.info(f"Processing clip {clip_info.clip_number}")

                self._uploading = True
                try:
                    result = await self._upload_clip(clip_info)
                    logger.info(f"Clip {clip_info.clip_number} result: {result.success}")
                finally:
                    self._uploading = False

                if self._on_upload_complete:
                    self._on_upload_complete(result)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Upload loop error: {e}", exc_info=True)
                self._uploading = False

        logger.info("Upload loop ENDED")

    async def _upload_clip(self, clip_info: ClipInfo) -> UploadResult:
        """Upload a single clip using presigned URL"""
        clip_number = clip_info.clip_number
        idempotency_key = self._generate_idempotency_key(clip_number)

        try:
            # Step 1: Create session on backend (first clip only)
            if not self._session_created:
                await self._create_session()
                self._session_created = True
                if self._on_session_created:
                    self._on_session_created(self.session_id)

            # Step 2: Request presigned upload URL from backend
            presigned_data = await self._request_presigned_url(
                clip_number, idempotency_key
            )
            if not presigned_data:
                return UploadResult(
                    success=False,
                    clip_number=clip_number,
                    error="Failed to get presigned URL"
                )

            upload_url = presigned_data["upload_url"]
            object_key = presigned_data["object_key"]

            # Step 3: Upload to R2 using presigned URL (HTTP PUT)
            upload_success = await self._upload_to_presigned_url(
                clip_info.filepath, upload_url
            )
            if not upload_success:
                return UploadResult(
                    success=False,
                    clip_number=clip_number,
                    error="Failed to upload to R2"
                )

            # Step 4: Notify backend - triggers transcription job
            job_id = await self._notify_upload_complete(
                clip_number, object_key, clip_info.is_final, idempotency_key
            )

            # Clean up temp file
            try:
                os.remove(clip_info.filepath)
                logger.info(f"Deleted temp file: {clip_info.filepath}")
            except Exception as e:
                logger.warning(f"Failed to delete temp clip: {e}")

            return UploadResult(
                success=True,
                clip_number=clip_number,
                job_id=job_id,
                object_key=object_key
            )

        except Exception as e:
            logger.error(f"Clip upload error: {e}", exc_info=True)
            return UploadResult(
                success=False,
                clip_number=clip_number,
                error=str(e)
            )

    async def _create_session(self) -> bool:
        """Create session on backend (registers patient, doctor, hospital)"""
        url = self._get_url("/session/create")

        payload = {
            "session_id": self.session_id,
            "patient_id": self.patient_id,
            "doctor_id": self.doctor_id,
            "hospital_id": self.hospital_id,
            "patient_name": self.patient_name,
            "age": self.patient_age,
            "gender": self.patient_gender,
            "health_screening": self.health_screening,
            "ner_webhook_url": self.ner_webhook_url,
            "status_webhook_url": self.status_webhook_url
        }

        logger.info(f"Creating session: {self.session_id}")
        logger.info(f"Backend URL: {url}")

        for attempt in range(self.max_retries):
            try:
                async with self._http_session.post(
                    url,
                    json=payload,
                    headers=self._get_headers(),
                    timeout=self.timeout
                ) as response:
                    if response.ok:
                        data = await response.json()
                        logger.info(f"Session created on backend: {data}")
                        return True

                    error_body = await response.text()
                    logger.warning(f"Session create failed: {response.status} - {error_body}")

            except asyncio.TimeoutError:
                logger.warning(f"Session create timeout (attempt {attempt + 1})")
            except Exception as e:
                logger.error(f"Session create error: {e}")

            if attempt < self.max_retries - 1:
                await asyncio.sleep(self.retry_delay * (attempt + 1))

        logger.warning("Backend session create failed - will retry on next clip")
        return False

    async def _request_presigned_url(
        self, clip_number: int, idempotency_key: str
    ) -> Optional[Dict[str, Any]]:
        """Request presigned upload URL from backend"""
        url = self._get_url("/upload/request")

        payload = {
            "session_id": self.session_id,
            "clip_number": clip_number,
            "idempotency_key": idempotency_key
        }

        logger.info(f"Requesting presigned URL for clip {clip_number}")

        for attempt in range(self.max_retries):
            try:
                async with self._http_session.post(
                    url,
                    json=payload,
                    headers=self._get_headers(),
                    timeout=self.timeout
                ) as response:
                    if response.ok:
                        data = await response.json()
                        logger.info(f"Got presigned URL: {data.get('object_key')}")
                        return data

                    error_body = await response.text()
                    logger.warning(f"Presigned URL request failed: {response.status} - {error_body}")

            except asyncio.TimeoutError:
                logger.warning(f"Presigned URL request timeout (attempt {attempt + 1})")
            except Exception as e:
                logger.error(f"Presigned URL request error: {e}")

            if attempt < self.max_retries - 1:
                await asyncio.sleep(self.retry_delay * (attempt + 1))

        return None

    async def _upload_to_presigned_url(self, filepath: str, upload_url: str) -> bool:
        """Upload file to R2 using presigned PUT URL"""
        logger.info(f"Uploading to presigned URL...")

        for attempt in range(self.max_retries):
            try:
                # Read file and upload via PUT
                with open(filepath, 'rb') as f:
                    file_data = f.read()

                headers = {"Content-Type": "audio/wav"}

                async with self._http_session.put(
                    upload_url,
                    data=file_data,
                    headers=headers,
                    timeout=self.upload_timeout
                ) as response:
                    if response.ok or response.status == 200:
                        logger.info(f"R2 upload successful via presigned URL")
                        return True

                    error_body = await response.text()
                    logger.warning(f"Presigned upload failed: {response.status} - {error_body}")

            except asyncio.TimeoutError:
                logger.warning(f"Presigned upload timeout (attempt {attempt + 1})")
            except Exception as e:
                logger.error(f"Presigned upload error: {e}")

            if attempt < self.max_retries - 1:
                await asyncio.sleep(self.retry_delay * (attempt + 1))

        return False

    async def _notify_upload_complete(
        self, clip_number: int, object_key: str, is_final: bool, idempotency_key: str
    ) -> Optional[str]:
        """Notify backend that clip is uploaded - triggers transcription"""
        url = self._get_url("/upload/complete")

        payload = {
            "session_id": self.session_id,
            "clip_number": clip_number,
            "object_key": object_key,
            "is_final": is_final,
            "idempotency_key": idempotency_key
        }

        logger.info(f"Notifying backend: clip {clip_number}, final={is_final}")

        for attempt in range(self.max_retries):
            try:
                async with self._http_session.post(
                    url,
                    json=payload,
                    headers=self._get_headers(),
                    timeout=self.timeout
                ) as response:
                    if response.ok:
                        data = await response.json()
                        job_id = data.get("job_id")
                        logger.info(f"Backend notified: clip {clip_number}, job_id={job_id}")
                        return job_id

                    error_body = await response.text()
                    logger.warning(f"Upload complete failed: {response.status} - {error_body}")

            except asyncio.TimeoutError:
                logger.warning(f"Upload complete timeout (attempt {attempt + 1})")
            except Exception as e:
                logger.error(f"Upload complete error: {e}")

            if attempt < self.max_retries - 1:
                await asyncio.sleep(self.retry_delay * (attempt + 1))

        logger.error("Failed to notify backend - clip uploaded but not queued")
        return None

    def get_session_id(self) -> Optional[str]:
        """Get the current session ID"""
        return self.session_id

    def get_queue_size(self) -> int:
        """Get number of clips waiting to upload"""
        return self._upload_queue.qsize()

    def is_busy(self) -> bool:
        """Check if uploader is busy"""
        return self._upload_queue.qsize() > 0 or self._uploading
