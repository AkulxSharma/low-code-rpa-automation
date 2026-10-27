"""One logged-in cycle: UB Learns login, Outlook login, counts only. Local runtime, gated by data/LIVE_GO.

Writes data/sweep-counts-latest.json and appends one counts-and-timings row to data/rpa-cycles.csv.
Credentials come from the process environment (UBL_USER, UBL_PASS) and are typed only on the SSO host,
the Microsoft sign-in host or nowhere. No page text, no names, no screenshots.
"""
import csv
import json
import os
import re
import sys
import time
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from reader import portal_counts  # noqa: E402
from reader.login_flow import LoginFlow, StateStore, env_credentials  # noqa: E402

MS_HOST = "login.microsoftonline.com"
FIELDS = ["ts_edt", "duration_s", "status", "courses", "worktodo_items", "worktodo_new", "inbox_rows", "inbox_new", "duo_pushes"]


def alert(message):
    with open(os.path.join(ROOT, "data", "alert-login.txt"), "a") as handle:
        handle.write(message + "\n")


def outlook_login(driver, duo_polls=60):
    """Open Outlook; if Microsoft asks, sign in there (host-guarded), approve Duo by a person, accept 'stay signed in'."""
    page = driver.page
    page.goto(portal_counts.OUTLOOK_URL, wait_until="load", timeout=45000)
    page.wait_for_timeout(5000)
    pushes = 0
    if driver._host() == MS_HOST:
        user, password = env_credentials()  # sanitize-ok: values come from the process environment
        email = page.locator("input[type=email], input[name=loginfmt]")
        if email.count():
            email.first.fill(user if "@" in user else user + "@buffalo.edu")
            page.locator("input[type=submit], button[type=submit]").first.click(timeout=5000)
            page.wait_for_timeout(6000)
        pw = page.locator("input[type=password]:visible")
        if driver._host() == MS_HOST and pw.count():
            pw.first.fill(password)
            page.locator("input[type=submit], button[type=submit]").first.click(timeout=5000)
            page.wait_for_timeout(6000)
        del user, password
    for _ in range(duo_polls):
        host = driver._host()
        text = (page.inner_text("body") or "").lower()
        if "stay signed in" in text:
            page.get_by_role("button", name=re.compile("^yes$", re.I)).first.click(timeout=5000)
            page.wait_for_timeout(5000)
            continue
        if "duosecurity" in page.url or "duo" in host:
            if not pushes:
                pushes = 1
                alert("Duo push sent to your phone for Outlook: approve it.")
        elif host.startswith("outlook.") and page.locator("[role=option], [role=listbox]").count():
            return True, pushes
        page.wait_for_timeout(5000)
    return False, pushes


def main():
    if not os.path.exists(os.path.join(ROOT, "data", "LIVE_GO")):
        print(json.dumps({"result": "not_authorised", "detail": "data/LIVE_GO missing"}))
        return 0
    from reader.browser_driver import BrowserDriver
    started = time.time()
    open(os.path.join(ROOT, "data", "alert-login.txt"), "w").close()
    driver = BrowserDriver("https://ublearns.buffalo.edu/", os.path.join(ROOT, ".browser-profile"), headless=os.environ.get("UBL_HEADED") != "1")
    result = {"status": "error"}
    pushes = 0
    try:
        flow = LoginFlow(driver, StateStore(os.path.join(ROOT, "state", "login.json")), alert, env_credentials, time.sleep)
        login = flow.run()
        result["login"] = login
        if login in ("logged_in", "already_logged_in"):
            pushes += 1 if login == "logged_in" else 0
            state = os.path.join(ROOT, "state", "seen.json")
            page = driver.page
            page.goto(portal_counts.HOME_URL, wait_until="load", timeout=30000)
            page.wait_for_timeout(4000)
            course_hashes = portal_counts.courses(page)
            page.goto(portal_counts.WORKTODO_URL, wait_until="load", timeout=30000)
            page.wait_for_timeout(4000)
            work_hashes = portal_counts.worktodo(page)
            ok, outlook_pushes = outlook_login(driver)
            pushes += outlook_pushes
            inbox_hashes = portal_counts.inbox(page) if ok else []
            result.update(portal_counts.summarize(course_hashes, work_hashes, inbox_hashes, state))
            result["outlook"] = "ok" if ok else "not_reached"
            result["status"] = "ok_logged_in" if ok else "partial"
        else:
            result["status"] = "auth_expired" if login in ("skipped_one_attempt_per_episode", "bad_credentials") else "error"
    finally:
        driver.close()
    duration = int(time.time() - started)
    result["duration_s"] = duration
    with open(os.path.join(ROOT, "data", "sweep-counts-latest.json"), "w") as handle:
        json.dump(result, handle)
    path = os.path.join(ROOT, "data", "rpa-cycles.csv")
    new_file = not os.path.exists(path)
    with open(path, "a", newline="") as handle:
        writer = csv.DictWriter(handle, FIELDS, extrasaction="ignore")
        if new_file:
            writer.writeheader()
        writer.writerow({**result, "ts_edt": datetime.now().strftime("%Y-%m-%dT%H:%M"), "duo_pushes": pushes})
    print(json.dumps({k: v for k, v in result.items()}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
