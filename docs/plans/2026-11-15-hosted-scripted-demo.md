# Plan: scripted-only hosted demo and a no-model compose file

Date: 2026-11-15 · Branch for this plan: menokog-agent/hosted-demo-plan · Status: Proposed, nothing built

Serves the agentic architect goal: a link a reviewer can open without cloning anything.

## 0. Classify

**Production.** A stranger on the internet touches it. All eleven gates apply, and Gate 9 stops being N/A. Gate 11 is N/A for the hosted service with a reason: it makes no model call.

## 1. Goal

A visitor opens one HTTPS link and plays Cinder Ward and the training range against the scripted crew, on a host that costs nothing and can't be made to cost something. Locally, one command starts the same thing without the model container.

## 2. Discovery

Read on 2026-11-15, main at 196e2fe.

| Source | What it gave |
|---|---|
| `compose.yaml` | `api` hardcodes `LINKFALL_MODEL_URL` and waits on `model` with `depends_on: service_healthy`. There is no way to start `api` alone today. |
| `api/config.py` | `model_url=None` already means scripted only. `LINKFALL_ALLOWED_HOSTS` replaces the default list, it does not add to it. |
| `api/registry.py` | 20 runs at most. `_make_room` evicts a run only when it is over and idle. |
| `api/security.py` | Same-origin check compares the `Origin` netloc with the `Host` header. Security headers have no HSTS. |
| `api/app.py` | Middleware order and where a new one goes. `TrustedHostMiddleware` runs before the body limit. |
| `api/requestlog.py` | One log line per request: method, path, status, duration. No client address. |
| `api/routes_run.py`, `routes_range.py` | `/api/health` already reports `model: not_configured`. No route lists run ids. One range run at a time (409 when busy). |
| `range/runner.py`, `web/js/range-model.js`, `view.js` | With no model client the range leaves the model target out, and the console disables the Model crew radio. The only "not available" text says the server "is not answering", which is wrong for a demo that has no model by design. |
| `Dockerfile.api` | Binds port 8000. `HEALTHCHECK` calls `127.0.0.1`. Data goes to `/data`. |
| `scripts/smoke.sh` | 18 checks, 9 of them need the `model` container. |
| `docs/security/asvs-l1.md` | 12.1.1, 12.2.1, 12.2.2 and 3.4.1 are N/A "because the api binds to 127.0.0.1 over HTTP. Revisit before any hosted release". |
| ADR 0004 | "Revisit with an egress-blocking firewall rule if the project is ever hosted." |

Findings that shape the work:

- **The app already runs without a model.** The hosted half needs hardening and a deploy target. It needs no new product behavior.
- **Twenty abandoned runs lock everyone out.** A run that nobody finishes is never evicted, so the 21st `POST /api/runs` returns 429 until the process restarts. On localhost that is one person's problem. On a public host it is a one-request-per-run denial of service. This is the most important fix in the plan.
- **Setting the public hostname breaks the container health check.** `LINKFALL_ALLOWED_HOSTS=<public name>` drops `127.0.0.1`, and the Dockerfile `HEALTHCHECK` then gets a 400.
- **Client addresses are never logged**, and the plan keeps it that way.

### Hosting facts (pages fetched 2026-11-15, none carry a date)

| | Render, Free web service | Fly.io, shared-cpu-1x 256 MB |
|---|---|---|
| Price | $0. Hobby workspace "does not have a monthly fee" | $2.19 a month in iad or ewr. Bills under $5 are waived for a personal organization |
| Size | 0.1 CPU, 512 MB | 1 shared CPU, 256 MB |
| Idle | Spins down after 15 minutes with no traffic. Waking "takes about one minute" | Runs all the time, or stops and bills $0.15 per GB of rootfs a month |
| Disk | Ephemeral. No persistent disk on Free | Volume $0.15 per GB a month |
| Hours | 750 Free instance hours per workspace per month | Not capped |
| Card | Not stated as required. Without one, bandwidth overage suspends the Free service for the month | Required after a $1, 7-day trial |
| TLS | Managed certificates included; HTTP redirects to HTTPS | First 10 single-hostname certificates free |
| Rollback | To the two most recent deploys | Not read |
| Egress | Counts against an included amount. The number was not on the pages read | $0.02 per GB in North America and Europe, no free allowance stated |

