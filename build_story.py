#!/usr/bin/env python3
"""Build story.json from parsed sections, repair links, and add ASCII art."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


PARSED_PATH = Path("parsed_sections.json")
STORY_PATH = Path("story.json")
REPORT_PATH = Path("link_report.txt")

CHOICE_SENTENCE_RE = re.compile(
    r"[^.!?]*\b(?:turn to|go to|proceed to)\s+[1-9]\d{0,2}[^.!?]*[.!?]?",
    re.IGNORECASE,
)
CHOICE_PHRASE_RE = re.compile(r"\b(?:turn to|go to|proceed to)\s+[1-9]\d{0,2}\b", re.IGNORECASE)
PAGE_ARTIFACT_RE = re.compile(r"^\s*-?\s*\d+\s*-?\s*$")


def normalize_line(text: str) -> str:
    text = text.replace("\u00ad", "")
    text = text.replace("—", "-")
    return text.strip()


def clean_body(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    paragraphs = re.split(r"\n{2,}", text)
    kept: list[str] = []
    for para in paragraphs:
        lines = [normalize_line(line) for line in para.split("\n")]
        lines = [line for line in lines if line and not PAGE_ARTIFACT_RE.fullmatch(line)]
        if not lines:
            continue
        merged = " ".join(lines)
        merged = CHOICE_SENTENCE_RE.sub(" ", merged)
        merged = CHOICE_PHRASE_RE.sub("", merged)
        merged = re.sub(r"\s+", " ", merged).strip(" ,;:-")
        merged = re.sub(r"\s+([,.!?;:])", r"\1", merged)
        if merged:
            kept.append(merged)
    return "\n\n".join(kept).strip()


def pick_scene_kind(text: str) -> str:
    lower = text.lower()
    if any(k in lower for k in ("forest", "woods", "tree", "grove")):
        return "forest"
    if any(k in lower for k in ("cave", "tunnel", "cavern", "underground")):
        return "cave"
    if any(
        k in lower
        for k in (
            "house",
            "building",
            "room",
            "hall",
            "tower",
            "castle",
            "temple",
            "inn",
        )
    ):
        return "building"
    if any(k in lower for k in ("river", "lake", "ocean", "sea", "water", "stream")):
        return "water"
    if any(k in lower for k in ("field", "plain", "meadow", "grassland", "open land")):
        return "field"
    return "default"


def fit_row(row: str) -> str:
    row = row[:40]
    if len(row) < 40:
        row = row + (" " * (40 - len(row)))
    return row


def centered(text: str, width: int = 38) -> str:
    t = text[:width]
    if len(t) < width:
        left = (width - len(t)) // 2
        right = width - len(t) - left
        return (" " * left) + t + (" " * right)
    return t


def generate_ascii_art(text: str, title: str) -> list[str]:
    kind = pick_scene_kind(text)

    if kind == "forest":
        rows = [
            "┌──────────────────────────────────────┐",
            "│ ▲   ▲    ▲   ▲▲   ▲    ▲   ▲▲   ▲   │",
            "│ │   │    │   ││   │    │   ││   │   │",
            "│ │ ▲ │ ▲  │ ▲ ││ ▲ │ ▲  │ ▲ ││ ▲ │   │",
            "│ │ │ │ │  │ │ ││ │ │ │  │ │ ││ │ │   │",
            "│ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   │",
            "│     ●  A winding forest trail  ●     │",
            "│ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   │",
            "│   ▲▲       ▲▲       ▲▲       ▲▲      │",
            "└──────────────────────────────────────┘",
        ]
    elif kind == "cave":
        rows = [
            "┌──────────────────────────────────────┐",
            "│▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓│",
            "│▓░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░▓│",
            "│▓░  █▄   █▄    ▓    ▄█   ▄█   ░░░░░░▓│",
            "│▓░ ▄██▄ ▄██▄   ▓   ▄██▄ ▄██▄  ░░░░░░▓│",
            "│▓░░░░░░░░░░░  ●  ░░░░░░░░░░░░░░░░░░▓│",
            "│▓░░░░░░░ Dark cavern passage ░░░░░░░▓│",
            "│▓░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░▓│",
            "│▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓│",
            "└──────────────────────────────────────┘",
        ]
    elif kind == "building":
        rows = [
            "┌──────────────────────────────────────┐",
            "│┌───────────┐      ┌───────────┐      │",
            "││ █ █ █ █ █ │      │ █ █ █ █ █ │      │",
            "││           │      │           │      │",
            "│├──────┬────┤  ●   ├──────┬────┤      │",
            "││      │    │      │      │    │      │",
            "││      │    │      │      │    │      │",
            "│└──────┴────┘      └──────┴────┘      │",
            "│        A tense interior scene         │",
            "└──────────────────────────────────────┘",
        ]
    elif kind == "water":
        rows = [
            "┌──────────────────────────────────────┐",
            "│≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈│",
            "│~~~~~~≈~~~~~~≈~~~~~~≈~~~~~~≈~~~~~~≈~~│",
            "│≈~~~~~≈~~~~~~≈~~~~~~≈~~~~~~≈~~~~~~≈~~│",
            "│~~~~~~≈~~~  ● drifting onward ~~~~≈~~~│",
            "│≈~~~~~≈~~~~~~≈~~~~~~≈~~~~~~≈~~~~~~≈~~│",
            "│~~~~~~≈~~~~~~≈~~~~~~≈~~~~~~≈~~~~~~≈~~│",
            "│≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈│",
            "│         Water stretches ahead         │",
            "└──────────────────────────────────────┘",
        ]
    elif kind == "field":
        rows = [
            "┌──────────────────────────────────────┐",
            "│──────────────────────────────────────│",
            "│░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░│",
            "│──────────────────────────────────────│",
            "│░░░░░░░░░░░░░░░░●░░░░░░░░░░░░░░░░░░░│",
            "│──────────────────────────────────────│",
            "│░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░│",
            "│──────────────────────────────────────│",
            "│        Wide open land and sky         │",
            "└──────────────────────────────────────┘",
        ]
    else:
        scene = centered(title.upper()[:24], 38)
        rows = [
            "┌──────────────────────────────────────┐",
            "│                                      │",
            "│                                      │",
            "│                                      │",
            f"│{scene}│",
            "│                                      │",
            "│                                      │",
            "│                                      │",
            "│                 ●                    │",
            "└──────────────────────────────────────┘",
        ]
    return [fit_row(r) for r in rows[:10]]


def infer_title(text: str) -> str:
    lower = text.lower()
    if any(k in lower for k in ("forest", "woods", "tree", "grove")):
        return "Shadows In The Forest"
    if any(k in lower for k in ("cave", "tunnel", "cavern", "underground")):
        return "Into The Dark Cave"
    if any(k in lower for k in ("house", "building", "room", "hall", "tower", "castle", "temple")):
        return "Inside The Silent Halls"
    if any(k in lower for k in ("river", "lake", "ocean", "sea", "water", "stream")):
        return "Across The Restless Water"
    if any(k in lower for k in ("field", "plain", "meadow", "grassland")):
        return "Across The Open Field"
    words = re.findall(r"[A-Za-z']{3,}", text)
    picked = [w.capitalize() for w in words[:6]]
    if len(picked) >= 3:
        return " ".join(picked[: min(6, max(3, len(picked)))])
    return "A Strange New Path"


def choice_sort_key(x: int, target: int) -> tuple[int, int]:
    return (abs(x - target), x)


def fix_broken_links(sections: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    by_num: dict[int, dict[str, Any]] = {s["section_number"]: s for s in sections}
    existing = set(by_num)
    report: list[str] = []

    for section in sections:
        for choice in section.get("choices", []):
            dest = int(choice["destination"])
            if dest in existing:
                continue
            near = [n for n in existing if abs(n - dest) <= 2]
            if near:
                new_dest = sorted(near, key=lambda n: choice_sort_key(n, dest))[0]
                choice["destination"] = new_dest
                report.append(
                    f"Remapped missing destination {dest} -> {new_dest} "
                    f"(source section {section['section_number']})"
                )
            else:
                by_num[dest] = {
                    "section_number": dest,
                    "text": f"[Section {dest} - not found in source]",
                    "choices": [],
                    "node_type": "ending_neutral",
                }
                existing.add(dest)
                report.append(f"Created stub section {dest} (referenced by section {section['section_number']})")

    full_sections = [by_num[n] for n in sorted(by_num)]
    return full_sections, report


def build_story_nodes(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    for section in sorted(sections, key=lambda s: s["section_number"]):
        n = int(section["section_number"])
        cleaned = clean_body(section.get("text", ""))
        title = infer_title(cleaned or section.get("text", ""))
        choices_out = []
        for c in section.get("choices", [])[:4]:
            label = " ".join(c.get("text", "").split())
            if not label:
                label = f"Go to section {c['destination']}"
            label = label[:60]
            choices_out.append(
                {
                    "text": label,
                    "next": f"section_{int(c['destination'])}",
                    "requires": {},
                    "effects": {},
                }
            )

        node_type = section.get("node_type", "normal")
        if choices_out:
            node_type = "normal"
        elif node_type not in {"ending_win", "ending_death", "ending_neutral"}:
            node_type = "ending_neutral"

        body_text = cleaned or section.get("text", "").strip() or f"[Section {n} - not found in source]"
        node = {
            "id": f"section_{n}",
            "section_number": n,
            "title": title,
            "text": body_text,
            "ascii_art": generate_ascii_art(body_text, title),
            "node_type": node_type,
            "choices": choices_out,
            "effects": {},
            "random_event_pool": [],
        }
        nodes.append(node)

    return nodes


def main() -> None:
    if not PARSED_PATH.exists():
        raise FileNotFoundError(f"Missing parsed file: {PARSED_PATH}")

    sections: list[dict[str, Any]] = json.loads(PARSED_PATH.read_text(encoding="utf-8"))
    fixed_sections, report_lines = fix_broken_links(sections)
    nodes = build_story_nodes(fixed_sections)

    # Ensure entry point is section 1 if available, otherwise lowest number.
    nodes.sort(key=lambda n: n["section_number"])
    if any(n["section_number"] == 1 for n in nodes):
        nodes.sort(key=lambda n: (n["section_number"] != 1, n["section_number"]))

    STORY_PATH.write_text(json.dumps(nodes, indent=2, ensure_ascii=False), encoding="utf-8")
    if report_lines:
        REPORT_PATH.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    else:
        REPORT_PATH.write_text("No broken links found.\n", encoding="utf-8")

    print(f"Wrote {STORY_PATH} with {len(nodes)} nodes")
    print(f"Wrote {REPORT_PATH} with {len(report_lines)} link changes")


if __name__ == "__main__":
    main()
