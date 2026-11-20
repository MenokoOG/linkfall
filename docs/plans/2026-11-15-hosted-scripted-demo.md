# Plan: hosted scripted demo on GitHub Pages, and a no-model compose file

Date: 2026-11-15 · Branch for this plan: menokog-agent/hosted-demo-plan · Status: Accepted (ADR 0012, 2026-11-19). PR 1 and PR 2 merged; PR 3 in progress

Serves the agentic architect goal: a link a reviewer can open without cloning anything.

## 0. Classify

**Production.** A stranger on the internet opens it. Gate 9 stops being N/A. Gate 11 is N/A for the hosted copy with a reason: it makes no model call.

## 1. Goal

A visitor opens one HTTPS link and plays Cinder Ward and the training range against the scripted crew. The Python engine, policy, supervisor and validator run inside the visitor's browser, so there is no server to pay for, attack or keep up. Locally, one command starts the same scripted stack without the model container.

## 2. Decision and the evidence for it

**Host: GitHub Pages. Runtime: the existing Python, unchanged, on Pyodide (CPython compiled to WebAssembly).**

The constraint is free, with no way to become a bill. Checked on 2026-11-15:

| Option | Free? | Why it lost or won |
|---|---|---|
| GitHub Pages + Pyodide | Yes. Static hosting, soft limits of 1 GB per site and 100 GB a month | No server, so no rate limit, no shared state, no cold start, no card |
| Render Free | Yes | Sleeps after 15 idle minutes and takes about a minute to wake. Needs the full public-server hardening. One person can lock out everyone (see findings) |
| Railway Free | $1 of credit a month | RAM is $10 per GB a month and CPU $20 per vCPU a month. A sleeping service's first request "may return a 502" |
| Fly.io | No free tier | $2.19 a month, waived under $5, card required |
| Recorded replays on Pages | Yes | The visitor can't move the link value, and that is the demo |

Sources: docs.github.com (Pages limits, What is GitHub Pages), render.com/docs/free and /docs/compute-plans, railway.com/pricing and docs.railway.com, docs.fly.io/about/pricing, pyodide.org package list. None of the pages carry a date.

**Spike, run 2026-11-15 in a scratch folder under Node 24.21.0 with Pyodide 314.0.8. Nothing from it is in the repo.**

| Question | Result |
|---|---|
| Does the code import and run on Pyodide? | Yes. Python 3.14.2, pydantic 2.12.5, pydantic-core 2.41.5, starlette 1.0.0, anyio 4.13.0, and fastapi 0.156.4 installed at the repo's own pin |
| Does the test suite pass there? | 530 passed, 1 failed, 13 errors, 5 deselected. The failure starts a subprocess. The 13 errors are `test_supervisor_http_client.py`, which starts a socket server on a thread. `test_api_misc.py` was left out because it imports uvicorn. None of those three paths run in the hosted copy |
| Can JavaScript drive the app with no server? | Yes. A JavaScript loop called the FastAPI app in-process: health said `not_configured`, a scripted Cinder Ward run played all 5 turns to an outcome in 671 ms, the event stream delivered 65 rows of all 8 kinds, replay returned 200, an unknown run returned 404, the range ran 7 of 7 probes on the reference target, and the recheck returned `ok` |
| What had to change? | Two patches at startup, because a browser tab has no threads: `asyncio.to_thread` and `anyio.to_thread.run_sync` run their function inline. No file under `src/` was edited |
| How big is the download? | 15.8 MB raw, 8.6 MB gzipped, for the runtime and wheels. Start-up took 4.0 s in Node with files on disk |

**Browser proof, run 2026-11-15 in headless Chromium (Playwright build 1255) against a static page served from a `/linkfall/` subpath with gzip on.**

| Question | Result |
|---|---|
| Does it run in a real browser? | Yes. A scripted mission played all 5 turns with 65 event-stream rows, and the range ran 7 of 7 probes with a clean recheck |
| Does the `<meta>` policy hold? | Yes. 0 policy violations and 0 console errors under `script-src 'self' 'wasm-unsafe-eval'` |
| How long until the app is ready? | 3.3 s unthrottled, 6.8 s at 20 Mbps, 17.4 s at 5 Mbps |
| How much is transferred? | 8.94 MB in 23 requests (16.0 MB on disk) |
| Does the page stay responsive? | The longest gap between frames while playing was 93 ms |

