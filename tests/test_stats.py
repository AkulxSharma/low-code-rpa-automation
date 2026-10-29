"""Unit tests on invented rows. Nothing here is real sweep data."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from reader import stats  # noqa: E402

HEADER = "ts_edt,ts_approx,duration_s,duration_approx,status,new_announcements,new_grades,new_due_dates,new_emails,new_wispr_meetings,auth_event,recovery,source\n"


def rows_from(text):
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as handle:
        handle.write(HEADER + text)
    try:
        return stats.load(handle.name)
    finally:
        os.unlink(handle.name)


class StatsTests(unittest.TestCase):
    def test_percentiles_and_missing_duration(self):
        rows = rows_from(
            "2030-01-01T01:00,no,10,no,ok,1,0,0,0,0,none,,x\n"
            "2030-01-01T05:00,no,20,no,ok,0,0,0,0,0,none,,x\n"
            "2030-01-01T09:00,no,,,ok,0,0,0,0,0,none,,x\n"
            "2030-01-01T13:00,no,40,no,ok,0,0,0,0,0,none,,x\n")
        s = stats.summarize(rows)
        self.assertEqual(s["n_runs"], 4)
        self.assertEqual(s["n_with_duration"], 3)
        self.assertEqual(s["duration_p50_s"], 20)
        self.assertEqual(s["duration_p90_s"], 40)

    def test_blind_durations_are_separate_from_pass_durations(self):
        rows = rows_from(
            "2030-01-01T01:00,no,5,no,auth_expired,,,,,,expired,,x\n"
            "2030-01-01T05:00,no,60,no,ok,0,0,0,0,0,none,,x\n")
        s = stats.summarize(rows)
        self.assertEqual(s["pass_p50_s"], 60)
        self.assertEqual(s["blind_p50_s"], 5)
        self.assertIn("blind cycles", stats.render(s))

    def test_episodes_group_consecutive_failures(self):
        rows = rows_from(
            "2030-01-01T01:00,no,5,no,auth_expired,,,,,,expired,,x\n"
            "2030-01-01T05:00,no,5,no,auth_expired,,,,,,expired,,x\n"
            "2030-01-01T09:00,no,5,no,ok,0,0,0,0,0,none,,x\n"
            "2030-01-01T13:00,no,5,no,auth_expired,,,,,,expired,,x\n")
        s = stats.summarize(rows)
        self.assertEqual(s["expiry_episodes"], 2)
        self.assertEqual(s["episode_cycles"], [2, 1])
        self.assertEqual(s["episodes_still_open"], 1)

    def test_blank_items_are_not_counted_as_zero_checks(self):
        rows = rows_from("2030-01-01,yes,,,partial,,1,0,,0,none,,x\n")
        s = stats.summarize(rows)
        self.assertEqual(s["new_items_total"]["new_grades"], 1)
        self.assertEqual(s["runs_that_checked_item"]["new_emails"], 0)

    def test_render_never_prints_source_column(self):
        rows = rows_from("2030-01-01T01:00,no,5,no,ok,0,0,0,0,0,none,,SECRET-JOB-ID\n")
        self.assertNotIn("SECRET-JOB-ID", stats.render(stats.summarize(rows)))

    def test_empty_file(self):
        s = stats.summarize([])
        self.assertEqual(s["n_runs"], 0)
        self.assertIsNone(s["duration_p50_s"])

    def test_inconclusive_probe_does_not_close_an_episode_or_count_as_a_pass(self):
        rows = rows_from(
            "2030-01-01T01:00,no,5,no,auth_expired,,,,,,expired,,x\n"
            "2030-01-01T05:00,no,19,no,probe_inconclusive,,,,,,none,,x\n"
            "2030-01-01T09:00,no,6,no,auth_expired,,,,,,expired,,x\n")
        s = stats.summarize(rows)
        self.assertEqual(s["episode_cycles"], [2])
        self.assertEqual(s["episodes_still_open"], 1)
        self.assertEqual(s["pass_n_with_duration"], 0)

    def test_cycle_section_counts_only(self):
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as handle:
            handle.write("ts_edt,duration_s,status,courses,worktodo_items,worktodo_new,inbox_rows,inbox_new,duo_pushes\n"
                         "2030-01-01T01:00,20,ok_logged_in,5,10,0,7,0,1\n2030-01-01T05:00,30,ok_logged_in,5,10,0,7,2,1\n")
        try:
            text = stats.cycle_section(handle.name)
        finally:
            os.unlink(handle.name)
        self.assertIn("n cycles: 2 (2 ok)", text)
        self.assertIn("p50 25.0 s", text)
        self.assertIn("Duo pushes: 2 in total", text)
        self.assertIn("2 in total.", text)
        self.assertEqual(stats.cycle_section("/nonexistent/none.csv"), "")

    def test_non_integer_cell_is_treated_as_missing(self):
        rows = rows_from("2030-01-01T01:00,no,n/a,no,ok,x,0,0,0,0,none,,y\n")
        self.assertIsNone(rows[0]["duration_s"])
        self.assertIsNone(rows[0]["items"]["new_announcements"])


if __name__ == "__main__":
    unittest.main()
