"""
Segmenter - cuts the audio stream into clips that upload as they are produced.

A clip closes on a silence boundary once past the minimum length, or is forced at
the maximum. Between those two points the segmenter watches for a sustained quiet
patch so cuts land in a natural gap rather than mid-sentence.

The important structural change from v1: this runs on **its own thread**, fed by a
queue. Previously `process_chunk` ran on the PyAudio callback thread and wrote up
to 12 MB of WAV synchronously inside it, which dropped frames at every clip
boundary. Now the capture thread only enqueues; loudness maths and sealing happen
here.

Commands (flush, pause, stop) travel through the same queue as audio, so they are
always processed after every chunk that preceded them. Ordering is what makes a
pause boundary exact.
"""
from __future__ import annotations

import logging
import queue
import threading
from array import array
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

logger = logging.getLogger(__name__)


# Prefer the C implementation where it exists. `audioop` is deprecated in 3.11 and
# removed in 3.13, so the pure-Python fallback is not optional.
try:  # pragma: no cover - depends on interpreter version
    import audioop  # type: ignore[import-not-found]

    def _rms(fragment: bytes, width: int) -> float:
        return float(audioop.rms(fragment, width))

except ImportError:  # pragma: no cover
    def _rms(fragment: bytes, width: int) -> float:
        if width != 2 or not fragment:
            return 0.0
        # ~150 µs per 2048-sample chunk, about 0.3% of one core at 44.1 kHz.
        samples = array("h")
        samples.frombytes(fragment[: len(fragment) - (len(fragment) % 2)])
        if not samples:
            return 0.0
        total = 0
        for value in samples:
            total += value * value
        return (total / len(samples)) ** 0.5


@dataclass(frozen=True)
class SealedSegment:
    """What the segmenter hands back for spooling."""
    pcm: bytes
    captured_start_at: datetime
    captured_end_at: datetime
    rms_mean: float
    is_final: bool


class _Command:
    """Queue sentinel so commands are ordered against the audio that precedes them."""
    __slots__ = ("kind", "done")

    def __init__(self, kind: str):
        self.kind = kind
        self.done = threading.Event()


