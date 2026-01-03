"""Style analysis module for maintaining consistent writing style across chapters."""

import re
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Tuple
import json
import os

@dataclass
class StyleProfile:
    """Profile of writing style metrics."""
    sentence_length_mean: float = 0.0
    sentence_length_std: float = 0.0
    sentence_length_median: float = 0.0
    dialogue_ratio: float = 0.0  # Percentage of dialogue lines
    description_density: float = 0.0  # Sensory details per 1000 words
    paragraph_count: int = 0
    word_count: int = 0
    common_patterns: List[str] = field(default_factory=list)
    transition_patterns: List[str] = field(default_factory=list)
    sample_chapters: List[int] = field(default_factory=list)  # Chapter indices analyzed

    def to_dict(self) -> Dict:
        return asdict(self)

def analyze_sentence_lengths(text: str) -> Tuple[float, float, float]:
    """Analyze sentence length distribution."""
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    if not sentences:
        return 0.0, 0.0, 0.0

    lengths = [len(s.split()) for s in sentences]
    mean = sum(lengths) / len(lengths)
    variance = sum((x - mean) ** 2 for x in lengths) / len(lengths)
    std = variance ** 0.5

    sorted_lengths = sorted(lengths)
    median = sorted_lengths[len(sorted_lengths) // 2]

    return mean, std, median

def analyze_dialogue_ratio(text: str) -> float:
    """Calculate the percentage of dialogue in the text."""
    lines = text.split('\n')
    dialogue_lines = 0
    total_lines = 0

    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        total_lines += 1
        # Check if line is dialogue (contains quotes)
        if '"' in line or '"' in line or "'" in line:
            dialogue_lines += 1

    if total_lines == 0:
        return 0.0
    return (dialogue_lines / total_lines) * 100

def analyze_description_density(text: str) -> float:
    """Count sensory details per 1000 words."""
    sensory_words = [
        'see', 'saw', 'look', 'watch', 'stare', 'gaze',
        'hear', 'heard', 'listen', 'sound', 'noise', 'quiet',
        'feel', 'felt', 'touch', 'cold', 'warm', 'hot', 'hard', 'soft',
        'smell', 'scent', 'odor', 'fragrance', 'stench',
        'taste', 'flavor', 'bitter', 'sweet', 'sour', 'salty',
        'red', 'blue', 'green', 'yellow', 'black', 'white',
        'bright', 'dark', 'light', 'shadow',
        'wind', 'rain', 'snow', 'sun', 'moon'
    ]

    words = text.lower().split()
    word_count = len(words)

    if word_count == 0:
        return 0.0

    sensory_count = sum(1 for word in words if any(s in word for s in sensory_words))

    # Per 1000 words
    return (sensory_count / word_count) * 1000

def extract_common_patterns(text: str, limit: int = 5) -> List[str]:
    """Extract common sentence patterns."""
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip() and len(s.split()) >= 5]

    if not sentences:
        return []

    # Get sentence starts (first 3 words)
    patterns = {}
    for s in sentences[:20]:  # Sample first 20 sentences
        words = s.split()
        if len(words) >= 3:
            pattern = ' '.join(words[:3])
            patterns[pattern] = patterns.get(pattern, 0) + 1

    # Sort by frequency
    sorted_patterns = sorted(patterns.items(), key=lambda x: x[1], reverse=True)
    return [p[0] for p in sorted_patterns[:limit]]

def extract_transition_patterns(text: str) -> List[str]:
    """Extract scene transition patterns."""
    transitions = []

    # Look for paragraph transitions
    paragraphs = text.split('\n\n')
    for i, para in enumerate(paragraphs):
        para = para.strip()
        if not para or para.startswith('#'):
            continue

        # Look for transition words at start
        first_words = para.split()[:3]
        for word in first_words:
            word = word.lower().strip('.,;:')
            if word in ['then', 'next', 'after', 'before', 'later', 'meanwhile',
                       'suddenly', 'finally', 'eventually', 'moments later']:
                transitions.append(word)
                break

    # Return unique transitions
    return list(set(transitions))

def analyze_chapter_style(chapter_text: str, chapter_idx: int = 0) -> StyleProfile:
    """Analyze a single chapter and create a style profile."""
    word_count = len(chapter_text.split())

    sent_mean, sent_std, sent_median = analyze_sentence_lengths(chapter_text)
    dialogue_ratio = analyze_dialogue_ratio(chapter_text)
    desc_density = analyze_description_density(chapter_text)

    paragraphs = [p.strip() for p in chapter_text.split('\n\n') if p.strip() and not p.startswith('#')]

    return StyleProfile(
        sentence_length_mean=sent_mean,
        sentence_length_std=sent_std,
        sentence_length_median=sent_median,
        dialogue_ratio=dialogue_ratio,
        description_density=desc_density,
        paragraph_count=len(paragraphs),
        word_count=word_count,
        common_patterns=extract_common_patterns(chapter_text),
        transition_patterns=extract_transition_patterns(chapter_text),
        sample_chapters=[chapter_idx]
    )

def build_style_profile(chapters: List[Tuple[int, str]]) -> StyleProfile:
    """Build aggregated style profile from multiple chapters.

    Args:
        chapters: List of (chapter_idx, chapter_text) tuples

    Returns:
        Aggregated StyleProfile
    """
    if not chapters:
        return StyleProfile()

    profiles = [analyze_chapter_style(text, idx) for idx, text in chapters]

    # Aggregate metrics
    return StyleProfile(
        sentence_length_mean=sum(p.sentence_length_mean for p in profiles) / len(profiles),
        sentence_length_std=sum(p.sentence_length_std for p in profiles) / len(profiles),
        sentence_length_median=sum(p.sentence_length_median for p in profiles) / len(profiles),
        dialogue_ratio=sum(p.dialogue_ratio for p in profiles) / len(profiles),
        description_density=sum(p.description_density for p in profiles) / len(profiles),
        paragraph_count=sum(p.paragraph_count for p in profiles),
        word_count=sum(p.word_count for p in profiles),
        common_patterns=profiles[0].common_patterns if profiles else [],
        transition_patterns=list(set(t for p in profiles for t in p.transition_patterns)),
        sample_chapters=[p.sample_chapters[0] for p in profiles]
    )

def save_style_profile(profile: StyleProfile, path: str) -> None:
    """Save style profile to JSON."""
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else '.', exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(profile.to_dict(), f, indent=2)

def load_style_profile(path: str) -> Optional[StyleProfile]:
    """Load style profile from JSON."""
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return StyleProfile(**data)

def format_style_for_prompt(profile: StyleProfile) -> str:
    """Format style profile for inclusion in LLM prompts."""
    if not profile or profile.word_count == 0:
        return "No style profile available yet."

    return f"""## STYLE PROFILE (from chapters {', '.join(map(str, profile.sample_chapters))})

### Sentence Structure
- Average length: {profile.sentence_length_mean:.1f} ± {profile.sentence_length_std:.1f} words
- Median length: {profile.sentence_length_median:.1f} words

### Dialogue & Description
- Dialogue ratio: {profile.dialogue_ratio:.1f}%
- Sensory detail density: {profile.description_density:.1f} per 1000 words

### Content
- Paragraphs: {profile.paragraph_count}
- Total words: {profile.word_count}

### Common Patterns
{chr(10).join(f'- {p}' for p in profile.common_patterns[:5]) if profile.common_patterns else '- N/A'}

### Transitions
{chr(10).join(f'- {t}' for t in profile.transition_patterns[:5]) if profile.transition_patterns else '- N/A'}
"""
