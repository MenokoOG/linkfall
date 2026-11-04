# 0002: Deterministic engine owns state, agents propose

Date: 2026-11-04 · Status: Proposed

## Context

LINKFALL runs a crew of LLM agents (Lodestar, Tactical, Systems, Comms, Vitals) on a CPU-only laptop with 16 GB of RAM. The models will be small local ones. Small models are unreliable at arithmetic, at keeping rules, and at staying consistent across turns.

Enemy signals are untrusted text, and they reach the Comms agent. A compromised agent must not be able to change the world directly.

We also need runs we can replay, so tests and evals give the same answer twice.

## Decision

We will split the system into four parts under `src/linkfall/`.

- **`engine/`** is a pure Python module. It does no network calls, reads no clock and touches no files. It takes a state, an action and a seeded random generator, and returns a new state plus a list of events.
- **`agents/`** holds one module per agent. Each agent receives a filtered view of the state and returns one proposal as JSON that matches a JSON Schema.
- **`validator/`** checks the schema first, then the rule preconditions (for example, overcharge needs heat at or below 60). It rejects with a reason and never repairs a proposal silently.
- **`eventlog/`** is an append-only SQLite table. Every proposal (accepted or rejected) and every engine event is a row. The current state is a fold over the events.

A run is identified by its seed, its scenario id and its event log. Replaying a log with the same seed must give an identical final state, and CI runs that check.

Models never write state, roll dice or compute damage. A model may return a short flavor text field. That field is shown to the player and never read by the engine.

## Alternatives considered

- **The model keeps world state in its context.** Considered because it is the simplest build. Rejected because state drifts, runs can't be replayed, and an injected message can rewrite the world. Revisit never for rules.
- **Engine as a separate service.** Considered for isolation. Rejected because it adds a container and a network hop for pure code. Revisit if a second front end needs the same engine.
- **A mutable save file instead of an event log.** Considered because it is easy. Rejected because replay and evals need history. Periodic snapshots are allowed later if replay gets slow.

## Consequences

- Pro: engine tests need no model, and run in milliseconds.
- Pro: a recorded log is an eval fixture, so a regression shows up as a diff.
- Pro: an injected instruction can only produce a proposal, and the validator and rules still apply.
- Con: more code than a narrated world, and agents get less freedom. Mitigation: the flavor text field keeps the fiction lively without touching state.
- Undo: hard. Every module depends on this split.

OWASP Top 10 for LLM Applications 2025, items that apply:

- LLM01 prompt injection: bounded by the validator and the engine rules.
- LLM05 improper output handling: schema and rule checks run before any model output is used.
- LLM06 excessive agency: agents have no tools. They only propose. How much autonomy Lodestar gets is decided in a later ADR.
- LLM10 unbounded consumption: per-call token and time budgets live in the supervisor (see 0003).

Items that don't apply yet: LLM08 (no vector store), LLM02 and LLM07 (no secrets or user data in prompts, and the prompts are public in the repo), LLM09 (the output is game fiction). LLM03 and LLM04 are handled in the model-selection ADR.

## Related

0003 (supervisor), 0004 (containers).
