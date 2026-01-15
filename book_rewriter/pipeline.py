from typing import Any, Dict, List
import logging
import os
import json
import datetime
import re
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
from .sambanova_client import sambanova_chat_simple
from .prompts import (
    BOOK_BIBLE_SYSTEM,
    BOOK_BIBLE_USER_TEMPLATE,
    REWRITE_SYSTEM,
    REWRITE_USER_TEMPLATE,
    EDIT_SYSTEM,
    EDIT_USER_TEMPLATE,
    GRAMMAR_BASELINE_SYSTEM,
    GRAMMAR_BASELINE_USER_TEMPLATE,
    FILL_GAPS_SYSTEM,
    FILL_GAPS_USER_TEMPLATE,
    FINAL_DRAFT_SYSTEM,
    FINAL_DRAFT_USER_TEMPLATE,
)


def _slugify(value: str) -> str:
    text = (value or "").strip().lower().replace("_", " ")
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"-{2,}", "-", text)
    return text.strip("-") or "unknown-book"


def _apply_front_matter(text: str, book_slug: str, title: str, order: int) -> str:
    front_matter = (
        "---\n"
        f"book: \"{book_slug}\"\n"
        f"title: \"{title}\"\n"
        f"order: {order}\n"
        "---\n"
    )
    # Remove leading chapter heading if present; front matter already carries title.
    cleaned = text
    if cleaned.lstrip().startswith("---\n"):
        parts = text.split("---\n", 2)
        if len(parts) >= 3:
            cleaned = parts[2].lstrip("\n")
    lines = cleaned.splitlines()
    if lines and lines[0].strip().startswith("## "):
        cleaned = "\n".join(lines[1:]).lstrip("\n")
    return front_matter + "\n" + cleaned

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

