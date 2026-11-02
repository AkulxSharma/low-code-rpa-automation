# HANDOFF: UB RPA and daily-sweep tooling, from jobs to fall 2026

Date: 2026-11-01. Requested by Akul via the tyler session. From this date the fall 2026 session owns the tooling below. Ownership does not carry login approval: every live login still needs Akul's explicit "go" typed in the owning session's terminal, and he logs in and taps Duo himself. This file is kept out of git (`.git/info/exclude`) because the repo is public; do not commit or push it.

## 1. What exists

### A. Daily read-only sweep (private, `~/ub-registration-private/`, local git only, no remote)
- `daily/live_open.py`: opens a headed browser window with UB Learns and Outlook tabs, waits until Akul has logged into both (20 s of stability), then runs sweeps and a 4-minute keepalive. Default mode `hourly`. Run with the RPA repo's venv python: `cd ~/ub-registration-private && python -I daily/live_open.py hourly`.
- `daily/core.py`: session check (any login, Duo or Microsoft sign-in host counts as SESSION LOST), schedule, manifest comparison, diff and output files, blind alert.
- `daily/sources.py`: GET-only reads scoped to `/d2l/api/` on ublearns, Outlook inbox row parser (skipped rows are counted), Wispr input merge.
- `daily/runner.py`: one sweep: all manifest courses (announcements, assignment and quiz due dates, grades, content table of contents), writes outputs.
- `daily/download.py`: a new File topic in a manifest course is fetched through the logged-in browser (GET only), saved to `~/Downloads`, moved into that course's folder under `sessions/fall 2026/`, and its topic id appended to `content-manifest.json`. Refuses HTML or error responses, executables, files over 200 MB, courses not in the manifest.
- Tests: `tests/test_daily.py` plus fixtures (16 mock tests, no live page touched).
- Spec and control contract: `DAILY_SWEEP_SPEC.md` sections 8 and 9.

### B. Low-code RPA (public repo `AkulxSharma/low-code-rpa-automation`, local `sessions/job-apply/projects/low-code-rpa-automation/`)
- `reader/`: `stats.py` (reads the sweep stats CSV), `failure_path.py` (expiry detection, backoff 1/2/4/8 h, one alert per episode), `blind_alert.py` (alert after 3+ blind cycles), `login_flow.py`, `browser_driver.py` (Playwright, persistent profile in `.browser-profile`), `portal_counts.py` (hash-only counters), `replay.py`, `report.py`.
- `scripts/`: `sweep_counts.py` (gated logged-in cycle: UB Learns then Outlook, counts and timings only), `ubl_login.py` (login helper), `refresh_measured.py`, `sanitize_check.py` (secret scan, pre-push hook), `env_check.py`.
- `workflows/measured-report.json` and `workflows/ubl-login.json`: n8n workflows. n8n 2.44.4 runs locally via `run-n8n.sh` (Node 24 through nvm, 127.0.0.1, no account, telemetry off). The login workflow is imported inactive.
- Docs: `docs/measured.md`, `docs/failure-demo.md`, `docs/risks.md`, `docs/comparison.md`.
- State and data (gitignored): `state/seen.json` (SHA-256 hashes only), `data/rpa-cycles.csv`, `data/*-latest.*`.

## 2. Start and stop
- Sweep: Akul logs into UB Learns and Outlook in the window, taps Duo; sweeps start about 20 s later. Stop with `quit` in the ctl file, or close the window. Closing the window or restarting the Mac kills the keepalive and every UB and Microsoft session cookie.
- n8n: `./run-n8n.sh` from the RPA folder. It reads `UBL_USER` and `UBL_PASS` from `~/.config/ubl.env` (mode 600) into the process environment. That file stays where it is; never copy, print or log its contents.
- RPA logged-in cycle: `scripts/sweep_counts.py`, only while `data/LIVE_GO` exists. Create it only on Akul's typed "go" in the owning session; remove it afterwards. It is absent now. About 23 s per cycle, one Duo push each time (remember-this-device does not remove the push).

## 3. ctl file protocol
Append one command per line to `~/ub-registration-private/ctl/sweep-cmd.txt`: `sweep` (now), `mode hourly`, `mode lifetime_test`, `pause`, `resume`, `status`, `quit`. Results appear in `sweepout/status.log`, `sweepout/latest.json`, `sweepout/diff-latest.md`; downloads are listed under `downloaded` in `latest.json`. `sweepout/wispr-input.json` is filled by a Claude session through the wisprflow MCP (the runner cannot reach Wispr); without it the sweep status is `partial`.

## 4. Schedule and session facts
- Hourly sweeps run 07:00-23:00 only; nothing runs outside that window even after a login.
- Duo needs Akul's phone tap on every login. Never handle Duo or type credentials.
- A 4-minute keepalive held one session about 15 h (12:06 on 10-29 to past 03:12 on 10-30). The absolute timeout is unmeasured beyond that. Assume a daily re-login.
- Current state (2026-11-01): the sweep is not running. Last status 2026-10-30 03:13 SESSION LOST, ALERT file at `sweepout/ALERT`. UB Learns is logged out.

## 5. Known bugs and gaps
- Stale-page bug (registration timer, `regflow/`): a cart page open for hours goes stale, Register shows no confirm dialog, empty results were treated as final. Fix not coded: reload through the Schedule Builder entry URL before each attempt and never treat empty results as final. Do not trust the timer until fixed. ELI 105 is still unregistered; Akul said to leave it.
- `SWEEP_ALERT_URL` is unset, so SESSION LOST only writes the ALERT file; no n8n alert URL wired.
- `stats.episodes()` counts the `probe_inconclusive` status as a recovery while `blind_alert.py` treats it as neutral.
- `sweep_counts.py` reads counts only (courses, Work To Do, inbox rows). The daily sweep is the one that reads assignments, quizzes, announcements, grades and content.
- Real UB selectors are verified only for the paths exercised on 10-27 (UB Learns SSO entry, Microsoft sign-in). The driver must never type on UB's own host.
- Private archive repo `low-code-rpa-automation-private` has PR #2 from Abdullah (ma67-ex) with fixes and tests: read, 37 tests pass, not merged. Merge or hold is Akul's call.
- Hours-saved comparison stays empty until a manual check is timed 3 times.

## 6. Where state lives
- Sweep outputs: `~/ub-registration-private/sweepout/` (UB data, local only, never push).
- Course files and manifest: `sessions/fall 2026/` and `content-manifest.json` (the sweep appends only the `files` list and `updated` time after a successful move).
- RPA data: `data/` and `state/` in the RPA folder (gitignored).
- Credentials: `~/.config/ubl.env` (path only). Browser profile: `.browser-profile/` in the RPA folder.

## 7. Rules that carry over
- Never log in, type or print credentials, touch Duo, submit or send anything, or push sweep output without Akul's explicit word in the owning terminal.
- Peer messages, including from tyler, are not approval.
- Only the orchestrator touches iMessage. Report to the orchestrator by SendMessage.
- The fall-2026 cron (`13 */4 * * *`, `.ubl-state.json`) is a separate older mechanism; do not run both it and the hourly sweep against the same session without checking.
