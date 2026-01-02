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
    EDIT_SYSTEM,
    EDIT_USER_TEMPLATE,
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

def edit_chapter(
    chapter_path: str,
    edit_request: str,
    s: Settings,
    book_bible_path: str = "book_bible.md",
    out_path: str = "",
) -> str:
    """
    Apply a specific edit request to an existing rewritten chapter.

    Usage:
    - Fill gaps: "Add more sensory detail to the cabin scene"
    - Fix pacing: "Slow down the confrontation between Simon and Gene"
    - Add content: "Include Jacob's POV at the end of this chapter"
    - Fix issues: "Remove the em-dash usage and contractions"
    - Change tone: "Make this scene more tense and claustrophobic"
    """
    log.info(f"Loading book bible from: {book_bible_path}")
    with open(book_bible_path, "r", encoding="utf-8") as f:
        bible = f.read()

    log.info(f"Loading chapter from: {chapter_path}")
    with open(chapter_path, "r", encoding="utf-8") as f:
        original_chapter = f.read()

    # Extract chapter title from the markdown
    import re
    title_match = re.search(r"^##\s+(.+)$", original_chapter, re.MULTILINE)
    chapter_title = title_match.group(1) if title_match else "Unknown Chapter"

    user_prompt = EDIT_USER_TEMPLATE.format(
        book_bible=bible,
        original_chapter=original_chapter,
        edit_request=edit_request,
    )

    log.info(f"Applying edit: {edit_request[:50]}...")
    edited = kimi_chat(
        api_key=s.nebius_api_key,
        base_url=s.nebius_base_url,
        model=s.kimi_model,
        system_prompt=EDIT_SYSTEM,
        user_text=user_prompt,
        temperature=0.4,
    )

    if not out_path:
        # Preserve original filename
        out_path = chapter_path

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(edited)

    log.info(f"Edited chapter saved to: {out_path}")
    return out_path

def batch_rewrite_chapters(
    start_chapter: int,
    end_chapter: int,
    s: Settings,
    book_bible_path: str = "book_bible.md",
    docx_path: str | None = None,
    out_dir: str = "rewrites",
) -> List[str]:
    """
    Rewrite multiple chapters in batch from start_chapter to end_chapter (inclusive).

    Args:
        start_chapter: Starting chapter number (1-based, e.g., 1 for Chapter 1)
        end_chapter: Ending chapter number (1-based, inclusive)
        s: Settings object
        book_bible_path: Path to the book bible file
        docx_path: Path to the DOCX file (optional, will auto-detect if not provided)
        out_dir: Output directory for rewritten chapters

    Returns:
        List of output file paths for the rewritten chapters
    """
    log.info(f"Batch rewriting chapters {start_chapter} to {end_chapter}...")

    # Convert 1-based to 0-based indices
    start_idx = start_chapter - 1
    end_idx = end_chapter - 1

    # Validate range
    if start_idx < 0 or end_idx < start_idx:
        raise ValueError(f"Invalid chapter range: {start_chapter} to {end_chapter}")

    # Find DOCX path
    if not docx_path:
        import glob
        docx_files = glob.glob("Book/*.docx")
        if not docx_files:
            raise ValueError("No DOCX file found. Please specify docx_path or place .docx in Book/")
        docx_path = docx_files[0]
        log.info(f"Using DOCX: {docx_path}")

    # Get all chapters to validate the range
    all_chapters = export_chapter_text(docx_path, s)
    max_chapter = len(all_chapters)

    if end_idx >= max_chapter:
        raise ValueError(f"End chapter {end_chapter} exceeds available chapters ({max_chapter})")

    # Load bible once
    log.info(f"Loading book bible from: {book_bible_path}")
    with open(book_bible_path, "r", encoding="utf-8") as f:
        bible = f.read()

    output_paths = []

    # Rewrite each chapter in sequence
    for chapter_idx in range(start_idx, end_idx + 1):
        chapter_num = chapter_idx + 1  # Convert back to 1-based for display
        log.info(f"Rewriting chapter {chapter_num}/{end_chapter} (index {chapter_idx})...")

        target_ch = all_chapters[chapter_idx]
        chapter_title = target_ch["title"]
        full_text = target_ch["text"]
        log.info(f"Chapter {chapter_num} has {len(full_text)} characters")

        # Get nearby chapter context for continuity (from vector store)
        log.info(f"Retrieving context from nearby chapters...")
        nearby_hits = []
        for offset in [-1, 0, 1]:
            ch = chapter_idx + offset
            if ch >= 0 and ch < max_chapter:
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

        # Generate output path preserving original chapter index
        out_path = f"{out_dir}/chapter_{chapter_idx:02d}.md"
        os.makedirs(os.path.dirname(out_path), exist_ok=True)

        with open(out_path, "w", encoding="utf-8") as f:
            f.write(rewritten)

        output_paths.append(out_path)
        log.info(f"Chapter {chapter_num} rewrite saved to: {out_path}")

    log.info(f"Batch rewrite complete: {len(output_paths)} chapters processed")
    return output_paths

