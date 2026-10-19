"""Color themes — hacker/CRT palettes + Textual theme registration."""

from __future__ import annotations

from textual.theme import Theme

# Each entry: textual theme + colors used by the spectrum/waveform widgets.
THEMES: dict[str, dict] = {
    "fsociety": {
        "theme": Theme(
            name="fsociety",
            primary="#00ff41",
            secondary="#ff1133",
            accent="#ffb000",
            background="#050505",
            surface="#0b0f0b",
            panel="#0f170f",
            success="#00ff41",
            warning="#ffb000",
            error="#ff1133",
            dark=True,
        ),
        "spectrum": ["#052b0e", "#0a5c1c", "#12a534", "#00ff41", "#c8ffd4"],
        "played": "#00ff41",
        "unplayed": "#14351c",
    },
    "redroom": {
        "theme": Theme(
            name="redroom",
            primary="#ff2a2a",
            secondary="#ffb000",
            accent="#ffd166",
            background="#070303",
            surface="#120705",
            panel="#1a0a06",
            success="#ff8c42",
            warning="#ffb000",
            error="#ff2a2a",
            dark=True,
        ),
        "spectrum": ["#3b0a0a", "#7a1414", "#c41e1e", "#ff2a2a", "#ffc9b0"],
        "played": "#ff2a2a",
        "unplayed": "#3a1616",
    },
    "crt": {
        "theme": Theme(
            name="crt",
            primary="#ffb000",
            secondary="#ff7b00",
            accent="#ffe08a",
            background="#060400",
            surface="#120b02",
            panel="#1a1206",
            success="#ffb000",
            warning="#ffe08a",
            error="#ff5c00",
            dark=True,
        ),
        "spectrum": ["#3b2500", "#7a4d00", "#c47f00", "#ffb000", "#ffedbf"],
        "played": "#ffb000",
        "unplayed": "#3a2c10",
    },
    "cipher": {
        "theme": Theme(
            name="cipher",
            primary="#00e5ff",
            secondary="#7cd6ff",
            accent="#b7f7ff",
            background="#020608",
            surface="#06121a",
            panel="#0a1a26",
            success="#00e5ff",
            warning="#ffe08a",
            error="#ff2a2a",
            dark=True,
        ),
        "spectrum": ["#053043", "#0a5c7a", "#0f9ec4", "#00e5ff", "#ccf6ff"],
        "played": "#00e5ff",
        "unplayed": "#123842",
    },
    "ghost": {
        "theme": Theme(
            name="ghost",
            primary="#b44dff",
            secondary="#ff2e88",
            accent="#8affff",
            background="#050308",
            surface="#0f0916",
            panel="#160d20",
            success="#8affc1",
            warning="#ffe08a",
            error="#ff2e88",
            dark=True,
        ),
        "spectrum": ["#2b0a4d", "#5c1494", "#8a2be2", "#b44dff", "#e8ccff"],
        "played": "#b44dff",
        "unplayed": "#2e1a42",
    },
}

DEFAULT_THEME = "fsociety"

MODE_NAMES = ["spectrum", "matrix rain", "oscilloscope"]


def register_themes(app) -> None:
    for entry in THEMES.values():
        app.register_theme(entry["theme"])


def theme_colors(name: str) -> dict:
    return THEMES.get(name, THEMES[DEFAULT_THEME])


def next_theme(name: str) -> str:
    names = list(THEMES)
    try:
        i = names.index(name)
    except ValueError:
        return DEFAULT_THEME
    return names[(i + 1) % len(names)]


def lerp_gradient(steps: int, stops: list[str]) -> list[str]:
    """Interpolate hex colors into `steps` shades (index 0 = first stop)."""
    def hx(c: str) -> tuple[int, int, int]:
        c = c.lstrip("#")
        return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)

    out: list[str] = []
    if len(stops) == 1 or steps == 1:
        return [stops[0]] * steps
    seg = (len(stops) - 1) / max(1, steps - 1)
    for i in range(steps):
        pos = i * seg
        j = min(int(pos), len(stops) - 2)
        t = pos - j
        a, b = hx(stops[j]), hx(stops[j + 1])
        rgb = tuple(int(a[k] + (b[k] - a[k]) * t) for k in range(3))
        out.append(f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}")
    return out
