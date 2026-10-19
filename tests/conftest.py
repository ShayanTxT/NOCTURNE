"""Shared test fixtures: isolate user config so tests never touch ~/.config."""

from __future__ import annotations

import pytest

from termvibe import config


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))
    monkeypatch.setattr(config, "config_dir", lambda: tmp_path / "xdg-config" / "termvibe")
    monkeypatch.setattr(config, "config_path", lambda: tmp_path / "xdg-config" / "termvibe" / "config.json")
    yield
