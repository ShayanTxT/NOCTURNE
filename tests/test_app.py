"""End-to-end UI tests using Textual's test pilot (silent mode)."""

from __future__ import annotations

import pytest

from nocturne.app import NocturneApp


@pytest.fixture()
def demo(tmp_path):
    """A tiny library: two playable 2s tracks + one broken file."""
    import numpy as np
    import soundfile as sf

    sr = 8000
    t = np.linspace(0, 45.0, int(sr * 45.0), endpoint=False, dtype=np.float32)
    for i, name in enumerate(("01_one.wav", "02_two.wav")):
        tone = (0.4 * np.sin(2 * np.pi * (300 + 100 * i) * t)).astype(np.float32)
        sf.write(str(tmp_path / name), np.stack([tone] * 2, axis=1), sr)
    (tmp_path / "03_broken.wav").write_bytes(b"garbage")
    (tmp_path / "readme.txt").write_text("not audio")
    return tmp_path


async def test_app_scans_and_autoplays(demo) -> None:
    async with NocturneApp(start_path=str(demo), silent=True, boot_sequence=False).run_test() as pilot:
        await pilot.pause(1.5)
        app = pilot.app
        assert len(app.tracks) == 2          # broken + txt skipped
        assert app.current == 0
        assert app.engine.playing


async def test_next_prev(demo) -> None:
    async with NocturneApp(start_path=str(demo), silent=True, boot_sequence=False).run_test() as pilot:
        await pilot.pause(1.5)
        app = pilot.app
        await pilot.press("n")
        await pilot.pause(0.8)
        assert app.current == 1
        await pilot.press("p")
        await pilot.pause(0.8)
        assert app.current == 0


async def test_auto_advance_at_end(demo) -> None:
    async with NocturneApp(start_path=str(demo), silent=True, boot_sequence=False).run_test() as pilot:
        await pilot.pause(1.5)
        app = pilot.app
        app.engine.seek(app.engine.duration - 0.3)   # near the end
        await pilot.pause(1.2)
        assert app.current == 1                      # repeat:all advances
        assert app.engine.playing


async def test_repeat_one_stays(demo) -> None:
    async with NocturneApp(start_path=str(demo), silent=True, repeat="one", boot_sequence=False).run_test() as pilot:
        await pilot.pause(1.5)
        app = pilot.app
        app.engine.seek(app.engine.duration - 0.3)
        await pilot.pause(1.2)
        assert app.current == 0
        assert app.engine.position < app.engine.duration  # restarted


async def test_repeat_off_stops(demo) -> None:
    async with NocturneApp(start_path=str(demo), silent=True, repeat="off", boot_sequence=False).run_test() as pilot:
        await pilot.pause(1.5)
        app = pilot.app
        await pilot.press("n")            # jump to the last track
        await pilot.pause(0.8)
        app.engine.seek(app.engine.duration - 0.3)
        await pilot.pause(1.2)
        assert not app.engine.playing     # playlist finished -> stop


async def test_toggle_pause(demo) -> None:
    async with NocturneApp(start_path=str(demo), silent=True, boot_sequence=False).run_test() as pilot:
        await pilot.pause(1.5)
        app = pilot.app
        await pilot.press("space")
        assert not app.engine.playing
        await pilot.press("space")
        assert app.engine.playing


async def test_volume_and_mute_keys(demo) -> None:
    async with NocturneApp(start_path=str(demo), silent=True, boot_sequence=False).run_test() as pilot:
        await pilot.pause(1.5)
        app = pilot.app
        start = app.engine.volume
        await pilot.press("plus")
        assert app.engine.volume == pytest.approx(start + 0.05)
        await pilot.press("minus")
        await pilot.press("m")
        assert app.engine.muted
        await pilot.press("m")
        assert not app.engine.muted


async def test_seek_keys(demo) -> None:
    async with NocturneApp(start_path=str(demo), silent=True, boot_sequence=False).run_test() as pilot:
        await pilot.pause(1.5)
        app = pilot.app
        await pilot.press("space")        # pause -> position stays put
        app.engine.seek(1.0)
        pos = app.engine.position
        await pilot.press("right")
        assert app.engine.position >= pos + 4     # +5s
        await pilot.press("full_stop")
        assert app.engine.position >= pos + 30    # +30s
        await pilot.press("comma")
        assert app.engine.position <= pos + 6     # −30s


async def test_filter_playlist(demo) -> None:
    async with NocturneApp(start_path=str(demo), silent=True, boot_sequence=False).run_test() as pilot:
        await pilot.pause(1.5)
        app = pilot.app
        app.filter_text = "two"
        app._apply_filter()
        await pilot.pause()
        assert app.view == [1]
        app.filter_text = ""
        app._apply_filter()
        await pilot.pause()
        assert app.view == [0, 1]


async def test_theme_cycle_and_zen(demo) -> None:
    async with NocturneApp(start_path=str(demo), silent=True, theme="cipher", boot_sequence=False).run_test() as pilot:
        await pilot.pause(1.5)
        app = pilot.app
        await pilot.press("t")
        assert app.theme == "ghost"   # cipher -> ghost in theme order
        await pilot.press("f")
        assert app.has_class("zen")
        await pilot.press("f")
        assert not app.has_class("zen")


async def test_shuffle_and_repeat_cycle(demo) -> None:
    async with NocturneApp(start_path=str(demo), silent=True, boot_sequence=False).run_test() as pilot:
        await pilot.pause(1.5)
        app = pilot.app
        assert app.cfg["repeat"] == "all"
        await pilot.press("s")
        assert app.cfg["shuffle"] is True
        await pilot.press("r")
        assert app.cfg["repeat"] == "one"
        await pilot.press("r")
        assert app.cfg["repeat"] == "off"


async def test_help_screen(demo) -> None:
    async with NocturneApp(start_path=str(demo), silent=True, boot_sequence=False).run_test() as pilot:
        await pilot.pause(1.5)
        app = pilot.app
        await pilot.press("question_mark")
        await pilot.pause()
        from textual.screen import ModalScreen

        assert isinstance(app.screen, ModalScreen)
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, ModalScreen)


async def test_splash_shown_without_path() -> None:
    async with NocturneApp(silent=True, boot_sequence=False).run_test() as pilot:
        await pilot.pause(0.8)
        app = pilot.app
        assert app.tracks == []
        assert not app.query_one("#playlist").display  # splash replaces list


async def test_open_screen_flow(demo) -> None:
    async with NocturneApp(silent=True, boot_sequence=False).run_test() as pilot:
        await pilot.pause(0.8)
        app = pilot.app
        await pilot.press("o")
        await pilot.pause()
        app.screen.query_one("#open-input").value = str(demo)
        await pilot.press("enter")
        await pilot.pause(2.0)
        assert len(app.tracks) == 2
        assert app.folder == demo
