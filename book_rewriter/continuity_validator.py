"""Continuity validation module for ensuring chapter-to-chapter consistency."""

from typing import List, Dict, Any, Optional
import re
from dataclasses import dataclass
import json
import os
import logging

logger = logging.getLogger(__name__)


@dataclass
class ContinuityReport:
    """Report of continuity validation results.

    Attributes:
        chapter_idx: Index of the chapter being validated
        pov_violations: List of POV violations found
        character_issues: List of character consistency issues
        location_issues: List of location continuity issues
        pacing_ok: Whether word count is within target range
        word_count: Total word count of the chapter
        target_min: Minimum target word count
        target_max: Maximum target word count
        restriction_violations: Dictionary of restriction violations (em_dashes, contractions)
        passed: Overall validation status
        errors: List of error messages
    """
    chapter_idx: int
    pov_violations: List[Dict]
    character_issues: List[str]
    location_issues: List[str]
    pacing_ok: bool
    word_count: int
    target_min: int
    target_max: int
    restriction_violations: Dict[str, List]
    passed: bool = True
    errors: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []

    def to_dict(self) -> Dict:
        """Convert report to dictionary for serialization."""
        return {
            'chapter_idx': self.chapter_idx,
            'pov_violations': self.pov_violations,
            'character_issues': self.character_issues,
            'location_issues': self.location_issues,
            'pacing_ok': self.pacing_ok,
            'word_count': self.word_count,
            'target_min': self.target_min,
            'target_max': self.target_max,
            'restriction_violations': self.restriction_violations,
            'passed': self.passed,
            'errors': self.errors
        }

    def get_summary(self) -> str:
        """Get a human-readable summary of the validation report."""
        lines = []
        lines.append(f"=== Continuity Report: Chapter {self.chapter_idx} ===")
        lines.append(f"Word Count: {self.word_count} (target: {self.target_min}-{self.target_max})")
        lines.append(f"Pacing: {'OK' if self.pacing_ok else 'OUT OF RANGE'}")

        pov_count = len(self.pov_violations)
        lines.append(f"POV Violations: {pov_count}")

        em_dash_count = len(self.restriction_violations.get('em_dashes', []))
        contraction_count = len(self.restriction_violations.get('contractions', []))
        lines.append(f"Em Dashes: {em_dash_count}")
        lines.append(f"Contractions: {contraction_count}")

        lines.append(f"Character Issues: {len(self.character_issues)}")
        lines.append(f"Location Issues: {len(self.location_issues)}")

        lines.append(f"Overall Status: {'PASSED' if self.passed else 'FAILED'}")

        if self.errors:
            lines.append(f"Errors: {len(self.errors)}")

        return "\n".join(lines)


