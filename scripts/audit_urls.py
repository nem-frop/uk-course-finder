"""Systematic URL audit for courses.csv.

Checks course URLs in batches with delays to avoid anti-bot triggers.
Tracks audit status in a separate file (data/url_audit.csv) so progress
persists across sessions.

Usage:
    python scripts/audit_urls.py                 # audit next unaudited batch (50)
    python scripts/audit_urls.py --batch 100     # audit 100 URLs
    python scripts/audit_urls.py --uni "Warwick"  # audit only Warwick URLs
    python scripts/audit_urls.py --recheck-fails  # re-audit previously failed URLs
    python scripts/audit_urls.py --report         # print summary report only
    python scripts/audit_urls.py --fix            # apply fixes (broken -> Google search)
"""

import argparse
import pandas as pd
import time
import random
import sys
from pathlib import Path
from urllib.parse import urlparse, quote_plus
from datetime import datetime
import urllib.request
import urllib.error
import ssl

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
COURSES_CSV = DATA_DIR / "courses.csv"
AUDIT_CSV = DATA_DIR / "url_audit.csv"

# Delay between requests (seconds) — randomized to look human
MIN_DELAY = 1.0
MAX_DELAY = 3.0

# Per-domain rate limiting: max requests before a longer pause
DOMAIN_BATCH_SIZE = 15
DOMAIN_PAUSE = 10.0  # seconds pause after DOMAIN_BATCH_SIZE requests to same domain

# User agent rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]

# SSL context that doesn't verify (some uni sites have cert issues)
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE


def load_audit() -> pd.DataFrame:
    """Load or create the audit tracking file."""
    if AUDIT_CSV.exists():
        return pd.read_csv(AUDIT_CSV)

    # Create from courses.csv
    courses = pd.read_csv(COURSES_CSV)
    audit = courses[["university", "course", "ucas_code", "course_url"]].copy()
    audit["audit_status"] = ""          # "", "ok", "redirect", "broken", "timeout", "error", "google_fallback"
    audit["http_status"] = ""           # HTTP status code
    audit["final_url"] = ""             # After redirects
    audit["audit_date"] = ""            # When last checked
    audit["notes"] = ""                 # Any notes
    audit.to_csv(AUDIT_CSV, index=False)
    print(f"Created audit file: {AUDIT_CSV} ({len(audit)} rows)")
    return audit


def check_url(url: str, timeout: int = 15) -> dict:
    """Check a single URL. Returns status dict."""
    if pd.isna(url) or not url or url.strip() == "":
        return {"status": "missing", "http_code": "", "final_url": "", "notes": "No URL"}

    url = url.strip()

    # Skip Google search fallbacks
    if "google.com/search" in url:
        return {"status": "google_fallback", "http_code": "", "final_url": url,
                "notes": "Google search fallback (no direct URL available)"}

    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-GB,en;q=0.5",
        })
        resp = urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX)
        final_url = resp.url
        code = resp.status

        # Check if we got redirected to a generic page
        notes = ""
        if final_url != url:
            notes = f"Redirected from {urlparse(url).path}"

        status = "ok" if 200 <= code < 400 else f"http_{code}"
        return {"status": status, "http_code": str(code), "final_url": final_url, "notes": notes}

    except urllib.error.HTTPError as e:
        return {"status": "broken", "http_code": str(e.code), "final_url": "",
                "notes": f"HTTP {e.code}"}

    except urllib.error.URLError as e:
        reason = str(e.reason) if hasattr(e, 'reason') else str(e)
        if "timed out" in reason.lower() or "timeout" in reason.lower():
            return {"status": "timeout", "http_code": "", "final_url": "",
                    "notes": f"Timeout after {timeout}s"}
        return {"status": "error", "http_code": "", "final_url": "",
                "notes": f"URLError: {reason[:100]}"}

    except Exception as e:
        return {"status": "error", "http_code": "", "final_url": "",
                "notes": f"{type(e).__name__}: {str(e)[:100]}"}


