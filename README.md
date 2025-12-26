# Book Rewriter

A pipeline to rewrite book chapters while preserving style and continuity.

## Features

- Parse DOCX manuscripts and split into chapters
- Create a global "Book Bible" for story consistency
- Rewrite chapters with expanded, vivid detail ("movie in mind" style)
- Export to PDF
- Local FAISS vector store for retrieval

## Setup

```bash
pip install -r requirements.txt
```

Copy `.env.example` → `.env` and add your API keys:
- `NEBIUS_API_KEY` - for Kimi/Nebius LLM
- `MISTRAL_API_KEY` - for embeddings

## Usage

```bash
# 1. Index your DOCX
python -m book_rewriter.cli index "Book/YourBook.docx"

# 2. Create Book Bible
python -m book_rewriter.cli bible --docx Book/YourBook.docx

# 3. Rewrite a chapter (chapter numbers are 1-based)
python -m book_rewriter.cli rewrite 3 --bible book_bible.md --docx Book/YourBook.docx

# 4. Create PDF from rewritten chapters
python create_book_pdf.py
```

## Notes

- Rewrites preserve original simple style while adding sensory detail
- No em-dashes or contractions in output
- Output: `rewrites/chapter_XX.md` files
- PDF output: `rewrites/book.pdf`
