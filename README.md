# Book Editor

Book Editor is a CLI pipeline for indexing a DOCX, generating a Book Bible, and rewriting chapters with continuity and style control.

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

## Quick start (multi-book)
```bash
# Create a book workspace
python -m book_rewriter.cli books create "Book/MyNovel.docx"

# Index and build bible
python -m book_rewriter.cli index "Book/MyNovel.docx" --book "my_novel"
python -m book_rewriter.cli bible --docx "Book/MyNovel.docx" --book "my_novel"

# Rewrite a chapter (1-based)
python -m book_rewriter.cli rewrite 3 --book "my_novel"
```

## Batch rewrite
Single-turn:
```bash
python -m book_rewriter.cli rewrite-batch 1 10 --book "my_novel"
```

Multi-turn (3-pass):
```bash
python -m book_rewriter.cli multiturn-batch 1 10 --book "my_novel" --save-intermediate
```

Notes:
- Chapters are 1-based for `rewrite` and `rewrite-batch`.
- For multi-turn, set `SAMBANOVA_API_KEY` in `.env`.
