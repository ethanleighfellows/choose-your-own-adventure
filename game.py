#!/usr/bin/env python3
"""Core game state machine and runtime loop."""

from __future__ import annotations

import json
import os
from pathlib import Path
import random
from typing import Any

import pygame

from player import PlayerState
from renderer import Renderer
from story import StoryEngine
from ui import MenuCursor, ScreenShake, ScreenTransition, TextInputField, TypewriterText


SAVE_PATH = Path("save.dat")
SAVE_TMP_PATH = Path("save.dat.tmp")
SAVE_REQUIRED_KEYS = {"player", "current_node_id", "visited_node_ids", "journal_entries"}
SAVE_PLAYER_KEYS = {"name", "health", "food", "gold", "morale"}

STATE_MENU = "menu"
STATE_NAME = "name_entry"
STATE_GAME = "gameplay"
STATE_JOURNAL = "journal"
STATE_GAME_OVER = "game_over"
STATE_VICTORY = "victory"
STATE_DATA_ERROR = "data_error"

JOURNAL_LIMIT = 500

DEFAULT_RANDOM_EVENTS = [
    {"text": "A traveler shares spare rations.", "effects": {"food": 6, "morale": 2}},
    {"text": "Cold rain soaks your gear and chills you.", "effects": {"health": -5, "morale": -3}},
    {"text": "You find a purse dropped on the trail.", "effects": {"gold": 8}},
    {"text": "A hard climb leaves you exhausted.", "effects": {"food": -6, "health": -3}},
    {"text": "A moment of luck renews your resolve.", "effects": {"morale": 5}},
]


class AudioManager:
    """Best-effort sound loader/player. Missing files never crash gameplay."""

    def __init__(self) -> None:
        self.enabled = False
        self.sounds: dict[str, pygame.mixer.Sound | None] = {}
        self.ambient_channel: pygame.mixer.Channel | None = None

        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init()
            self.enabled = True
        except pygame.error:
            self.enabled = False
            return

        self.sounds["click"] = self._load_sound("click.wav", volume=0.8)
        self.sounds["select"] = self._load_sound("select.wav", volume=0.8)
        self.sounds["danger"] = self._load_sound("danger.wav", volume=0.8)
        self.sounds["victory"] = self._load_sound("victory.wav", volume=0.8)
        self.sounds["death"] = self._load_sound("death.wav", volume=0.8)

        # Prefer WAV for deterministic compatibility in this project setup.
        ambient = self._load_sound("ambient.wav", volume=0.4)
        if ambient is None:
            ambient = self._load_sound("ambient.ogg", volume=0.4)
        self.sounds["ambient"] = ambient

    @staticmethod
    def _header_valid(path: Path) -> bool:
        ext = path.suffix.lower()
        try:
            header = path.read_bytes()[:4]
        except OSError:
            return False
        if ext == ".wav":
            return header == b"RIFF"
        if ext == ".ogg":
            return header == b"OggS"
        return True

    def _load_sound(self, filename: str, volume: float) -> pygame.mixer.Sound | None:
        if not self.enabled:
            return None
        path = Path("assets/sounds") / filename
        if not path.exists() or not self._header_valid(path):
            return None
        try:
            sound = pygame.mixer.Sound(str(path))
            sound.set_volume(max(0.0, min(1.0, volume)))
            return sound
        except pygame.error:
            return None

    def play(self, name: str) -> None:
        sound = self.sounds.get(name)
        if sound is not None:
            sound.play()

    def start_ambient(self) -> None:
        sound = self.sounds.get("ambient")
        if sound is None:
            return
        if self.ambient_channel and self.ambient_channel.get_busy():
            return
        self.ambient_channel = sound.play(loops=-1)

    def stop_ambient(self) -> None:
        if self.ambient_channel and self.ambient_channel.get_busy():
            self.ambient_channel.stop()
        self.ambient_channel = None


