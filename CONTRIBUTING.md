# Contributing to TermVibe

Thanks for wanting to make TermVibe cooler! 🎹

## Getting set up

```bash
git clone https://github.com/YOUR_USERNAME/termvibe.git
cd termvibe
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
```

On Linux you'll want PortAudio for actual sound: `sudo apt install libportaudio2`
(tests run fine without it — the engine falls back to silent mode).

## Ground rules

- Keep it **offline** — no network calls, no telemetry, no accounts.
- Any new feature should work in silent mode too (headless/CI friendly).
- Add or update tests for anything you touch. `pytest -q` must stay green.
- Match the existing code style (type hints, docstrings, small focused modules).
- One logical change per pull request, with a short clear description.

## Ideas that would be extra awesome

- More themes (add an entry to `termvibe/themes.py` — that's all it takes)
- OSC / oscilloscope visualizer modes
- CUE sheet support, gapless playback
- A `--screenshot` CLI flag that renders the UI headlessly

## Reporting bugs

Open an issue with: your OS + terminal, Python version, the command you ran,
and what you expected vs. what happened. For crashes, paste the traceback.
