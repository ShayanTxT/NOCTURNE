"""Custom Textual widgets: spectrum / matrix-rain / scope, waveform bar, art."""

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
RAIN_CHARS = "01"
LOGO_TEXT = "░▒▓ NOCTURNE"

SKULL = r"""\
      ______
   .-"      "-.
  /            \
 |,  .-.  .-.  ,|
 | )(_o/  \o_)( |
 |/     /\     \|
 (_     ^^     _)
  \__|IIIIII|__/
   | \IIIIII/ |
   \          /
    `--------`\
"""


def _style(hex_color: str, *, bold: bool = False) -> Style:
    return Style(color=hex_color, bold=bold)


# ----------------------------------------------------------------- visualizer
class SpectrumWidget(Widget):
    """Three visualizer modes: spectrum bars, matrix rain, oscilloscope."""

    DEFAULT_CSS = """
    SpectrumWidget { width: 1fr; min-height: 6; }
    """

    def __init__(self, engine: AudioEngine, theme: str, mode: int = 0, **kwargs):
        super().__init__(**kwargs)
        self.engine = engine
        self.analyzer = SpectrumAnalyzer(bars=60)
        self.theme_name = theme
        self.mode = mode % 3
        self.row_colors = themes.lerp_gradient(12, self._stops())
        self.cap_color = self._stops()[-1]
        self._rain_y: np.ndarray | None = None      # per-column head position
        self._rain_speed: np.ndarray | None = None
        self._scope_block: np.ndarray = np.zeros(64, dtype=np.float32)
        self._last_scope_seq = -1

    def _stops(self) -> list[str]:
        return themes.theme_colors(self.theme_name)["spectrum"]

    def set_theme(self, name: str) -> None:
        self.theme_name = name
        self.row_colors = themes.lerp_gradient(max(self.size.height, 12), self._stops())
        self.cap_color = self._stops()[-1]

    def cycle_mode(self) -> int:
        self.mode = (self.mode + 1) % 3
        return self.mode

    def on_mount(self) -> None:
        self.set_interval(1 / 24, self._tick)

    def _tick(self) -> None:
        block, seq = self.engine.vis.latest()
        if self.engine.playing:
            self.analyzer.update(block, self.engine.samplerate, seq)
            if self.mode == 2 and seq != self._last_scope_seq:
                self._scope_block = _downsample(block, 128)
                self._last_scope_seq = seq
        else:
            self.analyzer.decay()
            if self.mode == 2:
                self._scope_block *= 0.9
        self.refresh()

    # ------------------------------------------------------------------ render
    def render_line(self, y: int) -> Strip:
        width = max(self.size.width, 10)
        rows = max(self.size.height, 1)
        bars = max(8, width // 2)
        self.analyzer.resize(bars)
        if len(self.row_colors) != rows:
            self.row_colors = themes.lerp_gradient(rows, self._stops())
        if self.mode == 1:
            return self._render_rain(y, width, rows, bars)
        if self.mode == 2:
            return self._render_scope(y, width, rows)
        return self._render_spectrum(y, width, rows, bars)

    def _render_spectrum(self, y: int, width: int, rows: int, bars: int) -> Strip:
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

    def _render_rain(self, y: int, width: int, rows: int, bars: int) -> Strip:
        if self._rain_y is None or len(self._rain_y) != bars:
            rng = np.random.default_rng()
            self._rain_y = rng.random(bars) * rows
            self._rain_speed = 0.3 + rng.random(bars) * 0.8
        levels, _ = self.analyzer.snapshot()
        n = len(levels)
        step = n / bars
        segs: list[Segment] = []
        dim = self._stops()[1]
        mid = self._stops()[2]
        bright = self._stops()[-1]
        for bar in range(bars):
            i = min(int(bar * step), n - 1)
            level = float(levels[i])
            speed = self._rain_speed[bar] * (0.25 + 5.5 * level)
            self._rain_y[bar] += speed / 24.0
            if self._rain_y[bar] > rows + 3:
                self._rain_y[bar] = 0.0
                self._rain_speed[bar] = 0.3 + float(np.random.random()) * 0.8
            head = self._rain_y[bar]
            trail = 1 + int(level * rows * 0.75)
            dist = head - y  # cells above head are "older"
            if 0 <= dist < trail:
                if dist < 1:
                    segs.append(Segment("01"[bar & 1], _style(bright, bold=True)))
                elif dist < trail * 0.4:
                    segs.append(Segment("01"[(bar + int(y)) & 1], _style(mid)))
                else:
                    segs.append(Segment("01"[(bar + int(y)) & 1], _style(dim)))
            else:
                segs.append(Segment(" "))
            if bar < bars - 1:
                segs.append(Segment(" "))
        return Strip(segs)

    def _render_scope(self, y: int, width: int, rows: int) -> Strip:
        wave = self._scope_block
        idx = (np.linspace(0, len(wave) - 1, width)).astype(int)
        samples = wave[idx]
        center = (rows - 1) / 2.0
        amp = max(1.0, rows / 2.0 - 1)
        ys = center - samples * amp
        hot = self._stops()[-1]
        dimc = self._stops()[1]
        segs: list[Segment] = []
        points = np.clip(np.round(ys).astype(int), 0, rows - 1)
        near = abs(y - center) < 0.6
        for x in range(width):
            if points[x] == y:
                segs.append(Segment("●", _style(hot, bold=True)))
            elif near and (x % 4 == 0):
                segs.append(Segment("·", _style(dimc)))
            elif points[x] == y - 1 and x > 0 and abs(points[x - 1] - points[x]) > 1:
                segs.append(Segment("▝", _style(hot)))
            else:
                segs.append(Segment(" "))
        return Strip(segs)


def _downsample(block: np.ndarray, points: int) -> np.ndarray:
    if len(block) == 0:
        return np.zeros(points, dtype=np.float32)
    idx = np.linspace(0, len(block) - 1, points).astype(int)
    return np.asarray(block, dtype=np.float32)[idx]


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