class Segmenter:
    """
    Consumes raw PCM chunks and emits sealed segments.

    `on_segment` is called on the segmenter thread. It is expected to do the disk
    write (Spool.seal_segment) and return; uploading happens elsewhere.
    """

    def __init__(
        self,
        *,
        sample_rate: int,
        channels: int,
        sample_width: int,
        min_seconds: float,
        max_seconds: float,
        silence_rms: int,
        silence_hold_seconds: float,
        on_segment: Callable[[SealedSegment], None],
        queue_depth: int = 512,
    ):
        self.bytes_per_second = sample_rate * channels * sample_width
        self.sample_width = sample_width
        self.min_bytes = int(min_seconds * self.bytes_per_second)
        self.max_bytes = int(max_seconds * self.bytes_per_second)
        self.silence_rms = silence_rms
        self.silence_hold_bytes = int(silence_hold_seconds * self.bytes_per_second)
        self._on_segment = on_segment

        self._queue: "queue.Queue" = queue.Queue(maxsize=queue_depth)
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

        # Segment being assembled. Byte counts are integers so duration never drifts.
        self._buffer = bytearray()
        self._silence_bytes = 0
        self._rms_weighted_sum = 0.0
        self._rms_samples = 0
        self._segment_started_at: Optional[datetime] = None

        self.segments_emitted = 0
        self.dropped_chunks = 0

    # ---- lifecycle ----

    def start(self, started_at: Optional[datetime] = None) -> None:
        self._segment_started_at = started_at or datetime.now(timezone.utc)
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="Segmenter", daemon=True)
        self._thread.start()

    def set_segment_start(self, when: datetime) -> None:
        """
        Move the current segment's start timestamp.

        Used on resume: without it the next segment would be stamped as beginning
        when the previous one ended, implying continuous audio across a pause.
        """
        self._segment_started_at = when

    def submit(self, chunk: bytes) -> None:
        """
        Called from the capture thread. Raises queue.Full rather than blocking.

        AudioRecorder counts the Full case as an overrun; blocking here would stall
        PortAudio and lose the same audio with worse timing.
        """
        self._queue.put_nowait(chunk)

    def flush(self, *, is_final: bool = False, timeout: float = 30.0) -> bool:
        """
        Seal whatever is buffered. Used at pause and at stop.

        Blocks until the segmenter has drained every chunk queued before this call,
        so a pause boundary is exact rather than approximate.
        """
        command = _Command("final" if is_final else "flush")
        try:
            self._queue.put(command, timeout=5.0)
        except queue.Full:
            logger.error("Could not enqueue flush: segmenter queue is full")
            return False
        return command.done.wait(timeout=timeout)

    def stop(self, *, seal_remaining: bool = True, timeout: float = 30.0) -> None:
        if self._thread is None:
            return
        if seal_remaining:
            self.flush(is_final=True, timeout=timeout)
        self._stop.set()
        try:
            self._queue.put_nowait(_Command("stop"))
        except queue.Full:
            pass
        self._thread.join(timeout=timeout)
        self._thread = None

    # ---- worker ----

    def _run(self) -> None:
        logger.debug("Segmenter thread started")
        while True:
            try:
                item = self._queue.get(timeout=0.5)
            except queue.Empty:
                if self._stop.is_set():
                    break
                continue

            if isinstance(item, _Command):
                if item.kind in ("flush", "final"):
                    self._seal(is_final=(item.kind == "final"))
                    item.done.set()
                    continue
                if item.kind == "stop":
                    item.done.set()
                    break

            self._consume(item)

        logger.debug("Segmenter thread finished after %s segment(s)", self.segments_emitted)

    def _consume(self, chunk: bytes) -> None:
        self._buffer.extend(chunk)

        level = _rms(chunk, self.sample_width)
        self._rms_weighted_sum += level * len(chunk)
        self._rms_samples += len(chunk)

        size = len(self._buffer)

        # Below the minimum, keep accumulating regardless of how quiet it is.
        if size < self.min_bytes:
            self._silence_bytes = 0
            return

        # Hard cutoff so a continuous talker still produces regular clips.
        if size >= self.max_bytes:
            logger.debug("Segment reached maximum length; forcing a cut")
            self._seal(is_final=False)
            return

        # Inside the window, cut on a sustained quiet patch.
        if level < self.silence_rms:
            self._silence_bytes += len(chunk)
            if self._silence_bytes >= self.silence_hold_bytes:
                logger.debug("Silence boundary at %.1f s; cutting",
                             size / self.bytes_per_second)
                self._seal(is_final=False)
        else:
            self._silence_bytes = 0

    def _seal(self, *, is_final: bool) -> None:
        if not self._buffer:
            # A flush with nothing buffered is normal (pause immediately after a cut).
            if is_final:
                logger.debug("Final flush with an empty buffer; nothing to seal")
            return

        pcm = bytes(self._buffer)
        started = self._segment_started_at or datetime.now(timezone.utc)
        ended = started + timedelta(seconds=len(pcm) / self.bytes_per_second)
        mean_rms = (self._rms_weighted_sum / self._rms_samples) if self._rms_samples else 0.0

        # Reset before the callback: sealing writes to disk and could raise, and a
        # retry must not re-emit audio that is already accounted for in the chain.
        self._buffer = bytearray()
        self._silence_bytes = 0
        self._rms_weighted_sum = 0.0
        self._rms_samples = 0
        self._segment_started_at = ended

        try:
            self._on_segment(SealedSegment(
                pcm=pcm,
                captured_start_at=started,
                captured_end_at=ended,
                rms_mean=mean_rms,
                is_final=is_final,
            ))
            self.segments_emitted += 1
        except Exception as exc:
            # Losing a segment here means losing audio, so this is loud.
            logger.critical("Failed to seal segment: %s", exc, exc_info=True)
            raise

    # ---- metrics ----

    @property
    def queue_depth(self) -> int:
        return self._queue.qsize()

    @property
    def buffered_seconds(self) -> float:
        return len(self._buffer) / self.bytes_per_second


__all__ = ["Segmenter", "SealedSegment"]
