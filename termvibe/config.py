"""Persistent configuration (JSON) stored in the user's config directory."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

CONFIG_VERSION = 1

_DEFAULTS = {
    "version": CONFIG_VERSION,
    "last_folder": "",
    "volume": 0.85,
    "theme": "synthwave",
    "shuffle": False,
    "repeat": "all",        # off | all | one
    "recursive": True,
    "visualizer": True,
}


def config_dir() -> Path:
    if sys.platform == "win32":  # pragma: no cover
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "termvibe"


def config_path() -> Path:
    return config_dir() / "config.json"


def load_config() -> dict:
    cfg = dict(_DEFAULTS)
    try:
        raw = json.loads(config_path().read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            for key in _DEFAULTS:
                if key in raw:
                    cfg[key] = raw[key]
    except Exception:
        pass
    cfg["volume"] = min(1.0, max(0.0, float(cfg["volume"])))
    if cfg["repeat"] not in ("off", "all", "one"):
        cfg["repeat"] = "all"
    return cfg


def save_config(cfg: dict) -> None:
    try:
        path = config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {key: cfg.get(key, _DEFAULTS[key]) for key in _DEFAULTS}
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    except Exception:
        pass  # config is best-effort; never crash the player over it
