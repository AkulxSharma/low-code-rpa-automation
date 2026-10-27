"""Entry point n8n calls for the UB Learns login flow (local runtime only).

Refuses to run unless data/LIVE_GO exists. That file is created only after Akul says go
(and has been told UB's acceptable-use rules for automated logins are unread). Without
it this script exits 3 before any browser starts or any network request is made.
Credentials come from the process environment (UBL_USER, UBL_PASS), loaded by run-n8n.sh.
Prints one JSON line: the result and whether an alert was written. Never prints values.
"""
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from reader.login_flow import LoginFlow, StateStore, env_credentials  # noqa: E402


def main():
    if not os.path.exists(os.path.join(ROOT, "data", "LIVE_GO")):
        loaded = bool(os.environ.get("UBL_USER") and os.environ.get("UBL_PASS"))
        print(json.dumps({"result": "not_authorised", "credentials_in_environment": loaded,
                          "detail": "data/LIVE_GO missing; no live login without Akul's go"}))
        return 0
    if not (os.environ.get("UBL_USER") and os.environ.get("UBL_PASS")):
        print(json.dumps({"result": "no_credentials_in_environment"}))
        return 0
    from reader.browser_driver import BrowserDriver
    url = os.environ.get("UBL_PROTECTED_URL", "https://ublearns.buffalo.edu/")
    def alert(message):  # written the moment it is raised, so a watcher can relay "approve Duo" while the flow waits
        with open(os.path.join(ROOT, "data", "alert-login.txt"), "a") as handle:
            handle.write(message + "\n")
        alerts.append(message)

    alerts = []
    open(os.path.join(ROOT, "data", "alert-login.txt"), "w").close()  # fresh alert file for this run
    driver = BrowserDriver(url, os.path.join(ROOT, ".browser-profile"), headless=os.environ.get("UBL_HEADED") != "1")
    try:
        flow = LoginFlow(driver, StateStore(os.path.join(ROOT, "state", "login.json")), alert, env_credentials, time.sleep)
        result = flow.run()
        if flow.diagnostic:
            with open(os.path.join(ROOT, "data", "login-diagnostic.json"), "w") as handle:
                json.dump(flow.diagnostic, handle)
    finally:
        driver.close()
    print(json.dumps({"result": result, "alert_written": bool(alerts), "diagnostic_written": bool(flow.diagnostic)}))
    return 0  # the outcome is in the JSON line; a non-zero exit would hide stdout from n8n


if __name__ == "__main__":
    sys.exit(main())
