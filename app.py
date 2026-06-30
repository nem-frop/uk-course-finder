"""
UK Course Finder - Streamlit Web Application

A two-tab course explorer combining course data, rankings, medical school
requirements, and Oxbridge admissions statistics.
"""

import streamlit as st
import pandas as pd
import numpy as np
import re
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))
from data_loader import load_master_dataframe, get_filter_options
from grade_parser import ALEVEL_GRADE_OPTIONS, grade_score_to_display

# Page config
st.set_page_config(
    page_title="UK Course Finder",
    page_icon="\U0001f393",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Password gate ---
APP_PASSWORD = "courses"


def check_password():
    """Simple password check. Returns True if authenticated."""
    if st.session_state.get("authenticated"):
        return True

    st.markdown('<p style="font-size:2rem;font-weight:700;color:#1B365D;">UK Course Finder</p>', unsafe_allow_html=True)
    password = st.text_input("Enter password to continue", type="password")
    if password:
        if password == APP_PASSWORD:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    return False


if not check_password():
    st.stop()

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1B365D;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #555;
        margin-bottom: 1.2rem;
        font-style: italic;
    }
    .stMultiSelect [data-baseweb="tag"] {
        background-color: #1B365D;
    }
    div[data-testid="stExpander"] details summary p {
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)


# --- Search helpers ---

def parse_filter_groups(text: str) -> list[list[str]]:
    """Parse a filter string into OR-groups of AND-terms.

    The '+' operator joins terms that must ALL be present (AND); spaces or
    commas separate alternatives (OR). Commas allow multi-word phrases.

        "busi mana"               -> [["busi"], ["mana"]]            (busi OR mana)
        "econ+psych"              -> [["econ", "psych"]]             (econ AND psych)
        "econ+psych, mgmt+psych"  -> [["econ","psych"], ["mgmt","psych"]]
        "computer science, law"   -> [["computer science"], ["law"]]
    """
    if not text or not text.strip():
        return []
    # Collapse spaces around '+' so "econ + psych" reads as one AND-group.
    norm = re.sub(r"\s*\+\s*", "+", text)
    units = norm.split(",") if "," in norm else norm.split()
    groups = []
    for unit in units:
        terms = [t.strip().lower() for t in unit.split("+") if t.strip()]
        if terms:
            groups.append(terms)
    return groups


def apply_include_exclude(series: pd.Series, include_text: str, exclude_text: str) -> pd.Series:
    """Boolean mask for include (OR) / exclude (AND) keyword filtering.

    Within a group, '+' means AND (all terms must be present). Between groups,
    the logic is OR for includes and AND-not for excludes:

    - Includes: a row is kept if it matches ANY group (and a group matches only
      when ALL of its '+'-joined terms are present).
    - Excludes: a row is dropped if it matches ANY group; kept only if it
      matches none.

    Empty inputs are no-ops (all rows pass that test).
    """
    inc_groups = parse_filter_groups(include_text)
    exc_groups = parse_filter_groups(exclude_text)
    if not inc_groups and not exc_groups:
        return pd.Series(True, index=series.index)

    lower = series.str.lower().fillna("")

    def group_match(group: list[str]) -> pd.Series:
        # AND across the terms in one group
        m = pd.Series(True, index=series.index)
        for term in group:
            m &= lower.str.contains(term, na=False, regex=False)
        return m

    # Include: OR across groups (kept if any group matches)
    if inc_groups:
        include_mask = pd.Series(False, index=series.index)
        for g in inc_groups:
            include_mask |= group_match(g)
    else:
        include_mask = pd.Series(True, index=series.index)

    # Exclude: drop if any group matches (kept only if none match)
    exclude_mask = pd.Series(True, index=series.index)
    for g in exc_groups:
        exclude_mask &= ~group_match(g)

    return include_mask & exclude_mask


# --- Data loading ---

@st.cache_data(ttl=3600)
def load_data():
    """Load the master DataFrame with SMC + demographics + subject reqs + multi-domain (cached v5)."""
    return load_master_dataframe()


def format_rank(val):
    """Format rank value for display."""
    if pd.isna(val):
        return "-"
    v = int(val) if val == int(val) else val
    return str(v)


