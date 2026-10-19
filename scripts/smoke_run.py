#!/usr/bin/env python3
"""Headless smoke test + screenshot capture for TermVibe."""

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from termvibe.app import TermVibeApp  # noqa: E402


async def main() -> None:
    demo = ROOT / "demo_tracks"
    size = tuple(int(x) for x in (sys.argv[1].split("x"))) if len(sys.argv) > 1 else (120, 34)
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "docs" / "screenshot.svg"

    app = TermVibeApp(start_path=str(demo), silent=True, theme="synthwave")
    async with app.run_test(size=size) as pilot:
        await pilot.pause(2.5)          # scan + load + autoplay first track
        await pilot.pause(8.5)          # roll deeper into the music
        svg = app.export_screenshot()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(svg, encoding="utf-8")
        print(f"saved {out} ({out.stat().st_size // 1024} KB)")
        print("tracks:", len(app.tracks), "| current:", app.current,
              "| engine pos:", round(app.engine.position, 2), "/", round(app.engine.duration, 2),
              "| mode:", app.engine.mode)


if __name__ == "__main__":
    asyncio.run(main())
