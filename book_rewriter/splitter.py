import re
from typing import Dict, List, Tuple

CHAPTER_HEADING_RE = re.compile(
    r"^\s*(chapter|ch)\s+(\d+)\s*(?:[:.\-–—]\s*)?(.*\S)?\s*$",
    re.IGNORECASE
)

TOC_LINE_RE = re.compile(
    r"^\s*(chapter|ch)\s+\d+\s*[:.\-–—]?\s*.*?\.{5,}\s*\d+\s*$",
    re.IGNORECASE
)

HEADING_STYLES = {"Heading 1", "Heading 2"}

def is_toc_line(text: str) -> bool:
    return bool(TOC_LINE_RE.match(text.strip()))

def is_chapter_heading(style: str, text: str) -> bool:
    if style in HEADING_STYLES:
        # Some books use Heading 1 for the chapter title; still avoid TOC lines.
        return not is_toc_line(text)
    if is_toc_line(text):
        return False
    return bool(CHAPTER_HEADING_RE.match(text.strip()))

def parse_chapter_title(text: str) -> str:
    t = text.strip()
    m = CHAPTER_HEADING_RE.match(t)
    if not m:
        return t
    num = m.group(2)
    title = (m.group(3) or "").strip()
    return f"Chapter {num}: {title}" if title else f"Chapter {num}"

def split_into_chapters(paras: List[Tuple[str, str]]) -> List[Dict]:
    """
    Returns [{"title": str, "paras": [str]}]
    Ignores TOC dot-leader lines.
    """
    chapters: List[Dict] = []
    current = {"title": "Front Matter", "paras": []}

    def push():
        nonlocal current
        if current["paras"]:
            chapters.append(current)
        current = {"title": "Untitled", "paras": []}

    for style, txt in paras:
        if is_toc_line(txt):
            continue
        if is_chapter_heading(style, txt):
            push()
            current["title"] = parse_chapter_title(txt)
        else:
            current["paras"].append(txt)

    push()
    if not chapters:
        return [{"title": "Full Book", "paras": [t for _, t in paras]}]
    return chapters
