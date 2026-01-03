"""Pacing control module for ensuring consistent chapter lengths."""

from typing import Tuple, Dict, Any
import re

def calculate_target_word_count(
    chapter_idx: int,
    total_chapters: int,
    min_words: int = 2000,
    max_words: int = 3500
) -> Tuple[int, int]:
    """Calculate target word count for a chapter based on its position.

    Early chapters (1/3): Build tension gradually - shorter
    Middle chapters (1/3 to 2/3): Escalate action - longer
    Late chapters (2/3+): Accelerate toward climax - longest

    Args:
        chapter_idx: Zero-based chapter index
        total_chapters: Total number of chapters
        min_words: Minimum word count base
        max_words: Maximum word count base

    Returns:
        Tuple of (min_target, max_target) word counts
    """
    if total_chapters <= 0:
        total_chapters = 1

    position = chapter_idx / total_chapters

    if position < 0.33:
        # Early chapters: Build gradually
        target_min = int(min_words * 0.8)
        target_max = int(max_words * 0.9)
    elif position < 0.66:
        # Middle chapters: Full development
        target_min = min_words
        target_max = max_words
    else:
        # Late chapters: Accelerate
        target_min = int(min_words * 1.0)
        target_max = int(max_words * 1.1)

    return target_min, target_max

def analyze_pacing(chapter_text: str) -> Dict[str, Any]:
    """Analyze pacing metrics for a chapter.

    Returns dict with:
    - word_count: Total words
    - paragraph_count: Total paragraphs
    - avg_paragraph_length: Average words per paragraph
    - dialogue_paragraphs: Number of dialogue-heavy paragraphs
    - action_paragraphs: Number of action-heavy paragraphs
    """
    paragraphs = re.split(r'\n\n+', chapter_text)
    paragraphs = [p.strip() for p in paragraphs if p.strip() and not p.startswith('#')]

    word_count = len(chapter_text.split())
    paragraph_count = len(paragraphs)

    para_lengths = [len(p.split()) for p in paragraphs]
    avg_para_length = sum(para_lengths) / len(para_lengths) if para_lengths else 0

    # Identify dialogue vs action paragraphs
    dialogue_paras = 0
    action_paras = 0

    for para in paragraphs:
        # Count quote marks
        quote_count = para.count('"') + para.count('"')
        words = para.split()

        # If more than 30% of text is in quotes, it's dialogue-heavy
        if quote_count >= 2 and len(words) > 0:
            quoted_chars = sum(len(m.group(0)) for m in re.finditer(r'["\'][^"\']*["\']', para))
            if quoted_chars / len(para) > 0.3:
                dialogue_paras += 1
            else:
                action_paras += 1
        else:
            action_paras += 1

    return {
        'word_count': word_count,
        'paragraph_count': paragraph_count,
        'avg_paragraph_length': avg_para_length,
        'dialogue_paragraphs': dialogue_paras,
        'action_paragraphs': action_paras
    }

def validate_chapter_pacing(
    chapter_text: str,
    target_min: int,
    target_max: int
) -> Dict[str, Any]:
    """Validate if chapter meets pacing targets.

    Returns dict with:
    - within_range: bool
    - word_count: int
    - target_min: int
    - target_max: int
    - difference: int (how far from middle of range)
    - suggestions: list of improvement suggestions
    """
    word_count = len(chapter_text.split())

    within_range = target_min <= word_count <= target_max
    target_mid = (target_min + target_max) // 2
    difference = word_count - target_mid

    suggestions = []
    if word_count < target_min:
        needed = target_min - word_count
        suggestions.append(f"Add ~{needed} words: expand descriptions, add sensory details, develop character moments")
    elif word_count > target_max:
        excess = word_count - target_max
        suggestions.append(f"Remove ~{excess} words: tighten prose, combine sentences, remove redundancy")
    else:
        suggestions.append("Pacing is within target range")

    return {
        'within_range': within_range,
        'word_count': word_count,
        'target_min': target_min,
        'target_max': target_max,
        'difference': difference,
        'suggestions': suggestions
    }
