"""
Load all processed CSVs and merge into a single master DataFrame.

Data flow:
1. courses.csv = base (one row per course)
2. LEFT JOIN rankings_global on university -> QS/THE rank columns
3. LEFT JOIN rankings_subject on university+qs_subject -> subject rank
4. LEFT JOIN med_schools on university (medicine courses only) -> med columns
5. LEFT JOIN oxbridge_admissions on university+course -> offer rate columns
"""

import pandas as pd
from pathlib import Path

from subject_mapper import map_course_to_primary_subject, map_course_to_domain
from grade_parser import parse_alevel_grades, parse_ib_points

DATA_DIR = Path(__file__).parent.parent / "data"


# Oxbridge admissions course name aliases: admissions name -> courses.csv name
# These handle naming differences between the two data sources
OXBRIDGE_NAME_MAP = {
    # Oxford naming differences
    "Asian And Middle Eastern Studies": "Oriental Studies",
    "Biochemistry (Molecular And Cellular)": "Biochemistry",
    "Classics And Oriental Studies": "Classics And Asian And Middle Eastern Studies",
    "Earth Sciences (Geology)": "Earth Sciences",
    "History (Ancient And Modern)": "Ancient And Modern History",
    "Law (Jurisprudence)": "Law",
    "Maths": "Mathematics",
    "Maths And Computer Science": "Mathematics And Computer Science",
    "Maths And Philosophy": "Mathematics And Philosophy",
    "Maths And Statistics": "Mathematics And Statistics",
    "Philosophy, Politics And Economics (Ppe)": "Philosophy, Politics And Economics",
    "Psychology (Experimental)": "Experimental Psychology",
    "Psychology, Philosophy And Linguistics": "Psychology, Philosophy, And Linguistics",
    # Cambridge naming differences
    "Chemical Engineering & Biotechnology": "Chemical Engineering And Biotechnology",
    "Engineering": "Engineering",
    "Natural Sciences": "Natural Sciences",
}


def _merge_oxbridge(courses: pd.DataFrame, oxbridge: pd.DataFrame, offer_cols: list) -> pd.DataFrame:
    """Merge Oxbridge admissions data using smart name matching.

    Strategy:
    1. Try exact match on course name (title-cased)
    2. Try mapped name aliases for known mismatches
    3. For variant courses (e.g. "X With Foundation Year"), inherit parent course stats
    """
    # Build a lookup: (university, normalized_name) -> offer data row
    lookup = {}
    for _, row in oxbridge.iterrows():
        uni = row["university"]
        name = row["course_clean"]
        lookup[(uni, name)] = row[offer_cols]
        # Also add mapped aliases
        if name in OXBRIDGE_NAME_MAP:
            lookup[(uni, OXBRIDGE_NAME_MAP[name])] = row[offer_cols]

    # Match each course
    for col in offer_cols:
        courses[col] = pd.NA

    for idx, row in courses.iterrows():
        uni = row["university"]
        if uni not in ("University of Oxford", "University of Cambridge"):
            continue

        course_name = row["course"]

        # 1. Exact match
        key = (uni, course_name)
        if key in lookup:
            for col in offer_cols:
                courses.at[idx, col] = lookup[key][col]
            continue

        # 2. Strip common suffixes and try parent course
        matched = False
        for suffix in [" With Foundation Year", " With A Foundation Year",
                       " With Year Abroad", " With Placement Year",
                       " With Industrial Experience"]:
            if course_name.endswith(suffix):
                parent = course_name[:-len(suffix)]
                parent_key = (uni, parent)
                if parent_key in lookup:
                    for col in offer_cols:
                        courses.at[idx, col] = lookup[parent_key][col]
                    matched = True
                    break
        if matched:
            continue

        # 3. "Law With X Law" pattern -> inherit from "Law"
        if course_name.startswith("Law With ") and course_name.endswith(" Law"):
            law_key = (uni, "Law")
            if law_key in lookup:
                for col in offer_cols:
                    courses.at[idx, col] = lookup[law_key][col]

    # Convert to numeric
    for col in offer_cols:
        courses[col] = pd.to_numeric(courses[col], errors="coerce")

    return courses


