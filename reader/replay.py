"""Replay measured sweep history through the failure path.

This is a computation on real recorded cycles. It says how many failed cycles
the state machine would have collapsed into how many alerts and skipped
attempts. It is not a claim about live behaviour. Only rows with an exact
timestamp (ts_approx = no) are replayed, because backoff needs real spacing.
"""
import sys

from reader import failure_path as fp
from reader import stats


def replay(rows):
    # Inconclusive probes are neutral (as in stats.episodes and blind_alert): they neither end nor extend an episode.
    exact = [r for r in rows if r["ts"] and not r["ts_approx"] and r["status"] not in stats.NEUTRAL]
    excluded = sum(1 for r in rows if not r["ts"] or r["ts_approx"])
    if not exact:
        return {"replayed_cycles": 0, "excluded_approx_rows": excluded}
    origin = exact[0]["ts"]
    guard = fp.Guard()
    failed = alerts = skipped = 0
    for row in exact:
        hours = (row["ts"] - origin).total_seconds() / 3600
        if row["status"] in stats.FAILED:
            failed += 1
            ok_fetch = lambda: (200, None, '{"error": "Authentication required"}')
        else:
            ok_fetch = lambda: (200, None, "{}")
        out = guard.run(ok_fetch, hours)
        alerts += out["alert"]
        skipped += out["result"] == fp.SKIPPED_BACKOFF
    return {
        "replayed_cycles": len(exact),
        "excluded_approx_rows": excluded,
        "failed_cycles": failed,
        "alerts": alerts,
        "attempts_skipped_by_backoff": skipped,
    }


def render(result):
    if not result.get("replayed_cycles"):
        return "Replay: no rows with an exact timestamp.\n"
    return ("Replayed on the measured history ({replayed_cycles} cycles with exact timestamps; "
            "{excluded_approx_rows} rows with approximate times left out): {failed_cycles} failed cycles "
            "would have produced {alerts} alert(s) and {attempts_skipped_by_backoff} attempt(s) skipped by backoff.\n").format(**result)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python3 -m reader.replay <path to sweep-stats.csv>")
    sys.stdout.write(render(replay(stats.load(sys.argv[1]))))
