#!/usr/bin/env python3
"""
Generate small synthesized demo tracks (FLAC/WAV/OGG) so you can try
TermVibe instantly, with no downloads. Pure numpy — no network needed.

    python scripts/make_demo_tracks.py [output_dir]
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import soundfile as sf

SR = 44100


def note(freq: float, dur: float, sr: int = SR, kind: str = "saw", vol: float = 0.5) -> np.ndarray:
    t = np.linspace(0, dur, int(sr * dur), endpoint=False)
    if kind == "saw":
        wave = 2 * ((freq * t) % 1.0) - 1
    elif kind == "square":
        wave = np.sign(np.sin(2 * np.pi * freq * t))
    else:  # sine
        wave = np.sin(2 * np.pi * freq * t)
    env = np.exp(-t * 3.0) * np.minimum(1.0, t * 200)
    return (wave * env * vol).astype(np.float32)


NOTE_FREQS = {}
NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
for octave in range(1, 7):
    for i, name in enumerate(NAMES):
        midi = 12 * (octave + 1) + i
        NOTE_FREQS[f"{name}{octave}"] = 440.0 * 2 ** ((midi - 69) / 12)


def make_track(title: str, bpm: float, chords: list[list[str]], seed: int = 1) -> np.ndarray:
    rng = np.random.default_rng(seed)
    beat = 60.0 / bpm
    step = beat / 2  # eighth notes
    events: list[tuple[float, np.ndarray]] = []

    time_cursor = 0.0
    for bar, chord in enumerate(chords * 2):  # repeat progression
        root = chord[0]
        # bass line — eighth note pulse
        for k in range(8):
            f = NOTE_FREQS[root + "2"] * (1 if k % 4 else 2)
            events.append((time_cursor + k * step, note(f, step * 0.9, kind="saw", vol=0.42)))
        # arpeggio — sparkly sixteenths over the chord
        arp = chord + [chord[1], chord[2], chord[1]]
        for k in range(16):
            name = arp[k % len(arp)]
            oct_up = "5" if k % 8 < 4 else "6"
            f = NOTE_FREQS[name + oct_up]
            events.append((time_cursor + k * step / 2, note(f, step * 0.7, kind="square", vol=0.13)))
        # pad — soft sustained chord
        for name in chord:
            f = NOTE_FREQS[name + "4"]
            dur = step * 8
            t = np.linspace(0, dur, int(SR * dur), endpoint=False)
            pad = np.sin(2 * np.pi * f * t) * 0.06 * np.ones_like(t)
            events.append((time_cursor, pad.astype(np.float32)))
        # hats — noise bursts
        for k in range(8):
            n = int(SR * 0.03)
            hat = (rng.standard_normal(n) * np.exp(-np.linspace(0, 6, n)) * 0.12).astype(np.float32)
            events.append((time_cursor + k * step + step / 2, hat))
        # kick on beats
        for k in range(4):
            t = np.linspace(0, 0.12, int(SR * 0.12), endpoint=False)
            kick = np.sin(2 * np.pi * (55 + 60 * np.exp(-t * 30)) * t)
            kick = (kick * np.exp(-t * 18) * 0.8).astype(np.float32)
            events.append((time_cursor + k * beat, kick))
        time_cursor += step * 8

    total = int((time_cursor + 1.0) * SR)
    mix = np.zeros(total, dtype=np.float32)
    for start, snd in events:
        i = int(start * SR)
        j = min(i + len(snd), total)
        mix[i:j] += snd[: j - i]
    mix /= max(1.0, np.abs(mix).max() / 0.9)
    stereo = np.stack([mix, np.roll(mix, int(SR * 0.00012))], axis=1)
    return stereo.astype(np.float32)


TRACKS = [
    ("01 - Neon Skyline", 112, [["A", "C", "E"], ["F", "A", "C"], ["C", "E", "G"], ["G", "B", "D"]], 3),
    ("02 - Midnight Drive", 92, [["D", "F", "A"], ["A#", "D", "F"], ["F", "A", "C"], ["C", "E", "G"]], 7),
    ("03 - Aurora Bloom", 126, [["E", "G#", "B"], ["B", "D#", "F#"], ["A", "C#", "E"], ["E", "G#", "B"]], 11),
    ("04 - Vaporwave Sunset", 78, [["C", "E", "G"], ["A", "C", "E"], ["F", "A", "C"], ["G", "B", "D"]], 13),
]


def main() -> None:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "demo_tracks")
    out.mkdir(parents=True, exist_ok=True)
    fmts = [".flac", ".ogg", ".wav"]
    for i, (title, bpm, chords, seed) in enumerate(TRACKS):
        audio = make_track(title, bpm, chords, seed)
        stem = title.replace(" ", "_")
        ext = fmts[i % len(fmts)]
        path = out / f"{stem}{ext}"
        sf.write(str(path), audio, SR)
        dur = len(audio) / SR
        print(f"wrote {path.name}  ({dur:.1f}s, {path.stat().st_size / 1e6:.1f} MB)")
    print("done.")


if __name__ == "__main__":
    main()
