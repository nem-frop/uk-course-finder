"""
Process QS Global + QS Subject + THE -> data/rankings.csv

Three sources merged into one rankings file:
- QS Global 2026: university-level global ranking
- QS Subject 2025: subject-level rankings (60 subjects across 61 sheets)
- THE World Rankings 2026: university-level global ranking (JSON embedded in HTML)

Output: Two CSVs:
- rankings_global.csv: university | qs_global_rank | qs_global_score | the_rank | the_score
- rankings_subject.csv: university | subject | qs_subject_rank | qs_subject_score
"""

import pandas as pd
import json
import re
from pathlib import Path

RAW_DIR = Path(__file__).parent.parent / "data_raw"
OUT_DIR = Path(__file__).parent.parent / "data"

# Map ranking source university names to our standardized names
# (We'll build this dynamically from what we find)
QS_NAME_MAP = {
    "Imperial College London": "Imperial College London",
    "University of Oxford": "University of Oxford",
    "University of Cambridge": "University of Cambridge",
    "UCL": "University College London",
    "UCL (University College London)": "University College London",
    "King's College London": "King's College London",
    "King's College London (KCL)": "King's College London",
    "The London School of Economics and Political Science (LSE)": "London School of Economics and Political Science",
    "London School of Economics and Political Science (LSE)": "London School of Economics and Political Science",
    "London School of Economics and Political Science": "London School of Economics and Political Science",
    "University of Edinburgh": "University of Edinburgh",
    "The University of Edinburgh": "University of Edinburgh",
    "University of Manchester": "University of Manchester",
    "The University of Manchester": "University of Manchester",
    "University of Bristol": "University of Bristol",
    "Durham University": "Durham University",
    "University of Warwick": "University of Warwick",
    "The University of Warwick": "University of Warwick",
    "University of Exeter": "University of Exeter",
}

THE_NAME_MAP = {
    "Imperial College London": "Imperial College London",
    "University of Oxford": "University of Oxford",
    "University of Cambridge": "University of Cambridge",
    "UCL": "University College London",
    "King's College London": "King's College London",
    "King\u2019s College London": "King's College London",
    "London School of Economics and Political Science": "London School of Economics and Political Science",
    "University of Edinburgh": "University of Edinburgh",
    "University of Manchester": "University of Manchester",
    "University of Bristol": "University of Bristol",
    "Durham University": "Durham University",
    "University of Warwick": "University of Warwick",
    "University of Exeter": "University of Exeter",
}

# Our 12 target universities
TARGET_UNIS = {
    "Durham University", "Imperial College London", "King's College London",
    "London School of Economics and Political Science", "University of Edinburgh",
    "University College London", "University of Bristol", "University of Cambridge",
    "University of Exeter", "University of Manchester", "University of Oxford",
    "University of Warwick",
}


def parse_rank(val):
    """Parse rank string like '=5', '101-150', '4' into a numeric value."""
    if pd.isna(val):
        return None
    s = str(val).strip().replace("=", "").replace("+", "")
    # Range like "101-150" -> take midpoint
    if "-" in s:
        parts = s.split("-")
        try:
            return (int(parts[0]) + int(parts[1])) / 2
        except ValueError:
            return None
    try:
        return float(s)
    except ValueError:
        return None


def process_qs_global():
    """Parse QS Global 2026 rankings Excel."""
    path = list((RAW_DIR / "rankings").glob("*QS World University Rankings*.xlsx"))[0]
    df = pd.read_excel(path, sheet_name="Sheet1", header=2)
    print(f"QS Global: {len(df)} institutions loaded")

    # Filter to UK
    uk = df[df["Country/Territory"] == "United Kingdom"].copy()
    print(f"QS Global UK: {len(uk)} institutions")

    # Standardize names
    uk["university"] = uk["Name"].map(QS_NAME_MAP).fillna(uk["Name"])

    # Parse rank
    uk["qs_global_rank"] = uk["Rank"].apply(parse_rank)
    uk["qs_global_score"] = pd.to_numeric(uk.get("SCORE", uk.get("Overall", pd.Series())), errors="coerce")

    # Find score column (might be named differently)
    score_cols = [c for c in uk.columns if "score" in c.lower() or c == "SCORE"]
    if score_cols and "qs_global_score" not in uk.columns:
        uk["qs_global_score"] = pd.to_numeric(uk[score_cols[0]], errors="coerce")

    return uk[["university", "qs_global_rank", "qs_global_score"]].copy()


