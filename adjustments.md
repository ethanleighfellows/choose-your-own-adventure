# adjustments.md

## Overall Assessment
- Production Ready: No
- Risk Level: High
- Confidence Level: High

The codebase has a functional vertical slice, but it is not production-safe due to a critical save-file deserialization vulnerability and multiple reliability/performance gaps. Core gameplay, rendering, and state transitions work, but data quality and runtime hardening are insufficient for production-bound deployment. Story content integrity is currently weak (high OCR noise, duplicates, and low reachability), which materially impacts user experience and maintainability. Concurrency and race-condition risks are low in the current single-threaded architecture.

## Action Items (Prioritized)

1. ### [Severity: Critical] Replace Unsafe Pickle Deserialization for Save Loading

**Problem**  
`game.py` uses `pickle.load()` directly on `save.dat` (`game.py:219-220`). This allows arbitrary code execution if a crafted save file is loaded.

**Impact**  
Loading an untrusted or tampered save file can execute attacker-controlled code on the user’s machine.

**Required Fix**  
Replace save format with JSON (or another safe serialization format), enforce strict schema validation, and reject unknown fields/types.

**Suggested Implementation (if helpful)**  
Use `json.dumps/json.loads` with a typed validator (manual or pydantic-like model) and parse only primitive fields (`player`, `current_node_id`, `visited_node_ids`, `journal_entries`).

**Fix Applied**  
Replaced `pickle` save/load in `game.py` with JSON parsing and strict payload validation (`_validate_save_payload`). Unknown fields and invalid types are now rejected before state mutation.

---

2. ### [Severity: Major] Make Save Writes Atomic and Failure-Tolerant

**Problem**  
`_save_game()` writes directly to `save.dat` without atomic replacement or error handling (`game.py:210-213`).

**Impact**  
Process interruption or I/O failures can corrupt saves permanently; users can lose progress.

**Required Fix**  
Write to a temp file in the same directory and atomically replace (`os.replace`) only after successful flush/sync. Add `try/except OSError` and surface non-blocking UI error feedback.

**Suggested Implementation (if helpful)**  
`save.dat.tmp` -> `fsync` -> `os.replace(tmp, save.dat)`.

**Fix Applied**  
`_save_game()` now writes JSON to `save.dat.tmp`, flushes + `fsync`s, then atomically swaps via `os.replace`. Write failures are caught and surfaced in UI overlay.

---

3. ### [Severity: Major] Validate Choice Destination Before Applying Effects/Upkeep

**Problem**  
In `_activate_choice()`, choice effects and upkeep are applied before verifying `next` target validity (`game.py:282-289`). Invalid targets silently mutate state and can leave progression inconsistent.

**Impact**  
Malformed story data causes stat loss without movement, or unintended fallback behavior on next load path.

**Required Fix**  
Validate destination exists before applying any gameplay mutations. If invalid, block activation and display an explicit error overlay.

**Suggested Implementation (if helpful)**  
Check `self.story.node_exists(next_id)` first; return with `"Invalid story link"` message if false.

**Fix Applied**  
`_activate_choice()` now validates `next` destination existence before applying choice effects/upkeep. Invalid links are blocked with an explicit overlay message and border flash.

---

4. ### [Severity: Major] Remove Silent Fallback to Entry Node on Missing Node IDs

**Problem**  
`_set_current_node()` falls back to entry node when the node ID is missing (`game.py:167-170`), masking data defects.

**Impact**  
Broken story links silently teleport players to the start and hide content regressions in production.

**Required Fix**  
Fail fast: return error status/raise controlled exception and route to a recoverable error screen, not entry-node fallback.

**Suggested Implementation (if helpful)**  
Return `False` for missing node IDs and transition to a “Story Data Error” state with restart/load options.

**Fix Applied**  
`_set_current_node()` now returns `False` on missing nodes and no longer falls back to entry. Runtime transitions route such failures to a dedicated `data_error` state/screen.

---

5. ### [Severity: Major] Handle `normal` Nodes With Zero Choices to Prevent Softlocks

**Problem**  
`_resolve_terminal_node()` only handles ending node types and health-zero; malformed `normal` nodes with no choices are not resolved (`game.py:315-324`).