def compute_weighted_score(df: pd.DataFrame, global_weight: float) -> pd.Series:
    """Compute weighted composite score from normalized ranks.

    global_weight: 0.0 = subject only, 1.0 = global only
    """
    subject_weight = 1.0 - global_weight

    # Global component: average of QS global and THE (use whichever available)
    global_scores = df[["qs_global_norm", "the_norm"]].mean(axis=1, skipna=True)
    subject_scores = df["qs_subject_norm"]

    has_global = global_scores.notna()
    has_subject = subject_scores.notna()

    score = pd.Series(np.nan, index=df.index)

    # Both available: weighted blend
    both = has_global & has_subject
    score[both] = (
        global_weight * global_scores[both] +
        subject_weight * subject_scores[both]
    )

    # Only global available
    only_global = has_global & ~has_subject
    score[only_global] = global_scores[only_global]

    # Only subject available
    only_subject = ~has_global & has_subject
    score[only_subject] = subject_scores[only_subject]

    return score


def build_display_df(filtered, req_mode, has_oxbridge):
    """Build the display DataFrame with proper formatting and column selection."""
    wanted_cols = ["university", "course", "course_url", "domains_all",
                   "alevel_grades", "ib_points_raw",
                   "required_subjects",
                   "qs_global_rank", "the_rank", "qs_subject_rank",
                   "weighted_score",
                   "duration", "study_mode",
                   "total_offer_pct", "intl_offer_pct",
                   "asia_pct", "international_pct",
                   "smc_approved"]
    available_wanted = [c for c in wanted_cols if c in filtered.columns]
    display_df = filtered[available_wanted].copy()

    # Build a readable "Required Subjects" cell that distinguishes "open" from "unknown"
    if "required_subjects" in display_df.columns and "subject_req_status" in filtered.columns:
        status = filtered["subject_req_status"].values
        def _fmt_subj(i, val):
            if status[i] == "open":
                return "Any subjects"
            if status[i] != "specified" or not str(val).strip():
                return "Not listed"
            return val
        display_df["required_subjects"] = [
            _fmt_subj(i, v) for i, v in enumerate(display_df["required_subjects"])
        ]

    display_df = display_df.rename(columns={
        "university": "University",
        "course": "Course",
        "course_url": "Link",
        "domains_all": "Subject Area",
        "alevel_grades": "A-Level Req",
        "ib_points_raw": "IB Req",
        "required_subjects": "Required Subjects",
        "qs_global_rank": "QS Global",
        "the_rank": "THE Global",
        "qs_subject_rank": "QS Subject",
        "weighted_score": "Score",
        "duration": "Duration",
        "study_mode": "Study Mode",
        "total_offer_pct": "Offer %",
        "intl_offer_pct": "Intl Offer %",
        "asia_pct": "Asia %",
        "international_pct": "Intl %",
        "smc_approved": "SMC",
    })

    # Format SMC column
    if "SMC" in display_df.columns:
        display_df["SMC"] = display_df["SMC"].apply(
            lambda x: ("Yes" if x == "Yes" else "No") if pd.notna(x) else "-"
        )

    for rank_col in ["QS Global", "THE Global", "QS Subject"]:
        if rank_col in display_df.columns:
            display_df[rank_col] = display_df[rank_col].apply(format_rank)

    if "Score" in display_df.columns:
        display_df["Score"] = display_df["Score"].apply(
            lambda x: f"{x:.1f}" if pd.notna(x) else "-"
        )

    for pct_col in ["Offer %", "Intl Offer %", "Asia %", "Intl %"]:
        if pct_col in display_df.columns:
            display_df[pct_col] = display_df[pct_col].apply(
                lambda x: f"{x:.0f}%" if pd.notna(x) else "-"
            )

    show_cols = ["University", "Course", "Link", "Subject Area"]
    if req_mode == "A-Level":
        show_cols.append("A-Level Req")
    else:
        show_cols.append("IB Req")
    show_cols.append("Required Subjects")
    show_cols.extend(["QS Global", "THE Global", "QS Subject", "Score",
                       "Asia %", "Intl %"])
    if has_oxbridge:
        show_cols.extend(["Offer %", "Intl Offer %"])
    # Only show SMC column when results contain medicine courses
    if "SMC" in display_df.columns and display_df["SMC"].ne("-").any():
        show_cols.append("SMC")

    available_show = [c for c in show_cols if c in display_df.columns]
    return display_df, available_show


