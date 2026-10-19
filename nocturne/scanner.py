"""Folder scanning for audio files with natural (human) sorting."""

from __future__ import annotations

import re
from pathlib import Path

AUDIO_EXTENSIONS = {
    ".mp3", ".wav", ".flac", ".ogg", ".oga", ".opus", ".aif", ".aiff", ".w64",
}

_SKIP_DIRS = {"lost+found", "$RECYCLE.BIN", "System Volume Information", "."}


def natural_key(path: Path) -> list:
    """Sort key that handles numbers the way humans expect (track02 < track10)."""
    name = path.name.lower()
    parts = re.split(r"(\d+)", name)
    return [int(p) if p.isdigit() else p for p in parts]


def scan_folder(path: Path, recursive: bool = True) -> list[Path]:
    """Return audio files inside *path*, naturally sorted."""
    path = Path(path).expanduser()
    if path.is_file():
        return [path] if path.suffix.lower() in AUDIO_EXTENSIONS else []

    files: list[Path] = []
    if recursive:
        for root, dirs, names in path.walk():
            dirs[:] = sorted(
                d for d in dirs if not d.startswith(".") and d not in _SKIP_DIRS
            )
            for name in names:
                if name.startswith("."):
                    continue
                p = Path(root) / name
                if p.suffix.lower() in AUDIO_EXTENSIONS:
                    files.append(p)
    else:
        for p in path.iterdir():
            if p.is_file() and not p.name.startswith(".") and p.suffix.lower() in AUDIO_EXTENSIONS:
                files.append(p)

    files.sort(key=natural_key)
    return files
