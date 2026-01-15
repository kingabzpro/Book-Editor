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
ALT_CHAPTER_TITLES = {"prologue", "epilogue"}

def is_toc_line(text: str) -> bool:
    return bool(TOC_LINE_RE.match(text.strip()))

def is_chapter_heading(style: str, text: str) -> bool:
    if is_toc_line(text):
        return False
    t = text.strip()
    if style in HEADING_STYLES:
        if CHAPTER_HEADING_RE.match(t):
            return True
        return t.lower() in ALT_CHAPTER_TITLES
    return bool(CHAPTER_HEADING_RE.match(t))

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
    seen_chapter = False

    def push():
        nonlocal current
        if current["paras"]:
            if not seen_chapter and current["title"] == "Front Matter":
                current = {"title": "Untitled", "paras": []}
                return
            chapters.append(current)
        current = {"title": "Untitled", "paras": []}

    for style, txt in paras:
        if is_toc_line(txt):
            continue
        if is_chapter_heading(style, txt):
            push()
            seen_chapter = True
            current["title"] = parse_chapter_title(txt)
        else:
            if style in HEADING_STYLES:
                current["paras"].append(f"### {txt.strip()}")
            else:
                current["paras"].append(txt)

    push()
    if not chapters:
        return [{"title": "Full Book", "paras": [t for _, t in paras]}]
    return chapters