COLUMN_CONFIG = {
    "University": st.column_config.TextColumn(width="medium"),
    "Course": st.column_config.TextColumn(width="large"),
    "Link": st.column_config.LinkColumn(width="small", display_text="View"),
    "Subject Area": st.column_config.TextColumn(width="medium"),
    "A-Level Req": st.column_config.TextColumn(width="small"),
    "IB Req": st.column_config.TextColumn(width="small"),
    "Required Subjects": st.column_config.TextColumn(width="medium"),
    "QS Global": st.column_config.TextColumn(width="small"),
    "THE Global": st.column_config.TextColumn(width="small"),
    "QS Subject": st.column_config.TextColumn(width="small"),
    "Score": st.column_config.TextColumn(width="small"),
    "Offer %": st.column_config.TextColumn(width="small"),
    "Intl Offer %": st.column_config.TextColumn(width="small"),
    "Asia %": st.column_config.TextColumn(width="small"),
    "Intl %": st.column_config.TextColumn(width="small"),
    "SMC": st.column_config.TextColumn(width="small"),
}


_editor_counter = 0


def render_dataframe(display_df, available_show, height=600, enable_shortlist=False, source_df=None):
    """Render a styled st.dataframe, optionally with shortlist checkboxes."""
    global _editor_counter

    if enable_shortlist and source_df is not None:
        # Use st.data_editor with a Select column for shortlisting
        shortlist = st.session_state.get("shortlist", set())
        # Create unique keys from university + course + ucas_code
        keys = (source_df["university"] + " | " + source_df["course"] + " | " + source_df["ucas_code"].fillna("")).values
        editor_df = display_df[available_show].copy()
        editor_df.insert(0, "⭐", [k in shortlist for k in keys])

        col_cfg = {k: v for k, v in COLUMN_CONFIG.items() if k in available_show}
        col_cfg["⭐"] = st.column_config.CheckboxColumn(
            "⭐", help="Add to shortlist", default=False, width="small"
        )

        _editor_counter += 1
        edited = st.data_editor(
            editor_df,
            hide_index=True,
            width="stretch",
            height=height,
            column_config=col_cfg,
            disabled=[c for c in available_show],  # Only star column is editable
            key=f"shortlist_editor_{_editor_counter}",
        )

        # Sync selections back to session state
        new_shortlist = set()
        for i, selected in enumerate(edited["⭐"]):
            if selected and i < len(keys):
                new_shortlist.add(keys[i])
        # Preserve selections from other views/filters
        other_selections = shortlist - set(keys)
        st.session_state["shortlist"] = new_shortlist | other_selections
    else:
        st.dataframe(
            display_df[available_show],
            hide_index=True,
            width="stretch",
            height=height,
            column_config={k: v for k, v in COLUMN_CONFIG.items() if k in available_show}
        )


# --- Landing page ---

