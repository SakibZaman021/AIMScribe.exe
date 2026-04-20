"""
AIMScribe Recorder Configuration
System tray application that receives triggers from CMED
"""
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AudioConfig:
    """Audio recording settings"""
    sample_rate: int = 32000  # 32kHz
    channels: int = 1  # Mono
    sample_width: int = 2  # 16-bit (2 bytes)
    chunk_size: int = 1024  # Frames per buffer


@dataclass
class SplitterConfig:
    """Clip splitting parameters"""
    min_clip_duration_sec: float = 170.0  # 2 min 50 sec - start monitoring
    max_clip_duration_sec: float = 190.0  # 3 min 10 sec - hard cutoff
    silence_threshold_sec: float = 1.0  # 1 second silence to trigger split
    silence_rms_threshold: float = 500.0  # RMS threshold for silence


@dataclass
class BackendConfig:
    """AIMScribe Backend API configuration"""
    # Default to Render.com backend (production)
    # Override with AIMSCRIBE_BACKEND_URL env var for local testing
    base_url: str = "https://aimscribe-backend-render.onrender.com"
    api_prefix: str = "/api/v1"

    # Endpoints
    session_create: str = "/session/create"
    upload_request: str = "/upload/request"
    upload_complete: str = "/upload/complete"

    # Timeouts (seconds)
    request_timeout: int = 30
    upload_timeout: int = 300  # 5 minutes for large files

    # Retry settings
    max_retries: int = 3
    retry_delay: float = 2.0


@dataclass
class TriggerServerConfig:
    """Trigger API server configuration"""
    host: str = "127.0.0.1"
    port: int = 5050


@dataclass
class AimsLabServerConfig:
    """AIMS LAB local server configuration (receives audio files)"""
    base_url: str = "http://localhost:7000"
    # Set to True to forward recordings to AIMS LAB server
    # Disabled by default - enable when AIMS LAB server is running
    forward_recordings: bool = False
    # Delete local recording after successful forward
    delete_after_forward: bool = True


@dataclass
class PathConfig:
    """File and directory paths"""
    temp_clips_dir: str = "temp_clips"
    full_recordings_dir: str = "recordings"
    logs_dir: str = "logs"


@dataclass
class Config:
    """Main configuration class"""
    audio: AudioConfig = field(default_factory=AudioConfig)
    splitter: SplitterConfig = field(default_factory=SplitterConfig)
    backend: BackendConfig = field(default_factory=BackendConfig)
    trigger_server: TriggerServerConfig = field(default_factory=TriggerServerConfig)
    aimslab_server: AimsLabServerConfig = field(default_factory=AimsLabServerConfig)
    paths: PathConfig = field(default_factory=PathConfig)

    # Application info
    app_name: str = "AIMScribe Recorder"
    app_version: str = "1.0.0"

    def __post_init__(self):
        """Create necessary directories"""
        os.makedirs(self.paths.temp_clips_dir, exist_ok=True)
        os.makedirs(self.paths.full_recordings_dir, exist_ok=True)
        os.makedirs(self.paths.logs_dir, exist_ok=True)

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables"""
        config = cls()

        if os.getenv("AIMSCRIBE_BACKEND_URL"):
            config.backend.base_url = os.getenv("AIMSCRIBE_BACKEND_URL")

        if os.getenv("AIMSLAB_SERVER_URL"):
            config.aimslab_server.base_url = os.getenv("AIMSLAB_SERVER_URL")

        if os.getenv("TRIGGER_PORT"):
            config.trigger_server.port = int(os.getenv("TRIGGER_PORT"))

        return config


# Global configuration instance
config = Config.from_env()
