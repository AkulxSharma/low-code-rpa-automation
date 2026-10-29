"""The secret scan must cover the whole repo wherever it is started from."""
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import sanitize_check  # noqa: E402


class SanitizeCheckTests(unittest.TestCase):
    def test_scans_every_tracked_file_from_a_subfolder(self):
        here = os.getcwd()
        self.addCleanup(os.chdir, here)
        os.chdir(os.path.join(ROOT, "scripts"))
        self.assertIn("reader/stats.py", sanitize_check.tracked_files())


if __name__ == "__main__":
    unittest.main()
