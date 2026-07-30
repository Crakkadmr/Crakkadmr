#!/usr/bin/env python3
"""Draw profile statistics from GitHub's GraphQL API.

The script uses only Python's standard library. It produces deterministic SVGs
inside this repository and never calls a third-party badge or statistics
service.

Environment:
    GITHUB_TOKEN  GitHub Actions' built-in token
    GH_LOGIN      profile owner (defaults to Crakkadmr)
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone

from svg_theme import ASSET_DIR, WIDTH, escape, fade, svg_open, text, write_if_changed

API_URL = "https://api.github.com/graphql"
LOGIN = os.environ.get("GH_LOGIN", "Crakkadmr")

QUERY = """
query ProfileData($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            contributionCount
            date
            weekday
          }
        }
      }
    }
    repositories(
      first: 100
      ownerAffiliations: OWNER
      isFork: false
      privacy: PUBLIC
    ) {
      nodes {
        name
        languages(first: 12, orderBy: {field: SIZE, direction: DESC}) {
          edges {
            size
            node { name }
          }
        }
      }
    }
  }
}
"""

MONTHS = ("jan", "feb", "mar", "apr", "may", "jun",
          "jul", "aug", "sep", "oct", "nov", "dec")
RAMP = (" ", ".", ":", "+", "#", "@")


def utc_window() -> tuple[str, str]:
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=364)
    return (
        f"{start.isoformat()}T00:00:00Z",
        f"{today.isoformat()}T23:59:59Z",
    )


def fetch_profile(token: str) -> dict:
    start, end = utc_window()
    body = json.dumps(
        {
            "query": QUERY,
            "variables": {"login": LOGIN, "from": start, "to": end},
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": f"{LOGIN}-self-generated-profile",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"GitHub API returned {exc.code}: {detail}") from exc
    if payload.get("errors"):
        raise SystemExit(f"GitHub GraphQL errors: {payload['errors']}")
    user = (payload.get("data") or {}).get("user")
    if user is None:
        raise SystemExit(f"GitHub user not found: {LOGIN}")
    return user


def calculate_streaks(days: list[dict]) -> tuple[dict, dict]:
    longest = {"length": 0, "start": None, "end": None}
    length = 0
    start = None
    for day in days:
        if day["contributionCount"] > 0:
            length += 1
            start = start or day["date"]
            if length > longest["length"]:
                longest = {"length": length, "start": start, "end": day["date"]}
        else:
            length = 0
            start = None

    # Today is not over yet. An empty current day should not erase yesterday's
    # still-live streak.
    tail = days[:-1] if days and days[-1]["contributionCount"] == 0 else days
    current = {"length": 0, "start": None, "end": None}
    for day in reversed(tail):
        if day["contributionCount"] == 0:
            break
        current["length"] += 1
        current["start"] = day["date"]
        current["end"] = current["end"] or day["date"]
    return current, longest


def language_totals(repositories: list[dict]) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
    by_bytes: dict[str, int] = {}
    by_repository: dict[str, int] = {}
    for repository in repositories:
        edges = (repository.get("languages") or {}).get("edges") or []
        for edge in edges:
            name = edge["node"]["name"]
            by_bytes[name] = by_bytes.get(name, 0) + edge["size"]
        if edges:
            primary = max(edges, key=lambda edge: edge["size"])["node"]["name"]
            by_repository[primary] = by_repository.get(primary, 0) + 1

    def ranked(values: dict[str, int]) -> list[tuple[str, int]]:
        return sorted(values.items(), key=lambda item: (-item[1], item[0]))[:5]

    return ranked(by_bytes), ranked(by_repository)


def summarise(user: dict) -> dict:
    calendar = user["contributionsCollection"]["contributionCalendar"]
    weeks = [week["contributionDays"] for week in calendar["weeks"]]
    days = sorted((day for week in weeks for day in week), key=lambda item: item["date"])
    weekly = [sum(day["contributionCount"] for day in week) for week in weeks]
    current, longest = calculate_streaks(days)
    by_bytes, by_repository = language_totals(user["repositories"]["nodes"])
    return {
        "total": calendar["totalContributions"],
        "active_days": sum(day["contributionCount"] > 0 for day in days),
        "best_week": max(weekly, default=0),
        "weekly": weekly,
        "weeks": weeks,
        "days": days,
        "current": current,
        "longest": longest,
        "by_bytes": by_bytes,
        "by_repository": by_repository,
    }


def line_path(points: list[tuple[float, float]]) -> str:
    if not points:
        return ""
    commands = [f"M{points[0][0]:.1f} {points[0][1]:.1f}"]
    commands.extend(f"L{x:.1f} {y:.1f}" for x, y in points[1:])
    return "".join(commands)


def draw_stats(summary: dict) -> str:
    height = 158
    chart_top = 101
    chart_bottom = 148
    weekly = summary["weekly"] or [0]
    peak = max(weekly) or 1
    step = WIDTH / max(1, len(weekly) - 1)
    points = [
        (index * step, chart_bottom - value / peak * (chart_bottom - chart_top))
        for index, value in enumerate(weekly)
    ]

    parts = [
        svg_open(
            WIDTH,
            height,
            title="Crakkadmr contribution summary",
            description="Total contributions, active days, best week and weekly activity.",
        ),
        f'<g opacity="0">{fade(0.06)}',
        text(0, 55, summary["total"], size=54, css_class="strong", weight=600),
        text(0, 78, "contributions / katki", size=12, css_class="muted"),
        "</g>",
    ]
    for index, (value, label) in enumerate(
        (
            (summary["active_days"], "active days / aktif gun"),
            (summary["best_week"], "best week / en iyi hafta"),
        )
    ):
        y = 35 + index * 43
        parts.extend(
            (
                f'<g opacity="0">{fade(0.18 + index * 0.12)}',
                text(WIDTH, y, value, size=21, css_class="strong", weight=600, anchor="end"),
                text(WIDTH, y + 18, label, size=10, css_class="muted", anchor="end"),
                "</g>",
            )
        )

    path = line_path(points)
    area = (
        f"M{points[0][0]:.1f} {chart_bottom:.1f}"
        f"{path.replace(f'M{points[0][0]:.1f} {points[0][1]:.1f}', f'L{points[0][0]:.1f} {points[0][1]:.1f}', 1)}"
        f"L{points[-1][0]:.1f} {chart_bottom:.1f}Z"
    )
    parts.extend(
        (
            '<defs><linearGradient id="activity-fill" x1="0" y1="0" x2="0" y2="1">'
            '<stop offset="0" stop-color="#0f766e" stop-opacity=".32"/>'
            '<stop offset="1" stop-color="#0f766e" stop-opacity=".02"/>'
            "</linearGradient>"
            '<clipPath id="chart-reveal"><rect x="0" y="94" width="0" height="62">'
            '<animate attributeName="width" from="0" to="620" begin=".38s" '
            'dur="1.25s" fill="freeze"/></rect></clipPath></defs>',
            '<g clip-path="url(#chart-reveal)">',
            f'<path d="{area}" fill="url(#activity-fill)"/>',
            f'<path d="{path}" fill="none" class="accent-stroke" '
            'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
            "</g>",
            f'<circle cx="{points[-1][0] - 2:.1f}" cy="{points[-1][1]:.1f}" '
            f'r="4.2" class="accent" opacity="0">{fade(1.63, 0.25)}</circle>',
            "</svg>",
        )
    )
    return "".join(parts)


def pretty_date(value: str | None) -> str:
    if not value:
        return "-"
    parsed = date.fromisoformat(value)
    return f"{MONTHS[parsed.month - 1]} {parsed.day}"


def draw_streaks(summary: dict) -> str:
    height = 108
    middle = WIDTH / 2
    parts = [
        svg_open(
            WIDTH,
            height,
            title="Crakkadmr contribution streaks",
            description="Current and longest contribution streaks.",
        ),
        f'<line x1="{middle}" y1="14" x2="{middle}" y2="94" '
        f'class="rule" stroke-width="1" opacity="0">{fade(0.12)}</line>',
    ]
    for index, (key, label) in enumerate(
        (("current", "current / guncel"), ("longest", "longest / en uzun"))
    ):
        streak = summary[key]
        x = 28 if index == 0 else middle + 28
        span = (
            f"{pretty_date(streak['start'])} - {pretty_date(streak['end'])}"
            if streak["length"]
            else "-"
        )
        parts.extend(
            (
                f'<g opacity="0">{fade(0.10 + index * 0.14)}',
                text(x, 50, streak["length"], size=39, css_class="strong", weight=600),
                text(x, 72, label, size=11, css_class="muted"),
                text(x, 91, span, size=10, css_class="ink"),
                "</g>",
            )
        )
    parts.append("</svg>")
    return "".join(parts)


def horizontal_bar(x: float, y: float, width: float, height: float = 7) -> str:
    if width <= 0:
        return ""
    radius = min(height / 2, width / 2)
    return (
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" '
        f'height="{height:.1f}" rx="{radius:.1f}" class="accent"/>'
    )


def draw_languages(summary: dict) -> str:
    rows = max(1, len(summary["by_bytes"]), len(summary["by_repository"]))
    height = 37 + rows * 27
    gap = 30
    column_width = (WIDTH - gap) / 2
    groups = (
        (0, "BY BYTES", summary["by_bytes"], True),
        (column_width + gap, "BY REPOSITORY", summary["by_repository"], False),
    )
    parts = [
        svg_open(
            WIDTH,
            height,
            title="Languages used in public repositories",
            description="Top languages measured by bytes and primary repository language.",
        )
    ]
    for group_index, (group_x, heading, values, percentages) in enumerate(groups):
        parts.extend(
            (
                f'<g opacity="0">{fade(0.08 + group_index * 0.10)}',
                text(
                    group_x,
                    13,
                    heading,
                    size=9,
                    css_class="muted",
                    weight=600,
                    letter_spacing=1.4,
                ),
                "</g>",
            )
        )
        if not values:
            continue
        maximum = max(value for _, value in values) or 1
        total = sum(value for _, value in values) or 1
        for row, (name, value) in enumerate(values):
            y = 30 + row * 27
            shown = f"{value / total * 100:.0f}%" if percentages else str(value)
            parts.extend(
                (
                    f'<g opacity="0">{fade(0.20 + row * 0.06 + group_index * 0.08)}',
                    text(group_x, y, name.lower()[:15], size=11, css_class="strong"),
                    text(
                        group_x + column_width - 2,
                        y,
                        shown,
                        size=10,
                        css_class="muted",
                        anchor="end",
                    ),
                    horizontal_bar(
                        group_x,
                        y + 8,
                        (column_width - 4) * value / maximum,
                    ),
                    "</g>",
                )
            )
    parts.append("</svg>")
    return "".join(parts)


def intensity(value: int) -> int:
    if value <= 0:
        return 0
    if value <= 1:
        return 1
    if value <= 3:
        return 2
    if value <= 6:
        return 3
    if value <= 10:
        return 4
    return 5


def draw_year(summary: dict) -> str:
    font_size = 10.1
    char_width = font_size * 0.6
    row_height = 12.2
    left = 34
    top = 48
    weeks = summary["weeks"]
    height = round(top + 7 * row_height + 28)
    parts = [
        svg_open(
            WIDTH,
            height,
            title="Crakkadmr contribution year",
            description="One character per day, with denser characters for more contributions.",
        ),
        f'<g opacity="0">{fade(0.06)}',
        text(left, 14, "THE YEAR / YIL", size=9, css_class="muted", weight=600, letter_spacing=1.3),
        text(
            left,
            33,
            f"{summary['active_days']} active days / aktif gun",
            size=11,
            css_class="ink",
        ),
        "</g>",
    ]

    for weekday in range(7):
        characters = []
        for week in weeks:
            day = next((item for item in week if item["weekday"] == weekday), None)
            characters.append(RAMP[intensity(day["contributionCount"] if day else 0)])
        line = "".join(characters).rstrip()
        y = top + weekday * row_height
        reveal_width = max(1, len(line)) * char_width
        parts.extend(
            (
                f'<clipPath id="year-{weekday}"><rect x="{left}" y="{y:.1f}" '
                f'width="0" height="{row_height:.1f}"><animate attributeName="width" '
                f'from="0" to="{reveal_width:.1f}" begin="{0.25 + weekday * 0.07:.2f}s" '
                'dur=".52s" fill="freeze"/></rect></clipPath>',
                f'<text xml:space="preserve" x="{left}" y="{y + font_size:.1f}" '
                f'font-size="{font_size}" class="accent" '
                f'clip-path="url(#year-{weekday})">{escape(line)}</text>',
            )
        )

    for weekday, label in ((1, "mon"), (3, "wed"), (5, "fri")):
        parts.append(
            text(
                left - 7,
                top + weekday * row_height + font_size,
                label,
                size=9,
                css_class="muted",
                anchor="end",
            )
        )

    last_month = None
    last_x = -100
    label_y = top + 7 * row_height + 16
    for index, week in enumerate(weeks):
        if not week:
            continue
        month = int(week[0]["date"][5:7])
        x = left + index * char_width
        if month != last_month and x - last_x >= 35:
            parts.append(text(x, label_y, MONTHS[month - 1], size=9, css_class="muted"))
            last_x = x
        last_month = month

    parts.append("</svg>")
    return "".join(parts)


def draw_heading(label: str) -> str:
    height = 28
    text_width = len(label) * 16 * 0.6
    parts = [
        svg_open(
            WIDTH,
            height,
            title=label,
            description=f"Section heading: {label}",
        ),
        text(0, 20, label, size=16, css_class="strong", weight=600),
        f'<line x1="{text_width + 20:.1f}" y1="14" x2="{WIDTH}" y2="14" '
        'class="rule" stroke-width="1"/>',
        "</svg>",
    ]
    return "".join(parts)


def main() -> None:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("GITHUB_TOKEN is not set")

    summary = summarise(fetch_profile(token))
    graphics = {
        "stats.svg": draw_stats(summary),
        "streak.svg": draw_streaks(summary),
        "languages.svg": draw_languages(summary),
        "year.svg": draw_year(summary),
    }
    headings = {
        "heading-about.svg": "hakkimda / about",
        "heading-stack.svg": "teknolojiler / stack",
        "heading-projects.svg": "projeler / projects",
        "heading-stats.svg": "istatistikler / stats",
        "heading-page.svg": "bu sayfa / this page",
    }
    graphics.update({filename: draw_heading(label) for filename, label in headings.items()})

    changed = [
        filename
        for filename, content in graphics.items()
        if write_if_changed(ASSET_DIR / filename, content)
    ]
    print(
        f"{summary['total']} contributions, {summary['active_days']} active days, "
        f"current streak {summary['current']['length']}, "
        f"longest streak {summary['longest']['length']}"
    )
    print("updated: " + (", ".join(sorted(changed)) if changed else "nothing"))


if __name__ == "__main__":
    main()
