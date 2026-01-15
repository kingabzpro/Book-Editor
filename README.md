# Book Editor

CLI pipeline to index a DOCX, build a Book Bible, and rewrite chapters with continuity and style control.

## Requirements
- Python 3.10+
- API keys: Nebius (Kimi), Mistral (embeddings), optional SambaNova (multi-turn)

## Setup
```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

## Quick start
```bash
python -m book_rewriter.cli books create "Book/MyNovel.docx"
python -m book_rewriter.cli index "Book/MyNovel.docx" --book "my_novel"
python -m book_rewriter.cli bible --docx "Book/MyNovel.docx" --book "my_novel"
python -m book_rewriter.cli rewrite 3 --book "my_novel"
```

## Commands (short form)
Book management:
```bash
python -m book_rewriter.cli books list
python -m book_rewriter.cli books create "<docx_path>" --name "<book_name>"
python -m book_rewriter.cli books set-active "<book_name>"
python -m book_rewriter.cli books delete "<book_name>" --confirm
python -m book_rewriter.cli books migrate
```

Core pipeline:
```bash
python -m book_rewriter.cli index "<docx_path>" --book "<book_name>"
python -m book_rewriter.cli bible --docx "<docx_path>" --book "<book_name>"
python -m book_rewriter.cli bible-enhanced --docx "<docx_path>" --book "<book_name>"
python -m book_rewriter.cli search "<query>"
```

Single-turn rewrite:
```bash
python -m book_rewriter.cli rewrite 3 --book "<book_name>"
python -m book_rewriter.cli rewrite-batch 1 10 --book "<book_name>" --resume
python -m book_rewriter.cli rewrite-full --book "<book_name>" --resume
```

Multi-turn rewrite (SambaNova required):
```bash
python -m book_rewriter.cli multiturn 3 --book "<book_name>"
python -m book_rewriter.cli multiturn-batch 1 10 --book "<book_name>" --resume --save-intermediate
python -m book_rewriter.cli multiturn-full --book "<book_name>" --resume --save-intermediate
```

Analysis and utilities:
```bash
python -m book_rewriter.cli analyze-structure --book "<book_name>"
python -m book_rewriter.cli extract-chars all --book "<book_name>"
python -m book_rewriter.cli analyze-style --chapters 0-2 --book "<book_name>"
python -m book_rewriter.cli validate-chapter "books/<book_name>/rewrites/chapter_03.md"
python -m book_rewriter.cli edit "books/<book_name>/rewrites/chapter_03.md" "add more sensory detail"
```

Notes:
- Chapters are 1-based for `rewrite`, `rewrite-batch`.
- `--resume` uses a progress file and continues from the last completed chapter.
