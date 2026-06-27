"""
Extract structured subject requirements from the free-text `alevel_details`
and `ib_details` fields.

The raw detail text is scraped and highly inconsistent across universities, e.g.:
    "Including Mathematics at grade A or above. Excluding General Studies (if taken)"
    "Must include: A in Chemistry A in Biology, Physics or Mathematics ..."
    "with 7 6 6 at HL, including HL Mathematics"
    "Please check the website for subject requirements"

This module turns that into two clean, reliably-searchable fields:
    - required_subjects  : "; "-joined canonical subject names (e.g. "Mathematics; Chemistry")
    - subject_req_status : one of "specified" / "open" / "unknown"

A subject is classified as REQUIRED unless it appears in an exclusion context
("excluding X", "X not accepted") or a soft-recommendation context
("recommended", "useful", "preferred"). This is what fixes the precision problem
with plain substring search, where "Excluding General Studies" or
"Physics is useful" would otherwise look like requirements.

Coverage ceiling: cleaning improves precision, not completeness. Courses whose
source text is boilerplate ("check the website") or empty get status "unknown"
and cannot be matched by subject filters. That gap is surfaced in the UI, not
hidden.
"""

import re

# Canonical subject -> list of synonyms (matched case-insensitively).
# Order within the flattened list is handled by length (longest first) so that
# e.g. "Further Mathematics" is consumed before "Mathematics", and
# "Computer Science" before a bare science match.
CANONICAL_SUBJECTS = {
    "Further Mathematics": [r"further mathematics", r"further maths"],
    "Mathematics": [r"mathematics", r"\bmaths\b"],
    "Physics": [r"physics"],
    "Chemistry": [r"chemistry"],
    "Biology": [r"biology"],
    "English": [
        r"english language and literature", r"english literature",
        r"english lang/lit", r"english language", r"english lit", r"english",
    ],
    "History": [r"history"],
    "Geography": [r"geography"],
    "Economics": [r"economics"],
    "Psychology": [r"psychology"],
    "Computer Science": [r"computer science", r"computing"],
    "Modern Language": [
        r"modern language\(s\)", r"modern languages", r"modern language",
        r"modern foreign language", r"a foreign language",
    ],
    "Latin": [r"latin"],
    "Greek": [r"greek"],
    "Music": [r"music"],
    "Politics": [r"government and politics", r"politics"],
    "Philosophy": [r"philosophy"],
    "Sociology": [r"sociology"],
    "Business Studies": [r"business studies", r"business"],
    "Art": [r"history of art", r"\bart\b"],
    # Deliberately narrow: "a science"/"second science"/"two sciences" are real
    # requirements; bare "science subjects" matches boilerplate like "pass the
    # practical endorsement in all science subjects" and is excluded on purpose.
    "Science": [r"a science", r"second science", r"two sciences", r"a third science"],
    "Essay-based Subject": [r"essay-based subject", r"essay based subject"],
    "General Studies": [r"general studies"],
    "Critical Thinking": [r"critical thinking"],
}

# Subjects that are only meaningful as exclusions (universities reject them).
# Never surfaced as "required" even if the context detector slips.
_EXCLUSION_ONLY = {"General Studies", "Critical Thinking"}

# Flatten to (synonym_pattern, canonical) sorted by literal length, longest first.
_PATTERNS = sorted(
    ((syn, canon) for canon, syns in CANONICAL_SUBJECTS.items() for syn in syns),
    key=lambda x: len(x[0]), reverse=True,
)

_EXCLUDE_CTX = re.compile(
    r"(exclud|not be accepted|not accepted|are not accepted|is not accepted|do not accept|will not accept)",
    re.I,
)
_RECOMMEND_CTX = re.compile(
    r"(recommend|useful|preferred|desirable|helpful|advantageous|beneficial)",
    re.I,
)
_OPEN_RE = re.compile(
    r"(no specific subject|no specified subject|no particular subject|"
    r"no subject requirement|all subjects (are )?considered|any subjects? (are )?accept)",
    re.I,
)
_UNKNOWN_RE = re.compile(
    r"(check the website|please check|see (our |the )?website|"
    r"subject requirements for this course|visit the course)",
    re.I,
)

