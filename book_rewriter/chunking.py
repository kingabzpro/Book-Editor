from typing import List
from .utils import normalize_text

def chunk_text(text: str, target_chars: int, overlap_chars: int) -> List[str]:
    text = normalize_text(text)
    if len(text) <= target_chars:
        return [text]

    chunks: List[str] = []
    start = 0
    n = len(text)

    while start < n:
        end = min(n, start + target_chars)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= n:
            break
        start = max(0, end - overlap_chars)

    return chunks
