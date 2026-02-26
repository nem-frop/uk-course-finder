"""
Process Oxbridge Course list-Grid view.csv -> data/oxbridge_admissions.csv

Clean up the Oxbridge admissions data:
- Remove summary "All" rows
- Standardize university names
- Parse numeric fields
"""

import pandas as pd
from pathlib import Path

RAW_DIR = Path(__file__).parent.parent / "data_raw"
OUT_DIR = Path(__file__).parent.parent / "data"


def process():
    df = pd.read_csv(RAW_DIR / "oxbridge" / "Oxbridge Course list-Grid view.csv")
    print(f"Loaded {len(df)} rows")

    # Remove "All" summary rows
    df = df[df["Course Name"] != "All"].copy()
    print(f"After removing summary rows: {len(df)}")

    # Standardize university names
    df["university"] = df["University"].map({
        "Cambridge": "University of Cambridge",
        "Oxford": "University of Oxford",
    }).fillna(df["University"])

    # Rename columns
    df = df.rename(columns={
        "Course Name": "course",
        "Uni - Course": "uni_course_key",
        "Total applicants": "total_applicants",
        "UK applicants": "uk_applicants",
        "Intl applicants": "intl_applicants",
        "Total offers": "total_offers",
        "UK offers": "uk_offers",
        "Intl offers": "intl_offers",
        "Total offer %": "total_offer_pct",
        "UK offer %": "uk_offer_pct",
        "Intl offer %": "intl_offer_pct",
    })

    # Parse percentage columns (remove % sign)
    for pct_col in ["total_offer_pct", "uk_offer_pct", "intl_offer_pct"]:
        if pct_col in df.columns:
            df[pct_col] = pd.to_numeric(
                df[pct_col].astype(str).str.replace("%", "").str.strip(),
                errors="coerce"
            )

    # Clean course names to title case for matching
    df["course_clean"] = df["course"].str.strip().str.title()

    out_cols = [
        "university", "course", "course_clean",
        "total_applicants", "uk_applicants", "intl_applicants",
        "total_offers", "uk_offers", "intl_offers",
        "total_offer_pct", "uk_offer_pct", "intl_offer_pct",
    ]
    df = df[[c for c in out_cols if c in df.columns]]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_DIR / "oxbridge_admissions.csv", index=False, encoding="utf-8-sig")
    print(f"Wrote {len(df)} courses to data/oxbridge_admissions.csv")
    print(f"Cambridge: {(df['university'] == 'University of Cambridge').sum()}")
    print(f"Oxford: {(df['university'] == 'University of Oxford').sum()}")


if __name__ == "__main__":
    process()
