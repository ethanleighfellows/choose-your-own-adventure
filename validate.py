#!/usr/bin/env python3
"""Validate and auto-fix story.json constraints, then print final summary."""

from __future__ import annotations

import json
from collections import deque
from pathlib import Path
from typing import Any


STORY_PATH = Path("story.json")
VALID_NODE_TYPES = {"normal", "ending_win", "ending_death", "ending_neutral"}


def fit40(s: str) -> str:
    s = s[:40]
    if len(s) < 40:
        s += " " * (40 - len(s))
    return s


def default_art(label: str = "SCENE") -> list[str]:
    title = label.upper()[:20]
    line = title.center(38)
    art = [
        "┌──────────────────────────────────────┐",
        "│                                      │",
        "│                                      │",
        "│                                      │",
        f"│{line}│",
        "│                                      │",
        "│                                      │",
        "│                                      │",
        "│                 ●                    │",
        "└──────────────────────────────────────┘",
    ]
    return [fit40(r) for r in art]


def infer_node_type(node: dict[str, Any]) -> str:
    if node.get("choices"):
        return "normal"
    text = (node.get("text") or "").lower()
    if any(k in text for k in ("death", "die", "died", "killed", "fail", "failed")):
        return "ending_death"
    if any(k in text for k in ("win", "won", "escape", "success", "triumph", "victory")):
        return "ending_win"
    return "ending_neutral"


def bfs_depth(entry_id: str, graph: dict[str, list[str]]) -> int:
    if entry_id not in graph:
        return 0
    q: deque[tuple[str, int]] = deque([(entry_id, 0)])
    seen = {entry_id}
    max_depth = 0
    while q:
        node, d = q.popleft()
        if d > max_depth:
            max_depth = d
        for nxt in graph.get(node, []):
            if nxt not in seen:
                seen.add(nxt)
                q.append((nxt, d + 1))
    return max_depth


def reachable(entry_id: str, graph: dict[str, list[str]]) -> set[str]:
    if entry_id not in graph:
        return set()
    q = deque([entry_id])
    seen = {entry_id}
    while q:
        node = q.popleft()
        for nxt in graph.get(node, []):
            if nxt not in seen:
                seen.add(nxt)
                q.append(nxt)
    return seen


def auto_fix(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Remove duplicate IDs by keeping first.
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for node in nodes:
        node_id = node.get("id")
        if not node_id or node_id in seen:
            continue
        seen.add(node_id)
        deduped.append(node)
    nodes = deduped

    id_set = {n["id"] for n in nodes}

    # Fix required keys and art shape.
    for node in nodes:
        node.setdefault("section_number", int(str(node["id"]).split("_")[-1]))
        node.setdefault("title", "Untitled Scene")
        node.setdefault("text", "")
        node.setdefault("choices", [])
        node.setdefault("effects", {})
        node.setdefault("random_event_pool", [])

        art = node.get("ascii_art")
        if not isinstance(art, list):
            node["ascii_art"] = default_art(node["title"])
        else:
            fixed = [fit40(str(r)) for r in art[:10]]
            while len(fixed) < 10:
                fixed.append(" " * 40)
            node["ascii_art"] = fixed

        if node.get("node_type") not in VALID_NODE_TYPES:
            node["node_type"] = infer_node_type(node)
        elif node.get("choices"):
            node["node_type"] = "normal"

    # Ensure all next links exist; create stubs when needed.
    missing_ids: set[str] = set()
    for node in nodes:
        for choice in node.get("choices", []):
            nxt = choice.get("next")
            if isinstance(nxt, str) and nxt not in id_set:
                missing_ids.add(nxt)
            choice.setdefault("requires", {})
            choice.setdefault("effects", {})
            choice["text"] = str(choice.get("text", ""))[:60]

    if missing_ids:
        existing_numbers = {int(n["section_number"]) for n in nodes if isinstance(n.get("section_number"), int)}
        next_auto = max(existing_numbers) + 1 if existing_numbers else 1
        for missing in sorted(missing_ids):
            if missing.startswith("section_") and missing.split("_")[-1].isdigit():
                sec_no = int(missing.split("_")[-1])
            else:
                sec_no = next_auto
                next_auto += 1
            stub = {
                "id": missing,
                "section_number": sec_no,
                "title": "Missing Source Section",
                "text": f"[Section {sec_no} - not found in source]",
                "ascii_art": default_art("MISSING"),
                "node_type": "ending_neutral",
                "choices": [],
                "effects": {},
                "random_event_pool": [],
            }
            nodes.append(stub)
            id_set.add(missing)

    # Guarantee at least one win ending.
    if not any(n.get("node_type") == "ending_win" for n in nodes):
        converted = False
        for node in nodes:
            if node.get("node_type") == "ending_neutral" and not node.get("choices"):
                node["node_type"] = "ending_win"
                converted = True
                break
        if not converted:
            node = {
                "id": "section_999",
                "section_number": 999,
                "title": "Final Triumphant Escape",
                "text": "You survive and escape. Victory is yours.",
                "ascii_art": default_art("VICTORY"),
                "node_type": "ending_win",
                "choices": [],
                "effects": {},
                "random_event_pool": [],
            }
            nodes.append(node)

    # Sort with section 1 first if present, else lowest section number.
    nodes.sort(key=lambda n: n.get("section_number", 10**9))
    if any(n.get("section_number") == 1 for n in nodes):
        nodes.sort(key=lambda n: (n.get("section_number") != 1, n.get("section_number", 10**9)))

    return nodes


def summary(nodes: list[dict[str, Any]]) -> str:
    id_set = {n["id"] for n in nodes}
    graph = {
        n["id"]: [c.get("next") for c in n.get("choices", []) if c.get("next") in id_set]
        for n in nodes
    }
    entry = nodes[0]["id"] if nodes else ""
    reach = reachable(entry, graph) if entry else set()
    unreachable = sorted(id_set - reach)

    total_nodes = len(nodes)
    total_choices = sum(len(n.get("choices", [])) for n in nodes)
    win_count = sum(1 for n in nodes if n.get("node_type") == "ending_win")
    death_count = sum(1 for n in nodes if n.get("node_type") == "ending_death")
    neutral_count = sum(1 for n in nodes if n.get("node_type") == "ending_neutral")
    normal_nodes = [n for n in nodes if n.get("node_type") == "normal"]
    avg_choices = (
        sum(len(n.get("choices", [])) for n in normal_nodes) / len(normal_nodes) if normal_nodes else 0.0
    )
    depth = bfs_depth(entry, graph) if entry else 0

    lines = [
        f"Total nodes: {total_nodes}",
        f"Total choices: {total_choices}",
        f"Ending counts -> win: {win_count}, death: {death_count}, neutral: {neutral_count}",
        f"Average choices per normal node: {avg_choices:.2f}",
        f"Deepest reachable path length from entry ({entry}): {depth}",
        f"Unreachable nodes: {unreachable if unreachable else 'None'}",
    ]
    return "\n".join(lines)


def main() -> None:
    if not STORY_PATH.exists():
        raise FileNotFoundError(f"Missing file: {STORY_PATH}")

    nodes: list[dict[str, Any]] = json.loads(STORY_PATH.read_text(encoding="utf-8"))
    fixed = auto_fix(nodes)
    STORY_PATH.write_text(json.dumps(fixed, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Validation complete and auto-fixes applied.")
    print(summary(fixed))


if __name__ == "__main__":
    main()
