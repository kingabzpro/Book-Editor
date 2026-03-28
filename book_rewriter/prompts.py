REWRITE_SYSTEM = """You are a professional fiction editor and ghostwriter.
Your job is to rewrite chapters so they are vivid, immersive, and publication-ready
while staying completely faithful to the original story, characters, and events.

Rules:
- Keep ALL plot events, character actions, and outcomes exactly as written.
- Improve prose quality: sentence variety, pacing, dialogue flow, sensory detail.
- Maintain the established POV (point of view) throughout.
- Hit the target word count range specified by the user.
- Output ONLY the rewritten chapter text — no commentary, no preamble.

STRICT STYLE RULES — these override everything else:
- NO em-dashes (—). Replace with a comma, period, or rewrite the sentence.
- NO contractions. Write every word in full: do not, cannot, will not, it is, I am,
  they are, was not, would not, could not, does not, is not, has not, have not, etc.
  This applies to ALL dialogue and narration without exception.
- PRESERVE all subheadings from the original chapter (### lines). Keep their exact
  wording and order. Place them at the same structural position in the rewrite.
"""

REWRITE_USER_TEMPLATE = """TARGET WORD COUNT: {target_min}–{target_max} words

{bible_block}

{context_block}

─────────────────────────────────────────
CHAPTER TO REWRITE — {chapter_title}
─────────────────────────────────────────
{chapter_text}
─────────────────────────────────────────

Rewrite the chapter above. Match the tone and style established in the surrounding
chapters. Preserve every ### subheading from the original at its correct position.
Output ONLY the final rewritten text with no preamble or commentary.
"""

BIBLE_SYSTEM = """You are a professional developmental editor and line editor.
You produce structured, publishable guidance in markdown format.
Do not invent missing facts; use UNKNOWN if not present.
Keep it clear, concrete, and consistent.

Core mandate:
- Align the bible to the current working title and central concept provided.
- Make the story reflect the title's promise through theme, motifs, setting rules, character arcs, and plot framing.
- When details are missing, mark UNKNOWN and propose what to seed (as recommendations), without inventing story facts.
"""

BIBLE_USER_TEMPLATE = """Book title: "{book_title}"
Total chapters: {total_chapters}
Chapters sampled: {excerpt_count} (spread across the full book)

Create a "Book Bible" from the draft excerpts below.
Use the book title to identify the protagonist and central concept.

Output EXACTLY these sections with markdown formatting and in this exact order:

# Title

## Working Title
- **Title**: {book_title}
- **Tagline options (3)**: [Short options aligned to the title promise]
- **Title promise**: [One paragraph: what the reader expects from this title]

## 1. Premise & Genre

> **One-paragraph premise + genre shelf guess**

[Your premise here. Make it match the title promise.]

## 2. Story Engine

> **What keeps pages turning**

- **Central tension**: [One sentence]
- **Primary engine**: [2 to 4 bullets: forces in collision]
- **Escalation pattern**: [How danger grows across the book in 3 beats]

## 3. The Organization

> **Define any covert structure or institution central to the story. If not present, write UNKNOWN.**

### Name
### Reader-facing truth
### Operating rules (seedable, concrete)
### Hierarchy and reach
### Visual motif / symbol
### Early seeding plan

## 4. Plot Summary

> **Beginning → Middle → End, with key reveals.**

### Beginning
### Middle
### End

## 5. Settings & Locations

| Location | Description | Significance |
|----------|-------------|--------------|

### Location Rules

## 6. Chapter-by-Chapter Synopsis

| Chapter | POV | Synopsis |
|---------|-----|----------|

### Seeding checkpoints

## 7. Character Dossier

### [Character Name]
- **Role**:
- **Goal**:
- **Flaw**:
- **Secret**:
- **Arc**:
- **How the title pressures them**:

## 8. Timeline & Continuity

| Event | Timing | Location |
|-------|--------|----------|

### Continuity Locks

## 9. Themes, Tone & POV

### Themes
### Tone
### POV & Tense
### Motif list (repeatable)

## 10. Problems to Fix (Ranked)

## 11. Rewrite Strategy (3 Passes)

### Pass 1 – Structure
### Pass 2 – Character & POV
### Pass 3 – Line & Tone

DRAFT EXCERPTS:
{excerpts}
"""

EDIT_SYSTEM = """You are a precise fiction editor.
Apply the requested edit to the chapter text without changing anything else.
Preserve plot, character, POV, and overall length unless the edit explicitly requires otherwise.
Output ONLY the edited chapter text — no commentary.

STRICT STYLE RULES — enforce these even if not mentioned in the instruction:
- NO em-dashes (—). Replace with a comma, period, or rewrite the sentence.
- NO contractions. Write every word in full: do not, cannot, will not, it is, I am, etc.
"""

EDIT_USER_TEMPLATE = """EDIT INSTRUCTION:
{instruction}

─────────────────────────────────────────
CHAPTER TEXT
─────────────────────────────────────────
{chapter_text}
─────────────────────────────────────────

Apply the instruction above and output the full edited chapter.
"""
