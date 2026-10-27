"""Tests on invented HTML. Skipped without Playwright; run: .venv/bin/python -m unittest tests.test_portal_counts"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
try:
    from playwright.sync_api import sync_playwright
    HAVE_PW = True
except ImportError:
    HAVE_PW = False

from reader import portal_counts  # noqa: E402

WORK = ('<a href="/d2l/lms/dropbox/user/folder_submit_files.d2l?db=11">x</a><a href="/d2l/lms/dropbox/user/folder_submit_files.d2l?db=12">y</a>'
        '<a href="/d2l/le/5/discussions/topics/9/View">z</a><a href="/d2l/home">home</a>')
MAIL = '<div role=listbox><div role=option aria-label="alpha invented">a</div><div role=option aria-label="beta invented">b</div></div>'


@unittest.skipUnless(HAVE_PW, "playwright not installed in this interpreter")
class PortalCountsTests(unittest.TestCase):
    def setUp(self):
        self.pw = sync_playwright().start()
        self.browser = self.pw.chromium.launch()
        self.page = self.browser.new_page()
        self.addCleanup(self.pw.stop)
        self.addCleanup(self.browser.close)

    def test_counts_are_hashes_not_text(self):
        self.page.set_content(WORK + '<a href="/d2l/home/101">c</a><a href="/d2l/home/102">c</a>')
        self.assertEqual(len(portal_counts.worktodo(self.page)), 3)
        self.assertEqual(len(portal_counts.courses(self.page)), 2)
        self.assertNotIn("folder_submit", json.dumps(portal_counts.worktodo(self.page)))

    def test_inbox_rows_and_new_since(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "state", "seen.json")
            self.page.set_content(MAIL)
            first = portal_counts.inbox(self.page)
            self.assertEqual(portal_counts.new_since(path, "inbox", first), 0)  # baseline
            self.page.set_content(MAIL.replace("</div></div>", '</div><div role=option aria-label="gamma invented">c</div></div>', 1))
            second = portal_counts.inbox(self.page)
            self.assertEqual(portal_counts.new_since(path, "inbox", second), 1)
            self.assertEqual(portal_counts.new_since(path, "inbox", second), 0)  # already seen
            self.assertNotIn("invented", open(path).read())


if __name__ == "__main__":
    unittest.main()
