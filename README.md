# Book Editor

An intelligent book rewriting pipeline that enhances your manuscript while preserving style, continuity, and character consistency. Uses multiple LLMs in a coordinated multi-turn process to produce polished, publication-ready chapters.

## Features

- **Multi-turn rewriting strategy** with specialized models for each phase
- **Character tracking** across all chapters with canonical name management
- **Style analysis** to maintain consistent voice throughout
- **Pacing control** to ensure appropriate chapter lengths
- **Continuity validation** for POV, restrictions, and character consistency
- **Enhanced Book Bible** with character registry and location inventory
- **Vector store** for efficient context retrieval
- **PDF export** for final output

## Requirements

- Python 3.10+
- API keys for Nebius (Kimi), Mistral (embeddings), and SambaNova (optional)

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd Book-Editor
```

2. Create a virtual environment (recommended):
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment variables:
```bash
cp .env.example .env
```

Edit `.env` and add your API keys:
```bash
# Required
NEBIUS_API_KEY=your_nebius_api_key_here
NEBIUS_BASE_URL=https://api.tokenfactory.nebius.com/v1/
MISTRAL_API_KEY=your_mistral_api_key_here

# Optional (for multi-turn rewrites)
SAMBANOVA_API_KEY=your_sambanova_api_key_here

# Model settings
KIMI_MODEL=moonshotai/Kimi-K2-Instruct
KIMI_INSTRUCT_MODEL=moonshotai/Kimi-K2-Instruct
KIMI_THINKING_MODEL=moonshotai/Kimi-K2-Thinking
SAMBANOVA_MODEL=deepseek-ai/DeepSeek-V3

# Character tracking
CHARACTER_LEDGER_PATH=metadata/character_ledger.json

# Style analysis
STYLE_PROFILE_PATH=metadata/style_profile.json
STYLE_SAMPLE_SIZE=3

# Validation
ENABLE_VALIDATION=true
AUTO_CORRECT_POV=true

# Pacing
TARGET_WORD_COUNT_MIN=2000
TARGET_WORD_COUNT_MAX=3500
PREVIOUS_CHAPTERS_COUNT=3
FUTURE_CHAPTERS_COUNT=2
```

## Quick Start

### Basic Workflow (Single-Turn Rewrite)

```bash
# 1. Index your DOCX file
python -m book_rewriter.cli index "Book/YourBook.docx"

# 2. Generate a Book Bible
python -m book_rewriter.cli bible --docx "Book/YourBook.docx"

# 3. Rewrite a single chapter (numbers are 1-based)
python -m book_rewriter.cli rewrite 3 --bible book_bible.md --docx "Book/YourBook.docx"

# 4. Create PDF from rewritten chapters
python create_book_pdf.py
```

### Production Workflow (Enhanced 5-Turn Rewrite)

```bash
# 1. Index your DOCX file
python -m book_rewriter.cli index "Book/YourBook.docx"

# 2. Extract characters from all chapters
python -m book_rewriter.cli extract-chars all --docx "Book/YourBook.docx"

# 3. Generate enhanced Book Bible with character registry
python -m book_rewriter.cli bible-enhanced --docx "Book/YourBook.docx" --out book_bible_enhanced.md

# 4. Analyze writing style from first 3 chapters
python -m book_rewriter.cli analyze-style --chapters 0-2 --out metadata/style_profile.json

# 5. Rewrite chapters with production-quality pipeline
python -m book_rewriter.cli multiturn-pro 3 --bible book_bible_enhanced.md

# 6. Validate output
python -m book_rewriter.cli validate-chapter rewrites/chapter_03.md

# 7. Create PDF
python create_book_pdf.py
```

## Commands Reference

### `index`
Index a DOCX file and create a vector store for context retrieval.

```bash
python -m book_rewriter.cli index <docx_path> [options]
```

**Arguments:**
- `docx_path` - Path to your DOCX manuscript

**Options:**
- `--chapter-regex` - Regex pattern to identify chapters (default: `^Chapter\s+\d+`)
- `--output-dir` - Output directory for index files (default: `metadata/`)

**Example:**
```bash
python -m book_rewriter.cli index "Book/MyNovel.docx"
```

---

### `bible`
Generate a Book Bible with story information, themes, and guidelines.

```bash
python -m book_rewriter.cli bible [options]
```

**Options:**
- `--docx` - Path to DOCX file
- `--out` - Output path for bible (default: `book_bible.md`)
- `--chapters` - Number of sample chapters to analyze (default: `3`)

**Example:**
```bash
python -m book_rewriter.cli bible --docx "Book/MyNovel.docx" --out book_bible.md
```

---

### `bible-enhanced` (NEW)
Generate an enhanced Book Bible with character registry, location inventory, and continuity rules.

```bash
python -m book_rewriter.cli bible-enhanced [options]
```

**Options:**
- `--docx` - Path to DOCX file (for base bible generation)
- `--character-ledger` - Path to character ledger JSON (default: `metadata/character_ledger.json`)
- `--out` - Output path for enhanced bible (default: `book_bible_enhanced.md`)

**Example:**
```bash
python -m book_rewriter.cli bible-enhanced --docx "Book/MyNovel.docx" --out book_bible_enhanced.md
```

**Output includes:**
- Base bible content (genre, themes, title promise)
- Character registry with physical traits, voice patterns, relationships
- Canonical name mappings for consistency
- Location inventory with details
- Object continuity tracking
- Continuity rules (POV, restrictions, naming)

---

### `extract-chars` (NEW)
Extract character information from chapters using LLM analysis.

```bash
python -m book_rewriter.cli extract-chars <chapter_idx> [options]
```

**Arguments:**
- `chapter_idx` - Chapter number (0-based) or `all` for all chapters

**Options:**
- `--docx` - Path to DOCX file (default: auto-detect)
- `--out` - Output path for character ledger (default: `metadata/character_ledger.json`)
- `--model` - Model to use for extraction (default: Kimi-K2-Instruct)

**Examples:**
```bash
# Extract from single chapter
python -m book_rewriter.cli extract-chars 0 --docx "Book/MyNovel.docx"

