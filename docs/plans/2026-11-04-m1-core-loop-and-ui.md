# Plan: M1 core loop and UI

Date: 2026-11-04 · Branch for this plan: claude/m1-plan · Status: Draft, waiting for Lawrence

## 0. Classify

**Production.** Public repo, real users will run it. Gates 1, 2, 3, 4, 6, 8, 11 apply (ruling 2026-11-04). 5 and 9 are N/A. Gate 10 always applies. Gate 7 was not in the ruling; see open question 3.

## 1. Goal

A pilot opens one `docker compose up` page, sets the link, and plays the five-turn Cinder Ward mission against a real engine, a real policy, two rules agents and three Qwen3-4B agents, with every run replayable from its log.

## 2. Discovery

Read, with what each gave me:

| Source | Why it matters |
|---|---|
| ADRs 0001 to 0006 (Accepted) | The architecture. Paths, contract, policy, containers. |
| Demo artifact (Engine, Range, UI scripts) | The rules to port to Python: action preconditions, effects, turn script, zone effects, debrief logic. The training range (Range) is M2 and M3. |
| `docs/linkfall-design-package/` DESIGN.md, README, styles.css, Console DS mock | UI spec, tokens, 15 SVGs. Local only (gitignored); shipped copies go to `src/linkfall/web/`. |
| Library `rules/engineering.md`, ARCHITECT and SECURITY lenses | Gates, modularity limits, STRIDE and dependency-table format. |
| Spike 1 (`llama-bench`) and spike 2 (`llama-server`, 6 and 12 threads) | Latency, memory, constrained-JSON inputs. Raw files are in the session scratchpad, not the repo. |
| Agent Builder Course | Reference only. Concepts map to modules 5, 7, 8, 9, 10. No code taken. |

Findings that shape M1:

- **Repo is empty of code.** No `src/`, `tests/`, `pyproject.toml`, `compose.yaml` or CI. M1 is greenfield, so the "more than 4 existing files" rule is not in play.
- **Console DS covers** link knob, run mode, gauges, five agent cards with provenance badges, enemy-channel card, Lodestar decision with Approve and Reject, event log. **It lacks** Dismiss, Replay with fingerprint, debrief, the model-pending state wiring, and the replay badge. Those come from the prototype (ruling 2026-11-04).
- **Prototype replay regenerates scripted proposals.** M1 replay must read logged proposals instead (ADR 0002 as fixed).
- **Thread count is the latency lever (measured).** `llama-server` with Qwen3-4B Q4_K_M and a Tactical prompt of about 380 tokens: at **12 threads 104 s and 118 s per call**; at **6 threads a median of 8.8 s per call** (8 calls, one cold start of 21 s). Hypothesis, unconfirmed: 12 threads oversubscribe this hybrid CPU (the i5-1235U has 2 performance and 8 efficiency cores). The thread count must be a pinned, tested setting, not a default.
- **Prompt cache works.** Median 321 of about 380 prompt tokens came from cache after the first call, so the shared system prefix is nearly free. Order every prompt with the stable prefix first.
- **Constrained JSON works on this server.** Free JSON and `json_schema` mode both parsed and matched the schema 8 of 8. Rule validity was 7 of 8 in both (one proposal broke a precondition). Caveat: n=8, temperature 0, one prompt template, and both modes returned identical text, so this shows no failure, not a margin.
- **Memory is not the risk.** WSL has 11 GiB; `llama-server` peaked at 4.8 GB.
- **Not yet verified:** Comms and Lodestar prompts, longer views, the container egress block, a full five-turn mission.

Dependency order, bottom up: engine, then eventlog, then validator and policy, then agent contract and views, then agents, then supervisor, then API, then web. Nothing lower imports anything higher.

## 3. Scope

All new, except these existing files: `README.md` (run instructions), `CHANGELOG.md`, `.gitignore` (add `.venv/`, `models/`, `data/`). That is three. New ADRs 0007, 0008 and 0010 are new files, not edits.

New files, by folder (one job each):