**Impact**  
Users can become stuck on a node with no actionable inputs and no state transition.

**Required Fix**  
Normalize such nodes at load time (convert to `ending_neutral`) or handle at runtime by forcing game-over/victory resolution with explicit messaging.

**Suggested Implementation (if helpful)**  
At story normalization phase, if `node_type == "normal"` and `choices == []`, convert to `ending_neutral`.

**Fix Applied**  
Added normalization in `story.py` to convert `normal` nodes with zero choices into `ending_neutral`, and runtime fallback in `_resolve_terminal_node()` for defensive handling.

---

6. ### [Severity: Major] Reduce Per-Frame Allocation and Render Overhead

**Problem**  
`Renderer.draw()` allocates new full-screen surfaces each frame (`renderer.py:146`, `renderer.py:165`) and renders ASCII art character-by-character (400+ glyph renders per frame, `renderer.py:216-224`).

**Impact**  
Higher CPU/GPU cost, unstable frame pacing on lower-end hardware, and unnecessary GC pressure.

**Required Fix**  
Pre-allocate reusable frame/fade surfaces and cache rendered ASCII node art surfaces by node ID.

**Suggested Implementation (if helpful)**  
Maintain `self.frame_surface`, `self.fade_surface`, and `self.node_art_cache[node_id]`.

**Fix Applied**  
`renderer.py` now reuses preallocated frame/fade surfaces, caches wrapped text, and caches rendered ASCII node art surfaces to reduce per-frame allocations and glyph rendering cost.

---

7. ### [Severity: Major] Fix Audio Asset Format Mismatch for Ambient Track

**Problem**  
`assets/sounds/ambient.ogg` contains WAV/RIFF data (misnamed extension), which is non-portable and backend-dependent.

**Impact**  
Ambient audio may fail to load on systems requiring valid OGG decoding; behavior differs by platform/driver.

**Required Fix**  
Provide a real OGG file (or remove fake OGG and load WAV explicitly). Align loader behavior with actual file formats.

**Suggested Implementation (if helpful)**  
Delete fake `ambient.ogg`; keep `ambient.wav`; in `AudioManager`, load `ambient.wav` first or based on MIME/decoder support.

**Fix Applied**  
`AudioManager` now prefers `ambient.wav`, validates file headers (`RIFF` for WAV, `OggS` for OGG), and rejects mismatched assets instead of loading them opportunistically.

---

8. ### [Severity: Major] Add Story Content Quality Gate for Reachability and Duplicates

**Problem**  
`story.json` has severe OCR corruption, duplicate choices, and low reachability from entry (`section_3` reaches only 8/47 nodes).

**Impact**  
Players encounter incoherent text, redundant options, and inaccessible content; future content updates become error-prone.

**Required Fix**  
Add a content-lint step that rejects duplicate choices per node, enforces minimum reachability thresholds, and flags high-noise OCR artifacts.

**Suggested Implementation (if helpful)**  
Build `lint_story.py` to enforce: unique `(normalized_choice_text, next)` pairs, reachable-node ratio threshold, max garbage-character ratio.

**Fix Applied**  
Added `lint_story.py` quality gate with duplicate-choice detection, reachability threshold, and OCR-noise threshold checks. Applied `--fix` to remove duplicate choices from `story.json` and `storyfiles/book_story.json`.

---

9. ### [Severity: Major] Bound Journal/Path History Growth

**Problem**  
`visited_node_ids` and `journal_entries` grow unbounded for long sessions (`game.py:173-175` append path).

**Impact**  
Long-run memory growth and degraded journal rendering performance.

**Required Fix**  
Introduce a cap (ring buffer) or archival strategy for journal history.

**Suggested Implementation (if helpful)**  
Keep last N entries (e.g., 500) and summarize older history into a compact count entry.

**Fix Applied**  
Added bounded history (`JOURNAL_LIMIT = 500`) and centralized visit append/clamping logic to prevent unbounded growth of journal/path structures.

---

10. ### [Severity: Minor] Render Menu-Level Overlay Messages

**Problem**  
Menu frame includes `event_text` (`game.py:533`), but `renderer.py` menu path never renders it.

**Impact**  
Load/save failure feedback is invisible in menu flows.

