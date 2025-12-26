from typing import List
import numpy as np
from mistralai import Mistral
from tenacity import retry, wait_exponential, stop_after_attempt

# Safe defaults (tune if needed)
DEFAULT_BATCH_SIZE = 32

@retry(wait=wait_exponential(min=1, max=20), stop=stop_after_attempt(5))
def _embed_batch(client: Mistral, model: str, batch: List[str]) -> np.ndarray:
    resp = client.embeddings.create(model=model, inputs=batch)
    return np.array([row.embedding for row in resp.data], dtype=np.float32)

def embed_texts_mistral(
    api_key: str,
    model: str,
    texts: List[str],
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> np.ndarray:
    """
    Returns float32 array shape (N, D).
    Splits requests into batches to avoid 'Too many tokens overall'.
    """
    if not texts:
        return np.zeros((0, 0), dtype=np.float32)

    client = Mistral(api_key=api_key)

    all_embs: List[np.ndarray] = []
    i = 0
    n = len(texts)

    while i < n:
        batch = texts[i : i + batch_size]
        try:
            embs = _embed_batch(client, model, batch)
            all_embs.append(embs)
            i += batch_size
        except Exception as e:
            # If even a small batch fails due to token limits, reduce batch size dynamically.
            if batch_size <= 4:
                raise
            batch_size = max(4, batch_size // 2)

    return np.vstack(all_embs)

def l2_normalize(embs: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(embs, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return embs / norms
