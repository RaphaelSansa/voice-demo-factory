"""Speaker and microphone for live sessions, through sounddevice.

The SDK's default interface needs PyAudio, which needs PortAudio installed on
the system. sounddevice ships PortAudio in its wheel, so `pip install` is enough.
"""

from __future__ import annotations

import queue
import threading
from collections.abc import Callable

import sounddevice as sd
from elevenlabs.conversational_ai.conversation import AudioInterface

RATE = 16_000  # the agent speaks and listens in 16-bit PCM mono at 16 kHz
INPUT_CHUNK = 4_000  # 250 ms, as the SDK recommends


class SoundDeviceAudio(AudioInterface):
    """Plays the agent through the speakers; with `mic=False`, only listens (scenarios)."""

    def __init__(self, mic: bool = True) -> None:
        self.mic = mic
        self._chunks: queue.Queue[bytes] = queue.Queue()
        self._pending = b""
        self._idle = threading.Event()
        self._idle.set()
        self._streams: list[sd.RawInputStream | sd.RawOutputStream] = []

    def start(self, input_callback: Callable[[bytes], None]) -> None:
        out = sd.RawOutputStream(samplerate=RATE, channels=1, dtype="int16", callback=self._play)
        self._streams.append(out)
        if self.mic:
            self._streams.append(
                sd.RawInputStream(
                    samplerate=RATE,
                    channels=1,
                    dtype="int16",
                    blocksize=INPUT_CHUNK,
                    callback=lambda data, _frames, _time, _status: input_callback(bytes(data)),
                )
            )
        for stream in self._streams:
            stream.start()

    def stop(self) -> None:
        for stream in self._streams:
            stream.stop()
            stream.close()
        self._streams.clear()

    def output(self, audio: bytes) -> None:
        self._idle.clear()
        self._chunks.put(audio)

    def interrupt(self) -> None:
        self._drain()

    def wait_until_quiet(self, timeout: float = 30.0) -> None:
        """Block until everything the agent said has been played."""
        self._idle.wait(timeout)

    def _drain(self) -> None:
        while not self._chunks.empty():
            self._chunks.get_nowait()
        self._pending = b""
        self._idle.set()

    def _play(self, outdata, frames: int, _time, _status) -> None:
        # Runs on the audio thread: fill exactly `frames` samples, silence if nothing to say.
        needed = frames * 2
        while len(self._pending) < needed and not self._chunks.empty():
            self._pending += self._chunks.get_nowait()
        chunk, self._pending = self._pending[:needed], self._pending[needed:]
        outdata[:] = chunk + b"\x00" * (needed - len(chunk))
        if not chunk and self._chunks.empty():
            self._idle.set()
