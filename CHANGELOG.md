# Changelog

All notable changes to Nocturne are documented here.

## [2.0.1] — 2026-10-19 — performance & hardening

### Fixed
- Matrix rain advanced its state inside `render_line` (once per row!) — rain now
  steps exactly once per frame in the update tick; removed per-row RNG calls
- `Path.walk()` (Python 3.12+) replaced with `os.walk` — restores the promised
  3.10/3.11 support
- Silent-mode clock re-reads the sample rate every loop (stale `dt` after loading
  a track with a different sample rate)
- Boot screen: hard failsafe timer + deferred push + tiny-terminal guard, so it
  can never trap the app in degenerate PTYs (0x0 CI terminals)

### Performance (measured headless, 110x30)
- Per-frame numpy work computed once per frame (was once per rendered row,
  ~15x redundant); `render_line` is now pure lookups
- Visualizer stops repainting entirely when paused and fully decayed
- Waveform bar / clock / statusbar repaint only on actual change
- Boot typing at 50 Hz with fewer wakeups; ticker sleeps 0.1 s when idle
- Result: idle CPU 20% -> 3.7% of a core (-82%), playback 22% -> 12% (-45%);
  the remainder is Textual's own layout timer

### Changed
- `pytest-asyncio` moved into dev extras; lint clean (ruff F/B/E7)

## [2.0.0] — 2026-10-19 — the NOCTURNE rebrand

### Added
- Hacker boot sequence with live typing effect (skip: any key, `--no-boot`)
- Three visualizer modes cycled with `v`: spectrum, matrix rain, oscilloscope
- Mr. Robot-flavored UI: `root@nocturne:~$` statusline prompt with blinking
  cursor, skull splash ("hello, friend."), ghost-mode branding
- Themes: fsociety, redroom, crt, cipher, ghost
- Config: visualizer mode is persisted

### Changed
- Renamed TermVibe -> Nocturne (command, module, config dir)
- Now-playing header restyled as `> NOW PLAYING [i/n]`

## [1.0.0] — 2026-10-19
## [1.0.0] — 2026-10-19

### Added
- Textual TUI: playlist, now-playing bar, spectrum visualizer, waveform seek bar
- Real-time FFT spectrum (log-spaced bands, peak caps, auto-gain, fast attack / slow release)
- Waveform seek bar rendered from the decoded track envelope — click & drag to seek
- Recursive folder scan with natural sorting and mutagen tag reading
- Shuffle, repeat (off/all/one), auto-advance, auto-skip of undecodable files
- Playlist filter (`/`), zen mode (`f`), help overlay (`?`)
- 5 neon themes: synthwave, matrix, sunset, ice, candy
- M3U playlist export, persistent config (folder/volume/theme/shuffle/repeat)
- Silent mode (`--silent`) for headless machines, CI and demos
- Demo track generator (`scripts/make_demo_tracks.py`) — synthesized synth tracks, no downloads
- 37 automated tests (engine, scanner, DSP, UI pilot) and GitHub Actions CI
