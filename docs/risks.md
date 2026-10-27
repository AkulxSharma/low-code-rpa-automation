# Risks and limits

- **Automated logins may break an institution's rules.** Logging in to a university or employer system with a script can violate its acceptable-use policy. Read the policy for any system you point this at before you run the live login. The live login is off by default and refuses to run without a local gate file (`data/LIVE_GO`).
- **Duo or any second factor is a person's job.** After the password the identity provider asks for a push that only a person can approve. The login flow raises one alert per episode and waits a bounded time. Until a "remember this device" cookie holds, a fully unattended run is not possible, and this repo does not claim one.
- **Account lockout.** A wrong password can count toward a lockout. The flow makes one attempt per expiry episode, persists that attempt before submitting, and never retries.
- **Credentials stay local.** `run-n8n.sh` parses `UBL_USER` and `UBL_PASS` from an owner-only file (mode 600) into the process environment. They are never sourced, echoed, stored, logged or written to a workflow export. A pre-push hook and `scripts/sanitize_check.py` scan for them.
- **Real page selectors are heuristics.** They were tuned on one live login page and are checked only against mock pages in tests. A site redesign will break them; the flow then stops on an unknown page and writes a structure-only diagnostic (host, path, element counts, no text).
- **Typing guard.** The browser driver refuses to type credentials on the protected site's own host and only types on the single-sign-on host. This was added after a first live try showed the landing page has its own local form.
- **Timestamps reveal when sessions ran.** Published statistics are bucketed to the month and contain counts and timings only.
- **Small n.** Percentiles are over a few dozen runs from one account over a few days. Treat them as a measurement, not a benchmark.
- **No hours-saved claim.** The manual check was never timed.
