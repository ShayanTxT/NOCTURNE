"""
NOCTURNE — offline audio intrusion unit.

A hacker-terminal music player: playlist, live spectrum / matrix-rain /
oscilloscope visualizers, waveform seek bar, boot sequence, themes.
"""

from __future__ import annotations

import random
import threading
from pathlib import Path

from rich.style import Style
from rich.text import Text
from textual import on
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Footer, Input, ListItem, ListView, Static

from . import __version__, config, metadata, scanner, themes
from .boot import BootScreen
from .engine import AudioEngine, TrackLoadError
from .widgets import LOGO_TEXT, SKULL, SpectrumWidget, WaveBar, gradient_text

IND_PLAY = "▶"
IND_PAUSE = "▌▌"
IND_IDLE = " "

HELP_ROWS = [
    ("space", "play / pause"),
    ("n  /  p", "next / previous track"),
    ("←  →", "seek −5s / +5s"),
    (",  .", "seek −30s / +30s"),
    ("+  −", "volume up / down"),
    ("m", "mute"),
    ("v", "visualizer: spectrum → rain → scope"),
    ("s", "shuffle"),
    ("r", "repeat mode (off / all / one)"),
    ("t", "next color theme"),
    ("f", "zen mode — giant visualizer"),
    ("/", "filter playlist"),
    ("enter / click", "play track"),
    ("click waveform", "seek"),
    ("o", "open folder or file"),
    ("F5", "rescan folder"),
    ("ctrl+s", "save playlist as M3U"),
    ("?", "this help"),
    ("q", "quit"),
]

_IDLE_WHISPERS = [
    "hello, friend.",
    "control is an illusion.",
    "no packets leave this machine.",
    "the rest is noise.",
]


