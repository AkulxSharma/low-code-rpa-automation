"""Local browser driver for reader.login_flow (Playwright, headless Chromium, no cloud).

Maps whatever page is showing onto the four states the flow understands. It keeps a
persistent profile folder (gitignored) so the Duo "remember this device" cookie can
hold between runs. It never logs values, takes no screenshots and puts no page text
into errors, because a login page can echo what was typed.

The heuristics are deliberately generic. They are checked against the mock pages in
tests; they have NOT been checked against the real UB pages (no live login has run).
"""
import os

from reader.login_flow import DUO_CHALLENGE, DUO_TRUST, LOGGED_IN, LOGIN_FORM

USER_SELECTORS = "input[name=username], input#username, input[name=u], input[type=email], input[type=text]"
SUBMIT_SELECTORS = ("button[type=submit], input[type=submit], button:has-text('Log in'), button:has-text('Login'), "
                    "button:has-text('Sign in'), button:has-text('Submit'), button:has-text('Continue'), [role=button]:has-text('Log in')")
DUO_HINTS = ("duo push", "duo mobile", "check for a duo", "approve the login", "verify it's you")
TRUST_HINTS = ("is this your device", "trust this browser", "yes, this is my device", "remember this device")


ENTRY_LABELS = ("log in to ub learns", "log into ub learns", "login to ub learns", "log in with ub")


class BrowserDriver:
    def __init__(self, protected_url, profile_dir, headless=True, credential_hosts=None):  # headed (headless=False) lets Akul watch the first live try
        from playwright.sync_api import sync_playwright
        self.protected_url = protected_url
        # Hosts where credentials may be typed. Default: any host other than the protected site's own,
        # because the landing page there has an entry button and no credential form (found on the first live try).
        self.credential_hosts = tuple(credential_hosts) if credential_hosts else None
        self._pw = sync_playwright().start()
        os.makedirs(profile_dir, exist_ok=True)
        self.context = self._pw.chromium.launch_persistent_context(profile_dir, headless=headless)
        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()

    def describe(self):
        """Structure only, for diagnosing an unrecognised page: no page text, no query string, no screenshot."""
        from urllib.parse import urlsplit
        parts = urlsplit(self.page.url)
        count = lambda sel: self.page.locator(sel).count()
        return {"host": parts.netloc, "path": parts.path, "inputs": count("input"), "password_inputs": count("input[type=password]"),
                "buttons": count("button, input[type=submit]"), "iframes": count("iframe"), "forms": count("form")}

    def close(self):
        self.context.close()
        self._pw.stop()

    def _host(self):
        from urllib.parse import urlsplit
        return urlsplit(self.page.url).netloc

    def _credentials_allowed_here(self):
        host = self._host()
        if self.credential_hosts is not None:
            return host in self.credential_hosts
        from urllib.parse import urlsplit
        return host != urlsplit(self.protected_url).netloc

    def _click_entry_button(self):
        """The protected site's landing page needs a click on its login entry before any credential form exists."""
        sso = self.page.locator("a[href*='saml/initiate-login']")  # the real entry link, found by structure on the live page
        if sso.count() and sso.first.is_visible():
            sso.first.click(timeout=5000)
            self.page.wait_for_load_state("load")
            return True
        for label in ENTRY_LABELS:
            entry = self.page.locator("a, button, [role=button]").filter(has_text=label)
            if entry.count() and entry.first.is_visible():
                entry.first.click(timeout=5000)
                self.page.wait_for_load_state("load")
                return True
        return False

    def open_protected_page(self):
        self.page.goto(self.protected_url, wait_until="load", timeout=30000)
        if not self._credentials_allowed_here():
            self._click_entry_button()  # even when this host shows its own local form: credentials go to the SSO page only

    def _text(self):
        return (self.page.inner_text("body") or "").lower()

    def page_state(self):
        self.page.wait_for_load_state("load")
        text = self._text()
        # The "is this your device" page lives on the Duo host too, so it must be matched before the Duo-host rule.
        if any(h in text for h in TRUST_HINTS):
            return DUO_TRUST
        if "duosecurity" in self.page.url or any(h in text for h in DUO_HINTS):
            return DUO_CHALLENGE
        if self.page.locator("input[type=password]:visible").count():
            # A password field on the protected site's own landing page is not the login form: never type there.
            return LOGIN_FORM if self._credentials_allowed_here() else "unknown"
        return LOGGED_IN if self.page.url.startswith(self.protected_url.split("/", 3)[0] + "//" + self.protected_url.split("/")[2]) else "unknown"

    def submit_credentials(self, user, password):
        if not self._credentials_allowed_here():
            raise RuntimeError("refusing to type credentials on the protected site's own page")
        field = self.page.locator("input[type=password]:visible").first
        form = self.page.locator("form").filter(has=self.page.locator("input[type=password]:visible"))
        scope = form.first if form.count() else self.page
        scope.locator(USER_SELECTORS).first.fill(user)  # username box in the same form as the password box
        field.fill(password)
        buttons = self.page.locator(SUBMIT_SELECTORS + ":visible")
        if buttons.count():
            buttons.first.click(timeout=5000)
        else:
            field.press("Enter")  # no recognisable submit control: submit the form from the password field
        self.page.wait_for_load_state("load")

    def trust_device(self):
        for label in ("Yes, this is my device", "Trust this browser", "Trust browser", "Yes"):
            button = self.page.get_by_role("button", name=label)
            if button.count():
                button.first.click()
                self.page.wait_for_load_state("load")
                return
