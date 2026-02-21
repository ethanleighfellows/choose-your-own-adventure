

# CYOA Game — Product Overview

## What We're Building
A **Choose Your Own Adventure game engine** written entirely in Python using Pygame.
The player loads a story (defined in `story.json`), navigates branching narrative nodes via
on-screen choices, manages a small set of stats, and reaches one of several win or death endings.

The visual identity is inspired by **The Oregon Trail (1985)** — a retro CRT terminal aesthetic
with green-on-black text, ASCII scene art, and typewriter-style text rendering.

The engine is fully **data-driven**: all story content lives in `story.json`. The Python code
never needs to change to add new stories.

---

## Final Product

### Screens
| Screen | Description |
|---|---|
| Main Menu | ASCII title art, NEW GAME / LOAD GAME / QUIT options |
| Name Entry | Blinking cursor text input field |
| Game Screen | Scene art panel + story text panel + choice buttons + stat bar |
| Journal | Scrollable history of visited nodes (press J) |
| Game Over | Cause of death message + PLAY AGAIN prompt |
| Victory | Summary of path taken + ending flavour text |

### Gameplay Loop
1. Player arrives at a story node
2. Scene ASCII art renders in the top panel
3. Node text prints with typewriter effect (character by character)
4. Choices appear in the bottom panel; hidden if player lacks required stats
5. Player presses 1–4 or clicks to choose
6. Effects modify player stats (health, food, gold, morale)
7. 10% chance of a random modifier event fires before next node loads
8. Loop continues until a `win` or `death` node is reached

### Player Stats
- **Health** (0–100): reaches 0 = game over
- **Food** (0–100): depletes over time; low food drains health
- **Gold** (0–100): used to unlock certain choices
- **Morale** (0–100): affects available choices and random event outcomes

### Save System
- Press **S** at any time to save to `save.dat` (pickle)
- Press **L** on main menu to load last save

---

## File Structure

project/├── main.py          # Entry point, pygame init, screen router├── game.py          # Core game loop, screen state management├── renderer.py      # All Pygame drawing (panels, borders, scanlines)├── story.py         # JSON loader, node engine, stat condition checks├── player.py        # Player state, stat mutations, serialisation├── ui.py            # Typewriter text, buttons, input fields, transitions├── story.json       # All story content (nodes, choices, effects)├── assets/│   ├── fonts/       # Press Start 2P or Courier New fallback│   └── sounds/      # Keyclick SFX, ambient loop, sting sounds├── PRODUCT.md├── DESIGN.md└── PROGRESS.md

---

## Non-Negotiables
- All UI drawn in **Pygame only** — no tkinter, no curses, no browser
- Story content is **never hardcoded** in Python — always loaded from `story.json`
- Game must run with `python main.py` and no extra setup beyond `pip install pygame`
- Code must be split across the file structure above — no monolithic single-file builds
- Agent must **run the game after each major step** and fix any runtime errors before proceeding
