"""Local-runtime login flow with a Duo step that only a person can approve.

Guardrails (all enforced and tested here):
- One login attempt per expiry episode. The attempt is persisted BEFORE credentials
  are submitted, so a crash or restart cannot cause a second attempt.
- No retries and no loops. A wrong password, a Duo timeout or an unknown page ends
  the episode's attempt; a person has to look.
- One alert per episode, including the "Duo push needed" alert.
- Credentials come from a callable (the live one reads the process environment). Their
  values are never stored, logged, returned or included in error text.
- When Duo needs approval, the flow waits (bounded) and ticks "remember this device"
  on approval. Until that cookie holds, this cannot run fully unattended.
No live portal is touched by this module; the driver is injected.
"""
import json
import os

LOGGED_IN = "logged_in"
LOGIN_FORM = "login_form"
DUO_CHALLENGE = "duo_challenge"
DUO_TRUST = "duo_trust_prompt"


class StateStore:
    """Tiny JSON file in the gitignored state/ folder."""

    def __init__(self, path):
        self.path = path

    def load(self):
        try:
            with open(self.path) as handle:
                return json.load(handle)
        except (OSError, ValueError):
            return {"attempted": False, "alerted": False}

    def save(self, state):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w") as handle:
            json.dump(state, handle)


def env_credentials():
    """Live credential source. Values stay in the process; callers must not log them."""
    return os.environ["UBL_USER"], os.environ["UBL_PASS"]


class LoginFlow:
    def __init__(self, driver, store, alert, get_credentials, sleep, duo_wait_polls=60, poll_seconds=5):
        self.driver, self.store, self.alert = driver, store, alert
        self.get_credentials, self.sleep = get_credentials, sleep
        self.duo_wait_polls, self.poll_seconds = duo_wait_polls, poll_seconds
        self.diagnostic = None

    def _alert_once(self, state, message):
        if not state["alerted"]:
            state["alerted"] = True
            self.store.save(state)
            self.alert(message)

    def _diagnose(self):
        describe = getattr(self.driver, "describe", None)
        if describe:
            self.diagnostic = describe()

    def run(self):
        state = self.store.load()
        self.driver.open_protected_page()
        page = self.driver.page_state()
        if page == LOGGED_IN:
            self.store.save({"attempted": False, "alerted": False})
            return "already_logged_in"
        if state["attempted"]:
            self._alert_once(state, "UB login still needed; one attempt was already made this episode, not trying again.")
            return "skipped_one_attempt_per_episode"
        if page != LOGIN_FORM:
            state["attempted"] = True
            self.store.save(state)
            self._diagnose()
            self._alert_once(state, "UB login page not recognised; no attempt made, please look.")
            return "unknown_page"
        state["attempted"] = True
        self.store.save(state)  # persisted before the credentials are read or submitted
        try:
            user, password = self.get_credentials()  # sanitize-ok: value comes from the injected callable
        except Exception:
            state["attempted"] = False  # nothing was submitted (e.g. UBL_USER unset), so the episode's one attempt is still unused
            self.store.save(state)
            raise
        self.driver.submit_credentials(user, password)
        del user, password
        page = self.driver.page_state()
        if page == LOGIN_FORM:
            self._alert_once(state, "UB login was rejected; not retrying. Check the saved password.")
            return "bad_credentials"
        if page == DUO_CHALLENGE:
            self._alert_once(state, "Duo push sent to your phone: approve it to finish the UB login.")
            for _ in range(self.duo_wait_polls):
                self.sleep(self.poll_seconds)
                page = self.driver.page_state()
                if page != DUO_CHALLENGE:
                    break
            else:
                self._alert_once(state, "Duo was not approved in time; not retrying.")
                return "duo_timeout"
        if page == DUO_TRUST:
            self.driver.trust_device()
            page = self.driver.page_state()
        if page == LOGGED_IN:
            self.store.save({"attempted": False, "alerted": False})
            return "logged_in"
        self._diagnose()
        self._alert_once(state, "UB login ended on an unexpected page; not retrying.")
        return "unexpected_page"
