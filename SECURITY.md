# Security policy

LINKFALL is a local demo. Version 1.0.0 is the only version, and fixes go to `main`. It has no accounts, holds no user data, and binds to `127.0.0.1`. It is not hardened for hosting on the internet.

## Reporting a problem

If the Security tab shows "Report a vulnerability", use it. That is GitHub's private vulnerability reporting, and it was not enabled when this file was last checked on 2026-11-15. If the button is not there, open an issue that says you have a security report and leave out the details. I'll reply with a private channel.

Please include what you found, the steps to reproduce it, and the version or commit. I'll aim to answer within 7 days. That's a goal, not a promise.

## What counts

In scope: the `api` and `model` containers, the event log and the range log, the agent contract and validator, the training range, and anything that lets a model or enemy-channel text change state or reach the internet.

Out of scope: story mode accepting forged orders at high link. That weakness is deliberate and labeled. The same attack must fail in `hardened` mode; if it doesn't, report it. Also out of scope: a Comms agent on the training range giving up a protected value. The three values are fictional and sit in the public source, and measuring that leak is what the range is for.

## Design stance

See `docs/adr/`. The short version:

- The engine owns state; agents only propose (ADR 0002).
- The model container has no route to the internet (ADR 0004). `scripts/smoke.sh` checks it on a running stack.
- Accepting a truce always needs the pilot's signature (ADR 0006).
- Nothing in the repo holds secrets. Model weights are fetched by `scripts/fetch_model.sh` and checked against a pinned SHA-256.
- Dependencies are pinned with hashes. The time frames for fixing a vulnerable one are in `docs/security/asvs-l1.md`.

Standards used for reviews: OWASP ASVS 5.0.0 (level 1, no accounts) and the OWASP Top 10 for LLM Applications 2025.
