#!/usr/bin/env python3
"""Entry point for the CYOA pygame game."""

from __future__ import annotations

import argparse

import pygame

from game import Game


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CYOA pygame game")
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Run for a small number of frames and exit (test mode).",
    )
    parser.add_argument(
        "--frames",
        type=int,
        default=90,
        help="Frame budget for --smoke mode.",
    )
    parser.add_argument(
        "--autoplay",
        action="store_true",
        help="Automatically progress through menus and choices (useful for smoke tests).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pygame.init()
    try:
        if pygame.mixer.get_init() is None:
            pygame.mixer.init()
    except pygame.error:
        # Audio is optional in environments without an audio device.
        pass

    pygame.display.set_caption("Choose Your Own Adventure")

    game = Game(smoke=args.smoke, max_frames=max(1, args.frames), autoplay=args.autoplay)
    game.run()

    if pygame.mixer.get_init() is not None:
        pygame.mixer.quit()
    pygame.quit()


if __name__ == "__main__":
    main()
