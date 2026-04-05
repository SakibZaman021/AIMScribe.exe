"""
Audio Recorder Module
Records audio from microphone at 32kHz, mono, 16-bit.
Feeds audio to splitter and accumulates full recording.
"""
import os
import wave
import threading
import logging
from datetime import datetime
from typing import Optional, Callable, List

import pyaudio

logger = logging.getLogger(__name__)


class AudioRecorder:
    """
    Audio recorder using PyAudio.
    - Records at 32kHz, mono, 16-bit
    - Thread-safe with pause/resume support
    - Feeds audio chunks to splitter callback
    - Accumulates full recording for final file
    """

    _instance: Optional["AudioRecorder"] = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True

        # Audio settings
        self.sample_rate = 32000
        self.channels = 1
        self.sample_width = 2  # 16-bit
        self.chunk_size = 1024
        self.format = pyaudio.paInt16

        # State
        self._recording = False
        self._paused = False
        self._stream: Optional[pyaudio.Stream] = None
        self._pyaudio: Optional[pyaudio.PyAudio] = None

        # Locks
        self._state_lock = threading.Lock()
        self._data_lock = threading.Lock()

        # Audio buffers
        self._full_recording: List[bytes] = []
        self._chunk_callbacks: List[Callable[[bytes], None]] = []

        # Recording metadata
        self._start_time: Optional[datetime] = None
        self._recording_thread: Optional[threading.Thread] = None

        # Session info
        self.patient_id: str = ""
        self.doctor_id: str = ""
        self.hospital_id: str = ""

        logger.info(f"AudioRecorder initialized: {self.sample_rate}Hz, {self.channels}ch, 16-bit")

    @classmethod
    def get_instance(cls) -> "AudioRecorder":
        """Get singleton instance"""
        return cls()

    @classmethod
    def reset_instance(cls):
        """Reset singleton instance (for new recording)"""
        with cls._lock:
            if cls._instance:
                cls._instance._initialized = False
            cls._instance = None

    def add_chunk_callback(self, callback: Callable[[bytes], None]):
        """Add callback to receive audio chunks"""
        with self._data_lock:
            if callback not in self._chunk_callbacks:
                self._chunk_callbacks.append(callback)

    def remove_chunk_callback(self, callback: Callable[[bytes], None]):
        """Remove chunk callback"""
        with self._data_lock:
            if callback in self._chunk_callbacks:
                self._chunk_callbacks.remove(callback)

    def set_session_info(self, patient_id: str, doctor_id: str, hospital_id: str):
        """Set session info for file naming"""
        self.patient_id = patient_id
        self.doctor_id = doctor_id
        self.hospital_id = hospital_id

    def start_recording(self) -> bool:
        """Start recording audio."""
        with self._state_lock:
            if self._recording:
                logger.warning("Already recording")
                return False

            try:
                self._pyaudio = pyaudio.PyAudio()
                self._stream = self._pyaudio.open(
                    format=self.format,
                    channels=self.channels,
                    rate=self.sample_rate,
                    input=True,
                    frames_per_buffer=self.chunk_size
                )

                with self._data_lock:
                    self._full_recording.clear()

                self._recording = True
                self._paused = False
                self._start_time = datetime.now()

                self._recording_thread = threading.Thread(
                    target=self._recording_loop,
                    daemon=True,
                    name="AudioRecorderThread"
                )
                self._recording_thread.start()

                logger.info("Recording started")
                return True

            except Exception as e:
                logger.error(f"Failed to start recording: {e}")
                self._cleanup_stream()
                return False

    def _recording_loop(self):
        """Main recording loop - runs in separate thread"""
        while self._recording:
            if self._paused:
                threading.Event().wait(0.01)
                continue

            try:
                data = self._stream.read(self.chunk_size, exception_on_overflow=False)

                with self._data_lock:
                    self._full_recording.append(data)

                    for callback in self._chunk_callbacks:
                        try:
                            callback(data)
                        except Exception as e:
                            logger.error(f"Callback error: {e}")

            except Exception as e:
                if self._recording:
                    logger.error(f"Recording error: {e}")
                break

    def is_recording(self) -> bool:
        """Check if currently recording"""
        return self._recording

    def get_duration(self) -> float:
        """Get current recording duration in seconds"""
        if not self._start_time:
            return 0.0
        with self._data_lock:
            total_frames = len(self._full_recording) * self.chunk_size
            return total_frames / self.sample_rate

    def get_start_time(self) -> Optional[datetime]:
        """Get recording start time"""
        return self._start_time

    def stop_recording(self, recordings_dir: str = "recordings") -> Optional[str]:
        """Stop recording and save the full audio file."""
        with self._state_lock:
            if not self._recording:
                logger.warning("Not recording")
                return None

            self._recording = False
            self._paused = False

        if self._recording_thread:
            self._recording_thread.join(timeout=2.0)

        self._cleanup_stream()

        end_time = datetime.now()
        filepath = self._save_full_recording(end_time, recordings_dir)

        return filepath

    def _cleanup_stream(self):
        """Clean up PyAudio stream"""
        try:
            if self._stream:
                self._stream.stop_stream()
                self._stream.close()
                self._stream = None
        except Exception as e:
            logger.error(f"Error closing stream: {e}")

        try:
            if self._pyaudio:
                self._pyaudio.terminate()
                self._pyaudio = None
        except Exception as e:
            logger.error(f"Error terminating PyAudio: {e}")

    def _save_full_recording(self, end_time: datetime, recordings_dir: str) -> Optional[str]:
        """Save the full recording to a WAV file"""
        if not self._full_recording:
            logger.warning("No audio data to save")
            return None

        try:
            os.makedirs(recordings_dir, exist_ok=True)

            start_str = self._start_time.strftime("%H_%M")
            end_str = end_time.strftime("%H_%M")
            date_str = self._start_time.strftime("%Y_%m_%d")

            filename = f"{self.patient_id}_{self.doctor_id}_{self.hospital_id}_{start_str}_{end_str}_{date_str}.wav"
            filepath = os.path.join(recordings_dir, filename)

            with self._data_lock:
                audio_data = b"".join(self._full_recording)

            with wave.open(filepath, "wb") as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(self.sample_width)
                wf.setframerate(self.sample_rate)
                wf.writeframes(audio_data)

            logger.info(f"Full recording saved: {filepath} ({len(audio_data)} bytes)")
            return filepath

        except Exception as e:
            logger.error(f"Failed to save recording: {e}")
            return None


def get_recorder() -> AudioRecorder:
    """Get the singleton recorder instance"""
    return AudioRecorder.get_instance()
