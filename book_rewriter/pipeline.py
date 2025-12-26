from dataclasses import asdict
from typing import Any, Dict, List, Tuple
import numpy as np

from .config import Settings
from .docx_reader import read_docx_paragraphs
from .splitter import split_into_chapters
from .chunking import chunk_text
from .utils import join_paras
from .embeddings_mistral import embed_texts_mistral, l2_normalize
from .faiss_store import build_ip_index, save_index, load_index
from .kimi_client import kimi_chat
from .prompts import (
    BOOK_BIBLE_SYSTEM,
    BOOK_BIBLE_USER_TEMPLATE,
    REWRITE_SYSTEM,
    REWRITE_USER_TEMPLATE,
)

def build_chunks(docx_path: str, s: Settings) -> List[Dict[str, Any]]:
    paras = read_docx_paragraphs(docx_path)
    chapters = split_into_chapters(paras)

    meta: List[Dict[str, Any]] = []
    chunk_id = 0

    for chapter_idx, ch in enumerate(chapters):
        full_text = join_paras(ch["paras"])
        if not full_text.strip():
            continue

        chunks = chunk_text(full_text, s.chunk_char_target, s.chunk_char_overlap)
        for chunk_idx, text in enumerate(chunks):
            meta.append({
                "chunk_id": chunk_id,
                "chapter_idx": chapter_idx,
                "chapter_title": ch["title"],
                "chunk_idx_in_chapter": chunk_idx,
                "text": text,
            })
            chunk_id += 1

    if not meta:
        raise ValueError("No chunks produced. Check DOCX parsing and chapter splitting.")
    return meta

def index_book(docx_path: str, s: Settings) -> Dict[str, Any]:
    meta = build_chunks(docx_path, s)
    texts = [m["text"] for m in meta]

    embs = embed_texts_mistral(s.mistral_api_key, s.mistral_embed_model, texts)
    embs = l2_normalize(embs).astype(np.float32)

    index = build_ip_index(embs)
    save_index(s.index_dir, index, meta)

    return {
        "chunks_indexed": len(meta),
        "chapters_detected": len(set(m["chapter_idx"] for m in meta)),
        "index_dir": s.index_dir,
    }

def retrieve(query: str, s: Settings, k: int | None = None) -> List[Dict[str, Any]]:
    index, meta = load_index(s.index_dir)
    k = k or s.top_k

    q_emb = embed_texts_mistral(s.mistral_api_key, s.mistral_embed_model, [query])
    q_emb = l2_normalize(q_emb).astype(np.float32)

    scores, ids = index.search(q_emb, k)
    out: List[Dict[str, Any]] = []
    for score, idx in zip(scores[0], ids[0]):
        if idx < 0:
            continue
        item = dict(meta[idx])
        item["score"] = float(score)
        out.append(item)
    return out

def export_chapter_text(docx_path: str, s: Settings) -> List[Dict[str, Any]]:
    """
    Exports exact chapter text (no retrieval) to help you validate splits.
    """
    paras = read_docx_paragraphs(docx_path)
    chapters = split_into_chapters(paras)
    exported = []
    for i, ch in enumerate(chapters):
        exported.append({
            "chapter_idx": i,
            "title": ch["title"],
            "text": join_paras(ch["paras"]),
        })
    return exported

def create_book_bible(s: Settings, out_path: str = "book_bible.md") -> str:
    # Multi-query retrieval so the bible sees broad coverage.
    queries = [
        "Summarize overall plot (beginning middle end) and turning points",
        "List main characters with motivations, secrets, and arcs",
        "Identify timeline, locations, continuity constraints",
        "Identify themes, tone, POV/tense, style patterns",
        "Identify biggest problems: pacing clarity stakes inconsistencies",
    ]

    seen = set()
    gathered: List[Dict[str, Any]] = []
    for q in queries:
        for hit in retrieve(q, s, k=12):
            cid = hit["chunk_id"]
            if cid in seen:
                continue
            seen.add(cid)
            gathered.append(hit)

    # Keep bounded
    gathered = sorted(gathered, key=lambda x: x["score"], reverse=True)[:32]

    excerpts = []
    for h in gathered:
        excerpts.append(
            f"---\nCHAPTER {h['chapter_idx']}: {h['chapter_title']}\n"
            f"CHUNK {h['chunk_idx_in_chapter']}\n{h['text']}\n"
        )

    user_prompt = BOOK_BIBLE_USER_TEMPLATE.format(excerpts="".join(excerpts))
    bible = kimi_chat(
        api_key=s.nebius_api_key,
        base_url=s.nebius_base_url,
        model=s.kimi_model,
        system_prompt=BOOK_BIBLE_SYSTEM,
        user_text=user_prompt,
        temperature=0.3,
    )

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(bible)

    return out_path

def rewrite_chapter(
    chapter_idx: int,
    s: Settings,
    book_bible_path: str = "book_bible.md",
    out_path: str = "",
) -> str:
    with open(book_bible_path, "r", encoding="utf-8") as f:
        bible = f.read()

    # Retrieve chunk context around this chapter + neighbors for continuity
    hits = retrieve(f"Chapter {chapter_idx} content details", s, k=24)
    filtered = [h for h in hits if abs(int(h["chapter_idx"]) - chapter_idx) <= 1]
    selected = (filtered or hits)[:14]

    selected = sorted(selected, key=lambda x: (x["chapter_idx"], x["chunk_idx_in_chapter"]))
    chapter_title = selected[0]["chapter_title"] if selected else f"Chapter {chapter_idx}"

    chapter_excerpts = []
    for h in selected:
        chapter_excerpts.append(
            f"---\nCHAPTER {h['chapter_idx']}: {h['chapter_title']}\n"
            f"CHUNK {h['chunk_idx_in_chapter']}\n{h['text']}\n"
        )

    user_prompt = REWRITE_USER_TEMPLATE.format(
        book_bible=bible,
        chapter_title=chapter_title,
        chapter_excerpts="".join(chapter_excerpts),
    )

    rewritten = kimi_chat(
        api_key=s.nebius_api_key,
        base_url=s.nebius_base_url,
        model=s.kimi_model,
        system_prompt=REWRITE_SYSTEM,
        user_text=user_prompt,
        temperature=0.5,
    )

    if not out_path:
        out_path = f"rewrites/chapter_{chapter_idx:02d}.md"

    import os
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(rewritten)

    return out_path
