"""Replay tests on invented history."""
import os
import sys
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from reader import replay  # noqa: E402


def row(hours, status, approx=False):
    return {"ts": datetime(2030, 1, 1) + timedelta(hours=hours), "ts_approx": approx, "status": status}


class ReplayTests(unittest.TestCase):
    def test_four_failures_one_alert_with_skips(self):
        rows = [row(h, "auth_expired") for h in (0, 4, 8, 12)]
        r = replay.replay(rows)
        self.assertEqual(r["failed_cycles"], 4)
        self.assertEqual(r["alerts"], 1)
        self.assertEqual(r["attempts_skipped_by_backoff"], 0)  # 4h spacing >= 1,2,4h waits

    def test_eight_hour_wait_skips_next_cycle(self):
        rows = [row(h, "auth_expired") for h in range(0, 44, 4)]
        r = replay.replay(rows)
        self.assertEqual(r["alerts"], 1)
        self.assertGreater(r["attempts_skipped_by_backoff"], 0)

    def test_recovery_then_new_episode_alerts_again(self):
        rows = [row(0, "auth_expired"), row(4, "ok"), row(8, "auth_expired")]
        self.assertEqual(replay.replay(rows)["alerts"], 2)

    def test_approx_rows_excluded(self):
        rows = [row(0, "auth_expired", approx=True)]
        self.assertEqual(replay.replay(rows)["replayed_cycles"], 0)


if __name__ == "__main__":
    unittest.main()
