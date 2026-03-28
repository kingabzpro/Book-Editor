#!/usr/bin/env python3
"""Book Editor — interactive CLI.

Usage:
    python -m book_rewriter.cli
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

load_dotenv()

console = Console()

# ─── paths ───────────────────────────────────────────────────────────────────
BOOKS_DIR = Path("books")
REGISTRY_FILE = Path("books_registry.json")


# ─── settings ────────────────────────────────────────────────────────────────
def _settings():
    from .config import load_settings

    return load_settings()


# ─── LLM ─────────────────────────────────────────────────────────────────────
def _chat(model_key: str, system: str, user: str, temperature: float = 0.7) -> str:
    """Call Nebius. model_key is 'kimi' or 'glm'. Raises on failure."""
    from .models import chat

    s = _settings()
    if not s.nebius_api_key:
        raise RuntimeError("NEBIUS_API_KEY is not set. Add it to your .env file.")
    model = s.kimi_model if model_key == "kimi" else s.glm_model
    console.print(f"  [dim]Model: {model}[/dim]")
    result = chat(s.nebius_api_key, s.nebius_base_url, model, system, user, temperature)
    if not result or not result.strip():
        raise RuntimeError(
            f"Model returned an empty response. Check that '{model}' is available on Nebius."
        )
    return result


# ─── registry ────────────────────────────────────────────────────────────────
def _load_registry() -> Dict:
    if REGISTRY_FILE.exists():
        return json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
    return {"active_book": None, "books": {}}


def _save_registry(reg: Dict):
    REGISTRY_FILE.write_text(
        json.dumps(reg, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _active_book() -> Optional[str]:
    return _load_registry().get("active_book")


def _ask_docx_path(prompt: str = "  Path to DOCX file") -> Optional[Path]:
    """Ask for a DOCX path, normalise it, and show available files if not found."""
    raw = Prompt.ask(prompt).strip().strip('"').strip("'")
    p = Path(raw.replace("\\", "/"))
    if p.exists():
        return p
    console.print(f"  [red]File not found:[/red] {p}")
    available = sorted(Path("books").glob("*/source/*.docx"))
    if available:
        console.print("  Available DOCX files in your books folder:")
        for f in available:
            console.print(f"    [cyan]{f}[/cyan]")
    return None


def _set_active(name: str):
    reg = _load_registry()
    reg["active_book"] = name
    _save_registry(reg)


# ─── book paths ──────────────────────────────────────────────────────────────
def _book_dir(name: str) -> Path:
    return BOOKS_DIR / name


def _chapters_file(name: str) -> Path:
    return _book_dir(name) / "chapters.json"


def _bible_file(name: str) -> Path:
    return _book_dir(name) / "bible.md"


def _rewrites_dir(name: str) -> Path:
    return _book_dir(name) / "rewrites"


def _rewrite_path(name: str, idx: int) -> Path:
    return _rewrites_dir(name) / f"chapter-{idx + 1:02d}.md"


# ─── chapter I/O ─────────────────────────────────────────────────────────────
def _load_chapters(name: str) -> List[Dict]:
    f = _chapters_file(name)
    if not f.exists():
        return []
    return json.loads(f.read_text(encoding="utf-8"))


def _save_chapters(name: str, chapters: List[Dict]):
    _chapters_file(name).write_text(
        json.dumps(chapters, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _load_bible(name: str) -> str:
    f = _bible_file(name)
    return f.read_text(encoding="utf-8") if f.exists() else ""


def _rewritten_indices(name: str) -> List[int]:
    """Return 0-based indices of chapters that have a rewrite file.

    Handles two naming conventions so old runs are detected automatically:
      new format  chapter-01.md  →  1-indexed  →  index = N - 1
      old format  chapter_00.md  →  0-indexed  →  index = N
    """
    d = _rewrites_dir(name)
    if not d.exists():
        return []
    done: set[int] = set()
    for p in d.iterdir():
        if p.suffix != ".md":
            continue
        m = re.match(r"chapter-(\d+)\.md", p.name)  # new: chapter-01.md
        if m:
            done.add(int(m.group(1)) - 1)
            continue
        m = re.match(r"chapter_(\d+)\.md", p.name)  # old: chapter_00.md
        if m:
            done.add(int(m.group(1)))
    return sorted(done)


# ─── context building ─────────────────────────────────────────────────────────
def _build_context(chapters: List[Dict], idx: int) -> str:
    s = _settings()
    parts = []
    prev_start = max(0, idx - s.prev_chapters)
    for i in range(prev_start, idx):
        ch = chapters[i]
        parts.append(
            f"[PREVIOUS — Chapter {i + 1}: {ch['title']}]\n{ch['text'][:3000]}"
        )
    next_end = min(len(chapters), idx + 1 + s.next_chapters)
    for i in range(idx + 1, next_end):
        ch = chapters[i]
        parts.append(
            f"[UPCOMING — Chapter {i + 1}: {ch['title']}]\n{ch['text'][:1000]}"
        )
    if not parts:
        return ""
    header = "═══ SURROUNDING CHAPTERS (for context only — do not rewrite these) ═══"
    return header + "\n\n" + "\n\n---\n\n".join(parts)


# ─── DOCX loading ────────────────────────────────────────────────────────────
def _load_docx(docx_path: str, book_name: str) -> List[Dict]:
    from .docx_reader import read_docx_paragraphs
    from .splitter import split_into_chapters
    from .utils import join_paras

    console.print(f"  Reading [cyan]{docx_path}[/cyan]...")
    paras = read_docx_paragraphs(docx_path)
    raw = split_into_chapters(paras)
    chapters = []
    for i, ch in enumerate(raw):
        text = join_paras(ch["paras"])
        if text.strip():
            chapters.append(
                {"idx": i, "title": ch["title"] or f"Chapter {i + 1}", "text": text}
            )
    return chapters


# ─── book management helpers ─────────────────────────────────────────────────
def _ensure_book_dirs(name: str):
    for sub in ["", "rewrites"]:
        (_book_dir(name) / sub).mkdir(parents=True, exist_ok=True)


def _register_book(name: str, display: str, total: int):
    reg = _load_registry()
    reg.setdefault("books", {})[name] = {
        "display_name": display,
        "total_chapters": total,
    }
    if not reg.get("active_book"):
        reg["active_book"] = name
    _save_registry(reg)


def _sanitize(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*]', "", name)
    name = name.strip().replace(" ", "_").lower()
    return name[:50]


def _slugify(name: str) -> str:
    """Produce a clean hyphen-separated slug for front matter."""
    name = re.sub(r'[<>:"/\\|?*]', "", name)
    name = name.strip().replace(" ", "-").replace("_", "-").lower()
    name = re.sub(r"-{2,}", "-", name)
    return name[:60]


# ─── rewrite / bible helpers ─────────────────────────────────────────────────
def _do_rewrite(book: str, chapters: List[Dict], idx: int, model: str = "kimi") -> str:
    from .prompts import REWRITE_SYSTEM, REWRITE_USER_TEMPLATE

    s = _settings()
    ch = chapters[idx]
    bible = _load_bible(book)
    bible_block = (
        f"═══ BOOK BIBLE ═══\n{bible[:4000]}" if bible else "(no book bible yet)"
    )
    context_block = _build_context(chapters, idx)

    user_prompt = REWRITE_USER_TEMPLATE.format(
        target_min=s.target_min,
        target_max=s.target_max,
        bible_block=bible_block,
        context_block=context_block,
        chapter_title=ch["title"],
        chapter_text=ch["text"],
    )
    return _chat(model, REWRITE_SYSTEM, user_prompt, temperature=0.7)


def _clean_text(text: str) -> str:
    """Strip leading/trailing whitespace and fix indented heading lines."""
    lines = []
    for line in text.splitlines():
        # Remove leading spaces from markdown headings
        stripped = line.lstrip()
        if stripped.startswith("#"):
            lines.append(stripped)
        else:
            lines.append(line.rstrip())
    return "\n".join(lines).strip()


def _save_rewrite(book: str, idx: int, title: str, original_text: str, rewritten_text: str):
    _rewrites_dir(book).mkdir(parents=True, exist_ok=True)
    book_slug = _slugify(book)
    chapter_num = idx + 1
    full_title = f"Chapter {chapter_num}"
    front = (
        f"---\n"
        f'book: "{book_slug}"\n'
        f'title: "{full_title}"\n'
        f"order: {chapter_num}\n"
        f"---\n\n"
    )
    _rewrite_path(book, idx).write_text(front + _clean_text(rewritten_text) + "\n", encoding="utf-8")


def _word_count(text: str) -> int:
    return len(text.split())


def _build_bible_excerpts(chapters: List[Dict], chars_per_chapter: int = 3500) -> str:
    """Sample chapters spread across the whole book for a representative bible.

    Takes: first 3, last 2, and up to 5 evenly spaced from the middle.
    """
    n = len(chapters)
    if n <= 10:
        sampled = chapters
    else:
        first = chapters[:3]
        last = chapters[-2:]
        middle = chapters[3:-2]
        step = max(1, len(middle) // 5)
        mid_sample = middle[::step][:5]
        seen = {ch["idx"] for ch in first + last + mid_sample}
        sampled = sorted(first + mid_sample + last, key=lambda c: c["idx"])

    return "\n\n---\n\n".join(
        f"[Chapter {ch['idx'] + 1}: {ch['title']}]\n{ch['text'][:chars_per_chapter]}"
        for ch in sampled
    )


def _first_unwritten(chapters: List[Dict], done: List[int]) -> Optional[int]:
    """Return 0-based index of the first chapter without a rewrite, or None if all done."""
    done_set = set(done)
    for ch in chapters:
        if ch["idx"] not in done_set:
            return ch["idx"]
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# MENU ACTIONS
# ═══════════════════════════════════════════════════════════════════════════════


def _action_books():
    """Books sub-menu."""
    while True:
        reg = _load_registry()
        active = reg.get("active_book")
        books = reg.get("books", {})

        console.print()
        console.rule("[bold]Books[/bold]")
        if books:
            t = Table(show_header=True, header_style="bold cyan")
            t.add_column("#", style="dim", width=4)
            t.add_column("Name")
            t.add_column("Display Name")
            t.add_column("Chapters", justify="right")
            t.add_column("Active", justify="center")
            for i, (k, v) in enumerate(books.items(), 1):
                mark = "[green]✓[/green]" if k == active else ""
                t.add_row(
                    str(i),
                    k,
                    v.get("display_name", k),
                    str(v.get("total_chapters", "?")),
                    mark,
                )
            console.print(t)
        else:
            console.print("  [dim]No books yet.[/dim]")

        console.print()
        console.print("  [1] Select active book")
        console.print("  [2] Create book from DOCX")
        console.print("  [3] Delete a book")
        console.print("  [b] Back")
        console.print()
        choice = Prompt.ask("  Choice", default="b").strip().lower()

        if choice == "b":
            break
        elif choice == "1":
            _action_select_book(books)
        elif choice == "2":
            _action_create_book()
        elif choice == "3":
            _action_delete_book(books)


def _action_select_book(books: Dict):
    if not books:
        console.print("  [yellow]No books to select.[/yellow]")
        return
    keys = list(books.keys())
    for i, k in enumerate(keys, 1):
        console.print(f"  [{i}] {k}")
    raw = Prompt.ask("  Select number").strip()
    try:
        n = int(raw) - 1
        if 0 <= n < len(keys):
            _set_active(keys[n])
            console.print(f"  [green]Active book → {keys[n]}[/green]")
        else:
            console.print("  [red]Invalid selection.[/red]")
    except ValueError:
        console.print("  [red]Enter a number.[/red]")


def _action_create_book():
    docx = _ask_docx_path()
    if not docx:
        return

    display = Prompt.ask("  Book display name", default=Path(docx).stem).strip()
    name = _sanitize(display)

    if (_book_dir(name) / "chapters.json").exists():
        if not Confirm.ask(f"  '{name}' already exists. Overwrite?", default=False):
            return

    _ensure_book_dirs(name)
    with Progress(
        SpinnerColumn(), TextColumn("{task.description}"), console=console
    ) as p:
        p.add_task("  Parsing DOCX...", total=None)
        chapters = _load_docx(docx, name)

    if not chapters:
        console.print("  [red]No chapters found. Check the DOCX formatting.[/red]")
        return

    _save_chapters(name, chapters)
    _register_book(name, display, len(chapters))
    _set_active(name)
    console.print(
        f"  [green]Created '{name}' with {len(chapters)} chapters.[/green]  "
        f"Active book → {name}"
    )


def _action_delete_book(books: Dict):
    if not books:
        return
    keys = list(books.keys())
    for i, k in enumerate(keys, 1):
        console.print(f"  [{i}] {k}")
    raw = Prompt.ask("  Select number to delete").strip()
    try:
        n = int(raw) - 1
        if 0 <= n < len(keys):
            target = keys[n]
            if Confirm.ask(
                f"  Delete '{target}'? This removes all rewrites.", default=False
            ):
                import shutil

                shutil.rmtree(_book_dir(target), ignore_errors=True)
                reg = _load_registry()
                reg["books"].pop(target, None)
                if reg.get("active_book") == target:
                    remaining = list(reg["books"].keys())
                    reg["active_book"] = remaining[0] if remaining else None
                _save_registry(reg)
                console.print(f"  [green]Deleted '{target}'.[/green]")
    except ValueError:
        console.print("  [red]Enter a number.[/red]")


def _action_load_docx():
    book = _active_book()
    if not book:
        console.print("  [yellow]No active book. Create one first.[/yellow]")
        return

    docx = _ask_docx_path()
    if not docx:
        return

    if Confirm.ask("  This will overwrite existing chapters. Continue?", default=True):
        with Progress(
            SpinnerColumn(), TextColumn("{task.description}"), console=console
        ) as p:
            p.add_task("  Parsing DOCX...", total=None)
            chapters = _load_docx(docx, book)
        if not chapters:
            console.print("  [red]No chapters found.[/red]")
            return
        _save_chapters(book, chapters)
        # Update chapter count in registry
        reg = _load_registry()
        reg["books"].setdefault(book, {})["total_chapters"] = len(chapters)
        _save_registry(reg)
        console.print(
            f"  [green]Loaded {len(chapters)} chapters into '{book}'.[/green]"
        )


def _action_bible():
    """Generate or view the Book Bible."""
    book = _active_book()
    if not book:
        console.print("  [yellow]No active book.[/yellow]")
        return

    bible = _load_bible(book)
    if bible:
        console.print()
        console.rule("[bold]Book Bible[/bold]")
        console.print(bible[:3000])
        if len(bible) > 3000:
            console.print(
                f"  [dim]... ({len(bible)} chars total — see {_bible_file(book)})[/dim]"
            )
        console.print()
        if not Confirm.ask("  Regenerate?", default=False):
            return

    chapters = _load_chapters(book)
    if not chapters:
        console.print("  [yellow]No chapters loaded. Use 'Load DOCX' first.[/yellow]")
        return

    from .prompts import BIBLE_SYSTEM, BIBLE_USER_TEMPLATE

    excerpts = _build_bible_excerpts(chapters)
    reg = _load_registry()
    book_display = reg.get("books", {}).get(book, {}).get("display_name", book)
    user_prompt = BIBLE_USER_TEMPLATE.format(
        book_title=book_display,
        total_chapters=len(chapters),
        excerpt_count=excerpts.count("[Chapter "),
        excerpts=excerpts,
    )

    console.print("  Generating Book Bible with GLM model...")
    try:
        result = _chat("glm", BIBLE_SYSTEM, user_prompt, temperature=0.3)
    except Exception as e:
        console.print(f"  [red]Bible generation failed: {e}[/red]")
        return

    _bible_file(book).write_text(result, encoding="utf-8")
    console.print(f"  [green]Bible saved to {_bible_file(book)}[/green]")
    console.print()
    console.print(result[:2000])
    if len(result) > 2000:
        console.print("  [dim]... (truncated — full bible in file)[/dim]")


def _action_rewrite():
    book = _active_book()
    if not book:
        console.print("  [yellow]No active book.[/yellow]")
        return

    chapters = _load_chapters(book)
    if not chapters:
        console.print("  [yellow]No chapters loaded. Use 'Load DOCX' first.[/yellow]")
        return

    done = _rewritten_indices(book)
    _show_progress_table(book, chapters, done)

    console.print()
    idx = IntPrompt.ask(f"  Chapter number to rewrite (1–{len(chapters)})") - 1
    if not (0 <= idx < len(chapters)):
        console.print("  [red]Invalid chapter number.[/red]")
        return

    ch = chapters[idx]
    console.print(f"  Chapter {idx + 1}: [cyan]{ch['title']}[/cyan]")
    console.print(f"  Original: {_word_count(ch['text'])} words")
    if idx in done:
        if not Confirm.ask("  Already rewritten. Overwrite?", default=True):
            return

    s = _settings()
    console.print(f"  Model: [cyan]{s.kimi_model}[/cyan] (Kimi fast)")
    console.print()

    with Progress(
        SpinnerColumn(), TextColumn("{task.description}"), console=console
    ) as p:
        p.add_task(f"  Rewriting chapter {idx + 1}...", total=None)
        result = _do_rewrite(book, chapters, idx)

    _save_rewrite(book, idx, ch["title"], ch["text"], result)
    wc = _word_count(result)
    console.print(f"  [green]Done![/green]  {wc} words → {_rewrite_path(book, idx)}")


def _action_batch_rewrite():
    book = _active_book()
    if not book:
        console.print("  [yellow]No active book.[/yellow]")
        return

    chapters = _load_chapters(book)
    if not chapters:
        console.print("  [yellow]No chapters loaded.[/yellow]")
        return

    done = _rewritten_indices(book)
    _show_progress_table(book, chapters, done)

    first_todo = _first_unwritten(chapters, done)
    default_start = (first_todo + 1) if first_todo is not None else 1

    console.print()
    if done and first_todo is not None:
        console.print(
            f"  [yellow]Resuming from chapter {first_todo + 1}[/yellow]"
            f"  [dim]({len(done)}/{len(chapters)} already done)[/dim]"
        )
    start = (
        IntPrompt.ask(f"  Start chapter (1–{len(chapters)})", default=default_start) - 1
    )
    end = IntPrompt.ask(f"  End chapter (1–{len(chapters)})", default=len(chapters)) - 1

    if not (0 <= start <= end < len(chapters)):
        console.print("  [red]Invalid range.[/red]")
        return

    skip_done = Confirm.ask("  Skip already-rewritten chapters?", default=True)
    to_do = [i for i in range(start, end + 1) if not skip_done or i not in done]

    if not to_do:
        console.print(
            "  [green]Nothing to do — all chapters in range are already rewritten.[/green]"
        )
        return

    s = _settings()
    console.print(
        f"\n  Rewriting {len(to_do)} chapters with [cyan]{s.kimi_model}[/cyan]\n"
    )

    errors = []
    for pos, idx in enumerate(to_do, 1):
        ch = chapters[idx]
        console.print(f"  [{pos}/{len(to_do)}] Chapter {idx + 1}: {ch['title']}")
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("{task.description}"),
                console=console,
                transient=True,
            ) as p:
                p.add_task("  Calling model...", total=None)
                result = _do_rewrite(book, chapters, idx)
            _save_rewrite(book, idx, ch["title"], ch["text"], result)
            wc = _word_count(result)
            console.print(f"       [green]✓[/green] {wc} words")
        except Exception as e:
            console.print(f"       [red]✗ Error: {e}[/red]")
            errors.append((idx + 1, str(e)))

    console.print()
    if errors:
        console.print(f"  [yellow]Completed with {len(errors)} error(s):[/yellow]")
        for ch_num, err in errors:
            console.print(f"    Chapter {ch_num}: {err}")
    else:
        console.print(f"  [green]All {len(to_do)} chapters rewritten.[/green]")


def _action_edit():
    book = _active_book()
    if not book:
        console.print("  [yellow]No active book.[/yellow]")
        return

    done = _rewritten_indices(book)
    chapters = _load_chapters(book)

    if not done:
        console.print("  [yellow]No rewritten chapters to edit yet.[/yellow]")
        return

    console.print(f"  Rewritten chapters: {', '.join(str(i + 1) for i in done)}")
    idx = IntPrompt.ask(f"  Chapter number to edit (1–{len(chapters)})") - 1
    if idx not in done:
        console.print(
            "  [yellow]That chapter has not been rewritten yet. Run 'Rewrite' first.[/yellow]"
        )
        return

    path = _rewrite_path(book, idx)
    current_text = path.read_text(encoding="utf-8")

    console.print()
    instruction = Prompt.ask("  Edit instruction").strip()
    if not instruction:
        return

    from .prompts import EDIT_SYSTEM, EDIT_USER_TEMPLATE

    user_prompt = EDIT_USER_TEMPLATE.format(
        instruction=instruction, chapter_text=current_text
    )

    with Progress(
        SpinnerColumn(), TextColumn("{task.description}"), console=console
    ) as p:
        p.add_task("  Applying edit...", total=None)
        result = _chat("kimi", EDIT_SYSTEM, user_prompt, temperature=0.5)

    # Preserve front matter
    if current_text.startswith("---\n"):
        parts = current_text.split("---\n", 2)
        if len(parts) >= 3:
            front = "---\n" + parts[1] + "---\n\n"
            result = front + result.lstrip()

    path.write_text(result, encoding="utf-8")
    console.print(f"  [green]Saved edited chapter to {path}[/green]")


def _action_auto():
    """Full auto pipeline: DOCX → chapters → Bible → rewrite all → done."""
    console.print()
    console.rule("[bold green]AUTO MODE — full pipeline[/bold green]")
    console.print(
        "  This will:\n"
        "  [cyan]1)[/cyan] Load a DOCX and create a new book\n"
        "  [cyan]2)[/cyan] Generate the Book Bible  [dim][GLM][/dim]\n"
        "  [cyan]3)[/cyan] Rewrite every chapter  [dim][Kimi][/dim]\n"
    )

    docx = _ask_docx_path()
    if not docx:
        return

    display = Prompt.ask("  Book name", default=docx.stem).strip()
    name = _sanitize(display)

    s = _settings()
    if not s.nebius_api_key:
        console.print(
            "  [red]NEBIUS_API_KEY is not set. Add it to your .env file.[/red]"
        )
        return

    console.print(
        f"\n  Book   : [cyan]{display}[/cyan] → [dim]{name}[/dim]\n"
        f"  Kimi   : [cyan]{s.kimi_model}[/cyan]\n"
        f"  GLM    : [cyan]{s.glm_model}[/cyan]\n"
        f"  Target : {s.target_min}–{s.target_max} words/chapter\n"
    )
    if not Confirm.ask("  Start?", default=True):
        return

    # ── Step 1: parse DOCX ────────────────────────────────────────────────────
    console.print("\n[bold cyan]Step 1/3 — Parsing DOCX[/bold cyan]")
    if (_book_dir(name) / "chapters.json").exists():
        if not Confirm.ask(f"  '{name}' already exists. Overwrite?", default=False):
            return
    _ensure_book_dirs(name)

    with Progress(
        SpinnerColumn(), TextColumn("{task.description}"), console=console
    ) as p:
        p.add_task("  Parsing...", total=None)
        chapters = _load_docx(docx, name)

    if not chapters:
        console.print("  [red]No chapters found. Check the DOCX formatting.[/red]")
        return

    _save_chapters(name, chapters)
    _register_book(name, display, len(chapters))
    _set_active(name)
    console.print(f"  [green]✓[/green] {len(chapters)} chapters loaded")

    # ── Step 2: generate Bible ────────────────────────────────────────────────
    console.print("\n[bold cyan]Step 2/3 — Generating Book Bible[/bold cyan]")
    from .prompts import BIBLE_SYSTEM, BIBLE_USER_TEMPLATE

    excerpts = _build_bible_excerpts(chapters)
    try:
        bible_text = _chat(
            "glm",
            BIBLE_SYSTEM,
            BIBLE_USER_TEMPLATE.format(
                book_title=display,
                total_chapters=len(chapters),
                excerpt_count=excerpts.count("[Chapter "),
                excerpts=excerpts,
            ),
            temperature=0.3,
        )
    except Exception as e:
        console.print(f"  [red]Bible generation failed: {e}[/red]")
        console.print(
            "  [yellow]Continuing without a Bible — rewrites will use chapter context only.[/yellow]"
        )
        bible_text = ""

    if bible_text:
        _bible_file(name).write_text(bible_text, encoding="utf-8")
        console.print(f"  [green]✓[/green] Bible saved → {_bible_file(name)}")

    # ── Step 3: rewrite all chapters ─────────────────────────────────────────
    already_done = _rewritten_indices(name)
    to_write = [ch for ch in chapters if ch["idx"] not in set(already_done)]
    console.print(
        f"\n[bold cyan]Step 3/3 — Rewriting chapters[/bold cyan]  "
        f"[dim]{len(to_write)} to do, {len(already_done)} already done[/dim]"
    )
    errors = []
    for pos, ch in enumerate(to_write, 1):
        real_idx = ch["idx"]
        console.print(
            f"  [{pos}/{len(to_write)}] Chapter {real_idx + 1}: {ch['title']}"
        )
        try:
            result = _do_rewrite(name, chapters, real_idx)
            _save_rewrite(name, real_idx, ch["title"], ch["text"], result)
            wc = _word_count(result)
            console.print(f"       [green]✓[/green] {wc} words")
        except KeyboardInterrupt:
            console.print(
                "\n  [yellow]Interrupted — progress saved. Run Batch Rewrite to resume.[/yellow]"
            )
            return
        except Exception as e:
            console.print(f"       [red]✗ Error: {e}[/red]")
            errors.append((real_idx + 1, str(e)))

    # ── Summary ───────────────────────────────────────────────────────────────
    console.print()
    done = _rewritten_indices(name)
    if errors:
        console.print(f"  [yellow]Done with {len(errors)} error(s).[/yellow]")
        for ch_num, err in errors:
            console.print(f"    Chapter {ch_num}: {err}")
    else:
        console.print(
            f"  [bold green]✓ All {len(chapters)} chapters rewritten![/bold green]"
        )
    console.print(f"  Rewrites in: [cyan]{_rewrites_dir(name)}/[/cyan]")
    console.print(f"  Bible in   : [cyan]{_bible_file(name)}[/cyan]")


def _action_progress():
    book = _active_book()
    if not book:
        console.print("  [yellow]No active book.[/yellow]")
        return
    chapters = _load_chapters(book)
    done = _rewritten_indices(book)
    _show_progress_table(book, chapters, done)


def _action_settings():
    s = _settings()
    t = Table(show_header=False, box=None, padding=(0, 2))
    t.add_column("Key", style="dim")
    t.add_column("Value", style="cyan")
    t.add_row(
        "Nebius API Key",
        ("*" * 8 + s.nebius_api_key[-4:]) if s.nebius_api_key else "[red]NOT SET[/red]",
    )
    t.add_row("Nebius Base URL", s.nebius_base_url)
    t.add_row("Kimi model (fast)", s.kimi_model)
    t.add_row("GLM model (analysis)", s.glm_model)
    t.add_row("Target word count", f"{s.target_min}–{s.target_max}")
    t.add_row("Context: prev chapters", str(s.prev_chapters))
    t.add_row("Context: next chapters", str(s.next_chapters))
    console.print()
    console.rule("[bold]Settings[/bold]")
    console.print(t)
    console.print()
    console.print("  Edit [cyan].env[/cyan] to change these values.")


# ─── shared UI ───────────────────────────────────────────────────────────────
def _show_progress_table(book: str, chapters: List[Dict], done: List[int]):
    t = Table(show_header=True, header_style="bold cyan")
    t.add_column("#", style="dim", width=4)
    t.add_column("Title")
    t.add_column("Words (orig)", justify="right")
    t.add_column("Rewritten", justify="center")

    for ch in chapters:
        i = ch["idx"]
        mark = "[green]✓[/green]" if i in done else "[dim]·[/dim]"
        wc = str(_word_count(ch["text"]))
        t.add_row(str(i + 1), ch["title"], wc, mark)

    console.print()
    console.rule(f"[bold]Progress — {book}[/bold]")
    console.print(t)
    pct = int(100 * len(done) / len(chapters)) if chapters else 0
    console.print(f"  {len(done)}/{len(chapters)} chapters rewritten ({pct}%)")


def _header():
    book = _active_book()
    reg = _load_registry()
    s = _settings()

    if book and book in reg.get("books", {}):
        info = reg["books"][book]
        chapters = _load_chapters(book)
        done = _rewritten_indices(book)
        subtitle = (
            f"[bold cyan]{info.get('display_name', book)}[/bold cyan]  "
            f"[dim]{len(chapters)} chapters • {len(done)} rewritten[/dim]"
        )
    else:
        subtitle = "[dim]No active book — select or create one[/dim]"

    model_line = f"[dim]Kimi:[/dim] {s.kimi_model}  [dim]GLM:[/dim] {s.glm_model}"

    console.print(
        Panel(
            f"[bold white]📚 Book Editor[/bold white]\n{subtitle}\n{model_line}",
            border_style="blue",
            padding=(0, 2),
        )
    )


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN LOOP
# ═══════════════════════════════════════════════════════════════════════════════

_MENU = [
    (
        "a",
        "AUTO           ",
        "full pipeline: DOCX → Bible → rewrite all chapters",
        _action_auto,
    ),
    ("-", "", "", None),  # visual separator
    ("1", "Books          ", "select / create / manage books", _action_books),
    ("2", "Load DOCX      ", "parse a .docx into chapters", _action_load_docx),
    ("3", "Bible          ", "generate or view the Book Bible  [GLM]", _action_bible),
    ("4", "Rewrite        ", "rewrite one chapter  [Kimi]", _action_rewrite),
    (
        "5",
        "Batch Rewrite  ",
        "rewrite a range of chapters  [Kimi]",
        _action_batch_rewrite,
    ),
    (
        "6",
        "Edit           ",
        "apply a targeted edit to a chapter  [Kimi]",
        _action_edit,
    ),
    ("7", "Progress       ", "show which chapters are done", _action_progress),
    ("8", "Settings       ", "show current configuration", _action_settings),
]


def _resume_prompt() -> Optional[str]:
    """On startup, check for partial progress and offer smart shortcuts.

    Returns an action key to run immediately ('5' = batch rewrite, 'a' = auto),
    or None to just show the menu.
    """
    book = _active_book()
    if not book:
        return None

    chapters = _load_chapters(book)
    if not chapters:
        # No chapters.json yet — check if the source DOCX is known
        reg = _load_registry()
        source = reg.get("books", {}).get(book, {}).get("source_file", "")
        if source and Path(source).exists():
            console.print(
                f"\n  [yellow]Book '{book}' has no chapters loaded yet.[/yellow]\n"
                f"  Source DOCX found: [cyan]{source}[/cyan]"
            )
            if Confirm.ask("  Load chapters from DOCX now?", default=True):
                with Progress(
                    SpinnerColumn(), TextColumn("{task.description}"), console=console
                ) as p:
                    p.add_task("  Parsing...", total=None)
                    chapters = _load_docx(source, book)
                if chapters:
                    _save_chapters(book, chapters)
                    reg["books"][book]["total_chapters"] = len(chapters)
                    _save_registry(reg)
                    console.print(f"  [green]Loaded {len(chapters)} chapters.[/green]")
        return None

    done = _rewritten_indices(book)
    total = len(chapters)
    first_todo = _first_unwritten(chapters, done)

    if not done:
        return None  # nothing started yet — just show menu normally

    if first_todo is None:
        # All done
        console.print(
            f"\n  [green]All {total} chapters of '{book}' are already rewritten.[/green]\n"
            f"  Use [cyan]Edit (6)[/cyan] to refine individual chapters, or select a different book."
        )
        return None

    # Partial progress
    remaining = total - len(done)
    console.print(
        f"\n  [yellow]Resuming '{book}'[/yellow]  "
        f"[dim]{len(done)}/{total} done — {remaining} remaining[/dim]\n"
        f"  Next up: Chapter {first_todo + 1}"
    )
    if Confirm.ask("  Continue batch rewriting from here?", default=True):
        return "5"  # jump straight into batch rewrite
    return None


def main():
    BOOKS_DIR.mkdir(exist_ok=True)
    # One-time startup resume check
    console.clear()
    jump_to = _resume_prompt()

    while True:
        console.clear()
        _header()
        console.print()
        for key, label, desc, fn in _MENU:
            if fn is None:
                console.print(f"  [dim]{'-' * 40}[/dim]")
            elif key == "a":
                console.print(
                    f"  [bold green]{key}[/bold green]  [bold green]{label}[/bold green] [dim]{desc}[/dim]"
                )
            else:
                console.print(
                    f"  [bold cyan]{key}[/bold cyan]  [bold]{label}[/bold] [dim]{desc}[/dim]"
                )
        console.print("  [bold cyan]q[/bold cyan]  [bold]Quit[/bold]")
        console.print()

        if jump_to:
            choice = jump_to
            jump_to = None  # only fires once
        else:
            choice = Prompt.ask("  Choose", default="q").strip().lower()

        if choice == "q":
            console.print("[dim]Bye.[/dim]")
            break

        action = next((fn for k, _, _, fn in _MENU if k == choice), None)
        if action:
            console.print()
            try:
                action()
            except KeyboardInterrupt:
                console.print("\n  [dim]Cancelled.[/dim]")
            console.print()
            Prompt.ask("  [dim]Press Enter to continue[/dim]", default="")
        else:
            console.print(f"  [red]Unknown option: {choice}[/red]")
            import time

            time.sleep(0.8)


if __name__ == "__main__":
    main()
