"""Alert when the live sweep has been logged out for several cycles in a row.

Pure logic over the rows from reader.stats.load, plus a small CLI that keeps
one line of state so each logged-out episode alerts once. It reads counts and
timestamps only and never logs in. A person restoring the session is outside
this module.
"""
import json
import os
import sys

from reader import stats

DEFAULT_THRESHOLD = 3
# An inconclusive probe says nothing about the session: it neither breaks nor extends a streak.
NEUTRAL = {"probe_inconclusive"}


def open_streak(rows):
    """The trailing run of failed cycles: (cycles, first_ts or None). (0, None) if the last cycle passed."""
    cycles, first = 0, None
    for row in reversed(rows):
        if row["status"] in NEUTRAL:
            continue
        if row["status"] not in stats.FAILED:
            break
        cycles += 1
        first = row["ts"]
    return cycles, first


def episode_key(first):
    return first.isoformat(timespec="minutes") if first else None


def check(rows, last_alerted_key=None, threshold=DEFAULT_THRESHOLD):
    """Return {"alert", "cycles", "since", "key"}. Alerts once per episode, at the threshold or later."""
    cycles, first = open_streak(rows)
    key = episode_key(first)
    due = cycles >= threshold and key is not None and key != last_alerted_key
    return {"alert": due, "cycles": cycles, "since": key, "key": key}


def message(result):
    return ("Sweep has been logged out for {} cycles in a row (since {}). "
            "Log in to UB Learns and text 'in' so the real sweep can resume.").format(result["cycles"], result["since"])


def run(csv_path, state_path, alert_path, threshold=DEFAULT_THRESHOLD):
    """Evaluate, write the alert file and update state when due. Returns the check result."""
    try:
        with open(state_path) as handle:
            last = json.load(handle).get("last_alerted_key")
    except (OSError, ValueError):
        last = None
    result = check(stats.load(csv_path), last, threshold)
    if result["alert"]:
        with open(alert_path, "w") as handle:
            handle.write(message(result) + "\n")
        with open(state_path, "w") as handle:
            json.dump({"last_alerted_key": result["key"]}, handle)
    elif result["cycles"] == 0 and last is not None:
        with open(state_path, "w") as handle:  # recovered: the next episode may alert again
            json.dump({"last_alerted_key": None}, handle)
    return result


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python3 -m reader.blind_alert <path to sweep-stats.csv>")
    here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    out = run(sys.argv[1], os.path.join(here, "state", "blind-alert.json"), os.path.join(here, "data", "alert-blind.txt"))
    print(json.dumps({"alert": out["alert"], "cycles": out["cycles"], "since": out["since"]}))
