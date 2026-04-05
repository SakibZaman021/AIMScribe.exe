"""
Async Clip Uploader Module
Uploads audio clips to AIMScribe backend using presigned MinIO URLs.
"""
import os
import asyncio
import logging
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass

import aiohttp

from core.simple_splitter import ClipInfo

logger = logging.getLogger(__name__)


@dataclass
class UploadResult:
    """Result of a clip upload"""
    success: bool
    clip_number: int
    job_id: Optional[str] = None
    error: Optional[str] = None


class AsyncClipUploader:
    """
    Async clip uploader using aiohttp.

    Upload Flow:
    1. POST /api/v1/session/create (first clip only) → session_id
    2. POST /api/v1/upload/request → presigned URL
    3. PUT to presigned URL (direct MinIO upload)
    4. POST /api/v1/upload/complete → job queued
    """

    def __init__(
        self,
        backend_url: str = "http://localhost:6000",
        patient_id: str = "",
        doctor_id: str = "",
        hospital_id: str = "",
        patient_name: str = "",
        patient_age: str = "",
        patient_gender: str = "",
        health_screening: Optional[Dict[str, Any]] = None,
        ner_webhook_url: str = "",
        status_webhook_url: str = "",
    ):
        self.backend_url = backend_url
        self.api_prefix = "/api/v1"
        self.patient_id = patient_id
        self.doctor_id = doctor_id
        self.hospital_id = hospital_id
        self.patient_name = patient_name
        self.patient_age = patient_age
        self.patient_gender = patient_gender
        self.health_screening = health_screening or {}
        # Webhook URLs for CMED integration
        self.ner_webhook_url = ner_webhook_url
        self.status_webhook_url = status_webhook_url

        # Timeouts
        self.timeout = aiohttp.ClientTimeout(total=30)
        self.upload_timeout = aiohttp.ClientTimeout(total=300)
        self.max_retries = 3
        self.retry_delay = 2.0

        # Session state
        self.session_id: Optional[str] = None
        self._session_created = False

        # Upload queue
        self._upload_queue: asyncio.Queue[ClipInfo] = asyncio.Queue()
        self._running = False
        self._upload_task: Optional[asyncio.Task] = None
        self._uploading = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        # HTTP session
        self._http_session: Optional[aiohttp.ClientSession] = None

        # Callbacks
        self._on_upload_complete: Optional[Callable[[UploadResult], None]] = None
        self._on_session_created: Optional[Callable[[str], None]] = None

        logger.info(f"AsyncClipUploader initialized for patient={patient_id}")

    def _get_url(self, endpoint: str) -> str:
        """Build full URL for endpoint"""
        return f"{self.backend_url}{self.api_prefix}{endpoint}"

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
        """Upload a single clip"""
        clip_number = clip_info.clip_number

        try:
            # Step 1: Create session (first clip only)
            if not self._session_created:
                if not await self._create_session():
                    return UploadResult(
                        success=False,
                        clip_number=clip_number,
                        error="Failed to create session"
                    )

            # Step 2: Request presigned URL
            upload_url, object_key = await self._request_upload_url(clip_number)
            if not upload_url:
                return UploadResult(
                    success=False,
                    clip_number=clip_number,
                    error="Failed to get presigned URL"
                )

            # Step 3: Upload to MinIO
            if not await self._upload_to_minio(clip_info.filepath, upload_url):
                return UploadResult(
                    success=False,
                    clip_number=clip_number,
                    error="Failed to upload to MinIO"
                )

            # Step 4: Notify completion
            job_id = await self._notify_upload_complete(
                clip_number, object_key, clip_info.is_final
            )
            if not job_id:
                return UploadResult(
                    success=False,
                    clip_number=clip_number,
                    error="Failed to notify upload completion"
                )

            # Clean up temp file
            try:
                os.remove(clip_info.filepath)
            except Exception as e:
                logger.warning(f"Failed to delete temp clip: {e}")

            return UploadResult(
                success=True,
                clip_number=clip_number,
                job_id=job_id
            )

        except Exception as e:
            logger.error(f"Clip upload error: {e}")
            return UploadResult(
                success=False,
                clip_number=clip_number,
                error=str(e)
            )

    async def _create_session(self) -> bool:
        """Create a new session on the backend"""
        url = self._get_url("/session/create")

        payload = {
            "patient_id": self.patient_id,
            "doctor_id": self.doctor_id,
            "hospital_id": self.hospital_id,
            "patient_name": self.patient_name,
            "age": self.patient_age,
            "gender": self.patient_gender,
            "health_screening": self.health_screening if self.health_screening else {},
            # Webhook URLs for CMED integration
            "ner_webhook_url": self.ner_webhook_url,
            "status_webhook_url": self.status_webhook_url
        }

        logger.info(f"Creating session with webhook: {self.ner_webhook_url}")

        for attempt in range(self.max_retries):
            try:
                async with self._http_session.post(
                    url,
                    json=payload,
                    timeout=self.timeout
                ) as response:
                    if response.ok:
                        data = await response.json()
                        self.session_id = data.get("session_id")
                        self._session_created = True

                        logger.info(f"Session created: {self.session_id}")

                        if self._on_session_created:
                            self._on_session_created(self.session_id)

                        return True

                    error_body = await response.text()
                    logger.warning(f"Session create failed: {response.status} - {error_body}")

            except asyncio.TimeoutError:
                logger.warning(f"Session create timeout (attempt {attempt + 1})")
            except Exception as e:
                logger.error(f"Session create error: {e}")

            if attempt < self.max_retries - 1:
                await asyncio.sleep(self.retry_delay * (attempt + 1))

        return False

    async def _request_upload_url(self, clip_number: int) -> tuple[Optional[str], Optional[str]]:
        """Request presigned upload URL"""
        url = self._get_url("/upload/request")

        payload = {
            "session_id": self.session_id,
            "clip_number": clip_number
        }

        for attempt in range(self.max_retries):
            try:
                async with self._http_session.post(
                    url,
                    json=payload,
                    timeout=self.timeout
                ) as response:
                    if response.ok:
                        data = await response.json()
                        upload_url = data.get("upload_url")
                        object_key = data.get("object_key")

                        logger.info(f"Got presigned URL for clip {clip_number}")
                        return upload_url, object_key

                    logger.warning(f"Upload request failed: {response.status}")

            except asyncio.TimeoutError:
                logger.warning(f"Upload request timeout (attempt {attempt + 1})")
            except Exception as e:
                logger.error(f"Upload request error: {e}")

            if attempt < self.max_retries - 1:
                await asyncio.sleep(self.retry_delay * (attempt + 1))

        return None, None

    async def _upload_to_minio(self, filepath: str, upload_url: str) -> bool:
        """Upload file directly to MinIO"""
        for attempt in range(self.max_retries):
            try:
                with open(filepath, 'rb') as f:
                    file_data = f.read()

                async with self._http_session.put(
                    upload_url,
                    data=file_data,
                    headers={'Content-Type': 'audio/wav'},
                    timeout=self.upload_timeout
                ) as response:
                    if response.ok:
                        logger.info(f"Uploaded to MinIO: {filepath}")
                        return True

                    logger.warning(f"MinIO upload failed: {response.status}")

            except asyncio.TimeoutError:
                logger.warning(f"MinIO upload timeout (attempt {attempt + 1})")
            except Exception as e:
                logger.error(f"MinIO upload error: {e}")

            if attempt < self.max_retries - 1:
                await asyncio.sleep(self.retry_delay * (attempt + 1))

        return False

    async def _notify_upload_complete(
        self, clip_number: int, object_key: str, is_final: bool
    ) -> Optional[str]:
        """Notify backend that upload is complete"""
        url = self._get_url("/upload/complete")

        payload = {
            "session_id": self.session_id,
            "clip_number": clip_number,
            "object_key": object_key,
            "is_final": is_final
        }

        for attempt in range(self.max_retries):
            try:
                async with self._http_session.post(
                    url,
                    json=payload,
                    timeout=self.timeout
                ) as response:
                    if response.ok:
                        data = await response.json()
                        job_id = data.get("job_id")

                        logger.info(f"Upload complete: clip {clip_number}, job={job_id}")
                        return job_id

                    logger.warning(f"Upload complete failed: {response.status}")

            except asyncio.TimeoutError:
                logger.warning(f"Upload complete timeout (attempt {attempt + 1})")
            except Exception as e:
                logger.error(f"Upload complete error: {e}")

            if attempt < self.max_retries - 1:
                await asyncio.sleep(self.retry_delay * (attempt + 1))

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