Sources: render.com/docs/free, /docs/compute-plans, /docs/platform-features-by-plan, /docs/deploys, /docs/rollbacks, /docs/health-checks, /docs/web-services; docs.fly.io/about/pricing and fly.io/pricing.

Not verified: Render's paid prices and the Hobby bandwidth number (the pricing table did not load), whether a Free service builds from a Dockerfile (the Docker page does not exclude it), which proxy headers Render sends, and what Render's "DDoS protection" covers. The two Fly pages disagree on 512 MB and 1 GB prices; the 256 MB price matches on both.

## 3. Scope

Three PRs, so no single change touches more than four existing files.

**PR 1, local scripted stack**
- New: `compose.scripted.yaml`, `tests/web/` case for the new copy.
- Changed: `web/js/range-model.js` and `web/js/copy.js` (wording when no model is configured), `scripts/smoke.sh` (skip the model checks when told), `README.md`.

**PR 2, public-host hardening** (all off or inert on localhost)
- New: `api/ratelimit.py`, `tests/test_api_ratelimit.py`, `tests/test_api_proxy.py`.
- Changed: `api/config.py` (three settings), `api/app.py` (mount the limiter), `api/registry.py` (idle eviction), `api/security.py` (HSTS when hosted).

**PR 3, deploy target and records**
- New: `docs/adr/0012-scripted-only-hosted-demo.md`, `render.yaml`, `scripts/smoke_hosted.sh`, `docs/runbooks/hosted-demo.md`.
- Changed: `docs/security/asvs-l1.md`, `README.md`, `CHANGELOG.md` (each PR adds its own entry), `Dockerfile.api` only if the port has to follow `$PORT`.

Not in scope: hosting the model, accounts, a custom domain, persistent storage, analytics.

## 4. Modularity check

- `api/ratelimit.py` has one job and follows the pure ASGI middleware pattern in `security.py` and `requestlog.py`. About 70 lines.
- Idle eviction stays inside `Registry._make_room`, which already owns eviction.
- Nothing in `engine/`, `supervisor/`, `policy/`, `validator/` or `range/` changes.
- Names follow the repo: `compose.scripted.yaml` beside `compose.yaml`, `smoke_hosted.sh` beside `smoke.sh`, ADR 0012 after 0011.

## 5. Approach

**Local half.** A second compose file with `api` only: same image, same hardening, same loopback port, no `LINKFALL_MODEL_URL`, no `depends_on`. Command: `docker compose -f compose.scripted.yaml up`.

Why a file and not a Compose profile: putting `model` behind a profile changes the default. `docker compose up` would stop starting the model, and the README's one command and the 18-check smoke run would both change. A second file leaves version 1 alone. The cost is about 15 duplicated lines. Next check at build time: whether `extends` can reuse the `api` block without inheriting `depends_on` on Compose v5.5.1.

**Hosted half.** Render Free web service, built from `Dockerfile.api`, described in `render.yaml` with auto-deploy off, the health check on `/api/health`, and three variables: `LINKFALL_ALLOWED_HOSTS`, `LINKFALL_HOSTED=1`, `PORT=8000`.

Why Render Free over Fly: the bill is $0 by plan and not by waiver, and Free has no path to a charge. Overuse suspends the service. For a public demo that anyone can hammer, a hard stop is the right failure. The cost is the cold start: a reviewer who arrives after 15 quiet minutes waits about a minute. The README link says so. If that wait turns out to lose readers, Fly at 256 MB is the fallback and needs only a `fly.toml`.

