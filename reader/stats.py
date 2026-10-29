"""Read-only aggregates over the live sweep's per-cycle statistics file.

Input is the CSV the sweep's owner writes (sessions/fall 2026/sweep-stats.csv).
Only counts and timings are read. The free-text `source` column is never
returned or printed, because it can name internal job ids and notes.
"""
import csv
import statistics
import sys
from datetime import datetime

FAILED = {"auth_expired"}
# A probe that could not tell logged in from logged out: neither a pass nor a failure, so it
# neither ends nor extends an expiry episode and carries no pass duration.
NEUTRAL = {"probe_inconclusive"}
ITEM_COLUMNS = ("new_announcements", "new_grades", "new_due_dates", "new_emails", "new_wispr_meetings")


def _int(value):
    value = (value or "").strip()
    try:
        return int(value) if value else None
    except ValueError:  # "n/a", "12s" and the like: treat as missing rather than failing the whole file
        return None


def _ts(value):
    value = (value or "").strip()
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def load(path):
    with open(path, newline="") as handle:
        rows = []
        for raw in csv.DictReader(handle):
            rows.append({
                "ts": _ts(raw.get("ts_edt")),
                "ts_approx": raw.get("ts_approx", "").strip() == "yes",
                "duration_s": _int(raw.get("duration_s")),
                "duration_approx": raw.get("duration_approx", "").strip() == "yes",
                "status": raw.get("status", "").strip(),
                "items": {c: _int(raw.get(c)) for c in ITEM_COLUMNS},
                "auth_event": raw.get("auth_event", "").strip(),
            })
        return rows


def percentile(values, q):
    """Nearest-rank percentile; None when there are no values."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, -(-len(ordered) * q // 100))
    return ordered[int(rank) - 1]


def episodes(rows):
    """Runs of consecutive failed cycles. Each is (cycles, first_ts, recovered_ts or None)."""
    found, current = [], None
    for row in rows:
        if row["status"] in NEUTRAL:
            continue
        if row["status"] in FAILED:
            if current is None:
                current = {"cycles": 0, "first": row["ts"], "recovered": None}
            current["cycles"] += 1
        elif current is not None:
            current["recovered"] = row["ts"]
            found.append(current)
            current = None
    if current is not None:
        found.append(current)
    return found


def summarize(rows):
    stamps = [r["ts"] for r in rows if r["ts"]]
    durations = [r["duration_s"] for r in rows if r["duration_s"] is not None]
    # A blind cycle (logged out, auth_expired) ends at the login page, so its
    # duration is not the duration of a real pass and is reported separately.
    pass_durations = [r["duration_s"] for r in rows if r["duration_s"] is not None and r["status"] not in FAILED and r["status"] not in NEUTRAL]
    blind_durations = [r["duration_s"] for r in rows if r["duration_s"] is not None and r["status"] in FAILED]
    status_counts = {}
    for row in rows:
        status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1
    totals = {c: sum(r["items"][c] or 0 for r in rows) for c in ITEM_COLUMNS}
    checked = {c: sum(1 for r in rows if r["items"][c] is not None) for c in ITEM_COLUMNS}
    eps = episodes(rows)
    return {
        "n_runs": len(rows),
        "date_first": min(stamps).date().isoformat() if stamps else None,
        "date_last": max(stamps).date().isoformat() if stamps else None,
        "status_counts": status_counts,
        "n_with_duration": len(durations),
        "duration_p50_s": statistics.median(durations) if durations else None,
        "duration_p90_s": percentile(durations, 90),
        "pass_n_with_duration": len(pass_durations),
        "pass_p50_s": statistics.median(pass_durations) if pass_durations else None,
        "pass_p90_s": percentile(pass_durations, 90),
        "blind_n_with_duration": len(blind_durations),
        "blind_p50_s": statistics.median(blind_durations) if blind_durations else None,
        "blind_p90_s": percentile(blind_durations, 90),
        "new_items_total": totals,
        "runs_that_checked_item": checked,
        "expiry_episodes": len(eps),
        "episode_cycles": [e["cycles"] for e in eps],
        "episodes_still_open": sum(1 for e in eps if e["recovered"] is None),
    }


def _period(summary):
    """Month-level period only: exact days would reveal when sessions ran."""
    first, last = (summary["date_first"] or "")[:7], (summary["date_last"] or "")[:7]
    return first if first == last else "{} to {}".format(first, last)


def cycle_section(path):
    """Summary of this repo's own logged-in cycles (data/rpa-cycles.csv). Counts and timings only; empty string if absent."""
    try:
        with open(path, newline="") as handle:
            rows = list(csv.DictReader(handle))
    except OSError:
        return ""
    if not rows:
        return ""
    durations = [int(r["duration_s"]) for r in rows if (r.get("duration_s") or "").strip()]
    ok = [r for r in rows if r["status"] == "ok_logged_in"]
    return ("## This repo's own logged-in cycles\n\n"
            "n cycles: {n} ({ok} ok). Duration p50 {p50} s, max {mx} s. Duo pushes: {duo} in total ({per:.1f} per cycle). "
            "Items seen per cycle: {courses} courses, {todo} to-do items, {inbox} inbox rows. "
            "New inbox rows found since the previous cycle: {new} in total.\n").format(
        n=len(rows), ok=len(ok), p50=statistics.median(durations) if durations else "n/a", mx=max(durations) if durations else "n/a",
        duo=sum(int(r.get("duo_pushes") or 0) for r in rows), per=sum(int(r.get("duo_pushes") or 0) for r in rows) / len(rows),
        courses=rows[-1]["courses"], todo=rows[-1]["worktodo_items"], inbox=rows[-1]["inbox_rows"],
        new=sum(int(r.get("inbox_new") or 0) for r in rows))


def render(summary):
    lines = [
        "# Measured from the live sweep",
        "",
        "n runs: {n_runs}, {period}.".format(period=_period(summary), **summary),
        "Status counts: " + ", ".join("{}={}".format(k, v) for k, v in sorted(summary["status_counts"].items())) + ".",
    ]
    if summary["pass_n_with_duration"]:
        lines.append("Duration of passes that got past login: p50 {} s, p90 {} s, from {} runs.".format(
            summary["pass_p50_s"], summary["pass_p90_s"], summary["pass_n_with_duration"]))
    else:
        lines.append("Duration of passes that got past login: no run has a recorded duration yet.")
    if summary["blind_n_with_duration"]:
        lines.append("Duration of blind cycles (logged out, ended at the login page): p50 {} s, p90 {} s, from {} runs.".format(
            summary["blind_p50_s"], summary["blind_p90_s"], summary["blind_n_with_duration"]))
    lines.append("{} of {} runs have no recorded duration.".format(summary["n_runs"] - summary["n_with_duration"], summary["n_runs"]))
    lines.append("New items (total over runs that checked that type): " + ", ".join(
        "{}={} ({} of {} runs)".format(k.replace("new_", ""), v, summary["runs_that_checked_item"][k], summary["n_runs"])
        for k, v in summary["new_items_total"].items()) + ".")
    lines.append("Session-expiry episodes: {} (cycles each: {}); still open: {}.".format(
        summary["expiry_episodes"], summary["episode_cycles"], summary["episodes_still_open"]))
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python3 -I reader/stats.py <path to sweep-stats.csv>")
    sys.stdout.write(render(summarize(load(sys.argv[1]))))
