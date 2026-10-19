"""
Nocturne — audio engine.

Streams decoded samples to the sound device through a callback and exposes
real-time PCM taps for the spectrum visualizer.  When no audio device is
available (headless boxes, CI, missing PortAudio) the engine transparently
falls back to a *silent clock* that behaves exactly like real playback, so
the whole UI still works.
"""

from __future__ import annotations

import threading
import time

import numpy as np

try:  # pragma: no cover - depends on host machine
    import sounddevice as _sd
except Exception:  # PortAudio missing, broken install, ...
    _sd = None

try:
    import soundfile as _sf
except Exception as _e:  # pragma: no cover
    raise ImportError(
        "Nocturne requires 'soundfile' (libsndfile). pip install soundfile"
    ) from _e


class TrackLoadError(Exception):
    """Raised when a file cannot be decoded for playback."""


FILE_TOO_LARGE_MSG = "file too large for memory playback"
MAX_RAM_BYTES = 400 * 1024 * 1024  # ~50 minutes of stereo float32 @48kHz


class VisBus:
    """Latest-PCM-frame bus shared between the audio callback and the UI."""

    def __init__(self, block: int = 2048):
        self._lock = threading.Lock()
        self._data = np.zeros(block, dtype=np.float32)
        self._seq = 0

    def publish(self, mono_block: np.ndarray) -> None:
        with self._lock:
            n = min(len(mono_block), len(self._data))
            self._data[:n] = mono_block[:n]
            self._data[n:] = 0.0
            self._seq += 1

    def latest(self) -> tuple[np.ndarray, int]:
        """Return a copy of the most recent PCM block and its sequence id."""
        with self._lock:
            return self._data.copy(), self._seq


