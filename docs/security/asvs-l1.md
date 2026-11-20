# ASVS level 1 checklist

Standard: OWASP ASVS 5.0.0, level 1 (no accounts, no user data; ruling Q1). IDs and wording come from the project's `v5.0.0_release` CSV, read on 2026-11-04. The CSV lists 70 level 1 requirements.

Status is **planned** until a step ships the control with a test. Update this file in the same PR that does.

## Applies

| ID | Requirement in short | Control | Step | Status |
|---|---|---|---|---|
| v5.0.0-1.2.1 | Output encoding fits the context (HTTP, HTML) | Server sends JSON and event streams only so far; the UI will set text with `textContent` | 9, 10 | **done** for the API (`tests/test_api_runs.py`); UI in step 10 |
| v5.0.0-1.2.3 | Encode when building JavaScript or JSON content | No server-built script; JSON from `json.dumps` and FastAPI only (`api/sse.py`, `api/schemas.py`) | 9 | **done** |
| v5.0.0-1.2.4 | Parameterized database queries | Event log uses `?` placeholders, never string-built SQL; test stores SQL metacharacters as data. The range log (`range/store.py`) uses `?` placeholders too | 3, M3 | **done** (`tests/test_eventlog_store.py`, `tests/test_range_store.py`) |
| v5.0.0-1.3.2 | No `eval()` or dynamic code execution | Lint rule `S` (bandit set) in CI; the web code is scanned for `eval`, `new Function`, string timers and HTML sinks (`tests/web/static.test.mjs`) | 1, 10 | **done** |
| v5.0.0-2.1.1 | Documentation defines input validation rules | The input table is the docstring of `api/schemas.py` | 9 | **done** |
| v5.0.0-2.2.1 | Positive validation against allowlists | Strict pydantic models: enums, ranges, no extra fields, no "1" for 1 (`tests/test_api_security.py`). The range `target` is an enum and run ids match a fixed pattern (`tests/test_api_range.py`) | 9, M3 | **done** |
| v5.0.0-2.2.2 | Validation at a trusted service layer | The server validates every field; the policy, supervisor and engine validate again | 9 | **done** |
| v5.0.0-2.3.1 | Business flows in the expected order | Turn state machine; idempotency key per run and turn | 7, 9 | **done** (`tests/test_api_runs.py`: state machine, stale turn, repeated commit) |
| v5.0.0-3.2.1 | Browsers don't render content in the wrong context | CSP, `nosniff`, `frame-ancestors 'none'` on every response, including errors and rejected hosts (`api/security.py`). The range report holds model text, so it is served as an attachment with `nosniff` and is never rendered by this origin (`tests/test_api_range.py`) | 9, M3 | **done** |
| v5.0.0-3.2.2 | Text shown as text, via safe functions | Model and enemy text is set only through text nodes (`dom.js`); `tests/web/static.test.mjs` bans HTML sinks. A forged channel message displayed as plain text in the browser | 10 | **done** for all three slices and the range page; the event log builds its lines with text nodes and the same static test covers it. On the range page a stated value is marked by wrapping its own text node (`range-view.js`); after a live model run a line held only `b`, `mark` and `span` children |
| v5.0.0-3.4.2 | CORS allow-origin is fixed or allowlisted | No CORS headers are sent; Host allowlist (`TrustedHostMiddleware`) blocks DNS rebinding | 9 | **done** |
| v5.0.0-3.5.1 | Cross-origin requests to sensitive functions are validated | Custom `X-Linkfall-Request: 1` header, Origin must match Host, `Sec-Fetch-Site: cross-site` refused, on every POST, including the two range POSTs (`tests/test_api_range.py`) | 9, M3 | **done** |
| v5.0.0-3.5.3 | Sensitive functions use POST, not GET or HEAD | State changes are POST only; a GET on those routes returns 404 or 405 and changes nothing | 9 | **done** |
| v5.0.0-4.1.1 | Content-Type matches content, with charset | JSON and event-stream types checked by tests; static files checked in `tests/test_web_static.py`; the range report is `text/markdown; charset=utf-8` (`tests/test_api_range.py`) | 9, 10, M3 | **done** |
| v5.0.0-11.4.1 | Only approved hash functions | SHA-256 for the replay fingerprint (`engine/fingerprint.py`) | 2 | **done** |
| v5.0.0-13.4.1 | No `.git` metadata in the deployed app | `.dockerignore` excludes `.git`; `scripts/smoke.sh` checks the running image | 11 | **done** |
| v5.0.0-14.2.1 | No sensitive data in URLs | Run ids are 96 random bits (`secrets.token_urlsafe(12)`), carry no secret; nothing sensitive is sent at all | 9 | **done** |
| v5.0.0-15.1.1 | Documented remediation time frames for vulnerable components | Section below | 1 | **done** |
| v5.0.0-15.2.1 | No component past those time frames | Dependabot weekly; advisory check at each pin | 1 | **done** at pin time |
| v5.0.0-15.3.1 | Return only the required fields | Responses are built field by field; the generator's position is left out (`api/schemas.py`). The range sends item ids and labels, and a protected value only inside a reply that stated it (`tests/test_api_range.py`) | 9, M3 | **done** |

