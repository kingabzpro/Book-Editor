from typing import List
import numpy as np
from mistralai import Mistral
from tenacity import retry, wait_exponential, stop_after_attempt

@retry(wait=wait_exponential(min=1, max=20), stop=stop_after_attempt(5))
def embed_texts_mistral(api_key: str, model: str, texts: List[str]) -> np.ndarray:
    """
    Returns float32 array shape (N, D)
    """
    client = Mistral(api_key=api_key)
    resp = client.embeddings.create(model=model, inputs=texts)
    embs = np.array([row.embedding for row in resp.data], dtype=np.float32)
    return embs

def l2_normalize(embs: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(embs, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return embs / norms