# Extract from all chapters
python -m book_rewriter.cli extract-chars all --docx "Book/MyNovel.docx"
```

**Extracted information:**
- Character names and aliases
- Physical traits (hair, eyes, height, build)
- Voice patterns and speech style
- Current status and situation
- Relationships with other characters

---

### `rewrite`
Rewrite a single chapter using the single-turn pipeline.

```bash
python -m book_rewriter.cli rewrite <chapter_idx> [options]
```

**Arguments:**
- `chapter_idx` - Chapter number (1-based)

**Options:**
- `--bible` - Path to book bible (default: `book_bible.md`)
- `--docx` - Path to DOCX file
- `--out` - Output path for rewritten chapter

**Example:**
```bash
python -m book_rewriter.cli rewrite 3 --bible book_bible.md --docx "Book/MyNovel.docx"
```

---

### `multiturn`
Rewrite a chapter using the 3-turn pipeline with different models.

```bash
python -m book_rewriter.cli multiturn <chapter_idx> [options]
```

**Arguments:**
- `chapter_idx` - Chapter number (0-based)

**Options:**
- `--bible` - Path to book bible (default: `book_bible.md`)
- `--docx` - Path to DOCX file
- `--save-intermediate` - Save outputs from each turn
- `--out` - Output path for final chapter

**Turn structure:**
1. **Turn 1 (SambaNova)**: Grammar baseline
2. **Turn 2 (Kimi-Instruct)**: Fill gaps with previous chapters
3. **Turn 3 (Kimi-Thinking)**: Final polish with bible + future context

**Example:**
```bash
python -m book_rewriter.cli multiturn 2 --bible book_bible.md --save-intermediate
```

---

### `multiturn-batch`
Rewrite multiple chapters in sequence using the 3-turn pipeline.

```bash
python -m book_rewriter.cli multiturn-batch <start> <end> [options]
```

**Arguments:**
- `start` - Starting chapter index (0-based)
- `end` - Ending chapter index (0-based, exclusive)

**Options:**
- `--bible` - Path to book bible
- `--docx` - Path to DOCX file
- `--save-intermediate` - Save intermediate turn outputs
- `--rewrites-dir` - Directory for output files

**Example:**
```bash
# Rewrite chapters 0-5 (chapters 1-6)
python -m book_rewriter.cli multiturn-batch 0 6 --bible book_bible.md
```

---

### `multiturn-pro` (NEW)
Production-quality rewrite with character tracking, style calibration, and validation.

```bash
python -m book_rewriter.cli multiturn-pro <chapter_idx> [options]
```

**Arguments:**
- `chapter_idx` - Chapter number (0-based)

**Options:**
- `--bible` - Path to enhanced book bible (default: `book_bible_enhanced.md`)
- `--character-ledger` - Path to character ledger (default: `metadata/character_ledger.json`)
- `--style-profile` - Path to style profile (default: `metadata/style_profile.json`)
- `--docx` - Path to DOCX file
- `--save-intermediate` - Save intermediate turn outputs
- `--out` - Output path for final chapter
- `--target-min` - Minimum word count (default: from settings)
- `--target-max` - Maximum word count (default: from settings)

**Features:**
- Loads character ledger for consistency
- Loads style profile for voice matching
- Validates output (POV, restrictions, characters, pacing)
- Generates validation report

**Example:**
```bash
python -m book_rewriter.cli multiturn-pro 3 \
  --bible book_bible_enhanced.md \
  --character-ledger metadata/character_ledger.json \
  --style-profile metadata/style_profile.json \
  --save-intermediate
