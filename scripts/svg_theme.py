#!/usr/bin/env python3
"""Shared SVG helpers for the generated GitHub profile graphics."""

from __future__ import annotations

import base64
import html
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "assets"
FONT_DIR = Path(__file__).resolve().parent / "fonts"

WIDTH = 620
LIGHT = {
    "ink": "#72512f",
    "strong": "#352519",
    "accent": "#0f766e",
    "muted": "#6b7280",
    "rule": "#d8dee4",
    "surface": "#ffffff",
}
DARK = {
    "ink": "#d6b483",
    "strong": "#f6d79b",
    "accent": "#5eead4",
    "muted": "#9ca3af",
    "rule": "#30363d",
    "surface": "#0d1117",
}
FONT_FAMILY = "ProfileMono,ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"


def escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def font_face(filename: str, weight: int) -> str:
    encoded = base64.b64encode((FONT_DIR / filename).read_bytes()).decode("ascii")
    return (
        "@font-face{font-family:ProfileMono;font-style:normal;"
        f"font-weight:{weight};font-display:block;"
        f"src:url(data:font/woff2;base64,{encoded}) format('woff2')}}"
    )


def theme_css(*, regular: bool = True, semibold: bool = True) -> str:
    fonts = ""
    if regular:
        fonts += font_face("jbmono-400.woff2", 400)
    if semibold:
        fonts += font_face("jbmono-600.woff2", 600)

    def palette(values: dict[str, str]) -> str:
        return (
            f".ink{{fill:{values['ink']}}}"
            f".strong{{fill:{values['strong']}}}"
            f".accent{{fill:{values['accent']}}}"
            f".accent-stroke{{stroke:{values['accent']}}}"
            f".muted{{fill:{values['muted']}}}"
            f".rule{{stroke:{values['rule']}}}"
            f".surface{{fill:{values['surface']}}}"
        )

    return (
        f"<style>{fonts}{palette(LIGHT)}"
        f"@media(prefers-color-scheme:dark){{{palette(DARK)}}}</style>"
    )


def svg_open(width: int, height: int, *, title: str, description: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}" '
        f'font-family="{FONT_FAMILY}" role="img" aria-labelledby="title desc">'
        f"<title id=\"title\">{escape(title)}</title>"
        f"<desc id=\"desc\">{escape(description)}</desc>"
        f"{theme_css()}"
    )


def text(
    x: float,
    y: float,
    value: object,
    *,
    size: float = 12,
    css_class: str = "ink",
    weight: int = 400,
    anchor: str = "start",
    letter_spacing: float | None = None,
) -> str:
    attrs = [
        f'x="{x:.1f}"',
        f'y="{y:.1f}"',
        f'font-size="{size}"',
        f'font-weight="{weight}"',
        f'class="{css_class}"',
    ]
    if anchor != "start":
        attrs.append(f'text-anchor="{anchor}"')
    if letter_spacing is not None:
        attrs.append(f'letter-spacing="{letter_spacing}"')
    return f"<text {' '.join(attrs)}>{escape(value)}</text>"


def fade(begin: float, duration: float = 0.42) -> str:
    return (
        '<animate attributeName="opacity" from="0" to="1" '
        f'begin="{begin:.2f}s" dur="{duration:.2f}s" fill="freeze"/>'
    )


def write_if_changed(path: Path, content: str) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False
    path.write_text(content, encoding="utf-8")
    return True
