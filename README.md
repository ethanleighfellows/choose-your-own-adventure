# Choose Your Own Adventure Game (Pygame)

Quickstart guide to install and run the game, then load a save.

## Requirements

- Python 3.11+ (3.13 also works)
- `pip`

## 1) Install dependency

```bash
python3 -m pip install pygame
```

## 2) Run the game

From the project root:

```bash
python3 main.py
```

## 3) Start or load

At the main menu:

- `NEW GAME`: start a fresh run
- `LOAD GAME`: load from `save.dat`
- `QUIT`: exit

You can also press:

- `L` on the main menu to load
- `ENTER` to confirm the selected menu option
- Arrow keys or mouse to select menu items

## 4) Save during gameplay

While in-game, press:

- `S` to save to `save.dat`
- `J` to open/close journal
- `1-4` or arrow keys + `ENTER` to choose options
- `SPACE`/`ENTER` to skip typewriter text

## Quick smoke test (optional)

Headless smoke run (useful to verify setup):

```bash
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python3 main.py --smoke --frames 320 --autoplay
```

## Notes

- Story content is loaded from `story.json`.
- If `save.dat` is missing or invalid, loading is safely rejected and you can start a new game.
