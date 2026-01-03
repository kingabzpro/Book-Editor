"""
Character Tracking Module for Book Rewriting

This module provides comprehensive character state tracking across chapters,
ensuring consistency in names, physical traits, relationships, and appearances.
It supports character extraction from chapter text and validation functions.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any
import json
import os
import re
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


# Common pronouns to ignore in validation
PRONOUN_WHITELIST = {
    'i', 'me', 'my', 'mine', 'myself',
    'he', 'him', 'his', 'himself',
    'she', 'her', 'hers', 'herself',
    'they', 'them', 'their', 'theirs', 'themself',
    'we', 'us', 'our', 'ours', 'ourselves',
    'you', 'your', 'yours', 'yourself', 'yourselves'
}


@dataclass
class CharacterState:
    """Complete state of a character across all chapters.

    This class tracks all information about a character throughout the book,
    including physical traits, voice patterns, relationships, and appearances.
    """
    canonical_name: str
    aliases: List[str] = field(default_factory=list)
    physical_traits: Dict[str, str] = field(default_factory=dict)  # hair, eyes, height, build, age
    voice_patterns: Dict[str, str] = field(default_factory=dict)  # speech style, word choice
    relationships: List[Dict] = field(default_factory=list)  # [{name: "Simon", type: "ally"}]
    chapter_appearances: List[Dict] = field(default_factory=list)  # [{idx: 0, scenes: 3}]
    current_status: str = ""  # "injured", "working at diner", etc.
    first_appearance_chapter: int = -1

    def add_alias(self, alias: str) -> None:
        """Add an alias for this character if it doesn't already exist.

        Args:
            alias: The alias to add (e.g., "the man", "him")
        """
        normalized_alias = alias.lower().strip()
        canonical_lower = self.canonical_name.lower()

        if (normalized_alias not in [a.lower() for a in self.aliases] and
            normalized_alias != canonical_lower):
            self.aliases.append(alias)

    def record_appearance(self, chapter_idx: int, details: Dict = None) -> None:
        """Record a character's appearance in a chapter.

        Args:
            chapter_idx: The index of the chapter
            details: Optional additional details (scenes, context, etc.)
        """
        appearance = {
            "idx": chapter_idx,
            "timestamp": datetime.now().isoformat()
        }
        if details:
            appearance.update(details)

        self.chapter_appearances.append(appearance)

        if self.first_appearance_chapter == -1:
            self.first_appearance_chapter = chapter_idx

    def update_status(self, status: str) -> None:
        """Update the character's current status.

        Args:
            status: New status description
        """
        self.current_status = status

    def add_physical_trait(self, trait_name: str, value: str) -> None:
        """Add or update a physical trait.

        Args:
            trait_name: The trait name (e.g., "hair", "eyes")
            value: The trait value
        """
        self.physical_traits[trait_name] = value

    def add_voice_pattern(self, pattern_name: str, value: str) -> None:
        """Add or update a voice/speech pattern.

        Args:
            pattern_name: The pattern name (e.g., "style", "tone")
            value: The pattern value
        """
        self.voice_patterns[pattern_name] = value

    def add_relationship(self, character_name: str, relationship_type: str) -> None:
        """Add a relationship with another character.

        Args:
            character_name: Name of the related character
            relationship_type: Type of relationship (e.g., "ally", "enemy", "family")
        """
        # Check if relationship already exists
        for rel in self.relationships:
            if rel.get("name") == character_name:
                rel["type"] = relationship_type
                return

        self.relationships.append({"name": character_name, "type": relationship_type})

    def get_alias_variations(self) -> List[str]:
        """Get all variations of this character's name including canonical.

        Returns:
            List of all name variations
        """
        return [self.canonical_name] + self.aliases


@dataclass
class CharacterLedger:
    """Registry of all characters in the book.

    This ledger maintains the canonical source of truth for all character
    information, including name resolution and tracking of locations and objects.
    """
    characters: Dict[str, CharacterState] = field(default_factory=dict)
    canonical_names: Dict[str, str] = field(default_factory=dict)  # aliases -> canonical
    locations: Dict[str, Dict] = field(default_factory=dict)  # location tracking
    objects: Dict[str, List[str]] = field(default_factory=dict)  # object -> chapters

    def get_canonical_name(self, name: str) -> Optional[str]:
        """Resolve a name to its canonical form.

        Args:
            name: Any variation of a character's name

        Returns:
            Canonical name if found, None otherwise
        """
        if name in self.characters:
            return name
        return self.canonical_names.get(name.lower())

    def add_character(self, character: CharacterState) -> None:
        """Add a character to the ledger.

        Args:
            character: CharacterState object to add
        """
        self.characters[character.canonical_name] = character

        # Register all aliases
        for alias in character.aliases:
            self.canonical_names[alias.lower()] = character.canonical_name

        self.canonical_names[character.canonical_name.lower()] = character.canonical_name

    def get_character(self, name: str) -> Optional[CharacterState]:
        """Retrieve a character by any variation of their name.

        Args:
            name: Any variation of the character's name

        Returns:
            CharacterState if found, None otherwise
        """
        canonical = self.get_canonical_name(name)
        return self.characters.get(canonical) if canonical else None

    def update_character(self, name: str, **kwargs) -> bool:
        """Update character attributes.

        Args:
            name: Character name (any variation)
            **kwargs: Fields to update

        Returns:
            True if updated, False if character not found
        """
        character = self.get_character(name)
        if not character:
            return False

        for key, value in kwargs.items():
            if hasattr(character, key):
                setattr(character, key, value)

        return True

    def add_location(self, location_name: str, details: Dict = None) -> None:
        """Add or update a location in the ledger.

        Args:
            location_name: Name of the location
            details: Optional details about the location
        """
        if details:
            self.locations[location_name] = details
        else:
            if location_name not in self.locations:
                self.locations[location_name] = {}

    def track_object(self, object_name: str, chapter_idx: int) -> None:
        """Track an object's appearance in a chapter.

        Args:
            object_name: Name of the object
            chapter_idx: Chapter index where object appears
        """
        if object_name not in self.objects:
            self.objects[object_name] = []

        if chapter_idx not in self.objects[object_name]:
            self.objects[object_name].append(chapter_idx)

    def get_all_characters_sorted(self) -> List[CharacterState]:
        """Get all characters sorted by first appearance.

        Returns:
            List of CharacterState objects sorted by first appearance
        """
        return sorted(
            self.characters.values(),
            key=lambda c: (c.first_appearance_chapter if c.first_appearance_chapter != -1 else 999)
        )

    def get_characters_in_chapter(self, chapter_idx: int) -> List[CharacterState]:
        """Get all characters that appear in a specific chapter.

        Args:
            chapter_idx: Chapter index

        Returns:
            List of CharacterState objects
        """
        result = []
        for character in self.characters.values():
            for appearance in character.chapter_appearances:
                if appearance.get("idx") == chapter_idx:
                    result.append(character)
                    break
        return result


def extract_characters_from_chapter(
    chapter_text: str,
    chapter_idx: int,
    model_api,
    system_prompt: str = None
) -> Dict[str, Any]:
    """Extract character information from a chapter using LLM.

    This function sends the chapter text to an LLM and asks it to extract
    character information, locations, and plot events in structured JSON format.

    Args:
        chapter_text: The full text of the chapter
        chapter_idx: Index of the chapter being processed
        model_api: The LLM client function (kimi_chat or sambanova_chat_simple)
        system_prompt: Optional custom system prompt

    Returns:
        Dictionary with:
        - characters: List[Dict] of character data
        - locations: Dict of locations mentioned
        - plot_events: List of key events
        - success: Boolean indicating if extraction succeeded
        - error: Error message if failed
    """

    extraction_prompt = """You are a narrative analyst. Extract the following from this chapter:

