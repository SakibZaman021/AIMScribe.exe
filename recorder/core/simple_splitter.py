"""
Simple Amplitude-Based Silence Splitter
Splits audio clips between 2:50 and 3:10 minutes.
"""
import os
import wave
import logging
import struct
import math
from typing import Optional, Callable
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ClipInfo:
    filepath: str
    clip_number: int
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    is_final: bool


class SimpleSplitter:
    def __init__(
        self,
        patient_id: str,
        doctor_id: str,
        hospital_id: str,
        on_clip_ready: Callable[[ClipInfo], None],
        sample_rate: int = 32000,
        temp_dir: str = "temp_clips"
    ):
        self.patient_id = patient_id
        self.doctor_id = doctor_id
        self.hospital_id = hospital_id
        self.on_clip_ready = on_clip_ready
        self.sample_rate = sample_rate
        self.temp_dir = temp_dir

        # Configuration
        self.min_duration = 170.0  # 2m 50s
        self.max_duration = 190.0  # 3m 10s
        self.silence_threshold_db = -40.0  # dB threshold for silence
        self.min_silence_duration = 1.0    # seconds

        # State
        self._buffer = []
        self._clip_start_time = None
        self._clip_number = 1
        self._current_duration = 0.0
        self._silence_counter = 0.0
        self._running = False

        os.makedirs(temp_dir, exist_ok=True)
        logger.info(f"SimpleSplitter initialized for {patient_id}")

    def start(self, start_time: datetime):
        self._running = True
        self._clip_start_time = start_time
        self._buffer = []
        self._clip_number = 1
        self._current_duration = 0.0

    def stop(self):
        self._running = False
        # Save remaining audio as final clip
        if self._buffer:
            self._save_clip(is_final=True)

    def process_chunk(self, audio_data: bytes):
        if not self._running:
            return

        # Add to buffer
        self._buffer.append(audio_data)

        # Calculate duration (16-bit mono 32kHz: 64000 bytes/sec)
        bytes_per_sec = self.sample_rate * 2
        chunk_duration = len(audio_data) / bytes_per_sec
        self._current_duration += chunk_duration

        # 1. Check Min Duration (2:50)
        if self._current_duration < self.min_duration:
            return

        # 2. Check Max Duration (3:10) - Force Split
        if self._current_duration >= self.max_duration:
            logger.info("Max duration reached (3:10). Forcing split.")
            self._save_clip(is_final=False)
            return

        # 3. Check for Silence (Window: 2:50 - 3:10)
        is_silent = self._is_silence(audio_data)

        if is_silent:
            self._silence_counter += chunk_duration
        else:
            self._silence_counter = 0.0

        # If silence persists enough, split
        if self._silence_counter >= self.min_silence_duration:
            logger.info(f"Silence detected at {self._current_duration:.1f}s. Splitting.")
            self._save_clip(is_final=False)
            self._silence_counter = 0.0

    def _is_silence(self, audio_data: bytes) -> bool:
        """Calculate RMS amplitude to detect silence"""
        try:
            count = len(audio_data) // 2
            format_str = f"{count}h"
            samples = struct.unpack(format_str, audio_data)

            sum_squares = sum(s * s for s in samples)
            rms = math.sqrt(sum_squares / count) if count > 0 else 0

            if rms > 0:
                db = 20 * math.log10(rms / 32768.0)
            else:
                db = -96.0

            return db < self.silence_threshold_db

        except Exception:
            return False

    def _save_clip(self, is_final: bool):
        """Save buffer to wav file and notify"""
        if not self._buffer:
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.patient_id}_{self.doctor_id}_{self.hospital_id}_clip{self._clip_number}_{timestamp}.wav"
        filepath = os.path.join(self.temp_dir, filename)

        try:
            full_data = b"".join(self._buffer)

            with wave.open(filepath, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(self.sample_rate)
                wf.writeframes(full_data)

            duration = len(full_data) / (self.sample_rate * 2)

            info = ClipInfo(
                filepath=filepath,
                clip_number=self._clip_number,
                start_time=self._clip_start_time,
                end_time=datetime.now(),
                duration_seconds=duration,
                is_final=is_final
            )

            logger.info(f"Saved clip {self._clip_number}: {filepath} ({duration:.1f}s)")
            self.on_clip_ready(info)

            # Reset state for next clip
            self._buffer = []
            self._current_duration = 0.0
            self._clip_number += 1
            self._clip_start_time = datetime.now()

        except Exception as e:
            logger.error(f"Failed to save clip: {e}")