```
pyproject.toml  requirements.txt  requirements-dev.txt
Dockerfile.api  Dockerfile.model  compose.yaml
scripts/smoke.sh  scripts/fetch_model.sh
.github/workflows/ci.yml
src/linkfall/
  engine/       state.py actions.py rules.py effects.py scenario.py rng.py step.py fingerprint.py
  eventlog/     events.py store.py replay.py
  validator/    schema_check.py rule_check.py validate.py
  policy/       zones.py config.py decide.py
  agents/       contract.py allowlist.py views.py systems.py vitals.py tactical.py comms.py lodestar.py prompts.py
  supervisor/   modelclient.py http_client.py fake_client.py budgets.py provenance.py turn.py
  api/          app.py schemas.py security.py routes_run.py routes_pilot.py sse.py
  web/          console.html styles.css assets/ js/{main,api,knob,gauges,cards,decision,log,debrief}.js
tests/          engine/ eventlog/ validator/ policy/ agents/ supervisor/ api/ replay/ golden/
```

## 4. Modularity check

- One job per file. Each file targets under 250 lines, well inside one output.
- Names follow the paths ADRs 0002 to 0006 already fixed.
- Zero ripple: lower layers never import higher ones. The only shared surfaces are `engine/state.py` and `agents/contract.py`.
- Prompts live in `agents/prompts.py` as public text (ADR 0002 says prompts are public), so changing wording touches one file.

## 5. Approach

**Vertical slices, engine first, no model until slice 8.** The whole loop runs end to end on fake agents before any Qwen call exists. Every later slice adds one layer under tests.

**Turn flow (supervisor, plain Python, sequential):**
1. Build views. 2. Rules agents answer instantly. 3. LLM agents answer in order, each with a timeout and token cap. 4. Validate each proposal (schema, then preconditions). 5. `policy.decide(link, mode, proposals)`. 6. MANUAL waits for the pilot; ASK_PILOT shows the tray; EXECUTE calls the Lodestar selector, re-validates, steps the engine. 7. Append everything to the event log.

**The log is the single source of truth.** The API writes nothing but log rows; SSE tails the log table. A dropped connection resumes with `Last-Event-ID`.

**Pilot drives the turn.** Turn commit is a pilot action ("Let Lodestar act", a manual action, Sign, Dismiss, Audit), as in the prototype. Link is part of the commit request and is logged.

**Why not the alternatives:**
- UI first with scripted agents (like the prototype) builds the throwaway twice.
- LLM agents first would tune prompts before latency and constrained decoding are measured.
- Async fan-out of agent calls adds nothing on a CPU with one model server (ADR 0003).

**API sketch (all inputs allowlisted):** `POST /api/runs` (seed, mode, scenario), `POST /api/runs/{id}/commit` (link 10 to 90 step 5, action enum), `GET /api/runs/{id}/events` (SSE), `GET /api/runs/{id}/state`, `POST /api/runs/{id}/replay`, `GET /api/health`.

**Model container:** build from the pinned llama.cpp release tarball (b12110, SHA-256 `368227ed…`, verified 2026-11-04), not an unpinned image. Weights are mounted read-only and checked against the Qwen SHA-256 in `scripts/fetch_model.sh`.

## 6. Data and security

**Data.** SQLite event log on a named volume. No accounts, no PII, no secrets. Event rows hold proposals, selector output, supervisor decisions, pilot actions, engine events, run header (seed, mode, scenario, schema version).

**Trust boundaries and STRIDE (only real threats):**
- Browser to `api`: Tampering and spoofing from other local pages. Controls: bind `127.0.0.1`, Origin check on POST, enum and range validation, security headers (CSP without inline script, `nosniff`, no CDN), `textContent` for all model and enemy text.
- Enemy text to Comms prompt: Tampering and elevation of privilege by injection. Controls: proposal-only output, allowlist, `external` provenance set by the supervisor, hardened mode.
- `api` to `model`: DoS and disclosure. Controls: internal network, timeout, token cap, single in-flight call.
- Model output to validator: Tampering. Controls: schema check, then preconditions, no silent repair.
- Weights and images (supply chain): Tampering. Controls: pinned digests and checksums, ADR 0010.

