"""
UK Course Finder - Streamlit Web Application

A two-tab course explorer combining course data, rankings, medical school
requirements, and Oxbridge admissions statistics.
"""

import streamlit as st
import pandas as pd
import numpy as np
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))
from data_loader import load_master_dataframe, get_filter_options, load_med_schools
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

def parse_search_keywords(query: str) -> tuple[list[str], list[str]]:
    """Parse a search query into include and exclude keyword lists.

    Supports both comma-separated and space-separated tokens.
    If commas are present, split on commas. Otherwise split on spaces.
    Minus prefix for excludes: "-philo" removes matches.

    Examples:
        "comp, phys, -philo"  -> include=["comp","phys"], exclude=["philo"]
        "comp phys -philo"    -> include=["comp","phys"], exclude=["philo"]
        "computer science"    -> include=["computer science"] (comma mode preserves phrases)
    """
    if not query or not query.strip():
        return [], []

    includes = []
    excludes = []

    # If commas present, split on commas (preserves multi-word phrases)
    # Otherwise split on spaces (each word is a keyword)
    if "," in query:
        tokens = query.split(",")
    else:
        tokens = query.split()

    for token in tokens:
        token = token.strip()
        if not token:
            continue
        if token.startswith("-") and len(token) > 1:
            excludes.append(token[1:].strip().lower())
        else:
            includes.append(token.lower())

    return includes, excludes


def apply_keyword_search(series: pd.Series, query: str) -> pd.Series:
    """Apply multi-keyword AND search with excludes to a text Series.

    Returns a boolean mask.
    """
    includes, excludes = parse_search_keywords(query)
    if not includes and not excludes:
        return pd.Series(True, index=series.index)

    lower = series.str.lower().fillna("")
    mask = pd.Series(True, index=series.index)

    for kw in includes:
        mask &= lower.str.contains(kw, na=False)
    for kw in excludes:
        mask &= ~lower.str.contains(kw, na=False)

    return mask


# --- Data loading ---

@st.cache_data(ttl=3600)
def load_data():
    """Load the master DataFrame (cached)."""
    return load_master_dataframe()


@st.cache_data(ttl=3600)
def load_med_data():
    """Load the medical schools DataFrame (cached)."""
    return load_med_schools()


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
    wanted_cols = ["university", "course", "course_url", "domain",
                   "alevel_grades", "ib_points_raw",
                   "qs_global_rank", "the_rank", "qs_subject_rank",
                   "weighted_score",
                   "duration", "study_mode",
                   "total_offer_pct", "intl_offer_pct",
                   "asia_pct", "international_pct"]
    available_wanted = [c for c in wanted_cols if c in filtered.columns]
    display_df = filtered[available_wanted].copy()

    display_df = display_df.rename(columns={
        "university": "University",
        "course": "Course",
        "course_url": "Link",
        "domain": "Subject Area",
        "alevel_grades": "A-Level Req",
        "ib_points_raw": "IB Req",
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
    })

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
    show_cols.extend(["QS Global", "THE Global", "QS Subject", "Score",
                       "Asia %", "Intl %"])
    if has_oxbridge:
        show_cols.extend(["Offer %", "Intl Offer %"])

    available_show = [c for c in show_cols if c in display_df.columns]
    return display_df, available_show


