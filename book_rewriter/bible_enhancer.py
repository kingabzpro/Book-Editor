"""Enhanced Book Bible generation with character registry and location inventory."""

import os
from typing import Dict, List, Optional
from .character_tracker import CharacterLedger, format_character_state_for_prompt


def generate_enhanced_bible(
    base_bible: str,
    character_ledger: CharacterLedger,
    locations: Optional[Dict[str, Dict]] = None,
    objects: Optional[Dict[str, List[str]]] = None
) -> str:
    """Generate enhanced Book Bible with character registry.

    Args:
        base_bible: Existing book bible content
        character_ledger: Character ledger with all character data
        locations: Optional location inventory
        objects: Optional object tracking

    Returns:
        Enhanced book bible markdown content
    """
    sections = []

    # Add base bible
    if base_bible:
        sections.append(base_bible)
        sections.append("\n" + "=" * 60 + "\n")

    # Add Character Registry
    sections.append("## CHARACTER REGISTRY\n")
    sections.append("*Canonical names and traits for consistency*\n")

    if character_ledger.characters:
        for name, char in sorted(character_ledger.characters.items()):
            sections.append(f"\n### {name}\n")

            if char.aliases:
                sections.append(f"**Aliases:** {', '.join(char.aliases)}\n")

            if char.physical_traits:
                sections.append("**Physical Traits:**\n")
                for trait, value in char.physical_traits.items():
                    sections.append(f"- {trait.capitalize()}: {value}\n")

            if char.voice_patterns:
                sections.append("**Voice Patterns:**\n")
                for pattern, value in char.voice_patterns.items():
                    sections.append(f"- {pattern.capitalize()}: {value}\n")

            if char.current_status:
                sections.append(f"**Current Status:** {char.current_status}\n")

            if char.relationships:
                sections.append("**Relationships:**\n")
                for rel in char.relationships:
                    sections.append(f"- {rel.get('name', 'Unknown')}: {rel.get('type', 'unknown')}\n")

            if char.chapter_appearances:
                chapters = [str(ap.get('idx', '?')) for ap in char.chapter_appearances]
                sections.append(f"**Appears in Chapters:** {', '.join(chapters)}\n")
    else:
        sections.append("*No character information available yet.*\n")

    # Add Canonical Name Mappings
    if character_ledger.canonical_names:
        sections.append("\n## CANONICAL NAME MAPPINGS\n")
        sections.append("*Use these exact spellings in the text*\n")

        # Group by canonical name
        for canonical in sorted(character_ledger.characters.keys()):
            aliases = [alias for alias, canon in character_ledger.canonical_names.items()
                      if canon == canonical and alias.lower() != canonical.lower()]
            if aliases:
                sections.append(f"- **{canonical}** (not: {', '.join(aliases)})\n")

    # Add Location Inventory
    sections.append("\n## LOCATION INVENTORY\n")
    if locations:
        for name, details in sorted(locations.items()):
            sections.append(f"\n### {name}\n")
            if 'details' in details:
                sections.append(f"{details['details']}\n")
            if 'purpose' in details:
                sections.append(f"*Purpose: {details['purpose']}*\n")
    else:
        sections.append("*No location information available yet.*\n")

    # Add Object Continuity
    sections.append("\n## OBJECT CONTINUITY\n")
    if objects:
        for obj, chapters in sorted(objects.items()):
            sections.append(f"- **{obj}**: Chapters {', '.join(map(str, chapters))}\n")
    else:
        sections.append("*No object information available yet.*\n")

    # Add Continuity Rules
    sections.append("\n## CONTINUITY RULES\n")
    sections.append("- POV: First-person present (\"I\") throughout\n")
    sections.append("- Restrictions: NO em dashes (—), NO contractions\n")
    sections.append("- Character names: Use canonical names exactly as listed above\n")

    return '\n'.join(sections)


def save_enhanced_bible(content: str, path: str) -> None:
    """Save enhanced bible to file."""
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else '.', exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)


def load_base_bible(path: str) -> str:
    """Load existing base bible."""
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    return ""