**Hardening, in order of need.**
1. Idle eviction: a run untouched for 15 minutes can be evicted when the registry is full. The log keeps it, so replay still works.
2. Rate limit: a token bucket per client address, in memory, on `POST` routes only. Proposed: 10 new runs and 120 other POSTs per address per minute. Over the limit returns 429 with `Retry-After`. A cap on open event streams per address (proposed 4).
3. HSTS header when `LINKFALL_HOSTED=1`.
4. The health check keeps working: loopback hosts always stay on the allowlist.

Why hand-written and not `slowapi`: it would add two packages (`slowapi`, `limits`) to a hashed lockfile for one counter, and the repo already writes its middleware by hand. `slowapi` is the alternative if the bucket grows past one file.

## 6. Data and security

**Data.** No new data. The rate limiter holds client addresses in memory, drops them after a minute idle and never logs them. The SQLite logs sit on an ephemeral disk and vanish on every restart or spin-down, so a shared run link stops working. The page says that. No secrets exist; `render.yaml` holds none.

**Trust boundaries (STRIDE, real threats only).**
- **Internet to Render's proxy to `api`.** Denial of service: run flooding, stream hoarding, registry lockout. Controls: rate limit, stream cap, idle eviction, the Free tier's hard stop. Spoofing: a forged `X-Forwarded-For` to dodge the limit. Control: take the address from the proxy's own hop only, and confirm Render's header format before trusting it. Tampering: cross-site POST. Control: the existing header, Origin and `Sec-Fetch-Site` checks, tested behind a proxy.
- **Visitor to visitor.** Information disclosure: reading another visitor's run. Control: run ids are 96 random bits and no route lists them. A leaked link shows a scripted game and nothing personal.
- **`api` to the internet.** ADR 0004's open item. The code makes no outbound call; on Render there is no firewall rule to add. ADR 0012 records the residual risk.