COLUMN_CONFIG = {
    "University": st.column_config.TextColumn(width="medium"),
    "Course": st.column_config.TextColumn(width="large"),
    "Link": st.column_config.LinkColumn(width="small", display_text="View"),
    "Subject Area": st.column_config.TextColumn(width="medium"),
    "A-Level Req": st.column_config.TextColumn(width="small"),
    "IB Req": st.column_config.TextColumn(width="small"),
    "QS Global": st.column_config.TextColumn(width="small"),
    "THE Global": st.column_config.TextColumn(width="small"),
    "QS Subject": st.column_config.TextColumn(width="small"),
    "Score": st.column_config.TextColumn(width="small"),
    "Offer %": st.column_config.TextColumn(width="small"),
    "Intl Offer %": st.column_config.TextColumn(width="small"),
    "Asia %": st.column_config.TextColumn(width="small"),
    "Intl %": st.column_config.TextColumn(width="small"),
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
        st.caption("Type keywords to find courses. Use commas for AND logic, minus to exclude (e.g. `comp, sci, -philo`)")
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
        n_med = load_med_data().shape[0]
        st.markdown(f"""
        **Course Data (2025 UCAS cycle):**
        - {n_courses:,} undergraduate courses across {n_unis} universities
        - A-Level and IB entry requirements
        - Course URLs and UCAS codes

        **Rankings:** QS Global + Subject (60 subjects) + THE Global
        - {n_with_subj:,}/{n_courses:,} courses have subject-level rank data

        **Medical Schools tab:** {n_med} schools with SMC requirements,
        admission tests, interview types, and international applicant stats

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

    # Data quality / known gaps in expander
    with st.expander("Data Quality & Known Gaps (priority list)", expanded=False):
        # Compute dynamic stats
        n_courses = len(df)
        oxford_count = len(df[df["university"] == "University of Oxford"])
        oxford_stem = len(df[(df["university"] == "University of Oxford") & (df["domain"].isin(["Engineering", "Physical Sciences", "Mathematics & Statistics", "Computing & Technology", "Life Sciences"]))])
        cambridge_count = len(df[df["university"] == "University of Cambridge"])
        oxford_offer = df[(df["university"] == "University of Oxford") & (df["total_offer_pct"].notna())].shape[0]
        cambridge_offer = df[(df["university"] == "University of Cambridge") & (df["total_offer_pct"].notna())].shape[0]
        missing_urls = df["course_url"].isna().sum()
        missing_subj = df["qs_subject_rank"].isna().sum()

        st.markdown(f"""
| # | Priority | Gap | Detail | To fix |
|---|----------|-----|--------|--------|
| 1 | **MEDIUM** | Oxford course count | {oxford_count} Oxford courses ({oxford_stem} STEM) — many language variants from UCAS, core STEM added manually | Original UCAS extract heavy on language combos, light on sciences |
| 2 | **MEDIUM** | Cambridge course count | {cambridge_count} courses (core subjects covered, but variants like "with Year Abroad" not in data) | Get fuller Cambridge UCAS extract for variant courses |
| 3 | **MEDIUM** | Oxford Oxbridge stats | {oxford_offer}/{oxford_count} Oxford courses have offer data (vs {cambridge_offer}/{cambridge_count} Cambridge) | Many Oxford language variants have no separate admissions stats |
| 4 | **MEDIUM** | Missing course URLs | {missing_urls}/{n_courses} ({100*missing_urls//n_courses}%) have no link | Check if source Excel contains the URLs |
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

    # Sidebar filters
    with st.sidebar:
        st.header("Filters")

        # University filter
        selected_unis = st.multiselect(
            "Universities",
            options=options["universities"],
            default=[],
            placeholder="All universities"
        )

        # Domain filter
        selected_domains = st.multiselect(
            "Subject Area",
            options=options["domains"],
            default=[],
            placeholder="All subject areas"
        )

        # Course name search (multi-keyword)
        course_search = st.text_input(
            "Course name contains",
            placeholder="e.g. comp sci -philo"
        )
        st.caption("Space or comma-separated AND logic. Prefix with - to exclude.")

        st.divider()

        # A-Level / IB toggle
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
        selected_unis or selected_domains or course_search.strip()
        or grade_filter_enabled
        or selected_modes or selected_durations
        or demo_filter_active
    )

    # Initialize shortlist in session state
    if "shortlist" not in st.session_state:
        st.session_state["shortlist"] = set()

    shortlist_count = len(st.session_state["shortlist"])
    shortlist_label = f"Shortlist ({shortlist_count})" if shortlist_count > 0 else "Shortlist"

    # Tabs
    tab_courses, tab_med, tab_shortlist = st.tabs(["Course Explorer", "Medical Schools", shortlist_label])

    # ==================== TAB 1: Course Explorer ====================
    with tab_courses:
        if not any_filter_active:
            show_landing_page(df)
        else:
            # Apply filters
            mask = pd.Series(True, index=df.index)

            if selected_unis:
                mask &= df["university"].isin(selected_unis)
            if selected_domains:
                mask &= df["domain"].isin(selected_domains)
            if course_search:
                mask &= apply_keyword_search(df["course"], course_search)
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
                    "domain": "Subject Area",
                    "alevel_grades": "A-Level Req",
                    "ib_points_raw": "IB Req",
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

    # ==================== TAB 2: Medical Schools ====================
    with tab_med:
        render_medical_schools()

    # ==================== TAB 3: Shortlist ====================
    with tab_shortlist:
        render_shortlist(df, req_mode=req_mode)


def render_medical_schools():
    """Render the Medical Schools tab with independent data and filters."""
    med = load_med_data()

    st.subheader("UK Medical Schools")
    st.caption("Requirements and admissions data from the Medical School Council and international applicant statistics.")

    # Filters for this tab (independent of sidebar)
    f1, f2, f3 = st.columns(3)
    with f1:
        med_uni_filter = st.multiselect(
            "University",
            options=sorted(med["university"].dropna().unique()),
            default=[],
            placeholder="All medical schools",
            key="med_uni_filter"
        )
    with f2:
        test_options = sorted(med["test_category"].dropna().unique())
        med_test_filter = st.multiselect(
            "Admission Test",
            options=test_options,
            default=[],
            placeholder="All test types",
            key="med_test_filter"
        )
    with f3:
        smc_only = st.checkbox(
            "SMC Approved only",
            value=False,
            help="Filter to Singapore Medical Council approved schools (22 schools)",
            key="smc_filter"
        )

    # Apply med filters
    med_mask = pd.Series(True, index=med.index)
    if med_uni_filter:
        med_mask &= med["university"].isin(med_uni_filter)
    if med_test_filter:
        med_mask &= med["test_category"].isin(med_test_filter)
    if smc_only:
        med_mask &= med["med_singapore_approved"].str.contains("Yes", case=False, na=False)

    med_filtered = med.loc[med_mask].copy()

    st.metric("Medical Schools", len(med_filtered))
    st.divider()

    if med_filtered.empty:
        st.warning("No medical schools match your filters.")
        return

    # Select and rename columns for display
    display_cols = {
        "university": "University",
        "med_course": "Course",
        "med_singapore_approved": "SMC Approved",
        "med_alevel_req": "A-Level Req",
        "med_ib_req": "IB Req",
        "med_gcse_req": "GCSE Req",
        "test_category": "Admission Test",
        "med_interview_type": "Interview",
        "med_teaching_style": "Teaching Style",
        "med_work_experience": "Work Experience",
        "med_intl_applicants": "Intl Applicants",
        "med_intl_offers": "Intl Offers",
        "med_intl_offer_pct": "Intl Offer %",
    }

    available = {k: v for k, v in display_cols.items() if k in med_filtered.columns}
    med_display = med_filtered[list(available.keys())].rename(columns=available)

    # Format percentage
    if "Intl Offer %" in med_display.columns:
        med_display["Intl Offer %"] = med_display["Intl Offer %"].apply(
            lambda x: f"{x:.1f}%" if pd.notna(x) else "-"
        )

    col_config = {
        "University": st.column_config.TextColumn(width="medium"),
        "Course": st.column_config.TextColumn(width="medium"),
        "SMC Approved": st.column_config.TextColumn(width="small"),
        "A-Level Req": st.column_config.TextColumn(width="medium"),
        "IB Req": st.column_config.TextColumn(width="medium"),
        "GCSE Req": st.column_config.TextColumn(width="medium"),
        "Admission Test": st.column_config.TextColumn(width="small"),
        "Interview": st.column_config.TextColumn(width="medium"),
        "Teaching Style": st.column_config.TextColumn(width="medium"),
        "Work Experience": st.column_config.TextColumn(width="medium"),
        "Intl Applicants": st.column_config.NumberColumn(width="small"),
        "Intl Offers": st.column_config.NumberColumn(width="small"),
        "Intl Offer %": st.column_config.TextColumn(width="small"),
    }

    st.dataframe(
        med_display,
        hide_index=True,
        width="stretch",
        height=600,
        column_config={k: v for k, v in col_config.items() if k in med_display.columns}
    )


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
        "domain": "Subject Area",
        "alevel_grades": "A-Level Req",
        "ib_points_raw": "IB Req",
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