def load_master_dataframe() -> pd.DataFrame:
    """Load and merge all data sources into a single DataFrame."""

    # 1. Base: courses
    courses = pd.read_csv(DATA_DIR / "courses.csv")

    # Add domain and QS subject mapping
    courses["domain"] = courses["course"].apply(map_course_to_domain)
    courses["qs_subject"] = courses["course"].apply(map_course_to_primary_subject)

    # Parse grades to numeric
    courses["alevel_score"] = courses["alevel_grades"].apply(parse_alevel_grades)
    courses["ib_score"] = courses["ib_points_numeric"]  # already numeric from processing

    # 2. Global rankings
    rankings = pd.read_csv(DATA_DIR / "rankings_global.csv")
    courses = courses.merge(
        rankings[["university", "qs_global_rank", "qs_global_score", "the_rank", "the_score"]],
        on="university",
        how="left"
    )

    # 3. Subject rankings
    subject_rankings = pd.read_csv(DATA_DIR / "rankings_subject.csv")
    # Join on university + qs_subject
    courses = courses.merge(
        subject_rankings[["university", "subject", "qs_subject_rank", "qs_subject_score"]],
        left_on=["university", "qs_subject"],
        right_on=["university", "subject"],
        how="left"
    )
    courses = courses.drop(columns=["subject"], errors="ignore")

    # 4. Med school data - join only for medicine/health courses
    med = pd.read_csv(DATA_DIR / "med_schools.csv")
    med_cols = [c for c in med.columns if c.startswith("med_") or c == "university"]
    med_courses = courses[courses["domain"] == "Medicine & Health"].merge(
        med[med_cols], on="university", how="left", suffixes=("", "_med")
    )
    non_med_courses = courses[courses["domain"] != "Medicine & Health"]
    courses = pd.concat([med_courses, non_med_courses], ignore_index=True)

    # 5. Oxbridge admissions - smart matching with name normalization
    oxbridge = pd.read_csv(DATA_DIR / "oxbridge_admissions.csv")
    offer_cols = ["total_applicants", "uk_applicants", "intl_applicants",
                  "total_offers", "uk_offers", "intl_offers",
                  "total_offer_pct", "uk_offer_pct", "intl_offer_pct"]
    courses = _merge_oxbridge(courses, oxbridge, offer_cols)

    # 6. Demographics - student population breakdown
    demo_path = DATA_DIR / "demographics.csv"
    if demo_path.exists():
        demo = pd.read_csv(demo_path)
        demo_cols = ["university", "total_students", "international_pct", "asia_pct"]
        courses = courses.merge(
            demo[demo_cols], on="university", how="left"
        )

    # Compute a combined "best rank" for sorting
    courses["best_global_rank"] = courses[["qs_global_rank", "the_rank"]].min(axis=1)

    # Normalize ranks to 0-100 scale (100 = best) for composite scoring
    courses = normalize_ranks(courses)

    return courses


def normalize_ranks(df: pd.DataFrame) -> pd.DataFrame:
    """Add normalized rank columns (0-100 scale, 100 = best) for composite scoring."""
    for col, norm_col in [
        ("qs_global_rank", "qs_global_norm"),
        ("the_rank", "the_norm"),
        ("qs_subject_rank", "qs_subject_norm"),
    ]:
        if col in df.columns:
            valid = df[col].dropna()
            if not valid.empty:
                max_rank = valid.max()
                df[norm_col] = df[col].apply(
                    lambda r: 100 * (1 - (r - 1) / (max_rank - 1)) if pd.notna(r) and max_rank > 1 else None
                )
            else:
                df[norm_col] = None
    return df


def categorize_admission_test(text: str) -> str:
    """Extract admission test type from descriptive text.

    BMAT was phased out after 2023 — only UCAT remains as a standard test.
    """
    if pd.isna(text) or not str(text).strip():
        return "Unknown"
    t = str(text).lower()
    if "ucat" in t:
        return "UCAT"
    return "Other"


def load_med_schools() -> pd.DataFrame:
    """Load med_schools.csv independently for the Medical Schools tab."""
    med = pd.read_csv(DATA_DIR / "med_schools.csv")
    med["test_category"] = med["med_admission_test"].apply(categorize_admission_test)
    return med


def get_filter_options(df: pd.DataFrame) -> dict:
    """Extract available filter options from the master DataFrame."""
    return {
        "universities": sorted(df["university"].dropna().unique()),
        "domains": sorted(df["domain"].dropna().unique()),
        "study_modes": sorted(df["study_mode"].dropna().unique()),
        "durations": sorted(df["duration"].dropna().unique()),
        "alevel_score_range": (
            int(df["alevel_score"].min()) if df["alevel_score"].notna().any() else 0,
            int(df["alevel_score"].max()) if df["alevel_score"].notna().any() else 18
        ),
        "ib_score_range": (
            int(df["ib_score"].min()) if df["ib_score"].notna().any() else 24,
            int(df["ib_score"].max()) if df["ib_score"].notna().any() else 45
        ),
    }


if __name__ == "__main__":
    df = load_master_dataframe()
    print(f"Master DataFrame: {len(df)} rows, {len(df.columns)} columns")
    print(f"\nColumns: {list(df.columns)}")
    print(f"\nUniversities: {df['university'].nunique()}")
    print(f"Domains: {df['domain'].nunique()}")
    print(f"With QS Subject rank: {df['qs_subject_rank'].notna().sum()}")
    print(f"With med data: {df['med_course'].notna().sum() if 'med_course' in df.columns else 0}")
    print(f"With Oxbridge data: {df['total_offer_pct'].notna().sum()}")
    print(f"\nSample rows:")
    sample_cols = ["university", "course", "domain", "alevel_grades", "qs_global_rank", "the_rank", "qs_subject_rank"]
    print(df[sample_cols].head(10).to_string(index=False))
