"""
Parse A-Level and IB grade strings into numeric values for filtering.

A-Level grades: "A*A*A", "AAB", "ABB-BBB", "Not accepted"
IB points: "36 Points", "39", "36 Points (666)", "38-40 points"

Numeric scale for A-Level (UCAS tariff-like):
  A* = 6, A = 5, B = 4, C = 3, D = 2, E = 1

A "grade score" is the sum of the top 3 grades.
  A*A*A* = 18, A*A*A = 17, A*AA = 16, AAA = 15, AAB = 14, ABB = 13, BBB = 12, etc.
"""

import re


# Grade values
GRADE_VALUES = {
    "A*": 6,
    "A": 5,
    "B": 4,
    "C": 3,
    "D": 2,
    "E": 1,
}


def parse_alevel_grades(grade_str: str) -> int | None:
    """
    Parse an A-Level grade string into a numeric score.

    Examples:
        "A*A*A" -> 17
        "AAA" -> 15
        "AAB" -> 14
        "ABB-BBB" -> 13 (takes the higher end)
        "Not accepted" -> None
        None -> None
    """
    if not grade_str or str(grade_str).strip().lower() in ("nan", "not accepted", ""):
        return None

    s = str(grade_str).strip()

    # Handle ranges like "AAB-ABB" or "ABB - BBB" -> take the higher end (first part)
    if "-" in s and not s.startswith("-"):
        parts = s.split("-")
        # Check if it looks like grade ranges (not negative numbers)
        if any(c in parts[0] for c in "ABCDE*"):
            s = parts[0].strip()

    # Extract individual grades: find all A* and single letters
    grades = re.findall(r"A\*|[A-E]", s)

    if not grades:
        return None

    # Sum the values (typically 3 A-Levels)
    total = sum(GRADE_VALUES.get(g, 0) for g in grades)
    return total if total > 0 else None


def parse_ib_points(ib_str: str) -> int | None:
    """
    Parse an IB points string into a numeric value.

    Examples:
        "36 Points" -> 36
        "39" -> 39
        "36 Points (666)" -> 36
        "38-40 points" -> 38 (takes lower end = minimum requirement)
        None -> None
    """
    if not ib_str or str(ib_str).strip().lower() in ("nan", "not accepted", ""):
        return None

    s = str(ib_str).strip()

    # Extract the first number (the total points requirement)
    match = re.search(r"(\d+)", s)
    if match:
        val = int(match.group(1))
        # Sanity check: IB total is 24-45
        if 20 <= val <= 45:
            return val

    return None


def grade_score_to_display(score: int) -> str:
    """Convert a numeric grade score back to approximate grade string for display."""
    if score >= 18:
        return "A*A*A*"
    elif score >= 17:
        return "A*A*A"
    elif score >= 16:
        return "A*AA"
    elif score >= 15:
        return "AAA"
    elif score >= 14:
        return "AAB"
    elif score >= 13:
        return "ABB"
    elif score >= 12:
        return "BBB"
    elif score >= 11:
        return "BBC"
    elif score >= 10:
        return "BCC"
    elif score >= 9:
        return "CCC"
    else:
        return f"({score})"


def user_grades_to_score(grades: str) -> int | None:
    """Parse user-entered grades (for the 'I have these grades' filter)."""
    return parse_alevel_grades(grades)


# Grade options for the sidebar filter (from highest to lowest)
ALEVEL_GRADE_OPTIONS = [
    ("A*A*A* (18)", 18),
    ("A*A*A (17)", 17),
    ("A*AA (16)", 16),
    ("AAA (15)", 15),
    ("AAB (14)", 14),
    ("ABB (13)", 13),
    ("BBB (12)", 12),
    ("BBC (11)", 11),
    ("BCC (10)", 10),
    ("CCC (9)", 9),
]

IB_POINTS_OPTIONS = list(range(45, 23, -1))  # 45 down to 24


if __name__ == "__main__":
    # Test cases
    tests = [
        ("A*A*A", 17),
        ("A*AA", 16),
        ("AAA", 15),
        ("AAB", 14),
        ("ABB", 13),
        ("BBB", 12),
        ("AAB-ABB", 14),
        ("A*A*A*", 18),
        ("BBC", 11),
        ("Not accepted", None),
        (None, None),
        ("CCC", 9),
    ]

    print("A-Level grade parsing tests:")
    for input_str, expected in tests:
        result = parse_alevel_grades(input_str)
        status = "PASS" if result == expected else "FAIL"
        print(f"  {status}: '{input_str}' -> {result} (expected {expected})")

    ib_tests = [
        ("36 Points", 36),
        ("39", 39),
        ("36 Points (666)", 36),
        ("38-40 points", 38),
        ("26 points", 26),
        ("Not accepted", None),
        (None, None),
    ]

    print("\nIB points parsing tests:")
    for input_str, expected in ib_tests:
        result = parse_ib_points(input_str)
        status = "PASS" if result == expected else "FAIL"
        print(f"  {status}: '{input_str}' -> {result} (expected {expected})")
