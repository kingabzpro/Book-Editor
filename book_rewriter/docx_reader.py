from typing import List, Tuple
from docx import Document
from .utils import normalize_text

def read_docx_paragraphs(docx_path: str) -> List[Tuple[str, str]]:
    """
    Returns [(style_name, text)] for non-empty paragraphs.
    """
    doc = Document(docx_path)
    out: List[Tuple[str, str]] = []
    for p in doc.paragraphs:
        txt = normalize_text(p.text)
        if not txt:
            continue
        style = p.style.name if p.style else "Normal"
        out.append((style, txt))
    return out
