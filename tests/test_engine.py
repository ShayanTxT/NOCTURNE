"""Tests for the Nocturne audio engine (silent mode — no device needed)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from nocturne.engine import AudioEngine, TrackLoadError, _compute_envelope


@pytest.fixture()
def wav_file(tmp_path: Path) -> Path:
    sr = 22050
    t = np.linspace(0, 1.0, sr, endpoint=False, dtype=np.float32)
    data = np.stack([0.3 * np.sin(2 * np.pi * 440 * t)] * 2, axis=1)
    path = tmp_path / "tone.wav"
    sf.write(str(path), data, sr)
    return path


def test_silent_mode_defaults() -> None:
    eng = AudioEngine(silent=True)
    assert eng.silent
    assert eng.mode == "silent"
    assert not eng.loaded
    assert eng.duration == 0.0
    assert eng.volume == 0.85
    eng.close()


def test_load_and_play(wav_file: Path) -> None:
    eng = AudioEngine(silent=True)
    info = eng.load(wav_file)
    assert info["samplerate"] == 22050
    assert info["channels"] == 2
    assert eng.duration == pytest.approx(1.0, abs=0.01)

    eng.play()
    assert eng.playing
    eng.vis.latest()  # warm up
    import time

    time.sleep(0.25)
    assert eng.position > 0.1
    eng.pause()
    pos = eng.position
    time.sleep(0.15)
    assert eng.position == pytest.approx(pos, abs=0.02)
    eng.close()


def test_toggle_and_stop(wav_file: Path) -> None:
    eng = AudioEngine(silent=True)
    eng.load(wav_file)
    assert eng.toggle() is True
    assert eng.toggle() is False
    eng.play()
    eng.seek(0.5)
    assert eng.position == pytest.approx(0.5, abs=0.05)
    eng.stop()
    assert eng.position == pytest.approx(0.0, abs=0.05)
    eng.close()


def test_seek_clamping(wav_file: Path) -> None:
    eng = AudioEngine(silent=True)
    eng.load(wav_file)
    eng.seek(999)
    assert eng.position == pytest.approx(eng.duration, abs=0.02)
    eng.seek(-5)
    assert eng.position == pytest.approx(0.0, abs=0.02)
    eng.close()


def test_volume_and_mute() -> None:
    eng = AudioEngine(silent=True, volume=0.5)
    assert eng.volume_up() == pytest.approx(0.55)
    assert eng.volume_down() == pytest.approx(0.50)
    assert eng.set_volume(2.0) == 1.0
    assert eng.set_volume(-1) == 0.0
    assert not eng.muted
    eng.toggle_mute()
    assert eng.muted and eng.gain == 0.0
    eng.toggle_mute()
    assert not eng.muted
    eng.close()


def test_ended_flag_and_consume(wav_file: Path) -> None:
    eng = AudioEngine(silent=True)
    eng.load(wav_file)
    eng.play()
    import time

    deadline = time.time() + 5
    ended = False
    while time.time() < deadline:
        if eng.consume_ended():
            ended = True
            break
        time.sleep(0.05)
    assert ended, "engine never reported end-of-track"
    assert eng.consume_ended() is False  # one-shot
    eng.close()


def test_load_error(tmp_path: Path) -> None:
    bad = tmp_path / "bad.wav"
    bad.write_bytes(b"not audio at all")
    eng = AudioEngine(silent=True)
    with pytest.raises(TrackLoadError):
        eng.load(bad)
    eng.close()


def test_envelope() -> None:
    sr = 8000
    t = np.linspace(0, 1.0, sr, endpoint=False, dtype=np.float32)
    data = (0.5 * np.sin(2 * np.pi * 300 * t)).reshape(-1, 1)
    env = _compute_envelope(np.repeat(data, 2, axis=1), buckets=100)
    assert len(env) == 100
    assert env.max() == pytest.approx(1.0, abs=0.01)
    assert env.min() >= 0.0