def _load_chapters_from_metadata(s: Settings) -> List[Dict[str, Any]]:
    """
    Load chapters from vector store metadata (much faster than reading DOCX).

    Args:
        s: Settings object with index_dir path

    Returns:
        List of chapters with full reconstructed text
    """
    import json
    import os

    meta_path = os.path.join(s.index_dir, "meta.json")
    if not os.path.exists(meta_path):
        raise FileNotFoundError(f"Vector store metadata not found at {meta_path}. Run 'index' command first.")

    with open(meta_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    # Group chunks by chapter and reconstruct full text
    chapters = {}
    for chunk in chunks:
        idx = chunk["chapter_idx"]
        if idx not in chapters:
            chapters[idx] = {
                "chapter_idx": idx,
                "title": chunk["chapter_title"],
                "chunks": []
            }
        chapters[idx]["chunks"].append(chunk)

    # Sort chunks within each chapter and reconstruct text
    result = []
    for idx in sorted(chapters.keys()):
        ch = chapters[idx]
        # Sort by chunk_idx_in_chapter
        ch["chunks"].sort(key=lambda x: x["chunk_idx_in_chapter"])

        # Reconstruct full text by joining chunk texts
        # Note: chunks overlap, so we need to deduplicate properly
        # For now, just concatenate - small overlaps are acceptable for LLM context
        full_text = "\n\n".join([c["text"] for c in ch["chunks"]])

        result.append({
            "chapter_idx": idx,
            "title": ch["title"],
            "text": full_text
        })

    return result


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

def create_book_bible(
    s: Settings,
    out_path: str = "book_bible.md",
    docx_path: str | None = None,
    book_title: str | None = None,
) -> str:
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

    title_hint = f"CURRENT WORKING TITLE: {book_title}\n\n" if book_title else ""
    user_prompt = title_hint + BOOK_BIBLE_USER_TEMPLATE.format(
        excerpts="".join(excerpts)
    )
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

    order = chapter_idx + 1
    book_slug = _slugify(getattr(s, "book_name", ""))
    rewritten = _apply_front_matter(rewritten, book_slug, chapter_title, order)

    if not out_path:
        out_path = f"rewrites/chapter-{order:02d}.md"

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(rewritten)

    return out_path


def _save_progress(progress_path: str, last_completed: int) -> None:
    if not progress_path:
        return
    out_dir = os.path.dirname(progress_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    payload = {
        "last_completed": last_completed,
        "updated_at": datetime.datetime.now().isoformat(),
    }
    with open(progress_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def rewrite_chapter_batch(
    start_idx: int,
    end_idx: int,
    s: Settings,
    book_bible_path: str = "book_bible.md",
    docx_path: str | None = None,
    rewrites_dir: str = "rewrites",
    progress_path: str = "",
) -> List[str]:
    """
    Rewrite multiple chapters in sequence using single-turn pipeline.

    Each chapter is rewritten independently using the book bible and retrieval.

    Args:
        start_idx: First chapter index to rewrite (0-based)
        end_idx: Last chapter index to rewrite (inclusive, 0-based)
        s: Settings object
        book_bible_path: Path to book bible
        docx_path: Path to source DOCX
        rewrites_dir: Directory for rewritten chapters

    Returns:
        List of output file paths
    """
    output_paths = []

    for idx in range(start_idx, end_idx + 1):
        log.info(f"\n\n{'='*60}")
        log.info(f"BATCH: Processing Chapter {idx + 1} (index {idx})")
        log.info(f"{'='*60}\n")

        try:
            order = idx + 1
            out_path = f"{rewrites_dir}/chapter-{order:02d}.md"
            result = rewrite_chapter(
                chapter_idx=idx,
                s=s,
                book_bible_path=book_bible_path,
                out_path=out_path,
                docx_path=docx_path,
            )
            output_paths.append(result)
            if progress_path:
                _save_progress(progress_path, idx + 1)
        except Exception as e:
            log.error(f"Failed to rewrite chapter {idx}: {e}")
            raise

    log.info(f"\n\n{'='*60}")
    log.info(f"BATCH COMPLETE: {len(output_paths)} chapters rewritten")
    log.info(f"{'='*60}")

    return output_paths


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


def _load_previous_chapters(
    rewrites_dir: str,
    current_chapter_idx: int,
    count: int = 3,
) -> str:
    """
    Load text from previously rewritten chapters for continuity.

    Args:
        rewrites_dir: Directory containing rewritten chapter files
        current_chapter_idx: Index of current chapter being rewritten
        count: Number of previous chapters to load

    Returns:
        Concatenated text of previous chapters
    """
    import os
    import re

    previous_texts = []
    for i in range(current_chapter_idx):
        # Try to find the file (chapter-XX.md or legacy chapter_XX.md)
        order = i + 1
        for fmt in [
            f"chapter-{order:02d}.md",
            f"chapter-{order}.md",
            f"chapter_{i:02d}.md",
            f"chapter_{i}.md",
        ]:
            path = os.path.join(rewrites_dir, fmt)
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                    # Extract just the chapter content (skip front matter and heading)
                    if content.lstrip().startswith("---\n"):
                        parts = content.split("---\n", 2)
                        if len(parts) >= 3:
                            content = parts[2].lstrip("\n")
                    lines = content.split("\n")
                    if lines and lines[0].startswith("##"):
                        content = "\n".join(lines[1:])
                    previous_texts.append(f"---\n## PREVIOUS CHAPTER {order}\n{content}\n")
                break

        # Stop if we have enough chapters
        if len(previous_texts) >= count:
            break

    return "\n".join(previous_texts[-count:]) if previous_texts else "No previous chapters available yet."


def _retrieve_surrounding_chapter_context(
    chapter_idx: int,
    s: Settings,
    look_ahead: int = 1,
    look_behind: int = 2,
) -> str:
    """
    Retrieve context from surrounding chapters using vector store.

    Args:
        chapter_idx: Current chapter index (0-based)
        s: Settings object
        look_ahead: How many chapters ahead to retrieve
        look_behind: How many chapters behind to retrieve

    Returns:
        Concatenated context from surrounding chapters
    """
    context_parts = []

    # Retrieve from previous chapters
    for offset in range(-look_behind, 0):
        ch = chapter_idx + offset
        if ch >= 0:
            hits = retrieve(f"chapter {ch} plot events characters dialogue", s, k=8)
            chapter_hits = [h for h in hits if int(h["chapter_idx"]) == ch]
            if chapter_hits:
                context_parts.append(f"\n---\n## CHAPTER {ch} (previous) CONTEXT\n")
                for h in chapter_hits[:5]:
                    context_parts.append(h["text"][:600])

    # Retrieve from current chapter
    current_hits = retrieve(f"chapter {chapter_idx} plot events characters dialogue", s, k=10)
    current_chapter_hits = [h for h in current_hits if int(h["chapter_idx"]) == chapter_idx]
    if current_chapter_hits:
        context_parts.append(f"\n---\n## CHAPTER {chapter_idx} (current) CONTEXT\n")
        for h in current_chapter_hits[:6]:
            context_parts.append(h["text"][:600])

    # Retrieve from next chapter(s)
    for offset in range(1, look_ahead + 1):
        ch = chapter_idx + offset
        hits = retrieve(f"chapter {ch} plot events characters dialogue", s, k=8)
        chapter_hits = [h for h in hits if int(h["chapter_idx"]) == ch]
        if chapter_hits:
            context_parts.append(f"\n---\n## CHAPTER {ch} (future) CONTEXT\n")
            for h in chapter_hits[:5]:
                context_parts.append(h["text"][:600])

    return "\n".join(context_parts)


def _get_future_chapter_from_docx(
    chapter_idx: int,
    docx_path: str | None,
    s: Settings,
    count: int = 1,
) -> str:
    """
    Load future chapter(s) from metadata (much faster) or DOCX for continuity context.

    Args:
        chapter_idx: Current chapter index (0-based)
        docx_path: Path to DOCX file (fallback if metadata unavailable)
        s: Settings object
        count: Number of future chapters to load

    Returns:
        Concatenated text of future chapters
    """
    # Try loading from metadata first (faster)
    try:
        all_chapters = _load_chapters_from_metadata(s)
    except FileNotFoundError:
        # Fallback to DOCX
        if not docx_path:
            return "No future chapters available."
        all_chapters = export_chapter_text(docx_path, s)

    future_texts = []

    for i in range(chapter_idx + 1, min(chapter_idx + 1 + count, len(all_chapters))):
        ch = all_chapters[i]
        future_texts.append(f"---\n## FUTURE CHAPTER {ch['chapter_idx']}: {ch['title']}\n{ch['text'][:4000]}\n")

    return "\n".join(future_texts) if future_texts else "No future chapters available."


def rewrite_chapter_multiturn(
    chapter_idx: int,
    s: Settings,
    book_bible_path: str = "book_bible.md",
    out_path: str = "",
    docx_path: str | None = None,
    rewrites_dir: str = "rewrites",
    save_intermediate: bool = False,
) -> str:
    """
    Multi-turn rewrite using 3 different models for progressive improvement.

    Turn 1 (SambaNova gpt-oss-120b): Grammar baseline
    Turn 2 (Kimi-K2-Instruct): Fill gaps with up to 3 previous rewritten chapters
    Turn 3 (Kimi-K2-Thinking): Final draft with book bible + 3 previous rewritten + 2 future from DOCX

    Args:
        chapter_idx: Index of chapter to rewrite (0-based)
        s: Settings object containing API keys and model configs
        book_bible_path: Path to book bible markdown file
        out_path: Final output path (default: rewrites/chapter_XX.md)
        docx_path: Path to source DOCX file
        rewrites_dir: Directory containing previous rewritten chapters
        save_intermediate: Whether to save intermediate turn outputs (default: False)

    Returns:
        Path to final rewritten chapter
    """
    log.info("=" * 60)
    log.info(f"MULTI-TURN REWRITE: Chapter {chapter_idx + 1} (index {chapter_idx})")
    log.info("=" * 60)

    # Find DOCX path (only needed if metadata not available)
    if not docx_path:
        import glob
        docx_files = glob.glob("Book/*.docx")
        if docx_files:
            docx_path = docx_files[0]

    # Get FULL chapter text from vector store metadata (much faster than DOCX)
    log.info(f"Loading chapters from vector store metadata...")
    try:
        all_chapters = _load_chapters_from_metadata(s)
        log.info(f"Loaded {len(all_chapters)} chapters from metadata")
    except FileNotFoundError:
        # Fallback to DOCX if metadata not found
        if not docx_path:
            raise ValueError("No vector store metadata found. Please run 'index' command first.")
        log.info(f"Metadata not found, falling back to DOCX: {docx_path}")
        all_chapters = export_chapter_text(docx_path, s)

    target_ch = next((ch for ch in all_chapters if ch["chapter_idx"] == chapter_idx), None)
    if not target_ch:
        raise ValueError(f"Chapter {chapter_idx} not found in DOCX")

    chapter_title = target_ch["title"]
    original_text = target_ch["text"]
    log.info(f"Chapter {chapter_idx}: {chapter_title} ({len(original_text)} characters)")

    # Load previous rewritten chapters (for turns 2 and 3) - EXPANDED from 1 to 3
    previous_rewritten = _load_previous_chapters(rewrites_dir, chapter_idx, count=3)
    log.info(f"Loaded {previous_rewritten.count('PREVIOUS CHAPTER')} previous rewritten chapters")

    # Get future chapters from DOCX (for turn 3) - EXPANDED from 1 to 2
    future_chapter = _get_future_chapter_from_docx(chapter_idx, docx_path, s, count=2)
    log.info(f"Loaded future chapter context ({len(future_chapter)} characters)")

    current_text = original_text

    # ========================================================================
    # TURN 1: Grammar Baseline (SambaNova gpt-oss-120b)
    # Context: Chapter text only
    # ========================================================================
    log.info("-" * 60)
    log.info("TURN 1: Grammar Baseline (SambaNova gpt-oss-120b)")
    log.info("-" * 60)

    if not s.sambanova_api_key:
        raise ValueError("SAMBANOVA_API_KEY is required for multi-turn rewrite. Set it in environment or .env file.")

    turn1_prompt = GRAMMAR_BASELINE_USER_TEMPLATE.format(
        chapter_idx=chapter_idx + 1,  # Show 1-based
        chapter_title=chapter_title,
        chapter_text=original_text,
    )

    turn1_result = sambanova_chat_simple(
        api_key=s.sambanova_api_key,
        base_url=s.sambanova_base_url,
        model=s.sambanova_model,
        system_prompt=GRAMMAR_BASELINE_SYSTEM,
        user_text=turn1_prompt,
        temperature=0.1,
        top_p=0.1,
    )

    current_text = turn1_result
    log.info(f"Turn 1 complete. Output: {len(current_text)} characters")

    if save_intermediate:
        order = chapter_idx + 1
        intermediate_path = f"{rewrites_dir}/chapter-{order:02d}_turn1_grammar.md"
        os.makedirs(os.path.dirname(intermediate_path), exist_ok=True)
        with open(intermediate_path, "w", encoding="utf-8") as f:
            f.write(current_text)
        log.info(f"Saved Turn 1 output to: {intermediate_path}")

    # ========================================================================
    # TURN 2: Fill Gaps & Improve Dialogue (SambaNova gpt-oss-120b)
    # Context: Up to 3 previous rewritten chapters
    # ========================================================================
    log.info("-" * 60)
    log.info("TURN 2: Fill Gaps & Improve Dialogue (SambaNova gpt-oss-120b) - Up to 3 Previous chapters")
    log.info("-" * 60)

    turn2_prompt = FILL_GAPS_USER_TEMPLATE.format(
        previous_turn_text=current_text,
        previous_chapters=previous_rewritten,
    )

    turn2_result = sambanova_chat_simple(
        api_key=s.sambanova_api_key,
        base_url=s.sambanova_base_url,
        model=s.sambanova_model,
        system_prompt=FILL_GAPS_SYSTEM,
        user_text=turn2_prompt,
        temperature=0.3,
        top_p=0.9,
    )

    current_text = turn2_result
    log.info(f"Turn 2 complete. Output: {len(current_text)} characters")

    if save_intermediate:
        order = chapter_idx + 1
        intermediate_path = f"{rewrites_dir}/chapter-{order:02d}_turn2_gaps.md"
        os.makedirs(os.path.dirname(intermediate_path), exist_ok=True)
        with open(intermediate_path, "w", encoding="utf-8") as f:
            f.write(current_text)
        log.info(f"Saved Turn 2 output to: {intermediate_path}")

    # ========================================================================
    # TURN 3: Final Draft with Improved Flow (Kimi-K2-Thinking)
    # Context: Book bible + 3 previous rewritten chapters + 2 future chapters from DOCX
    # ========================================================================
    log.info("-" * 60)
    log.info("TURN 3: Final Draft (Kimi-K2-Thinking) - Book bible + 3 Previous + 2 Future")
    log.info("-" * 60)

    # Load book bible for turn 3 only
    log.info(f"Loading book bible from: {book_bible_path}")
    with open(book_bible_path, "r", encoding="utf-8") as f:
        bible = f.read()

    turn3_prompt = FINAL_DRAFT_USER_TEMPLATE.format(
        book_bible=bible,
        previous_turn_text=current_text,
        previous_chapters=previous_rewritten,
        future_chapter=future_chapter[:6000],
    )

    turn3_result = kimi_chat(
        api_key=s.nebius_api_key,
        base_url=s.nebius_base_url,
        model=s.kimi_thinking_model,
        system_prompt=FINAL_DRAFT_SYSTEM,
        user_text=turn3_prompt,
        temperature=0.5,
    )

    final_text = turn3_result
    log.info(f"Turn 3 complete. Final output: {len(final_text)} characters")

    # Save final output only
    if not out_path:
        order = chapter_idx + 1
        out_path = f"{rewrites_dir}/chapter-{order:02d}.md"

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    order = chapter_idx + 1
    book_slug = _slugify(getattr(s, "book_name", ""))
    final_text = _apply_front_matter(final_text, book_slug, chapter_title, order)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(final_text)

    log.info("=" * 60)
    log.info(f"Multi-turn rewrite complete!")
    log.info(f"Final chapter saved to: {out_path}")
    log.info("=" * 60)

    return out_path


def rewrite_chapter_multiturn_batch(
    start_idx: int,
    end_idx: int,
    s: Settings,
    book_bible_path: str = "book_bible.md",
    docx_path: str | None = None,
    rewrites_dir: str = "rewrites",
    save_intermediate: bool = False,
    progress_path: str = "",
) -> List[str]:
    """
    Rewrite multiple chapters in sequence using multi-turn pipeline.

    Each chapter builds on the previous ones for continuity.

    Args:
        start_idx: First chapter index to rewrite
        end_idx: Last chapter index to rewrite (inclusive)
        s: Settings object
        book_bible_path: Path to book bible
        docx_path: Path to source DOCX
        rewrites_dir: Directory for rewritten chapters
        save_intermediate: Whether to save intermediate turn outputs

    Returns:
        List of output file paths
    """
    output_paths = []

    for idx in range(start_idx, end_idx + 1):
        log.info(f"\n\n{'='*60}")
        log.info(f"BATCH: Processing Chapter {idx + 1} (index {idx})")
        log.info(f"{'='*60}\n")

        try:
            out_path = rewrite_chapter_multiturn(
                chapter_idx=idx,
                s=s,
                book_bible_path=book_bible_path,
                docx_path=docx_path,
                rewrites_dir=rewrites_dir,
                save_intermediate=save_intermediate,
            )
            output_paths.append(out_path)
            if progress_path:
                _save_progress(progress_path, idx + 1)
        except Exception as e:
            log.error(f"Failed to rewrite chapter {idx}: {e}")
            raise

    log.info(f"\n\n{'='*60}")
    log.info(f"BATCH COMPLETE: {len(output_paths)} chapters rewritten")
    log.info(f"{'='*60}")

    return output_paths
