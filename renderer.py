#!/usr/bin/env python3
"""Retro CRT renderer for menu, gameplay, journal, and ending screens."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pygame


class Renderer:
    """Centralized drawing module for all game screens."""

    WIDTH = 800
    HEIGHT = 600

    COLOR_BG = (0x0A, 0x0A, 0x0A)
    COLOR_TEXT = (0x39, 0xFF, 0x14)
    COLOR_DIM = (0x1A, 0x7A, 0x08)
    COLOR_HIGHLIGHT = (0xFF, 0xFF, 0xFF)
    COLOR_DANGER = (0xFF, 0x31, 0x31)
    COLOR_GOLD = (0xFF, 0xD7, 0x00)
    COLOR_BORDER = (0x39, 0xFF, 0x14)
    COLOR_LOCKED = (0x33, 0x33, 0x33)

    STAT_BAR_RECT = pygame.Rect(0, 0, WIDTH, 36)
    SCENE_RECT = pygame.Rect(0, 36, WIDTH, 160)
    STORY_RECT = pygame.Rect(0, 196, WIDTH, 240)
    CHOICE_RECT = pygame.Rect(0, 436, WIDTH, 164)

    INNER_PADDING = 12

    TITLE_ART = [
        "  ██████╗██╗   ██╗ ██████╗  █████╗ ",
        " ██╔════╝╚██╗ ██╔╝██╔═══██╗██╔══██╗",
        " ██║      ╚████╔╝ ██║   ██║███████║",
        " ██║       ╚██╔╝  ██║   ██║██╔══██║",
        " ╚██████╗   ██║   ╚██████╔╝██║  ██║",
        "  ╚═════╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝",
        "  CHOOSE YOUR OWN ADVENTURE ENGINE  ",
    ]

    def __init__(self) -> None:
        self.body_font = self._load_font(14)
        self.title_font = self._load_font(22)
        self.small_font = self._load_font(12)
        self.char_w = self.body_font.size("M")[0]
        self.line_height = int(self.body_font.get_linesize() * 1.6)
        self.scanline_surface = self._make_scanline_surface()
        self.frame_surface = pygame.Surface((self.WIDTH, self.HEIGHT))
        self.fade_surface = pygame.Surface((self.WIDTH, self.HEIGHT), pygame.SRCALPHA)
        self._node_art_cache: dict[str, pygame.Surface] = {}
        self._wrap_cache: dict[tuple[str, int], list[str]] = {}
        self._wrap_cache_order: list[tuple[str, int]] = []

    def _load_font(self, size: int) -> pygame.font.Font:
        font_path = Path("assets/fonts/PressStart2P-Regular.ttf")
        if font_path.exists():
            return pygame.font.Font(str(font_path), size)
        return pygame.font.SysFont("couriernew", size)

    def _make_scanline_surface(self) -> pygame.Surface:
        surface = pygame.Surface((self.WIDTH, self.HEIGHT), pygame.SRCALPHA)
        for y in range(0, self.HEIGHT, 2):
            pygame.draw.line(surface, (0, 0, 0, 38), (0, y), (self.WIDTH, y))
        return surface

    @staticmethod
    def _bar(value: int) -> str:
        blocks = max(0, min(10, int(value) // 10))
        return ("■" * blocks) + ("░" * (10 - blocks))

    @staticmethod
    def _truncate(text: str, max_chars: int) -> str:
        if len(text) <= max_chars:
            return text
        if max_chars <= 1:
            return text[:max_chars]
        return text[: max_chars - 1] + "…"

    def _wrap_text(self, text: str, max_width: int) -> list[str]:
        cache_key = (text, max_width)
        cached = self._wrap_cache.get(cache_key)
        if cached is not None:
            return list(cached)
        if not text:
            return []

        def split_long_word(word: str) -> list[str]:
            if self.body_font.size(word)[0] <= max_width:
                return [word]
            parts: list[str] = []
            buf = ""
            for ch in word:
                candidate = buf + ch
                if self.body_font.size(candidate)[0] <= max_width:
                    buf = candidate
                else:
                    if buf:
                        parts.append(buf)
                    buf = ch
            if buf:
                parts.append(buf)
            return parts

        lines: list[str] = []
        # Split by explicit double newlines first to preserve paragraph breaks
        paragraphs = text.split("\n\n")
        for i, para in enumerate(paragraphs):
            # Also handle single newlines as spaces unless they are intentional
            para = para.replace("\n", " ").strip()
            if not para:
                continue
            
            words = para.split(" ")
            current_line = ""
            for word in words:
                if not word:
                    continue
                word_parts = split_long_word(word)
                for part in word_parts:
                    test_line = f"{current_line} {part}".strip()
                    if self.body_font.size(test_line)[0] <= max_width:
                        current_line = test_line
                    else:
                        if current_line:
                            lines.append(current_line)
                        current_line = part
            if current_line:
                lines.append(current_line)
            
            # Add a blank line between paragraphs, but not after the last one
            if i < len(paragraphs) - 1:
                lines.append("")

        self._wrap_cache[cache_key] = list(lines)
        self._wrap_cache_order.append(cache_key)
        if len(self._wrap_cache_order) > 256:
            old_key = self._wrap_cache_order.pop(0)
            self._wrap_cache.pop(old_key, None)
        return lines

    def paginate_text(self, text: str, max_width: int, max_lines: int) -> list[list[str]]:
        """Split wrapped lines into pages based on maximum lines per page."""
        lines = self._wrap_text(text, max_width)
        if not lines:
            return [[]]
        
        pages: list[list[str]] = []
        current_page: list[str] = []
        
        for line in lines:
            if len(current_page) >= max_lines:
                pages.append(current_page)
                current_page = []
            # Skip leading empty lines on a new page unless the previous page ended with one (unlikely)
            if not current_page and line == "":
                continue
            current_page.append(line)
        
        if current_page:
            pages.append(current_page)
        
        if not pages:
            return [[]]
        return pages

    def _draw_ascii_border(
        self, canvas: pygame.Surface, rect: pygame.Rect, color: tuple[int, int, int]
    ) -> None:
        pygame.draw.rect(canvas, self.COLOR_BG, rect)

        cols = max(2, rect.width // self.char_w)
        rows = max(2, rect.height // self.body_font.get_linesize())
        top = "╔" + ("═" * (cols - 2)) + "╗"
        mid = "║" + (" " * (cols - 2)) + "║"
        bot = "╚" + ("═" * (cols - 2)) + "╝"

        y = rect.y
        for row_idx in range(rows):
            if row_idx == 0:
                line = top
            elif row_idx == rows - 1:
                line = bot
            else:
                line = mid
            rendered = self.body_font.render(line, True, color)
            canvas.blit(rendered, (rect.x, y))
            y += self.body_font.get_linesize()

    def _panel_inner(self, rect: pygame.Rect) -> pygame.Rect:
        return rect.inflate(-(self.INNER_PADDING * 2), -(self.INNER_PADDING * 2))

    def choice_hitboxes(self, count: int) -> list[pygame.Rect]:
        inner = self._panel_inner(self.CHOICE_RECT)
        boxes: list[pygame.Rect] = []
        for idx in range(max(0, count)):
            y = inner.y + idx * self.line_height
            boxes.append(pygame.Rect(inner.x, y, inner.width, self.line_height))
        return boxes

    def menu_hitboxes(self, count: int) -> list[pygame.Rect]:
        start_y = 360
        h = self.line_height
        x = self.WIDTH // 2 - 150
        w = 300
        return [pygame.Rect(x, start_y + i * (h + 6), w, h + 4) for i in range(max(0, count))]

    def journal_max_visible_lines(self) -> int:
        panel = pygame.Rect(40, 40, self.WIDTH - 80, self.HEIGHT - 80)
        inner = self._panel_inner(panel)
        return max(1, (inner.height - (self.line_height * 3)) // self.line_height)

    def _draw_overlay_box(
        self,
        canvas: pygame.Surface,
        text: str,
        border_color: tuple[int, int, int] | None = None,
    ) -> None:
        if not text:
            return
        overlay_rect = pygame.Rect(140, 230, 520, 120)
        color = border_color if border_color is not None else self.COLOR_BORDER
        self._draw_ascii_border(canvas, overlay_rect, color)
        inner = self._panel_inner(overlay_rect)
        lines = self._wrap_text(str(text), inner.width)
        for idx, line in enumerate(lines[:3]):
            surf = self.body_font.render(line, True, self.COLOR_TEXT)
            canvas.blit(surf, (inner.x, inner.y + idx * self.line_height))

    def _get_node_art_surface(self, node: dict[str, Any]) -> pygame.Surface:
        node_id = str(node.get("id", ""))
        ascii_art = node.get("ascii_art", [])
        cache_key = f"{node_id}|{len(ascii_art)}|{hash(tuple(ascii_art[:10]))}"
        cached = self._node_art_cache.get(cache_key)
        if cached is not None:
            return cached

        surface = pygame.Surface((40 * self.char_w, 10 * self.body_font.get_linesize()), pygame.SRCALPHA)
        y = 0
        for row in ascii_art[:10]:
            row_text = str(row)[:40].ljust(40)
            x = 0
            for ch in row_text:
                color = self.COLOR_DIM if ch in "░▒▓" else self.COLOR_TEXT
                glyph = self.body_font.render(ch, True, color)
                surface.blit(glyph, (x, y))
                x += self.char_w
            y += self.body_font.get_linesize()

        if len(self._node_art_cache) > 256:
            self._node_art_cache.clear()
        self._node_art_cache[cache_key] = surface
        return surface

    def draw(self, screen: pygame.Surface, frame: dict[str, Any]) -> None:
        canvas = self.frame_surface
        canvas.fill(self.COLOR_BG)

        scene = frame.get("screen", "gameplay")
        if scene == "menu":
            self._draw_main_menu(canvas, frame)
        elif scene == "name_entry":
            self._draw_name_entry(canvas, frame)
        elif scene == "journal":
            self._draw_journal(canvas, frame)
        elif scene == "game_over":
            self._draw_game_over(canvas, frame)
        elif scene == "data_error":
            self._draw_data_error(canvas, frame)
        elif scene == "victory":
            self._draw_victory(canvas, frame)
        else:
            self._draw_gameplay(canvas, frame)

        fade_alpha = int(frame.get("fade_alpha", 0))
        if fade_alpha > 0:
            self.fade_surface.fill((0, 0, 0, max(0, min(255, fade_alpha))))
            canvas.blit(self.fade_surface, (0, 0))

        canvas.blit(self.scanline_surface, (0, 0))
        offset = frame.get("offset", (0, 0))
        screen.fill(self.COLOR_BG)
        screen.blit(canvas, offset)

    def _draw_stat_bar(self, canvas: pygame.Surface, frame: dict[str, Any]) -> None:
        player = frame.get("player", {})
        name = str(player.get("name", "Traveler"))
        health = int(player.get("health", 100))
        food = int(player.get("food", 100))
        gold = int(player.get("gold", 0))
        morale = int(player.get("morale", 100))

        name_surface = self.body_font.render(name, True, self.COLOR_TEXT)
        canvas.blit(name_surface, (12, 10))

        stats = (
            f"HP:{self._bar(health)}  "
            f"Food:{self._bar(food)}  "
            f"Gold:{self._bar(gold)}  "
            f"Morale:{self._bar(morale)}"
        )
        stats_color = self.COLOR_DANGER if health < 20 else self.COLOR_TEXT
        stats_surface = self.small_font.render(stats, True, stats_color)
        canvas.blit(stats_surface, (self.WIDTH - stats_surface.get_width() - 12, 10))

        line_chars = "═" * max(1, self.WIDTH // self.char_w)
        rule = self.body_font.render(line_chars, True, self.COLOR_BORDER)
        canvas.blit(rule, (0, self.STAT_BAR_RECT.bottom - 4))

    def _draw_gameplay(self, canvas: pygame.Surface, frame: dict[str, Any]) -> None:
        if frame.get("gold_pulse_alpha", 0) > 0:
            pulse = pygame.Surface((self.WIDTH, self.HEIGHT), pygame.SRCALPHA)
            pulse.fill((self.COLOR_GOLD[0], self.COLOR_GOLD[1], self.COLOR_GOLD[2], frame["gold_pulse_alpha"]))
            canvas.blit(pulse, (0, 0))

        border_color = self.COLOR_DANGER if frame.get("border_flash", False) else self.COLOR_BORDER
        self._draw_stat_bar(canvas, frame)
        self._draw_ascii_border(canvas, self.SCENE_RECT, border_color)
        self._draw_ascii_border(canvas, self.STORY_RECT, border_color)
        self._draw_ascii_border(canvas, self.CHOICE_RECT, border_color)

        node = frame.get("node", {})
        art_inner = self._panel_inner(self.SCENE_RECT)
        art_surface = self._get_node_art_surface(node)
        start_x = art_inner.x + max(0, (art_inner.width - art_surface.get_width()) // 2)
        canvas.blit(art_surface, (start_x, art_inner.y))

        story_inner = self._panel_inner(self.STORY_RECT)
        story_text = str(frame.get("story_text", ""))
        
        # If text contains newlines, we treat it as pre-paginated lines
        if "\n" in story_text:
            lines = story_text.split("\n")
        else:
            lines = self._wrap_text(story_text, story_inner.width)
            
        max_story_lines = max(1, story_inner.height // self.line_height)
        for idx, line in enumerate(lines[:max_story_lines]):
            surface = self.body_font.render(line, True, self.COLOR_TEXT)
            canvas.blit(surface, (story_inner.x, story_inner.y + idx * self.line_height))

        if frame.get("show_story_cursor", False):
            is_paginated = bool(frame.get("is_paginated", False))
            cursor_text = "NEXT PAGE ▶" if is_paginated else "▶"
            cursor_surface = self.body_font.render(cursor_text, True, self.COLOR_TEXT)
            x = story_inner.right - cursor_surface.get_width()
            y = story_inner.bottom - cursor_surface.get_height()
            canvas.blit(cursor_surface, (x, y))

        choice_inner = self._panel_inner(self.CHOICE_RECT)
        choices = frame.get("choices", [])
        selected = int(frame.get("selected_choice_index", 0))
        for idx, choice in enumerate(choices[:4]):
            locked = bool(choice.get("locked", False))
            text = str(choice.get("text", "Continue"))
            if locked:
                prefix = "[✗]"
                color = self.COLOR_LOCKED
            elif idx == selected:
                prefix = ">"
                color = self.COLOR_HIGHLIGHT
            else:
                prefix = f"[{idx + 1}]"
                color = self.COLOR_DIM

            max_chars = max(8, (choice_inner.width // self.char_w) - len(prefix) - 2)
            line = f"{prefix} {self._truncate(text, max_chars)}"
            surf = self.body_font.render(line, True, color)
            canvas.blit(surf, (choice_inner.x, choice_inner.y + idx * self.line_height))

        event_text = frame.get("event_text")
        self._draw_overlay_box(canvas, str(event_text) if event_text else "", border_color=border_color)

    def _draw_main_menu(self, canvas: pygame.Surface, frame: dict[str, Any]) -> None:
        y = 90
        for line in self.TITLE_ART:
            surf = self.body_font.render(line, True, self.COLOR_TEXT)
            x = (self.WIDTH - surf.get_width()) // 2
            canvas.blit(surf, (x, y))
            y += self.line_height

        options = frame.get("menu_options", [])
        selected = int(frame.get("menu_index", 0))
        blink = bool(frame.get("menu_cursor_visible", True))
        hitboxes = self.menu_hitboxes(len(options))
        for idx, option in enumerate(options):
            rect = hitboxes[idx]
            label = str(option)
            prefix = "▶" if idx == selected and blink else " "
            color = self.COLOR_HIGHLIGHT if idx == selected else self.COLOR_DIM
            text = f"{prefix} {label}"
            surf = self.body_font.render(text, True, color)
            canvas.blit(surf, (rect.x, rect.y))

        version = str(frame.get("version_text", "v0.1.0"))
        vsurf = self.small_font.render(version, True, self.COLOR_DIM)
        canvas.blit(vsurf, (self.WIDTH - vsurf.get_width() - 8, self.HEIGHT - vsurf.get_height() - 8))

        event_text = frame.get("event_text")
        self._draw_overlay_box(canvas, str(event_text) if event_text else "")

    def _draw_name_entry(self, canvas: pygame.Surface, frame: dict[str, Any]) -> None:
        prompt = "ENTER YOUR NAME"
        prompt_surf = self.title_font.render(prompt, True, self.COLOR_TEXT)
        canvas.blit(prompt_surf, ((self.WIDTH - prompt_surf.get_width()) // 2, 180))

        input_rect = pygame.Rect(140, 260, 520, 84)
        self._draw_ascii_border(canvas, input_rect, self.COLOR_BORDER)
        inner = self._panel_inner(input_rect)

        name_text = str(frame.get("name_text", "Traveler"))
        if frame.get("name_cursor_visible", True):
            name_text = f"{name_text}_"
        rendered = self.body_font.render(name_text, True, self.COLOR_HIGHLIGHT)
        canvas.blit(rendered, (inner.x, inner.y + 20))

        hint = "Press ENTER to begin"
        hint_surf = self.small_font.render(hint, True, self.COLOR_DIM)
        canvas.blit(hint_surf, ((self.WIDTH - hint_surf.get_width()) // 2, 360))

    def _draw_journal(self, canvas: pygame.Surface, frame: dict[str, Any]) -> None:
        panel = pygame.Rect(40, 40, self.WIDTH - 80, self.HEIGHT - 80)
        self._draw_ascii_border(canvas, panel, self.COLOR_BORDER)
        inner = self._panel_inner(panel)

        title = self.title_font.render("JOURNAL", True, self.COLOR_TEXT)
        canvas.blit(title, (inner.x, inner.y))
        y = inner.y + self.line_height * 2

        entries = frame.get("journal_entries", [])
        scroll = int(frame.get("journal_scroll", 0))
        max_lines = self.journal_max_visible_lines()
        for idx, entry in enumerate(entries[scroll : scroll + max_lines]):
            surf = self.body_font.render(str(entry), True, self.COLOR_DIM)
            canvas.blit(surf, (inner.x, y + idx * self.line_height))

        hint = self.small_font.render("J to close  ↑/↓ scroll", True, self.COLOR_DIM)
        canvas.blit(hint, (inner.x, panel.bottom - self.line_height - 8))

    def _draw_game_over(self, canvas: pygame.Surface, frame: dict[str, Any]) -> None:
        msg = str(frame.get("end_text", "Your adventure has ended."))
        title = self.title_font.render("GAME OVER", True, self.COLOR_DANGER)
        canvas.blit(title, ((self.WIDTH - title.get_width()) // 2, 200))

        lines = self._wrap_text(msg, self.WIDTH - 120)
        for idx, line in enumerate(lines[:4]):
            surf = self.body_font.render(line, True, self.COLOR_TEXT)
            canvas.blit(surf, (60, 280 + idx * self.line_height))

        hint = self.small_font.render("Press ENTER to return to menu", True, self.COLOR_DIM)
        canvas.blit(hint, ((self.WIDTH - hint.get_width()) // 2, 500))

    def _draw_data_error(self, canvas: pygame.Surface, frame: dict[str, Any]) -> None:
        msg = str(frame.get("end_text", "Story data error."))
        title = self.title_font.render("DATA ERROR", True, self.COLOR_DANGER)
        canvas.blit(title, ((self.WIDTH - title.get_width()) // 2, 180))

        lines = self._wrap_text(msg, self.WIDTH - 120)
        for idx, line in enumerate(lines[:5]):
            surf = self.body_font.render(line, True, self.COLOR_TEXT)
            canvas.blit(surf, (60, 260 + idx * self.line_height))

        hint = self.small_font.render("Press ENTER to return to menu", True, self.COLOR_DIM)
        canvas.blit(hint, ((self.WIDTH - hint.get_width()) // 2, 520))

    def _draw_victory(self, canvas: pygame.Surface, frame: dict[str, Any]) -> None:
        pulse = int(frame.get("gold_pulse_alpha", 0))
        if pulse > 0:
            overlay = pygame.Surface((self.WIDTH, self.HEIGHT), pygame.SRCALPHA)
            overlay.fill((self.COLOR_GOLD[0], self.COLOR_GOLD[1], self.COLOR_GOLD[2], pulse))
            canvas.blit(overlay, (0, 0))

        title = self.title_font.render("VICTORY", True, self.COLOR_GOLD)
        canvas.blit(title, ((self.WIDTH - title.get_width()) // 2, 120))

        summary = str(frame.get("victory_summary", "You escaped the worst and lived to tell it."))
        lines = self._wrap_text(summary, self.WIDTH - 120)
        for idx, line in enumerate(lines[:7]):
            surf = self.body_font.render(line, True, self.COLOR_TEXT)
            canvas.blit(surf, (60, 200 + idx * self.line_height))

        hint = self.small_font.render("Press ENTER to return to menu", True, self.COLOR_DIM)
        canvas.blit(hint, ((self.WIDTH - hint.get_width()) // 2, 520))

    def pulse_alpha(self, ticks_ms: int) -> int:
        wave = (math.sin(ticks_ms / 350.0) + 1.0) / 2.0
        return int(30 + wave * 60)
