"""Custom Textual widgets: spectrum visualizer, waveform seek bar, banner."""

from __future__ import annotations

import numpy as np
from rich.segment import Segment
from rich.style import Style
from rich.text import Text
from textual.strip import Strip
from textual.widget import Widget

from . import themes
from .engine import AudioEngine
from .spectrum import SpectrumAnalyzer

BLOCK_CHARS = "▁▂▃▄▅▆▇█"

LOGO = r"""\
████████╗███████╗██████╗ ███╗   ███╗██╗   ██╗██╗██████╗ ███████╗
╚══██╔══╝██╔════╝██╔══██╗████╗ ████║██║   ██║██║██╔══██╗██╔════╝
   ██║   █████╗  ██████╔╝██╔████╔██║██║   ██║██║██████╔╝█████╗
   ██║   ██╔══╝  ██╔══██╗██║╚██╔╝██║╚██╗ ██╔╝██║██╔══██╗██╔══╝
   ██║   ███████╗██║  ██║██║ ╚═╝ ██║ ╚████╔╝ ██║██████╔╝███████╗
   ╚═╝   ╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝  ╚═══╝  ╚═╝╚═════╝ ╚══════╝\
"""


def _style(hex_color: str, *, bold: bool = False) -> Style:
    return Style(color=hex_color, bold=bold)


# ----------------------------------------------------------------- spectrum
class SpectrumWidget(Widget):
    """Full-width log-frequency spectrum with falling peak caps."""

    DEFAULT_CSS = """
    SpectrumWidget { width: 1fr; min-height: 6; }
    """

    def __init__(self, engine: AudioEngine, theme: str, **kwargs):
        super().__init__(**kwargs)
        self.engine = engine
        self.analyzer = SpectrumAnalyzer(bars=60)
        self.theme_name = theme
        self.row_colors = themes.lerp_gradient(12, self._stops())
        self.cap_color = self._stops()[-1]

    def _stops(self) -> list[str]:
        return themes.theme_colors(self.theme_name)["spectrum"]

    def set_theme(self, name: str) -> None:
        self.theme_name = name
        self.row_colors = themes.lerp_gradient(max(self.size.height, 12), self._stops())
        self.cap_color = self._stops()[-1]

    def on_mount(self) -> None:
        self.set_interval(1 / 24, self._tick)

    def _tick(self) -> None:
        block, seq = self.engine.vis.latest()
        if self.engine.playing:
            self.analyzer.update(block, self.engine.samplerate, seq)
        else:
            self.analyzer.decay()
        self.refresh()

    def render_line(self, y: int) -> Strip:
        width = max(self.size.width, 10)
        rows = max(self.size.height, 1)
        bars = max(8, width // 2)
        self.analyzer.resize(bars)
        if len(self.row_colors) != rows:
            self.row_colors = themes.lerp_gradient(rows, self._stops())

        levels, peaks = self.analyzer.snapshot()
        n = len(levels)
        step = n / bars
        fill = (levels * rows).astype(int)
        cap_y = np.clip((rows - 1) - (peaks * rows).astype(int), 0, rows - 1)

        segs: list[Segment] = []
        for bar in range(bars):
            i = min(int(bar * step), n - 1)
            filled_here = fill[i] > 0 and y >= rows - fill[i]
            cap_here = (not filled_here) and y == cap_y[i] and peaks[i] > 0.02
            if filled_here:
                color = self.row_colors[min(rows - 1 - y, len(self.row_colors) - 1)]
                segs.append(Segment("█ ", _style(color)))
            elif cap_here:
                segs.append(Segment("▄ ", _style(self.cap_color, bold=True)))
            else:
                segs.append(Segment("  "))
        return Strip(segs)


# ------------------------------------------------------------------ seekbar
class WaveBar(Widget):
    """Waveform seek bar — click or drag to seek."""

    DEFAULT_CSS = """
    WaveBar { width: 1fr; height: 1; }
    """
    can_focus = False

    def __init__(self, engine: AudioEngine, theme: str, **kwargs):
        super().__init__(**kwargs)
        self.engine = engine
        self.theme_name = theme
        self.on_seek = None  # callback(fraction: float)
        self.set_theme(theme)

    def set_theme(self, name: str) -> None:
        colors = themes.theme_colors(name)
        self._played = colors["played"]
        self._unplayed = colors["unplayed"]

    def render_line(self, y: int) -> Strip:
        width = max(self.size.width, 10)
        env = self.engine.envelope
        if len(env) == 0:
            env = np.zeros(1, dtype=np.float32)
        dur = self.engine.duration
        frac = (self.engine.position / dur) if dur > 0 else 0.0
        head = int(frac * width)

        played_style = _style(self._played, bold=True)
        unplayed_style = _style(self._unplayed)
        segs: list[Segment] = []
        for x in range(width):
            b = env[min(int(x / width * len(env)), len(env) - 1)]
            ch = BLOCK_CHARS[min(int(b * (len(BLOCK_CHARS) - 1) + 0.5), len(BLOCK_CHARS) - 1)]
            segs.append(Segment(ch, played_style if x < head else unplayed_style))
        return Strip(segs)

    def _seek_from_x(self, x: int) -> None:
        width = max(self.size.width, 1)
        frac = min(max(x / width, 0.0), 1.0)
        if self.on_seek:
            self.on_seek(frac)

    def on_click(self, event) -> None:
        self._seek_from_x(event.x)

    def on_mouse_move(self, event) -> None:
        if getattr(event, "button", 0) == 1:
            self._seek_from_x(event.x)


# --------------------------------------------------------------------- misc
def gradient_text(text: str, stops: list[str]) -> Text:
    """Render text with a horizontal color gradient."""
    colors = themes.lerp_gradient(max(len(text), 1), stops)
    out = Text()
    for i, ch in enumerate(text):
        out.append(ch, style=Style(color=colors[min(i, len(colors) - 1)], bold=True))
    return out