# Section header, e.g. "Preferred 3rd subjects ...", "Recommended subjects ..."
_REC_HEADER = re.compile(r"(preferred|recommended|useful|desirable)(\s+\w+){0,2}\s+subjects?", re.I)
# Trailing qualifier, e.g. "(Biology or Physics is preferred)", "Physics recommended."
_REC_TRAIL = re.compile(
    r"((is|are)\s+(preferred|recommended|useful|desirable)|"
    r"(preferred|recommended|useful|desirable)\s*[\).])", re.I,
)
_ENGLISH_FALSE = re.compile(r"english\s+(exam board|language requirement)", re.I)


def _recommended_spans(work: str) -> list[tuple[int, int]]:
    """Char ranges that describe *recommended* (not required) subjects.

    Handles both section headers ("Preferred 3rd subjects X Y Z", which qualify
    everything after them up to the next sentence) and trailing qualifiers
    ("(X or Y is preferred)", which qualify the list just before them).
    """
    spans = []
    for m in _REC_HEADER.finditer(work):
        end = work.find(".", m.end())
        spans.append((m.start(), end if end != -1 else min(len(work), m.end() + 120)))
    for m in _REC_TRAIL.finditer(work):
        lp = work.rfind("(", 0, m.start())
        start = lp if (lp != -1 and m.start() - lp < 90) else max(0, m.start() - 70)
        spans.append((start, m.end()))
    return spans


def _classify_one(text: str) -> dict:
    """Find subjects in one detail string, tagging each as required/excluded/recommended.

    Returns {canonical: context} where context is 'required'|'excluded'|'recommended'.
    """
    if not text or not str(text).strip():
        return {}
    orig = str(text).lower()          # immutable, used for context lookups
    work = orig                        # progressively blanked to avoid re-matching
    rec_spans = _recommended_spans(orig)
    found: dict[str, str] = {}

    for syn, canon in _PATTERNS:
        for m in re.finditer(syn, work):
            start, end = m.start(), m.end()
            mid = (start + end) // 2
            # Context window: current clause (nearest '.'/';' before) plus a short
            # forward reach to catch "... not accepted" style trailing exclusions.
            clause_start = max(orig.rfind(".", 0, start), orig.rfind(";", 0, start),
                               start - 80)
            window = orig[max(clause_start, 0):end + 18]

            if _EXCLUDE_CTX.search(window):
                ctx = "excluded"
            elif any(s <= mid <= e for s, e in rec_spans):
                ctx = "recommended"
            elif _RECOMMEND_CTX.search(window):
                ctx = "recommended"
            elif canon == "English" and _ENGLISH_FALSE.search(orig[start:end + 22]):
                ctx = "excluded"  # "English exam board" — not the subject
            else:
                ctx = "required"

            # A subject required somewhere wins over a later soft/excluded mention.
            if found.get(canon) != "required":
                found[canon] = ctx
            work = work[:start] + (" " * (end - start)) + work[end:]
    return found


def extract_subject_requirements(alevel_text: str, ib_text: str) -> dict:
    """Combine A-Level and IB detail text into clean structured requirements.

    Returns {"required_subjects": "A; B", "subject_req_status": "specified|open|unknown"}.
    Required subjects are the UNION across both qualification routes (a subject
    required by either route is treated as required).
    """
    combined_ctx: dict[str, str] = {}
    for txt in (alevel_text, ib_text):
        for canon, ctx in _classify_one(txt).items():
            if combined_ctx.get(canon) != "required":
                combined_ctx[canon] = ctx

    required = sorted(
        c for c, ctx in combined_ctx.items()
        if ctx == "required" and c not in _EXCLUSION_ONLY
    )

    if required:
        status = "specified"
    else:
        blob = f"{alevel_text or ''} {ib_text or ''}"
        if _OPEN_RE.search(blob):
            status = "open"
        else:
            status = "unknown"

    return {
        "required_subjects": "; ".join(required),
        "subject_req_status": status,
    }


def add_subject_requirement_columns(df):
    """Add `required_subjects` and `subject_req_status` columns to a courses df.

    Expects `alevel_details` and `ib_details` columns. Idempotent.
    """
    al = df["alevel_details"] if "alevel_details" in df.columns else ""
    ib = df["ib_details"] if "ib_details" in df.columns else ""
    results = [
        extract_subject_requirements(
            al.iloc[i] if hasattr(al, "iloc") else "",
            ib.iloc[i] if hasattr(ib, "iloc") else "",
        )
        for i in range(len(df))
    ]
    df["required_subjects"] = [r["required_subjects"] for r in results]
    df["subject_req_status"] = [r["subject_req_status"] for r in results]
    return df
