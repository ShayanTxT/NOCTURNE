"""Tests for the spectrum analyzer, themes and config."""

from __future__ import annotations

import json

import numpy as np

from termvibe import config, themes
from termvibe.spectrum import SpectrumAnalyzer


def _tone_block(sr: int = 44100, freq: float = 1000.0, n: int = 2048) -> np.ndarray:
    t = np.linspace(0, n / sr, n, endpoint=False)
    return (0.6 * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def test_analyzer_responds_to_new_data() -> None:
    an = SpectrumAnalyzer(bars=32)
    an.set_bands(44100)
    seq = 0
    levels, _ = an.snapshot()
    assert levels.max() == 0.0
    # feed a loud 1 kHz tone
    for _ in range(3):
        seq += 1
        an.update(_tone_block(), 44100, seq)
    levels, peaks = an.snapshot()
    assert levels.max() > 0.3
    assert (peaks >= levels - 1e-5).all()
    # same sequence id -> ignored (no new audio)
    before = levels.copy()
    an.update(_tone_block(), 44100, seq)
    assert (an.snapshot()[0] == before).all()


def test_analyzer_decays_when_paused() -> None:
    an = SpectrumAnalyzer(bars=16)
    an.set_bands(44100)
    an.update(_tone_block(), 44100, 1)
    peak_before = an.snapshot()[0].max()
    for _ in range(20):
        an.decay()
    assert an.snapshot()[0].max() < peak_before


def test_energy_distribution_is_log_sane() -> None:
    an = SpectrumAnalyzer(bars=48)
    an.set_bands(44100)
    an.update(_tone_block(freq=100.0), 44100, 1)  # low tone
    low_energy = an.snapshot()[0][:16].max()
    high_energy = an.snapshot()[0][32:].max()
    assert low_energy > high_energy
    an.update(_tone_block(freq=8000.0), 44100, 2)  # high tone
    an.update(_tone_block(freq=8000.0), 44100, 3)
    high_energy = an.snapshot()[0][32:].max()
    assert high_energy > 0.1


def test_resize_preserves_type() -> None:
    an = SpectrumAnalyzer(bars=10)
    an.resize(64)
    assert len(an.levels) == 64 and len(an.peaks) == 64
    an.resize(8)
    assert len(an.levels) == 8


def test_all_themes_registered_shapes() -> None:
    assert len(themes.THEMES) >= 5
    for name, entry in themes.THEMES.items():
        assert entry["theme"].name == name
        assert len(entry["spectrum"]) >= 2
        colors = themes.theme_colors(name)
        assert colors["played"] and colors["unplayed"]


def test_next_theme_wraps() -> None:
    names = list(themes.THEMES)
    assert themes.next_theme(names[-1]) == names[0]
    assert themes.next_theme("does-not-exist") == themes.DEFAULT_THEME


def test_lerp_gradient() -> None:
    stops = ["#000000", "#ffffff"]
    mid = themes.lerp_gradient(3, stops)[1]
    assert mid.lower() in ("#808080", "#7f7f7f")
    assert len(themes.lerp_gradient(10, stops)) == 10
    single = themes.lerp_gradient(5, ["#ff0000"])
    assert all(c == "#ff0000" for c in single)


def test_config_roundtrip(tmp_path, monkeypatch) -> None:
    cfg_dir = tmp_path / "cfg"
    monkeypatch.setattr(config, "config_dir", lambda: cfg_dir)
    monkeypatch.setattr(config, "config_path", lambda: cfg_dir / "config.json")
    cfg = config.load_config()
    assert cfg["theme"] == "synthwave"
    cfg["volume"] = 0.42
    cfg["repeat"] = "bogus"     # invalid value gets sanitized on load
    config.save_config(cfg)
    cfg2 = config.load_config()
    assert cfg2["volume"] == 0.42
    assert cfg2["repeat"] == "all"
    data = json.loads(config.config_path().read_text())
    assert data["version"] == config.CONFIG_VERSION
