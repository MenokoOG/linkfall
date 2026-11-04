# Security policy

LINKFALL is pre-release. There is no code and no tagged version yet, so nothing is supported for security fixes today.

## Reporting a problem

Use GitHub's private vulnerability reporting on this repo (Security tab, "Report a vulnerability"). I haven't confirmed that setting is enabled yet. Until it is, open an issue that says you have a security report and leave out the details. I'll reply with a private channel.

Please include what you found, the steps to reproduce it, and the version or commit. I'll aim to answer within 7 days. That's a goal, not a promise.

## What counts

In scope once code exists: the `api` and `model` containers, the event log, the agent contract and validator, and anything that lets a model or enemy-channel text change state or reach the internet.

Out of scope: story mode accepting forged orders at high link. That weakness is deliberate and labeled. The same attack must fail in `hardened` mode; if it doesn't, report it.

## Design stance

See `docs/adr/`. The short version:

- The engine owns state; agents only propose (ADR 0002).
- The model container has no route to the internet (ADR 0004). This is unverified until the scaffold smoke test runs.
- Accepting a truce always needs the pilot's signature (ADR 0006).
- Nothing in the repo holds secrets. Model weights are downloaded by hand and checksummed.

Standards used for reviews: OWASP ASVS 5.0.0 (level 1, no accounts) and the OWASP Top 10 for LLM Applications 2025.
