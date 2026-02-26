"""
Process Med School Council xlsx + Med School Airtable CSV -> data/med_schools.csv

Two sources:
- Med School Council 2025: 44 schools with A-Level, IB, GCSE, UCAT/BMAT, interview, teaching style
- Med School Airtable (from Admit Stats): 35 schools with applicant/offer stats

Output: Merged med_schools.csv with requirements + stats.
"""

import pandas as pd
from pathlib import Path

RAW_DIR = Path(__file__).parent.parent / "data_raw"
OUT_DIR = Path(__file__).parent.parent / "data"

# Name normalization: map both sources to a common name
COUNCIL_NAME_MAP = {
    "Cardiff University": "Cardiff University",
    "Keele University": "Keele University",
    "Kent and Medway Medical School": "Kent and Medway Medical School",
    "Lancaster University": "Lancaster University",
    "Newcastle University": "Newcastle University",
    "University of St Andrews (A100/ScotCOM)": "University of St Andrews",
    "City St George's University of London": "St George's University of London",
    "Queen Mary, University of London": "Queen Mary University of London",
}

AIRTABLE_NAME_MAP = {
    "University of Cardiff": "Cardiff University",
    "University of Keele": "Keele University",
    "University of Kent": "Kent and Medway Medical School",
    "University of Lancaster": "Lancaster University",
    "University of Newcastle": "Newcastle University",
    "University of St Andrews": "University of St Andrews",
    "St George's University of London": "St George's University of London",
    "Queen Mary University of London": "Queen Mary University of London",
}


def process():
    # Load Med School Council
    council_path = list((RAW_DIR / "med_schools").glob("*Med*Council*2025*.xlsx"))
    if not council_path:
        print("ERROR: Med School Council xlsx not found")
        return
    council = pd.read_excel(council_path[0], sheet_name="Sheet1")
    print(f"Med School Council: {len(council)} schools loaded")

    # Standardize council names
    council["university"] = council["University Name"].map(COUNCIL_NAME_MAP).fillna(council["University Name"])

    # Rename columns
    council = council.rename(columns={
        "(Undergraduate) Course": "med_course",
        "A-Levels": "med_alevel_req",
        "IB Requirements": "med_ib_req",
        "GCSEs": "med_gcse_req",
        "UCAT/Test Requirements": "med_admission_test",
        "Interview Requirements": "med_interview_type",
        "Teaching Style": "med_teaching_style",
        "Work Experience Requirements": "med_work_experience",
        "Singapore Approved?": "med_singapore_approved",
        "URL (MSC)": "med_url",
        "Location": "med_location",
    })

    council_cols = [
        "university", "med_course", "med_alevel_req", "med_ib_req", "med_gcse_req",
        "med_admission_test", "med_interview_type", "med_teaching_style",
        "med_work_experience", "med_singapore_approved", "med_url", "med_location",
    ]
    council = council[[c for c in council_cols if c in council.columns]]

    # Load Airtable stats
    airtable = pd.read_csv(RAW_DIR / "med_schools" / "Med School-Grid view.csv")
    # Remove reference rows
    airtable = airtable[~airtable["School name"].str.contains("REFERENCE", case=False, na=False)]
    print(f"Med School Airtable: {len(airtable)} schools loaded")

    # Standardize airtable names
    airtable["university"] = airtable["School name"].map(AIRTABLE_NAME_MAP).fillna(airtable["School name"])

    # Rename columns
    airtable = airtable.rename(columns={
        "# Applicants (International)": "med_intl_applicants",
        "# Offers (International)": "med_intl_offers",
        "% Offers (International)": "med_intl_offer_pct",
        "# Places (International)": "med_intl_places",
        "Recognised in Singapore?": "med_singapore_recognised_at",
    })

    # Clean percentage column
    if "med_intl_offer_pct" in airtable.columns:
        airtable["med_intl_offer_pct"] = (
            airtable["med_intl_offer_pct"]
            .str.replace("%", "")
            .astype(float, errors="ignore")
        )

    airtable_cols = [
        "university", "med_intl_applicants", "med_intl_offers",
        "med_intl_offer_pct", "med_intl_places", "med_singapore_recognised_at",
    ]
    airtable = airtable[[c for c in airtable_cols if c in airtable.columns]]

    # Merge on university name
    merged = pd.merge(council, airtable, on="university", how="outer", indicator=True)

    print(f"\nMerge results:")
    print(f"  Both sources: {(merged['_merge'] == 'both').sum()}")
    print(f"  Council only: {(merged['_merge'] == 'left_only').sum()}")
    print(f"  Airtable only: {(merged['_merge'] == 'right_only').sum()}")

    # Show unmatched for debugging
    council_only = merged[merged["_merge"] == "left_only"]["university"].tolist()
    airtable_only = merged[merged["_merge"] == "right_only"]["university"].tolist()
    if council_only:
        print(f"  Council only names: {council_only}")
    if airtable_only:
        print(f"  Airtable only names: {airtable_only}")

    merged = merged.drop(columns=["_merge"])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    merged.to_csv(OUT_DIR / "med_schools.csv", index=False, encoding="utf-8-sig")
    print(f"\nWrote {len(merged)} med schools to data/med_schools.csv")


if __name__ == "__main__":
    process()