def process_the_global():
    """Parse THE World Rankings 2026 from embedded JSON in HTML."""
    path = list((RAW_DIR / "rankings").glob("*Times Higher Education*.html"))[0]
    html = path.read_text(encoding="utf-8")

    # Find the __NEXT_DATA__ JSON
    match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if not match:
        print("ERROR: Could not find __NEXT_DATA__ in THE HTML")
        return pd.DataFrame()

    data = json.loads(match.group(1))

    # Navigate to rankings data
    rankings_data = data["props"]["pageProps"]["page"]["rankingsTableConfig"]["rankingsData"]["data"]
    print(f"THE Global: {len(rankings_data)} institutions loaded")

    rows = []
    for uni in rankings_data:
        if uni.get("location") == "United Kingdom":
            name = uni.get("name", "")
            std_name = THE_NAME_MAP.get(name, name)
            rows.append({
                "university": std_name,
                "the_rank": parse_rank(uni.get("rank")),
                "the_score": pd.to_numeric(uni.get("scores_overall"), errors="coerce"),
            })

    uk = pd.DataFrame(rows)
    print(f"THE Global UK: {len(uk)} institutions")
    return uk


def process_qs_subject():
    """Parse QS Subject 2025 rankings (60 subject sheets)."""
    path = list((RAW_DIR / "rankings").glob("*QS WUR by Subject*.xlsx"))[0]
    xl = pd.ExcelFile(path)

    # Skip the Menu sheet
    subject_sheets = [s for s in xl.sheet_names if s != "Menu"]
    print(f"QS Subject: {len(subject_sheets)} subject sheets found")

    all_rows = []
    for sheet_name in subject_sheets:
        df = pd.read_excel(path, sheet_name=sheet_name, header=10)

        # Filter to UK
        country_col = [c for c in df.columns if "country" in c.lower() or "territory" in c.lower()]
        if not country_col:
            continue
        uk = df[df[country_col[0]] == "United Kingdom"].copy()

        if uk.empty:
            continue

        # Find institution column
        inst_col = [c for c in df.columns if "institution" in c.lower() or "name" in c.lower()]
        if not inst_col:
            continue

        # Standardize names
        uk["university"] = uk[inst_col[0]].map(QS_NAME_MAP).fillna(uk[inst_col[0]])

        # Parse rank - column is named "2025"
        rank_col = "2025" if "2025" in uk.columns else uk.columns[0]
        uk["qs_subject_rank"] = uk[rank_col].apply(parse_rank)

        # Score column
        score_col = [c for c in uk.columns if c == "Score" or c == "SCORE"]
        uk["qs_subject_score"] = pd.to_numeric(uk[score_col[0]], errors="coerce") if score_col else None

        uk["subject"] = sheet_name

        all_rows.append(uk[["university", "subject", "qs_subject_rank", "qs_subject_score"]].copy())

    result = pd.concat(all_rows, ignore_index=True)
    print(f"QS Subject: {len(result)} total UK subject-university entries")
    return result


def process():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Process each source
    qs_global = process_qs_global()
    the_global = process_the_global()
    qs_subject = process_qs_subject()

    # Merge global rankings into one table
    global_rankings = pd.merge(qs_global, the_global, on="university", how="outer")
    global_rankings.to_csv(OUT_DIR / "rankings_global.csv", index=False, encoding="utf-8-sig")
    print(f"\nWrote {len(global_rankings)} universities to data/rankings_global.csv")

    # Show our 12 target unis
    targets = global_rankings[global_rankings["university"].isin(TARGET_UNIS)]
    print(f"Target unis with rankings: {len(targets)}/12")
    print(targets[["university", "qs_global_rank", "the_rank"]].sort_values("qs_global_rank").to_string(index=False))

    # Write subject rankings
    qs_subject.to_csv(OUT_DIR / "rankings_subject.csv", index=False, encoding="utf-8-sig")
    print(f"\nWrote {len(qs_subject)} subject ranking entries to data/rankings_subject.csv")

    # Show subjects available for target unis
    target_subjects = qs_subject[qs_subject["university"].isin(TARGET_UNIS)]
    print(f"Target uni subject entries: {len(target_subjects)}")
    print(f"Unique subjects: {target_subjects['subject'].nunique()}")


if __name__ == "__main__":
    process()
