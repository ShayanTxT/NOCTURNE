"""
Live spectrum analyzer.

Turns raw PCM blocks from the audio engine into log-spaced frequency bars
with fast-attack / slow-release smoothing and falling peak caps.
"""

from __future__ import annotations

import numpy as np

NFFT = 2048
FLOOR_DB = -74.0


class SpectrumAnalyzer:
    def __init__(self, bars: int = 60):
        self.nfft = NFFT
        self.window = np.hanning(NFFT).astype(np.float32)
        self.resize(bars)
        self._max_db = -30.0   # adaptive ceiling (auto-gain)
        self._last_seq = -1

    def resize(self, bars: int) -> None:
        bars = max(8, bars)
        if getattr(self, "levels", None) is not None and len(self.levels) == bars:
            return
        self.bars = bars
        self.levels = np.zeros(bars, dtype=np.float32)
        self.peaks = np.zeros(bars, dtype=np.float32)

    def set_bands(self, sr: int) -> None:
        """Log-spaced band edges from 35 Hz up to min(16 kHz, Nyquist)."""
        f_lo, f_hi = 35.0, min(16000.0, sr / 2 - 100)
        self.edges = np.geomspace(f_lo, max(f_hi, f_lo * self.bars), self.bars + 1)
        self.freqs = np.fft.rfftfreq(self.nfft, d=1.0 / sr)

    def update(self, block: np.ndarray, sr: int, seq: int) -> bool:
        """Feed a fresh PCM block. Returns True when new data was processed."""
        if seq == self._last_seq:
            return False
        self._last_seq = seq
        if not hasattr(self, "edges"):
            self.set_bands(sr)

        seg = np.asarray(block, dtype=np.float32)[: self.nfft]
        if len(seg) < self.nfft:
            seg = np.pad(seg, (0, self.nfft - len(seg)))
        mag = np.abs(np.fft.rfft(seg * self.window)) + 1e-7
        db = 20.0 * np.log10(mag)

        # adaptive ceiling: track the loudest band, decay it slowly
        frame_max = float(db.max())
        self._max_db = max(frame_max, self._max_db - 0.25)

        span = max(6.0, self._max_db - FLOOR_DB)
        idx = np.clip(np.searchsorted(self.edges, self.freqs) - 1, 0, self.bars - 1)
        norms = np.clip((db - FLOOR_DB) / span, 0.0, 1.0)

        target = np.zeros(self.bars, dtype=np.float32)
        np.maximum.at(target, idx, norms)

        # fast attack, exponential release
        self.levels = np.maximum(target, self.levels * 0.78)
        self.peaks = np.maximum(self.peaks - 0.035, self.levels)
        return True

    def decay(self) -> None:
        """Smoothly fall towards zero (used while paused)."""
        self.levels *= 0.72
        self.peaks = np.maximum(self.peaks - 0.035, self.levels)

    def snapshot(self) -> tuple[np.ndarray, np.ndarray]:
        return self.levels, self.peaks