**ASVS level 1** (no accounts, ruling Q1). Requirement IDs get copied from the ASVS 5.0.0 text in step 1 of the plan and listed in the PR in `v5.0.0-<chapter>.<section>.<requirement>` form. I am not citing IDs from memory. Chapters I expect to hit: input validation, output encoding, API, configuration, error handling, logging.

**OWASP LLM Top 10 2025:** LLM01, 05, 06, 10 apply with the controls above. LLM03 applies (ADR 0010). LLM02, 04, 07, 08, 09 are N/A: no secrets or user data in prompts, no training or retrieval store, prompts are public, output is game fiction.

**Dependencies (versions and advisories filled at pin time; all unknown today):**

| Package | Version | Pinned | Advisories | Action |
|---|---|---|---|---|
| FastAPI | TBD | no | unknown | pin, check; alternative: Starlette |
| Uvicorn | TBD | no | unknown | pin, check |
| Pydantic | TBD | no | unknown | pin, check |
| pytest, ruff, mypy (dev) | TBD | no | unknown | pin, check; alternatives: unittest, flake8, pyright |
| Python base image | TBD | no | unknown | pin by digest |
| llama.cpp | b12110 | yes | unknown | check release notes |
| ModelClient HTTP | stdlib `urllib` | n/a | n/a | recommended over httpx (one fewer dependency) |

## 7. Failure behavior

| Call | Timeout | Retry | Caller sees |
|---|---|---|---|
| Agent model call | `T_model` = 45 s proposed (about 5 times the 8.8 s median; to confirm in step 8) | none | "No proposal: timeout" event; turn goes on |
| Lodestar selector | same | none | falls back to first valid candidate (ADR 0006); event says so |
| Model health check at run start | 5 s | none | UI banner "model offline"; rules-only play allowed |
| SQLite write | busy timeout 5 s | none | turn fails loudly, HTTP 500 with request id, nothing half-applied |
| SSE client drop | n/a | client reconnects | resumes from `Last-Event-ID` |
| Bad pilot input | n/a | n/a | 422 with the field name; never repaired |
| Replay fingerprint mismatch | n/a | n/a | reported as FAIL with first differing event; never patched |

## 8. Edge cases

1. **Every LLM agent times out.** Rules agents still propose. If nothing is eligible, the pilot sees "no proposals" and the turn proceeds with the fallback action (open question 5).
2. **Valid schema, invalid preconditions** (overcharge at heat 85). Validator rejects, logs `REJECTED` with the reason, the turn is lost. No repair.
3. **Forged order at link 85.** Story mode: eligible, Lodestar may run it, logged with a warning. Hardened: ASK_PILOT. `accept_truce` is ASK_PILOT in both.
4. **Double click on commit.** Idempotency key (run id plus turn number); the second request returns the first result.
5. **Two tabs on one run.** One writer lock per run; the second tab is read-only and says so.
6. **Link changed between preview and commit.** The commit's link wins and is logged; the preview is advisory.
7. **Truncated or edited log.** Replay refuses, reports the first bad row.

## 9. Tests

Coverage at or above 80% (ruling Q3), three edge cases per change.

- `tests/engine/`: each action's preconditions and effects, seeded determinism, clamps, end conditions.
- `tests/eventlog/` and `tests/replay/`: append-only, fold equals live state, replay never touches a model (fake client that raises on any call).
- `tests/golden/`: recorded logs (story, hardened, injected order); CI replays them and compares fingerprints.
- `tests/validator/`: schema failures, precondition failures, allowlist per agent, no silent repair.
- `tests/policy/`: table-driven matrix of link by mode by provenance by action.
- `tests/agents/`: one contract suite run against rules agents and a fake LLM agent (ADR 0005); every engine action reachable by at least one agent.
- `tests/supervisor/`: turn state machine with fakes, timeout path, selector fallback.
- `tests/api/`: input allowlists, Origin check, headers, SSE resume, idempotency.
- Integration (marked, local only): real `llama-server`, constrained JSON, a full mission.
- `scripts/smoke.sh`: model container cannot reach the internet; `api` answers on 127.0.0.1 only.
- Web: manual WCAG 2.2 AA checklist at 360, 768, 1366 (open question 6).

