import json
import logging
import os
import re
import shutil
from pathlib import Path
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.logging import RichHandler

from .config import load_settings, load_settings_legacy
from .book_manager import (
    create_book_structure,
    list_books,
    get_active_book,
    set_active_book,
    delete_book,
    validate_book_structure,
    create_book_name_from_docx,
    get_book_source_path,
    get_book_metadata_path,
    get_book_rewrites_path,
    get_book_validation_path,
    get_book_index_path,
    update_book_info,
    load_central_config,
    save_central_config,
    BOOKS_DIR,
)
from .pipeline import (
    index_book,
    create_book_bible,
    rewrite_chapter,
    rewrite_chapter_batch,
    edit_chapter,
    retrieve,
    export_chapter_text,
    rewrite_chapter_multiturn,
    rewrite_chapter_multiturn_batch,
)
from .character_tracker import (
    load_ledger,
    save_ledger,
    extract_characters_from_chapter,
    merge_extraction_into_ledger,
    format_character_state_for_prompt,
    CharacterLedger,
)
from .bible_enhancer import (
    generate_enhanced_bible,
    save_enhanced_bible,
    load_base_bible,
)
from .continuity_validator import (
    validate_chapter_continuity,
    save_validation_report,
    load_validation_report,
    print_validation_report,
)
from .docx_reader import read_docx_paragraphs
from .splitter import split_into_chapters
from .utils import join_paras
from .kimi_client import kimi_chat
from .sambanova_client import sambanova_chat_simple

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
    """Check if required API keys are available."""
    missing = []

    # Handle both BookSettings and legacy Settings
    if hasattr(s, "settings"):
        api_keys = s.settings
    else:
        api_keys = s

    if not api_keys.nebius_api_key:
        missing.append("NEBIUS_API_KEY")
    if not api_keys.mistral_api_key:
        missing.append("MISTRAL_API_KEY")
    if missing:
        raise SystemExit(f"Missing env vars: {', '.join(missing)} (see .env.example)")


def _check_multiturn_env(s):
    """Check for additional env vars needed for multi-turn rewrite."""
    missing = []

    # Handle both BookSettings and legacy Settings
    if hasattr(s, "settings"):
        api_keys = s.settings
    else:
        api_keys = s

    if not api_keys.sambanova_api_key:
        missing.append("SAMBANOVA_API_KEY")
    if not api_keys.nebius_api_key:
        missing.append("NEBIUS_API_KEY")
    if not api_keys.mistral_api_key:
        missing.append("MISTRAL_API_KEY")
    if missing:
        raise SystemExit(
            f"Missing env vars for multi-turn rewrite: {', '.join(missing)} (see .env.example)"
        )


def get_book_context(args) -> str:
    """Get book name from argument or auto-detect."""
    if hasattr(args, "book") and args.book:
        return args.book

    if hasattr(args, "docx_path") and args.docx_path:
        from .book_manager import create_book_name_from_docx, list_books

        # Check if DOCX is in books/
        books = list_books()
        for book in books:
            docx_in_books = os.path.join(
                "books", book["name"], "source", os.path.basename(args.docx_path)
            )
            if os.path.exists(docx_in_books):
                return book["name"]

    # Auto-generate from filename
    return create_book_name_from_docx(args.docx_path)

    return None


def get_book_context(args) -> str:
    """Get book name from argument or auto-detect."""
    if hasattr(args, "book") and args.book:
        return args.book

    if hasattr(args, "docx_path") and args.docx_path:
        from .book_manager import create_book_name_from_docx, list_books

        # Check if DOCX is in books/
        books = list_books()
        for book in books:
            docx_in_books = os.path.join(
                "books", book["name"], "source", os.path.basename(args.docx_path)
            )
            if os.path.exists(docx_in_books):
                return book["name"]

        # Auto-generate from filename
        return create_book_name_from_docx(args.docx_path)

    return None


