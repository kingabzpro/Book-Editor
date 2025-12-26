import json
import os
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from .config import load_settings
from .pipeline import (
    index_book,
    create_book_bible,
    rewrite_chapter,
    retrieve,
    export_chapter_text,
)

console = Console()

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

    p_bible = sub.add_parser("bible", help="Create Book Bible from index")
    p_bible.add_argument("--out", default="book_bible.md")

    p_rewrite = sub.add_parser("rewrite", help="Rewrite a chapter using Book Bible + retrieval")
    p_rewrite.add_argument("chapter_idx", type=int)
    p_rewrite.add_argument("--bible", default="book_bible.md")
    p_rewrite.add_argument("--out", default="")

    p_search = sub.add_parser("search", help="Search index with a query")
    p_search.add_argument("query")
    p_search.add_argument("--k", type=int, default=10)

    p_export = sub.add_parser("export-chapters", help="Export exact chapter text (sanity check splitter)")
    p_export.add_argument("docx_path")
    p_export.add_argument("--out", default="chapters.json")

    args = p.parse_args()

    if args.cmd == "index":
        info = index_book(args.docx_path, s)
        console.print("[green]OK[/green] Indexed.")
        console.print(info)

    elif args.cmd == "bible":
        out = create_book_bible(s, out_path=args.out)
        console.print(f"[green]OK[/green] Book Bible written to: {out}")

    elif args.cmd == "rewrite":
        out = rewrite_chapter(args.chapter_idx, s, book_bible_path=args.bible, out_path=args.out)
        console.print(f"[green]OK[/green] Rewrite written to: {out}")

    elif args.cmd == "search":
        hits = retrieve(args.query, s, k=args.k)
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
        chapters = export_chapter_text(args.docx_path, s)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(chapters, f, ensure_ascii=False, indent=2)
        console.print(f"[green]OK[/green] Exported chapters to: {args.out}")

if __name__ == "__main__":
    main()