```

---

### `validate-chapter` (NEW)
Validate a rewritten chapter for consistency issues.

```bash
python -m book_rewriter.cli validate-chapter <chapter_path> [options]
```

**Arguments:**
- `chapter_path` - Path to chapter markdown file

**Options:**
- `--character-ledger` - Path to character ledger (default: `metadata/character_ledger.json`)
- `--out` - Save validation report to file
- `--target-min` - Minimum word count (default: 2000)
- `--target-max` - Maximum word count (default: 3500)

**Checks performed:**
- POV consistency (first-person throughout)
- Restriction compliance (no em dashes, no contractions)
- Character name consistency
- Pacing (word count within target range)

**Example:**
```bash
python -m book_rewriter.cli validate-chapter rewrites/chapter_03.md --out validation_report.json
```

---

### `analyze-style` (NEW)
Analyze writing style from rewritten chapters and create a style profile.

```bash
python -m book_rewriter.cli analyze-style [options]
```

**Options:**
- `--chapters` - Chapter range (default: `0-2`)
- `--rewrites-dir` - Directory containing rewritten chapters (default: `rewrites`)
- `--out` - Output path for style profile (default: `metadata/style_profile.json`)

**Style metrics analyzed:**
- Sentence length distribution (mean, std, median)
- Dialogue ratio (percentage)
- Sensory description density (per 1000 words)
- Common sentence patterns
- Scene transition patterns

**Examples:**
```bash
# Analyze chapters 0-2
python -m book_rewriter.cli analyze-style --chapters 0-2

# Analyze specific chapters
python -m book_rewriter.cli analyze-style --chapters 0,2,5
```

---

### `edit`
Edit an existing chapter with specific changes.

```bash
python -m book_rewriter.cli edit <chapter_idx> [options]
```

**Arguments:**
- `chapter_idx` - Chapter number (1-based)

**Options:**
- `--request` - Edit request/prompt (required)
- `--bible` - Path to book bible
- `--docx` - Path to DOCX file
- `--out` - Output path

**Example:**
```bash
python -m book_rewriter.cli edit 3 --request "Add more dialogue between the main characters" --bible book_bible.md
```

---

## Output Files

### Directory Structure
```
Book-Editor/
├── metadata/
│   ├── character_ledger.json      # Character tracking data
│   ├── style_profile.json          # Writing style metrics
│   └── *.faiss                    # Vector store index
├── rewrites/
│   ├── chapter_00.md              # Rewritten chapters
│   ├── chapter_01.md
│   ├── ...
│   └── book.pdf                   # Final PDF output
├── book_bible.md                  # Standard book bible
├── book_bible_enhanced.md         # Enhanced bible with characters
└── validation_reports/            # Chapter validation reports
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `NEBIUS_API_KEY` | Nebius/Kimi API key | *required* |
| `NEBIUS_BASE_URL` | Nebius base URL | `https://api.tokenfactory.nebius.com/v1/` |
| `MISTRAL_API_KEY` | Mistral embeddings API key | *required* |
| `SAMBANOVA_API_KEY` | SambaNova API key | optional |
| `CHARACTER_LEDGER_PATH` | Character ledger path | `metadata/character_ledger.json` |
| `STYLE_PROFILE_PATH` | Style profile path | `metadata/style_profile.json` |
| `ENABLE_VALIDATION` | Enable validation | `true` |
| `TARGET_WORD_COUNT_MIN` | Minimum chapter words | `2000` |
| `TARGET_WORD_COUNT_MAX` | Maximum chapter words | `3500` |
| `PREVIOUS_CHAPTERS_COUNT` | Previous chapters for context | `3` |
| `FUTURE_CHAPTERS_COUNT` | Future chapters for context | `2` |

## Writing Rules

The rewriter enforces these rules throughout:

- **No em dashes** (—) - Use commas, periods, or parentheses instead
- **No contractions** - Use full words (e.g., "do not" instead of "don't")
- **First-person POV** - Maintain consistent first-person narration
- **Canonical names** - Use character names exactly as specified in the ledger

## Troubleshooting

### Common Issues

**Issue**: `No vector store metadata found`
- **Solution**: Run `python -m book_rewriter.cli index "Book/YourBook.docx"` first

**Issue**: `SAMBANOVA_API_KEY is required for multi-turn rewrite`
- **Solution**: Add `SAMBANOVA_API_KEY` to your `.env` file, or use single-turn `rewrite` command

**Issue**: `Chapter X not found in DOCX`
- **Solution**: Check your chapter regex pattern matches your DOCX chapter headings

**Issue**: POV inconsistencies detected
- **Solution**: Run validation with `--auto-correct` flag or manually fix identified slips

## Tips

1. **Start with character extraction** - Run `extract-chars all` before rewriting to build your character ledger
2. **Analyze early chapters** - Use `analyze-style` on your first 3 rewritten chapters to establish a style profile
3. **Validate frequently** - Run `validate-chapter` after each rewrite to catch issues early
4. **Use batch processing** - For entire books, use `multiturn-batch` with `--save-intermediate` for debugging
5. **Update the ledger** - If you make manual character changes, re-run `extract-chars` to update the ledger

## License

MIT License - see LICENSE file for details
