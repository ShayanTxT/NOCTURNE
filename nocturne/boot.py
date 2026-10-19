"""Boot sequence overlay — typed-out hacker terminal intro. Skip with any key."""

from __future__ import annotations

import random

from rich.style import Style
from rich.text import Text
from textual.screen import ModalScreen
from textual.widgets import Static

from . import __version__

_BANNER = r"""
  ███╗   ██╗ ██████╗  ██████╗████████╗██╗   ██╗██████╗ ███╗   ███╗███████╗
  ████╗  ██║██╔═══██╗██╔════╝╚══██╔══╝██║   ██║██╔══██╗████╗ ████║██╔════╝
  ██╔██╗ ██║██║   ██║██║        ██║   ██║   ██║██████╔╝██╔████╔██║█████╗
  ██║╚██╗██║██║   ██║██║        ██║   ██║   ██║██╔══██╗██║╚██╔╝██║██╔══╝
  ██║ ╚████║╚██████╔╝╚██████╗   ██║   ╚██████╔╝██║  ██║██║ ╚═╝ ██║███████╗
  ╚═╝  ╚═══╝ ╚═════╝  ╚═════╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝╚═╝     ╚═╝╚══════╝"""

_MODIFIER_KEYS = {
    "shift", "control", "alt", "meta",
    "left_shift", "right_shift", "left_control", "right_control",
    "left_alt", "right_alt", "left_meta", "right_meta",
}


class BootScreen(ModalScreen):
    """Fake system boot log with a live typing effect. Any key/click skips it."""

    can_focus = True

    DEFAULT_CSS = """
    BootScreen { background: #000000; }
    #boot-log { width: 1fr; max-width: 100; height: 1fr; padding: 1 2;
                content-align: left middle; }
    """

    def __init__(self, ghost: bool = False, device: str = "", **kwargs):
        super().__init__(**kwargs)
        self._ghost = ghost
        self._device = device
        self._revealed = 0
        self._hold = 0
        self._finished = False
        self._full: Text | None = None

    # ---------------------------------------------------------------- content
    def compose(self):
        yield Static("", id="boot-log")

    def _build_log(self) -> Text:
        colors = self.app._colors()["spectrum"]  # noqa: SLF001 — sibling module
        dim = colors[1]
        ok = colors[3]
        hot = colors[4]
        session = f"0x{random.getrandbits(32):08x}"

        t = Text()
        t.append(_BANNER + "\n", style=Style(color=dim, bold=True))
        t.append(f" v{__version__} · audio intrusion unit · session {session}\n",
                 style=Style(color=ok))
        t.append(" " + "─" * 62 + "\n", style=Style(color=dim))

        rows: list[tuple[str, str, str]] = [
            ("[ok]", "decoder", "libsndfile · flac/ogg/wav/aiff"),
            ("[ok]", "spectrum", "2048-pt fft · log bands · peak caps"),
            ("[ok]", "playlist", "natural sort · id3/vorbis tags"),
            ("[ok]", "playback", "48 kHz stereo · zero network"),
        ]
        for status, name, desc in rows:
            color = ok if status == "[ok]" else dim
            t.append(f" {status} ".ljust(7), style=Style(color=color, bold=True))
            t.append(f"{name:<11}", style=Style(color=hot, bold=True))
            t.append(desc + "\n", style=Style(color=dim))

        if self._ghost:
            t.append(" [!!] ".ljust(7), style=Style(color="#ff1133", bold=True))
            t.append(f"{'audio':<11}", style=Style(color=hot, bold=True))
            t.append("device not found — ghost mode engaged\n",
                     style=Style(color="#ff1133"))
        else:
            t.append(" [ok] ".ljust(7), style=Style(color=ok, bold=True))
            t.append(f"{'audio':<11}", style=Style(color=hot, bold=True))
            t.append(f"{self._device[:40]}\n", style=Style(color=dim))

        t.append(" [..] ".ljust(7), style=Style(color=dim, bold=True))
        t.append(f"{'handshake':<11}", style=Style(color=hot, bold=True))
        t.append("done\n", style=Style(color=dim))
        t.append("\n")
        if self._ghost:
            t.append(" GHOST MODE ENGAGED", style=Style(color="#ff1133", bold=True))
        else:
            t.append(" ACCESS GRANTED", style=Style(color=ok, bold=True))
        return t

    # ----------------------------------------------------------------- typing
    def on_mount(self) -> None:
        self._full = self._build_log()
        self.query_one("#boot-log", Static).update(Text(""))
        self.focus()
        self.set_interval(0.012, self._type_tick)

    def _type_tick(self) -> None:
        self._ticks = getattr(self, "_ticks", 0) + 1
        if self._ticks > 1500:  # failsafe: never trap the app in a bad env
            self._finish()
            return
        if self._full is None:
            return
        total = len(self._full.plain)
        if self._revealed < total:
            self._revealed = min(total, self._revealed + 9)
            self.query_one("#boot-log", Static).update(self._full[: self._revealed])
        else:
            self._hold += 1
            if self._hold > 45:  # ~0.55s beat on the final line, then dissolve
                self._finish()

    # ------------------------------------------------------------------ skip
    def _finish(self) -> None:
        if self._finished:
            return
        self._finished = True
        self.dismiss()

    def on_key(self, event) -> None:  # any real key skips the intro
        if event.key in _MODIFIER_KEYS:
            return
        event.prevent_default()
        event.stop()
        self._finish()

    def on_click(self, _event) -> None:
        self._finish()
