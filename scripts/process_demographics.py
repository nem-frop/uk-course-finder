"""Process UK Universities Infosheet into demographics CSV.

Source: archive/UK Universities Infosheet_shared.xlsx, sheet '_uni_data'
Output: data/demographics.csv

Contains student population breakdown by region for 50 UK universities.
"""

import pandas as pd
from pathlib import Path

RAW_PATH = Path(__file__).parent.parent.parent / "archive" / "UK Universities Infosheet_shared.xlsx"
OUT_PATH = Path(__file__).parent.parent / "data" / "demographics.csv"

# Map infosheet university names to our standard names
NAME_MAP = {
    "The University of Aberdeen": "University of Aberdeen",
    "The University of Bath": "University of Bath",
    "Queen's University Belfast": "Queen's University Belfast",
    "Birkbeck College": "Birkbeck, University of London",
    "The University of Birmingham": "University of Birmingham",
    "The University of Bristol": "University of Bristol",
    "Brunel University London": "Brunel University London",
    "The University of Cambridge": "University of Cambridge",
    "Cardiff University": "Cardiff University",
    "City, University of London": "City, University of London",
    "Coventry University": "Coventry University",
    "The University of Dundee": "University of Dundee",
    "University of Durham": "Durham University",
    "The University of East Anglia": "University of East Anglia",
    "The University of Edinburgh": "University of Edinburgh",
    "The University of Essex": "University of Essex",
    "The University of Exeter": "University of Exeter",
    "The University of Glasgow": "University of Glasgow",
    "Goldsmiths College": "Goldsmiths, University of London",
    "Imperial College of Science, Technology and Medicine": "Imperial College London",
    "The University of Kent": "University of Kent",
    "King's College London": "King's College London",
    "The University of Lancaster": "Lancaster University",
    "The University of Leeds": "University of Leeds",
    "The University of Leicester": "University of Leicester",
    "The University of Liverpool": "University of Liverpool",
    "University of the Arts, London": "University of the Arts London",
    "London School of Economics and Political Science": "London School of Economics and Political Science",
    "Loughborough University": "Loughborough University",
    "The University of Manchester": "University of Manchester",
    "Newcastle University": "Newcastle University",
    "University of Northumbria at Newcastle": "Northumbria University",
    "University of Nottingham": "University of Nottingham",
    "Oxford Brookes University": "Oxford Brookes University",
    "The University of Oxford": "University of Oxford",
    "Queen Mary University of London": "Queen Mary University of London",
    "The University of Reading": "University of Reading",
    "Royal Holloway and Bedford New College": "Royal Holloway, University of London",
    "The University of St. Andrews": "University of St Andrews",
    "SOAS University of London": "SOAS University of London",
    "The University of Sheffield": "University of Sheffield",
    "The University of Southampton": "University of Southampton",
    "The University of Strathclyde": "University of Strathclyde",
    "The University of Surrey": "University of Surrey",
    "The University of Sussex": "University of Sussex",
    "Swansea University": "Swansea University",
    "University College London": "University College London",
    "The University of Warwick": "University of Warwick",
    "University of the West of England, Bristol": "University of the West of England",
    "The University of York": "University of York",
}


def main():
    df = pd.read_excel(RAW_PATH, sheet_name="_uni_data", header=None)

    # Row 2 has field labels, data rows 3-52
    # Col 0: university name
    # Col 1: description
    # Col 2: overall rank, col 3: med rank, col 4: eng rank, col 5: sci rank, col 6: arts rank
    # Col 7-10: cohort size M/E/S/A
    # Col 11: total students, col 12: UK, col 13: EU, col 14: MidEast/Africa,
    # col 15: Asia, col 16: Australasia, col 17: Americas

    records = []
    for i in range(3, 53):
        raw_name = df.iloc[i, 0]
        if pd.isna(raw_name):
            continue

        name = str(raw_name).strip()
        std_name = NAME_MAP.get(name, name)

        total = pd.to_numeric(df.iloc[i, 11], errors="coerce")
        uk = pd.to_numeric(df.iloc[i, 12], errors="coerce")
        eu = pd.to_numeric(df.iloc[i, 13], errors="coerce")
        mideast = pd.to_numeric(df.iloc[i, 14], errors="coerce")
        asia = pd.to_numeric(df.iloc[i, 15], errors="coerce")
        australasia = pd.to_numeric(df.iloc[i, 16], errors="coerce")
        americas = pd.to_numeric(df.iloc[i, 17], errors="coerce")

        # Compute percentages
        international = total - uk if pd.notna(total) and pd.notna(uk) else None

        records.append({
            "university": std_name,
            "total_students": total,
            "uk_students": uk,
            "international_students": international,
            "eu_students": eu,
            "mideast_africa_students": mideast,
            "asia_students": asia,
            "australasia_students": australasia,
            "americas_students": americas,
            "international_pct": round(100 * international / total, 1) if international and total else None,
            "asia_pct": round(100 * asia / total, 1) if pd.notna(asia) and pd.notna(total) and total > 0 else None,
        })

    out = pd.DataFrame(records)
    out.to_csv(OUT_PATH, index=False)
    print(f"Wrote {len(out)} universities to {OUT_PATH}")

    # Show summary for our 12 current universities
    our = [
        "University of Oxford", "University of Cambridge", "Imperial College London",
        "University College London", "University of Edinburgh", "University of Manchester",
        "King's College London", "London School of Economics and Political Science",
        "University of Bristol", "University of Warwick", "Durham University",
        "University of Exeter",
    ]
    print("\nOur 12 universities:")
    for uni in our:
        row = out[out["university"] == uni]
        if not row.empty:
            r = row.iloc[0]
            print(f"  {uni}: {int(r['total_students']):,} students, "
                  f"Asia={r['asia_pct']:.0f}%, International={r['international_pct']:.0f}%")
        else:
            print(f"  {uni}: NOT FOUND IN DEMOGRAPHICS")


if __name__ == "__main__":
    main()
