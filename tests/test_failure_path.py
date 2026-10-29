"""Failure-path tests against the mock portal (TEST HARNESS, invented data only)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from harness.mock_portal import MockPortal  # noqa: E402
from reader import failure_path as fp  # noqa: E402


class FailurePathTests(unittest.TestCase):
    def setUp(self):
        self.portal = MockPortal().__enter__()
        self.addCleanup(self.portal.__exit__, None, None, None)
        self.fetch = lambda: fp.http_fetch(self.portal.url)

    def test_ok(self):
        g = fp.Guard()
        self.assertEqual(g.run(self.fetch, 0)["result"], fp.OK)

    def test_each_expiry_signal_is_detected(self):
        for mode in ("expired_error", "redirect", "nonjson"):
            with self.subTest(mode=mode):
                self.portal.set_mode(mode)
                self.assertEqual(fp.Guard().run(self.fetch, 0)["result"], fp.EXPIRED)

    def test_no_retry_loop_and_one_alert_per_episode(self):
        self.portal.set_mode("expired_error")
        g = fp.Guard()
        first = g.run(self.fetch, 0)
        hits_after_first = self.portal.hits
        self.assertTrue(first["alert"])
        self.assertEqual(hits_after_first, 1)  # a single request, no retry on expiry
        self.assertEqual(g.run(self.fetch, 0.5)["result"], fp.SKIPPED_BACKOFF)
        self.assertEqual(self.portal.hits, hits_after_first)  # nothing sent during backoff
        second = g.run(self.fetch, 1.0)
        self.assertEqual(second["result"], fp.EXPIRED)
        self.assertFalse(second["alert"])  # same episode, no second alert
        self.assertEqual(g.alerts_sent, 1)

    def test_backoff_grows_and_caps(self):
        self.portal.set_mode("redirect")
        g, now, gaps = fp.Guard(), 0.0, []
        for _ in range(6):
            g.run(self.fetch, now)
            gaps.append(g.next_attempt - now)
            now = g.next_attempt
        self.assertEqual(gaps, [1, 2, 4, 8, 8, 8])

    def test_recovery_clears_state_and_rearms_alert(self):
        self.portal.set_mode("expired_error")
        g = fp.Guard()
        g.run(self.fetch, 0)
        self.portal.set_mode("ok")  # stands in for a person logging in again
        self.assertEqual(g.run(self.fetch, 1)["result"], fp.OK)
        self.assertIsNone(g.dead_letter)
        self.portal.set_mode("expired_error")
        self.assertTrue(g.run(self.fetch, 2)["alert"])
        self.assertEqual(g.alerts_sent, 2)

    def test_dead_letter_records_since_and_next(self):
        self.portal.set_mode("nonjson")
        g = fp.Guard()
        g.run(self.fetch, 3)
        self.assertEqual(g.dead_letter, {"skipped_since_hours": 3, "next_attempt_hours": 4})

    def test_transient_retries_three_times_then_fails_without_alert(self):
        self.portal.set_mode("flaky")  # odd hits 503, even hits 200
        g = fp.Guard()
        self.assertEqual(g.run(self.fetch, 0)["result"], fp.OK)  # 503 then 200 on retry
        self.portal.set_mode("transient_always")  # unknown mode -> 500
        before = self.portal.hits
        out = fp.Guard().run(self.fetch, 0)
        self.assertEqual(out, {"result": fp.TRANSIENT_FAILED, "alert": False})
        self.assertEqual(self.portal.hits - before, 1 + fp.MAX_TRANSIENT_RETRIES)

    def test_classify_error_pages_are_not_session_expiry(self):
        self.assertEqual(fp.classify(401, None, '{"error": "Unauthorized"}'), fp.EXPIRED)
        self.assertEqual(fp.classify(200, None, "<html>Please sign in</html>"), fp.EXPIRED)
        for status in (404, 429):
            with self.subTest(status=status):
                self.assertEqual(fp.classify(status, None, "<html>error page</html>"), "transient")

    def test_network_error_is_transient_and_retried_without_alert(self):
        calls = []

        def down():
            calls.append(1)
            raise ConnectionRefusedError("portal down")
        out = fp.Guard().run(down, 0)
        self.assertEqual(out, {"result": fp.TRANSIENT_FAILED, "alert": False})
        self.assertEqual(len(calls), 1 + fp.MAX_TRANSIENT_RETRIES)


if __name__ == "__main__":
    unittest.main()
