"""Session-expiry failure path: detect, back off, alert once, dead-letter, never retry in a loop.

Pure logic with an injected clock and an injected fetch function, so it runs
the same against the test harness and on a replay of measured history. It never
logs in: a person restoring the session is outside this module.
"""
import json
import urllib.error
import urllib.request

BACKOFF_HOURS = (1, 2, 4, 8)
MAX_TRANSIENT_RETRIES = 3

OK = "ok"
EXPIRED = "auth_expired"
TRANSIENT_FAILED = "transient_failed"
SKIPPED_BACKOFF = "skipped_backoff"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def http_fetch(url):
    """Return (status, location, body). Redirects are reported, not followed."""
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(url, timeout=5) as res:
            return res.status, res.headers.get("Location"), res.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as err:
        try:
            return err.code, err.headers.get("Location"), err.read().decode("utf-8", "replace")
        finally:
            err.close()


def classify(status, location, body):
    """OK, EXPIRED (auth signal) or 'transient' (anything else that failed)."""
    if status in (301, 302, 303, 307, 308) and location and "login" in location.lower():
        return EXPIRED
    if status == 401:
        return EXPIRED
    if status >= 500:
        return "transient"
    try:
        parsed = json.loads(body)
    except ValueError:
        # HTML where JSON was expected is a login page only when the request itself succeeded;
        # a 404 or 429 error page says nothing about the session.
        return EXPIRED if 200 <= status < 300 else "transient"
    if isinstance(parsed, dict) and str(parsed.get("error", "")).startswith("Authentication"):
        return EXPIRED
    return OK if 200 <= status < 300 else "transient"


class Guard:
    """State for one source. `hours` is a float clock supplied by the caller."""

    def __init__(self):
        self.expired_since = None
        self.next_attempt = None
        self.backoff_step = 0
        self.alerted = False
        self.dead_letter = None
        self.alerts_sent = 0

    def run(self, fetch, now):
        if self.expired_since is not None and now < self.next_attempt:
            return {"result": SKIPPED_BACKOFF, "alert": False}
        verdict = "transient"
        for _ in range(1 + MAX_TRANSIENT_RETRIES):
            try:
                verdict = classify(*fetch())
            except OSError:  # URLError, timeouts and refused connections: a network blip is transient, not a crash
                verdict = "transient"
            if verdict != "transient":
                break
        if verdict == OK:
            self.expired_since = self.next_attempt = self.dead_letter = None
            self.backoff_step, self.alerted = 0, False
            return {"result": OK, "alert": False}
        if verdict == EXPIRED:
            if self.expired_since is None:
                self.expired_since = now
            wait = BACKOFF_HOURS[min(self.backoff_step, len(BACKOFF_HOURS) - 1)]
            self.backoff_step += 1
            self.next_attempt = now + wait
            self.dead_letter = {"skipped_since_hours": self.expired_since, "next_attempt_hours": self.next_attempt}
            alert = not self.alerted
            if alert:
                self.alerted = True
                self.alerts_sent += 1
            return {"result": EXPIRED, "alert": alert}
        return {"result": TRANSIENT_FAILED, "alert": False}
