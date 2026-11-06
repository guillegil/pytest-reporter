"""Colour tokens, contrast and themes in the HTML report.

The report has a dark theme (default), a light theme (from the OS setting or
the header toggle) and a print sheet. Colours live in tokens, so a theme only
remaps roles. Contrast is checked here from the token values themselves; the
rendered page was also measured in Chromium.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

from pytest_reporter._html_builder._css import _LIGHT_TOKENS, CSS
from pytest_reporter._html_builder._js import JS

if TYPE_CHECKING:
    from pytest import Pytester


def _tokens(block: str) -> dict[str, str]:
    return dict(re.findall(r"--([\w-]+):\s*(#[0-9A-Fa-f]{6})\s*;", block))


def _dark_tokens() -> dict[str, str]:
    root = CSS[CSS.index(":root {") : CSS.index("}", CSS.index(":root {"))]
    return _tokens(root)


def _rgb(hex_: str) -> tuple[int, int, int]:
    h = hex_.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _luminance(c: tuple[float, float, float]) -> float:
    def ch(v: float) -> float:
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    r, g, b = c
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def _contrast(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    la, lb = _luminance(a), _luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def _mix(top: str, under: str, amount: float) -> tuple[float, float, float]:
    t, u = _rgb(top), _rgb(under)
    return tuple(t[i] * amount + u[i] * (1 - amount) for i in range(3))  # type: ignore[return-value]


def _theme(name: str) -> tuple[dict[str, str], float]:
    dark = _dark_tokens()
    if name == "dark":
        return dark, 0.14
    return {**dark, **_tokens(_LIGHT_TOKENS)}, 0.12


SURFACES = ("bg", "surface", "surface2", "surface3")
STATUSES = ("passed", "failed", "skipped", "error", "accent")


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_secondary_text_passes_aa_on_every_surface(theme: str) -> None:
    t, _ = _theme(theme)
    for text in ("c-text", "c-text2", "c-text3"):
        for surface in SURFACES:
            ratio = _contrast(_rgb(t[text]), _rgb(t[f"c-{surface}"]))
            assert ratio >= 4.5, f"{theme}: {text} on {surface} is {ratio:.2f}:1"


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_status_ink_passes_aa_on_its_tint(theme: str) -> None:
    t, tint = _theme(theme)
    for status in STATUSES:
        ink = _rgb(t[f"c-{status}-ink"])
        for surface in SURFACES:
            bg = _mix(t[f"c-{status}"], t[f"c-{surface}"], tint)
            ratio = _contrast(ink, bg)
            assert ratio >= 4.5, f"{theme}: {status} ink on its tint over {surface}: {ratio:.2f}"


def test_graph_colours_are_the_same_in_every_theme() -> None:
    dark = _dark_tokens()
    assert dark["c-passed"] == "#22C55E"
    assert dark["c-failed"] == "#EF4444"
    assert dark["c-skipped"] == "#F59E0B"
    assert dark["c-error"] == "#F97316"
    light = _tokens(_LIGHT_TOKENS)
    assert not {"c-passed", "c-failed", "c-skipped", "c-error"} & light.keys()


def test_colours_come_from_tokens() -> None:
    body = CSS[CSS.index("Reset & base") :]
    # Status tints are mixed from the tokens, never written out.
    assert not re.search(r"rgba\((34,197,94|239,68,68|245,158,11|249,115,22|59,130,246)", CSS)
    assert "#FF6B6B" not in body
    assert "--c-failed-text" not in CSS
    # Status text uses the ink tokens, not the graph fills.
    assert not re.search(r"(?<![-\w])color: var\(--c-(passed|failed|skipped|error|accent)\)", body)
    # The JS draws charts with the tokens too.
    assert not re.search(r"#[0-9A-Fa-f]{6}\b|rgba\(", JS)
    assert "var(--c-passed)" in JS


def test_light_theme_follows_os_toggle_and_print(pytester: Pytester) -> None:
    pytester.makepyfile("def test_ok():\n    pass\n")
    pytester.runpytest("--report-dir=reports")
    runs = sorted((pytester.path / "reports" / "runs").iterdir())
    html = (runs[0] / "report.html").read_text(encoding="utf-8")

    assert "@media (prefers-color-scheme: light)" in html
    assert ':root:not([data-theme="dark"])' in html
    assert ':root[data-theme="light"]' in html
    assert "@media print" in html
    assert html.count("--c-text3: #526174;") == 3
    # The toggle is a labelled button; the saved choice applies before paint.
    assert 'id="theme-toggle" type="button" aria-label="Switch to light theme"' in html
    assert html.index('<script id="theme-boot">') < html.index("<body>")
    assert "localStorage.setItem('pytest-reporter-theme'" in html


def test_type_scale_has_an_11px_floor() -> None:
    from pytest_reporter._html_builder._js import JS

    scale = dict(re.findall(r"--fs-([\w]+):\s*(\d+)px;", CSS))
    assert scale == {
        "xs": "11",
        "sm": "12",
        "md": "13",
        "lg": "15",
        "xl": "18",
        "2xl": "24",
        "3xl": "36",
    }
    # Every size in the rules and the inline JS styles comes from the scale.
    body = CSS[CSS.index("Reset & base") :]
    assert not re.findall(r"font-size:\s*\d+px", body)
    assert not re.findall(r"font-size:\s*\d+px|'font-size':", JS)
    assert not re.search(r"font-weight:\s*[38]00", CSS)
