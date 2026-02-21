#!/usr/bin/env python3
"""Parse CYOA sections from raw_text.txt into parsed_sections.json."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


RAW_PATH = Path("raw_text.txt")
PARSED_PATH = Path("parsed_sections.json")

SECTION_RE = re.compile(r"^(?:[1-9]\d{0,2}|500)$")
DIRECT_CHOICE_RE = re.compile(
    r"\b(?:turn|go(?:\s+on)?|proceed)\b[^0-9]{0,50}?([1-9]\d{0,2}|500)\b",
    re.IGNORECASE,
)
SENTENCE_TO_NUM_RE = re.compile(r"\bto\s+([1-9]\d{0,2}|500)\b[.?!;:]?\s*$", re.IGNORECASE)
ANY_NUM_RE = re.compile(r"\b([1-9]\d{0,2}|500)\b")
CHOICE_CUE_RE = re.compile(r"\b(turn|go|proceed|decide|choose|if)\b", re.IGNORECASE)
DEATH_RE = re.compile(r"\b(death|die|dies|died|killed|fail|failed)\b", re.IGNORECASE)
WIN_RE = re.compile(r"\b(win|wins|won|escape|escaped|success|triumph|victory)\b", re.IGNORECASE)


def normalize_ws(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


CHOICE_FULL_SENTENCE_RE = re.compile(
    r"([^.!?\n]*?\b(?:if|when|to|choose|decide|you)\b[^.!?\n]*?\b(?:turn|go|proceed)\s+(?:to\s+)?(?:page\s+|section\s+)?([1-9]\d{0,2}|500)\b[^.!?\n]*?[.!?\n]?)",
    re.IGNORECASE | re.DOTALL,
)

def extract_choices(section_text: str) -> list[dict[str, Any]]:
    choices: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    
    # Normalize text but keep some sentence structure
    text = normalize_ws(section_text)
    
    def add_choice(label: str, dest: int) -> None:
        label = normalize_ws(label)
        # Clean up label: remove trailing numbers if they are just the destination
        label = re.sub(rf"\s*(?:turn|go|proceed)\s+(?:to\s+)?(?:page\s+|section\s+)?{dest}\b.*$", "", label, flags=re.IGNORECASE).strip(" ,;:-.")
        if not label:
            label = f"Go to section {dest}"
        
        if not (1 <= dest <= 500):
            return
        key = (label, dest)
        if key in seen:
            return
        seen.add(key)
        choices.append({"text": label, "destination": dest})

    # Try to find full descriptive sentences first
    for match in CHOICE_FULL_SENTENCE_RE.finditer(text):
        full_sentence = match.group(1)
        dest = int(match.group(2))
        add_choice(full_sentence, dest)

    # Fallback: if no choices found, use the old line-based method but smarter
    if not choices:
        raw_lines = section_text.split("\n")
        lines = [normalize_ws(l) for l in raw_lines if l.strip()]
        for i, line in enumerate(lines):
            dest_match = ANY_NUM_RE.search(line)
            if dest_match and CHOICE_CUE_RE.search(line):
                dest = int(dest_match.group(1))
                # Try to grab the previous line if it looks like part of the choice
                label = line
                if i > 0 and not ANY_NUM_RE.search(lines[i-1]) and len(lines[i-1]) < 100:
                    label = f"{lines[i-1]} {line}"
                add_choice(label, dest)

    return choices


def classify_node(text: str, choices: list[dict[str, Any]]) -> str:
    if choices:
        return "normal"
    if DEATH_RE.search(text):
        return "ending_death"
    if WIN_RE.search(text):
        return "ending_win"
    return "ending_neutral"


def parse_sections(raw_text: str) -> list[dict[str, Any]]:
    lines = raw_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    sections: list[dict[str, Any]] = []
    current_num: int | None = None
    buf: list[str] = []

    def flush() -> None:
        nonlocal buf, current_num
        if current_num is None:
            buf = []
            return
        text = "\n".join(buf).strip()
        choices = extract_choices(text)
        node_type = classify_node(text, choices)
        sections.append(
            {
                "section_number": current_num,
                "text": text,
                "choices": choices,
                "node_type": node_type,
            }
        )
        buf = []

    for raw_line in lines:
        line = raw_line.strip()
        if line.startswith("--- PAGE ") and line.endswith(" ---"):
            continue
        if SECTION_RE.fullmatch(line):
            sec_no = int(line)
            if 1 <= sec_no <= 500:
                flush()
                current_num = sec_no
                continue
        if current_num is not None:
            buf.append(raw_line)
    flush()

    # Keep first appearance of each section number.
    unique: dict[int, dict[str, Any]] = {}
    for sec in sections:
        num = sec["section_number"]
        if num not in unique:
            unique[num] = sec
    return [unique[n] for n in sorted(unique)]


def main() -> None:
    if not RAW_PATH.exists():
        raise FileNotFoundError(f"Missing input file: {RAW_PATH}")

    raw_text = RAW_PATH.read_text(encoding="utf-8")
    sections = parse_sections(raw_text)
    PARSED_PATH.write_text(json.dumps(sections, indent=2, ensure_ascii=False), encoding="utf-8")

    section_numbers = {s["section_number"] for s in sections}
    total_sections = len(sections)
    total_choices = sum(len(s["choices"]) for s in sections)
    dead_ends = sum(1 for s in sections if len(s["choices"]) == 0)
    broken = sorted(
        {
            c["destination"]
            for s in sections
            for c in s["choices"]
            if c["destination"] not in section_numbers
        }
    )

    print(f"Total sections: {total_sections}")
    print(f"Total choices: {total_choices}")
    print(f"Dead ends: {dead_ends}")
    print(f"Broken links: {broken if broken else 'None'}")
    print(f"Wrote {PARSED_PATH}")


if __name__ == "__main__":
    main()