def show_landing_page(df):
    """Show the landing page when no filters are active."""
    st.info("Use the **sidebar filters** or **search for a course** to get started.")

    # Quick stats
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Courses", f"{len(df):,}")
    with col2:
        st.metric("Universities", df["university"].nunique())
    with col3:
        st.metric("Subject Areas", df["domain"].nunique())

    st.divider()

    # How it works
    st.subheader("How It Works")
    how_cols = st.columns(4)
    with how_cols[0]:
        st.markdown("**1. Search Courses**")
        st.caption("Filter course names, subject areas, and entry requirements with separate Includes (match any) and Excludes (drop any) boxes")
    with how_cols[1]:
        st.markdown("**2. Filter**")
        st.caption("Narrow by university, subject area, grade requirements, study mode, and duration")
    with how_cols[2]:
        st.markdown("**3. Compare Rankings**")
        st.caption("See QS and THE global ranks plus subject-specific ranks. Adjust the weighting slider to your preference")
    with how_cols[3]:
        st.markdown("**4. Export**")
        st.caption("Download your filtered results as CSV for offline analysis")

    st.divider()

    # Two-column layout
    left_col, right_col = st.columns([1, 1])

    with left_col:
        st.subheader("What's Included")
        n_courses = len(df)
        n_unis = df["university"].nunique()
        n_with_subj = df["qs_subject_rank"].notna().sum()
        n_smc = df["smc_approved"].notna().sum() if "smc_approved" in df.columns else 0
        st.markdown(f"""
        **Course Data (2025 UCAS cycle):**
        - {n_courses:,} undergraduate courses across {n_unis} universities
        - A-Level and IB entry requirements
        - Course URLs and UCAS codes
        - Singapore Medical Council (SMC) approval status for {n_smc} medicine courses

        **Rankings:** QS Global + Subject (60 subjects) + THE Global
        - {n_with_subj:,}/{n_courses:,} courses have subject-level rank data

        **Oxbridge admissions:** Per-course offer rates for Oxford and Cambridge

        **Demographics:** Student population, international %, and Asian student % per university
        """)

    with right_col:
        st.subheader("Data Sources")
        st.markdown("""
        **Rankings (2025-26):**
        - QS World University Rankings 2026 (global)
        - QS Subject Rankings 2025 (60 subjects)
        - Times Higher Education World Rankings 2026

        **Admissions:**
        - Oxbridge per-course offer rates (92 courses matched)
        - Medical School Council requirements (44 schools)
        - International applicant statistics (34 schools)
        - Student demographics (50 universities)
        """)

    # Grade data advisory
    st.warning("""
**Grade Requirements — Please Verify Before Relying On This Data**

A-Level grades are generally accurate across all universities. IB scores have been audited and corrected where systematic errors were found, but should still be treated as indicative. Key things to watch:

- **Ranges vs single values** — Some universities publish grade ranges (e.g. AAA-AAB or IB 36-34). We show a single value, typically the higher end of the range.
- **LSE** — Some courses may show contextual (lower) A-Level offers rather than standard offers (e.g. AAA instead of A*AA). LSE is also raising requirements for 2027 entry. Our data reflects 2026 entry.
- **Edinburgh** — Courses show the upper end of a published range. Actual requirements may be lower. Verify directly on the university website.
- **Bristol IB & Durham IB** — Systematic errors were found and corrected (Bristol: contextual offers shown instead of standard; Durham: off by 1 across the board). Now fixed.
- **UCL & Oxford** — IB scores could not be independently verified (sites block automated access). Treat as indicative.
- **Required Subjects** — auto-extracted from each course's requirement text, so they're indicative. Subject data is available for ~63% of courses; the rest (including all Cambridge courses) show "Not listed" and are hidden when you filter by a required subject.

Always confirm entry requirements on the university's own course page before making decisions.
    """)

    # Data quality / known gaps in expander
    with st.expander("Data Quality & Known Gaps (priority list)", expanded=False):
        # Compute dynamic stats
        n_courses = len(df)
        oxford_count = len(df[df["university"] == "University of Oxford"])
        oxford_stem = len(df[(df["university"] == "University of Oxford") & (df["domain"].isin(["Engineering", "Physical Sciences", "Mathematics & Statistics", "Computing & Technology", "Life Sciences"]))])
        cambridge_count = len(df[df["university"] == "University of Cambridge"])
        oxford_offer = df[(df["university"] == "University of Oxford") & (df["total_offer_pct"].notna())].shape[0]
        cambridge_offer = df[(df["university"] == "University of Cambridge") & (df["total_offer_pct"].notna())].shape[0]
        fallback_urls = df["course_url"].str.contains("google.com/search", na=False).sum()
        missing_urls = df["course_url"].isna().sum()
        missing_subj = df["qs_subject_rank"].isna().sum()

        st.markdown(f"""
| # | Priority | Gap | Detail | To fix |
|---|----------|-----|--------|--------|
| 1 | **MEDIUM** | Oxford course count | {oxford_count} Oxford courses ({oxford_stem} STEM) — many language variants from UCAS, core STEM added manually | Original UCAS extract heavy on language combos, light on sciences |
| 2 | **MEDIUM** | Cambridge course count | {cambridge_count} courses (core subjects covered, but variants like "with Year Abroad" not in data) | Get fuller Cambridge UCAS extract for variant courses |
| 3 | **MEDIUM** | Oxford Oxbridge stats | {oxford_offer}/{oxford_count} Oxford courses have offer data (vs {cambridge_offer}/{cambridge_count} Cambridge) | Many Oxford language variants have no separate admissions stats |
| 4 | **LOW** | Course URL fallbacks | {fallback_urls} courses use Google search links (no direct URL available), {missing_urls} missing | Scrape specific course pages for remaining universities |
| 5 | **LOW** | Unmatched QS subjects | {missing_subj}/{n_courses} ({100*missing_subj//n_courses}%) courses have no subject-level rank | Expand subject mapper keyword rules |
        """)

    st.divider()

    # Universities overview
    st.subheader("Universities Covered")
    agg_dict = {
        "Courses": ("course", "size"),
        "Domains": ("domain", "nunique"),
        "QS_Rank": ("qs_global_rank", "first"),
        "THE_Rank": ("the_rank", "first"),
    }
    if "total_students" in df.columns:
        agg_dict["Students"] = ("total_students", "first")
        agg_dict["Intl %"] = ("international_pct", "first")
        agg_dict["Asia %"] = ("asia_pct", "first")
    uni_summary = df.groupby("university").agg(**agg_dict).sort_values("QS_Rank")
    uni_summary["QS_Rank"] = uni_summary["QS_Rank"].apply(format_rank)
    uni_summary["THE_Rank"] = uni_summary["THE_Rank"].apply(format_rank)
    if "Students" in uni_summary.columns:
        uni_summary["Students"] = uni_summary["Students"].apply(
            lambda x: f"{int(x):,}" if pd.notna(x) else "-"
        )
        uni_summary["Intl %"] = uni_summary["Intl %"].apply(
            lambda x: f"{x:.0f}%" if pd.notna(x) else "-"
        )
        uni_summary["Asia %"] = uni_summary["Asia %"].apply(
            lambda x: f"{x:.0f}%" if pd.notna(x) else "-"
        )
    uni_summary = uni_summary.rename(columns={"QS_Rank": "QS Global", "THE_Rank": "THE Global"})
    st.dataframe(uni_summary, width="stretch")


