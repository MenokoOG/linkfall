# 0012: The hosted demo runs the engine in the browser

Date: 2026-11-15 · Status: Accepted

## Context

LINKFALL runs on one machine: `docker compose up` starts an `api` container and a model container, bound to `127.0.0.1` (ADR 0004). A reviewer has to clone the repo and fetch 2.5 GB of weights to see it. A link they can open would show the work to more people.

Two constraints shape the choice. The host has to be free with no way to become a bill. And the hosted copy must not weaken the demo's claim, which is that tested code decides what the lead agent may do.

A hosted `api` container is a public server. It needs a rate limit, a fix for the run registry (20 abandoned runs block every new one until restart), tests behind a proxy, TLS rows in the ASVS checklist and a rollback plan. The free server hosts read on 2026-11-15 either sleep (Render Free: 15 idle minutes, about a minute to wake), give $1 of credit a month (Railway Free) or require a card (Fly.io).

A spike on 2026-11-15 tested the other route: run the Python as it is, inside the browser, on Pyodide 314.0.8 (CPython 3.14.2 compiled to WebAssembly).

- Under Node 24.21.0, 530 of the repo's Python tests passed on Pyodide. 1 failed and 13 errored; those 14 start a subprocess or a socket server on a thread. `test_api_misc.py` was left out because it imports uvicorn. That run used Pyodide's own starlette 1.0.0 and anyio 4.13.0.
- In headless Chromium (Playwright build 1255), a static page served from a `/linkfall/` subpath loaded the runtime, started the FastAPI app in-process, played a scripted Cinder Ward run for all 5 turns, received 65 event-stream rows, and ran the range for 7 of 7 probes with a clean recheck. The page ran under a `<meta>` content security policy with 0 violations and 0 console errors.
- The page transferred 8.94 MB in 23 requests with gzip on (16.0 MB on disk). The app was ready in 3.3 s unthrottled, 6.8 s at 20 Mbps and 17.4 s at 5 Mbps. The longest gap between frames while a mission and a range run played was 93 ms.
- No file under `src/` was edited. Two patches at startup run threaded calls inline, because a browser tab has no threads.

## Decision

We will publish a scripted-only copy of LINKFALL as a static site on GitHub Pages. The engine, policy, supervisor, validator, event log and range run in the visitor's browser on Pyodide, through the same FastAPI app the server uses.

**One seam on each side.** A new `linkfall.browser.bridge` module turns a request into an ASGI call and applies the two thread patches. A new `local-backend.js` loads Pyodide and provides the fetch function and the event-stream class that `api.js` and `events.js` already accept. Nothing in `engine/`, `supervisor/`, `policy/`, `validator/`, `agents/`, `eventlog/` or `range/` changes.

**Packages.** Pure-Python packages ship at the versions in `requirements.txt`. Three things can't match the pins, because they are compiled: Python (3.14.2 against 3.13), pydantic (2.12.5 against 2.14.1) and pydantic-core (2.41.5 against 2.50.1). A CI job runs the Python suite on Pyodide with the exact set the site ships, so the hosted copy never runs code that CI didn't run on that runtime.

**The site serves its own runtime.** The build copies the Pyodide files and wheels into the site and checks each against a SHA-256 list committed in the repo. No CDN is used. The policy is `default-src 'self'; script-src 'self' 'wasm-unsafe-eval'` plus the existing directives.

**No model.** The hosted copy offers the scripted crew and the three scripted range targets. The page says so, and says how to run the model locally.

**Deploys are manual.** A workflow that runs only on `workflow_dispatch` builds the site from a chosen tag and publishes it. Lawrence runs it. Rollback is running it again on the previous tag.

**Budget.** First playable turn within 8 s at 20 Mbps on a cold load, measured in Chromium. The measured 6.8 s is the baseline.

## Alternatives considered

- **`api` container on Render Free.** Considered because it needs no new code path. Rejected because it sleeps and takes about a minute to wake, it needs the full public-server hardening, and one visitor can affect another. Revisit if a hosted model is ever wanted.
- **Railway Free or Fly.io.** Considered because they don't sleep by default. Rejected because Railway's free credit is $1 a month against $10 per GB of RAM, and Fly needs a card and has no free tier. Revisit never under the free constraint.
- **Port the engine to JavaScript.** Considered because the download would be small. Rejected because it is a second implementation that can drift from the tested Python. Revisit never.
- **Recorded replays as static JSON.** Considered because it is the least work. Rejected because the visitor can't move the link value. Revisit never.
- **A thin Python facade without FastAPI.** Considered because it trims the download. Rejected because it would need its own validation and JSON shapes, and FastAPI and starlette are about 0.3 MB of 16.0 MB. Revisit if the download budget is missed.

## Consequences

- Pro: no server. No rate limit, no shared state, no cold start, no bill, and one visitor can't affect another.
- Pro: the hosted copy runs the tested Python through the tested routes.
- Pro: ADR 0004's open item about `api` reaching the internet doesn't apply to the hosted copy. Nothing runs outside the visitor's tab.
- Con: an 8.94 MB first load. Mitigation: a loading state with progress, the budget above, and browser caching on later visits.
- Con: GitHub Pages can't send response headers. `X-Content-Type-Options`, `Referrer-Policy`, `frame-ancestors` and the cross-origin policies don't apply to the hosted copy, and a `<meta>` policy can't express `frame-ancestors`. Accepted: the page holds no session, no secret and no user data. The local server keeps every header.
- Con: a visitor can change the code in their own tab. Accepted and stated in the README: the hosted copy shows behavior; the local stack with the hash-checked log is the evidence.
- Con: runs live in the tab's memory and end on reload. The page says so and offers no shareable run link.
- Con: three compiled components differ from the pins. Mitigation: the CI job on Pyodide, and Pyodide held at its pinned version until the suite passes on a newer one.
- Con: a second runtime to keep working. Mitigation: it is confined to two files and one CI job.
- Undo: easy. Remove the Pages workflow and the two files. The server path is untouched.

Threats (STRIDE): tampering with the runtime files is bounded by the hash list and by workflow actions pinned to commit SHAs. Spoofing, denial of service and information disclosure between visitors have no surface, because there is no server.

OWASP Top 10 for LLM Applications 2025: not in play for the hosted copy. It makes no model call.

Not verified: Firefox and Safari, whether GitHub Pages compresses `.wasm` and `.whl` files, and the "Enforce HTTPS" default for the site. Each is a check in the build plan.

## Related

0004 (two containers on localhost; the hosted copy is a second way to run, and the local stack stays the reference), 0008 (the event stream, now also delivered in-process), 0010 (the model stays local only). Plan: `docs/plans/2026-11-15-hosted-scripted-demo.md`.