def validate_chapter_continuity(
    chapter_text: str,
    chapter_idx: int,
    character_ledger: Any,
    previous_chapters: List[str],
    target_min: int = 2000,
    target_max: int = 3500
) -> ContinuityReport:
    """Comprehensive continuity validation for a chapter.

    This function performs multiple validation checks:
    - POV consistency (first-person narrative)
    - Stylistic restrictions (no em dashes, no contractions)
    - Character consistency
    - Location continuity
    - Word count pacing

    Args:
        chapter_text: The chapter text to validate
        chapter_idx: Index of the chapter being validated
        character_ledger: CharacterLedger object with character information
        previous_chapters: List of previous chapter texts for context
        target_min: Minimum target word count
        target_max: Maximum target word count

    Returns:
        ContinuityReport with validation results
    """
    from book_rewriter.pov_validator import check_first_person_pov, check_no_em_dashes, check_no_contractions
    from book_rewriter.character_tracker import validate_character_consistency

    errors = []
    passed = True

    # Word count validation
    word_count = len(chapter_text.split())
    pacing_ok = target_min <= word_count <= target_max

    if not pacing_ok:
        passed = False
        if word_count < target_min:
            errors.append(f"Word count ({word_count}) below minimum ({target_min})")
        else:
            errors.append(f"Word count ({word_count}) above maximum ({target_max})")

    # POV validation
    try:
        pov_violations = check_first_person_pov(chapter_text)
    except Exception as e:
        logger.error(f"POV validation error: {e}")
        pov_violations = []
        errors.append(f"POV validation failed: {str(e)}")
        passed = False

    # Restriction validation
    try:
        em_dashes = check_no_em_dashes(chapter_text)
        contractions = check_no_contractions(chapter_text)
        restriction_violations = {
            'em_dashes': em_dashes,
            'contractions': contractions
        }
    except Exception as e:
        logger.error(f"Restriction validation error: {e}")
        restriction_violations = {'em_dashes': [], 'contractions': []}
        errors.append(f"Restriction validation failed: {str(e)}")
        passed = False

    # Character validation
    try:
        character_issues = validate_character_consistency(
            chapter_text,
            character_ledger,
            is_first_person=True  # Smart validation: skip pronoun false positives
        )
    except Exception as e:
        logger.error(f"Character validation error: {e}")
        character_issues = []
        errors.append(f"Character validation failed: {str(e)}")
        passed = False

    # Location continuity (basic implementation)
    location_issues = []
    if previous_chapters:
        # Check for sudden location changes without transition
        # This is a placeholder for more sophisticated location tracking
        location_indicators = ['location:', 'scene:', 'setting:', 'at the', 'in the']
        for indicator in location_indicators:
            if indicator in chapter_text.lower():
                # Check if this location was mentioned in recent chapters
                found_in_previous = any(indicator in prev.lower() for prev in previous_chapters[-2:])
                if not found_in_previous:
                    location_issues.append(f"New location introduced without clear transition: {indicator}")

    # Update passed status based on findings
    if len(pov_violations) > 5:
        passed = False
        errors.append(f"Too many POV violations: {len(pov_violations)}")

    if len(restriction_violations['em_dashes']) > 10:
        passed = False
        errors.append(f"Too many em dashes: {len(restriction_violations['em_dashes'])}")

    if len(restriction_violations['contractions']) > 10:
        passed = False
        errors.append(f"Too many contractions: {len(restriction_violations['contractions'])}")

    return ContinuityReport(
        chapter_idx=chapter_idx,
        pov_violations=pov_violations,
        character_issues=character_issues,
        location_issues=location_issues,
        pacing_ok=pacing_ok,
        word_count=word_count,
        target_min=target_min,
        target_max=target_max,
        restriction_violations=restriction_violations,
        passed=passed,
        errors=errors
    )


def validate_batch_continuity(
    chapters: List[str],
    character_ledger: Any,
    target_min: int = 2000,
    target_max: int = 3500
) -> List[ContinuityReport]:
    """Validate continuity across multiple chapters.

    Args:
        chapters: List of chapter texts to validate
        character_ledger: CharacterLedger object with character information
        target_min: Minimum target word count
        target_max: Maximum target word count

    Returns:
        List of ContinuityReport objects
    """
    reports = []

    for idx, chapter_text in enumerate(chapters):
        # Get previous chapters for context
        previous_chapters = chapters[:idx]

        report = validate_chapter_continuity(
            chapter_text=chapter_text,
            chapter_idx=idx,
            character_ledger=character_ledger,
            previous_chapters=previous_chapters,
            target_min=target_min,
            target_max=target_max
        )

        reports.append(report)

    return reports


def save_validation_report(report: ContinuityReport, path: str) -> None:
    """Save validation report to JSON file.

    Args:
        report: ContinuityReport to save
        path: File path to save the report
    """
    try:
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else '.', exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(report.to_dict(), f, indent=2)
        logger.info(f"Validation report saved to {path}")
    except Exception as e:
        logger.error(f"Failed to save validation report: {e}")
        raise


def load_validation_report(path: str) -> ContinuityReport:
    """Load validation report from JSON file.

    Args:
        path: File path to load the report from

    Returns:
        ContinuityReport object
    """
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        return ContinuityReport(**data)
    except Exception as e:
        logger.error(f"Failed to load validation report: {e}")
        raise


