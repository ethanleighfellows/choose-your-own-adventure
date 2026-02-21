#!/usr/bin/env python3
"""Story quality gate for duplicate choices, reachability, and OCR noise."""

from __future__ import annotations

import argparse
import json
from collections import deque
from pathlib import Path
import re
import string
from typing import Any


def normalize_choice_text(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def choice_duplicates(nodes: list[dict[str, Any]]) -> list[tuple[str, str, str]]:
    dups: list[tuple[str, str, str]] = []
    for node in nodes:
        seen: set[tuple[str, str]] = set()
        for choice in node.get("choices", []):
            text = str(choice.get("text", ""))
            nxt = str(choice.get("next", ""))
            key = (normalize_choice_text(text), nxt)
            if key in seen:
                dups.append((node["id"], text, nxt))
            else:
                seen.add(key)
    return dups


def fix_duplicate_choices(nodes: list[dict[str, Any]]) -> int:
    removed = 0
    for node in nodes:
        unique: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for choice in node.get("choices", []):
            text = str(choice.get("text", ""))
            nxt = str(choice.get("next", ""))
            key = (normalize_choice_text(text), nxt)
            if key in seen:
                removed += 1
                continue
            seen.add(key)
            unique.append(choice)
        node["choices"] = unique[:4]
    return removed


def reachable_ratio(nodes: list[dict[str, Any]]) -> tuple[float, int, int]:
    if not nodes:
        return (0.0, 0, 0)
    idset = {n["id"] for n in nodes}
    graph = {n["id"]: [c.get("next") for c in n.get("choices", []) if c.get("next") in idset] for n in nodes}
    entry = nodes[0]["id"]

    q: deque[str] = deque([entry])
    seen = {entry}
    while q:
        cur = q.popleft()
        for nxt in graph.get(cur, []):
            if nxt not in seen:
                seen.add(nxt)
                q.append(nxt)
    return (len(seen) / len(nodes), len(seen), len(nodes))


def max_noise_ratio(nodes: list[dict[str, Any]]) -> tuple[float, str]:
    allowed = set(
        string.ascii_letters
        + string.digits
        + " \t\n\r.,!?;:'\"()-[]{}_/\\@#$%^&*+=<>|`~€£"
    )
    max_ratio = 0.0
    max_node = ""
    for node in nodes:
        text = str(node.get("text", ""))
        if not text:
            continue
        bad = sum(1 for ch in text if ch not in allowed)
        ratio = bad / len(text)
        if ratio > max_ratio:
            max_ratio = ratio
            max_node = node["id"]
    return (max_ratio, max_node)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Lint story quality constraints.")
    p.add_argument("--story", default="story.json", help="Path to story JSON.")
    p.add_argument("--min-reachable-ratio", type=float, default=0.15)
    p.add_argument("--max-noise-ratio", type=float, default=0.03)
    p.add_argument("--fix", action="store_true", help="Auto-fix duplicate choices in place.")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    story_path = Path(args.story)
    if not story_path.exists():
        print(f"ERROR: story file not found: {story_path}")
        return 2

    try:
        nodes = json.loads(story_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"ERROR: invalid JSON in {story_path}: {exc}")
        return 2
    if not isinstance(nodes, list):
        print(f"ERROR: story root must be a list: {story_path}")
        return 2

    if args.fix:
        removed = fix_duplicate_choices(nodes)
        if removed:
            story_path.write_text(json.dumps(nodes, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"FIXED: removed {removed} duplicate choices in {story_path}")

    duplicates = choice_duplicates(nodes)
    ratio, reachable, total = reachable_ratio(nodes)
    noise_ratio, noisy_node = max_noise_ratio(nodes)

    failed = False
    if duplicates:
        failed = True
        print(f"FAIL: duplicate choices detected ({len(duplicates)} total)")
    else:
        print("PASS: no duplicate choices")

    if ratio < args.min_reachable_ratio:
        failed = True
        print(
            f"FAIL: reachable ratio {ratio:.3f} is below threshold {args.min_reachable_ratio:.3f} "
            f"({reachable}/{total})"
        )
    else:
        print(
            f"PASS: reachable ratio {ratio:.3f} meets threshold {args.min_reachable_ratio:.3f} "
            f"({reachable}/{total})"
        )

    if noise_ratio > args.max_noise_ratio:
        failed = True
        print(
            f"FAIL: max noise ratio {noise_ratio:.3f} exceeds threshold {args.max_noise_ratio:.3f} "
            f"(node {noisy_node})"
        )
    else:
        print(
            f"PASS: max noise ratio {noise_ratio:.3f} within threshold {args.max_noise_ratio:.3f} "
            f"(node {noisy_node})"
        )

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