1. CHARACTERS - For each character:
   - Full name (most commonly used)
   - Aliases or variations (pronouns, titles, descriptive references)
   - Physical traits (hair, eyes, height, build, age, distinguishing features)
   - Voice/speech patterns (style, tone, word choice)
   - Current status or situation
   - Relationships mentioned (with other characters)

2. LOCATIONS - Each place with physical details

3. PLOT EVENTS - Key events in sequence

Return ONLY valid JSON in this exact format:
{
  "characters": [
    {
      "canonical_name": "Simon",
      "aliases": ["the man", "him"],
      "physical_traits": {"hair": "dark", "eyes": "brown", "height": "6'0"},
      "voice_patterns": {"style": "direct", "tone": "calm"},
      "current_status": "sheltering at cabin",
      "relationships": [{"name": "Gené", "type": "protecting"}]
    }
  ],
  "locations": {
    "Simon's Cabin": {"details": "remote, snowbound, one road, fireplace"}
  },
  "plot_events": ["Gené arrives injured", "Simon treats her wounds"]
}

Do not include any text outside the JSON."""

    try:
        # Prepare messages for the LLM
        messages = [
            {"role": "system", "content": system_prompt or "You are a narrative analyst."},
            {"role": "user", "content": f"{extraction_prompt}\n\nChapter text:\n{chapter_text}"}
        ]

        # Call the LLM - handle both function and object APIs
        if callable(model_api):
            # Direct function call (kimi_chat, sambanova_chat_simple, etc.)
            # These functions expect: api_key, base_url, model, system_prompt, user_text, temperature
            # We need to get settings from environment
            import os
            api_key = os.environ.get("NEBIUS_API_KEY") or os.environ.get("SAMBANOVA_API_KEY")
            base_url = os.environ.get("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1/")
            model = os.environ.get("KIMI_INSTRUCT_MODEL", "moonshotai/Kimi-K2-Instruct")

            response = model_api(
                api_key=api_key,
                base_url=base_url,
                model=model,
                system_prompt=messages[0]["content"],
                user_text=messages[1]["content"],
                temperature=0.1
            )
        elif hasattr(model_api, 'chat'):
            # Kimi-like API object
            response = model_api.chat(
                messages=messages,
                temperature=0.1
            )
        elif hasattr(model_api, 'generate'):
            # SambaNova-like API object
            response = model_api.generate(
                prompt=messages[1]["content"],
                system_prompt=messages[0]["content"],
                temperature=0.1
            )
        else:
            raise ValueError("Unsupported model API - must be callable or have 'chat' or 'generate' method")

        # Extract response text
        if isinstance(response, dict):
            response_text = response.get("content", response.get("text", ""))
        else:
            response_text = str(response)

        # Parse JSON from response
        # Handle markdown code blocks
        json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find JSON object
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                json_str = response_text

        data = json.loads(json_str)

        # Validate structure
        if not isinstance(data, dict):
            raise ValueError("Response is not a valid JSON object")

        # Ensure required keys exist
        data.setdefault("characters", [])
        data.setdefault("locations", {})
        data.setdefault("plot_events", [])

        # Record chapter index for each character
        for char_data in data["characters"]:
            char_data["chapter_idx"] = chapter_idx

        logger.info(f"Successfully extracted {len(data['characters'])} characters from chapter {chapter_idx}")

        return {
            "characters": data["characters"],
            "locations": data["locations"],
            "plot_events": data["plot_events"],
            "success": True,
            "error": None
        }

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from LLM response: {e}")
        return {
            "characters": [],
            "locations": {},
            "plot_events": [],
            "success": False,
            "error": f"JSON parsing error: {str(e)}"
        }
    except Exception as e:
        logger.error(f"Character extraction failed: {e}")
        return {
            "characters": [],
            "locations": {},
            "plot_events": [],
            "success": False,
            "error": str(e)
        }


def merge_extraction_into_ledger(
    extraction_data: Dict[str, Any],
    ledger: CharacterLedger,
    chapter_idx: int
) -> int:
    """Merge extracted character data into the character ledger.

    This function takes the output from extract_characters_from_chapter
    and intelligently merges it with existing character data, handling
    name resolution and updating existing characters.

    Args:
        extraction_data: Dictionary from extract_characters_from_chapter
        ledger: Existing CharacterLedger to update
        chapter_idx: Current chapter index

    Returns:
        Number of characters added/updated
    """
    characters_data = extraction_data.get("characters", [])
    locations_data = extraction_data.get("locations", {})

    updated_count = 0

    # Merge locations
    for location_name, details in locations_data.items():
        ledger.add_location(location_name, details)

    # Merge characters
    for char_data in characters_data:
        canonical_name = char_data.get("canonical_name", "")
        if not canonical_name:
            continue

        # Check if character already exists
        existing_char = ledger.get_character(canonical_name)

        if existing_char:
            # Update existing character
            aliases = char_data.get("aliases", [])
            for alias in aliases:
                existing_char.add_alias(alias)

            # Merge physical traits
            physical_traits = char_data.get("physical_traits", {})
            for trait_name, value in physical_traits.items():
                existing_char.add_physical_trait(trait_name, value)

            # Merge voice patterns
            voice_patterns = char_data.get("voice_patterns", {})
            for pattern_name, value in voice_patterns.items():
                existing_char.add_voice_pattern(pattern_name, value)

            # Update status if provided
            if char_data.get("current_status"):
                existing_char.update_status(char_data["current_status"])

            # Add relationships
            relationships = char_data.get("relationships", [])
            for rel in relationships:
                if isinstance(rel, dict):
                    existing_char.add_relationship(
                        rel.get("name", ""),
                        rel.get("type", "unknown")
                    )

            # Record appearance
            details = {k: v for k, v in char_data.items()
                      if k not in ["canonical_name", "aliases", "physical_traits",
                                  "voice_patterns", "current_status", "relationships"]}
            existing_char.record_appearance(chapter_idx, details)

            updated_count += 1
        else:
            # Create new character
            new_char = CharacterState(
                canonical_name=canonical_name,
                aliases=char_data.get("aliases", []),
                physical_traits=char_data.get("physical_traits", {}),
                voice_patterns=char_data.get("voice_patterns", {}),
                relationships=char_data.get("relationships", []),
                current_status=char_data.get("current_status", "")
            )

            # Record appearance
            details = {k: v for k, v in char_data.items()
                      if k not in ["canonical_name", "aliases", "physical_traits",
                                  "voice_patterns", "current_status", "relationships"]}
            new_char.record_appearance(chapter_idx, details)

            ledger.add_character(new_char)
            updated_count += 1

    logger.info(f"Merged {updated_count} characters into ledger for chapter {chapter_idx}")
    return updated_count


def validate_character_consistency(
    chapter_text: str,
    ledger: CharacterLedger,
    is_first_person: bool = False
) -> List[str]:
    """Check for character name inconsistencies using smart validation.

    This function scans the chapter text and compares character names
    against the canonical ledger to identify REAL issues only:
    - Wrong name spellings (typos)
    - Unknown characters (appearing 3+ times)
    - Does NOT flag pronoun usage (he/she/her/him, etc.)

    Args:
        chapter_text: The chapter text to validate
        ledger: CharacterLedger with known characters
        is_first_person: Whether the narrative is first-person (skips pronoun validation)

    Returns:
        List of consistency issues found (real issues only)
    """
    issues = []
    chapter_lower = chapter_text.lower()

    # Check all characters in ledger
    for char_name, character in ledger.characters.items():
        # Filter out pronoun aliases from validation
        non_pronoun_aliases = [
            alias for alias in character.aliases
            if alias.lower() not in PRONOUN_WHITELIST and len(alias) > 2
        ]

        # Check for wrong name spellings
        # If canonical name not found, check if it's a spelling issue
        if char_name not in chapter_text:
            # Check if any non-pronoun aliases are used
            alias_found = False
            for alias in non_pronoun_aliases:
                if alias.lower() in chapter_lower:
                    alias_found = True
                    break

            # Only flag if non-pronoun aliases found (indicates possible spelling issue)
            if alias_found and non_pronoun_aliases:
                issues.append(
                    f"Character '{char_name}' may have spelling variant: "
                    f"{', '.join(non_pronoun_aliases[:3])}"
                )

    # Detect potential new characters (capitalized words not in ledger)
    # This is a simple heuristic and may have false positives
    words = re.findall(r'\b[A-Z][a-z]+\b', chapter_text)
    word_counts = {}
    for word in words:
        word_lower = word.lower()
        # Skip pronouns and very short words
        if word_lower not in PRONOUN_WHITELIST and len(word) > 2:
            word_counts[word] = word_counts.get(word, 0) + 1

    # Check frequent capitalized words that aren't known characters
    for word, count in word_counts.items():
        if count >= 3:  # Appears at least 3 times (not a one-off)
            canonical = ledger.get_canonical_name(word)
            word_lower = word.lower()
            # Only flag if not in ledger, not a location, and not a pronoun
            if (not canonical and
                word not in ledger.locations and
                word_lower not in PRONOUN_WHITELIST):
                issues.append(
                    f"Potential new character detected: '{word}' (appears {count} times)"
                )

    return issues


def detect_name_variations(text: str, known_names: List[str]) -> Dict[str, List[str]]:
    """Detect variations of character names in text.

    This function uses pattern matching to find variations of known
    character names in the text (e.g., "Simon" -> "Si", "Sim").

    Args:
        text: The text to search
        known_names: List of known character names

    Returns:
        Dictionary mapping known names to detected variations
    """
    variations = {}

    for name in known_names:
        # Look for similar patterns - names starting with same letters
        pattern = re.compile(r'\b(' + re.escape(name[:3]) + r'\w*)\b', re.IGNORECASE)
        matches = pattern.findall(text)

        if matches:
            # Filter to only include variations that are reasonable
            filtered = []
            for match in matches:
                match_lower = match.lower()
                # Exclude exact matches and very short variations
                if match_lower != name.lower() and len(match) >= 3:
                    if match_lower not in [m.lower() for m in filtered]:
                        filtered.append(match)

            if filtered:
                variations[name] = sorted(filtered)

    return variations


def save_ledger(ledger: CharacterLedger, path: str) -> None:
    """Save character ledger to JSON file.

    Args:
        ledger: CharacterLedger to save
        path: File path to save to
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)

    data = {
        "characters": {
            name: asdict(char) for name, char in ledger.characters.items()
        },
        "canonical_names": ledger.canonical_names,
        "locations": ledger.locations,
        "objects": ledger.objects,
        "metadata": {
            "total_characters": len(ledger.characters),
            "total_locations": len(ledger.locations),
            "last_updated": datetime.now().isoformat()
        }
    }

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved character ledger with {len(ledger.characters)} characters to {path}")


