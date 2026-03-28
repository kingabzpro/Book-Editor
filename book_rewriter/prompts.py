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
chapters. Output ONLY the final rewritten text with no headings or commentary.
"""

BIBLE_SYSTEM = """You are a senior developmental editor.
Analyse the provided chapter excerpts and produce a comprehensive Book Bible in
markdown format. Be concrete and specific; write UNKNOWN where information is absent.
Do not invent facts that are not present in the text.
"""

BIBLE_USER_TEMPLATE = """Produce a Book Bible from the chapter excerpts below.

Include these sections:
# Working Title
# Premise & Genre
# Story Engine  (central tension, primary forces, escalation pattern)
# Characters    (name, role, physical description, motivation, arc)
# Settings      (key locations, atmosphere, symbolic meaning)
# Plot Summary  (beginning → middle → end with key turning points)
# Themes & Motifs
# Tone & Style Notes

─────────────────────────────────────────
CHAPTER EXCERPTS
─────────────────────────────────────────
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