## Not applicable

| IDs | Reason |
|---|---|
| 6.x, 7.x, 9.x, 10.x | No accounts, sessions, tokens or OAuth |
| 8.1.1, 8.2.1, 8.3.1 | One local pilot, no roles. Any local process can call the API on 127.0.0.1; accepted for a localhost demo, and the bind is tested |
| 5.x | No file uploads. The model path comes from deployment config, not from a request |
| 12.1.1, 12.2.1, 12.2.2 | The `api` binds to 127.0.0.1 over HTTP and is not external facing. For the hosted copy see the section below |
| 3.3.1, 3.4.1 | No cookies; no TLS, so no HSTS |
| 1.2.2, 1.2.5, 1.3.1, 1.5.1 | No dynamic URLs from untrusted data, no OS command built from input, no WYSIWYG, no XML |
| 11.3.1, 11.3.2 | No encryption in the application |
| 14.3.1 | No authenticated client data |
| 4.4.1 | No WebSocket (ADR 0008 uses SSE) |

## Hosted copy (ADR 0012)

The hosted demo runs the same app inside the visitor's tab on Pyodide, served as static files by GitHub Pages. There is no server, no shared state and no model call. These rows say what changes for that copy; every other row above holds as written, because the tab runs the same routes and the same web code. Still level 1.

| ID | Hosted copy | Status |
|---|---|---|
| v5.0.0-1.3.2 | The page policy adds `'wasm-unsafe-eval'` so Pyodide can compile WebAssembly. That allows no JavaScript `eval`. The Python it runs comes from `linkfall.zip`, built from this repo and loaded from the same origin | **done** (`scripts/build_pages.py`, `tests/test_build_pages.py`) |
| v5.0.0-3.2.1 | Pages can't send headers, so the policy is a `<meta>` tag: the server's policy with `frame-ancestors` dropped (a meta tag can't carry it) and `'wasm-unsafe-eval'` added, read from `api/security.py` so the two can't drift. `nosniff`, `Referrer-Policy`, `X-Frame-Options` and the cross-origin policies don't apply. Framing is accepted: the page holds no session, secret or user data (ADR 0012). The range report is saved as a file made in the page and never rendered | **done** for the meta policy; header loss **accepted** |
| v5.0.0-3.4.2 | No server, so no CORS surface | **n/a** |
| v5.0.0-3.5.1 | No server state another origin could change. The in-tab app still runs the same check: the bridge passes the page's headers through and fixes Host, so a POST without `X-Linkfall-Request` gets 403 (`tests/test_browser_bridge.py`) | **done** |
| v5.0.0-12.1.1, 12.2.1, 12.2.2 | TLS is GitHub's. "Enforce HTTPS" has to be on for the site; its default isn't stated in the Pages docs read for the plan. Checked in the runbook after Pages is turned on | **planned** |
| v5.0.0-13.4.1 | The site is built only from `src/linkfall/web/` and the hash-checked runtime; the Pages upload skips dotfiles. No `.git` or source tree is published | **done** by construction (`scripts/build_pages.py`) |
| v5.0.0-15.2.1 | The pure wheels follow `requirements.txt`, so Dependabot covers them. Pyodide and its compiled packages are pinned in `pages/runtime.json`, which Dependabot doesn't watch: check advisories by hand at each Pyodide bump (runbook). None found on 2026-11-20 for 314.0.7 | **done** at pin time |

Supply chain, beyond the level 1 rows: every runtime file is checked against a committed SHA-256 before use, and a mismatch stops the build. The deploy workflow's actions are pinned to commit SHAs, with no permissions at the top level. The CI job `pyodide` runs the suite on the exact files that ship (`.github/workflows/ci.yml`, `.github/workflows/pages.yml`).

## Vulnerable component time frames (v5.0.0-15.1.1)

Proposed for Lawrence's ruling. Clock starts when an advisory is published for a version we ship.

| Severity (CVSS v4.0) | Fix or mitigate within |
|---|---|
| Critical | 7 days |
| High | 14 days |
| Medium | 30 days |
| Low | next regular update |

Library updates in general: Dependabot opens weekly PRs; patch and minor updates merge after the gates pass. New pins, direct and transitive, use releases at least 14 days old (`--exclude-newer`).