def print_validation_report(report: ContinuityReport) -> None:
    """Print a formatted validation report to console.

    Args:
        report: ContinuityReport to print
    """
    print("\n" + "=" * 70)
    print(f"CONTINUITY VALIDATION REPORT: Chapter {report.chapter_idx}")
    print("=" * 70)

    # Word count and pacing
    print(f"\nWord Count: {report.word_count}")
    print(f"Target Range: {report.target_min} - {report.target_max}")
    pacing_status = "OK" if report.pacing_ok else "OUT OF RANGE"
    print(f"Pacing: {pacing_status}")

    # POV violations
    pov_count = len(report.pov_violations)
    print(f"\nPOV Violations: {pov_count}")
    if pov_count > 0:
        print("  Found third-person slips:")
        for v in report.pov_violations[:5]:
            print(f"  Line {v['line']}: {v['text'][:70]}...")
        if pov_count > 5:
            print(f"  ... and {pov_count - 5} more")

    # Restriction violations
    em_dash_count = len(report.restriction_violations.get('em_dashes', []))
    contraction_count = len(report.restriction_violations.get('contractions', []))

    print(f"\nEm Dash Violations: {em_dash_count}")
    if em_dash_count > 0:
        dashes = report.restriction_violations['em_dashes']
        print(f"  Found on lines: {dashes[:10]}")
        if em_dash_count > 10:
            print(f"  ... and {em_dash_count - 10} more")

    print(f"\nContraction Violations: {contraction_count}")
    if contraction_count > 0:
        contractions = report.restriction_violations['contractions']
        print("  Found contractions:")
        for v in contractions[:5]:
            print(f"  Line {v['line']}: '{v['contraction']}' in {v['text'][:60]}...")
        if contraction_count > 5:
            print(f"  ... and {contraction_count - 5} more")

    # Character issues
    print(f"\nCharacter Issues: {len(report.character_issues)}")
    if report.character_issues:
        for issue in report.character_issues[:5]:
            print(f"  - {issue}")
        if len(report.character_issues) > 5:
            print(f"  ... and {len(report.character_issues) - 5} more")

    # Location issues
    print(f"\nLocation Issues: {len(report.location_issues)}")
    if report.location_issues:
        for issue in report.location_issues:
            print(f"  - {issue}")

    # Errors
    if report.errors:
        print(f"\nErrors: {len(report.errors)}")
        for error in report.errors:
            print(f"  - {error}")

    # Summary
    total_issues = (pov_count + em_dash_count + contraction_count +
                   len(report.character_issues) + len(report.location_issues))

    print("\n" + "=" * 70)
    print(f"Overall Status: {'PASSED' if report.passed else 'FAILED'}")
    print(f"Total Issues: {total_issues}")

    if report.passed:
        print("Quality: EXCELLENT - Chapter ready for production")
    elif total_issues > 20:
        print("Quality: POOR - Major revision required")
    elif total_issues > 10:
        print("Quality: FAIR - Revision recommended")
    else:
        print("Quality: GOOD - Minor polish may be needed")

    print("=" * 70 + "\n")


def generate_batch_summary(reports: List[ContinuityReport]) -> str:
    """Generate a summary report for multiple chapters.

    Args:
        reports: List of ContinuityReport objects

    Returns:
        Formatted summary string
    """
    lines = []
    lines.append("=" * 70)
    lines.append("BATCH CONTINUITY VALIDATION SUMMARY")
    lines.append("=" * 70)
    lines.append("")

    total_chapters = len(reports)
    passed_chapters = sum(1 for r in reports if r.passed)
    failed_chapters = total_chapters - passed_chapters

    lines.append(f"Total Chapters: {total_chapters}")
    lines.append(f"Passed: {passed_chapters}")
    lines.append(f"Failed: {failed_chapters}")
    lines.append("")

    # Word count statistics
    word_counts = [r.word_count for r in reports]
    avg_word_count = sum(word_counts) / len(word_counts) if word_counts else 0
    min_word_count = min(word_counts) if word_counts else 0
    max_word_count = max(word_counts) if word_counts else 0

    lines.append("Word Count Statistics:")
    lines.append(f"  Average: {avg_word_count:.0f}")
    lines.append(f"  Range: {min_word_count} - {max_word_count}")
    lines.append("")

    # Issue statistics
    total_pov = sum(len(r.pov_violations) for r in reports)
    total_em_dashes = sum(len(r.restriction_violations.get('em_dashes', [])) for r in reports)
    total_contractions = sum(len(r.restriction_violations.get('contractions', [])) for r in reports)
    total_char_issues = sum(len(r.character_issues) for r in reports)
    total_loc_issues = sum(len(r.location_issues) for r in reports)

    lines.append("Total Issues Across All Chapters:")
    lines.append(f"  POV Violations: {total_pov}")
    lines.append(f"  Em Dashes: {total_em_dashes}")
    lines.append(f"  Contractions: {total_contractions}")
    lines.append(f"  Character Issues: {total_char_issues}")
    lines.append(f"  Location Issues: {total_loc_issues}")
    lines.append("")

    # Per-chapter breakdown
    lines.append("Per-Chapter Results:")
    for r in reports:
        status = "PASS" if r.passed else "FAIL"
        lines.append(f"  Chapter {r.chapter_idx}: {status} ({r.word_count} words)")

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)
