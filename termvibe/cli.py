"""Command line interface for TermVibe."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__, themes


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="termvibe",
        description="TermVibe — a stunning terminal music player. Give it a folder, it plays everything in it. 100%% offline.",
        epilog="examples:\n"
        "  termvibe ~/Music                play a folder (recursive)\n"
        "  termvibe ~/Music --flat         don't scan subfolders\n"
        "  termvibe song.flac              play a single file\n"
        "  termvibe --theme matrix -s      matrix theme + shuffle\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("path", nargs="?", default=None,
                   help="folder (or single audio file) to play; defaults to your last folder")
    p.add_argument("-s", "--shuffle", action="store_true", help="start with shuffle on")
    p.add_argument("-r", "--repeat", choices=["off", "all", "one"], default=None,
                   help="repeat mode (default: all)")
    p.add_argument("-t", "--theme", choices=sorted(themes.THEMES), default=None,
                   help="color theme (default: synthwave)")
    p.add_argument("--flat", action="store_true", help="don't scan subfolders")
    p.add_argument("--no-visualizer", action="store_true", help="hide the spectrum")
    p.add_argument("--silent", action="store_true",
                   help="force silent mode (no audio output; useful for demos/CI)")
    p.add_argument("--list-themes", action="store_true", help="list available themes and exit")
    p.add_argument("-V", "--version", action="version", version=f"TermVibe {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.list_themes:
        for name in themes.THEMES:
            marker = "*" if name == themes.DEFAULT_THEME else " "
            print(f" {marker} {name}")
        return 0

    # merge CLI args over saved config
    from . import config

    cfg = config.load_config()
    theme = args.theme or cfg["theme"]
    repeat = args.repeat or cfg["repeat"]
    volume = cfg["volume"]
    if args.path is None and not cfg["last_folder"]:
        # nothing remembered — try ~/Music, then cwd
        for candidate in (Path.home() / "Music", Path.cwd()):
            if candidate.is_dir():
                args.path = str(candidate)
                break

    from .app import TermVibeApp

    app = TermVibeApp(
        start_path=args.path,
        theme=theme,
        shuffle=args.shuffle or bool(cfg["shuffle"]),
        repeat=repeat,
        recursive=not args.flat and bool(cfg["recursive"]),
        visualizer=not args.no_visualizer,
        silent=args.silent,
        volume=volume,
    )
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