# --- Main app ---

def main():
    df = load_data()
    options = get_filter_options(df)

    # Header
    st.markdown('<p class="main-header">UK Course Finder</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Explore undergraduate courses across top UK universities with rankings, entry requirements, and admissions data</p>', unsafe_allow_html=True)
    st.caption("Looking for US colleges instead? Check out the [US College Finder](https://us-colleges-longlist.streamlit.app/) (password: rankings).")

    # Sidebar filters
    with st.sidebar:
        st.header("Filters")

        st.caption(
            "**Includes** = match ANY term (OR). **Excludes** = drop if ANY term matches. "
            "Separate terms with spaces, or commas for multi-word phrases. "
            "Use **`+`** to require several at once, e.g. `econ+psych` matches courses with **both** "
            "(try `econ+psych, mgmt+psych` for either pairing)."
        )

        # University filter
        selected_unis = st.multiselect(
            "Universities",
            options=options["universities"],
            default=[],
            placeholder="All universities"
        )

        st.divider()

        # Course name include / exclude
        st.markdown("**University Course**")
        course_inc = st.text_input(
            "Includes",
            key="course_inc",
            placeholder="e.g. busi mana  (econ+psych = both)",
            help="Keep courses matching ANY term (OR). Use + for AND, e.g. econ+psych = courses with both."
        )
        course_exc = st.text_input(
            "Excludes",
            key="course_exc",
            placeholder="e.g. geo account fin",
            help="Drop courses whose name contains ANY of these terms"
        )

        st.divider()

        # Domain (Subject Area) include / exclude
        st.markdown("**Domain (Subject Area)**")
        domain_inc = st.multiselect(
            "Includes",
            options=options["domains"],
            default=[],
            key="domain_inc",
            placeholder="All subject areas"
        )
        domain_exc = st.multiselect(
            "Excludes",
            options=options["domains"],
            default=[],
            key="domain_exc",
            placeholder="Exclude none"
        )
        st.caption("Matches every domain a course spans — excluding Languages also drops e.g. *Business with Chinese*.")

        st.divider()

        # Subject requirements include / exclude (structured required subjects)
        st.markdown("**Required Subjects**")
        subj_options = options.get("required_subjects", [])
        subj_inc = st.multiselect(
            "Requires (any of)",
            options=subj_options,
            default=[],
            key="subj_inc",
            placeholder="Any subjects",
            help="Keep courses that require ANY of these subjects at A-Level/IB"
        )
        subj_exc = st.multiselect(
            "Must not require",
            options=subj_options,
            default=[],
            key="subj_exc",
            placeholder="Exclude none",
            help="Drop courses that require ANY of these subjects"
        )
        # Coverage indicator — be transparent about missing data
        n_known = int((df["subject_req_status"] == "specified").sum()) if "subject_req_status" in df.columns else 0
        n_unknown = int((df["subject_req_status"] == "unknown").sum()) if "subject_req_status" in df.columns else 0
        st.caption(
            f"⚠️ Subject data available for {n_known:,} of {len(df):,} courses. "
            f"{n_unknown:,} have none listed (incl. all Cambridge) and are hidden when you filter by subject."
        )
        keep_unknown_subj = False
        if subj_inc:
            keep_unknown_subj = st.checkbox(
                "Also keep courses with no subject data",
                value=False,
                key="keep_unknown_subj",
                help="Include courses whose required subjects are unknown, instead of dropping them"
            )

        st.divider()

        # A-Level / IB toggle (drives the grade requirement column + grade filter)
        req_mode = st.radio(
            "Requirements view",
            ["A-Level", "IB"],
            horizontal=True
        )

        # Grade filter
        if req_mode == "A-Level":
            grade_labels = [f"{label}" for label, _ in ALEVEL_GRADE_OPTIONS]
            grade_values = [v for _, v in ALEVEL_GRADE_OPTIONS]

            grade_filter_enabled = st.checkbox("Filter by my A-Level grades", value=False)
            if grade_filter_enabled:
                selected_grade_idx = st.select_slider(
                    "I have at least...",
                    options=list(range(len(grade_labels))),
                    value=4,  # Default to AAB
                    format_func=lambda i: grade_labels[i]
                )
                my_grade_score = grade_values[selected_grade_idx]
            else:
                my_grade_score = None
        else:
            grade_filter_enabled = st.checkbox("Filter by my IB points", value=False)
            if grade_filter_enabled:
                my_ib_points = st.slider(
                    "I have at least... points",
                    min_value=24, max_value=45, value=36
                )
            else:
                my_ib_points = None

        st.divider()

        # Weighted ranking slider
        global_weight = st.slider(
            "Ranking emphasis",
            min_value=0.0, max_value=1.0, value=0.5, step=0.1,
            help="0 = Subject rank only, 1 = Global rank only"
        )
        st.caption("Global rank vs Subject rank emphasis")

        st.divider()

        # Study mode filter
        selected_modes = st.multiselect(
            "Study Mode",
            options=options["study_modes"],
            default=[],
            placeholder="All modes"
        )

        # Duration filter
        selected_durations = st.multiselect(
            "Duration",
            options=options["durations"],
            default=[],
            placeholder="All durations"
        )

        st.divider()

        # Demographics filters
        min_asia, max_asia = st.slider(
            "Min Asia %",
            min_value=0, max_value=50, value=(0, 50),
            help="Filter universities by percentage of Asian students"
        )
        min_intl, max_intl = st.slider(
            "Min International %",
            min_value=0, max_value=70, value=(0, 70),
            help="Filter universities by percentage of international students"
        )
        demo_filter_active = (min_asia > 0 or max_asia < 50
                              or min_intl > 0 or max_intl < 70)

        # SMC filter
        smc_only = st.checkbox(
            "SMC approved only",
            help="Show only courses at universities approved by the Singapore Medical Council"
        )

        st.divider()

        # Group by
        group_by = st.selectbox(
            "Group by",
            options=["None", "University", "Subject Area"]
        )

        # Sort options
        sort_by = st.selectbox(
            "Sort by",
            options=[
                "Weighted score (best first)",
                "University ranking (QS)",
                "University ranking (THE)",
                "Subject ranking (QS)",
                "Grade requirement (highest first)",
                "Grade requirement (lowest first)",
                "Course name (A-Z)",
                "Offer rate (lowest first)",
                "Asia % (highest first)",
                "International % (highest first)",
            ]
        )

        st.divider()

        # Export limit
        export_limit = st.number_input(
            "Max export rows",
            min_value=1, max_value=500, value=50,
            help="Limit the number of rows in CSV export"
        )

    # Detect if any filter is active (triggers results vs landing page)
    any_filter_active = bool(
        selected_unis
        or course_inc.strip() or course_exc.strip()
        or domain_inc or domain_exc
        or subj_inc or subj_exc
        or grade_filter_enabled
        or selected_modes or selected_durations
        or demo_filter_active or smc_only
    )

    # Initialize shortlist in session state
    if "shortlist" not in st.session_state:
        st.session_state["shortlist"] = set()

    shortlist_count = len(st.session_state["shortlist"])
    shortlist_label = f"Shortlist ({shortlist_count})" if shortlist_count > 0 else "Shortlist"

    # Tabs
    tab_courses, tab_shortlist = st.tabs(["Course Explorer", shortlist_label])

    # ==================== TAB 1: Course Explorer ====================
    with tab_courses:
        if not any_filter_active:
            show_landing_page(df)
        else:
            # Apply filters
            mask = pd.Series(True, index=df.index)

            if selected_unis:
                mask &= df["university"].isin(selected_unis)

            # Course name include (OR) / exclude (AND)
            if course_inc.strip() or course_exc.strip():
                mask &= apply_include_exclude(df["course"], course_inc, course_exc)

            # Domain include (OR) / exclude (AND) — matched against a course's
            # FULL domain set, so excluding e.g. Languages also drops
            # "International Business with Chinese". Falls back to the single
            # primary domain if the multi-domain column is unavailable.
            if domain_inc or domain_exc:
                if "domain_list" in df.columns:
                    if domain_inc:
                        inc = set(domain_inc)
                        mask &= df["domain_list"].apply(lambda ds: bool(set(ds) & inc))
                    if domain_exc:
                        exc = set(domain_exc)
                        mask &= df["domain_list"].apply(lambda ds: not (set(ds) & exc))
                else:
                    if domain_inc:
                        mask &= df["domain"].isin(domain_inc)
                    if domain_exc:
                        mask &= ~df["domain"].isin(domain_exc)

            # Required-subject include (OR) / exclude (AND) on structured data
            if (subj_inc or subj_exc) and "required_subjects" in df.columns:
                req_sets = df["required_subjects"].fillna("").apply(
                    lambda s: set(p for p in s.split("; ") if p)
                )
                if subj_inc:
                    inc_set = set(subj_inc)
                    inc_mask = req_sets.apply(lambda r: bool(r & inc_set))
                    if keep_unknown_subj:
                        inc_mask |= df["subject_req_status"].ne("specified")
                    mask &= inc_mask
                if subj_exc:
                    exc_set = set(subj_exc)
                    mask &= req_sets.apply(lambda r: not (r & exc_set))

            if selected_modes:
                mask &= df["study_mode"].isin(selected_modes)
            if selected_durations:
                mask &= df["duration"].isin(selected_durations)

            # Demographics filters
            if demo_filter_active:
                if "asia_pct" in df.columns:
                    mask &= (df["asia_pct"] >= min_asia) & (df["asia_pct"] <= max_asia)
                if "international_pct" in df.columns:
                    mask &= (df["international_pct"] >= min_intl) & (df["international_pct"] <= max_intl)

            # SMC filter
            if smc_only and "smc_approved" in df.columns:
                mask &= df["smc_approved"] == "Yes"

            # Grade filters
            if req_mode == "A-Level" and grade_filter_enabled and my_grade_score is not None:
                mask &= (df["alevel_score"].isna()) | (df["alevel_score"] <= my_grade_score)

            if req_mode == "IB" and grade_filter_enabled and my_ib_points is not None:
                mask &= (df["ib_score"].isna()) | (df["ib_score"] <= my_ib_points)

            filtered = df.loc[mask].copy()

            # Compute weighted score
            filtered["weighted_score"] = compute_weighted_score(filtered, global_weight)

            # Sort
            sort_map = {
                "Weighted score (best first)": ("weighted_score", False),
                "University ranking (QS)": ("qs_global_rank", True),
                "University ranking (THE)": ("the_rank", True),
                "Subject ranking (QS)": ("qs_subject_rank", True),
                "Grade requirement (highest first)": ("alevel_score", False),
                "Grade requirement (lowest first)": ("alevel_score", True),
                "Course name (A-Z)": ("course", True),
                "Offer rate (lowest first)": ("total_offer_pct", True),
                "Asia % (highest first)": ("asia_pct", False),
                "International % (highest first)": ("international_pct", False),
            }
            sort_col, sort_asc = sort_map.get(sort_by, ("weighted_score", False))
            if sort_col in filtered.columns:
                filtered = filtered.sort_values(sort_col, ascending=sort_asc, na_position="last")

            filtered = filtered.reset_index(drop=True)

            # Summary stats
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Courses", f"{len(filtered):,}")
            with col2:
                st.metric("Universities", filtered["university"].nunique())
            with col3:
                st.metric("Subject Areas", filtered["domain"].nunique())
            with col4:
                with_ranks = filtered["qs_subject_rank"].notna().sum()
                st.metric("With Subject Rankings", f"{with_ranks:,}")

            st.divider()

            if filtered.empty:
                st.warning("No courses match your filters. Try broadening your search.")
            else:
                has_oxbridge = filtered["total_offer_pct"].notna().any()

                if group_by == "None":
                    # Flat table
                    display_df, available_show = build_display_df(filtered, req_mode, has_oxbridge)
                    render_dataframe(display_df, available_show,
                                     enable_shortlist=True, source_df=filtered)
                else:
                    # Grouped tables inside expanders
                    group_col = "university" if group_by == "University" else "domain"
                    groups = filtered.groupby(group_col, sort=True)

                    for group_name, group_df in groups:
                        count = len(group_df)
                        # Add demographics to university group headers
                        label = f"{group_name} ({count} courses)"
                        if group_by == "University" and "asia_pct" in group_df.columns:
                            asia = group_df["asia_pct"].iloc[0]
                            intl = group_df["international_pct"].iloc[0]
                            if pd.notna(asia) and pd.notna(intl):
                                label += f" — Asia {asia:.0f}%, Intl {intl:.0f}%"
                        with st.expander(label, expanded=True):
                            gdf = group_df.reset_index(drop=True)
                            display_df, available_show = build_display_df(gdf, req_mode, has_oxbridge)
                            render_dataframe(display_df, available_show,
                                             height=min(400, 35 * count + 60),
                                             enable_shortlist=True, source_df=gdf)

                # Export
                st.divider()
                n_export = min(len(filtered), export_limit)
                if len(filtered) > export_limit:
                    st.info(f"Exporting first {export_limit} of {len(filtered):,} courses. Increase the limit in the sidebar or apply more filters.")

                export_cols = {
                    "university": "University",
                    "course": "Course",
                    "course_url": "URL",
                    "domains_all": "Subject Area",
                    "alevel_grades": "A-Level Req",
                    "ib_points_raw": "IB Req",
                    "required_subjects": "Required Subjects",
                    "subject_req_status": "Subject Req Status",
                    "qs_global_rank": "QS Global Rank",
                    "the_rank": "THE Rank",
                    "qs_subject_rank": "QS Subject Rank",
                    "weighted_score": "Weighted Score",
                    "duration": "Duration",
                    "study_mode": "Study Mode",
                    "total_offer_pct": "Offer %",
                    "intl_offer_pct": "Intl Offer %",
                    "asia_pct": "Asia %",
                    "international_pct": "Intl %",
                    "total_students": "Total Students",
                    "ucas_code": "UCAS Code",
                    "qualification": "Qualification",
                    "smc_approved": "SMC Approved",
                }
                available_export = {k: v for k, v in export_cols.items() if k in filtered.columns}
                export_df = filtered.head(n_export)[list(available_export.keys())].rename(columns=available_export)
                csv = export_df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label=f"Export {n_export} courses as CSV",
                    data=csv,
                    file_name="uk_courses_filtered.csv",
                    mime="text/csv"
                )

    # ==================== TAB 2: Shortlist ====================
    with tab_shortlist:
        render_shortlist(df, req_mode=req_mode)