def load_ledger(path: str) -> CharacterLedger:
    """Load character ledger from JSON file.

    Args:
        path: File path to load from

    Returns:
        CharacterLedger object (empty if file doesn't exist)
    """
    if not os.path.exists(path):
        logger.warning(f"Ledger file not found: {path}. Creating empty ledger.")
        return CharacterLedger()

    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        ledger = CharacterLedger()

        # Reconstruct characters
        for name, char_data in data.get("characters", {}).items():
            char = CharacterState(**char_data)
            ledger.add_character(char)

        ledger.locations = data.get("locations", {})
        ledger.objects = data.get("objects", {})

        logger.info(f"Loaded character ledger with {len(ledger.characters)} characters from {path}")

        return ledger

    except Exception as e:
        logger.error(f"Failed to load ledger from {path}: {e}")
        return CharacterLedger()


def format_character_state_for_prompt(ledger: CharacterLedger) -> str:
    """Format character ledger as text for LLM prompts.

    This function creates a formatted text representation of the character
    ledger suitable for inclusion in LLM prompts to ensure character consistency.

    Args:
        ledger: CharacterLedger to format

    Returns:
        Formatted string for prompt inclusion
    """
    if not ledger.characters:
        return "No character information available yet."

    sections = []
    sections.append("## CHARACTER LEDGER (must preserve exactly)\n")

    # Sort characters by first appearance
    sorted_chars = ledger.get_all_characters_sorted()

    for char in sorted_chars:
        sections.append(f"### {char.canonical_name}")

        if char.aliases:
            sections.append(f"- Aliases: {', '.join(char.aliases)}")

        if char.physical_traits:
            traits = ', '.join(f"{k}: {v}" for k, v in char.physical_traits.items())
            sections.append(f"- Physical: {traits}")

        if char.current_status:
            sections.append(f"- Status: {char.current_status}")

        if char.voice_patterns:
            patterns = ', '.join(f"{k}: {v}" for k, v in char.voice_patterns.items())
            sections.append(f"- Voice: {patterns}")

        if char.relationships:
            rels = ', '.join(f"{r.get('name', 'Unknown')} ({r.get('type', 'unknown')})"
                            for r in char.relationships)
            sections.append(f"- Relationships: {rels}")

        sections.append("")

    # Add canonical name mappings
    if ledger.canonical_names:
        sections.append("## CANONICAL NAME MAPPINGS")
        sections.append("Use these exact spellings:")

        # Sort and deduplicate mappings
        seen = set()
        for alias, canonical in sorted(ledger.canonical_names.items()):
            if alias.lower() != canonical.lower() and canonical not in seen:
                sections.append(f"- {alias.title()} → {canonical}")
                seen.add(canonical)

        sections.append("")

    # Add locations if present
    if ledger.locations:
        sections.append("## KNOWN LOCATIONS")
        for location, details in sorted(ledger.locations.items()):
            if details:
                detail_str = ', '.join(f"{k}: {v}" for k, v in details.items())
                sections.append(f"- {location}: {detail_str}")
            else:
                sections.append(f"- {location}")
        sections.append("")

    return '\n'.join(sections)