**ASVS.** Level 1 still: no accounts, no user data. Rows that come due in `docs/security/asvs-l1.md`: v5.0.0-12.1.1, v5.0.0-12.2.1, v5.0.0-12.2.2 (TLS, met by Render's proxy, evidenced by the hosted smoke run) and v5.0.0-3.4.1 (HSTS). v5.0.0-3.5.1 gets a second test behind a proxy. v5.0.0-3.3.1 stays N/A (no cookies). I have not re-read the ASVS CSV for an anti-automation row at level 1; that is a check in PR 3.

**Dependencies.** None added.

## 7. Failure behavior

| Call | Timeout | Retry | What the caller sees |
|---|---|---|---|
| Browser to `api` on a cold start | Render holds the request about a minute | none | A slow first load. The README warns of it |
| SQLite write | existing behavior | none | 500 with a request id, as today |
| Rate limit exceeded | n/a | client waits | 429, `Retry-After`, and the existing error banner |
| Registry full after eviction | n/a | none | 429 "too many runs in progress", as today |
| Free hours or bandwidth used up | n/a | none | Render suspends the service until the month ends. The README link goes dead and the local path still works |
| Model call | n/a | n/a | Never made. A forced `crew: model` returns 503, as today |

## 8. Edge cases

1. **Forged `X-Forwarded-For`.** Only the address the proxy appended counts. Test with a two-entry header.
2. **Health check through the allowlist.** Loopback hosts stay allowed when `LINKFALL_ALLOWED_HOSTS` is set. Test both the Docker health check path and Render's check, which sends the `onrender.com` host.
3. **Restart mid-run.** The visitor's run id returns 404. The console already handles "no such run"; confirm the message reads right for a hosted visitor.
4. **Many visitors behind one address** (a campus, a VPN). They share one bucket. The limits are set high enough for a classroom and the 429 message says to wait.
5. **`Origin` with a port or a scheme change at the proxy.** The check compares netloc with `Host`. Test `https://name.onrender.com` against a forwarded `Host` of `name.onrender.com`.
6. **Scripted compose file with a stale volume from the model stack.** Same volume name, same schema, so old runs replay. State it in the README.

## 9. Tests

- `tests/test_api_ratelimit.py`: under the limit passes, over it returns 429 with `Retry-After`, the bucket refills, GETs are not limited, two addresses don't share a bucket, the stream cap holds.
- `tests/test_api_proxy.py`: same-origin check with proxy headers, forged forwarded header, HSTS present only when hosted, loopback always allowed.
- `tests/test_api_runs.py` (added cases): 20 idle runs, the 21st succeeds after the idle window and fails before it; an evicted run still replays.
- `tests/web/`: the no-model wording for the range and the crew radio.
- `scripts/smoke.sh` with the scripted file: the 9 checks that don't need the model.
- `scripts/smoke_hosted.sh <url>`: HTTPS answers, HTTP redirects, HSTS present, foreign Host refused, POST without the header refused, a scripted run starts and ends, health says `not_configured`.

## 10. Steps

1. ADR 0012 as Proposed, for your ruling. It fixes the host, the limits and the residual risks before any code.
2. PR 1: `compose.scripted.yaml`, the wording, the smoke flag, README.
3. PR 2a: idle eviction in the registry, with tests.
4. PR 2b: `api/ratelimit.py`, config, HSTS, proxy tests.
5. Measure on a 0.1 CPU, 512 MB container locally (`docker run --cpus 0.1 --memory 512m`): memory at rest, turn latency, bytes written per run.
6. PR 3: `render.yaml`, `smoke_hosted.sh`, the runbook, the ASVS rows, README.
7. You create the Render service and deploy. I run `smoke_hosted.sh` against the URL and report.
8. Run the gates on every PR: `ruff`, `mypy`, `coverage run -m pytest -m "not integration" && coverage report`, `node --test tests/web/*.test.mjs`, `docker compose config -q` for both files.

## 11. Production DoD plan

| # | Gate | Artifact |
|---|---|---|
| 1 | Correctness | The test files in section 9; coverage stays at or above 80% (98% today) |
| 2 | Failure behavior | Section 7, copied into the ADR |
| 3 | Observability | Existing request log. SLIs: `/api/health` success and p95 of `POST .../commit`. SLO proposed after step 5's numbers, over 30 days, excluding cold starts |
| 4 | Security | ADR 0012 threat lines, the ASVS rows, the two new test files, the hosted smoke output |
| 5 | Data | N/A: no schema change, and hosted data is throwaway by design |
| 6 | Accessibility | New wording only. Contrast and focus are unchanged; the new notice gets a contrast number |
| 7 | Performance | Step 5's numbers against a budget set in the ADR |
| 8 | Documentation | ADR 0012, README, runbook, CHANGELOG |
| 9 | Deploy and rollback | `render.yaml` with auto-deploy off. Rollback trigger: any `smoke_hosted.sh` failure after a deploy, or `/api/health` failing 3 checks in a row. Rollback is Render's "Rollback to this deploy", yours to press |
| 10 | Human gate | You review each PR and do the deploy |
| 11 | AI components | N/A hosted: no model call. Local model path is unchanged |

## 12. Open questions for Lawrence

1. **Host.** Render Free with a one-minute cold start, or Fly at 256 MB with a card on file? I recommend Render Free.
2. **Compose shape.** A second file (`compose.scripted.yaml`), or a profile that changes what `docker compose up` does? I recommend the file.
3. **Limits.** 10 new runs and 120 other POSTs per address per minute, 4 open streams, 15-minute idle eviction. Accept as proposed, or wait for step 5's numbers?
4. **Hostname.** `linkfall.onrender.com` if it is free, or a custom domain? A custom domain is spend and a DNS change.
5. **README wording** for the link: it must say scripted only, cold start, and that runs are wiped.
6. **ADR 0004's egress note.** Accept the residual risk on Render, or does that block hosting?

## Self-check

Fit 4, SOLID 4, error handling 4, modularity 5. First draft put everything in one PR that touched nine existing files; I split it into three and moved idle eviction to its own step because it is the fix that matters most.
