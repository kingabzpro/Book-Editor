"""POV validation module for ensuring first-person consistency."""

import re
from typing import List, Dict, Tuple


def check_first_person_pov(text: str) -> List[Dict]:
    """Check for third-person slips in first-person narrative.

    Args:
        text: Chapter text to validate

    Returns:
        List of violation dictionaries with line number, text, and pattern
    """
    violations = []
    # Look for patterns like "he said", "she thought" when narrator should use "I"
    third_person_patterns = [
        r'\b(he|she|they)\s+(said|thought|felt|saw|heard|knew)\b',
        r'\b(him|her|them)\s+(being|feeling|thinking)\b',
    ]

    lines = text.split('\n')
    for i, line in enumerate(lines, 1):
        for pattern in third_person_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                violations.append({
                    'line': i,
                    'text': line.strip(),
                    'pattern': pattern
                })
    return violations


def check_no_em_dashes(text: str) -> List[int]:
    """Find all em dash (—) occurrences.

    Args:
        text: Chapter text to validate

    Returns:
        List of line numbers containing em dashes
    """
    lines = text.split('\n')
    violations = []
    for i, line in enumerate(lines, 1):
        if '—' in line:
            violations.append(i)
    return violations


def check_no_contractions(text: str) -> List[Dict]:
    """Find common contractions.

    Args:
        text: Chapter text to validate

    Returns:
        List of violation dictionaries with line number, contraction, and text
    """
    contractions = [
        "don't", "can't", "won't", "shouldn't", "couldn't", "wouldn't",
        "I'm", "you're", "he's", "she's", "it's", "we're", "they're",
        "I've", "you've", "we've", "they've",
        "I'll", "you'll", "he'll", "she'll", "it'll", "we'll", "they'll",
        "isn't", "aren't", "wasn't", "weren't", "didn't", "doesn't"
    ]

    violations = []
    lines = text.split('\n')
    for i, line in enumerate(lines, 1):
        for contraction in contractions:
            if contraction.lower() in line.lower():
                violations.append({
                    'line': i,
                    'contraction': contraction,
                    'text': line.strip()
                })
    return violations


def auto_correct_pov(text: str) -> str:
    """Auto-correct simple POV slips (basic substitutions).

    Note: This is a basic implementation. Context-aware corrections
    require more sophisticated NLP.

    Args:
        text: Chapter text to correct

    Returns:
        Text with basic corrections applied
    """
    # Simple corrections - can be expanded
    # This is a placeholder for future enhancement
    corrections = []
    return text


def generate_validation_report(text: str) -> Dict:
    """Generate comprehensive validation report.

    Args:
        text: Chapter text to validate

    Returns:
        Dictionary with all validation results
    """
    return {
        'pov_violations': check_first_person_pov(text),
        'em_dashes': check_no_em_dashes(text),
        'contractions': check_no_contractions(text),
        'word_count': len(text.split())
    }


def print_validation_report(report: Dict) -> None:
    """Print a formatted validation report to console.

    Args:
        report: Validation report dictionary from generate_validation_report()
    """
    print("\n" + "=" * 60)
    print("POV VALIDATION REPORT")
    print("=" * 60)

    # Word count
    print(f"\nWord Count: {report['word_count']}")

    # POV violations
    pov_count = len(report['pov_violations'])
    print(f"\nThird-Person POV Violations: {pov_count}")
    if pov_count > 0:
        print("  Found third-person slips in first-person narrative:")
        for v in report['pov_violations'][:10]:  # Show first 10
            print(f"  Line {v['line']}: {v['text'][:80]}...")
        if pov_count > 10:
            print(f"  ... and {pov_count - 10} more")
    else:
        print("  No third-person violations found!")

    # Em dashes
    em_count = len(report['em_dashes'])
    print(f"\nEm Dash (—) Violations: {em_count}")
    if em_count > 0:
        print(f"  Found em dashes on lines: {report['em_dashes'][:10]}")
        if em_count > 10:
            print(f"  ... and {em_count - 10} more lines")
    else:
        print("  No em dashes found!")

    # Contractions
    contract_count = len(report['contractions'])
    print(f"\nContraction Violations: {contract_count}")
    if contract_count > 0:
        print("  Found contractions:")
        for v in report['contractions'][:10]:  # Show first 10
            print(f"  Line {v['line']}: '{v['contraction']}' in {v['text'][:60]}...")
        if contract_count > 10:
            print(f"  ... and {contract_count - 10} more")
    else:
        print("  No contractions found!")

    # Summary
    total_issues = pov_count + em_count + contract_count
    print("\n" + "=" * 60)
    if total_issues == 0:
        print("EXCELLENT! No issues found.")
    else:
        print(f"TOTAL ISSUES: {total_issues}")
        if total_issues > 20:
            print("STATUS: Multiple issues detected - review recommended")
        elif total_issues > 5:
            print("STATUS: Some issues detected - manual review advised")
        else:
            print("STATUS: Minor issues - optional review")
    print("=" * 60 + "\n")
