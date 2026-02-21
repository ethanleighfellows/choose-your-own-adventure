#!/usr/bin/env python3
"""Extract page-by-page text from a PDF into raw_text.txt."""

from pathlib import Path

import pdfplumber


PDF_PATH = Path("storyfiles/book.pdf")
OUT_PATH = Path("raw_text.txt")


def main() -> None:
    if not PDF_PATH.exists():
        raise FileNotFoundError(f"Missing PDF at {PDF_PATH}")

    page_count = 0
    with pdfplumber.open(PDF_PATH) as pdf:
        with OUT_PATH.open("w", encoding="utf-8") as out:
            for i, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                out.write(f"--- PAGE {i} ---\n")
                out.write(text.strip())
                out.write("\n\n")
                page_count += 1

    print(f"Extracted {page_count} pages to {OUT_PATH}")


if __name__ == "__main__":
    main()
