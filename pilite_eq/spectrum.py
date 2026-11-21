"""Turns audio into 14 bar heights for a 9-row display."""

from __future__ import annotations

import numpy as np

from .display import COLS, ROWS


def band_edges(bands: int = COLS, fmin: float = 60.0, fmax: float = 10000.0) -> np.ndarray:
    """Log-spaced band edges, so each band covers the same musical interval."""
    return np.geomspace(fmin, fmax, bands + 1)


class Analyzer:
    """Power in each band, in dB relative to a full-scale sine."""

    def __init__(self, rate: int = 22050, n_fft: int = 2048, bands: int = COLS,
                 fmin: float = 60.0, fmax: float = 10000.0):
        if fmax >= rate / 2:
            raise ValueError("fmax must be below half the sample rate")
        self.n_fft = n_fft
        self.window = np.hanning(n_fft)
        freqs = np.fft.rfftfreq(n_fft, 1.0 / rate)
        edges = band_edges(bands, fmin, fmax)
        self.masks = []
        for lo, hi in zip(edges[:-1], edges[1:]):
            mask = (freqs >= lo) & (freqs < hi)
            if not mask.any():  # band narrower than one bin: use the nearest bin
                mask = np.zeros_like(mask)
                mask[np.argmin(np.abs(freqs - np.sqrt(lo * hi)))] = True
            self.masks.append(mask)
        # Total spectral energy of a full-scale sine (Parseval), so a band
        # holding one whole sine reads 0 dB.
        self.ref = n_fft * float(np.sum(self.window ** 2)) / 4

    def band_db(self, samples: np.ndarray) -> np.ndarray:
        """samples: float array of the last n_fft samples, range -1..1."""
        spec = np.abs(np.fft.rfft(samples * self.window)) ** 2
        # Summing (not averaging) the bins in each band makes pink-ish music
        # come out roughly level across the bands.
        power = np.array([spec[m].sum() for m in self.masks])
        return 10.0 * np.log10(power / self.ref + 1e-12)


class Meter:
    """Maps band levels (dB) to bar heights with automatic gain, a fast rise,
    a slower fall, and peak dots that hang for a moment before dropping."""

    def __init__(self, bands: int = COLS, rows: int = ROWS, range_db: float = 40.0,
                 gate_db: float = -65.0, agc_fall_db: float = 3.0,
                 fall_rows: float = 18.0, peak_hold: float = 0.6,
                 peak_fall_rows: float = 8.0):
        self.rows = rows
        self.range_db = range_db          # dB shown from bottom to top of a bar
        self.gate_db = gate_db            # quieter than this counts as silence
        self.agc_fall_db = agc_fall_db    # dB/s the gain recovers after loud bits
        self.fall_rows = fall_rows        # rows/s a bar drops
        self.peak_hold = peak_hold        # s a peak dot waits before falling
        self.peak_fall_rows = peak_fall_rows
        self.top = gate_db + range_db     # level that fills a bar
        self.heights = np.zeros(bands)
        self.peaks = np.zeros(bands)
        self.peak_age = np.zeros(bands)

    def update(self, db: np.ndarray, dt: float) -> tuple[np.ndarray, np.ndarray]:
        loudest = float(db.max())
        self.top = max(loudest, self.top - self.agc_fall_db * dt, self.gate_db + self.range_db)
        if loudest < self.gate_db:
            target = np.zeros_like(db)
        else:
            target = (db - (self.top - self.range_db)) / self.range_db * self.rows
            target = np.clip(target, 0.0, self.rows)

        fallen = self.heights - self.fall_rows * dt
        self.heights = np.maximum(target, fallen)

        self.peak_age += dt
        rising = self.heights >= self.peaks
        self.peaks[rising] = self.heights[rising]
        self.peak_age[rising] = 0.0
        dropping = self.peak_age > self.peak_hold
        self.peaks[dropping] = np.maximum(
            self.peaks[dropping] - self.peak_fall_rows * dt, self.heights[dropping])
        return self.heights, self.peaks


def bars_grid(heights: np.ndarray, peaks: np.ndarray | None = None,
              rows: int = ROWS) -> list[list[bool]]:
    """grid[row][col] with bars growing up from the bottom row, plus a peak dot
    where the peak sits above the bar."""
    lit = np.rint(heights).astype(int)
    grid = [[False] * len(heights) for _ in range(rows)]
    for c, h in enumerate(lit):
        for k in range(min(h, rows)):
            grid[rows - 1 - k][c] = True
        if peaks is not None:
            p = int(np.rint(peaks[c]))
            if p > h and p >= 1:
                grid[rows - min(p, rows)][c] = True
    return grid
