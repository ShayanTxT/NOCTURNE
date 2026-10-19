"""Tests for the decoder fallback chain (libsndfile -> miniaudio -> ffmpeg)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from nocturne import engine as engine_mod
from nocturne.engine import AudioEngine, TrackLoadError, _decode_any, _load_miniaudio


def _make_mp3(path: Path, seconds: float = 1.0, sr: int = 44100) -> Path:
    """Encode a real MP3 with lameenc (skipped when the encoder is absent)."""
    lameenc = pytest.importorskip("lameenc")
    t = np.linspace(0, seconds, int(sr * seconds), endpoint=False)
    pcm = np.zeros((len(t), 2), dtype=np.int16)
    pcm[:, 0] = (0.4 * np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16)
    pcm[:, 1] = pcm[:, 0]
    enc = lameenc.Encoder()
    enc.set_bit_rate(128)
    enc.set_in_sample_rate(sr)
    enc.set_channels(2)
    enc.set_quality(2)  # fastest
    blob = enc.encode(pcm.tobytes()) + enc.flush()
    path.write_bytes(blob)
    return path


@pytest.fixture(scope="module")
def mp3_file(tmp_path_factory) -> Path:
    return _make_mp3(tmp_path_factory.mktemp("mp3") / "song.mp3")


def test_miniaudio_decodes_mp3(mp3_file: Path) -> None:
    data, sr = _load_miniaudio(mp3_file)
    assert data.ndim == 2 and data.shape[1] == 2
    assert sr == 44100
    assert float(np.abs(data).max()) > 0.05  # real audio came out


def test_engine_loads_mp3(mp3_file: Path) -> None:
    eng = AudioEngine(silent=True)
    info = eng.load(mp3_file)
    assert info["duration"] == pytest.approx(1.0, abs=0.2)
    assert info["decoder"] in ("libsndfile", "miniaudio")
    assert eng.duration == pytest.approx(1.0, abs=0.2)
    eng.close()


def test_chain_falls_back_to_miniaudio(mp3_file: Path, monkeypatch) -> None:
    """Simulate an old libsndfile without MP3 support (the user's machine)."""

    def broken_sndfile(_path):
        raise TrackLoadError("no mp3 support in this libsndfile")

    monkeypatch.setattr(engine_mod, "_load_sndfile", broken_sndfile)
    data, sr, decoder = _decode_any(mp3_file)
    assert decoder == "miniaudio"
    assert len(data) > 0


def test_chain_fails_cleanly_on_garbage(tmp_path: Path) -> None:
    bad = tmp_path / "broken.mp3"
    bad.write_bytes(b"\x00\x01garbage" * 512)
    with pytest.raises(TrackLoadError):
        _decode_any(bad)


def test_load_error_message_mentions_help(monkeypatch, tmp_path: Path) -> None:
    bad = tmp_path / "broken.m4a"
    bad.write_bytes(b"not really audio" * 64)
    with pytest.raises(TrackLoadError) as exc:
        _decode_any(bad)
    assert str(exc.value)  # a human-readable reason exists


def test_wav_still_loads_via_sndfile(tmp_path: Path) -> None:
    p = tmp_path / "tone.wav"
    t = np.linspace(0, 0.3, 8000, endpoint=False, dtype=np.float32)
    sf.write(str(p), np.stack([t * 0.1] * 2, axis=1), 8000)
    eng = AudioEngine(silent=True)
    info = eng.load(p)
    assert info["decoder"] == "libsndfile"
    eng.close()