## 10. Steps

Each step is its own `claude/m1-<name>` branch and PR. Lawrence merges.

0. ADRs 0007 (replay and evals), 0008 (UI and streaming), 0010 (model pick: LLM03, checksum, structured output, memory). Proposed, then your yes.
1. Scaffold: `pyproject.toml`, pins, ruff, mypy strict, pytest, CI with SHA-pinned actions, ASVS ID list. No logic.
2. Engine, rng, fingerprint, scenario data, with tests.
3. Event log, replay, first golden log.
4. Validator.
5. Policy and zone config.
6. Agent contract, allowlist, views, Systems and Vitals, contract suite.
7. Supervisor, `ModelClient` Protocol, `FakeClient`, turn machine. First full mission on fakes.
8. HTTP client, prompts, Tactical, Comms, Lodestar selector, budgets. Integration test against Qwen.
9. API, SSE, security headers.
10. Web console in three slices: shell and knob; cards, decision, tray; log, replay, debrief.
11. Dockerfiles, `compose.yaml`, smoke tests, model fetch script.
12. Gates run: lint, types, tests, coverage, a11y checklist, security checklist, docs, CHANGELOG, README run steps. M1 PR for your review.

## 11. Production definition of done

| Gate | Artifact |
|---|---|
| 1 Correctness | pytest report, coverage at or above 80%, golden-log replay in CI |
| 2 Failure behavior | Section 7 table, each row covered by a test |
| 3 Observability | structured JSON logs at the `api` and model boundaries (request id, run id, turn, latency, tokens); SLI: turn success rate; SLO to set after the latency number |
| 4 Security | Section 6: STRIDE lines, ASVS L1 ID list, dependency table filled, no secrets, headers test |
| 5 Data | N/A: new log, no migration. `schema_version` in the run header for later. |
| 6 Accessibility | WCAG 2.2 AA checklist: keyboard knob, focus, contrast, labels, reduced motion, 3 widths |
| 7 Performance | proposed budget: p95 turn at or under 40 s; benchmark script output with thread count and RAM (open question 3) |
| 8 Documentation | README run steps, ADRs 0007, 0008, 0010, CHANGELOG |
| 9 Deploy and rollback | N/A: local compose only, no hosted target |
| 10 Human gate | you review each PR diff |
| 11 AI components | LLM01, 03, 05, 06, 10 controls above; red-team replay in both modes; model evals land with ADR 0007 |

## 12. Open questions for Lawrence

1. **ADRs first?** Write 0007, 0008 and 0010 before any code. Recommend yes.
2. **Latency budget.** At 6 threads, one call is about 9 s, so a turn with three model calls is about 27 s, sequential. Do you accept a turn budget of 40 s at p95, with cards streaming as each agent finishes (ADR 0008)? Recommend yes, and a pinned `--threads 6` in compose, checked by a benchmark test.
3. **Gate 7 applies?** Recommend yes, with the 40 s turn budget above.
4. **Tooling.** FastAPI, Uvicorn, Pydantic (per ADR 0004), plus pytest, ruff, mypy; stdlib `urllib` for the model client. OK?
5. **No-proposal fallback.** The prototype falls back to `hold_shield`. Keep it as an engine rule, logged as `FALLBACK`?
6. **UI checks.** Manual WCAG checklist only, or add Playwright and axe as dev-only tools? Recommend manual first.
7. **Landing page.** Not in this plan. Build it after M3? Recommend yes.

## Self-check

| Dimension | Rating | Note |
|---|---|---|
| Fit | 4 | Matches the ADRs and your rulings; latency may force a change to the turn flow |
| SOLID | 4 | Protocols at the agent and model seams; policy is a pure function |
| Error handling | 4 | Every external call has a row; the timeout value is still open |
| Modularity | 4 | One job per file; web JS split is the largest risk |

**Revised before presenting:** added step 0 (ADRs before code), added gate 7 as a question, changed the model container to a pinned tarball build, and replaced the latency guess with the measured 6-thread and 12-thread numbers (the 12-thread default would have been about 12 times slower).