One finding changed the design: Pyodide's own anyio and typing-extensions are older than fastapi 0.156.4 and anyio 4.15.1 need. The site ships every pure-Python package at the repo's pin and takes only the compiled ones (Python, pydantic, pydantic-core) from Pyodide.

Not yet tested: Firefox and Safari, and whether GitHub Pages compresses `.wasm` and `.whl` files.

## 3. Discovery

Read on 2026-11-15, main at 196e2fe.

| Source | What it gave |
|---|---|
| `web/js/api.js` | `createApi(fetchFn)` already takes the fetch function. One seam for every request |
| `web/js/events.js` | `openEvents(..., { EventSourceCtor })` already takes the stream class. One seam for the event stream |
| `web/js/range-model.js` | `reportPath` builds a link to `/api/range/runs/<id>/report.md`. A static site can't answer it, so the browser build turns the report into a download made in the page |
| `web/index.html`, `range.html` | Every asset path starts with `/`. A project site lives under `/linkfall/`, so those paths break there |
| `api/security.py` | The security headers are sent by the server. GitHub Pages can't send custom headers |
| `api/routes_*.py`, `api/sse.py`, `supervisor/http_client.py` | Every use of threads: `asyncio.to_thread` in five places and FastAPI's thread pool for sync dependencies |
| `compose.yaml` | `api` hardcodes `LINKFALL_MODEL_URL` and waits on `model`. No way to start `api` alone |
| `range/runner.py`, `web/js/range-model.js`, `view.js` | With no model client the range drops the model target and the console disables the Model radio. The only wording says the server "is not answering", which is wrong when there is no model by design |
| `requirements.txt` | Pins differ from Pyodide's builds: pydantic 2.14.1, pydantic-core 2.50.1, starlette 1.9.0, anyio 4.15.1 |
| `api/registry.py` | A run nobody finishes is never evicted, so 20 abandoned runs block new ones until restart. Harmless in a browser, where each visitor has their own registry. Still a bug on a shared server; listed under "not in scope" |

## 4. Scope

Three PRs. No PR changes more than four existing files.

**PR 1, local scripted stack**
- New: `compose.scripted.yaml`.
- Changed: `web/js/range-model.js` and `web/js/copy.js` (wording when no model is configured), `scripts/smoke.sh` (skip the model checks when told), `README.md`.

**PR 2, the browser backend**
- New: `src/linkfall/browser/__init__.py`, `src/linkfall/browser/bridge.py` (the two thread patches, one request function, one event-stream function), `web/js/local-backend.js` (loads Pyodide, exposes a `fetchFn` and an `EventSource`-shaped class), `web/js/backend.js` (picks server or browser backend), `tests/test_browser_bridge.py`, `tests/web/local-backend.test.mjs`.
- Changed: `web/js/main.js` and `web/js/range-main.js` (take the backend from `backend.js`), `web/js/range-model.js` (report as a download in the browser build).

**PR 3, build, deploy and records**
- New: `scripts/build_pages.py`, `.github/workflows/pages.yml`, `scripts/test_pyodide.mjs`, `docs/adr/0012-hosted-demo-runs-in-the-browser.md`, `docs/runbooks/hosted-demo.md`.
- Changed: `.github/workflows/ci.yml` (one job runs the suite on Pyodide), `docs/security/asvs-l1.md`, `README.md`.

Each PR adds its own `CHANGELOG.md` entry.

Not in scope: hosting the model, a custom domain, saving runs across a page reload, analytics, and the registry eviction bug (worth its own small fix; it matters only if LINKFALL is ever put on a shared server).

## 5. Modularity check

- `browser/bridge.py` is the only Python file that knows about the browser. It imports `api.app` and nothing imports it. The server never loads it.
- `local-backend.js` is the only JavaScript file that knows about Pyodide. `api.js` and `events.js` don't change; they already accept the two things it provides.
- `backend.js` has one job: return `{ fetchFn, EventSourceCtor }` for the build it is in.
- `build_pages.py` assembles a `dist/` folder and changes nothing under `src/`.
- Nothing in `engine/`, `supervisor/`, `policy/`, `validator/`, `agents/`, `eventlog/` or `range/` changes.

