#!/usr/bin/env python3
"""Generate a self-typing ASCII portrait from the profile's source photo.

This is intentionally a one-off generator. The scheduled workflow refreshes
GitHub statistics, while the portrait changes only when its source photo does.

Usage:
    python scripts/generate_portrait.py
    python scripts/generate_portrait.py --crop 145,75,380,285 --preview
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

from svg_theme import ASSET_DIR, FONT_FAMILY, ROOT, escape, font_face, write_if_changed

RAMP = " .`:-=+*cs#%@"
DEFAULT_CROP = (145, 75, 380, 285)
COLS = 78
ROW_RATIO = 0.49
FONT_SIZE = 12.5
CHAR_WIDTH = FONT_SIZE * 0.6
LINE_HEIGHT = 14.5
PADDING = 18
ROW_DELAY = 0.075
ROW_DURATION = 0.30


def parse_crop(value: str) -> tuple[int, int, int, int]:
    parts = tuple(int(part.strip()) for part in value.split(","))
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("crop must be left,top,right,bottom")
    return parts


def prepare_photo(source: Path, crop: tuple[int, int, int, int]) -> Image.Image:
    image = Image.open(source).convert("RGB").crop(crop)
    gray = ImageOps.grayscale(image)
    gray = ImageOps.autocontrast(gray, cutoff=1)
    gray = gray.filter(ImageFilter.GaussianBlur(0.45))
    gray = ImageEnhance.Contrast(gray).enhance(1.65)
    gray = ImageEnhance.Sharpness(gray).enhance(1.35)

    # A soft oval keeps attention on the cat's face and headphones while
    # mapping the patterned wall and couch to the blank end of the ramp.
    mask = Image.new("L", gray.size, 0)
    inset_x = max(3, int(gray.width * 0.035))
    inset_y = max(3, int(gray.height * 0.015))
    ImageDraw.Draw(mask).ellipse(
        (inset_x, inset_y, gray.width - inset_x, gray.height - inset_y),
        fill=255,
    )
    mask = mask.filter(ImageFilter.GaussianBlur(max(7, int(gray.width * 0.055))))
    gray = Image.composite(gray, Image.new("L", gray.size, 255), mask)

    # Darken mid-tones so whiskers, eyes and the headphone band survive the
    # heavy downscale into character cells.
    return gray.point(lambda value: int(255 * (value / 255) ** 1.38))


def to_ascii(image: Image.Image, cols: int) -> list[str]:
    rows = max(1, round(cols * image.height / image.width * ROW_RATIO))
    image = image.resize((cols, rows), Image.Resampling.LANCZOS)
    values = list(image.get_flattened_data())
    last = len(RAMP) - 1
    lines: list[str] = []
    for row in range(rows):
        line = "".join(
            RAMP[min(last, round((255 - values[row * cols + col]) / 255 * last))]
            for col in range(cols)
        ).rstrip()
        lines.append(line)

    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def build_svg(lines: list[str], cols: int) -> str:
    width = round(cols * CHAR_WIDTH + PADDING * 2)
    height = round(len(lines) * LINE_HEIGHT + PADDING * 2)
    ramp_font = font_face("jbmono-ramp.woff2", 400)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}" '
        f'font-family="{FONT_FAMILY}" role="img" aria-labelledby="title desc">',
        '<title id="title">Crakkadmr ASCII cat portrait</title>',
        '<desc id="desc">A self-typing ASCII portrait of a cat wearing headphones '
        "and sitting at a laptop.</desc>",
        f"<style>{ramp_font}.portrait{{fill:#72512f}}"
        ".cursor{fill:#0f766e}"
        "@media(prefers-color-scheme:dark){.portrait{fill:#d6b483}"
        ".cursor{fill:#5eead4}}</style>",
    ]

    for index, line in enumerate(lines):
        y = PADDING + index * LINE_HEIGHT
        begin = index * ROW_DELAY
        line_width = max(1, len(line)) * CHAR_WIDTH
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
            f'class="portrait" clip-path="url(#{clip_id})">{escape(line)}</text>'
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
    parser.add_argument("--crop", type=parse_crop, default=DEFAULT_CROP)
    parser.add_argument("--cols", type=int, default=COLS)
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args()

    lines = to_ascii(prepare_photo(args.source, args.crop), args.cols)
    if args.preview:
        print("\n".join(lines))
    changed = write_if_changed(args.output, build_svg(lines, args.cols))
    state = "updated" if changed else "unchanged"
    print(f"{state}: {args.output} ({len(lines)} rows, {args.cols} columns)")


if __name__ == "__main__":
    main()
