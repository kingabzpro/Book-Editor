import json
import os
from typing import Any, Dict, List, Tuple
import numpy as np
import faiss
from .utils import ensure_dir

def index_paths(index_dir: str) -> Tuple[str, str]:
    return (
        os.path.join(index_dir, "faiss.index"),
        os.path.join(index_dir, "meta.json"),
    )

def save_index(index_dir: str, index: faiss.Index, meta: List[Dict[str, Any]]) -> None:
    ensure_dir(index_dir)
    index_path, meta_path = index_paths(index_dir)
    faiss.write_index(index, index_path)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

def load_index(index_dir: str) -> Tuple[faiss.Index, List[Dict[str, Any]]]:
    index_path, meta_path = index_paths(index_dir)
    if not os.path.exists(index_path) or not os.path.exists(meta_path):
        raise FileNotFoundError(f"Index not found in {index_dir}. Run: index first.")
    index = faiss.read_index(index_path)
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    return index, meta

def build_ip_index(embs: np.ndarray) -> faiss.Index:
    """
    Inner-product index (use with normalized vectors = cosine similarity)
    """
    dim = embs.shape[1]
    idx = faiss.IndexFlatIP(dim)
    idx.add(embs)
    return idx
