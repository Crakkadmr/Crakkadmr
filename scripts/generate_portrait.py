#!/usr/bin/env python3
"""Generate a self-typing ASCII portrait from the profile's source photo.

This is intentionally a one-off generator. The scheduled workflow refreshes
GitHub statistics, while the portrait changes only when its source photo does.

Usage:
    python scripts/generate_portrait.py
    python scripts/generate_portrait.py --preview
    python scripts/generate_portrait.py --crop 145,75,380,285
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from svg_theme import ASSET_DIR, FONT_FAMILY, ROOT, escape, font_face, write_if_changed

RAMP = ".:;-=+*cs#%@"
COLS = 96
ROW_RATIO = 0.49
FONT_SIZE = 10.5
CHAR_WIDTH = FONT_SIZE * 0.6
LINE_HEIGHT = 12.7
PADDING = 16
ROW_DELAY = 0.065
ROW_DURATION = 0.30


def parse_crop(value: str) -> tuple[int, int, int, int]:
    parts = tuple(int(part.strip()) for part in value.split(","))
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("crop must be left,top,right,bottom")
    return parts


def prepare_photo(
    source: Path,
    crop: tuple[int, int, int, int] | None,
) -> tuple[Image.Image, Image.Image]:
    image = Image.open(source).convert("RGB")
    if crop:
        image = image.crop(crop)
    color = ImageEnhance.Color(image).enhance(1.16)
    color = ImageEnhance.Contrast(color).enhance(1.08)

    gray = ImageOps.grayscale(color)
    gray = ImageOps.autocontrast(gray, cutoff=1)
    gray = gray.filter(ImageFilter.GaussianBlur(0.45))
    gray = ImageEnhance.Contrast(gray).enhance(1.55)
    gray = ImageEnhance.Sharpness(gray).enhance(1.35)
    gray = ImageEnhance.Brightness(gray).enhance(1.04)

    # Darken mid-tones so eyes, facial contours and fine background details
    # survive the heavy downscale into character cells.
    gray = gray.point(lambda value: int(255 * (value / 255) ** 1.28))
    return color, gray


def display_color(pixel: tuple[int, int, int]) -> str:
    """Lift dark source colors so every glyph remains visible on GitHub."""
    red, green, blue = (min(255, round(38 + channel * 0.85)) for channel in pixel)
    return f"#{red:02x}{green:02x}{blue:02x}"


def to_ascii(
    images: tuple[Image.Image, Image.Image],
    cols: int,
) -> list[list[tuple[str, str]]]:
    color, gray = images
    rows = max(1, round(cols * gray.height / gray.width * ROW_RATIO))
    color = color.resize((cols, rows), Image.Resampling.LANCZOS)
    gray = gray.resize((cols, rows), Image.Resampling.LANCZOS)
    colors = list(color.get_flattened_data())
    values = list(gray.get_flattened_data())
    last = len(RAMP) - 1
    lines: list[list[tuple[str, str]]] = []
    for row in range(rows):
        line = [
            (
                RAMP[
                    min(
                        last,
                        round((255 - values[row * cols + col]) / 255 * last),
                    )
                ],
                display_color(colors[row * cols + col]),
            )
            for col in range(cols)
        ]
        lines.append(line)
    return lines


def build_svg(lines: list[list[tuple[str, str]]], cols: int) -> str:
    width = round(cols * CHAR_WIDTH + PADDING * 2)
    height = round(len(lines) * LINE_HEIGHT + PADDING * 2)
    ramp_font = font_face("jbmono-ramp.woff2", 400)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}" '
        f'font-family="{FONT_FAMILY}" role="img" aria-labelledby="title desc">',
        '<title id="title">Crakkadmr ASCII portrait</title>',
        '<desc id="desc">A full-scene, self-typing, color ASCII portrait '
        "generated from Crakkadmr's profile photo.</desc>",
        f"<style>{ramp_font}.portrait{{fill:#d6b483}}"
        ".cursor{fill:#0f766e}"
        "@media(prefers-color-scheme:dark){.cursor{fill:#5eead4}}</style>",
        f'<rect width="{width}" height="{height}" rx="12" fill="#0b111a"/>',
    ]

    for index, line in enumerate(lines):
        y = PADDING + index * LINE_HEIGHT
        begin = index * ROW_DELAY
        line_width = cols * CHAR_WIDTH
        clip_id = f"row-{index}"
        parts.append(
            f'<clipPath id="{clip_id}"><rect x="{PADDING}" y="{y:.1f}" '
            f'width="0" height="{LINE_HEIGHT:.1f}">'
            f'<animate attributeName="width" from="0" to="{line_width:.1f}" '
            f'begin="{begin:.2f}s" dur="{ROW_DURATION:.2f}s" fill="freeze"/>'
            "</rect></clipPath>"
        )
        parts.append(
            f'<text xml:space="preserve" x="{PADDING}" '
            f'y="{y + FONT_SIZE - 0.8:.1f}" font-size="{FONT_SIZE}" '
            f'class="portrait" clip-path="url(#{clip_id})">'
            + "".join(
                f'<tspan fill="{color}">{escape(character)}</tspan>'
                for character, color in line
            )
            + "</text>"
        )
        parts.append(
            f'<rect y="{y + 1:.1f}" width="3.5" height="{FONT_SIZE:.1f}" '
            'class="cursor" opacity="0">'
            f'<animate attributeName="x" from="{PADDING}" '
            f'to="{PADDING + line_width:.1f}" begin="{begin:.2f}s" '
            f'dur="{ROW_DURATION:.2f}s" fill="freeze"/>'
            f'<set attributeName="opacity" to="0.85" begin="{begin:.2f}s"/>'
            f'<set attributeName="opacity" to="0" '
            f'begin="{begin + ROW_DURATION:.2f}s"/></rect>'
        )

    parts.append("</svg>")
    return "".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--source",
        type=Path,
        default=ROOT / "assets" / "portrait-source.jpg",
    )
    parser.add_argument("--output", type=Path, default=ASSET_DIR / "portrait.svg")
    parser.add_argument(
        "--crop",
        type=parse_crop,
        help="optional left,top,right,bottom crop; omitted means the full photo",
    )
    parser.add_argument("--cols", type=int, default=COLS)
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args()

    lines = to_ascii(prepare_photo(args.source, args.crop), args.cols)
    if args.preview:
        print("\n".join("".join(character for character, _ in line) for line in lines))
    changed = write_if_changed(args.output, build_svg(lines, args.cols))
    state = "updated" if changed else "unchanged"
    print(f"{state}: {args.output} ({len(lines)} rows, {args.cols} columns)")


if __name__ == "__main__":
    main()
