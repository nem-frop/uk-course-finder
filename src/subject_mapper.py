"""
Map UCAS course names to QS subject categories.

Uses keyword matching to assign each course to the most relevant QS subject.
A course can map to multiple QS subjects (e.g. "Biochemistry" -> Chemistry, Biological).
"""

# Ordered by specificity - more specific patterns first
# Each entry: (QS subject name, list of keyword patterns)
# Patterns are matched case-insensitively against the course name
SUBJECT_RULES = [
    # Engineering specialties (before general engineering)
    ("Engineering - Chemical", ["chemical engineering"]),
    ("Engineering - Civil", ["civil engineering"]),
    ("Engineering - Electrical", ["electrical engineering", "electronic engineering", "electronics"]),
    ("Engineering - Mechanical", ["mechanical engineering"]),
    ("Engineering - Mineral", ["mining engineering", "mineral engineering"]),
    ("Petroleum Engineering", ["petroleum engineering"]),

    # Medicine and health (before general science)
    ("Medicine", ["medicine", "medical sciences", "mbbs", "mbchb", "clinical",
                  "radiography", "diagnostic imaging"]),
    ("Dentistry", ["dentistry", "dental"]),
    ("Nursing", ["nursing", "midwifery", "audiology", "speech therapy",
                 "occupational therapy", "physiotherapy"]),
    ("Pharmacy", ["pharmacy", "pharmacology", "pharmaceutical"]),
    ("Veterinary Science", ["veterinary"]),
    ("Anatomy", ["anatomy", "physiology"]),
    ("Psychology", ["psychology"]),

    # Sciences
    ("Chemistry", ["chemistry", "chemical"]),
    ("Physics", ["physics", "astrophysics", "theoretical physics"]),
    ("Biological", ["biology", "biological", "biochemistry", "biomedical", "bioscience",
                     "genetics", "microbiology", "neuroscience", "zoology", "ecology",
                     "molecular biology", "cell biology", "biotechnology", "animal",
                     "plant science"]),
    ("Mathematics", ["mathematics", "maths", "mathematical"]),
    ("Statistics", ["statistics", "statistical", "actuarial"]),
    ("Computer Science", ["computer science", "computing", "software engineering",
                          "artificial intelligence", "data science", "informatics",
                          "cyber security", "cybersecurity"]),
    ("Data Science", ["data science", "data analytics"]),
    ("Materials Science", ["materials science", "materials engineering"]),
    ("Environmental Sciences", ["environmental science", "environmental studies",
                                 "sustainability", "climate"]),
    ("Earth & Marine Sciences", ["earth science", "marine", "ocean"]),
    ("Geology", ["geology", "geological"]),
    ("Geophysics", ["geophysics"]),

    # Engineering general (after specialties)
    ("Engineering & Technology", ["engineering", "mechatronics", "robotics",
                                   "aerospace", "automotive", "bioengineering"]),

    # Business
    ("Accounting", ["accounting"]),
    ("Business", ["business", "management", "commerce", "enterprise",
                  "finance", "banking", "investment"]),
    ("Marketing", ["marketing"]),
    ("Economics & Econometrics", ["economics", "econometrics"]),

    # Social sciences
    ("Law", ["law", "legal"]),
    ("Politics", ["politics", "political", "international relations", "government",
                   "public policy", "public administration"]),
    ("Sociology", ["sociology", "social science", "childhood studies"]),
    ("Anthropology", ["anthropology"]),
    ("Education", ["education", "teaching"]),
    ("Development Studies", ["development studies", "international development"]),
    ("Social Policy", ["social policy", "social work", "criminology"]),
    ("Communication", ["journalism", "media", "communication", "film"]),
    ("Geography", ["geography", "geographic"]),
    ("Area Studies", ["middle east", "middle eastern", "area studies"]),
    ("Hospitality", ["hospitality", "tourism"]),
    ("Sports-related Subjects", ["sport", "exercise science", "kinesiology"]),

    # Humanities
    ("History$", ["history"]),
    ("History of Art", ["history of art", "art history"]),
    ("Archaeology", ["archaeology", "archaeological"]),
    ("Classics", ["classics", "classical", "latin", "greek", "ancient", "assyriology",
                  "egyptology"]),
    ("Philosophy", ["philosophy"]),
    ("Theology", ["theology", "religious studies", "divinity", "religion"]),
    ("English Language", ["english", "creative writing", "literature"]),
    ("Modern Languages", ["french", "german", "spanish", "italian", "portuguese",
                           "russian", "japanese", "chinese", "mandarin", "arabic",
                           "language", "linguistics", "celtic", "gaelic", "persian",
                           "korean", "slavonic", "czech", "polish", "hebrew",
                           "scandinavian", "dutch", "catalan", "romanian",
                           "bulgarian", "danish", "finnish", "hungarian",
                           "norwegian", "serbian", "croatian", "swedish",
                           "ukrainian", "yiddish", "turkish", "thai",
                           "swahili", "sanskrit"]),
    ("Linguistics", ["linguistics", "phonetics"]),
    ("Music", ["music"]),
    ("Performing Arts", ["drama", "theatre", "dance", "performing arts"]),
    ("Art & Design", ["art", "design", "fine art", "fashion", "textile", "animation",
                      "creative", "visual"]),
    ("Architecture", ["architecture"]),

    # Natural Sciences (broad)
    ("Natural Sciences", ["natural sciences", "science"]),
]


