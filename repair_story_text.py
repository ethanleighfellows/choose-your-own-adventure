#!/usr/bin/env python3
"""Rebuild story JSON from PDF text with OCR cleanup and playable links."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from pypdf import PdfReader


PDF_PATH = Path("storyfiles/book.pdf")
STORY_PATH = Path("story.json")
BACKUP_STORY_PATH = Path("storyfiles/book_story.json")
LINK_REPORT_PATH = Path("link_report.txt")

VALID_NODE_TYPES = {"normal", "ending_win", "ending_death", "ending_neutral"}
NOISE_SYMBOL_RE = re.compile(r"[\\/_=~`|<>]{3,}")
PAGE_NUMBER_RE = re.compile(r"^[^A-Za-z0-9]*\d{1,3}[^A-Za-z0-9]*$")

# Keep this regex aligned with cleanup so extracted sentences are removable from prose.
CHOICE_SENTENCE_RE = re.compile(
    r"(?is)("
    r"(?:(?:if|when|should|decide|step|wiser|wait|you|you're|to|go)\b[^.!?\n]{0,350}?)?"
    r"\b(?:turn|go|proceed|continue|head|page|section|p\.|pg\.)\b"
    r"[^.!?\n]{0,80}?"
    r"([0-9A-Za-z]{1,5})"
    r"[^.!?\n]{0,100}[.!?]?"
    r")"
)

DIGIT_OCR_MAP = {
    "O": "0",
    "o": "0",
    "I": "1",
    "l": "1",
    "S": "5",
    "s": "5",
    "B": "8",
    "g": "9",
    "q": "9",
    "H": "7",
    "h": "7",
}


def fit40(text: str) -> str:
    text = text[:40]
    if len(text) < 40:
        text += " " * (40 - len(text))
    return text


def centered(text: str, width: int = 38) -> str:
    text = text[:width]
    if len(text) < width:
        left = (width - len(text)) // 2
        right = width - len(text) - left
        return (" " * left) + text + (" " * right)
    return text


def normalize_text(raw: str) -> str:
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("—", "-")
    text = text.replace("–", "-")
    text = text.replace("“", '"').replace("”", '"')
    text = text.replace("’", "'").replace("‘", "'")
    text = text.replace("\u00ad", "")
    text = text.replace("_", " ")

    # OCR sometimes splits page numbers like "page 1 8".
    text = re.sub(r"(?i)(page|section)\s+(\d)\s+(\d)\b", r"\1 \2\3", text)
    text = re.sub(r"(?i)(page|section)\s+(\d)\s+(\d)\s+(\d)\b", r"\1 \2\3\4", text)
    return text


def token_to_int(token: str) -> int | None:
    if token.isdigit():
        return int(token)
    chars: list[str] = []
    for char in token:
        if char.isdigit():
            chars.append(char)
        elif char in DIGIT_OCR_MAP:
            chars.append(DIGIT_OCR_MAP[char])
        else:
            return None
    if not chars:
        return None
    return int("".join(chars))


def looks_like_section_header(page_text: str) -> bool:
    lines = [ln.strip() for ln in page_text.splitlines() if ln.strip()]
    for line in lines[:4]:
        stripped = re.sub(r"^[^0-9A-Za-z]+|[^0-9A-Za-z]+$", "", line)
        if not stripped:
            continue
        if re.fullmatch(r"\d{1,3}", stripped):
            return True
        if re.fullmatch(r"\d{1,3}\s+\d{1,3}", stripped):
            return True
        if re.match(r"^\d{1,3}\b", stripped) and len(stripped.split()) <= 3:
            return True
    return False


def is_noise_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if PAGE_NUMBER_RE.fullmatch(stripped):
        return True
    if NOISE_SYMBOL_RE.search(stripped):
        return True

    non_space = len(stripped.replace(" ", ""))
    if non_space == 0:
        return True
    alpha = sum(1 for char in stripped if char.isalpha())
    alpha_ratio = alpha / non_space

    if len(stripped) >= 10 and alpha_ratio < 0.28:
        return True

    words = re.findall(r"[A-Za-z]+", stripped)
    if len(words) >= 6:
        singles = sum(1 for word in words if len(word) == 1)
        if singles / len(words) > 0.55:
            return True
        avg_len = sum(len(word) for word in words) / len(words)
        vowelish = sum(1 for word in words if any(ch in "aeiouAEIOU" for ch in word))
        if avg_len < 3.2 and vowelish / len(words) < 0.65:
            return True
        caps = sum(1 for word in words if word.isupper())
        if caps / len(words) > 0.7 and vowelish / len(words) < 0.7:
            return True

    punctuation = sum(1 for char in stripped if not char.isalnum() and not char.isspace())
    if punctuation / max(1, len(stripped)) > 0.25 and alpha_ratio < 0.55:
        return True

    return False


def clean_choice_label(label: str, destination: int) -> str:
    text = normalize_text(label)
    text = re.sub(r"\s+", " ", text).strip(" -_~")
    text = re.sub(r"\s+([,.!?;:])", r"\1", text)
    text = re.sub(r"(?i)\bpage\b", "section", text)
    text = re.sub(
        r"(?i)\b(section)\s+[0-9A-Za-z]{1,5}\b",
        f"section {destination}",
        text,
    )

    if text and text[0].islower():
        text = text[0].upper() + text[1:]

    alpha = sum(1 for char in text if char.isalpha())
    if alpha < 6 or len(text) < 8:
        text = f"Go to section {destination}."

    if len(text) > 60:
        text = text[:57].rstrip() + "..."
    return text


def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def extract_choices(raw_text: str) -> list[tuple[str, int]]:
    text = normalize_ws(normalize_text(raw_text))
    found: list[tuple[str, int]] = []
    seen_dest: set[int] = set()

    for match in CHOICE_SENTENCE_RE.finditer(text):
        sentence = match.group(1).strip()
        token = match.group(2).strip()
        destination = token_to_int(token)
        if destination is None or not (1 <= destination <= 500):
            continue
        if destination in seen_dest:
            continue
        seen_dest.add(destination)
        found.append((clean_choice_label(sentence, destination), destination))
        if len(found) >= 4:
            break

    return found


def remove_choice_sentences(text: str) -> str:
    return CHOICE_SENTENCE_RE.sub(" ", text)


def page_text(reader: PdfReader, section_number: int) -> str:
    page_index = section_number + 9
    if page_index < 0 or page_index >= len(reader.pages):
        return ""
    return reader.pages[page_index].extract_text() or ""


def has_usable_page(reader: PdfReader, section_number: int) -> bool:
    text = page_text(reader, section_number)
    if not text.strip():
        return False
    alpha = sum(1 for char in text if char.isalpha())
    return alpha >= 80


def clean_prose(raw_text: str, section_number: int, fallback: str = "") -> str:
    if not raw_text.strip():
        fb = normalize_text(fallback).strip()
        return fb if fb else f"[Section {section_number} - not found in source]"

    text = normalize_text(raw_text)
    text = remove_choice_sentences(text)
    text = re.sub(r"([A-Za-z])-\n([A-Za-z])", r"\1\2", text)

    filtered_lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            filtered_lines.append("")
            continue

        stripped = re.sub(r"^[^A-Za-z]*\d{1,3}\b[^A-Za-z]*", "", stripped).strip()
        if not stripped:
            continue
        if is_noise_line(stripped):
            continue

        filtered_lines.append(stripped)

    paragraphs: list[str] = []
    current: list[str] = []
    for line in filtered_lines:
        if not line:
            if current:
                paragraphs.append(" ".join(current))
                current = []
            continue
        current.append(line)
    if current:
        paragraphs.append(" ".join(current))

    cleaned_paragraphs: list[str] = []
    for paragraph in paragraphs:
        paragraph = re.sub(r"\s+", " ", paragraph).strip()
        paragraph = re.sub(r"\s+([,.!?;:])", r"\1", paragraph)
        paragraph = paragraph.strip(" -")
        if paragraph:
            cleaned_paragraphs.append(paragraph)

    cleaned = "\n\n".join(cleaned_paragraphs).strip()
    fallback_norm = normalize_text(fallback).strip()
    if not cleaned:
        return fallback_norm if fallback_norm else f"[Section {section_number} - not found in source]"
    return cleaned


def infer_title(section_number: int, text: str) -> str:
    lower = text.lower()
    if "dragon" in lower:
        return "Dragon Trail" if "trail" in lower else "Dragon Encounter"
    if "forbidden castle" in lower:
        return "Toward Forbidden Castle"
    if any(word in lower for word in ("forest", "woods", "tree", "wolves")):
        return "Forest Road"
    if any(word in lower for word in ("cave", "cavern", "tunnel")):
        return "Cave Passage"
    if any(word in lower for word in ("king", "court", "castle", "dungeon", "guard")):
        return "Court And Castle"
    if any(word in lower for word in ("stream", "river", "waterfall", "lake", "water")):
        return "Crossing The Water"
    if any(word in lower for word in ("mountain", "trail", "ridge", "climb")):
        return "Mountain Ascent"
    if "the end" in lower:
        return "Journey's End"
    return f"Section {section_number}"


def scene_kind(text: str) -> str:
    lower = text.lower()
    if any(word in lower for word in ("forest", "woods", "tree", "wolves")):
        return "forest"
    if any(word in lower for word in ("cave", "cavern", "tunnel", "dungeon")):
        return "cave"
    if any(word in lower for word in ("river", "stream", "lake", "water", "waterfall")):
        return "water"
    if any(word in lower for word in ("field", "meadow", "pasture", "plain")):
        return "field"
    if any(word in lower for word in ("castle", "court", "hall", "tower", "room", "village")):
        return "building"
    return "default"


def generate_ascii_art(text: str, title: str) -> list[str]:
    kind = scene_kind(text)

    if kind == "forest":
        rows = [
            "┌──────────────────────────────────────┐",
            "│ ▲   ▲    ▲   ▲▲   ▲    ▲   ▲▲   ▲   │",
            "│ │   │    │   ││   │    │   ││   │   │",
            "│ │ ▲ │ ▲  │ ▲ ││ ▲ │ ▲  │ ▲ ││ ▲ │   │",
            "│ │ │ │ │  │ │ ││ │ │ │  │ │ ││ │ │   │",
            "│ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   │",
            "│         Forest trail ahead           │",
            "│ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   │",
            "│   ▲▲       ▲▲       ▲▲       ▲▲      │",
            "└──────────────────────────────────────┘",
        ]
    elif kind == "cave":
        rows = [
            "┌──────────────────────────────────────┐",
            "│▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓│",
            "│▓░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░▓│",
            "│▓░  █▄   █▄    ▓    ▄█   ▄█   ░░░░░░▓│",
            "│▓░ ▄██▄ ▄██▄   ▓   ▄██▄ ▄██▄  ░░░░░░▓│",
            "│▓░░░░░░░░░░░  ●  ░░░░░░░░░░░░░░░░░░▓│",
            "│▓░░░░░░░ Dark cavern path ░░░░░░░░░░▓│",
            "│▓░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░▓│",
            "│▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓│",
            "└──────────────────────────────────────┘",
        ]
    elif kind == "building":
        rows = [
            "┌──────────────────────────────────────┐",
            "│┌───────────┐      ┌───────────┐      │",
            "││ █ █ █ █ █ │      │ █ █ █ █ █ │      │",
            "││           │      │           │      │",
            "│├──────┬────┤  ●   ├──────┬────┤      │",
            "││      │    │      │      │    │      │",
            "││      │    │      │      │    │      │",
            "│└──────┴────┘      └──────┴────┘      │",
            "│        Stone halls and towers         │",
            "└──────────────────────────────────────┘",
        ]
    elif kind == "water":
        rows = [
            "┌──────────────────────────────────────┐",
            "│≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈│",
            "│~~~~~~≈~~~~~~≈~~~~~~≈~~~~~~≈~~~~~~≈~~│",
            "│≈~~~~~≈~~~~~~≈~~~~~~≈~~~~~~≈~~~~~~≈~~│",
            "│~~~~~~≈~~~  ● drifting onward ~~~~≈~~~│",
            "│≈~~~~~≈~~~~~~≈~~~~~~≈~~~~~~≈~~~~~~≈~~│",
            "│~~~~~~≈~~~~~~≈~~~~~~≈~~~~~~≈~~~~~~≈~~│",
            "│≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈│",
            "│         Water stretches ahead         │",
            "└──────────────────────────────────────┘",
        ]
    elif kind == "field":
        rows = [
            "┌──────────────────────────────────────┐",
            "│──────────────────────────────────────│",
            "│░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░│",
            "│──────────────────────────────────────│",
            "│░░░░░░░░░░░░░░░░●░░░░░░░░░░░░░░░░░░░│",
            "│──────────────────────────────────────│",
            "│░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░│",
            "│──────────────────────────────────────│",
            "│         Open ground and sky           │",
            "└──────────────────────────────────────┘",
        ]
    else:
        label = centered(title.upper()[:24], 38)
        rows = [
            "┌──────────────────────────────────────┐",
            "│                                      │",
            "│                                      │",
            "│                                      │",
            f"│{label}│",
            "│                                      │",
            "│                                      │",
            "│                                      │",
            "│                 ●                    │",
            "└──────────────────────────────────────┘",
        ]

    return [fit40(row) for row in rows[:10]]


def infer_node_type(text: str, has_choices: bool) -> str:
    if has_choices:
        return "normal"

    lower = text.lower()
    death_terms = (
        "death",
        "die",
        "dead",
        "killed",
        "execution",
        "burn",
        "collapse",
        "you don't",
        "too late",
        "never seen again",
        "won't be",
    )
    win_terms = (
        "victory",
        "you survive",
        "you return",
        "back in your own time",
        "you are free",
        "you find the forbidden castle",
        "worth the trip",
    )

    if any(term in lower for term in death_terms):
        return "ending_death"
    if any(term in lower for term in win_terms):
        return "ending_win"
    return "ending_neutral"


def extract_existing_destinations(node: dict[str, Any] | None) -> list[int]:
    if not node:
        return []
    destinations: list[int] = []
    for choice in node.get("choices", []):
        if not isinstance(choice, dict):
            continue
        next_id = str(choice.get("next", ""))
        if next_id.startswith("section_") and next_id.split("_")[-1].isdigit():
            destination = int(next_id.split("_")[-1])
            if destination not in destinations:
                destinations.append(destination)
    return destinations[:4]


def extract_section_payload(
    reader: PdfReader,
    section_number: int,
    existing_node: dict[str, Any] | None,
) -> dict[str, Any]:
    raw_main = page_text(reader, section_number)
    existing_text = str(existing_node.get("text", "")) if existing_node else ""

    combined_raw = normalize_text(raw_main)
    choices = extract_choices(combined_raw)

    if combined_raw.strip():
        # Pull in continuation pages when this page seems truncated and lacks choices.
        for step in (1, 2):
            if choices:
                break
            if "the end" in combined_raw.lower():
                break
            continuation_raw = page_text(reader, section_number + step)
            if not continuation_raw.strip():
                break
            if looks_like_section_header(continuation_raw):
                break

            combined_raw = combined_raw + "\n" + normalize_text(continuation_raw)
            updated_choices = extract_choices(combined_raw)
            if updated_choices:
                choices = updated_choices

    cleaned_text = clean_prose(combined_raw, section_number, fallback=existing_text)

    if not choices:
        fallback_destinations = extract_existing_destinations(existing_node)
        if fallback_destinations and "the end" not in cleaned_text.lower():
            choices = [(f"Go to section {dest}.", dest) for dest in fallback_destinations[:4]]

    title = infer_title(section_number, cleaned_text)
    node_type = infer_node_type(cleaned_text, has_choices=bool(choices))

    choice_rows = []
    for label, destination in choices[:4]:
        choice_rows.append(
            {
                "text": clean_choice_label(label, destination),
                "destination": destination,
                "requires": {},
                "effects": {},
            }
        )

    return {
        "section_number": section_number,
        "title": title,
        "text": cleaned_text,
        "node_type": node_type,
        "choices": choice_rows,
    }


def build_story() -> tuple[list[dict[str, Any]], list[str]]:
    if not PDF_PATH.exists():
        raise FileNotFoundError(f"Missing PDF source: {PDF_PATH}")
    if not STORY_PATH.exists():
        raise FileNotFoundError(f"Missing story source: {STORY_PATH}")

    existing_data: Any = json.loads(STORY_PATH.read_text(encoding="utf-8"))
    if not isinstance(existing_data, list):
        raise ValueError("story.json must be a JSON array")

    existing_by_section: dict[int, dict[str, Any]] = {}
    for node in existing_data:
        if not isinstance(node, dict):
            continue
        section_number = node.get("section_number")
        try:
            section_int = int(section_number)
        except (TypeError, ValueError):
            continue
        existing_by_section[section_int] = node

    reader = PdfReader(str(PDF_PATH))

    seed_sections = set(existing_by_section)
    if has_usable_page(reader, 1):
        seed_sections.add(1)

    queue = sorted(seed_sections)
    parsed: dict[int, dict[str, Any]] = {}

    # Expand reachable sections from current content plus section 1.
    while queue and len(parsed) < 200:
        section_number = queue.pop(0)
        if section_number in parsed:
            continue

        payload = extract_section_payload(reader, section_number, existing_by_section.get(section_number))
        parsed[section_number] = payload

        for choice in payload["choices"]:
            destination = int(choice["destination"])
            if destination in parsed:
                continue
            if destination in queue:
                continue
            if destination in existing_by_section or has_usable_page(reader, destination):
                queue.append(destination)

    link_changes: list[str] = []

    # Add directly extractable missing destinations before remapping/stubbing.
    while True:
        missing = sorted(
            {
                int(choice["destination"])
                for node in parsed.values()
                for choice in node["choices"]
                if int(choice["destination"]) not in parsed
            }
        )
        if not missing:
            break

        added_any = False
        for destination in missing:
            if has_usable_page(reader, destination):
                parsed[destination] = extract_section_payload(
                    reader,
                    destination,
                    existing_by_section.get(destination),
                )
                link_changes.append(f"Added missing destination section {destination} from PDF source.")
                added_any = True
        if not added_any:
            break

    # Resolve remaining broken links by nearest remap (±2), else create stub endings.
    existing_sections = set(parsed)
    for node in sorted(parsed.values(), key=lambda item: item["section_number"]):
        for choice in node["choices"]:
            destination = int(choice["destination"])
            if destination in existing_sections:
                continue

            near = [num for num in existing_sections if abs(num - destination) <= 2]
            if near:
                remap = sorted(near, key=lambda value: (abs(value - destination), value))[0]
                choice["destination"] = remap
                link_changes.append(
                    f"Remapped missing destination {destination} -> {remap} "
                    f"(from section {node['section_number']})."
                )
                continue

            parsed[destination] = {
                "section_number": destination,
                "title": f"Section {destination}",
                "text": f"[Section {destination} - not found in source]",
                "node_type": "ending_neutral",
                "choices": [],
            }
            existing_sections.add(destination)
            link_changes.append(
                f"Created stub section {destination} (referenced by section {node['section_number']})."
            )

    nodes: list[dict[str, Any]] = []
    for section_number in sorted(parsed):
        payload = parsed[section_number]

        choices = [
            {
                "text": str(choice["text"])[:60],
                "next": f"section_{int(choice['destination'])}",
                "requires": choice.get("requires", {}) if isinstance(choice.get("requires"), dict) else {},
                "effects": choice.get("effects", {}) if isinstance(choice.get("effects"), dict) else {},
            }
            for choice in payload.get("choices", [])[:4]
        ]

        node_type = str(payload.get("node_type", "normal"))
        if node_type not in VALID_NODE_TYPES:
            node_type = infer_node_type(str(payload.get("text", "")), bool(choices))
        if choices:
            node_type = "normal"

        title = str(payload.get("title", f"Section {section_number}")).strip() or f"Section {section_number}"
        text = str(payload.get("text", "")).strip() or f"[Section {section_number} - not found in source]"

        node = {
            "id": f"section_{section_number}",
            "section_number": section_number,
            "title": title,
            "text": text,
            "ascii_art": generate_ascii_art(text, title),
            "node_type": node_type,
            "choices": choices,
            "effects": {},
            "random_event_pool": [],
        }
        nodes.append(node)

    nodes.sort(key=lambda node: node["section_number"])
    if any(node["section_number"] == 1 for node in nodes):
        nodes.sort(key=lambda node: (node["section_number"] != 1, node["section_number"]))

    # Ensure at least one win ending for runtime requirements.
    if not any(node["node_type"] == "ending_win" for node in nodes):
        for node in nodes:
            if node["node_type"] == "ending_neutral" and "the end" in node["text"].lower():
                if any(term in node["text"].lower() for term in ("return", "survive", "find", "worth")):
                    node["node_type"] = "ending_win"
                    break
        if not any(node["node_type"] == "ending_win" for node in nodes):
            for node in nodes:
                if node["node_type"] == "ending_neutral":
                    node["node_type"] = "ending_win"
                    break

    return nodes, link_changes


def write_story(nodes: list[dict[str, Any]]) -> None:
    STORY_PATH.write_text(json.dumps(nodes, indent=2, ensure_ascii=False), encoding="utf-8")
    if BACKUP_STORY_PATH.exists():
        BACKUP_STORY_PATH.write_text(json.dumps(nodes, indent=2, ensure_ascii=False), encoding="utf-8")


def write_link_report(changes: list[str]) -> None:
    if changes:
        LINK_REPORT_PATH.write_text("\n".join(changes) + "\n", encoding="utf-8")
    else:
        LINK_REPORT_PATH.write_text("No broken links found.\n", encoding="utf-8")


def main() -> None:
    nodes, changes = build_story()
    write_story(nodes)
    write_link_report(changes)
    print(f"Rebuilt story with {len(nodes)} nodes.")
    print(f"Link changes logged: {len(changes)}")


if __name__ == "__main__":
    main()