## 6. Approach

**The browser calls the same FastAPI app, in-process.** `local-backend.js` hands each request to `bridge.py`, which builds an ASGI scope and awaits the app. Routes, validation, error shapes and the event stream are the ones the tests already cover.

Why this beats a hand-written JavaScript port of the engine: a port is a second implementation that can drift from the Python one, and the demo's claim is that code decides what the lead agent may do. Running the tested code keeps that claim true. Why it beats a thin Python facade that skips FastAPI: the facade would need its own request validation and its own JSON shapes. FastAPI and starlette add about 0.3 MB to a 15.8 MB download.

**The site serves the runtime itself, with no CDN.** `build_pages.py` copies the Pyodide files and wheels into `dist/` and checks each against a SHA-256 list committed in the repo. The page then loads scripts from its own origin only, and the content security policy stays `script-src 'self'` plus `'wasm-unsafe-eval'`.

**A CI job closes the version drift.** A new CI job runs the Python suite on Pyodide with the same packages the site ships. The hosted copy never runs code that CI didn't run on that runtime.

**Deploys are manual.** `pages.yml` runs only on `workflow_dispatch`, builds `dist/` from a chosen tag and publishes it with GitHub's Pages actions, pinned to commit SHAs. You press the button.

**Asset paths.** `build_pages.py` rewrites the leading `/` to relative paths in the two HTML files, the stylesheets (`url(/assets/...)`) and the scripts (`'/assets/...'` and `` `/assets/...` `` in `zones.js` and `cards-view.js`), and a test asserts no absolute path is left in `dist/`.

**Local half.** A second compose file with `api` only: same image, same hardening, same loopback port, no `LINKFALL_MODEL_URL`, no `depends_on`. Command: `docker compose -f compose.scripted.yaml up`. A Compose profile would change what plain `docker compose up` does and break the README's one command and the 18-check smoke run, so the model stack stays the default.

## 7. Data and security

**Data.** None leaves the browser. The SQLite logs live in the tab's memory and vanish on reload. No cookies, no storage, no accounts, no secrets. GitHub logs visitor addresses as it does for any Pages site; the README says so.

**Trust boundaries (STRIDE, real threats only).**
- **GitHub Pages to the visitor's browser.** Tampering with the runtime files in the supply chain. Controls: files are self-hosted, pinned by SHA-256 at build time, and the workflow's actions are pinned to commit SHAs with least-privilege `permissions`.
- **Visitor to their own tab.** A visitor can edit the code running in their browser and make the demo show anything. That affects only their own tab. The README states it: the hosted copy shows behavior, and the local stack with the hash-checked log is the evidence.
- **Visitor to visitor, and visitor to server.** No longer exist. There is no shared state and no server.

**What gets weaker, stated plainly.** Pages can't send response headers, so `X-Content-Type-Options`, `Referrer-Policy`, `frame-ancestors` and the cross-origin policies don't apply to the hosted copy. The policy moves to a `<meta>` tag, which can't express `frame-ancestors`. The page holds no session and no secret, so framing it gains an attacker nothing. The local server keeps every header.

