# Failure path demo: an expired session

## The scenario

A daily check logs in to a portal and reads it. Overnight the session expires and the portal starts answering with a redirect to its login page. A naive job would either keep hammering the login (risking a lockout) or fail silently every run. The failure path in `reader/failure_path.py` does neither.

## What it does

| Situation | Behaviour |
|---|---|
| Redirect to a login URL, non-JSON where JSON is expected, or an "Authentication" error | Classified as an expired session. |
| A 5xx or other odd response | Treated as transient: retried up to 3 times in the same cycle, then reported as a transient failure. Never confused with an expired session. |
| First expired cycle | One alert is raised and the episode starts. |
| Later expired cycles | Skipped by backoff (1, 2, 4 then 8 hours, capped), no new alert, a dead-letter note records since when and until when. |
| A cycle that passes | The episode ends and the state resets, so the next expiry alerts again. |

Logging back in is not part of this module. A person, or the gated login flow in `reader/login_flow.py` (one attempt per episode, saved before submitting, a person approves the second factor), restores the session.

## How it is demonstrated

1. **Tests on a mock portal** (`harness/mock_portal.py`, `tests/test_failure_path.py`): invented pages on `127.0.0.1` cover each row of the table above, including recovery and a second episode.
2. **Replay on measured history** (`reader/replay.py`): the same state machine is run over the real cycle history with the timestamps the cycles actually had. The current numbers are in `docs/measured.md`: 51 cycles with exact times, 29 of them failed, which the guard turns into 6 alerts with 9 attempts skipped by backoff.
3. **Logged-out streak alert** (`reader/blind_alert.py`): a separate check that alerts once after 3 or more logged-out cycles in a row and treats an inconclusive probe as neutral.

## What it does not show

The replay shows how many alerts and skipped attempts the guard would have produced. It does not show that a real person responded faster, and no time-saved figure is claimed.
