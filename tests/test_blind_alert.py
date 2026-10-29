"""Unit tests on invented rows. Nothing here is real sweep data."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from reader import blind_alert, stats  # noqa: E402
from tests.test_stats import rows_from  # noqa: E402


def csv_line(hour, status):
    return "2030-01-01T{:02d}:00,no,9,no,{},0,0,0,0,0,none,,x\n".format(hour, status)


def rows(statuses):
    return rows_from("".join(csv_line(i, s) for i, s in enumerate(statuses)))


class BlindAlertTests(unittest.TestCase):
    def test_no_alert_below_threshold(self):
        result = blind_alert.check(rows(["ok", "auth_expired", "auth_expired"]))
        self.assertFalse(result["alert"])
        self.assertEqual(result["cycles"], 2)

    def test_alert_at_threshold_counts_only_the_trailing_streak(self):
        result = blind_alert.check(rows(["auth_expired", "ok", "auth_expired", "auth_expired", "auth_expired"]))
        self.assertTrue(result["alert"])
        self.assertEqual(result["cycles"], 3)
        self.assertEqual(result["since"], "2030-01-01T02:00")

    def test_one_alert_per_episode(self):
        data = rows(["auth_expired"] * 4)
        first = blind_alert.check(data)
        self.assertTrue(first["alert"])
        again = blind_alert.check(data, last_alerted_key=first["key"])
        self.assertFalse(again["alert"])

    def test_recovery_then_new_episode_alerts_again(self):
        statuses = ["auth_expired"] * 3 + ["ok"] + ["auth_expired"] * 3
        result = blind_alert.check(rows(statuses), last_alerted_key="2030-01-01T00:00")
        self.assertTrue(result["alert"])
        self.assertEqual(result["since"], "2030-01-01T04:00")

    def test_last_cycle_passed_means_no_streak(self):
        self.assertEqual(blind_alert.open_streak(rows(["auth_expired"] * 5 + ["ok"])), (0, None))

    def test_inconclusive_probe_neither_breaks_nor_counts(self):
        result = blind_alert.check(rows(["auth_expired"] * 3 + ["probe_inconclusive"]))
        self.assertTrue(result["alert"])
        self.assertEqual(result["cycles"], 3)
        self.assertEqual(blind_alert.open_streak(rows(["ok", "probe_inconclusive"])), (0, None))

    def test_run_writes_alert_once_and_resets_after_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path, state, alert = (os.path.join(tmp, n) for n in ("s.csv", "state.json", "alert.txt"))

            def write(statuses):
                with open(csv_path, "w") as handle:
                    handle.write(stats_header() + "".join(csv_line(i, s) for i, s in enumerate(statuses)))

            write(["auth_expired"] * 3)
            self.assertTrue(blind_alert.run(csv_path, state, alert)["alert"])
            text = open(alert).read()
            self.assertIn("3 cycles", text)
            os.unlink(alert)
            self.assertFalse(blind_alert.run(csv_path, state, alert)["alert"])
            self.assertFalse(os.path.exists(alert))
            write(["auth_expired"] * 3 + ["ok"])
            blind_alert.run(csv_path, state, alert)
            self.assertIsNone(json.load(open(state))["last_alerted_key"])
            write(["auth_expired"] * 3 + ["ok"] + ["auth_expired"] * 3)
            self.assertTrue(blind_alert.run(csv_path, state, alert)["alert"])

    def test_run_creates_missing_state_and_data_folders(self):
        with tempfile.TemporaryDirectory() as tmp:  # a fresh clone has neither state/ nor data/ (both gitignored)
            csv_path = os.path.join(tmp, "s.csv")
            with open(csv_path, "w") as handle:
                handle.write(stats_header() + "".join(csv_line(i, "auth_expired") for i in range(3)))
            alert_path = os.path.join(tmp, "data", "alert.txt")
            state_path = os.path.join(tmp, "state", "b.json")
            self.assertTrue(blind_alert.run(csv_path, state_path, alert_path)["alert"])
            self.assertTrue(os.path.exists(alert_path))
            with open(state_path) as handle:
                self.assertIsNotNone(json.load(handle)["last_alerted_key"])


def stats_header():
    from tests.test_stats import HEADER
    return HEADER


if __name__ == "__main__":
    unittest.main()
