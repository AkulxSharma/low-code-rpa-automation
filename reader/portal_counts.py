"""Read-only counts from a logged-in UB Learns / Outlook page, with a seen-set diff.

Takes a Playwright page (already logged in) and returns numbers and opaque hashes only.
Nothing here returns, prints or stores page text, course names, grades or message
content: items are identified by the SHA-256 of their link or aria-label, and only
those hashes are kept in the gitignored state/ folder. A person restoring a session
is outside this module; it never logs in.
"""
import hashlib
import json
import os

WORKTODO_URL = "https://ublearns.buffalo.edu/d2l/le/worktodo/view"
HOME_URL = "https://ublearns.buffalo.edu/d2l/home"
OUTLOOK_URL = "https://outlook.office.com/mail/"
WORKTODO_ITEMS = "a[href*='folder_submit_files'], a[href*='/discussions/topics/'], a[href*='/quizzing/']"


def _hash(value):
    return hashlib.sha256(value.encode("utf-8", "replace")).hexdigest()[:16]


def _hashes(page, selector, attribute):
    seen = []
    for el in page.locator(selector).all():
        value = el.get_attribute(attribute) or ""
        if value:
            seen.append(_hash(value))
    return sorted(set(seen))


def courses(page):
    return _hashes(page, "a[href*='/d2l/home/']", "href")


def worktodo(page):
    return _hashes(page, WORKTODO_ITEMS, "href")


def inbox(page):
    return _hashes(page, "[role=option]", "aria-label")


def new_since(state_path, key, current):
    """Count hashes not seen before, then remember them. The first run for a key counts everything as seen (baseline)."""
    try:
        with open(state_path) as handle:
            state = json.load(handle)
    except (OSError, ValueError):
        state = {}
    first_run = key not in state
    known = set(state.get(key, []))
    fresh = 0 if first_run else len([h for h in current if h not in known])
    state[key] = sorted(known | set(current))
    os.makedirs(os.path.dirname(state_path), exist_ok=True)
    with open(state_path, "w") as handle:
        json.dump(state, handle)
    return fresh


def summarize(page_courses, page_worktodo, page_inbox, state_path):
    """Counts for one cycle: totals plus new-since-last-run per area."""
    return {
        "courses": len(page_courses),
        "worktodo_items": len(page_worktodo),
        "worktodo_new": new_since(state_path, "worktodo", page_worktodo),
        "inbox_rows": len(page_inbox),
        "inbox_new": new_since(state_path, "inbox", page_inbox),
    }