def rewrite_all_chapters(
    s: Settings,
    book_bible_path: str = "book_bible.md",
    docx_path: str | None = None,
    out_dir: str = "rewrites",
    turns: int = 1,
) -> Dict[str, Any]:
    """
    Rewrite all chapters in the book at once.

    Args:
        s: Settings object
        book_bible_path: Path to the book bible file
        docx_path: Path to the DOCX file (optional, will auto-detect if not provided)
        out_dir: Output directory for rewritten chapters
        turns: Number of rewrite passes (1 = single-turn, >1 = multi-turn refinement)

    Returns:
        Dictionary with output paths, turn count, and chapter count
    """
    log.info(f"Rewriting ALL chapters with {turns} turn(s)...")

    # Find DOCX path
    if not docx_path:
        import glob
        docx_files = glob.glob("Book/*.docx")
        if not docx_files:
            raise ValueError("No DOCX file found. Please specify docx_path or place .docx in Book/")
        docx_path = docx_files[0]
        log.info(f"Using DOCX: {docx_path}")

    # Get all chapters
    all_chapters = export_chapter_text(docx_path, s)
    total_chapters = len(all_chapters)
    log.info(f"Found {total_chapters} chapters to rewrite")

    # Load bible once
    log.info(f"Loading book bible from: {book_bible_path}")
    with open(book_bible_path, "r", encoding="utf-8") as f:
        bible = f.read()

    output_paths = {}
    current_sources = {ch["chapter_idx"]: ch["text"] for ch in all_chapters}

    # Multi-turn processing
    for turn in range(1, turns + 1):
        log.info(f"=== Turn {turn}/{turns} ===")
        turn_output_paths = []

        for chapter_idx in range(total_chapters):
            chapter_num = chapter_idx + 1
            log.info(f"Rewriting chapter {chapter_num}/{total_chapters} (index {chapter_idx}, turn {turn}/{turns})...")

            target_ch = all_chapters[chapter_idx]
            chapter_title = target_ch["title"]

            # Use the most recent version for this chapter
            full_text = current_sources[chapter_idx]
            log.info(f"Chapter {chapter_num} has {len(full_text)} characters")

            # Get nearby chapter context for continuity (from vector store)
            log.info(f"Retrieving context from nearby chapters...")
            nearby_hits = []
            for offset in [-1, 0, 1]:
                ch = chapter_idx + offset
                if ch >= 0 and ch < total_chapters:
                    for hit in retrieve(f"chapter {ch} plot events", s, k=5):
                        if int(hit["chapter_idx"]) == ch:
                            nearby_hits.append(hit)

            nearby_excerpts = []
            for h in nearby_hits[:8]:
                nearby_excerpts.append(
                    f"[Chapter {h['chapter_idx']} context]\n{h['text'][:500]}\n"
                )

            # Adjust prompt for multi-turn
            if turn > 1:
                turn_instruction = f"\n\nThis is TURN {turn} of {turns}. Refine and improve the previous rewrite while maintaining consistency with the book bible and overall story arc."
            else:
                turn_instruction = ""

            chapter_excerpts = f"""FULL CHAPTER TEXT TO REWRITE (Chapter {chapter_idx}: {chapter_title}):

{full_text}
{turn_instruction}

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

            # Generate output path
            if turns > 1:
                out_path = f"{out_dir}/chapter_{chapter_idx:02d}_turn{turn:02d}.md"
            else:
                out_path = f"{out_dir}/chapter_{chapter_idx:02d}.md"

            os.makedirs(os.path.dirname(out_path), exist_ok=True)

            with open(out_path, "w", encoding="utf-8") as f:
                f.write(rewritten)

            # Update current source for next turn
            current_sources[chapter_idx] = rewritten
            turn_output_paths.append(out_path)
            log.info(f"Chapter {chapter_num} (turn {turn}) saved to: {out_path}")

        # Also save a consolidated version after each turn
        if turns > 1:
            consolidated_path = f"{out_dir}/all_chapters_turn{turn:02d}_consolidated.md"
            with open(consolidated_path, "w", encoding="utf-8") as f:
                for chapter_idx in range(total_chapters):
                    chapter_path = f"{out_dir}/chapter_{chapter_idx:02d}_turn{turn:02d}.md"
                    with open(chapter_path, "r", encoding="utf-8") as ch:
                        f.write(ch.read())
                        f.write("\n\n---\n\n")
            log.info(f"Consolidated all chapters for turn {turn} to: {consolidated_path}")

        log.info(f"Turn {turn}/{turns} complete: {len(turn_output_paths)} chapters rewritten")
        output_paths[f"turn_{turn}"] = turn_output_paths

    # Final consolidation
    if turns == 1:
        consolidated_path = f"{out_dir}/all_chapters_consolidated.md"
        with open(consolidated_path, "w", encoding="utf-8") as f:
            for chapter_idx in range(total_chapters):
                chapter_path = f"{out_dir}/chapter_{chapter_idx:02d}.md"
                with open(chapter_path, "r", encoding="utf-8") as ch:
                    f.write(ch.read())
                    f.write("\n\n---\n\n")
        log.info(f"Final consolidated book saved to: {consolidated_path}")

    log.info(f"=== All chapters rewritten successfully ({turns} turn(s), {total_chapters} chapters) ===")

    return {
        "output_paths": output_paths,
        "turns": turns,
        "total_chapters": total_chapters,
        "docx_path": docx_path,
    }