def run_audit(batch_size: int = 50, uni_filter: str = None, recheck_fails: bool = False, slow: bool = False):
    """Run a batch of URL checks. Use slow=True for rate-limit-prone sites (5-10s delays)."""
    global MIN_DELAY, MAX_DELAY, DOMAIN_BATCH_SIZE, DOMAIN_PAUSE
    if slow:
        MIN_DELAY = 5.0
        MAX_DELAY = 10.0
        DOMAIN_BATCH_SIZE = 8
        DOMAIN_PAUSE = 20.0
        print("SLOW MODE: 5-10s delays, 20s pause every 8 requests")
    audit = load_audit()

    # Select rows to audit
    if recheck_fails:
        # Re-audit previously failed URLs
        to_check = audit[audit["audit_status"].isin(["broken", "timeout", "error"])]
        print(f"Re-checking {len(to_check)} previously failed URLs")
    elif uni_filter:
        to_check = audit[
            (audit["university"].str.contains(uni_filter, case=False, na=False)) &
            (audit["audit_status"].fillna("") == "")
        ]
        print(f"Checking {len(to_check)} unaudited URLs for '{uni_filter}'")
    else:
        to_check = audit[audit["audit_status"].fillna("") == ""]
        print(f"Found {len(to_check)} unaudited URLs total")

    if len(to_check) == 0:
        print("Nothing to audit!")
        return

    # Limit to batch size
    batch = to_check.head(batch_size)
    print(f"Auditing batch of {len(batch)} URLs...")
    print()

    # Track per-domain request counts
    domain_counts = {}
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    checked = 0
    ok = 0
    broken = 0
    other = 0

    for idx, row in batch.iterrows():
        url = row["course_url"]
        uni_short = row["university"].split()[-1] if pd.notna(row["university"]) else "?"
        course_short = str(row["course"])[:40]

        # Domain-based rate limiting
        if pd.notna(url) and "google.com" not in str(url):
            domain = urlparse(str(url)).netloc
            domain_counts[domain] = domain_counts.get(domain, 0) + 1
            if domain_counts[domain] > 0 and domain_counts[domain] % DOMAIN_BATCH_SIZE == 0:
                print(f"  [pause] {DOMAIN_PAUSE}s cooldown for {domain} ({domain_counts[domain]} requests)")
                time.sleep(DOMAIN_PAUSE)

        # Check the URL
        result = check_url(url)

        # Update audit
        audit.at[idx, "audit_status"] = result["status"]
        audit.at[idx, "http_status"] = result["http_code"]
        audit.at[idx, "final_url"] = result["final_url"]
        audit.at[idx, "audit_date"] = now
        audit.at[idx, "notes"] = result["notes"]

        # Progress indicator
        checked += 1
        status_icon = {
            "ok": "+", "redirect": "~", "broken": "X", "timeout": "T",
            "error": "!", "google_fallback": "G", "missing": "-"
        }.get(result["status"], "?")

        if result["status"] == "ok":
            ok += 1
        elif result["status"] in ("broken", "timeout", "error"):
            broken += 1
            print(f"  [{status_icon}] {uni_short}: {course_short} -> {result['http_code']} {result['notes']}")
        else:
            other += 1

        if checked % 10 == 0:
            print(f"  ... {checked}/{len(batch)} checked ({ok} ok, {broken} broken, {other} other)")

        # Random delay between requests
        if checked < len(batch):
            delay = random.uniform(MIN_DELAY, MAX_DELAY)
            time.sleep(delay)

    # Save
    audit.to_csv(AUDIT_CSV, index=False)

    print()
    print(f"Batch complete: {checked} checked")
    print(f"  OK: {ok} | Broken: {broken} | Other: {other}")
    print(f"Saved to {AUDIT_CSV}")

    # Show overall progress
    total = len(audit)
    audited = audit["audit_status"].fillna("").ne("").sum()
    print(f"\nOverall progress: {audited}/{total} audited ({100*audited//total}%)")