class HelpScreen(ModalScreen):
    BINDINGS = [
        ("escape", "close", "Close"),
        ("q", "close", "Close"),
    ]
    DEFAULT_CSS = """
    HelpScreen { align: center middle; background: #00000099; }
    #help-box { width: 62; height: auto; max-height: 90%; padding: 1 2;
                border: round $primary; background: $surface; }
    #help-title { text-style: bold; color: $primary; margin-bottom: 1; }
    .help-row { height: 1; }
    .help-key { width: 16; color: $secondary; text-style: bold; }
    .help-desc { width: 1fr; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="help-box"):
            yield Static(f"nocturne(1) v{__version__} — key bindings", id="help-title")
            for key, desc in HELP_ROWS:
                with Horizontal(classes="help-row"):
                    yield Static(key, classes="help-key")
                    yield Static(desc, classes="help-desc")

    def action_close(self) -> None:
        self.dismiss()


class OpenScreen(ModalScreen):
    BINDINGS = [("escape", "close", "Cancel")]
    DEFAULT_CSS = """
    OpenScreen { align: center middle; background: #00000099; }
    #open-box { width: 72; height: auto; padding: 1 2; border: round $secondary;
                background: $surface; }
    #open-label { margin-bottom: 1; }
    """

    def __init__(self, initial: str = "", **kwargs):
        super().__init__(**kwargs)
        self._initial = initial

    def compose(self) -> ComposeResult:
        with Vertical(id="open-box"):
            yield Static("target folder (scanned recursively) or a single audio file:",
                         id="open-label")
            yield Input(placeholder="~/Music …", value=self._initial, id="open-input")

    def on_mount(self) -> None:
        self.query_one("#open-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        self.dismiss(value if value else None)

    def action_close(self) -> None:
        self.dismiss(None)


class NocturneApp(App):
    TITLE = "NOCTURNE"
    SUB_TITLE = f"v{__version__}"

    CSS = """
    #topbar { height: 1; padding: 0 1; }
    #logo { width: auto; text-style: bold; }
    #tagline { width: 1fr; color: $foreground-muted; padding-left: 2; }
    #topright { width: auto; color: $secondary; }

    #now { height: 3; padding: 0 1; background: $surface;
           border-top: solid $panel; border-bottom: solid $panel; }
    #np-left { width: 1fr; }
    #np-title { color: $text; text-style: bold; }
    #np-tech { color: $foreground-muted; }
    #np-time { width: 15; text-align: right; color: $secondary; text-style: bold; }

    #spectrum { height: 1fr; }
    #wavebox { height: 1; padding: 0 1; }

    #playlist { height: 12; background: $background; }
    .zen #playlist { display: none; }
    .zen #now, .zen #topbar { display: none; }

    .track-row { height: 1; }
    .row-ind { width: 2; color: $primary; }
    .row-num { width: 5; color: $foreground-muted; }
    .row-title { width: 1fr; text-overflow: ellipsis; }
    .row-dur { width: 7; text-align: right; color: $foreground-muted; }

    #splash { width: 1fr; height: 1fr; align: center middle; }
    #splash-box { width: auto; height: auto; align: center middle; }
    #splash-hint { margin-top: 1; text-style: italic; color: $foreground-muted; }

    #filterbar { height: 3; padding: 0 1; display: none; background: $surface; }
    #filterbar.visible { display: block; }

    #statusbar { height: 1; padding: 0 1; background: $panel; }
    """

    BINDINGS = [
        ("space", "toggle_play", "Play/Pause"),
        ("n", "next_track", "Next"),
        ("p", "prev_track", "Prev"),
        ("right", "seek_forward_5", "+5s"),
        ("left", "seek_back_5", "−5s"),
        ("full_stop", "seek_forward_30", "+30s"),
        ("comma", "seek_back_30", "−30s"),
        ("plus", "volume_up", "Vol+"),
        ("minus", "volume_down", "Vol−"),
        ("m", "toggle_mute", "Mute"),
        ("v", "cycle_vis", "Visualizer"),
        ("s", "toggle_shuffle", "Shuffle"),
        ("r", "cycle_repeat", "Repeat"),
        ("t", "cycle_theme", "Theme"),
        ("f", "toggle_zen", "Zen"),
        ("question_mark", "help", "Help"),
        ("slash", "show_filter", "Filter"),
        ("escape", "hide_filter", "Unfilter"),
        ("o", "open_folder", "Open"),
        ("f5", "rescan", "Rescan"),
        ("ctrl+s", "save_m3u", "Save M3U"),
        ("q", "quit", "Quit"),
    ]

    def __init__(
        self,
        start_path: str | Path | None = None,
        theme: str = themes.DEFAULT_THEME,
        shuffle: bool = False,
        repeat: str = "all",
        recursive: bool = True,
        visualizer: bool = True,
        vis_mode: int = 0,
        silent: bool = False,
        volume: float = 0.85,
        boot_sequence: bool = True,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.engine = AudioEngine(silent=silent, volume=volume)
        self.cfg = {
            "theme": theme,
            "shuffle": shuffle,
            "repeat": repeat,
            "recursive": recursive,
            "visualizer": visualizer,
            "vis_mode": int(vis_mode) % 3,
        }
        self.boot_sequence = boot_sequence
        self.folder: Path | None = None
        self.tracks: list[metadata.Track] = []
        self.view: list[int] = []            # indices into tracks (post-filter)
        self.rows: list[ListItem] = []
        self.current: int = -1               # index into tracks
        self._painted_current: int = -2
        self._status_msg: str = ""
        self._blink_counter: int = 0
        self.filter_text = ""
        self.zen = False
        self._shuffle_order: list[int] = []
        self._load_lock = threading.Lock()
        self._load_gen = 0
        self.pending_start = start_path

        themes.register_themes(self)
        self.theme = theme if theme in themes.THEMES else themes.DEFAULT_THEME

    # ---------------------------------------------------------------- layout
    def compose(self) -> ComposeResult:
        colors = self._colors()
        with Horizontal(id="topbar"):
            yield Static(gradient_text(LOGO_TEXT, colors["spectrum"][:2]), id="logo")
            yield Static("// offline audio intrusion unit — no packets leave this machine",
                         id="tagline")
            yield Static("", id="topright")
        with Horizontal(id="now"):
            with Vertical(id="np-left"):
                yield Static("> no signal — press [o] to mount a target folder",
                             id="np-title")
                yield Static("", id="np-tech")
            yield Static("00:00 / 00:00", id="np-time")
        yield SpectrumWidget(self.engine, self.theme, mode=self.cfg["vis_mode"], id="spectrum")
        with Vertical(id="wavebox"):
            yield WaveBar(self.engine, self.theme, id="wavebar")
        yield ListView(id="playlist")
        with Horizontal(id="filterbar"):
            yield Input(placeholder="filter by title / artist / filename … (esc to clear)",
                        id="filter-input")
        yield Static("", id="statusbar")
        yield Footer()

    def _colors(self) -> dict:
        return themes.theme_colors(self.theme)

    def on_mount(self) -> None:
        self.set_interval(0.12, self._heartbeat)
        self.query_one("#wavebar", WaveBar).on_seek = self._seek_fraction
        self._refresh_topright()

        # defer the intro until the main screen is fully up; skipped on tiny/degenerate PTYs
        if self.boot_sequence:
            self.call_after_refresh(self._push_boot)

        path = self.pending_start
        if not path:
            last = config.load_config().get("last_folder")
            if last and Path(last).exists():
                path = last
        if path:
            self._hide_splash()  # never shown yet; harmless
            self.call_after_refresh(self._open_path, path)
        else:
            self._show_splash()

        if not self.cfg["visualizer"]:
            self.query_one("#spectrum").display = False
        if self.engine.silent:
            self.notify(
                "No audio device found — ghost mode (visuals only).",
                title="nocturne",
                severity="warning",
                timeout=10,
            )

    # --------------------------------------------------------------- splash
    def _push_boot(self) -> None:
        if self.boot_sequence and self.size.width >= 60 and self.size.height >= 12:
            self.push_screen(
                BootScreen(ghost=self.engine.silent, device=self.engine.device_name or "")
            )

    def _show_splash(self) -> None:
        lv = self.query_one("#playlist", ListView)
        if lv.display:
            lv.display = False
            colors = self._colors()
            art = Text(SKULL, style=f"bold {colors['spectrum'][2]}")
            hello = Text("hello, friend.", style="italic")
            hint = Text("press [o] to mount your music · [?] for the man page",
                        style="dim")
            box = Vertical(Static(art), Static(hello, id="splash-hello"),
                           Static(hint, id="splash-hint"), id="splash-box")
            self.mount(Vertical(box, id="splash"), before="#playlist")

    def _hide_splash(self) -> None:
        try:
            self.query_one("#splash").display = False
        except Exception:
            pass
        self.query_one("#playlist", ListView).display = True

    # ---------------------------------------------------------------- theme
    def _refresh_topright(self) -> None:
        out = "ghost mode" if self.engine.silent else (self.engine.device_name or "audio output")
        if len(out) > 30:
            out = out[:29] + "…"
        self.query_one("#topright", Static).update(f"{self.theme} · {out}")

    def action_cycle_theme(self) -> None:
        self.theme = themes.next_theme(self.theme)
        colors = self._colors()
        self.query_one("#logo", Static).renderable = gradient_text(
            LOGO_TEXT, colors["spectrum"][:2]
        )
        self.query_one("#spectrum", SpectrumWidget).set_theme(self.theme)
        self.query_one("#wavebar", WaveBar).set_theme(self.theme)
        self._refresh_topright()
        self._paint_current_row(force=True)
        self.notify(f"theme: {self.theme}", timeout=2)

    def action_cycle_vis(self) -> None:
        spectrum = self.query_one("#spectrum", SpectrumWidget)
        mode = spectrum.cycle_mode()
        self.cfg["vis_mode"] = mode
        self.notify(f"visualizer: {themes.MODE_NAMES[mode]}", timeout=1)

    # --------------------------------------------------------------- opening
    def _open_path(self, raw: str) -> None:
        path = Path(str(raw)).expanduser()
        if not path.exists():
            self.notify(f"target not found: {path}", severity="error", title="open")
            return
        self.folder = path if path.is_dir() else path.parent
        self._hide_splash()
        self._set_status(f"indexing {self._short_folder()} …")
        threading.Thread(
            target=self._scan_worker,
            args=(self.folder, self.cfg["recursive"]),
            daemon=True,
        ).start()

    def _scan_worker(self, folder: Path, recursive: bool) -> None:
        import soundfile as sf

        files = scanner.scan_folder(folder, recursive=recursive)
        tracks: list[metadata.Track] = []
        for p in files:
            try:
                info = sf.info(str(p))
            except Exception:
                continue
            t = metadata.Track(
                path=p,
                duration=info.frames / max(info.samplerate, 1),
                samplerate=info.samplerate,
                format=info.format,
                subtype=info.subtype,
                size_bytes=p.stat().st_size,
            )
            t.tags = metadata.read_tags(p)
            tracks.append(t)
        self.call_from_thread(self._scan_done, folder, tracks)

    def _scan_done(self, folder: Path, tracks: list[metadata.Track]) -> None:
        self.tracks = tracks
        self.current = -1
        self._painted_current = -2
        total = sum(t.duration for t in tracks)
        self._apply_filter()
        self._set_status(
            f"{len(tracks)} files indexed · {metadata.fmt_time(total)} total"
        )
        if tracks:
            self.notify(f"{len(tracks)} tracks indexed", title="nocturne", timeout=3)
            self._play_index(0)
        else:
            self.notify("no playable audio in target.", severity="warning", title="nocturne")

    # -------------------------------------------------------------- playlist
    def _make_row(self, ti: int) -> ListItem:
        t = self.tracks[ti]
        ind = Static(IND_IDLE, classes="row-ind")
        num = Static(f"{ti + 1:>3}", classes="row-num")
        title = Static(self._short(t.title, 80), classes="row-title")
        dur = Static(metadata.fmt_time(t.duration), classes="row-dur")
        item = ListItem(Horizontal(ind, num, title, dur), classes="track-row")
        item._tv_refs = (ind, num, title, dur)  # type: ignore[attr-defined]
        item._track_index = ti  # type: ignore[attr-defined]
        return item

    @staticmethod
    def _short(s: str, n: int) -> str:
        return s if len(s) <= n else s[: n - 1] + "…"

    def _short_folder(self) -> str:
        if self.folder is None:
            return "~"
        try:
            return "~/" + str(self.folder.expanduser().relative_to(Path.home()))
        except ValueError:
            return self.folder.name or str(self.folder)

    def _rebuild_playlist(self) -> None:
        lv = self.query_one("#playlist", ListView)
        lv.clear()
        self.rows = [self._make_row(ti) for ti in self.view]
        if self.rows:
            lv.extend(self.rows)
        self._painted_current = -2
        self._paint_current_row(force=True)

    def _paint_current_row(self, force: bool = False) -> None:
        """Refresh only the rows whose look changed (current vs previous)."""
        cur = self.current
        if cur == self._painted_current and not force:
            return
        primary = self._colors()["theme"].primary
        for row in self.rows:
            ti = getattr(row, "_track_index", -1)
            if ti not in (cur, self._painted_current) and not force:
                continue
            ind, num, title, dur = row._tv_refs  # type: ignore[attr-defined]
            if ti == cur:
                playing = self.engine.playing
                ind.update(IND_PLAY if playing else IND_PAUSE)
                title.update(Text(self._short(self.tracks[ti].title, 80),
                                  style=f"bold {primary}"))
            else:
                ind.update(IND_IDLE)
                title.update(Text(self._short(self.tracks[ti].title, 80)))
        self._painted_current = cur

    @on(ListView.Selected, "#playlist")
    def _playlist_selected(self, event: ListView.Selected) -> None:
        ti = getattr(event.item, "_track_index", None)
        if ti is not None:
            self._play_index(ti)

    # --------------------------------------------------------------- loading
    def _play_index(self, ti: int) -> None:
        if not (0 <= ti < len(self.tracks)):
            return
        self._hide_splash()
        self._load_gen += 1
        gen = self._load_gen
        self._set_status(f"decrypting {self.tracks[ti].path.name} …")

        def work() -> None:
            with self._load_lock:  # serialize engine access
                if gen != self._load_gen:  # a newer request superseded us
                    return
                try:
                    info = self.engine.load(self.tracks[ti].path)
                except TrackLoadError as exc:
                    self.call_from_thread(self._load_failed, ti, str(exc), gen)
                    return
                self.call_from_thread(self._load_ok, ti, info, gen)

        threading.Thread(target=work, daemon=True).start()

    def _load_failed(self, ti: int, err: str, gen: int) -> None:
        if gen != self._load_gen:
            return
        name = self.tracks[ti].path.name
        self.notify(f"skipped {name}: {err}", severity="error", title="playback")
        nxt = ti + 1
        if nxt < len(self.tracks):
            self._play_index(nxt)
        else:
            self._set_status("nothing playable in target")

    def _load_ok(self, ti: int, info: dict, gen: int) -> None:
        if gen != self._load_gen:
            return
        self.current = ti
        self.engine.play()
        t = self.tracks[ti]
        tech_bits = [t.subtitle, f"{info['format']}.{info['subtype']}",
                     f"{info['samplerate'] / 1000:g} kHz"]
        if t.tags.bitrate_kbps:
            tech_bits.append(f"{t.tags.bitrate_kbps}kbps")
        if t.tags.year:
            tech_bits.append(t.tags.year)
        self.query_one("#np-title", Static).update(
            Text(f"> NOW PLAYING [{ti + 1}/{len(self.tracks)}] {t.title}", style="bold")
        )
        self.query_one("#np-tech", Static).update("  ·  ".join(tech_bits))
        self._paint_current_row(force=True)
        self._scroll_to_current()
        self._set_status(f"injected {t.path.name} into /dev/audio")
        if self.cfg["shuffle"]:
            self._refresh_shuffle_order()

    def _scroll_to_current(self) -> None:
        for vi, ti in enumerate(self.view):
            if ti == self.current:
                try:
                    self.rows[vi].scroll_visible(animate=False)
                except Exception:
                    pass
                break

    # -------------------------------------------------------------- transport
    def action_toggle_play(self) -> None:
        if self.current < 0:
            if self.tracks:
                self._play_index(self.view[0] if self.view else 0)
            return
        playing = self.engine.toggle()
        t = self.tracks[self.current]
        label = "NOW PLAYING" if playing else "PAUSED"
        self.query_one("#np-title", Static).update(
            Text(f"> {label} [{self.current + 1}/{len(self.tracks)}] {t.title}",
                 style="bold")
        )
        self._paint_current_row(force=True)

    def _play_order(self) -> list[int]:
        if self.cfg["shuffle"] and self._shuffle_order:
            return self._shuffle_order
        return list(range(len(self.tracks)))

    def _refresh_shuffle_order(self) -> None:
        order = list(range(len(self.tracks)))
        random.shuffle(order)
        if self.current in order:
            order.remove(self.current)
            order.insert(0, self.current)
        self._shuffle_order = order

    def _next_index(self, direction: int, auto: bool) -> int | None:
        n = len(self.tracks)
        if n == 0:
            return None
        if auto and self.cfg["repeat"] == "one" and self.current >= 0:
            return self.current
        order = self._play_order()
        pos = order.index(self.current) if self.current in order else -1
        nxt = pos + direction
        if nxt >= n:
            if auto and self.cfg["repeat"] == "off":
                return None
            nxt = 0
        if nxt < 0:
            nxt = n - 1
        return order[nxt]

    def action_next_track(self) -> None:
        idx = self._next_index(+1, auto=False)
        if idx is not None:
            self._play_index(idx)

    def action_prev_track(self) -> None:
        if self.engine.position > 3.0:
            self.engine.seek(0)
            return
        idx = self._next_index(-1, auto=False)
        if idx is not None:
            self._play_index(idx)

    def _auto_advance(self) -> None:
        idx = self._next_index(+1, auto=True)
        if idx is None:
            self._set_status("transmission ended · press [n] to restart")
            return
        self._play_index(idx)

    def _seek_fraction(self, frac: float) -> None:
        self.engine.seek(frac * self.engine.duration)

    def action_seek_forward_5(self) -> None:
        self.engine.seek_relative(5)

    def action_seek_back_5(self) -> None:
        self.engine.seek_relative(-5)

    def action_seek_forward_30(self) -> None:
        self.engine.seek_relative(30)

    def action_seek_back_30(self) -> None:
        self.engine.seek_relative(-30)

    def action_volume_up(self) -> None:
        v = self.engine.volume_up()
        self.notify(f"vol {int(v * 100)}%", timeout=1)

    def action_volume_down(self) -> None:
        v = self.engine.volume_down()
        self.notify(f"vol {int(v * 100)}%", timeout=1)

    def action_toggle_mute(self) -> None:
        self.notify("muted" if self.engine.toggle_mute() else "unmuted", timeout=1)

    # ------------------------------------------------------------------ modes
    def action_toggle_shuffle(self) -> None:
        self.cfg["shuffle"] = not self.cfg["shuffle"]
        if self.cfg["shuffle"]:
            self._refresh_shuffle_order()
        self.notify(f"shuffle {'on' if self.cfg['shuffle'] else 'off'}", timeout=2)

    def action_cycle_repeat(self) -> None:
        modes = ["off", "all", "one"]
        self.cfg["repeat"] = modes[(modes.index(self.cfg["repeat"]) + 1) % 3]
        self.notify(f"repeat: {self.cfg['repeat']}", timeout=2)

    def action_toggle_zen(self) -> None:
        self.zen = not self.zen
        self.set_class(self.zen, "zen")

    def action_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_show_filter(self) -> None:
        self.query_one("#filterbar").add_class("visible")
        self.query_one("#filter-input", Input).focus()

    def action_hide_filter(self) -> None:
        bar = self.query_one("#filterbar")
        if bar.has_class("visible"):
            bar.remove_class("visible")
            inp = self.query_one("#filter-input", Input)
            if self.filter_text:
                inp.value = ""
                self.filter_text = ""
                self._apply_filter()
            self.set_focus(None)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "filter-input":
            self.filter_text = event.value.strip().lower()
            self._apply_filter()

    def _apply_filter(self) -> None:
        q = self.filter_text
        if not q:
            self.view = list(range(len(self.tracks)))
        else:
            self.view = [
                i for i, t in enumerate(self.tracks)
                if q in t.title.lower()
                or q in t.tags.artist.lower()
                or q in t.path.name.lower()
            ]
        try:
            self._rebuild_playlist()
        except Exception:
            pass  # UI not mounted yet

    # ------------------------------------------------------------------- misc
    def action_open_folder(self) -> None:
        self.push_screen(OpenScreen(initial=str(self.folder) if self.folder else ""),
                         callback=self._on_open_result)

    def _on_open_result(self, result: str | None) -> None:
        if result:
            self._open_path(result)

    def action_rescan(self) -> None:
        if self.folder:
            self._open_path(str(self.folder))

    def action_save_m3u(self) -> None:
        if not self.tracks:
            self.notify("nothing to save.", severity="warning", timeout=2)
            return
        target = (self.folder or Path.cwd()) / "nocturne_playlist.m3u"
        lines = ["#EXTM3U"]
        for t in self.tracks:
            artist = t.tags.artist or ""
            lines.append(f"#EXTINF:{int(t.duration)},{artist} - {t.title}")
            lines.append(str(t.path.resolve()))
        try:
            target.write_text("\n".join(lines) + "\n", encoding="utf-8")
            self.notify(f"saved {target.name}", title="m3u", timeout=3)
        except OSError as exc:
            self.notify(f"save failed: {exc}", severity="error", timeout=4)

    # ---------------------------------------------------------------- updates
    def _set_status(self, msg: str) -> None:
        self._status_msg = msg
        self._render_status()

    def _render_status(self) -> None:
        blink_on = (self._blink_counter % 8) < 5
        cursor = "▊" if blink_on else " "
        prompt = Text()
        prompt.append(f"root@nocturne:{self._short_folder()}$ ",
                      style=Style(color=self._colors()["theme"].primary, bold=True))
        prompt.append(cursor, style=Style(color=self._colors()["theme"].primary))
        if self._status_msg:
            prompt.append(f" {self._status_msg}", style=Style(dim=True))
        # right side: mode flags
        modes: list[str] = []
        modes.append("SHUF" if self.cfg["shuffle"] else "SEQ")
        modes.append(f"RPT:{self.cfg['repeat'].upper()}")
        modes.append("MUTE" if self.engine.muted else f"VOL:{int(self.engine.volume * 100)}")
        if self.tracks:
            modes.append(f"{len(self.view)}/{len(self.tracks)} FILES")
        right = " ".join(f"[{m}]" for m in modes)
        width = max(20, self.size.width)
        pad = max(1, width - len(prompt.plain) - len(right) - 1)
        prompt.append(" " * pad, style=Style(dim=True))
        prompt.append(right, style=Style(dim=True, bold=True))
        try:
            self.query_one("#statusbar", Static).update(prompt)
        except Exception:
            pass

    def _heartbeat(self) -> None:
        self._blink_counter += 1
        if self.engine.consume_ended():
            self._auto_advance()
        pos, dur = self.engine.position, self.engine.duration
        try:
            self.query_one("#np-time", Static).update(
                f"{metadata.fmt_time(pos)} / {metadata.fmt_time(dur)}"
            )
            self.query_one("#wavebar", WaveBar).refresh()
            self._render_status()
        except Exception:
            pass

    # ------------------------------------------------------------------- exit
    def on_unmount(self) -> None:
        cfg = config.load_config()
        cfg.update(
            {
                "last_folder": str(self.folder) if self.folder else cfg.get("last_folder", ""),
                "volume": self.engine.volume,
                "theme": self.theme,
                "shuffle": self.cfg["shuffle"],
                "repeat": self.cfg["repeat"],
                "recursive": self.cfg["recursive"],
                "visualizer": self.cfg["visualizer"],
                "vis_mode": self.cfg["vis_mode"],
            }
        )
        config.save_config(cfg)
        self.engine.close()
