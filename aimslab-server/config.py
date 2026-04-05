"""
AIMS LAB Server Configuration
This server runs on the AIMS LAB local server to receive audio files from doctor PCs.
"""
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ServerConfig:
    """Server configuration"""
    host: str = "0.0.0.0"  # Listen on all interfaces
    port: int = 7000


@dataclass
class StorageConfig:
    """Storage configuration"""
    # Base directory for storing audio files
    audio_storage_dir: Path = Path("D:/AIMSLAB_AUDIO_STORAGE")
    # Subdirectories
    recordings_dir: Path = None
    clips_dir: Path = None

    def __post_init__(self):
        self.recordings_dir = self.audio_storage_dir / "recordings"
        self.clips_dir = self.audio_storage_dir / "clips"

        # Create directories if they don't exist
        self.audio_storage_dir.mkdir(parents=True, exist_ok=True)
        self.recordings_dir.mkdir(parents=True, exist_ok=True)
        self.clips_dir.mkdir(parents=True, exist_ok=True)


@dataclass
class DatabaseConfig:
    """Database configuration for forwarding to AIMScribe backend"""
    backend_url: str = "http://localhost:6000"


# Global config instances
server_config = ServerConfig()
storage_config = StorageConfig()
db_config = DatabaseConfig()