def generate_character_summary(ledger: CharacterLedger, character_name: str) -> str:
    """Generate a detailed summary of a specific character.

    Args:
        ledger: CharacterLedger containing the character
        character_name: Name of the character (any variation)

    Returns:
        Formatted summary string
    """
    character = ledger.get_character(character_name)

    if not character:
        return f"Character '{character_name}' not found in ledger."

    sections = []
    sections.append(f"# {character.canonical_name}")
    sections.append("")

    if character.aliases:
        sections.append(f"**Also known as:** {', '.join(character.aliases)}")
        sections.append("")

    if character.physical_traits:
        sections.append("## Physical Appearance")
        for trait, value in character.physical_traits.items():
            sections.append(f"- **{trait.capitalize()}:** {value}")
        sections.append("")

    if character.voice_patterns:
        sections.append("## Voice & Speech")
        for pattern, value in character.voice_patterns.items():
            sections.append(f"- **{pattern.capitalize()}:** {value}")
        sections.append("")

    if character.current_status:
        sections.append(f"## Current Status\n{character.current_status}\n")

    if character.relationships:
        sections.append("## Relationships")
        for rel in character.relationships:
            name = rel.get("name", "Unknown")
            rel_type = rel.get("type", "unknown")
            sections.append(f"- **{name}:** {rel_type}")
        sections.append("")

    if character.chapter_appearances:
        sections.append("## Appearances")
        chapters = sorted(set(appearance.get("idx", -1) for appearance in character.chapter_appearances))
        if chapters:
            chapter_list = ", ".join(f"Chapter {c}" for c in chapters)
            sections.append(f"Appears in: {chapter_list}")
        sections.append("")

    return '\n'.join(sections)


