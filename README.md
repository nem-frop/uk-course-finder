# UK Course Finder

A Streamlit web app for exploring undergraduate courses across top UK universities, combining course data with global/subject rankings, entry requirements, and admissions statistics.

## Features

- **Course Explorer** - Browse 2,437 courses across 12 universities with filters for university, subject area, study mode, and duration
- **Multi-keyword search** - Comma-separated AND logic with exclude support (e.g. `comp, phys, -philo`)
- **A-Level & IB filtering** - Toggle between requirement views and filter by your grades
- **Composite ranking** - Weighted score blending global university rank with subject-specific rank, adjustable via slider
- **Oxbridge offer rates** - Per-course applicant/offer data shown conditionally when Oxford or Cambridge courses are in results
- **Medical Schools tab** - Dedicated view of 47 UK medical schools with requirements, admission tests, interview types, and international applicant statistics
- **CSV export** - Download filtered results with configurable row limits

## Data Sources

| Source | Coverage |
|--------|----------|
| UCAS course listings (2025 cycle) | 12 universities, 2,437 courses |
| QS World University Rankings 2026 | Global university ranks |
| QS World University Rankings by Subject 2025 | 60 subject-level ranks |
| Times Higher Education World Rankings 2026 | Global university ranks |
| Medical School Council 2025 | 44 medical schools with requirements |
| Oxbridge per-course admissions | 78 courses (30 Cambridge, 48 Oxford) |

### Universities Covered

Cambridge, Oxford, Imperial College London, UCL, King's College London, LSE, Edinburgh, Manchester, Bristol, Warwick, Durham, Exeter

### Known Gaps

- **Oxford STEM courses**: The source UCAS data (`Uni-Course 2025.xlsx`) contains 248 Oxford courses but 0 STEM subjects. This is a source data limitation, not a processing error. To fix: obtain an updated course listing that includes Oxford sciences and drop it into `data_raw/courses/`.

## Setup

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Architecture

```
uk-course-finder/
├── app.py                  # Streamlit app (two tabs: Course Explorer + Medical Schools)
├── src/
│   ├── data_loader.py      # Loads & merges 5 CSV sources into master DataFrame
│   ├── subject_mapper.py   # Maps course names to QS subject categories + domains
│   └── grade_parser.py     # Parses A-Level/IB grade strings to numeric scores
├── data/                   # Processed CSVs (committed, app reads from here)
│   ├── courses.csv
│   ├── rankings_global.csv
│   ├── rankings_subject.csv
│   ├── med_schools.csv
│   └── oxbridge_admissions.csv
├── data_raw/               # Raw source files (gitignored)
│   ├── courses/            # Drop new UCAS Excel files here
│   ├── rankings/           # QS + THE ranking files
│   ├── med_schools/        # Med School Council + Airtable data
│   └── oxbridge/           # Oxbridge admissions CSV
├── scripts/                # Data processing scripts
│   ├── process_courses.py
│   ├── process_rankings.py
│   ├── process_med.py
│   └── process_oxbridge.py
└── requirements.txt
```

## Updating Data

1. Drop updated source files into the appropriate `data_raw/` subdirectory
2. Run the relevant processing script: `python scripts/process_<source>.py`
3. Restart the Streamlit app to pick up new data
