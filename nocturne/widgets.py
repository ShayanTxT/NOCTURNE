"""Custom Textual widgets: spectrum / matrix-rain / scope, waveform bar, art.

Performance notes
-----------------
``render_line`` is called once per row, so all per-frame numpy work happens
exactly once in ``_tick`` (cached in ``self._frame``); the renderer only does
cheap lookups.  When playback is paused and the bars have decayed to zero the
widget stops repainting altogether.
"""

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
LOGO_TEXT = "░▒▓ NOCTURNE"
FPS = 20  # visualizer refresh rate

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
        self._rng = np.random.default_rng()
        self._rain_y: np.ndarray | None = None       # per-column head position
        self._rain_speed: np.ndarray | None = None
        self._scope_pts: np.ndarray = np.full(64, -1, dtype=int)  # y per x
        self._scope_alive = 0.0
        self._last_scope_seq = -1
        self._frame: tuple | None = None             # per-frame render cache
        self._frame_key: tuple | None = None

    def _stops(self) -> list[str]:
        return themes.theme_colors(self.theme_name)["spectrum"]

    def set_theme(self, name: str) -> None:
        self.theme_name = name
        self.row_colors = themes.lerp_gradient(max(self.size.height, 12), self._stops())
        self.cap_color = self._stops()[-1]
        self._frame_key = None  # force re-color on next frame

    def cycle_mode(self) -> int:
        self.mode = (self.mode + 1) % 3
        self._frame_key = None
        return self.mode

    def on_mount(self) -> None:
        self.set_interval(1 / FPS, self._tick)

    # ------------------------------------------------------------------ update
    def _tick(self) -> None:
        if not self.is_mounted or not self.display:
            return
        width, rows = self.size.width, self.size.height
        if width < 4 or rows < 2:
            return

        block, seq = self.engine.vis.latest()
        playing = self.engine.playing
        if playing:
            self.analyzer.update(block, self.engine.samplerate, seq)
        else:
            self.analyzer.decay()

        levels, peaks = self.analyzer.snapshot()
        idle = (not playing) and float(levels.max()) < 0.004 and float(peaks.max()) < 0.02

        if self.mode == 2:
            if playing and seq != self._last_scope_seq:
                self._scope_pts = self._compute_scope(block, width, rows)
                self._last_scope_seq = seq
                self._scope_alive = 1.0
            elif self._scope_alive > 0:
                self._scope_alive *= 0.88
                if self._scope_alive < 0.02:
                    self._scope_alive = 0.0
                    self._scope_pts = np.full(width, -1, dtype=int)
            idle = idle and self._scope_alive == 0.0

        if idle:
            return  # nothing is moving — skip the repaint entirely

        self._prepare_frame(width, rows)
        self.refresh()

    def _prepare_frame(self, width: int, rows: int) -> None:
        """Compute everything render_line needs — once per frame, not per row."""
        bars = max(8, width // 2)
        self.analyzer.resize(bars)
        if len(self.row_colors) != rows:
            self.row_colors = themes.lerp_gradient(rows, self._stops())

        key = (width, rows, self.mode)
        if key != self._frame_key:
            if self.mode == 1 and (self._rain_y is None or len(self._rain_y) != bars):
                self._rain_y = self._rng.random(bars) * rows
                self._rain_speed = 0.3 + self._rng.random(bars) * 0.8
            self._frame_key = key

        levels, peaks = self.analyzer.snapshot()
        n = len(levels)

        if self.mode == 0:
            idx = np.minimum((np.arange(bars) * (n / bars)).astype(int), n - 1)
            fill = (levels[idx] * rows).astype(int)
            cap_y = np.clip((rows - 1) - (peaks[idx] * rows).astype(int), 0, rows - 1)
            cap_on = peaks[idx] > 0.02
            self._frame = ("spectrum", fill, cap_y, cap_on)
        elif self.mode == 1:
            idx = np.minimum((np.arange(bars) * (n / bars)).astype(int), n - 1)
            lv = levels[idx]
            # advance rain exactly once per frame (state lives here, not in render)
            self._rain_y += self._rain_speed * (0.2 + 3.0 * lv)
            respawn = self._rain_y > rows + 3
            if respawn.any():
                self._rain_y[respawn] = self._rng.random(int(respawn.sum())) * -2.0
                self._rain_speed[respawn] = 0.3 + self._rng.random(int(respawn.sum())) * 0.8
            trail = 1 + (lv * rows * 0.75).astype(int)
            self._frame = ("rain", self._rain_y.copy(), trail)
        else:
            self._frame = ("scope", self._scope_pts, self._scope_alive)

    # ------------------------------------------------------------------ render
    def render_line(self, y: int) -> Strip:
        if self._frame is None or self._frame_key is None:
            self._prepare_frame(max(self.size.width, 10), max(self.size.height, 1))
            if self._frame is None:
                return Strip([Segment(" " * max(self.size.width, 1))])
        kind = self._frame[0]
        if kind == "spectrum":
            return self._draw_spectrum(y, self._frame[1], self._frame[2], self._frame[3])
        if kind == "rain":
            return self._draw_rain(y, self._frame[1], self._frame[2])
        return self._draw_scope(y, self._frame[1], self._frame[2])

    def _draw_spectrum(self, y: int, fill: np.ndarray, cap_y: np.ndarray,
                       cap_on: np.ndarray) -> Strip:
        rows = max(self.size.height, 1)
        segs: list[Segment] = []
        for bar in range(len(fill)):
            if fill[bar] > 0 and y >= rows - fill[bar]:
                color = self.row_colors[min(rows - 1 - y, len(self.row_colors) - 1)]
                segs.append(Segment("█ ", _style(color)))
            elif cap_on[bar] and y == cap_y[bar]:
                segs.append(Segment("▄ ", _style(self.cap_color, bold=True)))
            else:
                segs.append(Segment("  "))
        return Strip(segs)

    def _draw_rain(self, y: int, heads: np.ndarray, trail: np.ndarray) -> Strip:
        dim = self._stops()[1]
        mid = self._stops()[2]
        bright = self._stops()[-1]
        segs: list[Segment] = []
        for bar in range(len(heads)):
            dist = heads[bar] - y  # cells above the head are older
            if 0 <= dist < trail[bar]:
                if dist < 1:
                    segs.append(Segment("01"[bar & 1], _style(bright, bold=True)))
                elif dist < trail[bar] * 0.4:
                    segs.append(Segment("01"[(bar + int(y)) & 1], _style(mid)))
                else:
                    segs.append(Segment("01"[(bar + int(y)) & 1], _style(dim)))
            else:
                segs.append(Segment(" "))
            if bar < len(heads) - 1:
                segs.append(Segment(" "))
        return Strip(segs)

    def _compute_scope(self, block: np.ndarray, width: int, rows: int) -> np.ndarray:
        wave = _downsample(block, width)
        center = (rows - 1) / 2.0
        amp = max(1.0, rows / 2.0 - 1)
        ys = center - wave * amp
        return np.clip(np.round(ys).astype(int), 0, rows - 1)

    def _draw_scope(self, y: int, pts: np.ndarray, alive: float) -> Strip:
        width = max(self.size.width, 10)
        rows = max(self.size.height, 1)
        hot = self._stops()[-1]
        dimc = self._stops()[1]
        center = (rows - 1) / 2.0
        near = abs(y - center) < 0.6
        segs: list[Segment] = []
        n = len(pts)
        for x in range(width):
            p = pts[min(int(x * n / width), n - 1)]
            if p == y:
                segs.append(Segment("●", _style(hot, bold=True)))
            elif near and x % 4 == 0:
                segs.append(Segment("·", _style(dimc)))
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
    """Waveform seek bar — click or drag to seek. Repaints only on change."""

    DEFAULT_CSS = """
    WaveBar { width: 1fr; height: 1; }
    """
    can_focus = False

    def __init__(self, engine: AudioEngine, theme: str, **kwargs):
        super().__init__(**kwargs)
        self.engine = engine
        self.theme_name = theme
        self.on_seek = None  # callback(fraction: float)
        self._last_key: tuple | None = None
        self.set_theme(theme)

    def set_theme(self, name: str) -> None:
        colors = themes.theme_colors(name)
        self._played = colors["played"]
        self._unplayed = colors["unplayed"]
        self._last_key = None
        self.refresh()

    def refresh_bar(self) -> None:
        """Called from the app heartbeat; repaints only when something moved."""
        key = (round(self.engine.position, 2), round(self.engine.duration, 2),
               self.size.width)
        if key != self._last_key:
            self._last_key = key
            self.refresh()

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
