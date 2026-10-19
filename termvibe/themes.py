"""Color themes — Textual theme registration + visualizer gradients."""

from __future__ import annotations

from textual.theme import Theme

# Each entry: textual theme + colors used by the spectrum/waveform widgets.
THEMES: dict[str, dict] = {
    "synthwave": {
        "theme": Theme(
            name="synthwave",
            primary="#ff2e88",
            secondary="#00e5ff",
            accent="#ffb84d",
            background="#0d0a1a",
            surface="#161130",
            panel="#1c1638",
            success="#3dff9e",
            warning="#ffd166",
            error="#ff4d6d",
            dark=True,
        ),
        "spectrum": ["#00e5ff", "#4d7cff", "#b44dff", "#ff2e88", "#ffd166"],
        "played": "#ff2e88",
        "unplayed": "#4d3d75",
    },
    "matrix": {
        "theme": Theme(
            name="matrix",
            primary="#00ff66",
            secondary="#39ff14",
            accent="#ccff00",
            background="#020a04",
            surface="#04180b",
            panel="#07250f",
            success="#39ff14",
            warning="#ccff00",
            error="#ff5555",
            dark=True,
        ),
        "spectrum": ["#043d1a", "#0d7a2e", "#39ff14", "#aaff00", "#eaffbf"],
        "played": "#39ff14",
        "unplayed": "#123d20",
    },
    "sunset": {
        "theme": Theme(
            name="sunset",
            primary="#ff7a18",
            secondary="#ff2e63",
            accent="#ffd166",
            background="#160b08",
            surface="#241209",
            panel="#301809",
            success="#ffb84d",
            warning="#ffd166",
            error="#ff2e63",
            dark=True,
        ),
        "spectrum": ["#5c1a05", "#c2410c", "#ff7a18", "#ff2e63", "#ffd166"],
        "played": "#ff7a18",
        "unplayed": "#5a3222",
    },
    "ice": {
        "theme": Theme(
            name="ice",
            primary="#7cd6ff",
            secondary="#4f7cff",
            accent="#b7f7ff",
            background="#060b16",
            surface="#0c1426",
            panel="#111d38",
            success="#7cffd6",
            warning="#ffe08a",
            error="#ff7a9e",
            dark=True,
        ),
        "spectrum": ["#12305c", "#2d6bb8", "#4f7cff", "#7cd6ff", "#e6faff"],
        "played": "#7cd6ff",
        "unplayed": "#2b3d5e",
    },
    "candy": {
        "theme": Theme(
            name="candy",
            primary="#ff8ad8",
            secondary="#8affff",
            accent="#fff08a",
            background="#140a18",
            surface="#20122a",
            panel="#2a1840",
            success="#8affc1",
            warning="#fff08a",
            error="#ff6a6a",
            dark=True,
        ),
        "spectrum": ["#8affff", "#7a8aff", "#c77dff", "#ff8ad8", "#fff08a"],
        "played": "#ff8ad8",
        "unplayed": "#4a3358",
    },
}

DEFAULT_THEME = "synthwave"


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
