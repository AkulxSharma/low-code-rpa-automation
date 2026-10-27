"""Pre-push sanitization and secret scan over tracked files.

Fails (exit 1) if a tracked file contains something that must not be in this repo.
Never prints a secret value: findings show file, line number and the rule name only.
Live credential values are read from the process environment (UBL_USER, UBL_PASS)
when present and searched for as literal strings; if they are not in the environment
only the pattern rules run.
"""
import os
import re
import subprocess
import sys

RULES = {
    "course-code": re.compile(r"\b(ECO|AI|PSC|MTH|CSE|EAS)[ -]?\d{3}\b"),
    "email-address": re.compile(r"[\w.+-]+@[\w-]+\.[A-Za-z]{2,}\b"),
    "password-assignment": re.compile(r"(?i)(pass(word)?|pwd|secret|token)\s*[=:]\s*['\"]?[^\s'\"]{6,}"),
    "local-path": re.compile(r"/Users/[A-Za-z0-9_.-]+/|/home/[A-Za-z0-9_.-]+/"),  # sanitize-ok
    "private-key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "long-secret-like": re.compile(r"(?<![\w])[A-Za-z0-9+/=]{40,}(?![\w])"),
}
# Invented test fixtures and rule definitions are allowed to match these.
ALLOW_FILES = {"scripts/sanitize_check.py", "harness/mock_sso.py", "tests/test_login_flow.py"}
ALLOW_LINE = re.compile(r"test-pass-not-real|secret-(user|pass)-xyz|#\s*sanitize-ok")


def env_value_rules():
    """The UB username is also scanned for as a whole word, from the environment only (never written here)."""
    user = os.environ.get("UBL_USER")
    return {"ub-username-like": re.compile(r"\b%s\b" % re.escape(user), re.I)} if user and len(user) >= 4 else {}


def tracked_files():
    out = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True).stdout
    return [f for f in out.splitlines() if f.endswith((".py", ".md", ".json", ".sh", ".csv", ".txt", ".gitignore"))]


def main():
    secrets = [v for v in (os.environ.get("UBL_USER"), os.environ.get("UBL_PASS")) if v and len(v) >= 4]
    findings = []
    rules = dict(RULES, **env_value_rules())
    for path in tracked_files():
        with open(path, errors="replace") as handle:
            for number, line in enumerate(handle, 1):
                if any(s in line for s in secrets):
                    findings.append((path, number, "live-credential-value"))
                if path in ALLOW_FILES or ALLOW_LINE.search(line):
                    continue
                for name, rule in rules.items():
                    if rule.search(line):
                        findings.append((path, number, name))
    for path, number, name in findings:
        print("%s:%d  %s" % (path, number, name))
    print("sanitize_check: %d finding(s); live values checked: %s" % (len(findings), "yes" if secrets else "no (not in environment)"))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