def compare_characters(char1: CharacterState, char2: CharacterState) -> Dict[str, Any]:
    """Compare two CharacterState objects and identify differences.

    Args:
        char1: First CharacterState
        char2: Second CharacterState

    Returns:
        Dictionary with comparison results
    """
    differences = {
        "physical_traits": [],
        "voice_patterns": [],
        "aliases": [],
        "relationships": [],
        "status_changed": False
    }

    # Compare physical traits
    all_traits = set(char1.physical_traits.keys()) | set(char2.physical_traits.keys())
    for trait in all_traits:
        val1 = char1.physical_traits.get(trait)
        val2 = char2.physical_traits.get(trait)
        if val1 != val2:
            differences["physical_traits"].append({
                "trait": trait,
                "char1": val1,
                "char2": val2
            })

    # Compare voice patterns
    all_patterns = set(char1.voice_patterns.keys()) | set(char2.voice_patterns.keys())
    for pattern in all_patterns:
        val1 = char1.voice_patterns.get(pattern)
        val2 = char2.voice_patterns.get(pattern)
        if val1 != val2:
            differences["voice_patterns"].append({
                "pattern": pattern,
                "char1": val1,
                "char2": val2
            })

    # Compare aliases
    aliases1 = set(a.lower() for a in char1.aliases)
    aliases2 = set(a.lower() for a in char2.aliases)

    if aliases1 != aliases2:
        differences["aliases"] = {
            "only_in_char1": list(aliases1 - aliases2),
            "only_in_char2": list(aliases2 - aliases1)
        }

    # Compare status
    if char1.current_status != char2.current_status:
        differences["status_changed"] = True
        differences["status"] = {
            "char1": char1.current_status,
            "char2": char2.current_status
        }

    return differences
