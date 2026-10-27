"""TEST HARNESS ONLY. Drives the mock SSO over HTTP using the data-state marker.

The real driver (a local browser) is separate and not built here; it must map the
real pages to the same four states.
"""
import re
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar


class HttpDriver:
    def __init__(self, base):
        self.base = base
        self.jar = CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.last = ""

    def _get(self, path):
        with self.opener.open(self.base + path, timeout=5) as res:
            self.last = res.read().decode()

    def open_protected_page(self):
        self._get("/app")

    def submit_credentials(self, user, password):
        data = urllib.parse.urlencode({"u": user, "p": password}).encode()
        with self.opener.open(self.base + "/login", data=data, timeout=5) as res:
            self.last = res.read().decode()

    def page_state(self):
        if "duo_challenge" in self.last or "duo_trust_prompt" in self.last:
            self._get("/duo")  # poll the Duo page for the current state
        match = re.search(r'data-state="([a-z_]+)"', self.last)
        return match.group(1) if match else "unknown"

    def trust_device(self):
        self._get("/trust")
