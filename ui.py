#!/usr/bin/env python3
"""UI primitives for input, text effects, and transitions."""

from __future__ import annotations

from dataclasses import dataclass, field
import random

import pygame


@dataclass
class TypewriterTick:
    """Result payload for one typewriter update step."""

    revealed_chars: int = 0
    click_events: int = 0
    finished: bool = False


@dataclass
class TypewriterText:
    """Typewriter engine with punctuation pauses and skip support."""

    full_text: str = ""
    visible_chars: int = 0
    finished: bool = False
    base_delay_ms: int = 30
    punctuation_pause_ms: int = 200
    click_every_chars: int = 3
    _timer_ms: int = 0
    _pause_ms: int = 0
    _revealed_total: int = 0
    _cursor_timer_ms: int = 0
    _cursor_visible: bool = True

    def reset(self, new_text: str) -> None:
        self.full_text = new_text or ""
        self.visible_chars = 0
        self.finished = False
        self._timer_ms = 0
        self._pause_ms = 0
        self._revealed_total = 0
        self._cursor_timer_ms = 0
        self._cursor_visible = True

    def skip(self) -> None:
        self.visible_chars = len(self.full_text)
        self.finished = True

    def update(self, delta_ms: int) -> TypewriterTick:
        tick = TypewriterTick(finished=self.finished)
        self._cursor_timer_ms += max(0, int(delta_ms))
        if self._cursor_timer_ms >= 450:
            self._cursor_timer_ms = 0
            self._cursor_visible = not self._cursor_visible
        if self.finished:
            tick.finished = True
            return tick

        self._timer_ms += max(0, int(delta_ms))

        while self._timer_ms >= self.base_delay_ms and not self.finished:
            if self._pause_ms > 0:
                step = min(self._pause_ms, self._timer_ms)
                self._pause_ms -= step
                self._timer_ms -= step
                if self._pause_ms > 0:
                    break

            if self.visible_chars >= len(self.full_text):
                self.finished = True
                break

            self._timer_ms -= self.base_delay_ms
            next_char = self.full_text[self.visible_chars]
            self.visible_chars += 1
            self._revealed_total += 1
            tick.revealed_chars += 1

            if self._revealed_total % max(1, self.click_every_chars) == 0 and not next_char.isspace():
                tick.click_events += 1
            if next_char in ".!?":
                self._pause_ms += self.punctuation_pause_ms

            if self.visible_chars >= len(self.full_text):
                self.finished = True
                break

        tick.finished = self.finished
        return tick

    @property
    def visible_text(self) -> str:
        return self.full_text[: self.visible_chars]

    @property
    def cursor_visible(self) -> bool:
        return self._cursor_visible

@dataclass
class MenuCursor:
    """Cursor state for linear selectable menus."""

    index: int = 0

    def move(self, delta: int, total: int) -> None:
        if total <= 0:
            self.index = 0
            return
        self.index = (self.index + delta) % total

    def clamp(self, total: int) -> None:
        if total <= 0:
            self.index = 0
            return
        self.index = max(0, min(self.index, total - 1))


@dataclass
class TextInputField:
    """Simple blinking-cursor text input."""

    text: str = ""
    max_length: int = 16
    placeholder: str = "Traveler"
    _cursor_timer_ms: int = 0
    _cursor_visible: bool = True

    def update(self, delta_ms: int) -> None:
        self._cursor_timer_ms += max(0, int(delta_ms))
        if self._cursor_timer_ms >= 450:
            self._cursor_timer_ms = 0
            self._cursor_visible = not self._cursor_visible

    def clear(self) -> None:
        self.text = ""
        self._cursor_timer_ms = 0
        self._cursor_visible = True

    def handle_key(self, event: pygame.event.Event) -> bool:
        if event.type != pygame.KEYDOWN:
            return False
        if event.key == pygame.K_BACKSPACE:
            self.text = self.text[:-1]
            return True
        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_ESCAPE):
            return False
        if len(self.text) >= self.max_length:
            return False

        char = event.unicode
        if not char:
            return False
        if char.isprintable() and char not in "\r\n\t":
            self.text += char
            return True
        return False

    @property
    def value(self) -> str:
        cleaned = self.text.strip()
        return cleaned if cleaned else self.placeholder

    @property
    def display_value(self) -> str:
        return self.text if self.text else self.placeholder

    @property
    def cursor_visible(self) -> bool:
        return self._cursor_visible


@dataclass
class TransitionTick:
    """Result payload for one transition update step."""

    midpoint_reached: bool = False
    finished: bool = False


@dataclass
class ScreenTransition:
    """Fade-out/fade-in transition controller."""

    duration_ms: int = 300
    phase: str = "idle"  # idle | out | in
    timer_ms: int = 0
    _midpoint_emitted: bool = False

    def start(self) -> None:
        self.phase = "out"
        self.timer_ms = 0
        self._midpoint_emitted = False

    @property
    def active(self) -> bool:
        return self.phase != "idle"

    @property
    def alpha(self) -> int:
        if self.phase == "idle":
            return 0
        duration = max(1, self.duration_ms)
        if self.phase == "out":
            return int(min(255, (self.timer_ms / duration) * 255))
        return int(min(255, ((duration - self.timer_ms) / duration) * 255))

    def update(self, delta_ms: int) -> TransitionTick:
        tick = TransitionTick()
        if self.phase == "idle":
            return tick

        self.timer_ms += max(0, int(delta_ms))
        duration = max(1, self.duration_ms)

        if self.phase == "out" and self.timer_ms >= duration:
            self.phase = "in"
            self.timer_ms = 0
            if not self._midpoint_emitted:
                tick.midpoint_reached = True
                self._midpoint_emitted = True
            return tick

        if self.phase == "in" and self.timer_ms >= duration:
            self.phase = "idle"
            self.timer_ms = 0
            tick.finished = True
            return tick

        return tick


@dataclass
class ScreenShake:
    """Short-lived shake effect used on game-over transitions."""

    amplitude: int = 4
    total_frames: int = 8
    active: bool = False
    frame_index: int = 0
    rng: random.Random = field(default_factory=random.Random)

    def start(self) -> None:
        self.active = True
        self.frame_index = 0

    def update(self) -> tuple[int, int]:
        if not self.active:
            return (0, 0)
        if self.frame_index >= self.total_frames:
            self.active = False
            return (0, 0)
        self.frame_index += 1
        return (
            self.rng.randint(-self.amplitude, self.amplitude),
            self.rng.randint(-self.amplitude, self.amplitude),
        )
