"""Tests for folder scanning + metadata helpers."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

from nocturne.metadata import Tags, Track, fmt_time, read_tags
from nocturne.scanner import natural_key, scan_folder


def _write(path: Path, seconds: float = 0.2, sr: int = 22050) -> None:
    t = np.linspace(0, seconds, int(sr * seconds), endpoint=False, dtype=np.float32)
    sf.write(str(path), np.stack([t * 0.1] * 2, axis=1), sr)


def test_scan_folder_recursive_and_natural(tmp_path: Path) -> None:
    (tmp_path / "album").mkdir()
    _write(tmp_path / "album" / "track02.wav")
    _write(tmp_path / "album" / "track10.wav")
    _write(tmp_path / "top1.flac")
    (tmp_path / "notes.txt").write_text("ignore me")
    (tmp_path / "album" / ".hidden.ogg").write_bytes(b"x")

    files = scan_folder(tmp_path)
    names = [f.name for f in files]
    assert names == ["top1.flac", "track02.wav", "track10.wav"]  # natural order, no txt, no hidden


def test_scan_flat(tmp_path: Path) -> None:
    sub = tmp_path / "sub"
    sub.mkdir()
    _write(tmp_path / "a.wav")
    _write(sub / "b.wav")
    files = scan_folder(tmp_path, recursive=False)
    assert [f.name for f in files] == ["a.wav"]


def test_scan_single_file(tmp_path: Path) -> None:
    p = tmp_path / "one.ogg"
    _write(p)
    assert scan_folder(p) == [p]


def test_natural_key() -> None:
    a, b = natural_key(Path("track2.mp3")), natural_key(Path("track10.mp3"))
    assert a < b


def test_track_title_and_subtitle(tmp_path: Path) -> None:
    p = tmp_path / "My Song.flac"
    t = Track(path=p)
    assert t.title == "My Song"
    t2 = Track(path=p, tags=Tags(title="T", artist="A", album="L"))
    assert t2.title == "T"
    assert t2.subtitle == "A — L"


def test_read_tags_wav_is_optional(tmp_path: Path) -> None:
    p = tmp_path / "plain.wav"
    _write(p)
    tags = read_tags(p)  # WAVs usually have no tags; must not raise
    assert isinstance(tags, Tags)


def test_fmt_time() -> None:
    assert fmt_time(0) == "00:00"
    assert fmt_time(65) == "01:05"
    assert fmt_time(3671) == "1:01:11"
    assert fmt_time(-3) == "00:00"
