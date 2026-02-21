# CYOA Game — Design Language

> This document is the source of truth for all visual and UX decisions.
> The agent must consult this before writing any rendering, UI, or layout code.
> Do not deviate from these specs without explicit instruction.

---

## Colour Palette

| Role | Hex | Usage |
|---|---|---|
| Background | `#0A0A0A` | Window fill, panel fill |
| Primary Text | `#39FF14` | All story text, menu text |
| Dim Text | `#1A7A08` | Inactive choices, stat labels |
| Highlight | `#FFFFFF` | Hovered/selected choice |
| Danger | `#FF3131` | Health low warning, death screen |
| Gold Accent | `#FFD700` | Gold stat, victory screen |
| Panel Border | `#39FF14` | All double-line ASCII borders |
| Scanline | `#000000` at 15% alpha | Overlay on all panels |

---

## Typography

- **Primary font**: `Press Start 2P` (load from `assets/fonts/`)
- **Fallback font**: `Courier New`, monospace system font
- **Body text size**: 10pt
- **Title/header size**: 16pt
- **Line height**: 1.6× font height
- **Letter spacing**: 0 (default)
- All text is **left-aligned** inside panels with 12px padding

---

## Layout (800 × 600 window, fixed size)

┌─────────────────────────────────────────────┐│  STAT BAR  Name HP:■■■■░  Food:■■░  Gold:■│  Height: 36px├─────────────────────────────────────────────┤│                                             ││           ASCII SCENE ART PANEL             │  Height: 160px│                                             │├─────────────────────────────────────────────┤│                                             ││           STORY TEXT PANEL                  │  Height: 240px│  (scrollable, typewriter render)            ││                                             │├─────────────────────────────────────────────┤│   Choice text here                       ││   Choice text here                       │  Height: 128px│   Choice text here (locked)              ││   Choice text here                       │└─────────────────────────────────────────────┘Total: 800 × 600 (no resizing)


---

## Panels

### All panels share:
- Black fill `#0A0A0A`
- Double-line ASCII border: `╔ ╗ ╚ ╝ ║ ═`
- Border colour: `#39FF14`
- Inner padding: 12px on all sides
- Scanline overlay rendered on top of content

### Stat Bar
- Single-line panel at top, no border box — just a horizontal rule `═` below it
- Stats rendered as: `HP: ■■■■░░░░░░` (filled/unfilled block chars based on value ÷ 10)
- Player name left-aligned, stats right-aligned

### Scene Art Panel
- Fixed-width ASCII art (40 chars wide × 10 rows)
- Centred horizontally in panel
- Rendered in `#39FF14`, dim `#1A7A08` for depth/shadow chars

### Story Text Panel
- Word-wrapped to panel inner width
- Typewriter effect: render one character every 30ms
- Player can press **SPACE** or **ENTER** to skip typewriter and show full text instantly
- After text completes, a blinking `▶` cursor appears bottom-right

### Choice Panel
- Each choice on its own line prefixed with `[1]`, `[2]`, etc.
- Default state: `#1A7A08` (dim green)
- Hovered state: `#FFFFFF` with `>` prefix replacing `[N]`
- Locked/unavailable choice: `#333333` with `[✗]` prefix and greyed text
- Selected choice: brief flash to `#39FF14` then transition

---

## Effects & Animation

### Typewriter Effect
- Render characters from story text one at a time
- Delay: 30ms per character
- Play a soft "clack" sound (`assets/sounds/click.wav`) every 3rd character
- Punctuation (`.`, `!`, `?`) adds an extra 200ms pause

### Screen Transitions
- **Node transition**: fade to black over 300ms, fade in new node over 300ms
- **Game over**: screen shake (±4px, 8 frames) then red tint fade in
- **Victory**: gold pulse effect on background (alpha sine wave)

### CRT Scanline Overlay
- Draw horizontal lines every 2 pixels across the entire window
- Each line: black fill at 15% alpha (use a pre-rendered surface for performance)
- Render scanlines **after** all other content so they sit on top

### Random Event Flash
- When a random event fires, briefly flash the border colour to `#FF3131` for 500ms
- Display event text in a centred overlay box with its own border

---

## Sound Design

| Sound | File | Trigger |
|---|---|---|
| Keyclick | `click.wav` | Every 3rd typewriter character |
| Choice select | `select.wav` | Player confirms a choice |
| Danger sting | `danger.wav` | Health < 20 or random bad event |
| Ambient loop | `ambient.ogg` | Looping background during gameplay |
| Victory fanfare | `victory.wav` | Win screen |
| Death sound | `death.wav` | Game over screen |

All audio loaded with `pygame.mixer`. Ambient loop at 40% volume. SFX at 80% volume.

---

## Main Menu
- Full-screen ASCII title art centred vertically (generate art for the game's title)
- Blinking `▶` cursor next to active menu item
- Arrow keys or mouse to navigate, ENTER to select
- Version number bottom-right in dim text

## Do Not
- Do not use any non-monospace fonts
- Do not use rounded rectangles or any non-ASCII border shapes
- Do not use colour fills other than those in the palette
- Do not animate anything faster than 30fps
- Do not render text outside of its designated panel
