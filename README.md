# Low-code RPA: a measured daily check with a tested session-expiry path

A small automation project with a local, self-hosted n8n workflow on top of standard-library Python. It does two things:

1. **Measures** a real daily check that runs elsewhere (a multi-source sweep of a university learning portal, mailbox and notes) from its per-cycle statistics file: number of runs, duration percentiles, new items by type, and session-expiry episodes.
2. **Handles an expired login session correctly**: detect it, back off, alert once per episode, write a dead-letter note, and never retry in a loop. This is tested on a mock portal and mock single sign-on, and replayed on the measured history.

It also contains a gated, human-in-the-loop login flow and read-only counters for the portal and the mailbox. Those run on the owner's machine only.

## What is measured and what is a test harness

- **Measured:** every number in `docs/measured.md` comes from the statistics file of the live sweep, with the number of runs next to it. Only counts and timings are read. No course names, grades, message text, file names or credentials are in this repo, and dates are bucketed to the month.
- **Test harness:** `harness/` holds an invented portal and single sign-on with Duo-style pages on `127.0.0.1`. They exist to exercise the failure path and the login flow in tests. They produce no reported statistic.
- **Not claimed:** hours saved. The manual check was never timed, so `docs/comparison.md` is an empty template.

## How it fits together

```
sweep-stats.csv --> reader/stats.py --> reader/report.py --> n8n workflow --> report or alert file
                        |                      ^
                        +--> reader/replay.py -+   (replays the failure path on measured history)

expired session --> reader/failure_path.py   backoff 1, 2, 4, 8 h, one alert per episode, dead-letter note
                --> reader/login_flow.py     one attempt per episode, persisted before submit, Duo by a person
                --> reader/blind_alert.py    alert once after 3 or more logged-out cycles in a row

logged in --> reader/portal_counts.py        course, to-do and inbox counts as SHA-256 hashes, new-since-last-run
```

## Folders

- `reader/`: stats, failure path, replay, login flow, browser driver, blind alert, portal counts.
- `harness/`: mock portal, mock SSO, and an HTTP driver. Test code only.
- `workflows/`: exported n8n workflows without credentials. Replace `/path/to/` with your own paths after import.
- `scripts/`: gated entry points (`ubl_login.py`, `sweep_counts.py`), `refresh_measured.py`, `env_check.py` (presence and length only), `sanitize_check.py`.
- `tests/`: unit tests.
- `docs/`: `measured.md` (generated), `failure-demo.md` (the scenario and how it is shown), `comparison.md` (template), `risks.md`.

## Quick start

Python 3.9 or newer and nothing else for the core.

```bash
python3 -m unittest discover -s tests -t .
python3 -m reader.report path/to/sweep-stats.csv
```

The statistics file needs these columns: `ts_edt, ts_approx, duration_s, duration_approx, status, new_announcements, new_grades, new_due_dates, new_emails, new_wispr_meetings, auth_event, recovery, source`. The `source` column is never read or printed.

Browser tests and the live scripts need Playwright:

```bash
python3 -m venv .venv && .venv/bin/pip install playwright && .venv/bin/playwright install chromium
.venv/bin/python -m unittest tests.test_browser_driver tests.test_portal_counts
```

### n8n (optional, local)

`run-n8n.sh` starts n8n 2.x (Node 24) bound to `127.0.0.1` with telemetry, update checks and templates off. Import `workflows/measured-report.json` and set the paths. It runs the report and the logged-out streak check every four hours and saves a report or an alert file. `workflows/ubl-login.json` is a manual-trigger workflow that runs the gated logged-in cycle; it needs a person for the second factor, so it is not scheduled. No account and no cloud service is used.

### Live login (off by default)

`scripts/ubl_login.py` and `scripts/sweep_counts.py` do nothing unless the file `data/LIVE_GO` exists. They read `UBL_USER` and `UBL_PASS` from the environment (the launcher loads them from an owner-only file), type credentials only on the sign-in host, and wait for a person to approve the second factor. Read `docs/risks.md` first, and check the acceptable-use policy of any system you point them at.

## Safety design

- One login attempt per expiry episode, saved before the form is submitted, so a crash cannot cause a second attempt.
- No retry loops, one alert per episode, a bounded wait for the second factor.
- Credentials are never stored, logged, returned or put in error text. `scripts/sanitize_check.py` and a pre-push hook scan the tree for secrets, emails and course codes, including the live credential values if they are in the environment.
- Page contents are never recorded: diagnostics hold the host, path and element counts; portal counters keep SHA-256 hashes of link targets or labels.

## Results so far

See `docs/measured.md`, generated from real runs, with n beside every figure. Two full logged-in cycles on the real portal and mailbox each took about 23 seconds and needed one second-factor push; the second cycle found new inbox rows by hash comparison, so the seen-set diff works. Whether "remember this device" can remove the push is unconfirmed: it did not remove it in either cycle.

## Limits

Heuristics for the real login page were tuned on one site and are checked only on mock pages in tests. Percentiles come from a few dozen runs on one account. See `docs/risks.md`.

## License

MIT, see `LICENSE`.
