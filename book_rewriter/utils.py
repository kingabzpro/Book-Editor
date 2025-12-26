import os
import re
from typing import Iterable, List

def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

def normalize_text(s: str) -> str:
    s = (s or "").replace("\u00a0", " ").strip()
    s = re.sub(r"[ \t]+", " ", s)
    return s

def join_paras(paras: Iterable[str]) -> str:
    # Preserve paragraph breaks as newlines (helps LLM keep rhythm)
    return "\n".join(p.strip() for p in paras if p.strip())

def clamp(n: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, n))