**Required Fix**  
Display `event_text` overlay in `_draw_main_menu()` consistent with gameplay overlay style.

**Suggested Implementation (if helpful)**  
Reuse existing overlay box rendering helper for menu scene.

**Fix Applied**  
Implemented shared overlay-box rendering helper in `renderer.py` and enabled `event_text` rendering on the main menu screen.

---

11. ### [Severity: Minor] Correct Journal Scroll Clamping Logic

**Problem**  
Journal scroll upper bound is clamped to `len(entries)-1` (`game.py:419`) instead of `len(entries)-visible_lines`.

**Impact**  
Users can scroll into mostly empty journal pages.

**Required Fix**  
Clamp scroll based on computed renderable line capacity for the journal panel.

**Suggested Implementation (if helpful)**  
`max_scroll = max(0, len(entries) - max_lines)` and clamp to `[0, max_scroll]`.

**Fix Applied**  
Added `Renderer.journal_max_visible_lines()` and clamped journal scroll against `len(entries) - max_visible_lines` in gameplay logic.

---

12. ### [Severity: Minor] Remove Dead/Unused Code Paths and Stale Process Metadata

**Problem**  
Unused symbols (`ui.py:103 format_choices`, `renderer.py:49 self.char_h`) and stale process state in `progress.md` (“No issues logged”) reduce maintainability.

**Impact**  
Increases cognitive load, hides true risk status, and encourages drift between implementation and operational documentation.

**Required Fix**  
Delete unused code, or wire it into active paths; keep `progress.md` issue log synchronized with actual defects.

**Suggested Implementation (if helpful)**  
Enable lint checks (`ruff/flake8`) with dead-code rules and require CI failure on stale issue states.

**Fix Applied**  
Removed unused `ui.format_choices` and unused `renderer` char-height state, and updated engineering tracking to reflect this remediation pass.

---

## Testing Gaps
- No automated tests for save/load schema validation and malformed save recovery.
- No security test ensuring untrusted save files are rejected safely.
- No tests for invalid/missing `next` choice destinations.
- No tests for `normal` node with zero choices (softlock prevention).
- No tests for random event application boundaries and deterministic reproducibility.
- No tests for journal scroll clamping and max-history behavior.
- No renderer performance regression tests (frame-time budget, allocation counts).
- No audio compatibility tests verifying format/decoder correctness across platforms.
- No story content lint tests for reachability, duplicate choices, or OCR-noise thresholds.

## Scalability & Performance Concerns
- Per-frame surface allocations in renderer increase GC pressure and frame jitter.
- Character-by-character ASCII rendering every frame is expensive; should be cached per node.
- Text wrapping is recomputed repeatedly for unchanged text; cache wrapped lines by `(text,width,font)`.
- Unbounded journal/path lists can grow indefinitely in long sessions.
- No profiling hooks/metrics to track frame time, audio init latency, or memory growth over extended play.

## UI & UX Issues (Prioritized)

13. ### [Severity: Major] Fix Text Wrapping and Overflow in Story Panels

**Problem**  
The story text panel does not correctly wrap text within its ASCII borders. Text frequently overflows the panel boundaries or becomes unreadable when the content exceeds the available vertical space.

**Impact**  
Narrative content is cut off or visually glitched, breaking immersion and making the game unplayable for longer sections.

**Required Fix**  
Implement a robust word-wrapping algorithm that respects panel padding and borders. Add support for scrollable text or pagination within the story panel when content exceeds the fixed height.

---

14. ### [Severity: Major] Extract and Display Descriptive Choice Labels

**Problem**  
In-game choices are often displayed with generic labels like "proceed to section X" instead of the actual descriptive text from the book (e.g., "If you want to open the door, turn to 42").

**Impact**  
Players lose the context of their decisions, reducing the game to a random number selection rather than a narrative experience.

**Required Fix**  
Improve the NLP/regex heuristics in `parse.py` and `build_story.py` to better capture the descriptive sentences preceding the page numbers and use them as choice labels.

---

## Security Review
- Input validation issues: Save payload structure/type validation is weak; malformed data can enter runtime paths.
- Injection risks: `pickle.load()` on save file is a direct code-execution vector.
- Authentication/authorization concerns: No issues found.
- Secrets handling problems: No issues found.
