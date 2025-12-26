# Book Rewriter (DOCX → Local Vector Store → Kimi K2 Editing)

A production-ready pipeline to turn an old DOCX draft into a publishable rewrite while avoiding context drift.

It does:
- Parse a DOCX manuscript
- Split into chapters (supports `Chapter N: Title`)
- Ignores TOC dot-leader lines (`Chapter 21: Jacob .... 89`)
- Chunk + embed locally (Mistral embeddings)
- Store vectors in a local FAISS index
- Create a global “Book Bible” using Kimi K2 (Nebius OpenAI-compatible)
- Rewrite chapters with retrieval + global constraints

## Why this workflow
Editing “chapter by chapter” in isolation causes drift: characters change, tone shifts, continuity breaks.
This pipeline keeps a global memory (Book Bible) and injects relevant context into every rewrite.



## Setup

### 1) Install
```bash
pip install -r requirements.txt
````

### 2) Environment variables

Copy `.env.example` → `.env` and fill keys:

```bash
NEBIUS_API_KEY=...
MISTRAL_API_KEY=...
```


## Commands

### Index your DOCX

Build a local vector store from the manuscript:

```bash
python -m book_rewriter.cli index "YourBook.docx"
```

### Sanity check chapter splitting

Exports exact chapter text so you can confirm the splitter is correct:

```bash
python -m book_rewriter.cli export-chapters "YourBook.docx" --out chapters.json
```

### Create the Book Bible

This uses retrieval from the local index + Kimi K2:

```bash
python -m book_rewriter.cli bible --out book_bible.md
```

### Rewrite a chapter

Requires `book_bible.md`:

```bash
python -m book_rewriter.cli rewrite 3 --bible book_bible.md
```

Output default: `rewrites/chapter_03.md`

### Search the manuscript memory

```bash
python -m book_rewriter.cli search "Where does the protagonist first lie?" --k 10
```



## Notes

* Embeddings: Mistral `mistral-embed`
* Retrieval: cosine similarity via L2-normalized vectors + inner product FAISS index
* Kimi K2: accessed via Nebius OpenAI-compatible endpoint
* If your chapter headings use different formatting, edit `book_rewriter/splitter.py`



## Next improvements (optional)

* Add exact-chapter rewrite (no excerpt stitching) by storing chapter boundaries + concatenating all chunks for that chapter
* Add “continuity checker” command: scan for contradictions vs Book Bible
* Add “style sheet” extraction for voice consistency


## How to run (quick)

```bash
# 1) index
python -m book_rewriter.cli index "YourBook.docx"

# 2) make bible
python -m book_rewriter.cli bible --out book_bible.md

# 3) rewrite chapter 1
python -m book_rewriter.cli rewrite 1 --bible book_bible.md
```