**ASVS.** Level 1 still. Rows to update in `docs/security/asvs-l1.md`, each with a "hosted copy" note: v5.0.0-3.2.1 (headers: meta policy only), v5.0.0-3.4.2 and v5.0.0-3.5.1 (no cross-origin surface: no server), v5.0.0-12.1.1, v5.0.0-12.2.1, v5.0.0-12.2.2 (TLS is GitHub's). Next check: that "Enforce HTTPS" is on for the site; the Pages pages I read don't state the default.

**Dependencies.** No Python package added. Pyodide 314.0.7 is a new runtime artifact, pinned by hash in `pages/runtime.json`. 314.0.8 (published 2026-11-13) was too new for the 14-day rule on 2026-11-20; its changes are bug fixes, its `pyodide-lock.json` is byte-identical to 314.0.7's, and moving to it is a small PR after 2026-11-27. Advisory status, checked 2026-11-20: none for Pyodide in its repo's advisories or in GitHub's advisory database (npm and pip).

## 8. Failure behavior

| Call | Timeout | Retry | What the visitor sees |
|---|---|---|---|
| Download of the runtime (8.6 MB gzipped) | 60 s | one, on the visitor's click | A loading state with progress, then an error panel with a retry button and the link to run it locally |
| Browser without WebAssembly | n/a | none | A plain message and the local instructions |
| Python start-up error | n/a | none | The error panel, with the message in the console |
| A request to the in-page app | none needed; same thread | none | The same JSON errors as the server, through the existing banner |
| Model call | n/a | n/a | Never made. A forced `crew: model` returns 503, as today |
| Page reload mid-run | n/a | none | The run is gone. The page says runs last until reload |

## 9. Edge cases

1. **Site lives under `/linkfall/`.** Relative paths after the build, in HTML, CSS and JavaScript; a test fails on any absolute one.
2. **Report download.** No server route exists, so the page fetches the text from the in-page app and saves it as a file. The text is still never rendered by the page.
3. **Event stream on one thread.** The stream polls with `asyncio.sleep`, which yields to the browser. The spike showed rows arriving while turns were posted. The browser test in step 2 confirms the page stays responsive.
4. **A slow phone.** 8.6 MB and a few seconds of start-up. The loading state shows progress, and the budget is set from step 2's numbers.
5. **Run link shared with someone else.** It can't work, because the run is in one tab. In the browser build the page doesn't offer a shareable run link.
6. **Pyodide and the pins move apart.** The CI job fails first. The fix is to hold Pyodide at its pinned version until the suite passes on the new one.

## 10. Tests

- `tests/test_browser_bridge.py` (CPython): the request function returns the same status and body as the test client for a create, a turn, a commit and a 404; the event function delivers rows and stops on disconnect.
- `scripts/test_pyodide.mjs` in CI: the Python suite on Pyodide, minus the three files that need threads, sockets or a subprocess. Today's count is 530.
- `tests/web/local-backend.test.mjs`: the `fetchFn` and the event class behave like the real ones against a fake bridge; a load failure surfaces as an error and never as an empty success.
- `tests/web/static.test.mjs` (existing): covers the new `.js` files automatically.
- Build test: `dist/` holds no absolute asset path, every runtime file matches its hash, and the meta policy is present on both pages.
- Browser check on the built site with headless Chromium: both pages load, one mission plays to an outcome, one range run finishes, zero console errors, zero policy violations.

## 11. Steps

1. ADR 0012 as Proposed, for your ruling.
2. Browser proof before any feature work. Done 2026-11-15, passed; results in section 2.
3. PR 1: `compose.scripted.yaml`, wording, smoke flag, README. Merged 2026-11-19 (MenokoOG/linkfall#41).
4. PR 2: `browser/bridge.py`, `local-backend.js`, `backend.js`, with tests. Merged 2026-11-20 (MenokoOG/linkfall#42).
5. PR 3: `build_pages.py`, the CI job, `pages.yml`, ASVS rows, runbook, README. In progress on `menokog-agent/pages-build`. ADR 0012 already exists (Accepted 2026-11-19), so PR 3 doesn't add it.
6. You turn on Pages for the repo (source: GitHub Actions) and run the workflow. I run the browser check against the live URL and report.
7. Run the gates on every PR: `ruff`, `mypy`, `coverage run -m pytest -m "not integration" && coverage report`, `node --test tests/web/*.test.mjs`, `docker compose config -q` for both files.

## Progress and findings

**PR 1 (2026-11-19).** `compose.scripted.yaml` needed `!reset` for `environment` and `depends_on` and `!override` for `networks`: plain `extends` carries `depends_on` over and fails (Compose v5.5.1). `range-model.js` needed no change; with no model set up, the server leaves the model target out of the catalog.

**PR 2 (2026-11-20).** As built, and what PR 3 builds on:
- The switch is `<meta name="linkfall-backend" content="browser">` in the page. Without it, `backend.js` returns the server backend and never loads the Pyodide files.
- The page loads from `runtime/` beside it: `manifest.json` (`packages` for Pyodide's `loadPackage`, `wheels` to unpack into site-packages, `app`, the zip of `src/linkfall`), the wheels, and `pyodide/`. `build_pages.py` writes that layout.
- `bridge.start_page()` is the page's one Python call. It patches the two thread hand-offs and builds the app with both logs in memory.
- Pyodide 314 turns JavaScript `null` into `JsNull`, not `None`. The page passes `undefined` for absent values.
- `tests/web/static.test.mjs` now follows dynamic imports, a fourth changed file in PR 2.
- Browser check on a scratch build under `/linkfall/`: ready in 4.5 to 6 s unthrottled, a mission to SURVIVED with 55 streamed rows, replay and recheck pass, the report downloads, 0 console errors, 0 policy violations. The server build passed the same flow.
- Found: `zones.js` and `cards-view.js` build `/assets/` paths, so the build rewrites scripts and stylesheets as well as pages (section 6).

**PR 3 (in progress).**
- `scripts/build_pages.py` builds `dist/` (or `--out`). Pyodide's files come from jsDelivr and are checked against `pages/runtime.json`; each hash there matched both the npm package and the jsDelivr copy, and the wheel hashes match `pyodide-lock.json`. The pure wheels come from PyPI at the versions in `requirements.txt` and must match one of its hashes, so Dependabot's bumps reach the site. Downloads are cached in `.cache/pages/` by hash and checked again on use. The build refuses to write into the repo root, `src/` or a folder it didn't make.
- The meta policy is the server's policy with `frame-ancestors` dropped and `'wasm-unsafe-eval'` added to `script-src`, read from `api/security.py` so the two can't drift.
- `.gitignore` gains `/dist/` and `/.cache/`, a fifth existing file in PR 3.
- CI job `pyodide` (`.github/workflows/ci.yml`): builds the site, fetches pytest and its four dependencies hash-checked from `requirements-dev.txt` (`scripts/fetch_test_wheels.py`), and runs the suite on Pyodide with exactly the shipped files (`scripts/test_pyodide.mjs`). It checks that `linkfall` loads from the shipped zip, not `src/`. Locally on 2026-11-20: 540 passed under Python 3.14.2 and pydantic 2.12.5. Left out, each with its reason in the script: `test_api_misc.py` (uvicorn and a real socket), `test_supervisor_http_client.py` (socket server on a thread), one replay test (a subprocess), and `test_web_static.py` (the server serving `web/`, which the hosted copy leaves to Pages). The job runs on Node 24, the version it was checked on; `gates` stays on Node 22. Making `pyodide` a required check is a repo setting, so it's yours.
- Browser check on the real build, 2026-11-20, Pyodide 314.0.7: ready in 4.9 s (console) and 6.5 s (range) unthrottled, the same mission, replay, range, download and recheck results as PR 2, 0 console errors, 0 policy violations.

## 12. Production DoD plan

| # | Gate | Artifact |
|---|---|---|
| 1 | Correctness | The tests in section 10; coverage stays at or above 80% (98% today) |
| 2 | Failure behavior | Section 8, copied into the ADR |
| 3 | Observability | No server, so no service SLO. Errors show in the page and the browser console. Availability is GitHub's |
| 4 | Security | ADR 0012 threat lines, the hash list, the ASVS notes, the build test |
| 5 | Data | N/A: no schema change, and the hosted copy keeps nothing |
| 6 | Accessibility | The loading and error states get keyboard, focus, contrast and a live-region check. Everything else is unchanged |
| 7 | Performance | Budget set from step 2: time to first playable turn on a cold load, measured in Chromium with network throttling |
| 8 | Documentation | ADR 0012, README, runbook, CHANGELOG |
| 9 | Deploy and rollback | Manual `pages.yml` run from a tag. Rollback trigger: the browser check fails on the live URL. Rollback is running the workflow again on the previous tag |
| 10 | Human gate | You review each PR, turn on Pages and run the deploy |
| 11 | AI components | N/A hosted: no model call. The local model path is unchanged |

## 13. Open questions for Lawrence

1. **Go or no-go on this design.** It is my recommendation and the spike backs it.
2. **Turning on GitHub Pages** is a repo setting, so it is yours, at step 6.
3. **README wording** for the link. It has to say: scripted crew only, runs in your browser, and runs last until you reload.

## Self-check

Fit 5, SOLID 4, error handling 4, modularity 5. The first version of this plan chose Render Free and carried a rate limiter, eviction, proxy tests and a deploy runbook. A free static host with the real engine in the browser removes that whole class of work, so the plan was rewritten around it after the spike passed.
