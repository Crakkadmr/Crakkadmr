#!/usr/bin/env python3
"""Generate the animated ASCII backend control plane used by the profile."""

from __future__ import annotations

from svg_theme import ASSET_DIR, FONT_FAMILY, escape, font_face, write_if_changed

COLS = 102
FONT_SIZE = 12.4
CHAR_WIDTH = FONT_SIZE * 0.60
LINE_HEIGHT = 18.2
PADDING_X = 18
PADDING_Y = 18


def border() -> str:
    return "+" + "-" * (COLS - 2) + "+"


def row(content: str = "") -> str:
    if len(content) > COLS - 2:
        raise ValueError(f"ASCII row is too wide ({len(content)} > {COLS - 2})")
    return "|" + content.ljust(COLS - 2) + "|"


LINES = (
    border(),
    row(" CRAKKADMR::BACKEND_CONTROL_PLANE                                  STATUS [ ONLINE ]"),
    border(),
    row(),
    row("  REQUESTS              GATEWAY                  SERVICE MESH                    DATA PLANE"),
    row(),
    row("   o  o  o  ----->  +---------------+      +-------------------------+      +------------------+"),
    row("   o  o  o          | AUTH / LIMIT  |----->| API   CORE   WORKERS    |----->| POSTGRES / CACHE |"),
    row("   o  o  o  ----->  | LOG  / TRACE  |      | JOBS  NET    AUTOMATION |      | QUEUE / STORAGE  |"),
    row("                    +-------+-------+      +------------+------------+      +---------+--------+"),
    row("                            |                           |                             |"),
    row("                            +------------ OBSERVABILITY ----------------------------+"),
    row(),
    row("  FLOW   request > validate > execute > persist > observe > deliver"),
    row("  BUILD  [####################] PASS      NETWORK [####################] STABLE"),
    row(),
    row("  .NET / C#   ASP.NET CORE   POSTGRESQL   DOCKER   GITHUB ACTIONS   PLAYWRIGHT"),
    border(),
    row(" > engineering reliable systems_"),
    border(),
)

BRIGHT_ROWS = {0, 1, 2, 4, 17, 18, 19}
DIM_ROWS = {3, 5, 12, 15}


def build_svg() -> str:
    width = round(COLS * CHAR_WIDTH + PADDING_X * 2)
    height = round(len(LINES) * LINE_HEIGHT + PADDING_Y * 2)
    fonts = font_face("jbmono-400.woff2", 400) + font_face(
        "jbmono-600.woff2",
        600,
    )
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}" '
        f'font-family="{FONT_FAMILY}" role="img" aria-labelledby="title desc">',
        '<title id="title">Crakkadmr animated ASCII backend control plane</title>',
        '<desc id="desc">An animated monochrome terminal diagram showing requests, '
        "gateway, services, observability, data stores and delivery status.</desc>",
        f"<style>{fonts}"
        ".surface{fill:#0d1117}.frame{fill:none;stroke:#30363d}"
        ".text{fill:#8b949e}.bright{fill:#f0f6fc}.dim{fill:#484f58}"
        ".packet{fill:#f0f6fc}.scan{fill:#f0f6fc}"
        "</style>",
        f'<rect class="surface" width="{width}" height="{height}" rx="14"/>',
        f'<rect class="frame" x="0.5" y="0.5" width="{width - 1}" '
        f'height="{height - 1}" rx="13.5"/>',
        '<rect class="scan" x="1" y="1" width="100%" height="1" opacity="0">'
        '<animate attributeName="y" from="1" '
        f'to="{height - 2}" begin="1.8s" dur="4.5s" repeatCount="indefinite"/>'
        '<animate attributeName="opacity" values="0;0.12;0" '
        'begin="1.8s" dur="4.5s" repeatCount="indefinite"/></rect>',
    ]

    for index, line in enumerate(LINES):
        y = PADDING_Y + index * LINE_HEIGHT + FONT_SIZE
        css_class = (
            "bright"
            if index in BRIGHT_ROWS
            else "dim"
            if index in DIM_ROWS
            else "text"
        )
        weight = 600 if index in BRIGHT_ROWS else 400
        begin = 0.08 + index * 0.055
        parts.append(
            f'<text xml:space="preserve" x="{PADDING_X}" y="{y:.1f}" '
            f'font-size="{FONT_SIZE}" font-weight="{weight}" '
            f'class="{css_class}" opacity="0">{escape(line)}'
            '<animate attributeName="opacity" from="0" to="1" '
            f'begin="{begin:.2f}s" dur="0.22s" fill="freeze"/></text>'
        )

    flow_start = PADDING_X + 19 * CHAR_WIDTH
    flow_end = PADDING_X + 88 * CHAR_WIDTH
    for number, row_index in enumerate((6, 7, 8)):
        y = PADDING_Y + row_index * LINE_HEIGHT + FONT_SIZE
        parts.append(
            f'<text x="{flow_start:.1f}" y="{y:.1f}" '
            f'font-size="{FONT_SIZE}" font-weight="600" class="packet">&gt;'
            f'<animate attributeName="x" from="{flow_start:.1f}" '
            f'to="{flow_end:.1f}" begin="{1.4 + number * 0.55:.2f}s" '
            'dur="3.2s" repeatCount="indefinite"/>'
            '<animate attributeName="opacity" values="0;1;1;0" '
            f'begin="{1.4 + number * 0.55:.2f}s" dur="3.2s" '
            'repeatCount="indefinite"/></text>'
        )

    status_x = PADDING_X + 91 * CHAR_WIDTH
    status_y = PADDING_Y + LINE_HEIGHT + FONT_SIZE
    parts.append(
        f'<text x="{status_x:.1f}" y="{status_y:.1f}" '
        f'font-size="{FONT_SIZE}" class="bright">*</text>'
        '<animate attributeName="opacity" values="1;0.25;1" '
        'begin="1.2s" dur="1.5s" repeatCount="indefinite"/>'
    )

    cursor_x = PADDING_X + 32 * CHAR_WIDTH
    cursor_y = PADDING_Y + 18 * LINE_HEIGHT + 2
    parts.append(
        f'<rect x="{cursor_x:.1f}" y="{cursor_y:.1f}" width="{CHAR_WIDTH:.1f}" '
        f'height="{FONT_SIZE + 2:.1f}" class="bright">'
        '<animate attributeName="opacity" values="1;0;1" '
        'begin="1.4s" dur="1s" repeatCount="indefinite"/></rect>'
    )

    parts.append("</svg>")
    return "".join(parts)


def main() -> None:
    output = ASSET_DIR / "ascii-backend-system.svg"
    changed = write_if_changed(output, build_svg())
    state = "updated" if changed else "unchanged"
    print(f"{state}: {output} ({len(LINES)} rows, {COLS} columns)")


if __name__ == "__main__":
    main()