class Game:
    """Owns game runtime state and delegates rendering/audio."""

    def __init__(self, smoke: bool = False, max_frames: int = 90, autoplay: bool = False) -> None:
        self.renderer = Renderer()
        self.screen = pygame.display.set_mode((Renderer.WIDTH, Renderer.HEIGHT))
        self.clock = pygame.time.Clock()
        self.running = True
        self.smoke = smoke
        self.max_frames = max(1, int(max_frames))
        self.autoplay = autoplay
        self.frame_count = 0
        self.rng = random.Random()

        self.audio = AudioManager()
        self.story = StoryEngine("story.json")
        self.story.load()
        self.player = PlayerState()

        self.state = STATE_MENU
        self.menu_options = ["NEW GAME", "LOAD GAME", "QUIT"]
        self.menu_cursor = MenuCursor(0)
        self.menu_cursor_blink_ms = 0
        self.menu_cursor_visible = True

        self.name_input = TextInputField(max_length=18, placeholder="Traveler")
        self.typewriter = TypewriterText()
        self.transition = ScreenTransition(duration_ms=300)
        self.shake = ScreenShake(amplitude=4, total_frames=8)
        self.choice_cursor = MenuCursor(0)

        self.current_node = self.story.get_entry_node()
        self.current_node_id = self.current_node["id"]
        self.current_pages: list[str] = []
        self.current_page_idx = 0
        self.choice_rows: list[dict[str, Any]] = []
        self.pending_node_id: str | None = None

        self.visited_node_ids: list[str] = []
        self.journal_entries: list[str] = []
        self.journal_scroll = 0

        self.overlay_text = ""
        self.overlay_timer_ms = 0
        self.border_flash_timer_ms = 0

        self.end_text = ""
        self.victory_summary = ""
        self.autoplay_cooldown_ms = 0

    def _set_overlay(self, text: str, duration_ms: int = 1200, flash_border: bool = False) -> None:
        self.overlay_text = text
        self.overlay_timer_ms = max(0, int(duration_ms))
        if flash_border:
            self.border_flash_timer_ms = max(self.border_flash_timer_ms, 500)

    def _format_journal_line(self, node: dict[str, Any]) -> str:
        section = node.get("section_number", "?")
        title = str(node.get("title", "Untitled"))
        return f"{len(self.visited_node_ids):03d} | §{section} | {title}"

    def _clamp_journal_scroll(self) -> None:
        max_lines = self.renderer.journal_max_visible_lines()
        max_scroll = max(0, len(self.journal_entries) - max_lines)
        self.journal_scroll = max(0, min(self.journal_scroll, max_scroll))

    def _append_visit(self, node: dict[str, Any]) -> None:
        self.visited_node_ids.append(node["id"])
        self.journal_entries.append(self._format_journal_line(node))
        if len(self.visited_node_ids) > JOURNAL_LIMIT:
            overflow = len(self.visited_node_ids) - JOURNAL_LIMIT
            del self.visited_node_ids[:overflow]
        if len(self.journal_entries) > JOURNAL_LIMIT:
            overflow = len(self.journal_entries) - JOURNAL_LIMIT
            del self.journal_entries[:overflow]
            self.journal_scroll = max(0, self.journal_scroll - overflow)
        self._clamp_journal_scroll()

    def _rebuild_choices(self) -> None:
        rows: list[dict[str, Any]] = []
        choices = self.story.get_available_choices(self.current_node, self.player, include_locked=True)
        for choice in choices[:4]:
            locked = not self.story.choice_available(choice, self.player)
            rows.append(
                {
                    "text": str(choice.get("text", "Continue")),
                    "next": str(choice.get("next", "")),
                    "effects": choice.get("effects", {}) if isinstance(choice.get("effects"), dict) else {},
                    "locked": locked,
                }
            )
        self.choice_rows = rows
        unlocked = [idx for idx, c in enumerate(rows) if not c["locked"]]
        self.choice_cursor.index = unlocked[0] if unlocked else 0

    def _set_current_node(self, node_id: str, apply_node_effects: bool = True, record_visit: bool = True) -> bool:
        node = self.story.get_node(node_id)
        if node is None:
            return False

        self.current_node = node
        self.current_node_id = node["id"]

        if record_visit:
            self._append_visit(node)

        if apply_node_effects:
            self.player.apply_effects(node.get("effects", {}))

        story_inner = self.renderer._panel_inner(self.renderer.STORY_RECT)
        max_lines = max(1, story_inner.height // self.renderer.line_height)
        pages = self.renderer.paginate_text(str(node.get("text", "")), story_inner.width, max_lines)
        
        self.current_pages = ["\n".join(p) for p in pages]
        self.current_page_idx = 0
        self.typewriter.reset(self.current_pages[0] if self.current_pages else "")
        
        self._rebuild_choices()

        if self.player.health < 20:
            self.audio.play("danger")
        return True

    def _enter_data_error(self, text: str) -> None:
        self.audio.stop_ambient()
        self.state = STATE_DATA_ERROR
        self.end_text = text

    def _start_new_game(self, name: str) -> None:
        self.player = PlayerState(name=name)
        self.story.load()
        self.visited_node_ids.clear()
        self.journal_entries.clear()
        self.journal_scroll = 0
        self.end_text = ""
        self.victory_summary = ""
        self.overlay_text = ""
        self.overlay_timer_ms = 0
        self.border_flash_timer_ms = 0
        self.pending_node_id = None
        self.transition.phase = "idle"
        self.audio.start_ambient()
        self.state = STATE_GAME

        entry_id = self.story.get_entry_node()["id"]
        if not self._set_current_node(entry_id, apply_node_effects=True, record_visit=True):
            self._enter_data_error(f"Story data error: missing entry node '{entry_id}'.")

    def _save_game(self) -> None:
        payload = {
            "player": self.player.to_dict(),
            "current_node_id": self.current_node_id,
            "visited_node_ids": list(self.visited_node_ids),
            "journal_entries": list(self.journal_entries),
        }
        try:
            with SAVE_TMP_PATH.open("w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(SAVE_TMP_PATH, SAVE_PATH)
            self._set_overlay("Game saved.")
        except (OSError, TypeError, ValueError):
            self._set_overlay("Save failed.", duration_ms=1600, flash_border=True)
            try:
                if SAVE_TMP_PATH.exists():
                    SAVE_TMP_PATH.unlink()
            except OSError:
                pass

    @staticmethod
    def _validate_save_payload(payload: Any) -> dict[str, Any] | None:
        if not isinstance(payload, dict):
            return None
        if set(payload.keys()) != SAVE_REQUIRED_KEYS:
            return None

        player = payload.get("player")
        node_id = payload.get("current_node_id")
        visited = payload.get("visited_node_ids")
        journal = payload.get("journal_entries")

        if not isinstance(player, dict):
            return None
        if set(player.keys()) - SAVE_PLAYER_KEYS:
            return None
        if not isinstance(node_id, str) or not node_id:
            return None
        if not isinstance(visited, list) or not all(isinstance(x, str) for x in visited):
            return None
        if not isinstance(journal, list) or not all(isinstance(x, str) for x in journal):
            return None

        return {
            "player": player,
            "current_node_id": node_id,
            "visited_node_ids": visited[-JOURNAL_LIMIT:],
            "journal_entries": journal[-JOURNAL_LIMIT:],
        }

    def _load_game(self) -> bool:
        if not SAVE_PATH.exists():
            return False
        try:
            payload = json.loads(SAVE_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False

        valid_payload = self._validate_save_payload(payload)
        if valid_payload is None:
            return False

        self.player = PlayerState.from_dict(valid_payload["player"])
        self.visited_node_ids = list(valid_payload["visited_node_ids"])
        self.journal_entries = list(valid_payload["journal_entries"])
        self._clamp_journal_scroll()

        self.story.load()
        node_id = valid_payload["current_node_id"]
        if not self.story.node_exists(node_id):
            return False

        self.audio.start_ambient()
        self.state = STATE_GAME
        if not self._set_current_node(node_id, apply_node_effects=False, record_visit=False):
            return False
        self.typewriter.skip()
        self._set_overlay("Save loaded.")
        return True

    def _choose_random_event(self, next_node_id: str) -> dict[str, Any] | None:
        if self.rng.random() >= 0.10:
            return None
        node = self.story.get_node(next_node_id) or {}
        pool = node.get("random_event_pool", [])
        if isinstance(pool, list) and pool:
            valid = [e for e in pool if isinstance(e, dict)]
            if valid:
                return self.rng.choice(valid)
        return self.rng.choice(DEFAULT_RANDOM_EVENTS)

    def _apply_random_event(self, next_node_id: str) -> None:
        event = self._choose_random_event(next_node_id)
        if not event:
            return
        text = str(event.get("text", "A random event occurs."))
        effects = event.get("effects", {})
        if isinstance(effects, dict):
            self.player.apply_effects(effects)
            if any(int(v) < 0 for v in effects.values() if isinstance(v, (int, float))):
                self.audio.play("danger")
        self._set_overlay(text, duration_ms=1400, flash_border=True)

    def _move_choice_cursor(self, delta: int) -> None:
        total = len(self.choice_rows)
        if total == 0:
            return
        start = self.choice_cursor.index
        self.choice_cursor.move(delta, total)
        for _ in range(total):
            if not self.choice_rows[self.choice_cursor.index]["locked"]:
                return
            self.choice_cursor.move(delta, total)
        self.choice_cursor.index = start

    def _activate_choice(self, idx: int) -> None:
        if idx < 0 or idx >= len(self.choice_rows):
            return
        choice = self.choice_rows[idx]
        if choice.get("locked", False):
            return

        next_id = str(choice.get("next", "")).strip()
        if not next_id or not self.story.node_exists(next_id):
            self._set_overlay("Invalid story link.", duration_ms=1600, flash_border=True)
            return

        effects = choice.get("effects", {})
        if isinstance(effects, dict):
            self.player.apply_effects(effects)
        self.player.apply_upkeep()

        if self.player.health <= 0:
            self._enter_game_over("You collapse from your wounds before you can continue.")
            return

        self.audio.play("select")
        self._apply_random_event(next_id)
        self.pending_node_id = next_id
        self.transition.start()

    def _enter_game_over(self, text: str) -> None:
        self.audio.stop_ambient()
        self.audio.play("death")
        self.state = STATE_GAME_OVER
        self.end_text = text
        self.shake.start()

    def _enter_victory(self, text: str) -> None:
        self.audio.stop_ambient()
        self.audio.play("victory")
        self.state = STATE_VICTORY
        path = " -> ".join(self.visited_node_ids[-8:])
        self.victory_summary = f"{text}\n\nPath: {path}"

    def _resolve_terminal_node(self) -> None:
        node_type = str(self.current_node.get("node_type", "ending_neutral"))
        base_text = str(self.current_node.get("text", "Your adventure ends here."))

        if node_type == "ending_win":
            self._enter_victory(base_text)
            return
        if node_type == "ending_death":
            self._enter_game_over(base_text)
            return
        if node_type == "ending_neutral":
            self._enter_game_over(base_text)
            return
        if node_type == "normal" and not self.choice_rows:
            self._enter_game_over("This path cannot continue due to missing choices.")
            return
        if self.player.health <= 0:
            self._enter_game_over("You can continue no further.")

    def _handle_menu_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                self.menu_cursor.move(-1, len(self.menu_options))
            elif event.key == pygame.K_DOWN:
                self.menu_cursor.move(1, len(self.menu_options))
            elif event.key == pygame.K_l:
                if not self._load_game():
                    self._set_overlay("No valid save found.", duration_ms=1400)
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._activate_menu_option(self.menu_cursor.index)
        elif event.type == pygame.MOUSEMOTION:
            for idx, rect in enumerate(self.renderer.menu_hitboxes(len(self.menu_options))):
                if rect.collidepoint(event.pos):
                    self.menu_cursor.index = idx
                    break
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for idx, rect in enumerate(self.renderer.menu_hitboxes(len(self.menu_options))):
                if rect.collidepoint(event.pos):
                    self._activate_menu_option(idx)
                    break

    def _activate_menu_option(self, idx: int) -> None:
        if idx == 0:
            self.state = STATE_NAME
            self.name_input.clear()
        elif idx == 1:
            if not self._load_game():
                self._set_overlay("No valid save found.", duration_ms=1400)
        else:
            self.running = False

    def _handle_name_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.state = STATE_MENU
                return
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._start_new_game(self.name_input.value)
                return
        self.name_input.handle_key(event)

    def _handle_gameplay_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_j:
                self.state = STATE_JOURNAL
                return
            if event.key == pygame.K_s:
                self._save_game()
                return
            if event.key == pygame.K_UP:
                self._move_choice_cursor(-1)
                return
            if event.key == pygame.K_DOWN:
                self._move_choice_cursor(1)
                return
            if pygame.K_1 <= event.key <= pygame.K_4:
                if self.typewriter.finished:
                    idx = event.key - pygame.K_1
                    self._activate_choice(idx)
                return
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                if not self.typewriter.finished:
                    self.typewriter.skip()
                elif self.current_page_idx < len(self.current_pages) - 1:
                    self.current_page_idx += 1
                    self.typewriter.reset(self.current_pages[self.current_page_idx])
                elif self.choice_rows:
                    self._activate_choice(self.choice_cursor.index)
                else:
                    self._resolve_terminal_node()
                return
        elif event.type == pygame.MOUSEMOTION:
            for idx, rect in enumerate(self.renderer.choice_hitboxes(len(self.choice_rows))):
                if rect.collidepoint(event.pos):
                    self.choice_cursor.index = idx
                    break
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not self.typewriter.finished:
                self.typewriter.skip()
                return
            if self.current_page_idx < len(self.current_pages) - 1:
                self.current_page_idx += 1
                self.typewriter.reset(self.current_pages[self.current_page_idx])
                return
            for idx, rect in enumerate(self.renderer.choice_hitboxes(len(self.choice_rows))):
                if rect.collidepoint(event.pos):
                    self._activate_choice(idx)
                    break

    def _handle_journal_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        if event.key in (pygame.K_ESCAPE, pygame.K_j):
            self.state = STATE_GAME
        elif event.key == pygame.K_UP:
            self.journal_scroll -= 1
            self._clamp_journal_scroll()
        elif event.key == pygame.K_DOWN:
            self.journal_scroll += 1
            self._clamp_journal_scroll()

    def _handle_ending_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            self.state = STATE_MENU
            self.end_text = ""
            self.victory_summary = ""

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                continue

            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                if self.state == STATE_MENU:
                    self.running = False
                    continue
                if self.state == STATE_GAME:
                    self.running = False
                    continue
                if self.state == STATE_NAME:
                    self.state = STATE_MENU
                    continue
                if self.state == STATE_JOURNAL:
                    self.state = STATE_GAME
                    continue
                if self.state in (STATE_GAME_OVER, STATE_VICTORY, STATE_DATA_ERROR):
                    self.state = STATE_MENU
                    continue

            if self.state == STATE_MENU:
                self._handle_menu_event(event)
            elif self.state == STATE_NAME:
                self._handle_name_event(event)
            elif self.state == STATE_GAME:
                self._handle_gameplay_event(event)
            elif self.state == STATE_JOURNAL:
                self._handle_journal_event(event)
            else:
                self._handle_ending_event(event)

    def _update_autoplay(self, delta_ms: int) -> None:
        if not self.autoplay:
            return
        self.autoplay_cooldown_ms = max(0, self.autoplay_cooldown_ms - delta_ms)
        if self.autoplay_cooldown_ms > 0:
            return

        if self.state == STATE_MENU:
            self._activate_menu_option(0)
            self.autoplay_cooldown_ms = 150
            return
        if self.state == STATE_NAME:
            self._start_new_game("Auto")
            self.autoplay_cooldown_ms = 150
            return
        if self.state == STATE_GAME:
            if not self.typewriter.finished:
                self.typewriter.skip()
            elif self.choice_rows:
                for idx, choice in enumerate(self.choice_rows):
                    if not choice.get("locked", False):
                        self._activate_choice(idx)
                        break
            else:
                self._resolve_terminal_node()
            self.autoplay_cooldown_ms = 150
            return
        if self.state in (STATE_GAME_OVER, STATE_VICTORY, STATE_DATA_ERROR):
            if self.smoke:
                self.running = False
            else:
                self.state = STATE_MENU
            self.autoplay_cooldown_ms = 150

    def _update(self, delta_ms: int) -> None:
        self.menu_cursor_blink_ms += delta_ms
        if self.menu_cursor_blink_ms >= 450:
            self.menu_cursor_blink_ms = 0
            self.menu_cursor_visible = not self.menu_cursor_visible

        self.name_input.update(delta_ms)

        self.overlay_timer_ms = max(0, self.overlay_timer_ms - delta_ms)
        if self.overlay_timer_ms == 0:
            self.overlay_text = ""

        self.border_flash_timer_ms = max(0, self.border_flash_timer_ms - delta_ms)

        if self.transition.active:
            ttick = self.transition.update(delta_ms)
            if ttick.midpoint_reached and self.pending_node_id:
                if not self._set_current_node(
                    self.pending_node_id, apply_node_effects=True, record_visit=True
                ):
                    self._enter_data_error(
                        f"Story data error: missing destination '{self.pending_node_id}'."
                    )
                self.pending_node_id = None
        elif self.state == STATE_GAME:
            t_tick = self.typewriter.update(delta_ms)
            if t_tick.click_events > 0:
                self.audio.play("click")

            if self.player.health <= 0:
                self._enter_game_over("Your health has reached zero.")

        self._update_autoplay(delta_ms)

    def _build_frame(self) -> dict[str, Any]:
        if self.state == STATE_MENU:
            return {
                "screen": "menu",
                "menu_options": self.menu_options,
                "menu_index": self.menu_cursor.index,
                "menu_cursor_visible": self.menu_cursor_visible,
                "version_text": "v0.6.0",
                "event_text": self.overlay_text if self.overlay_timer_ms > 0 else "",
                "fade_alpha": self.transition.alpha,
                "offset": (0, 0),
            }
        if self.state == STATE_NAME:
            name_text = self.name_input.display_value
            if self.name_input.text:
                name_text = self.name_input.text
            return {
                "screen": "name_entry",
                "name_text": name_text,
                "name_cursor_visible": self.name_input.cursor_visible,
                "fade_alpha": self.transition.alpha,
                "offset": (0, 0),
            }
        if self.state == STATE_JOURNAL:
            return {
                "screen": "journal",
                "journal_entries": self.journal_entries,
                "journal_scroll": self.journal_scroll,
                "fade_alpha": self.transition.alpha,
                "offset": (0, 0),
            }
        if self.state == STATE_GAME_OVER:
            return {
                "screen": "game_over",
                "end_text": self.end_text or "Your journey ends here.",
                "fade_alpha": self.transition.alpha,
                "offset": self.shake.update(),
            }
        if self.state == STATE_DATA_ERROR:
            return {
                "screen": "data_error",
                "end_text": self.end_text or "Story data error.",
                "fade_alpha": self.transition.alpha,
                "offset": (0, 0),
            }
        if self.state == STATE_VICTORY:
            return {
                "screen": "victory",
                "victory_summary": self.victory_summary,
                "gold_pulse_alpha": self.renderer.pulse_alpha(pygame.time.get_ticks()),
                "fade_alpha": self.transition.alpha,
                "offset": (0, 0),
            }

        return {
            "screen": "gameplay",
            "player": self.player.to_dict(),
            "node": self.current_node,
            "story_text": self.typewriter.visible_text,
            "is_paginated": self.current_page_idx < len(self.current_pages) - 1,
            "show_story_cursor": self.typewriter.finished and self.typewriter.cursor_visible,
            "choices": self.choice_rows,
            "selected_choice_index": self.choice_cursor.index,
            "event_text": self.overlay_text if self.overlay_timer_ms > 0 else "",
            "border_flash": self.border_flash_timer_ms > 0,
            "gold_pulse_alpha": 0,
            "fade_alpha": self.transition.alpha,
            "offset": (0, 0),
        }

    def run(self) -> None:
        while self.running:
            delta_ms = self.clock.tick(30)
            self._handle_events()
            self._update(delta_ms)
            frame = self._build_frame()
            self.renderer.draw(self.screen, frame)
            pygame.display.flip()

            self.frame_count += 1
            if self.smoke and self.frame_count >= self.max_frames:
                self.running = False

        self.audio.stop_ambient()
