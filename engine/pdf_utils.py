"""
PDF handling: extracting full text and isolating the Item 3 section.
"""

import re
from typing import Optional, Union
from io import BytesIO

import pdfplumber


def extract_pdf_text(pdf_source: Union[str, BytesIO]) -> str:
    """Extract all text from a PDF, given a file path or an in-memory file object."""
    text_parts = []
    with pdfplumber.open(pdf_source) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            text_parts.append(page_text)
    return "\n".join(text_parts)


def isolate_item3(full_text: str) -> Optional[str]:
    """
    Attempt to isolate the Item 3 section from full FDD text by finding the
    heading for Item 3 and cutting off at the heading for Item 4.

    Returns None if no Item 3 heading could be found at all.
    """
    # Anchored to the start of a line, AND requiring the item's actual title
    # word to follow closely, not just the item number. This fixes two
    # distinct false-match sources found in real FDDs:
    #   - "Item 3" mentioned mid-sentence (e.g. a cross-reference elsewhere)
    #   - a state addendum that says "Item 3 of the Disclosure Document is
    #     amended by adding..." — this also sits at the start of a line, so
    #     the line-start anchor alone doesn't exclude it, but it's never
    #     followed by the word "LITIGATION", so requiring that word does.
    # A little whitespace tolerance (\s*) lets "LITIGATION" appear right after
    # the number, on the next line, or separated by a dash/colon — real FDDs
    # format this heading several different ways ("ITEM 3 LITIGATION",
    # "ITEM 3. LITIGATION", "ITEM 3 – LITIGATION", "ITEM 3:\nLITIGATION").
    # \s* can only skip whitespace, so it still can't skip over an addendum's
    # unrelated sentence text the way a plain "match anything nearby" would.
    item3_pattern = re.compile(r"^[ \t]*ITEM\s*3\s*[.\-\u2013\u2014:]?\s*LITIGATION\b", re.IGNORECASE | re.MULTILINE)
    item4_pattern = re.compile(r"^[ \t]*ITEM\s*4\s*[.\-\u2013\u2014:]?\s*BANKRUPTCY\b", re.IGNORECASE | re.MULTILINE)

    matches3 = list(item3_pattern.finditer(full_text))
    matches4 = list(item4_pattern.finditer(full_text))

    if not matches3:
        return None

    # A table of contents often lists "ITEM 3" before the real section does.
    # Prefer the later match as the actual section start when there's more than one.
    start = matches3[-1].start() if len(matches3) > 1 else matches3[0].start()

    end = None
    for m in matches4:
        if m.start() > start:
            end = m.start()
            break

    if end is None:
        end = start + 8000  # generous fallback window

    section = full_text[start:end].strip()
    return section if section else None
