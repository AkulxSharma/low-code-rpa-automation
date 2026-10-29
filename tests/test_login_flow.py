"""Login-flow tests against the mock SSO (TEST HARNESS, invented credentials only)."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from harness.http_driver import HttpDriver  # noqa: E402
from harness.mock_sso import GOOD, MockSSO  # noqa: E402
from reader.login_flow import LoginFlow, StateStore  # noqa: E402


class LoginFlowTests(unittest.TestCase):
    def setUp(self):
        self.sso = MockSSO().__enter__()
        self.addCleanup(self.sso.__exit__, None, None, None)
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.store = StateStore(os.path.join(self.dir.name, "state", "login.json"))
        self.alerts, self.sleeps = [], []
        self.driver = HttpDriver(self.sso.base)

    def flow(self, creds=GOOD, on_sleep=None, polls=3):
        def sleep(s):
            self.sleeps.append(s)
            if on_sleep:
                on_sleep(len(self.sleeps))
        return LoginFlow(self.driver, self.store, self.alerts.append, lambda: creds, sleep, duo_wait_polls=polls, poll_seconds=1)

    def test_full_path_waits_for_duo_then_trusts_device(self):
        result = self.flow(on_sleep=lambda n: self.sso.approve_duo() if n == 2 else None).run()
        self.assertEqual(result, "logged_in")
        self.assertEqual(len(self.alerts), 1)  # exactly one "approve Duo" alert
        self.assertTrue(self.sso.server.trusted)
        self.assertEqual(self.sso.login_posts, 1)
        self.assertFalse(self.store.load()["attempted"])  # episode cleared

    def test_bad_password_is_one_attempt_no_retry(self):
        result = self.flow(creds=("test-user", "wrong")).run()
        self.assertEqual(result, "bad_credentials")
        self.assertEqual(self.flow(creds=("test-user", "wrong")).run(), "skipped_one_attempt_per_episode")
        self.assertEqual(self.sso.login_posts, 1)
        self.assertEqual(len(self.alerts), 1)

    def test_duo_timeout_no_second_attempt_and_still_one_alert(self):
        self.assertEqual(self.flow(polls=2).run(), "duo_timeout")
        self.assertEqual(self.flow().run(), "skipped_one_attempt_per_episode")
        self.assertEqual(self.sso.login_posts, 1)
        self.assertEqual(len(self.alerts), 1)  # one alert per episode, never repeated

    def test_attempt_is_persisted_before_credentials_are_sent(self):
        seen = {}
        def creds():
            seen["attempted"] = self.store.load()["attempted"]
            return GOOD
        LoginFlow(self.driver, self.store, self.alerts.append, creds, lambda s: None, duo_wait_polls=1, poll_seconds=1).run()
        self.assertTrue(seen["attempted"])

    def test_credential_values_never_leak(self):
        flow = self.flow(creds=("secret-user-xyz", "secret-pass-xyz"))
        result = flow.run()
        everything = repr(result) + repr(self.alerts) + repr(self.store.load())
        with open(self.store.path) as handle:
            everything += handle.read()
        self.assertNotIn("secret-user-xyz", everything)
        self.assertNotIn("secret-pass-xyz", everything)

    def test_already_logged_in_skips_login(self):
        self.driver.jar.set_cookie(__import__("http.cookiejar").cookiejar.Cookie(
            0, "sid", "ok", None, False, "127.0.0.1", True, False, "/", True, False, None, False, None, None, {}))
        self.assertEqual(self.flow().run(), "already_logged_in")
        self.assertEqual(self.sso.login_posts, 0)

    def test_missing_credentials_do_not_use_up_the_attempt(self):
        def missing():
            raise KeyError("UBL_USER")
        with self.assertRaises(KeyError):
            LoginFlow(self.driver, self.store, self.alerts.append, missing, lambda s: None).run()
        self.assertFalse(self.store.load()["attempted"])  # nothing was submitted, so the episode's attempt is still available
        self.assertEqual(self.sso.login_posts, 0)


if __name__ == "__main__":
    unittest.main()
