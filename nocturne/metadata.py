"""Tag / metadata reading (via mutagen) with graceful degradation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

try:
    import mutagen
except Exception:  # pragma: no cover
    mutagen = None


@dataclass
class Tags:
    title: str = ""
    artist: str = ""
    album: str = ""
    bitrate_kbps: int = 0
    year: str = ""
    has_tags: bool = False


@dataclass
class Track:
    path: Path
    duration: float = 0.0
    samplerate: int = 0
    format: str = ""
    subtype: str = ""
    size_bytes: int = 0
    tags: Tags = field(default_factory=Tags)

    @property
    def title(self) -> str:
        return self.tags.title or self.path.stem.replace("_", " ")

    @property
    def subtitle(self) -> str:
        bits = [b for b in (self.tags.artist, self.tags.album) if b]
        return " — ".join(bits) if bits else self.path.parent.name


def _first(*values) -> str:
    for v in values:
        if v:
            return str(v)
    return ""


def read_tags(path: Path) -> Tags:
    tags = Tags()
    if mutagen is None:
        return tags
    try:
        mf = mutagen.File(str(path), easy=True)
    except Exception:
        return tags
    if mf is None:
        return tags
    try:
        tags.title = _first((mf.get("title") or [""])[0])
        tags.artist = _first((mf.get("artist") or [""])[0])
        tags.album = _first((mf.get("album") or [""])[0])
        if hasattr(mf, "info") and getattr(mf.info, "bitrate", 0):
            tags.bitrate_kbps = int(round(mf.info.bitrate / 1000))
        year = _first((mf.get("date") or [""])[0], (mf.get("year") or [""])[0])
        tags.year = year[:4]
        tags.has_tags = bool(tags.title or tags.artist or tags.album)
    except Exception:
        pass
    return tags


def probe(path) -> tuple[float, int, str] | None:
    """Fallback probe via mutagen: returns (duration, samplerate, format)."""
    if mutagen is None:
        return None
    try:
        mf = mutagen.File(path)
    except Exception:
        return None
    if mf is None or not hasattr(mf, "info"):
        return None
    try:
        length = float(getattr(mf.info, "length", 0.0) or 0.0)
        sr = int(getattr(mf.info, "sample_rate", 0) or 0)
        kind = type(mf).__name__  # MP3, M4A, WMA, ...
        if length <= 0:
            return None
        return length, sr, kind
    except Exception:
        return None


def fmt_time(seconds: float) -> str:
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
