#!/usr/bin/env python3
"""Story loading helpers for JSON-driven CYOA content."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Mapping


STAT_KEYS = ("health", "food", "gold", "morale")


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class StoryEngine:
    """Loads node data, resolves links, and evaluates stat requirements."""

    def __init__(self, story_path: str = "story.json") -> None:
        self.story_path = Path(story_path)
        self.nodes: list[dict[str, Any]] = []
        self.node_by_id: dict[str, dict[str, Any]] = {}

    def load(self) -> None:
        data: Any = None
        if self.story_path.exists():
            try:
                data = json.loads(self.story_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                data = None

        if not isinstance(data, list) or not data:
            self.nodes = self._default_story()
        else:
            normalized = [self._normalize_node(n) for n in data if isinstance(n, dict)]
            self.nodes = [n for n in normalized if n.get("id")]
            if not self.nodes:
                self.nodes = self._default_story()

        self.node_by_id = {node["id"]: node for node in self.nodes}
        self.nodes.sort(key=lambda n: (n.get("section_number", 10**9), n.get("id", "")))

    def _normalize_node(self, raw: Mapping[str, Any]) -> dict[str, Any]:
        node_id = str(raw.get("id", "")).strip()
        section_number = _as_int(raw.get("section_number"), 0)
        if not node_id:
            if section_number > 0:
                node_id = f"section_{section_number}"
            else:
                node_id = "section_0"
        if section_number <= 0 and node_id.startswith("section_"):
            section_number = _as_int(node_id.split("_")[-1], 0)

        choices_raw = raw.get("choices", [])
        choices: list[dict[str, Any]] = []
        seen_choices: set[tuple[str, str]] = set()
        if isinstance(choices_raw, list):
            for choice in choices_raw[:4]:
                if not isinstance(choice, Mapping):
                    continue
                next_id = str(choice.get("next", "")).strip()
                if not next_id:
                    continue
                choice_text = str(choice.get("text", "Continue")).strip() or "Continue"
                requires = choice.get("requires", {})
                effects = choice.get("effects", {})
                choices.append(
                    {
                        "text": choice_text,
                        "next": next_id,
                        "requires": requires if isinstance(requires, Mapping) else {},
                        "effects": effects if isinstance(effects, Mapping) else {},
                    }
                )
                norm_text = re.sub(r"[^a-z0-9]+", " ", choice_text.lower()).strip()
                dedupe_key = (norm_text, next_id)
                if dedupe_key in seen_choices:
                    choices.pop()
                    continue
                seen_choices.add(dedupe_key)

        node_type = str(raw.get("node_type", "normal")).strip() or "normal"
        if node_type not in {"normal", "ending_win", "ending_death", "ending_neutral"}:
            node_type = "normal" if choices else "ending_neutral"
        if node_type == "normal" and not choices:
            # Avoid softlocking on malformed normal nodes with no outgoing choices.
            node_type = "ending_neutral"

        ascii_art = raw.get("ascii_art", [])
        if not isinstance(ascii_art, list):
            ascii_art = []

        effects = raw.get("effects", {})
        if not isinstance(effects, Mapping):
            effects = {}

        random_events = raw.get("random_event_pool", [])
        if not isinstance(random_events, list):
            random_events = []

        return {
            "id": node_id,
            "section_number": section_number if section_number > 0 else 0,
            "title": str(raw.get("title", "")).strip() or "Untitled Scene",
            "text": str(raw.get("text", "")),
            "ascii_art": [str(x) for x in ascii_art[:10]],
            "node_type": node_type,
            "choices": choices,
            "effects": dict(effects),
            "random_event_pool": random_events,
        }

    def get_entry_node(self) -> dict[str, Any]:
        if "section_1" in self.node_by_id:
            return self.node_by_id["section_1"]
        # Otherwise, default to the lowest available section number.
        if self.nodes:
            return self.nodes[0]
        return self._default_story()[0]

    def get_node(self, node_id: str) -> dict[str, Any] | None:
        return self.node_by_id.get(node_id)

    def node_exists(self, node_id: str) -> bool:
        return node_id in self.node_by_id

    def resolve_node(self, node_or_id: str | Mapping[str, Any]) -> dict[str, Any] | None:
        if isinstance(node_or_id, str):
            return self.get_node(node_or_id)
        if isinstance(node_or_id, Mapping):
            node_id = str(node_or_id.get("id", "")).strip()
            if node_id and node_id in self.node_by_id:
                return self.node_by_id[node_id]
            return dict(node_or_id)
        return None

    def _extract_stats(self, player_or_stats: Mapping[str, Any] | Any | None) -> dict[str, Any]:
        stats: dict[str, Any] = {}
        for key in STAT_KEYS:
            if isinstance(player_or_stats, Mapping):
                stats[key] = _as_int(player_or_stats.get(key, 0), 0)
            elif player_or_stats is not None:
                stats[key] = _as_int(getattr(player_or_stats, key, 0), 0)
            else:
                stats[key] = 0
        if isinstance(player_or_stats, Mapping):
            for key, value in player_or_stats.items():
                if key not in stats:
                    stats[key] = value
        return stats

    @staticmethod
    def _compare_rule(current: Any, rule: Any) -> bool:
        if isinstance(rule, Mapping):
            checks: list[bool] = []
            if "min" in rule:
                checks.append(_as_int(current, 0) >= _as_int(rule["min"], 0))
            if "max" in rule:
                checks.append(_as_int(current, 0) <= _as_int(rule["max"], 0))
            if "gt" in rule:
                checks.append(_as_int(current, 0) > _as_int(rule["gt"], 0))
            if "gte" in rule:
                checks.append(_as_int(current, 0) >= _as_int(rule["gte"], 0))
            if "lt" in rule:
                checks.append(_as_int(current, 0) < _as_int(rule["lt"], 0))
            if "lte" in rule:
                checks.append(_as_int(current, 0) <= _as_int(rule["lte"], 0))
            if "eq" in rule:
                checks.append(current == rule["eq"])
            if "ne" in rule:
                checks.append(current != rule["ne"])
            if "in" in rule and isinstance(rule["in"], list):
                checks.append(current in rule["in"])
            if "not_in" in rule and isinstance(rule["not_in"], list):
                checks.append(current not in rule["not_in"])
            return all(checks) if checks else True

        if isinstance(rule, bool):
            return bool(current) is rule
        if isinstance(rule, (int, float)):
            # Numeric shorthand means minimum required value.
            return _as_int(current, 0) >= int(rule)
        return current == rule

    def requirements_met(
        self,
        requires: Mapping[str, Any] | None,
        player_or_stats: Mapping[str, Any] | Any | None,
    ) -> bool:
        if not requires:
            return True
        stats = self._extract_stats(player_or_stats)
        for key, rule in requires.items():
            if key not in stats:
                return False
            if not self._compare_rule(stats[key], rule):
                return False
        return True

    def choice_available(
        self,
        choice: Mapping[str, Any],
        player_or_stats: Mapping[str, Any] | Any | None,
    ) -> bool:
        requires = choice.get("requires", {})
        if not isinstance(requires, Mapping):
            return True
        return self.requirements_met(requires, player_or_stats)

    def get_available_choices(
        self,
        node_or_id: str | Mapping[str, Any],
        player_or_stats: Mapping[str, Any] | Any | None,
        include_locked: bool = False,
    ) -> list[dict[str, Any]]:
        node = self.resolve_node(node_or_id)
        if not node:
            return []
        raw_choices = node.get("choices", [])
        if not isinstance(raw_choices, list):
            return []
        choices = [c for c in raw_choices if isinstance(c, Mapping)]
        if include_locked:
            return [dict(c) for c in choices]
        return [dict(c) for c in choices if self.choice_available(c, player_or_stats)]

    def resolve_choice_next_id(
        self,
        node_or_id: str | Mapping[str, Any],
        choice_index: int,
        player_or_stats: Mapping[str, Any] | Any | None = None,
        include_locked: bool = False,
    ) -> str | None:
        choices = self.get_available_choices(
            node_or_id, player_or_stats=player_or_stats, include_locked=include_locked
        )
        if choice_index < 0 or choice_index >= len(choices):
            return None
        next_id = str(choices[choice_index].get("next", "")).strip()
        if not next_id or not self.node_exists(next_id):
            return None
        return next_id

    def resolve_choice_node(
        self,
        node_or_id: str | Mapping[str, Any],
        choice_index: int,
        player_or_stats: Mapping[str, Any] | Any | None = None,
        include_locked: bool = False,
    ) -> dict[str, Any] | None:
        next_id = self.resolve_choice_next_id(
            node_or_id,
            choice_index=choice_index,
            player_or_stats=player_or_stats,
            include_locked=include_locked,
        )
        if not next_id:
            return None
        return self.get_node(next_id)

    @staticmethod
    def _default_story() -> list[dict[str, Any]]:
        return [
            {
                "id": "section_1",
                "section_number": 1,
                "title": "Cold Start",
                "text": "No story file was found. Add story.json to continue.",
                "ascii_art": [
                    "┌──────────────────────────────────────┐",
                    "│                                      │",
                    "│                                      │",
                    "│                                      │",
                    "│            STORY NOT FOUND           │",
                    "│                                      │",
                    "│                                      │",
                    "│                                      │",
                    "│                 ●                    │",
                    "└──────────────────────────────────────┘",
                ],
                "node_type": "ending_neutral",
                "choices": [],
                "effects": {},
                "random_event_pool": [],
            }
        ]
