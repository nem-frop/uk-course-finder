"""
Add structured subject-requirement columns to data/courses.csv.

Parses the free-text `alevel_details` / `ib_details` fields into:
    - required_subjects   ("Mathematics; Chemistry")
    - subject_req_status  ("specified" / "open" / "unknown")

using the shared logic in src/subject_requirements.py.

Idempotent: re-running recomputes the two columns in place. Run this AFTER
process_courses.py (which regenerates courses.csv from the raw extract).

Usage:
    python3 scripts/process_subject_requirements.py            # write changes
    python3 scripts/process_subject_requirements.py --report   # stats only, no write
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from subject_requirements import add_subject_requirement_columns  # noqa: E402

DATA = Path(__file__).parent.parent / "data" / "courses.csv"


def main(report_only: bool = False):
    df = pd.read_csv(DATA)
    n = len(df)
    df = add_subject_requirement_columns(df)

    status = df["subject_req_status"].value_counts()
    spec = int(status.get("specified", 0))
    print(f"Courses: {n}")
    print(f"  specified (>=1 required subject): {spec} ({100*spec//n}%)")
    print(f"  open (no specific subject):       {int(status.get('open', 0))}")
    print(f"  unknown (boilerplate/empty):      {int(status.get('unknown', 0))}")

    # Per-university availability
    df["_spec"] = df["subject_req_status"].eq("specified")
    per_uni = (df.groupby("university")["_spec"]
               .agg(["size", "sum"]))
    per_uni["pct"] = (100 * per_uni["sum"] / per_uni["size"]).round(0).astype(int)
    print("\nSpecified % by university (lowest first):")
    for uni, row in per_uni.sort_values("pct").iterrows():
        short = uni.replace("University of ", "").replace("University", "").strip()
        print(f"  {short[:24]:24} {int(row['sum']):>4}/{int(row['size']):<4} {row['pct']:>3}%")

    # Top subjects
    exploded = (df["required_subjects"].str.split("; ").explode())
    exploded = exploded[exploded.str.strip().astype(bool)]
    print("\nMost common required subjects:")
    for subj, cnt in exploded.value_counts().head(12).items():
        print(f"  {subj:24} {cnt}")

    df = df.drop(columns=["_spec"])
    if report_only:
        print("\n(--report: no file written)")
        return
    df.to_csv(DATA, index=False)
    print(f"\nWrote {DATA} with required_subjects + subject_req_status columns.")


if __name__ == "__main__":
    main(report_only="--report" in sys.argv)
