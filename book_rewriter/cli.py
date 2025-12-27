import json
import logging
import os
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.logging import RichHandler

from .config import load_settings
from .pipeline import (
    index_book,
    create_book_bible,
    rewrite_chapter,
    edit_chapter,
    retrieve,
    export_chapter_text,
)

console = Console()

# Configure rich logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(console=console, rich_tracebacks=True)],
)
log = logging.getLogger("book-rewriter")

def _check_env(s):
    missing = []
    if not s.nebius_api_key:
        missing.append("NEBIUS_API_KEY")
    if not s.mistral_api_key:
        missing.append("MISTRAL_API_KEY")
    if missing:
        raise SystemExit(f"Missing env vars: {', '.join(missing)} (see .env.example)")

def main():
    load_dotenv()  # loads .env if present
    s = load_settings()
    _check_env(s)

    import argparse
    p = argparse.ArgumentParser("book-rewriter")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_index = sub.add_parser("index", help="Build local FAISS index from DOCX")
    p_index.add_argument("docx_path")

    p_bible = sub.add_parser("bible", help="Create Book Bible from DOCX")
    p_bible.add_argument("--out", default="book_bible.md")
    p_bible.add_argument("--docx", default="")

    p_rewrite = sub.add_parser("rewrite", help="Rewrite a chapter using Book Bible + retrieval")
    p_rewrite.add_argument("chapter_idx", type=int)
    p_rewrite.add_argument("--bible", default="book_bible.md")
    p_rewrite.add_argument("--out", default="")
    p_rewrite.add_argument("--docx", default="")

    p_search = sub.add_parser("search", help="Search index with a query")
    p_search.add_argument("query")
    p_search.add_argument("--k", type=int, default=10)

    p_export = sub.add_parser("export-chapters", help="Export exact chapter text (sanity check splitter)")
    p_export.add_argument("docx_path")
    p_export.add_argument("--out", default="chapters.json")

    p_edit = sub.add_parser("edit", help="Edit an existing rewritten chapter with a specific request")
    p_edit.add_argument("chapter_path", help="Path to the chapter .md file to edit")
    p_edit.add_argument("request", help="Edit request (e.g., 'add more sensory detail', 'slow down pacing', 'include Jacob POV')")
    p_edit.add_argument("--bible", default="book_bible.md", help="Path to book bible")
    p_edit.add_argument("--out", default="", help="Output path (default: overwrite original)")

    args = p.parse_args()

    if args.cmd == "index":
        log.info(f"Reading DOCX: {args.docx_path}")
        info = index_book(args.docx_path, s)
        log.info(f"Indexed {info['chunks_indexed']} chunks from {info['chapters_detected']} chapters")
        log.info(f"Index saved to: {info['index_dir']}")
        console.print("[green]OK[/green] Indexed.")

    elif args.cmd == "bible":
        log.info("Building Book Bible from chapter text...")
        docx_path = args.docx if args.docx else None
        out = create_book_bible(s, out_path=args.out, docx_path=docx_path)
        log.info(f"Book Bible written to: {out}")
        console.print("[green]OK[/green] Book Bible created.")

    elif args.cmd == "rewrite":
        # Convert 1-based chapter number to 0-based index
        chapter_idx = args.chapter_idx - 1
        log.info(f"Rewriting chapter {args.chapter_idx} (index {chapter_idx})...")
        log.info(f"Using book bible: {args.bible}")
        docx_path = args.docx if args.docx else None
        out = rewrite_chapter(chapter_idx, s, book_bible_path=args.bible, out_path=args.out, docx_path=docx_path)
        log.info(f"Rewrite written to: {out}")
        console.print("[green]OK[/green] Rewrite complete.")

    elif args.cmd == "search":
        log.info(f"Searching for: '{args.query}' (k={args.k})")
        hits = retrieve(args.query, s, k=args.k)
        log.info(f"Found {len(hits)} matches")
        table = Table(title="Top matches")
        table.add_column("Score", justify="right")
        table.add_column("Chapter")
        table.add_column("Chunk")
        table.add_column("Title")
        for h in hits:
            table.add_row(
                f"{h['score']:.3f}",
                str(h["chapter_idx"]),
                str(h["chunk_idx_in_chapter"]),
                h["chapter_title"][:60],
            )
        console.print(table)

    elif args.cmd == "export-chapters":
        log.info(f"Exporting chapters from: {args.docx_path}")
        chapters = export_chapter_text(args.docx_path, s)
        log.info(f"Found {len(chapters)} chapters")
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(chapters, f, ensure_ascii=False, indent=2)
        log.info(f"Exported chapters to: {args.out}")
        console.print("[green]OK[/green] Chapters exported.")

    elif args.cmd == "edit":
        log.info(f"Editing chapter: {args.chapter_path}")
        log.info(f"Edit request: {args.request}")
        out = edit_chapter(
            chapter_path=args.chapter_path,
            edit_request=args.request,
            s=s,
            book_bible_path=args.bible,
            out_path=args.out if args.out else "",
        )
        log.info(f"Edited chapter saved to: {out}")
        console.print("[green]OK[/green] Chapter edited.")

if __name__ == "__main__":
    main()