class AudioEngine:
    """Sample-accurate player for one track at a time."""

    def __init__(self, silent: bool = False, volume: float = 0.85):
        self.lock = threading.RLock()
        self.vis = VisBus()

        self._data: np.ndarray | None = None   # float32 [frames, 2]
        self._sr = 44100
        self._pos = 0                          # playback frame index
        self._playing = False
        self._ended = False
        self._envelope: np.ndarray = np.zeros(1, dtype=np.float32)

        self.volume = volume
        self.muted = False

        self.stream = None
        self.device_name: str | None = None
        self.mode: str = "device"
        self.last_error: str | None = None

        self._ticker: threading.Thread | None = None
        self._ticker_stop = threading.Event()

        self._detect_device(silent)

    # ------------------------------------------------------------------ setup
    def _detect_device(self, silent: bool) -> None:
        if _sd is None:
            self.mode = "silent"
            self.last_error = "sounddevice/PortAudio not available"
            return
        if silent:
            self.mode = "silent"
            return
        try:
            info = _sd.query_devices(kind="output")
            self.device_name = f"{info['name']}"
            self.mode = "device"
        except Exception as exc:  # no output device
            self.mode = "silent"
            self.last_error = str(exc)

    @property
    def silent(self) -> bool:
        return self.mode == "silent"

    # ------------------------------------------------------------------- load
    def load(self, path) -> dict:
        """Decode *path* into memory and prepare playback. Returns file info."""
        try:
            info = _sf.info(str(path))
            if info.frames * info.channels * 4 > MAX_RAM_BYTES:
                raise TrackLoadError(FILE_TOO_LARGE_MSG)
            data, sr = _sf.read(str(path), dtype="float32", always_2d=True)
        except TrackLoadError:
            raise
        except Exception as exc:
            raise TrackLoadError(f"cannot decode: {exc}") from exc

        # normalize channel layout to stereo
        if data.shape[1] >= 2:
            data = np.ascontiguousarray(data[:, :2])
        else:
            data = np.ascontiguousarray(np.repeat(data, 2, axis=1))

        with self.lock:
            self._data = data
            self._sr = sr
            self._pos = 0
            self._playing = False
            self._ended = False
            self._envelope = _compute_envelope(data, buckets=900)

        self._reopen_stream()
        return {
            "samplerate": sr,
            "channels": 2,
            "frames": len(data),
            "duration": len(data) / sr,
            "format": info.format,
            "subtype": info.subtype,
        }

    def unload(self) -> None:
        with self.lock:
            self._data = None
            self._pos = 0
            self._playing = False
            self._ended = False
            self._envelope = np.zeros(1, dtype=np.float32)

    @property
    def envelope(self) -> np.ndarray:
        with self.lock:
            return self._envelope

    # --------------------------------------------------------------- playback
    def _reopen_stream(self) -> None:
        """(Re)open the output stream for the current sample rate."""
        self._stop_ticker()
        if self.silent:
            self._ensure_ticker()
            return
        try:
            if self.stream is not None:
                self.stream.close()
                self.stream = None
            self.stream = _sd.OutputStream(
                samplerate=self._sr,
                channels=2,
                dtype="float32",
                blocksize=0,
                callback=self._callback,
            )
            self.stream.start()
        except Exception as exc:
            self.stream = None
            self.mode = "silent"
            self.last_error = str(exc)
            self._ensure_ticker()

    def _callback(self, outdata, frames, _time_info, _status) -> None:  # pragma: no cover
        """Real-time audio callback (runs on the PortAudio thread)."""
        with self.lock:
            if self._data is None or not self._playing:
                outdata[:] = 0.0
                self.vis.publish(_zeros(frames))
                return
            n = min(frames, len(self._data) - self._pos)
            if n > 0:
                chunk = self._data[self._pos : self._pos + n]
                outdata[:n] = chunk * self.gain
                self.vis.publish(chunk.mean(axis=1))
                self._pos += n
            if n < frames:
                outdata[n:] = 0.0
                self.vis.publish(_zeros(frames - n))
                self._playing = False
                self._ended = True

    def _ensure_ticker(self) -> None:
        """Silent-mode clock: walks through samples in real time."""
        if self._ticker is not None and self._ticker.is_alive():
            return
        self._ticker_stop.clear()
        self._ticker = threading.Thread(
            target=self._tick_loop, name="nocturne-silent", daemon=True
        )
        self._ticker.start()

    def _stop_ticker(self) -> None:
        self._ticker_stop.set()
        if self._ticker is not None:
            self._ticker.join(timeout=1.0)
            self._ticker = None

    def _tick_loop(self) -> None:
        """Silent-mode clock. Sleeps deeply when idle; paces in real time
        while playing (sample rate re-read every loop)."""
        block = 512
        next_t = time.perf_counter()
        while not self._ticker_stop.is_set():
            with self.lock:
                playing = self._playing and self._data is not None
                if playing:
                    sr = self._sr
                    n = min(block, len(self._data) - self._pos)
                    if n > 0:
                        self.vis.publish(
                            self._data[self._pos : self._pos + n].mean(axis=1)
                        )
                        self._pos += n
                    if self._pos >= len(self._data):
                        self._playing = False
                        self._ended = True
            if not playing:
                # idle: nothing to advance — poll slowly, nearly zero cost
                self._ticker_stop.wait(0.1)
                next_t = time.perf_counter()
                continue
            next_t += block / sr
            delay = next_t - time.perf_counter()
            if delay > 0:
                self._ticker_stop.wait(delay)
            else:
                next_t = time.perf_counter()

    # --------------------------------------------------------------- controls
    @property
    def gain(self) -> float:
        return 0.0 if self.muted else float(self.volume) ** 2  # perceptual-ish

    def play(self) -> None:
        with self.lock:
            if self._data is None:
                return
            if self._pos >= len(self._data):
                self._pos = 0
            self._ended = False
            self._playing = True

    def pause(self) -> None:
        with self.lock:
            self._playing = False

    def toggle(self) -> bool:
        with self.lock:
            if self._playing:
                self.pause()
            else:
                self.play()
            return self._playing

    def stop(self) -> None:
        with self.lock:
            self._playing = False
            self._pos = 0
            self._ended = False

    def seek(self, seconds: float) -> None:
        with self.lock:
            if self._data is None:
                return
            self._pos = int(np.clip(seconds, 0.0, self.duration) * self._sr)
            if self._pos < len(self._data):
                self._ended = False

    def seek_relative(self, seconds: float) -> None:
        self.seek(self.position + seconds)

    # ------------------------------------------------------------- properties
    @property
    def playing(self) -> bool:
        with self.lock:
            return self._playing

    @property
    def loaded(self) -> bool:
        with self.lock:
            return self._data is not None

    @property
    def duration(self) -> float:
        with self.lock:
            return (len(self._data) / self._sr) if self._data is not None else 0.0

    @property
    def position(self) -> float:
        with self.lock:
            return min(self._pos / self._sr, self.duration) if self._data is not None else 0.0

    @property
    def samplerate(self) -> int:
        return self._sr

    def set_volume(self, value: float) -> float:
        self.volume = float(np.clip(value, 0.0, 1.0))
        return self.volume

    def volume_up(self, step: float = 0.05) -> float:
        return self.set_volume(self.volume + step)

    def volume_down(self, step: float = 0.05) -> float:
        return self.set_volume(self.volume - step)

    def toggle_mute(self) -> bool:
        self.muted = not self.muted
        return self.muted

    def consume_ended(self) -> bool:
        """One-shot check: did the current track finish playing?"""
        with self.lock:
            ended = self._ended
            self._ended = False
            return ended

    def close(self) -> None:
        self._stop_ticker()
        with self.lock:
            self._playing = False
            if self.stream is not None:
                try:
                    self.stream.close()
                except Exception:
                    pass
                self.stream = None
            self._data = None


def _zeros(n: int) -> np.ndarray:
    return np.zeros(n, dtype=np.float32)


def _compute_envelope(data: np.ndarray, buckets: int = 900) -> np.ndarray:
    """Peak amplitude envelope used by the waveform seek bar."""
    frames = len(data)
    if frames == 0:
        return np.zeros(buckets, dtype=np.float32)
    mono = np.abs(data.mean(axis=1))
    edges = np.linspace(0, frames, buckets + 1, dtype=int)
    edges[-1] = frames
    env = np.maximum.reduceat(mono, edges[:-1])
    peak = float(env.max()) or 1.0
    return (env / peak).astype(np.float32)