def map_course_to_subjects(course_name: str) -> list[str]:
    """Map a course name to a list of matching QS subject categories."""
    name_lower = course_name.lower()
    matches = []
    for qs_subject, keywords in SUBJECT_RULES:
        for keyword in keywords:
            if keyword in name_lower:
                matches.append(qs_subject)
                break
    return matches


def map_course_to_primary_subject(course_name: str) -> str | None:
    """Map a course name to its primary (first matching) QS subject."""
    matches = map_course_to_subjects(course_name)
    return matches[0] if matches else None


def map_course_to_domain(course_name: str) -> str:
    """Map a course name to a broad domain category for display."""
    primary = map_course_to_primary_subject(course_name)
    if not primary:
        return "Other"
    return SUBJECT_TO_DOMAIN.get(primary, "Other")


# Broad domain categories for colored tags (like IvyPrep's Domain column)
SUBJECT_TO_DOMAIN = {
    # STEM
    "Computer Science": "Computing & Technology",
    "Data Science": "Computing & Technology",
    "Engineering & Technology": "Engineering",
    "Engineering - Chemical": "Engineering",
    "Engineering - Civil": "Engineering",
    "Engineering - Electrical": "Engineering",
    "Engineering - Mechanical": "Engineering",
    "Engineering - Mineral": "Engineering",
    "Petroleum Engineering": "Engineering",
    "Mathematics": "Mathematics & Statistics",
    "Statistics": "Mathematics & Statistics",
    "Physics": "Physical Sciences",
    "Chemistry": "Physical Sciences",
    "Materials Science": "Physical Sciences",
    "Earth & Marine Sciences": "Physical Sciences",
    "Geology": "Physical Sciences",
    "Geophysics": "Physical Sciences",
    "Environmental Sciences": "Physical Sciences",
    "Biological": "Life Sciences",
    "Anatomy": "Life Sciences",
    "Natural Sciences": "Life Sciences",

    # Health
    "Medicine": "Medicine & Health",
    "Dentistry": "Medicine & Health",
    "Nursing": "Medicine & Health",
    "Pharmacy": "Medicine & Health",
    "Veterinary Science": "Medicine & Health",
    "Psychology": "Social Sciences",

    # Business
    "Accounting": "Business & Economics",
    "Business": "Business & Economics",
    "Marketing": "Business & Economics",
    "Economics & Econometrics": "Business & Economics",
    "Hospitality": "Business & Economics",

    # Social Sciences
    "Law": "Law",
    "Politics": "Social Sciences",
    "Sociology": "Social Sciences",
    "Anthropology": "Social Sciences",
    "Education": "Social Sciences",
    "Development Studies": "Social Sciences",
    "Social Policy": "Social Sciences",
    "Communication": "Social Sciences",
    "Geography": "Social Sciences",
    "Area Studies": "Social Sciences",
    "Sports-related Subjects": "Social Sciences",

    # Humanities
    "History$": "Humanities",
    "History of Art": "Humanities",
    "Archaeology": "Humanities",
    "Classics": "Humanities",
    "Philosophy": "Humanities",
    "Theology": "Humanities",
    "English Language": "Humanities",
    "Modern Languages": "Humanities",
    "Linguistics": "Humanities",
    "Music": "Arts",
    "Performing Arts": "Arts",
    "Art & Design": "Arts",
    "Architecture": "Arts",
}


if __name__ == "__main__":
    # Test with sample course names
    import pandas as pd
    from pathlib import Path

    courses = pd.read_csv(Path(__file__).parent.parent / "data" / "courses.csv")

    # Map all courses
    courses["domain"] = courses["course"].apply(map_course_to_domain)
    courses["qs_subject"] = courses["course"].apply(map_course_to_primary_subject)

    unmapped = courses[courses["domain"] == "Other"]
    print(f"Mapped: {len(courses) - len(unmapped)}/{len(courses)} courses ({100*(1-len(unmapped)/len(courses)):.1f}%)")
    print(f"\nDomain distribution:")
    print(courses["domain"].value_counts().to_string())
    print(f"\nUnmapped courses ({len(unmapped)}):")
    for c in sorted(unmapped["course"].unique())[:30]:
        print(f"  {c}")
    if len(unmapped["course"].unique()) > 30:
        print(f"  ... and {len(unmapped['course'].unique()) - 30} more")
