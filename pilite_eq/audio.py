"""Audio sources: a USB mic through ALSA's arecord, or a WAV file for testing."""

from __future__ import annotations

import re
import subprocess
import threading
import time
import wave

import numpy as np


def find_usb_mic() -> str:
    """ALSA name of the first capture card that isn't the Pi's own, e.g.
    'plughw:CARD=Device,DEV=0'. Card names survive reboots; numbers may not."""
    out = subprocess.run(["arecord", "-l"], capture_output=True, text=True).stdout
    cards = re.findall(r"^card \d+: (\S+) \[.*?\], device (\d+):", out, re.M)
    if not cards:
        raise SystemExit("No capture device found. Is the USB mic plugged in? "
                         "Check with: arecord -l")
    name, dev = cards[0]
    return f"plughw:CARD={name},DEV={dev}"


class Ring:
    """Keeps the most recent `size` samples."""

    def __init__(self, size: int):
        self.buf = np.zeros(size, dtype=np.float32)
        self.lock = threading.Lock()

    def push(self, chunk: np.ndarray) -> None:
        with self.lock:
            n = min(len(chunk), len(self.buf))
            self.buf = np.roll(self.buf, -n)
            self.buf[-n:] = chunk[-n:]

    def latest(self) -> np.ndarray:
        with self.lock:
            return self.buf.copy()


class MicSource:
    """Runs arecord (mono, 16-bit) and keeps the latest samples in a ring.
    plughw converts from whatever rate the mic really uses."""

    def __init__(self, device: str, rate: int, size: int, chunk: int = 512):
        self.ring = Ring(size)
        self.proc = subprocess.Popen(
            ["arecord", "-q", "-D", device, "-f", "S16_LE", "-c", "1",
             "-r", str(rate), "-t", "raw"],
            stdout=subprocess.PIPE)
        self.chunk_bytes = chunk * 2
        self.error: str | None = None
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self) -> None:
        assert self.proc.stdout is not None
        while True:
            data = self.proc.stdout.read(self.chunk_bytes)
            if not data:
                self.error = f"arecord stopped (exit code {self.proc.wait()})"
                return
            self.ring.push(np.frombuffer(data, dtype="<i2").astype(np.float32) / 32768.0)

    def latest(self) -> np.ndarray:
        if self.error:
            raise RuntimeError(self.error)
        return self.ring.latest()

    def close(self) -> None:
        self.proc.terminate()


class WavSource:
    """Plays a WAV file through the analyser at real-time pace (no sound)."""

    def __init__(self, path: str, size: int):
        with wave.open(path) as w:
            if w.getsampwidth() != 2:
                raise SystemExit("WAV must be 16-bit")
            self.rate = w.getframerate()
            raw = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
            data = raw.reshape(-1, w.getnchannels()).mean(axis=1)
        self.data = (data / 32768.0).astype(np.float32)
        self.size = size
        self.start = time.monotonic()

    @property
    def finished(self) -> bool:
        return (time.monotonic() - self.start) * self.rate >= len(self.data)

    def latest(self) -> np.ndarray:
        end = int((time.monotonic() - self.start) * self.rate)
        end = min(max(end, self.size), len(self.data))
        out = self.data[max(0, end - self.size):end]
        return np.pad(out, (self.size - len(out), 0))

    def close(self) -> None:
        pass