def print_report():
    """Print summary report of audit status."""
    if not AUDIT_CSV.exists():
        print("No audit file found. Run an audit first.")
        return

    audit = pd.read_csv(AUDIT_CSV)
    total = len(audit)
    audited = audit["audit_status"].fillna("").ne("").sum()

    print(f"=== URL AUDIT REPORT ===")
    print(f"Total courses: {total}")
    print(f"Audited: {audited} ({100*audited//total}%)")
    print(f"Remaining: {total - audited}")
    print()

    if audited > 0:
        print("Status breakdown:")
        for status, count in audit["audit_status"].value_counts().items():
            if status:
                print(f"  {status}: {count}")
        print()

        # Broken by university
        broken = audit[audit["audit_status"].isin(["broken", "timeout", "error"])]
        if len(broken) > 0:
            print(f"Broken URLs by university ({len(broken)} total):")
            for uni, group in broken.groupby("university"):
                print(f"  {uni}: {len(group)}")
                for _, r in group.iterrows():
                    print(f"    {r['course']} -> {r['http_status']} {r['notes']}")
            print()

        # Progress by university
        print("Audit progress by university:")
        for uni in sorted(audit["university"].unique()):
            uni_data = audit[audit["university"] == uni]
            uni_audited = uni_data["audit_status"].fillna("").ne("").sum()
            uni_broken = uni_data["audit_status"].isin(["broken", "timeout", "error"]).sum()
            print(f"  {uni}: {uni_audited}/{len(uni_data)} audited, {uni_broken} broken")


def apply_fixes():
    """Apply fixes: replace broken URLs with Google search fallback in courses.csv."""
    if not AUDIT_CSV.exists():
        print("No audit file found.")
        return

    audit = pd.read_csv(AUDIT_CSV)
    courses = pd.read_csv(COURSES_CSV)

    broken = audit[audit["audit_status"].isin(["broken", "timeout", "error"])]
    if len(broken) == 0:
        print("No broken URLs to fix.")
        return

    fixed = 0
    for _, row in broken.iterrows():
        # Find matching course in courses.csv
        match = courses[
            (courses["university"] == row["university"]) &
            (courses["course"] == row["course"]) &
            (courses["ucas_code"] == row["ucas_code"])
        ]
        if len(match) == 0:
            continue

        idx = match.index[0]
        current_url = courses.at[idx, "course_url"]

        # Don't replace if already a Google fallback
        if pd.notna(current_url) and "google.com/search" in str(current_url):
            continue

        # Replace with Google search
        query = quote_plus(f"{row['course']} undergraduate {row['university']}")
        courses.at[idx, "course_url"] = f"https://www.google.com/search?q={query}"
        fixed += 1

    if fixed > 0:
        courses.to_csv(COURSES_CSV, index=False)
        print(f"Fixed {fixed} broken URLs -> Google search fallback")
    else:
        print("No fixes needed (all broken URLs already have fallbacks)")


def main():
    parser = argparse.ArgumentParser(description="Systematic URL audit for course links")
    parser.add_argument("--batch", type=int, default=50, help="Batch size (default: 50)")
    parser.add_argument("--uni", type=str, default=None, help="Filter by university name")
    parser.add_argument("--recheck-fails", action="store_true", help="Re-check previously failed URLs")
    parser.add_argument("--slow", action="store_true", help="Slow mode: longer delays for rate-limit-prone sites")
    parser.add_argument("--report", action="store_true", help="Print report only")
    parser.add_argument("--fix", action="store_true", help="Apply fixes to courses.csv")
    args = parser.parse_args()

    if args.report:
        print_report()
    elif args.fix:
        apply_fixes()
    else:
        run_audit(batch_size=args.batch, uni_filter=args.uni, recheck_fails=args.recheck_fails, slow=args.slow)


if __name__ == "__main__":
    main()