def main():
    load_dotenv()

    import argparse

    p = argparse.ArgumentParser("book-rewriter")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_index = sub.add_parser("index", help="Build local FAISS index from DOCX")
    p_index.add_argument(
        "docx_path",
        nargs="?",
        help="Source DOCX file (auto-detects from Book/ if not specified)",
    )
    p_index.add_argument("--book", help="Book name (uses registry if not specified)")

    p_bible = sub.add_parser("bible", help="Create Book Bible from DOCX")
    p_bible.add_argument("--out", default="book_bible.md")
    p_bible.add_argument("--docx", default="")
    p_bible.add_argument("--book", help="Book name (uses registry if not specified)")

    p_rewrite = sub.add_parser(
        "rewrite", help="Rewrite a chapter using Book Bible + retrieval"
    )
    p_rewrite.add_argument("chapter_idx", type=int)
    p_rewrite.add_argument("--bible", default="book_bible.md")
    p_rewrite.add_argument("--out", default="")
    p_rewrite.add_argument("--docx", default="")
    p_rewrite.add_argument("--book", help="Book name (uses registry if not specified)")

    p_rewrite_batch = sub.add_parser(
        "rewrite-batch", help="Rewrite multiple chapters in sequence (single-turn)"
    )
    p_rewrite_batch.add_argument(
        "start_idx", type=int, help="First chapter number (1-based)"
    )
    p_rewrite_batch.add_argument(
        "end_idx", type=int, help="Last chapter number (1-based, inclusive)"
    )
    p_rewrite_batch.add_argument(
        "--bible", default="book_bible.md", help="Path to book bible"
    )
    p_rewrite_batch.add_argument("--docx", default="", help="Path to source DOCX")
    p_rewrite_batch.add_argument(
        "--rewrites-dir", default="rewrites", help="Directory for rewritten chapters"
    )
    p_rewrite_batch.add_argument(
        "--book", help="Book name (uses registry if not specified)"
    )

    p_search = sub.add_parser("search", help="Search index with a query")
    p_search.add_argument("query")
    p_search.add_argument("--k", type=int, default=10)

    p_export = sub.add_parser(
        "export-chapters", help="Export exact chapter text (sanity check splitter)"
    )
    p_export.add_argument("docx_path")
    p_export.add_argument("--out", default="chapters.json")

    p_edit = sub.add_parser(
        "edit", help="Edit an existing rewritten chapter with a specific request"
    )
    p_edit.add_argument("chapter_path", help="Path to the chapter .md file to edit")
    p_edit.add_argument(
        "request",
        help="Edit request (e.g., 'add more sensory detail', 'slow down pacing', 'include Jacob POV')",
    )
    p_edit.add_argument("--bible", default="book_bible.md", help="Path to book bible")
    p_edit.add_argument(
        "--out", default="", help="Output path (default: overwrite original)"
    )

    # Multi-turn rewrite commands
    p_multiturn = sub.add_parser(
        "multiturn",
        help="Rewrite chapter using 3-turn pipeline (SambaNova -> Kimi-Instruct -> Kimi-Thinking)",
    )
    p_multiturn.add_argument("chapter_idx", type=int, help="Chapter number (1-based)")
    p_multiturn.add_argument(
        "--bible", default="book_bible.md", help="Path to book bible"
    )
    p_multiturn.add_argument(
        "--out", default="", help="Output path (default: rewrites/chapter_XX.md)"
    )
    p_multiturn.add_argument("--docx", default="", help="Path to source DOCX")
    p_multiturn.add_argument(
        "--rewrites-dir",
        default="rewrites",
        help="Directory containing previous rewritten chapters",
    )
    p_multiturn.add_argument(
        "--save-intermediate",
        action="store_true",
        help="Save intermediate turn outputs (turn1, turn2)",
    )
    p_multiturn.add_argument(
        "--book", help="Book name (uses registry if not specified)"
    )

    p_multiturn_batch = sub.add_parser(
        "multiturn-batch",
        help="Rewrite multiple chapters in sequence using 3-turn pipeline",
    )
    p_multiturn_batch.add_argument(
        "start_idx", type=int, help="First chapter number (1-based)"
    )
    p_multiturn_batch.add_argument(
        "end_idx", type=int, help="Last chapter number (1-based, inclusive)"
    )
    p_multiturn_batch.add_argument(
        "--bible", default="book_bible.md", help="Path to book bible"
    )
    p_multiturn_batch.add_argument("--docx", default="", help="Path to source DOCX")
    p_multiturn_batch.add_argument(
        "--rewrites-dir", default="rewrites", help="Directory for rewritten chapters"
    )
    p_multiturn_batch.add_argument(
        "--save-intermediate",
        action="store_true",
        help="Save intermediate turn outputs",
    )
    p_multiturn_batch.add_argument(
        "--book", help="Book name (uses registry if not specified)"
    )

    # Character extraction command
    p_extract_chars = sub.add_parser(
        "extract-chars", help="Extract character information from chapters"
    )
    p_extract_chars.add_argument(
        "chapter_idx", help="Chapter number (0-based) or 'all'"
    )
    p_extract_chars.add_argument("--docx", default="", help="Path to DOCX file")
    p_extract_chars.add_argument(
        "--out",
        default="metadata/character_ledger.json",
        help="Output path for character ledger",
    )
    p_extract_chars.add_argument(
        "--book", help="Book name (uses registry if not specified)"
    )

    # Validation command
    p_validate = sub.add_parser(
        "validate-chapter", help="Validate a rewritten chapter for consistency"
    )
    p_validate.add_argument("chapter_path", help="Path to chapter markdown file")
    p_validate.add_argument(
        "--character-ledger", default="metadata/character_ledger.json"
    )
    p_validate.add_argument("--out", help="Save validation report to file")
    p_validate.add_argument(
        "--target-min", type=int, default=2000, help="Minimum word count"
    )
    p_validate.add_argument(
        "--target-max", type=int, default=3500, help="Maximum word count"
    )

    # Enhanced bible command
    p_bible_enhanced = sub.add_parser(
        "bible-enhanced", help="Generate enhanced Book Bible with character registry"
    )
    p_bible_enhanced.add_argument("--docx", default="", help="Path to DOCX file")
    p_bible_enhanced.add_argument(
        "--character-ledger", default="metadata/character_ledger.json"
    )
    p_bible_enhanced.add_argument("--out", default="book_bible_enhanced.md")
    p_bible_enhanced.add_argument(
        "--book", help="Book name (uses registry if not specified)"
    )

    # Style analysis command
    p_analyze_style = sub.add_parser(
        "analyze-style", help="Analyze writing style from rewritten chapters"
    )
    p_analyze_style.add_argument(
        "--chapters", default="0-2", help="Chapter range (e.g., '0-2' or '0,1,2')"
    )
    p_analyze_style.add_argument(
        "--rewrites-dir",
        default="rewrites",
        help="Directory containing rewritten chapters",
    )
    p_analyze_style.add_argument("--out", default="metadata/style_profile.json")
    p_analyze_style.add_argument(
        "--book", help="Book name (uses registry if not specified)"
    )

    # Production multiturn command
    p_multiturn_pro = sub.add_parser(
        "multiturn-pro", help="Production-quality 5-turn rewrite with validation"
    )
    p_multiturn_pro.add_argument(
        "chapter_idx", type=int, help="Chapter index (0-based)"
    )
    p_multiturn_pro.add_argument("--bible", default="book_bible_enhanced.md")
    p_multiturn_pro.add_argument(
        "--character-ledger", default="metadata/character_ledger.json"
    )
    p_multiturn_pro.add_argument("--style-profile", default="")
    p_multiturn_pro.add_argument("--save-intermediate", action="store_true")
    p_multiturn_pro.add_argument("--docx", default="", help="Path to source DOCX")
    p_multiturn_pro.add_argument("--out", default="", help="Output path")
    p_multiturn_pro.add_argument(
        "--book", help="Book name (uses registry if not specified)"
    )

    # Book management commands
    p_books = sub.add_parser("books", help="Manage multiple books")
    books_sub = p_books.add_subparsers(dest="books_cmd", required=True)

    # books list
    p_books_list = books_sub.add_parser("list", help="List all registered books")

    # books create
    p_books_create = books_sub.add_parser("create", help="Create a new book from DOCX")
    p_books_create.add_argument("docx_path", help="Path to source DOCX file")
    p_books_create.add_argument(
        "--name",
        help="Custom book name (auto-generated from filename if not specified)",
    )

    # books delete
    p_books_delete = books_sub.add_parser(
        "delete", help="Delete a book and all its data"
    )
    p_books_delete.add_argument("book_name", help="Name of book to delete")
    p_books_delete.add_argument(
        "--confirm", action="store_true", help="Confirm deletion without prompt"
    )

    # books set-active
    p_books_set_active = books_sub.add_parser("set-active", help="Set active book")
    p_books_set_active.add_argument("book_name", help="Name of book to set as active")

    # books migrate
    p_books_migrate = books_sub.add_parser(
        "migrate", help="Migrate existing data to book structure"
    )

    args = p.parse_args()

    # Get book context for book-related commands
    book = get_book_context(args)

    # Try to load BookSettings first for new book-aware functionality
    try:
        s = load_settings(book)
    except:
        s = load_settings_legacy(book)

    _check_env(s)

    # Handle commands
    if args.cmd == "index":
        docx_path = args.docx_path
        if not docx_path:
            # Try to use book's source file
            if book:
                source_dir = get_book_source_path(book)
                docx_candidates = sorted(source_dir.glob("*.docx"))
                if docx_candidates:
                    docx_path = str(docx_candidates[0])
            elif not docx_path and book:
                log.error(
                    "No DOCX file specified and no books available. Use 'books create' first."
                )
                return

        log.info(f"Reading DOCX: {docx_path}")
        info = index_book(docx_path, s)
        log.info(
            f"Indexed {info['chunks_indexed']} chunks from {info['chapters_detected']} chapters"
        )
        log.info(f"Index saved to: {info['index_dir']}")
        console.print("[green]OK[/green] Indexed.")

    elif args.cmd == "bible":
        docx_path = args.docx if args.docx else None
        bible_path = args.out if args.out else None

        if book:
            if not docx_path:
                source_dir = get_book_source_path(book)
                docx_candidates = sorted(source_dir.glob("*.docx"))
                if docx_candidates:
                    docx_path = str(docx_candidates[0])

            if not args.out or args.out == "book_bible.md":
                bible_path = str(get_book_metadata_path(book) / "book_bible.md")

        if not docx_path:
            log.error(
                "No DOCX file specified and no book source found. Provide --docx."
            )
            return

        if bible_path:
            Path(bible_path).parent.mkdir(parents=True, exist_ok=True)

        log.info(f"Generating book bible from: {docx_path}")
        out = create_book_bible(
            s,
            out_path=bible_path or "book_bible.md",
            docx_path=docx_path,
            book_title=book,
        )
        log.info(f"Book bible written to: {out}")
        console.print("[green]OK[/green] Book bible created.")

    elif args.cmd == "rewrite":
        chapter_idx = args.chapter_idx - 1
        bible_path = args.bible if args.bible else None
        out_path = args.out if args.out else None

        # Use book context for paths
        if book:
            if not out_path:
                out_path = str(
                    get_book_rewrites_path(book) / f"chapter_{chapter_idx:02d}.md"
                )
            # Rewrite needs book bible path
            if not bible_path:
                bible_path = os.path.join("books", book, "metadata", "book_bible.md")

            log.info(f"Rewriting chapter {args.chapter_idx} (index {chapter_idx})...")
            out = rewrite_chapter(
                chapter_idx,
                s,
                bible_path=bible_path,
                out_path=out_path,
                docx_path=args.docx if args.docx else None,
            )
        elif not book:
            # Fallback to default behavior
            log.warning("No book context specified. Using default paths.")
            out = rewrite_chapter(
                chapter_idx,
                s,
                bible_path=bible_path,
                out_path=out_path,
                docx_path=args.docx if args.docx else None,
            )

        log.info(f"Rewrite written to: {out}")
        console.print("[green]OK[/green] Rewrite complete.")

    elif args.cmd == "rewrite-batch":
        # Convert 1-based chapter numbers to 0-based indices
        start_idx = args.start_idx - 1
        end_idx = args.end_idx - 1
        log.info(f"Single-turn batch: chapters {args.start_idx} to {args.end_idx}...")
        docx_path = args.docx if args.docx else None
        if book:
            if not docx_path:
                source_dir = get_book_source_path(book)
                docx_candidates = sorted(source_dir.glob("*.docx"))
                if docx_candidates:
                    docx_path = str(docx_candidates[0])
            if args.rewrites_dir == "rewrites":
                args.rewrites_dir = str(get_book_rewrites_path(book))
            if args.bible == "book_bible.md":
                args.bible = str(get_book_metadata_path(book) / "book_bible.md")
        output_paths = rewrite_chapter_batch(
            start_idx=start_idx,
            end_idx=end_idx,
            s=s,
            book_bible_path=args.bible,
            docx_path=docx_path,
            rewrites_dir=args.rewrites_dir,
        )
        log.info(f"Batch complete: {len(output_paths)} chapters rewritten")
        console.print(
            f"[green]OK[/green] Batch complete: {len(output_paths)} chapters rewritten."
        )

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

    elif args.cmd == "multiturn":
        _check_multiturn_env(s)
        # Convert 1-based chapter number to 0-based index
        chapter_idx = args.chapter_idx - 1
        log.info(
            f"Multi-turn rewrite: chapter {args.chapter_idx} (index {chapter_idx})..."
        )
        log.info(
            "Using 3-turn pipeline: SambaNova (grammar) -> Kimi-Instruct (gaps/dialogue) -> Kimi-Thinking (final)"
        )
        docx_path = args.docx if args.docx else None
        if book:
            if not docx_path:
                source_dir = get_book_source_path(book)
                docx_candidates = sorted(source_dir.glob("*.docx"))
                if docx_candidates:
                    docx_path = str(docx_candidates[0])
            if args.rewrites_dir == "rewrites":
                args.rewrites_dir = str(get_book_rewrites_path(book))
            if args.bible == "book_bible.md":
                args.bible = str(get_book_metadata_path(book) / "book_bible.md")
        out = rewrite_chapter_multiturn(
            chapter_idx=chapter_idx,
            s=s,
            book_bible_path=args.bible,
            out_path=args.out,
            docx_path=docx_path,
            rewrites_dir=args.rewrites_dir,
            save_intermediate=args.save_intermediate,
        )
        log.info(f"Multi-turn rewrite written to: {out}")
        console.print("[green]OK[/green] Multi-turn rewrite complete.")

    elif args.cmd == "multiturn-batch":
        _check_multiturn_env(s)
        # Convert 1-based chapter numbers to 0-based indices
        start_idx = args.start_idx - 1
        end_idx = args.end_idx - 1
        log.info(f"Multi-turn batch: chapters {args.start_idx} to {args.end_idx}...")
        log.info(
            "Using 3-turn pipeline: SambaNova (grammar) -> Kimi-Instruct (gaps/dialogue) -> Kimi-Thinking (final)"
        )
        docx_path = args.docx if args.docx else None
        if book:
            if not docx_path:
                source_dir = get_book_source_path(book)
                docx_candidates = sorted(source_dir.glob("*.docx"))
                if docx_candidates:
                    docx_path = str(docx_candidates[0])
            if args.rewrites_dir == "rewrites":
                args.rewrites_dir = str(get_book_rewrites_path(book))
            if args.bible == "book_bible.md":
                args.bible = str(get_book_metadata_path(book) / "book_bible.md")
        output_paths = rewrite_chapter_multiturn_batch(
            start_idx=start_idx,
            end_idx=end_idx,
            s=s,
            book_bible_path=args.bible,
            docx_path=docx_path,
            rewrites_dir=args.rewrites_dir,
            save_intermediate=args.save_intermediate,
        )
        log.info(f"Batch complete: {len(output_paths)} chapters rewritten")
        console.print(
            f"[green]OK[/green] Batch complete: {len(output_paths)} chapters rewritten."
        )

    elif args.cmd == "extract-chars":
        """Extract character information from chapters."""
        docx_path = args.docx if args.docx else None
        if book:
            if not docx_path:
                source_dir = get_book_source_path(book)
                docx_candidates = sorted(source_dir.glob("*.docx"))
                if docx_candidates:
                    docx_path = str(docx_candidates[0])
            if args.out == "metadata/character_ledger.json":
                args.out = str(get_book_metadata_path(book) / "character_ledger.json")
        if not docx_path:
            raise SystemExit("Error: --docx path required for character extraction")

        log.info(f"Extracting characters from: {args.chapter_idx}")
        log.info(f"Source DOCX: {docx_path}")

        # Load or create ledger
        ledger = load_ledger(args.out)

        # Read chapters from DOCX
        paras = read_docx_paragraphs(docx_path)
        chapters = split_into_chapters(paras)

        # Determine which chapters to process
        if args.chapter_idx.lower() == "all":
            indices_to_process = range(len(chapters))
        else:
            indices_to_process = [int(args.chapter_idx)]

        # Extract characters
        for idx in indices_to_process:
            if idx >= len(chapters):
                log.warning(f"Chapter index {idx} out of range, skipping")
                continue

            chapter_text = join_paras(chapters[idx]["paras"])
            log.info(f"Processing chapter {idx}: {chapters[idx]['title']}")

            # Use Kimi for extraction
            extraction_data = extract_characters_from_chapter(
                chapter_text=chapter_text,
                chapter_idx=idx,
                model_api=kimi_chat,
                system_prompt="You are a narrative analyst specializing in character analysis.",
            )

            if extraction_data["success"]:
                merge_extraction_into_ledger(extraction_data, ledger, idx)
                log.info(
                    f"Extracted {len(extraction_data['characters'])} characters from chapter {idx}"
                )
            else:
                log.error(
                    f"Failed to extract from chapter {idx}: {extraction_data.get('error')}"
                )

        # Save ledger
        save_ledger(ledger, args.out)
        log.info(f"Character ledger saved to: {args.out}")
        log.info(f"Total characters in ledger: {len(ledger.characters)}")
        console.print(
            f"[green]OK[/green] Extracted {len(ledger.characters)} characters."
        )

    elif args.cmd == "validate-chapter":
        """Validate a rewritten chapter for consistency."""
        # Read chapter text
        with open(args.chapter_path, "r", encoding="utf-8") as f:
            chapter_text = f.read()

        # Extract chapter index from filename for context
        match = re.search(r"chapter[_\-]?(\d+)", args.chapter_path.lower())
        chapter_idx = int(match.group(1)) - 1 if match else 0

        # Load character ledger
        ledger = load_ledger(args.character_ledger)

        log.info(f"Validating chapter: {args.chapter_path}")
        log.info(f"Using character ledger: {args.character_ledger}")

        # Run validation
        report = validate_chapter_continuity(
            chapter_text=chapter_text,
            chapter_idx=chapter_idx,
            character_ledger=ledger,
            previous_chapters=[],  # Would need to load previous chapters for full context
            target_min=args.target_min,
            target_max=args.target_max,
        )

        # Print report
        print_validation_report(report)

        # Save report if requested
        if args.out:
            save_validation_report(report, args.out)
            log.info(f"Validation report saved to: {args.out}")

        if report.passed:
            console.print("[green]OK[/green] Chapter validation passed.")
        else:
            console.print(
                "[yellow]WARNING[/yellow] Chapter validation failed. Review issues above."
            )

    elif args.cmd == "bible-enhanced":
        """Generate enhanced Book Bible with character registry."""
        log.info("Generating enhanced Book Bible with character registry...")

        # Check if character ledger exists
        if os.path.exists(args.character_ledger):
            ledger = load_ledger(args.character_ledger)
            log.info(
                f"Loaded character ledger with {len(ledger.characters)} characters"
            )
        else:
            log.warning(f"Character ledger not found at {args.character_ledger}")
            log.warning("Run 'extract-chars' first to populate the ledger")
            ledger = CharacterLedger()

        # Create enhanced bible content
        docx_path = args.docx if args.docx else None
        if book:
            if not docx_path:
                source_dir = get_book_source_path(book)
                docx_candidates = sorted(source_dir.glob("*.docx"))
                if docx_candidates:
                    docx_path = str(docx_candidates[0])
            if args.character_ledger == "metadata/character_ledger.json":
                args.character_ledger = str(
                    get_book_metadata_path(book) / "character_ledger.json"
                )
            if args.out == "book_bible_enhanced.md":
                args.out = str(get_book_metadata_path(book) / "book_bible_enhanced.md")

        # First generate the base bible
        base_bible_path = (
            str(get_book_metadata_path(book) / "book_bible.md")
            if book
            else "book_bible.md"
        )
        if not os.path.exists(base_bible_path):
            log.info("Creating base book bible first...")
            create_book_bible(
                s,
                out_path=base_bible_path,
                docx_path=docx_path,
                book_title=book,
            )

        # Read base bible
        base_bible = load_base_bible(base_bible_path)

        # Generate enhanced bible using the new module
        enhanced_content = generate_enhanced_bible(
            base_bible=base_bible,
            character_ledger=ledger,
            locations=ledger.locations if hasattr(ledger, "locations") else None,
            objects=ledger.objects if hasattr(ledger, "objects") else None,
        )

        # Save enhanced bible
        save_enhanced_bible(enhanced_content, args.out)

        log.info(f"Enhanced Book Bible written to: {args.out}")
        console.print("[green]OK[/green] Enhanced Book Bible created.")

    elif args.cmd == "analyze-style":
        """Analyze writing style from rewritten chapters."""
        import asyncio

        log.info("Analyzing writing style from rewritten chapters...")
        if book:
            if args.rewrites_dir == "rewrites":
                args.rewrites_dir = str(get_book_rewrites_path(book))
            if args.out == "metadata/style_profile.json":
                args.out = str(get_book_metadata_path(book) / "style_profile.json")

        # Parse chapter range
        if "-" in args.chapters:
            start, end = map(int, args.chapters.split("-"))
            chapter_indices = list(range(start, end + 1))
        else:
            chapter_indices = [int(x) for x in args.chapters.split(",")]

        log.info(f"Analyzing chapters: {chapter_indices}")

        # Read chapter texts
        chapter_texts = []
        for idx in chapter_indices:
            chapter_path = os.path.join(args.rewrites_dir, f"chapter_{idx:02d}.md")
            if not os.path.exists(chapter_path):
                log.warning(f"Chapter file not found: {chapter_path}")
                continue

            with open(chapter_path, "r", encoding="utf-8") as f:
                text = f.read()
                chapter_texts.append(text)
                log.info(f"Loaded chapter {idx}: {len(text.split())} words")

        if not chapter_texts:
            raise SystemExit("Error: No valid chapter files found")

        # Create style analysis prompt
        style_prompt = """Analyze the writing style of these sample chapters and create a style profile that captures:

1. VOICE & TONE
   - Narrative voice (first-person, etc.)
   - Overall tone and mood
   - Emotional resonance

2. SENTENCE STRUCTURE
   - Average sentence length
   - Sentence variety (simple, compound, complex)
   - Rhythm and flow patterns

3. DIALOGUE STYLE
   - Dialogue tag usage
   - Natural speech patterns
   - Internal vs external dialogue balance

4. DESCRIPTIVE PATTERNS
   - Sensory detail preferences
   - Metaphor and simile usage
   - Pacing of descriptions

5. POV CHARACTERISTICS
   - Internal monologue style
   - Perspective consistency
   - Character voice differentiation

Return ONLY valid JSON in this format:
{
  "voice": {
    "narrative_mode": "first-person",
    "tone": "intimate, introspective",
    "mood": "tense but hopeful"
  },
  "sentence_structure": {
    "avg_length": "15-20 words",
    "variety": "mix of short punchy sentences and longer descriptive ones",
    "rhythm": "varied, with occasional fragments for emphasis"
  },
  "dialogue": {
    "tag_usage": "minimal, mostly action beats",
    "natural_speech": "contractions allowed in dialogue only",
    "internal_external_balance": "heavy internal monologue, sparse external dialogue"
  },
  "descriptive": {
    "sensory_focus": "visual and tactile",
    "metaphor_usage": "sparse, grounded",
    "pacing": "slow, detailed during action scenes"
  },
  "pov": {
    "internal_monologue": "present tense, immediate",
    "perspective": "strict first-person",
    "character_voice": "distinct per character"
  },
  "restrictions": [
    "no em dashes (—) in narrative",
    "no contractions in narrative (dialogue OK)",
    "maintain first-person POV throughout"
  ]
}"""

        # Combine samples
        combined_samples = "\n\n---CHAPTER BREAK---\n\n".join(
            chapter_texts[: s.style_sample_size]
        )

        # Call Kimi for analysis
        messages = [
            {
                "role": "system",
                "content": "You are a literary analyst specializing in prose style analysis.",
            },
            {
                "role": "user",
                "content": f"{style_prompt}\n\nSample chapters:\n\n{combined_samples}",
            },
        ]

        response = asyncio.run(kimi_chat(messages=messages, temperature=0.1))

        # Extract JSON from response
        json_match = re.search(r"\{.*\}", response, re.DOTALL)
        if json_match:
            style_data = json.loads(json_match.group(0))
        else:
            raise SystemExit("Failed to parse style profile from response")

        # Add metadata
        style_data["metadata"] = {
            "source_chapters": chapter_indices[: s.style_sample_size],
            "total_words_analyzed": sum(
                len(t.split()) for t in chapter_texts[: s.style_sample_size]
            ),
            "generated_at": __import__("datetime").datetime.now().isoformat(),
        }

        # Save style profile
        os.makedirs(
            os.path.dirname(args.out) if os.path.dirname(args.out) else ".",
            exist_ok=True,
        )
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(style_data, f, indent=2, ensure_ascii=False)

        log.info(f"Style profile saved to: {args.out}")
        log.info(f"Analyzed {len(chapter_texts[: s.style_sample_size])} chapters")
        console.print("[green]OK[/green] Style analysis complete.")

    elif args.cmd == "multiturn-pro":
        """Production-quality 5-turn rewrite with validation."""
        _check_multiturn_env(s)

        # Convert 1-based to 0-based
        chapter_idx = args.chapter_idx - 1
        log.info(
            f"Production 5-turn rewrite: chapter {args.chapter_idx} (index {chapter_idx})..."
        )

        # Load additional resources
        if book:
            if args.bible == "book_bible_enhanced.md":
                args.bible = str(get_book_metadata_path(book) / "book_bible_enhanced.md")
            if args.character_ledger == "metadata/character_ledger.json":
                args.character_ledger = str(
                    get_book_metadata_path(book) / "character_ledger.json"
                )
            if args.style_profile == "" and os.path.exists(
                get_book_metadata_path(book) / "style_profile.json"
            ):
                args.style_profile = str(
                    get_book_metadata_path(book) / "style_profile.json"
                )
            if args.docx == "":
                source_dir = get_book_source_path(book)
                docx_candidates = sorted(source_dir.glob("*.docx"))
                if docx_candidates:
                    args.docx = str(docx_candidates[0])

        if os.path.exists(args.character_ledger):
            ledger = load_ledger(args.character_ledger)
            log.info(f"Loaded character ledger: {len(ledger.characters)} characters")
        else:
            log.warning(f"Character ledger not found: {args.character_ledger}")
            ledger = None

        style_profile = None
        if args.style_profile and os.path.exists(args.style_profile):
            with open(args.style_profile, "r", encoding="utf-8") as f:
                style_profile = json.load(f)
            log.info(f"Loaded style profile")

        # For now, use the existing 3-turn rewrite
        # TODO: Implement full 5-turn pipeline with validation
        log.info("Using enhanced 3-turn pipeline with validation...")

        docx_path = args.docx if args.docx else None
        rewrites_dir = (
            str(get_book_rewrites_path(book)) if book else "rewrites"
        )
        out = rewrite_chapter_multiturn(
            chapter_idx=chapter_idx,
            s=s,
            book_bible_path=args.bible,
            out_path=args.out,
            docx_path=docx_path,
            rewrites_dir=rewrites_dir,
            save_intermediate=args.save_intermediate,
        )

        # Validate the result if enabled
        if s.enable_validation and ledger:
            log.info("Running validation on rewritten chapter...")
            with open(out, "r", encoding="utf-8") as f:
                chapter_text = f.read()

            report = validate_chapter_continuity(
                chapter_text=chapter_text,
                chapter_idx=chapter_idx,
                character_ledger=ledger,
                previous_chapters=[],
                target_min=s.target_word_count_min,
                target_max=s.target_word_count_max,
            )

            print_validation_report(report)

            # Save validation report to validation folder
            validation_dir = (
                str(get_book_validation_path(book)) if book else "book_validator"
            )
            os.makedirs(validation_dir, exist_ok=True)
            chapter_name = os.path.basename(out).replace(".md", "")
            validation_path = os.path.join(
                validation_dir, f"{chapter_name}_validation.json"
            )
            save_validation_report(report, validation_path)
            log.info(f"Validation report saved to: {validation_path}")

        log.info(f"Production rewrite written to: {out}")
        console.print("[green]OK[/green] Production rewrite complete.")

    elif args.cmd == "books":
        if args.books_cmd == "list":
            books = list_books()
            if not books:
                console.print("[yellow]No books registered yet.[/yellow]")
                console.print(
                    "Use 'books create <docx_path>' to create your first book."
                )
            else:
                table = Table(title="Registered Books")
                table.add_column("Book Name", style="cyan")
                table.add_column("Display Name", style="magenta")
                table.add_column("Created", style="dim")
                table.add_column("Chapters", justify="right")
                table.add_column("Last Modified", style="dim")
                table.add_column("Active", justify="center")

                for book in books:
                    active_marker = "[green]✓[/green]" if book["is_active"] else ""
                    table.add_row(
                        book["name"],
                        book["display_name"],
                        book["created"][:10],
                        str(book["total_chapters"]),
                        book["last_modified"][:10],
                        active_marker,
                    )
                console.print(table)

                active_book = get_active_book()
                if active_book:
                    console.print(f"\nActive book: [cyan]{active_book}[/cyan]")
                else:
                    console.print(
                        "\nNo active book set. Use 'books set-active <name>'."
                    )

        elif args.books_cmd == "create":
            log.info(f"Creating new book from: {args.docx_path}")

            if not os.path.exists(args.docx_path):
                raise SystemExit(f"Error: DOCX file not found: {args.docx_path}")

            book_name = (
                args.name if args.name else create_book_name_from_docx(args.docx_path)
            )
            book_info = create_book_structure(book_name, args.docx_path)

            console.print(f"[green]OK[/green] Book created: {book_name}")
            console.print(f"Display name: {book_info['name']}")
            console.print(f"Source file: {book_info['source_file']}")
            console.print(
                f"\nUse --book {book_name} with commands to work with this book."
            )
            console.print(
                f"Or set as active: python -m book_rewriter.cli books set-active {book_name}"
            )

        elif args.books_cmd == "delete":
            book_name = args.book_name

            if not args.confirm:
                console.print(
                    f"[yellow]WARNING: This will delete all data for '{book_name}'[/yellow]"
                )
                confirm = input(f"Type '{book_name}' to confirm deletion: ")
                if confirm != book_name:
                    console.print("[yellow]Cancelled.[/yellow]")
                    return

            delete_book(book_name)
            console.print(f"[green]OK[/green] Deleted book: {book_name}")

        elif args.books_cmd == "set-active":
            book_name = args.book_name
            set_active_book(book_name)
            console.print(f"[green]OK[/green] Active book set to: {book_name}")

        elif args.books_cmd == "migrate":
            log.info("Migrating existing data to new book structure...")

            # Check if migration has already been done
            if os.path.exists(BOOKS_DIR) and list(os.listdir(BOOKS_DIR)):
                console.print(
                    "[yellow]Books directory already exists with data.[/yellow]"
                )
                console.print("Contents of books/:")
                for book_dir in sorted(os.listdir(BOOKS_DIR)):
                    book_path = os.path.join(BOOKS_DIR, book_dir)
                    console.print(f"  - {book_dir}/")
                console.print("\n[yellow]Options:[/yellow]")
                console.print("1. Continue migration - may overwrite existing books")
                console.print("2. Abort migration - keep current state")
                choice = input("Choose (1/2, or press Enter to abort): ").strip()

                if choice == "2":
                    console.print("[yellow]Aborted by user.[/yellow]")
                    return
                elif choice != "1":
                    console.print("[yellow]Aborted.[/yellow]")
                    return

            # Migrate from existing structure

            # Find source DOCX
            docx_files = (
                list(Path("Book").glob("*.docx")) if os.path.exists("Book") else []
            )
            if not docx_files:
                console.print("[yellow]No DOCX files found in Book/ directory[/yellow]")
                return

            source_docx = str(docx_files[0])
            book_name = create_book_name_from_docx(source_docx)

            console.print(f"Creating book: {book_name}")
            book_info = create_book_structure(book_name, source_docx)

            # Migrate metadata
            if os.path.exists("metadata"):
                console.print("Migrating metadata...")
                metadata_dest = get_book_metadata_path(book_name)
                for item in os.listdir("metadata"):
                    src = os.path.join("metadata", item)
                    dst = os.path.join(metadata_dest, item)
                    if os.path.isdir(src):
                        shutil.copytree(src, dst, dirs_exist_ok=True)
                    else:
                        shutil.copy2(src, dst)

            # Migrate rewrites
            if os.path.exists("rewrites"):
                console.print("Migrating rewrites...")
                rewrites_dest = get_book_rewrites_path(book_name)
                for item in os.listdir("rewrites"):
                    src = os.path.join("rewrites", item)
                    dst = os.path.join(rewrites_dest, item)
                    shutil.copy2(src, dst)

                # Update chapter count
                chapter_count = len(
                    [f for f in os.listdir(rewrites_dest) if f.startswith("chapter_")]
                )
                update_book_info(book_name, {"total_chapters": chapter_count})

            # Migrate validation
            if os.path.exists("book_validator"):
                console.print("Migrating validation reports...")
                validation_dest = get_book_validation_path(book_name)
                for item in os.listdir("book_validator"):
                    src = os.path.join("book_validator", item)
                    dst = os.path.join(validation_dest, item)
                    shutil.copy2(src, dst)

            # Migrate index
            if os.path.exists("book_index"):
                console.print("Migrating index...")
                index_dest = get_book_index_path(book_name)
                for item in os.listdir("book_index"):
                    src = os.path.join("book_index", item)
                    dst = os.path.join(index_dest, item)
                    shutil.copy2(src, dst)

            # Migrate bibles
            for bible_file in ["book_bible.md", "book_bible_enhanced.md"]:
                if os.path.exists(bible_file):
                    console.print(f"Migrating {bible_file}...")
                    shutil.copy2(
                        bible_file, get_book_metadata_path(book_name) / bible_file
                    )

            console.print("[green]OK[/green] Migration complete!")
            console.print(f"Your book has been migrated to: books/{book_name}/")
            console.print("\nNext steps:")
            console.print(
                f"  1. Set active book: python -m book_rewriter.cli books set-active {book_name}"
            )
            console.print(f"  2. Use commands with --book {book_name}")
            console.print("\nOld directories can now be deleted if desired:")
            console.print("  Book/, metadata/, rewrites/, book_validator/, book_index/")


if __name__ == "__main__":
    main()
