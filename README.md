# Choose Your Own Adventure (CYOA) - Python Engine & Pipeline

This project is an experimental toolset designed to test the feasibility of converting classic "Choose Your Own Adventure" books into interactive, data-driven Python games. It features a complete pipeline for extracting story data from PDFs and a retro-styled game engine built with Pygame.

## Project Goal

The primary objective is to automate the transition from printed media (PDFs) to a playable digital format. This involves:
1. **OCR/Extraction**: Pulling raw text from page-oriented PDFs.
2. **Parsing**: Identifying story sections, branching choices, and destination links using regex-based heuristics.
3. **Data Synthesis**: Cleaning text, repairing broken links, and generating thematic ASCII art to create a structured `story.json`.
4. **Gameplay**: Providing a robust engine to play these stories with added RPG elements like stat management and random events.

## Features

- **Retro CRT Aesthetic**: Inspired by *The Oregon Trail (1985)*, featuring green-on-black text, scanlines, and ASCII art panels.
- **Typewriter Rendering**: Dynamic text delivery with sound effects and punctuation pauses.
- **Data-Driven Engine**: The game engine is entirely decoupled from the story content. Swap `story.json` to play a completely different adventure.
- **Stat System**: Tracks Health, Food, Gold, and Morale, which can influence available choices and trigger random events.
- **Save/Load System**: Persistent game state stored in `save.dat`.
- **Automated Pipeline**: Tools to handle the "heavy lifting" of story conversion.

## Conversion Pipeline

If you have a CYOA book in PDF format:

1. **Extract**: Run `python extract.py` to convert `storyfiles/book.pdf` into `raw_text.txt`.
2. **Parse**: Run `python parse.py` to identify sections and choices, outputting `parsed_sections.json`.
3. **Build**: Run `python build_story.py` to clean the narrative, generate ASCII art, and produce the final `story.json`.
4. **Validate**: Run `python validate.py` to ensure the story graph is traversable and free of dead ends.

## Requirements

- Python 3.11+
- `pdfplumber` (for extraction)
- `pygame` (for the game engine)

```bash
pip install pygame pdfplumber
```

## Running the Game

Simply run the entry point:

```bash
python main.py
```

### Controls
- **Arrow Keys / Mouse**: Navigate menus and choices.
- **1-4**: Quick-select choices.
- **ENTER / SPACE**: Confirm selection or skip typewriter animation.
- **S**: Save game.
- **J**: Open Journal (view path history).
- **L**: Load game (from Main Menu).

---

*This project is for educational and experimental purposes, exploring the intersection of legacy print media and modern interactive software.*
