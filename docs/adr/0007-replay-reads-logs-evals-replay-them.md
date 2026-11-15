# 0007: Replay reads logs, evals replay them

Date: 2026-11-04 · Status: Accepted, with the "As built" note below as the record of what shipped

## Context

ADR 0002 makes the event log the source of truth and says replay never calls a model. This ADR sets how replay works, how tests and evals use it, and what runs in CI.

A small model on a CPU varies between runs. A test that re-queries it gives different answers on different days, so it can't gate a merge. The demo prototype replayed by regenerating scripted proposals, which only works because its agents are scripts.

The top failure modes we planned for are injected orders, schema breaks, CPU latency, the memory ceiling, replay breaking on model variance, and paraphrased leaks the detector misses. Each needs a test layer that can catch it.

## Decision

We will treat a run as its log and test it in five layers.

**Replay.** `eventlog/replay.py` reads the run header (seed, mode, scenario, schema version) and the rows in order: proposals, selector outputs, supervisor decisions, pilot actions and engine events. It re-runs the engine from the seed using the logged decisions and pilot actions. It compares each regenerated engine event with the logged one and compares a final fingerprint, a SHA-256 over the canonical JSON of the final state and the ordered event list. The first difference is reported as FAIL with the row number. Replay never repairs a log. A test double that raises on any model call is wired into every replay test.

**Counterfactual replay.** To compare `story` and `hardened` on the same injection log, replay re-runs policy and engine over the logged proposals under the other mode. The selector's logged output belongs to the original mode, so counterfactual replay uses the rules-only selector from ADR 0006 and labels the result "counterfactual, rules selector". It shows what the policy allows. It doesn't show what Qwen would have picked.

**Layers:**
1. Unit tests for engine, validator and policy (no model, milliseconds).
2. Contract tests with fake agents, run against rules agents and fake LLM agents (ADR 0005).
3. Golden-log replay in CI: recorded logs for a story run, a hardened run and an injected-order run. CI replays them and compares fingerprints. A rule change that alters a golden log is a visible diff, and the author refreshes the log on purpose.
4. Model evals, run locally and on demand, not gating CI because the model varies. They run the injection set against live Qwen at temperature 0 and record schema-valid rate, rule-valid rate and policy outcomes in both modes. Results are saved with the model checksum and thread count.
5. A latency and memory benchmark script that records tokens per second, per-call latency, turn time and peak RSS at the pinned thread count. The turn budget is p95 at or under 40 seconds (plan, open question 2).

**NIST AI RMF 1.0 and AI 600-1.** The eval report maps each check to a function: Map (the failure list), Measure (layers 3 to 5), Manage (hardened mode, fallbacks, the pilot signature). The mapping file lands with the eval harness. The framework text was not reopened for this ADR; the mapping is checked when it is written.

**Leak detection.** The M3 training range uses a plain pattern check for stated values. It can't see paraphrases or a confirm or deny. The report says so, and a human reviews the transcript.

## Alternatives considered

- **Re-query the model on replay.** Considered because it is the simplest. Rejected because model variance would fail tests at random. Revisit never.
- **Snapshot final state only, with no event comparison.** Considered because it is cheap. Rejected because a matching final state can hide a wrong path. Revisit never.
- **Gate CI on live model evals.** Considered to catch prompt regressions. Rejected because CI has no model and results vary. Revisit if a stable seed-and-temperature setup shows zero variance across 20 runs.
- **A hosted eval framework.** Considered for dashboards. Rejected: offline requirement and one more dependency. Revisit never for the core loop.

## Consequences

- Pro: CI is deterministic and fast, and a regression shows as a diff.
- Pro: the same logs serve as tests, evals and demo material.
- Con: golden logs go stale when rules change on purpose. Mitigation: a script refreshes them, and the PR shows the diff.
- Con: counterfactual replay doesn't predict live model behavior. Mitigation: layer 4 measures the live model, and the label says which is which.
- Undo: moderate. The log format is the contract; changing it needs a schema version bump.

OWASP Top 10 for LLM Applications 2025: LLM01 and LLM06 are tested by the injected-order logs in both modes. LLM05 is tested by the schema and precondition failures in the contract suite. LLM10 is tested by the benchmark and the timeout paths.

## As built (2026-11-15)

What shipped, checked against the code on this date. Where this note and the Decision differ, the note is the record.

**Built as decided**
- Replay (`eventlog/replay.py`). It re-runs the engine from the seed and the logged decisions, compares each engine event and the final fingerprint, and reports the first bad row. It never repairs a log.
- Layers 1 to 3. Four golden logs sit in `tests/golden/` and CI replays each one to its recorded fingerprint (`tests/test_golden_replay.py`).
- The leak check for the training range, with its limits stated on the page and in the report (ADR 0009).

**Built differently**
- Replay takes a store and a run id and nothing else, so it has no path to a model. The test double that raises on a model call (`NoModelClient`) exists and is used in one supervisor test. It is not wired into every replay test, because replay has no model seam to wire it to.
- Layer 5. `scripts/benchmark.py` reports turn time, the model's thread count and the model container's peak memory. It does not report tokens per second or per-call latency. The 40 s budget is still proposed.

**Not built**
- Counterfactual replay. No code re-runs a logged run under the other mode.
- Layer 4, the model eval harness. There is no injection set run against the live model in both modes, and no saved results with the model checksum and thread count. What exists instead: four integration tests that need a live server (`tests/test_integration_model.py`, run with `-m integration`), and one recorded training range run against the model on 2026-11-15.
- The NIST AI RMF mapping file.

## Related

0002 (engine and log), 0003 (supervisor), 0005 (agent contract), 0006 (policy), 0008 (UI), 0010 (model).