def render_shortlist(df, req_mode="A-Level"):
    """Render the Shortlist tab showing saved courses."""
    shortlist = st.session_state.get("shortlist", set())

    st.subheader("Your Shortlist")
    st.caption("Star courses in the Course Explorer to add them here. Shortlist persists during your session.")

    if not shortlist:
        st.info("No courses shortlisted yet. Use the ⭐ column in Course Explorer to add courses.")
        return

    # Filter master df to shortlisted courses (avoid mutating original df)
    keys = df["university"] + " | " + df["course"] + " | " + df["ucas_code"].fillna("")
    shortlisted = df[keys.isin(shortlist)].copy()

    if shortlisted.empty:
        st.warning("Shortlisted courses not found in current data.")
        return

    # Stats
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Shortlisted", len(shortlisted))
    with col2:
        st.metric("Universities", shortlisted["university"].nunique())
    with col3:
        st.metric("Subject Areas", shortlisted["domain"].nunique())

    st.divider()

    # Display table
    has_oxbridge = shortlisted["total_offer_pct"].notna().any()
    display_df, available_show = build_display_df(shortlisted, req_mode, has_oxbridge)
    st.dataframe(
        display_df[available_show],
        hide_index=True,
        width="stretch",
        height=min(600, 35 * len(shortlisted) + 60),
        column_config={k: v for k, v in COLUMN_CONFIG.items() if k in available_show}
    )

    # Export shortlist
    st.divider()
    export_cols = {
        "university": "University",
        "course": "Course",
        "course_url": "URL",
        "domains_all": "Subject Area",
        "alevel_grades": "A-Level Req",
        "ib_points_raw": "IB Req",
        "required_subjects": "Required Subjects",
        "subject_req_status": "Subject Req Status",
        "qs_global_rank": "QS Global Rank",
        "the_rank": "THE Rank",
        "qs_subject_rank": "QS Subject Rank",
        "duration": "Duration",
        "asia_pct": "Asia %",
        "international_pct": "Intl %",
        "total_students": "Total Students",
        "ucas_code": "UCAS Code",
        "qualification": "Qualification",
        "total_offer_pct": "Offer %",
        "intl_offer_pct": "Intl Offer %",
        "smc_approved": "SMC Approved",
    }
    available_export = {k: v for k, v in export_cols.items() if k in shortlisted.columns}
    export_df = shortlisted[list(available_export.keys())].rename(columns=available_export)

    col_dl, col_clear = st.columns([3, 1])
    with col_dl:
        csv = export_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label=f"Export shortlist ({len(shortlisted)} courses) as CSV",
            data=csv,
            file_name="uk_courses_shortlist.csv",
            mime="text/csv"
        )
    with col_clear:
        if st.button("Clear shortlist", type="secondary"):
            st.session_state["shortlist"] = set()
            st.rerun()


if __name__ == "__main__":
    main()
