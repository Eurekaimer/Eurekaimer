#!/usr/bin/env python3
"""Replace github-profile-3d-contrib's gray "other" slice with named languages."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

SVG_NS = "http://www.w3.org/2000/svg"
GRAPHQL_URL = "https://api.github.com/graphql"
FALLBACK_COLORS = (
    "#0969da",
    "#8250df",
    "#1f883d",
    "#bf8700",
    "#cf222e",
    "#0550ae",
    "#953800",
    "#116329",
)

ET.register_namespace("", SVG_NS)


def svg_tag(name: str) -> str:
    return f"{{{SVG_NS}}}{name}"


def add(parent: ET.Element, name: str, **attributes: object) -> ET.Element:
    return ET.SubElement(
        parent,
        svg_tag(name),
        {key.replace("_", "-"): str(value) for key, value in attributes.items()},
    )


def fallback_color(language: str) -> str:
    digest = hashlib.sha256(language.encode("utf-8")).digest()
    return FALLBACK_COLORS[digest[0] % len(FALLBACK_COLORS)]


def fetch_languages(token: str, username: str) -> list[dict[str, Any]]:
    query = """
        query($login: String!) {
          user(login: $login) {
            contributionsCollection {
              commitContributionsByRepository(maxRepositories: 100) {
                repository {
                  primaryLanguage {
                    name
                    color
                  }
                }
                contributions {
                  totalCount
                }
              }
            }
          }
        }
    """
    request = Request(
        GRAPHQL_URL,
        data=json.dumps({"query": query, "variables": {"login": username}}).encode(),
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "Eurekaimer-profile-language-pie",
        },
        method="POST",
    )
    with urlopen(request, timeout=30) as response:
        payload = json.load(response)
    if payload.get("errors"):
        raise RuntimeError(payload["errors"][0]["message"])

    repositories = payload["data"]["user"]["contributionsCollection"][
        "commitContributionsByRepository"
    ]
    contributions_by_language: dict[str, dict[str, Any]] = {}
    for repository in repositories:
        primary_language = repository["repository"]["primaryLanguage"]
        if not primary_language:
            continue
        language = primary_language["name"]
        contributions = repository["contributions"]["totalCount"]
        if language in contributions_by_language:
            contributions_by_language[language]["contributions"] += contributions
        else:
            contributions_by_language[language] = {
                "language": language,
                "color": primary_language["color"] or fallback_color(language),
                "contributions": contributions,
            }

    return sorted(
        contributions_by_language.values(),
        key=lambda language: (-language["contributions"], language["language"]),
    )


def format_number(number: float) -> str:
    return f"{number:.3f}".rstrip("0").rstrip(".")


def polar(radius: float, angle: float) -> tuple[float, float]:
    return radius * math.sin(angle), -radius * math.cos(angle)


def donut_path(start: float, end: float, outer: float = 117, inner: float = 65) -> str:
    span = end - start
    outer_start = polar(outer, start)
    inner_start = polar(inner, start)
    if math.isclose(span, math.tau):
        outer_middle = polar(outer, start + math.pi)
        inner_middle = polar(inner, start + math.pi)
        return (
            f"M{format_number(outer_start[0])},{format_number(outer_start[1])}"
            f"A{outer},{outer},0,1,1,{format_number(outer_middle[0])},"
            f"{format_number(outer_middle[1])}"
            f"A{outer},{outer},0,1,1,{format_number(outer_start[0])},"
            f"{format_number(outer_start[1])}"
            f"L{format_number(inner_start[0])},{format_number(inner_start[1])}"
            f"A{inner},{inner},0,1,0,{format_number(inner_middle[0])},"
            f"{format_number(inner_middle[1])}"
            f"A{inner},{inner},0,1,0,{format_number(inner_start[0])},"
            f"{format_number(inner_start[1])}Z"
        )

    outer_end = polar(outer, end)
    inner_end = polar(inner, end)
    large_arc = 1 if span > math.pi else 0
    return (
        f"M{format_number(outer_start[0])},{format_number(outer_start[1])}"
        f"A{outer},{outer},0,{large_arc},1,{format_number(outer_end[0])},"
        f"{format_number(outer_end[1])}"
        f"L{format_number(inner_end[0])},{format_number(inner_end[1])}"
        f"A{inner},{inner},0,{large_arc},0,{format_number(inner_start[0])},"
        f"{format_number(inner_start[1])}Z"
    )


def animation_values(index: int, language_count: int, steps: int = 5) -> str:
    return ";".join(
        str(0 if frame < index else min((frame - index) / steps, 1))
        for frame in range(language_count + steps)
    )


def rebuild_language_pie(svg_path: Path, languages: list[dict[str, Any]]) -> None:
    if not languages:
        raise RuntimeError("No identifiable repository languages were returned by GitHub")

    tree = ET.parse(svg_path)
    root = tree.getroot()
    chart = next(
        (
            group
            for group in root.iter(svg_tag("g"))
            if group.get("transform", "").replace(" ", "") == "translate(40,520)"
        ),
        None,
    )
    if chart is None:
        raise RuntimeError(f"Language pie chart not found in {svg_path}")
    chart[:] = []

    height = 260
    row_count = max(8, len(languages))
    font_size = height / row_count / 1.5
    offset = (row_count - len(languages)) / 2 + 0.5
    label_group = add(chart, "g", transform="translate(273, 0)")

    for index, language in enumerate(languages):
        opacity = animation_values(index, len(languages))
        marker = add(
            label_group,
            "rect",
            x=0,
            y=(index + offset) * (height / row_count) - font_size / 2,
            width=font_size,
            height=font_size,
            fill=language["color"],
            **{"class": "stroke-bg", "stroke-width": "1px"},
        )
        add(
            marker,
            "animate",
            attributeName="fill-opacity",
            values=opacity,
            dur="3s",
            repeatCount=1,
        )
        label = add(
            label_group,
            "text",
            x=font_size * 1.2,
            y=(index + offset) * (height / row_count),
            **{
                "dominant-baseline": "middle",
                "class": "fill-fg",
                "font-size": f"{font_size}px",
            },
        )
        label.text = language["language"]
        add(
            label,
            "animate",
            attributeName="fill-opacity",
            values=opacity,
            dur="3s",
            repeatCount=1,
        )

    pie_group = add(chart, "g", transform="translate(130, 130)")
    total = sum(language["contributions"] for language in languages)
    angle = 0.0
    for index, language in enumerate(languages):
        end = angle + math.tau * language["contributions"] / total
        path = add(
            pie_group,
            "path",
            d=donut_path(angle, end),
            style=f"fill: {language['color']};",
            **{"class": "stroke-bg", "stroke-width": "2px"},
        )
        title = add(path, "title")
        title.text = f"{language['language']} {language['contributions']}"
        add(
            path,
            "animate",
            attributeName="fill-opacity",
            values=animation_values(index, len(languages)),
            dur="3s",
            repeatCount=1,
        )
        angle = end

    tree.write(svg_path, encoding="unicode", xml_declaration=False)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile-dir", type=Path, default=Path("profile-3d-contrib"))
    parser.add_argument("--languages-json", type=Path)
    args = parser.parse_args()

    if args.languages_json:
        languages = json.loads(args.languages_json.read_text(encoding="utf-8"))
    else:
        token = os.environ.get("GITHUB_TOKEN")
        username = os.environ.get("USERNAME")
        if not token or not username:
            raise RuntimeError("GITHUB_TOKEN and USERNAME are required")
        languages = fetch_languages(token, username)

    svg_paths = sorted(args.profile_dir.glob("*.svg"))
    if not svg_paths:
        raise RuntimeError(f"No SVG files found under {args.profile_dir}")
    for svg_path in svg_paths:
        rebuild_language_pie(svg_path, languages)
        print(f"expanded language pie chart: {svg_path}")


if __name__ == "__main__":
    main()
