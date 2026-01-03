import json
import logging
import os
import re
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.logging import RichHandler

from .config import load_settings
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
    missing = []
    if not s.nebius_api_key:
        missing.append("NEBIUS_API_KEY")
    if not s.mistral_api_key:
        missing.append("MISTRAL_API_KEY")
    if missing:
        raise SystemExit(f"Missing env vars: {', '.join(missing)} (see .env.example)")

def _check_multiturn_env(s):
    """Check for additional env vars needed for multi-turn rewrite."""
    missing = []
    if not s.sambanova_api_key:
        missing.append("SAMBANOVA_API_KEY")
    if not s.nebius_api_key:
        missing.append("NEBIUS_API_KEY")
    if not s.mistral_api_key:
        missing.append("MISTRAL_API_KEY")
    if missing:
        raise SystemExit(f"Missing env vars for multi-turn rewrite: {', '.join(missing)}")

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

    p_rewrite_batch = sub.add_parser("rewrite-batch", help="Rewrite multiple chapters in sequence (single-turn)")
    p_rewrite_batch.add_argument("start_idx", type=int, help="First chapter number (1-based)")
    p_rewrite_batch.add_argument("end_idx", type=int, help="Last chapter number (1-based, inclusive)")
    p_rewrite_batch.add_argument("--bible", default="book_bible.md", help="Path to book bible")
    p_rewrite_batch.add_argument("--docx", default="", help="Path to source DOCX")
    p_rewrite_batch.add_argument("--rewrites-dir", default="rewrites", help="Directory for rewritten chapters")

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

    # Multi-turn rewrite commands
    p_multiturn = sub.add_parser("multiturn", help="Rewrite chapter using 3-turn pipeline (SambaNova -> Kimi-Instruct -> Kimi-Thinking)")
    p_multiturn.add_argument("chapter_idx", type=int, help="Chapter number (1-based)")
    p_multiturn.add_argument("--bible", default="book_bible.md", help="Path to book bible")
    p_multiturn.add_argument("--out", default="", help="Output path (default: rewrites/chapter_XX.md)")
    p_multiturn.add_argument("--docx", default="", help="Path to source DOCX")
    p_multiturn.add_argument("--rewrites-dir", default="rewrites", help="Directory containing previous rewritten chapters")
    p_multiturn.add_argument("--save-intermediate", action="store_true", help="Save intermediate turn outputs (turn1, turn2)")

    p_multiturn_batch = sub.add_parser("multiturn-batch", help="Rewrite multiple chapters in sequence using 3-turn pipeline")
    p_multiturn_batch.add_argument("start_idx", type=int, help="First chapter number (1-based)")
    p_multiturn_batch.add_argument("end_idx", type=int, help="Last chapter number (1-based, inclusive)")
    p_multiturn_batch.add_argument("--bible", default="book_bible.md", help="Path to book bible")
    p_multiturn_batch.add_argument("--docx", default="", help="Path to source DOCX")
    p_multiturn_batch.add_argument("--rewrites-dir", default="rewrites", help="Directory for rewritten chapters")
    p_multiturn_batch.add_argument("--save-intermediate", action="store_true", help="Save intermediate turn outputs")

    # Character extraction command
    p_extract_chars = sub.add_parser("extract-chars", help="Extract character information from chapters")
    p_extract_chars.add_argument("chapter_idx", help="Chapter number (0-based) or 'all'")
    p_extract_chars.add_argument("--docx", default="", help="Path to DOCX file")
    p_extract_chars.add_argument("--out", default="metadata/character_ledger.json", help="Output path for character ledger")

    # Validation command
    p_validate = sub.add_parser("validate-chapter", help="Validate a rewritten chapter for consistency")
    p_validate.add_argument("chapter_path", help="Path to chapter markdown file")
    p_validate.add_argument("--character-ledger", default="metadata/character_ledger.json")
    p_validate.add_argument("--out", help="Save validation report to file")
    p_validate.add_argument("--target-min", type=int, default=2000, help="Minimum word count")
    p_validate.add_argument("--target-max", type=int, default=3500, help="Maximum word count")

    # Enhanced bible command
    p_bible_enhanced = sub.add_parser("bible-enhanced", help="Generate enhanced Book Bible with character registry")
    p_bible_enhanced.add_argument("--docx", default="", help="Path to DOCX file")
    p_bible_enhanced.add_argument("--character-ledger", default="metadata/character_ledger.json")
    p_bible_enhanced.add_argument("--out", default="book_bible_enhanced.md")

    # Style analysis command
    p_analyze_style = sub.add_parser("analyze-style", help="Analyze writing style from rewritten chapters")
    p_analyze_style.add_argument("--chapters", default="0-2", help="Chapter range (e.g., '0-2' or '0,1,2')")
    p_analyze_style.add_argument("--rewrites-dir", default="rewrites", help="Directory containing rewritten chapters")
    p_analyze_style.add_argument("--out", default="metadata/style_profile.json")

    # Production multiturn command
    p_multiturn_pro = sub.add_parser("multiturn-pro", help="Production-quality 5-turn rewrite with validation")
    p_multiturn_pro.add_argument("chapter_idx", type=int, help="Chapter index (0-based)")
    p_multiturn_pro.add_argument("--bible", default="book_bible_enhanced.md")
    p_multiturn_pro.add_argument("--character-ledger", default="metadata/character_ledger.json")
    p_multiturn_pro.add_argument("--style-profile", default="")
    p_multiturn_pro.add_argument("--save-intermediate", action="store_true")
    p_multiturn_pro.add_argument("--docx", default="", help="Path to source DOCX")
    p_multiturn_pro.add_argument("--out", default="", help="Output path")

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

    elif args.cmd == "rewrite-batch":
        # Convert 1-based chapter numbers to 0-based indices
        start_idx = args.start_idx - 1
        end_idx = args.end_idx - 1
        log.info(f"Single-turn batch: chapters {args.start_idx} to {args.end_idx}...")
        docx_path = args.docx if args.docx else None
        output_paths = rewrite_chapter_batch(
            start_idx=start_idx,
            end_idx=end_idx,
            s=s,
            book_bible_path=args.bible,
            docx_path=docx_path,
            rewrites_dir=args.rewrites_dir,
        )
        log.info(f"Batch complete: {len(output_paths)} chapters rewritten")
        console.print(f"[green]OK[/green] Batch complete: {len(output_paths)} chapters rewritten.")

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
        log.info(f"Multi-turn rewrite: chapter {args.chapter_idx} (index {chapter_idx})...")
        log.info("Using 3-turn pipeline: SambaNova (grammar) -> Kimi-Instruct (gaps/dialogue) -> Kimi-Thinking (final)")
        docx_path = args.docx if args.docx else None
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
        log.info("Using 3-turn pipeline: SambaNova (grammar) -> Kimi-Instruct (gaps/dialogue) -> Kimi-Thinking (final)")
        docx_path = args.docx if args.docx else None
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
        console.print(f"[green]OK[/green] Batch complete: {len(output_paths)} chapters rewritten.")

    elif args.cmd == "extract-chars":
        """Extract character information from chapters."""
        docx_path = args.docx if args.docx else None
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
                system_prompt="You are a narrative analyst specializing in character analysis."
            )

            if extraction_data["success"]:
                merge_extraction_into_ledger(extraction_data, ledger, idx)
                log.info(f"Extracted {len(extraction_data['characters'])} characters from chapter {idx}")
            else:
                log.error(f"Failed to extract from chapter {idx}: {extraction_data.get('error')}")

        # Save ledger
        save_ledger(ledger, args.out)
        log.info(f"Character ledger saved to: {args.out}")
        log.info(f"Total characters in ledger: {len(ledger.characters)}")
        console.print(f"[green]OK[/green] Extracted {len(ledger.characters)} characters.")

    elif args.cmd == "validate-chapter":
        """Validate a rewritten chapter for consistency."""
        # Read chapter text
        with open(args.chapter_path, 'r', encoding='utf-8') as f:
            chapter_text = f.read()

        # Extract chapter index from filename for context
        match = re.search(r'chapter[_\-]?(\d+)', args.chapter_path.lower())
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
            target_max=args.target_max
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
            console.print("[yellow]WARNING[/yellow] Chapter validation failed. Review issues above.")

    elif args.cmd == "bible-enhanced":
        """Generate enhanced Book Bible with character registry."""
        log.info("Generating enhanced Book Bible with character registry...")

        # Check if character ledger exists
        if os.path.exists(args.character_ledger):
            ledger = load_ledger(args.character_ledger)
            log.info(f"Loaded character ledger with {len(ledger.characters)} characters")
        else:
            log.warning(f"Character ledger not found at {args.character_ledger}")
            log.warning("Run 'extract-chars' first to populate the ledger")
            ledger = CharacterLedger()

        # Create enhanced bible content
        docx_path = args.docx if args.docx else None

        # First generate the base bible
        base_bible_path = "book_bible.md"
        if not os.path.exists(base_bible_path):
            log.info("Creating base book bible first...")
            create_book_bible(s, out_path=base_bible_path, docx_path=docx_path)

        # Read base bible
        base_bible = load_base_bible(base_bible_path)

        # Generate enhanced bible using the new module
        enhanced_content = generate_enhanced_bible(
            base_bible=base_bible,
            character_ledger=ledger,
            locations=ledger.locations if hasattr(ledger, 'locations') else None,
            objects=ledger.objects if hasattr(ledger, 'objects') else None
        )

        # Save enhanced bible
        save_enhanced_bible(enhanced_content, args.out)

        log.info(f"Enhanced Book Bible written to: {args.out}")
        console.print("[green]OK[/green] Enhanced Book Bible created.")

    elif args.cmd == "analyze-style":
        """Analyze writing style from rewritten chapters."""
        import asyncio

        log.info("Analyzing writing style from rewritten chapters...")

        # Parse chapter range
        if '-' in args.chapters:
            start, end = map(int, args.chapters.split('-'))
            chapter_indices = list(range(start, end + 1))
        else:
            chapter_indices = [int(x) for x in args.chapters.split(',')]

        log.info(f"Analyzing chapters: {chapter_indices}")

        # Read chapter texts
        chapter_texts = []
        for idx in chapter_indices:
            chapter_path = os.path.join(args.rewrites_dir, f"chapter_{idx:02d}.md")
            if not os.path.exists(chapter_path):
                log.warning(f"Chapter file not found: {chapter_path}")
                continue

            with open(chapter_path, 'r', encoding='utf-8') as f:
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
        combined_samples = "\n\n---CHAPTER BREAK---\n\n".join(chapter_texts[:s.style_sample_size])

        # Call Kimi for analysis
        messages = [
            {"role": "system", "content": "You are a literary analyst specializing in prose style analysis."},
            {"role": "user", "content": f"{style_prompt}\n\nSample chapters:\n\n{combined_samples}"}
        ]

        response = asyncio.run(kimi_chat(messages=messages, temperature=0.1))

        # Extract JSON from response
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            style_data = json.loads(json_match.group(0))
        else:
            raise SystemExit("Failed to parse style profile from response")

        # Add metadata
        style_data['metadata'] = {
            'source_chapters': chapter_indices[:s.style_sample_size],
            'total_words_analyzed': sum(len(t.split()) for t in chapter_texts[:s.style_sample_size]),
            'generated_at': __import__('datetime').datetime.now().isoformat()
        }

        # Save style profile
        os.makedirs(os.path.dirname(args.out) if os.path.dirname(args.out) else '.', exist_ok=True)
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(style_data, f, indent=2, ensure_ascii=False)

        log.info(f"Style profile saved to: {args.out}")
        log.info(f"Analyzed {len(chapter_texts[:s.style_sample_size])} chapters")
        console.print("[green]OK[/green] Style analysis complete.")

    elif args.cmd == "multiturn-pro":
        """Production-quality 5-turn rewrite with validation."""
        _check_multiturn_env(s)

        # Convert 1-based to 0-based
        chapter_idx = args.chapter_idx - 1
        log.info(f"Production 5-turn rewrite: chapter {args.chapter_idx} (index {chapter_idx})...")

        # Load additional resources
        if os.path.exists(args.character_ledger):
            ledger = load_ledger(args.character_ledger)
            log.info(f"Loaded character ledger: {len(ledger.characters)} characters")
        else:
            log.warning(f"Character ledger not found: {args.character_ledger}")
            ledger = None

        style_profile = None
        if args.style_profile and os.path.exists(args.style_profile):
            with open(args.style_profile, 'r', encoding='utf-8') as f:
                style_profile = json.load(f)
            log.info(f"Loaded style profile")

        # For now, use the existing 3-turn rewrite
        # TODO: Implement full 5-turn pipeline with validation
        log.info("Using enhanced 3-turn pipeline with validation...")

        docx_path = args.docx if args.docx else None
        out = rewrite_chapter_multiturn(
            chapter_idx=chapter_idx,
            s=s,
            book_bible_path=args.bible,
            out_path=args.out,
            docx_path=docx_path,
            rewrites_dir="rewrites",
            save_intermediate=args.save_intermediate,
        )

        # Validate the result if enabled
        if s.enable_validation and ledger:
            log.info("Running validation on rewritten chapter...")
            with open(out, 'r', encoding='utf-8') as f:
                chapter_text = f.read()

            report = validate_chapter_continuity(
                chapter_text=chapter_text,
                chapter_idx=chapter_idx,
                character_ledger=ledger,
                previous_chapters=[],
                target_min=s.target_word_count_min,
                target_max=s.target_word_count_max
            )

            print_validation_report(report)

            # Save validation report to book_validator folder
            os.makedirs("book_validator", exist_ok=True)
            chapter_name = os.path.basename(out).replace('.md', '')
            validation_path = f"book_validator/{chapter_name}_validation.json"
            save_validation_report(report, validation_path)
            log.info(f"Validation report saved to: {validation_path}")

        log.info(f"Production rewrite written to: {out}")
        console.print("[green]OK[/green] Production rewrite complete.")

if __name__ == "__main__":
    main()
