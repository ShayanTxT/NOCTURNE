# Changelog

All notable changes to Nocturne are documented here.

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
