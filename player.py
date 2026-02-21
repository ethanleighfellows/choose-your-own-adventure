#!/usr/bin/env python3
"""Player state model for the CYOA game."""

from __future__ import annotations

import pickle
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping


SAVE_PATH = Path("save.dat")
STAT_NAMES = ("health", "food", "gold", "morale")

def _clamp(value: int, low: int = 0, high: int = 100) -> int:
    return max(low, min(high, int(value)))


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@dataclass
class PlayerState:
    """Mutable player stats used by game logic and rendering."""

    name: str = "Traveler"
    health: int = 100
    food: int = 100
    gold: int = 0
    morale: int = 100

    def __post_init__(self) -> None:
        self.health = _clamp(self.health)
        self.food = _clamp(self.food)
        self.gold = _clamp(self.gold)
        self.morale = _clamp(self.morale)
        self.name = str(self.name).strip() or "Traveler"

    def get_stat(self, stat: str) -> int:
        if stat not in STAT_NAMES:
            raise ValueError(f"Unknown stat: {stat}")
        return int(getattr(self, stat))

    def set_stat(self, stat: str, value: int) -> None:
        if stat not in STAT_NAMES:
            raise ValueError(f"Unknown stat: {stat}")
        setattr(self, stat, _clamp(_as_int(value)))

    def mutate_stat(self, stat: str, delta: int) -> int:
        """Apply a signed delta to one stat and return the new value."""
        current = self.get_stat(stat)
        updated = _clamp(current + _as_int(delta))
        setattr(self, stat, updated)
        return updated

    def apply_effects(self, effects: Mapping[str, Any]) -> dict[str, int]:
        """Apply stat deltas from a node/choice effect object."""
        deltas = {stat: _as_int(effects.get(stat, 0)) for stat in STAT_NAMES}
        for stat, delta in deltas.items():
            self.mutate_stat(stat, delta)
        return deltas

    def can_afford(self, amount: int) -> bool:
        return self.gold >= max(0, _as_int(amount))

    def spend_gold(self, amount: int) -> bool:
        cost = max(0, _as_int(amount))
        if self.gold < cost:
            return False
        self.gold = _clamp(self.gold - cost)
        return True

    def apply_upkeep(
        self,
        food_cost: int = 1,
        starving_health_penalty: int = 5,
        low_food_threshold: int = 20,
        low_food_morale_penalty: int = 1,
    ) -> dict[str, int]:
        """
        Apply per-turn survival rules.

        - Food always decreases by `food_cost`.
        - If food reaches 0, health decreases.
        - If food is low, morale decreases slightly.
        """
        food_before = self.food
        self.mutate_stat("food", -abs(_as_int(food_cost, 1)))
        deltas = {"health": 0, "food": self.food - food_before, "gold": 0, "morale": 0}

        if self.food <= 0:
            health_before = self.health
            self.mutate_stat("health", -abs(_as_int(starving_health_penalty, 5)))
            deltas["health"] = self.health - health_before
        elif self.food <= max(0, _as_int(low_food_threshold, 20)):
            morale_before = self.morale
            self.mutate_stat("morale", -abs(_as_int(low_food_morale_penalty, 1)))
            deltas["morale"] = self.morale - morale_before

        return deltas

    @property
    def is_alive(self) -> bool:
        return self.health > 0

    @property
    def is_starving(self) -> bool:
        return self.food <= 0

    def to_dict(self) -> dict[str, int | str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PlayerState":
        return cls(
            name=str(data.get("name", "Traveler")),
            health=_clamp(_as_int(data.get("health", 100), 100)),
            food=_clamp(_as_int(data.get("food", 100), 100)),
            gold=_clamp(_as_int(data.get("gold", 0), 0)),
            morale=_clamp(_as_int(data.get("morale", 100), 100)),
        )

    def save(self, path: str | Path = SAVE_PATH) -> None:
        save_path = Path(path)
        payload = self.to_dict()
        with save_path.open("wb") as fh:
            pickle.dump(payload, fh, protocol=pickle.HIGHEST_PROTOCOL)

    @classmethod
    def load(cls, path: str | Path = SAVE_PATH) -> "PlayerState":
        save_path = Path(path)
        with save_path.open("rb") as fh:
            payload = pickle.load(fh)
        if not isinstance(payload, dict):
            raise ValueError(f"Invalid save data in {save_path}")
        return cls.from_dict(payload)
