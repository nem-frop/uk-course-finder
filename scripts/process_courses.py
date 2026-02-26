"""
Process Uni-Course 2025.xlsx -> data/courses.csv

Source: Uni-Course 2025.xlsx (2,437 courses across 12 universities)
Output: Cleaned CSV with standardized column names and university names.
"""

import pandas as pd
from pathlib import Path

RAW_DIR = Path(__file__).parent.parent / "data_raw"
OUT_DIR = Path(__file__).parent.parent / "data"

# Standardize university names for joining with rankings/other sources
UNI_NAME_MAP = {
    "Durham University": "Durham University",
    "Imperial College London": "Imperial College London",
    "King's College London, University of London": "King's College London",
    "London School of Economics and Political Science, University of London": "London School of Economics and Political Science",
    "The University of Edinburgh": "University of Edinburgh",
    "UCL (University College London)": "University College London",
    "University of Bristol": "University of Bristol",
    "University of Cambridge": "University of Cambridge",
    "University of Exeter": "University of Exeter",
    "University of Manchester": "University of Manchester",
    "University of Oxford": "University of Oxford",
    "University of Warwick": "University of Warwick",
}


def process():
    # Find course Excel file(s) in data_raw/courses/
    course_files = list((RAW_DIR / "courses").glob("*.xlsx"))
    if not course_files:
        print("ERROR: No .xlsx files found in data_raw/courses/")
        return
    df = pd.read_excel(course_files[0], sheet_name="Uni-Course")
    if len(course_files) > 1:
        for f in course_files[1:]:
            try:
                extra = pd.read_excel(f, sheet_name="Uni-Course")
                df = pd.concat([df, extra], ignore_index=True)
                print(f"  Also loaded {len(extra)} courses from {f.name}")
            except Exception as e:
                print(f"  Skipping {f.name}: {e}")
    print(f"Loaded {len(df)} courses from {df['school'].nunique()} universities")

    # Rename columns for clarity
    df = df.rename(columns={
        "school": "university_raw",
        "course_name": "course",
        "course_code": "ucas_code",
        "course_website_url": "course_url",
        "course_provider_url": "provider_url",
        "course_description": "description",
        "a-level_title": "alevel_title",
        "a-level_points": "alevel_grades",
        "a-level_description": "alevel_details",
        "ib_title": "ib_title",
        "ib_points": "ib_points",
        "ib_description": "ib_details",
        "degree-level": "degree_level",
        "study-mode": "study_mode",
    })

    # Standardize university names
    df["university"] = df["university_raw"].map(UNI_NAME_MAP)
    unmapped = df[df["university"].isna()]["university_raw"].unique()
    if len(unmapped) > 0:
        print(f"WARNING: Unmapped universities: {unmapped}")
        df["university"] = df["university"].fillna(df["university_raw"])

    # Clean course names - title case
    df["course"] = df["course"].str.strip().str.title()

    # Clean A-Level grades
    df["alevel_grades"] = df["alevel_grades"].str.strip()

    # Clean IB points - extract numeric where possible
    df["ib_points_raw"] = df["ib_points"]
    df["ib_points_numeric"] = df["ib_points"].str.extract(r"(\d+)").astype(float)

    # Select and order output columns
    out_cols = [
        "university", "course", "ucas_code", "degree_level", "study_mode", "duration",
        "alevel_grades", "alevel_details",
        "ib_points_raw", "ib_points_numeric", "ib_details",
        "course_url", "provider_url", "description",
        "qualification",
    ]
    df = df[[c for c in out_cols if c in df.columns]]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_DIR / "courses.csv", index=False, encoding="utf-8-sig")
    print(f"Wrote {len(df)} courses to data/courses.csv")
    print(f"Universities: {sorted(df['university'].unique())}")
    print(f"Columns: {list(df.columns)}")


if __name__ == "__main__":
    process()
