from typing import Any, Dict, List
import logging
import os
import numpy as np

from .config import Settings

log = logging.getLogger("book-rewriter")
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
    log.info("Reading DOCX paragraphs...")
    paras = read_docx_paragraphs(docx_path)
    log.info(f"Found {len(paras)} paragraphs, splitting into chapters...")
    chapters = split_into_chapters(paras)
    log.info(f"Found {len(chapters)} chapters")

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
    log.info(f"Creating {len(texts)} chunks for embedding...")

    log.info(f"Generating embeddings ({s.mistral_embed_model})...")
    embs = embed_texts_mistral(s.mistral_api_key, s.mistral_embed_model, texts)
    embs = l2_normalize(embs).astype(np.float32)
    log.info("Embeddings generated, building FAISS index...")

    index = build_ip_index(embs)
    save_index(s.index_dir, index, meta)
    log.info("Index saved.")

    return {
        "chunks_indexed": len(meta),
        "chapters_detected": len(set(m["chapter_idx"] for m in meta)),
        "index_dir": s.index_dir,
    }

def retrieve(query: str, s: Settings, k: int | None = None) -> List[Dict[str, Any]]:
    index, meta = load_index(s.index_dir)
    k = k or s.top_k

    log.debug(f"Embedding query: {query[:50]}...")
    q_emb = embed_texts_mistral(s.mistral_api_key, s.mistral_embed_model, [query])
    q_emb = l2_normalize(q_emb).astype(np.float32)

    log.debug("Searching index...")
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

def create_book_bible(s: Settings, out_path: str = "book_bible.md", docx_path: str | None = None) -> str:
    log.info("Creating Book Bible from chapter text...")

    # Need the DOCX path - try to find it from config or require it
    if not docx_path:
        # Try to find DOCX in Book/ directory
        import glob
        docx_files = glob.glob("Book/*.docx")
        if not docx_files:
            raise ValueError("No DOCX file found. Please specify --docx or place .docx in Book/")
        docx_path = docx_files[0]
        log.info(f"Using DOCX: {docx_path}")

    # Get full chapter text directly (not from index)
    log.info("Reading chapters from DOCX...")
    chapters = export_chapter_text(docx_path, s)
    log.info(f"Found {len(chapters)} chapters")

    # Prepare excerpts with full chapter text
    excerpts = []
    for ch in chapters:
        text = ch["text"][:3000] if len(ch["text"]) > 3000 else ch["text"]  # Limit per chapter
        excerpts.append(
            f"---\nCHAPTER {ch['chapter_idx']}: {ch['title']}\n{text}\n"
        )

    user_prompt = BOOK_BIBLE_USER_TEMPLATE.format(excerpts="".join(excerpts))
    log.info("Sending to LLM for bible generation...")
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
    docx_path: str | None = None,
) -> str:
    log.info(f"Loading book bible from: {book_bible_path}")
    with open(book_bible_path, "r", encoding="utf-8") as f:
        bible = f.read()

    # Find DOCX path
    if not docx_path:
        import glob
        docx_files = glob.glob("Book/*.docx")
        if docx_files:
            docx_path = docx_files[0]
            log.info(f"Using DOCX: {docx_path}")

    # Get FULL chapter text from DOCX (not chunks)
    log.info(f"Getting full chapter {chapter_idx} text from DOCX...")
    all_chapters = export_chapter_text(docx_path, s)

    # Find the target chapter
    target_ch = next((ch for ch in all_chapters if ch["chapter_idx"] == chapter_idx), None)
    if not target_ch:
        raise ValueError(f"Chapter {chapter_idx} not found in DOCX")

    chapter_title = target_ch["title"]
    full_text = target_ch["text"]
    log.info(f"Chapter {chapter_idx} has {len(full_text)} characters")

    # Get nearby chapter context for continuity (from vector store)
    log.info(f"Retrieving context from nearby chapters...")
    nearby_hits = []
    for offset in [-1, 0, 1]:
        ch = chapter_idx + offset
        if ch >= 0:
            for hit in retrieve(f"chapter {ch} plot events", s, k=5):
                if int(hit["chapter_idx"]) == ch:
                    nearby_hits.append(hit)

    nearby_excerpts = []
    for h in nearby_hits[:8]:
        nearby_excerpts.append(
            f"[Chapter {h['chapter_idx']} context]\n{h['text'][:500]}\n"
        )

    chapter_excerpts = f"""FULL CHAPTER TEXT TO REWRITE (Chapter {chapter_idx}: {chapter_title}):

{full_text}

CONTINUITY CONTEXT FROM NEARBY CHAPTERS:
{"".join(nearby_excerpts)}
"""

    user_prompt = REWRITE_USER_TEMPLATE.format(
        book_bible=bible,
        chapter_title=chapter_title,
        chapter_excerpts=chapter_excerpts,
    )

    log.info("Sending to LLM for chapter rewrite...")
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

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(rewritten)

    return out_path
