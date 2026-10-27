"""Browser-driver tests on the mock SSO. Skipped when Playwright is not importable.

Run with the venv interpreter: .venv/bin/python -m unittest tests.test_browser_driver
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
try:
    import playwright  # noqa: F401
    HAVE_PW = True
except ImportError:
    HAVE_PW = False

from harness.mock_sso import GOOD, MockSSO  # noqa: E402
from reader.login_flow import LoginFlow, StateStore  # noqa: E402


@unittest.skipUnless(HAVE_PW, "playwright not installed in this interpreter")
class BrowserDriverTests(unittest.TestCase):
    def setUp(self):
        from reader.browser_driver import BrowserDriver
        self.sso = MockSSO().__enter__()
        self.addCleanup(self.sso.__exit__, None, None, None)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        from urllib.parse import urlsplit
        self.driver = BrowserDriver(self.sso.base + "/app", os.path.join(self.tmp.name, "profile"),
                                    credential_hosts=(urlsplit(self.sso.base).netloc,))
        self.addCleanup(self.driver.close)
        self.alerts, self.n = [], 0
        self.store = StateStore(os.path.join(self.tmp.name, "state", "login.json"))

    def test_real_browser_through_login_duo_and_trust(self):
        def sleep(_):
            self.n += 1
            if self.n == 1:
                self.sso.approve_duo()
            self.driver.page.goto(self.sso.base + "/duo")  # a person approving then reloading
        flow = LoginFlow(self.driver, self.store, self.alerts.append, lambda: GOOD, sleep, duo_wait_polls=5, poll_seconds=0)
        self.assertEqual(flow.run(), "logged_in")
        self.assertEqual(len(self.alerts), 1)
        self.assertEqual(self.sso.login_posts, 1)
        self.assertTrue(self.sso.server.trusted)

    def test_describe_is_structure_only(self):
        self.driver.page.goto(self.sso.base + "/login?token=SHOULD-NOT-APPEAR")  # sanitize-ok: invented marker
        info = self.driver.describe()
        self.assertEqual(info["password_inputs"], 1)
        self.assertNotIn("SHOULD-NOT-APPEAR", repr(info))
        self.assertNotIn("Sign in", repr(info))

    def test_bad_credentials_one_attempt(self):
        flow = LoginFlow(self.driver, self.store, self.alerts.append, lambda: ("x", "y"), lambda s: None, duo_wait_polls=1, poll_seconds=0)
        self.assertEqual(flow.run(), "bad_credentials")
        self.assertEqual(flow.run(), "skipped_one_attempt_per_episode")
        self.assertEqual(self.sso.login_posts, 1)

    def test_never_types_on_protected_sites_own_page(self):
        self.driver.credential_hosts = None  # default rule: the protected site's own host is not allowed
        self.driver.page.goto(self.sso.base + "/login")
        self.assertEqual(self.driver.page_state(), "unknown")
        with self.assertRaises(RuntimeError):
            self.driver.submit_credentials("u", "p")
        self.assertEqual(self.sso.login_posts, 0)


if __name__ == "__main__":
    unittest.main()
