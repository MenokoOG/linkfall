# 0003: Plain Python supervisor, no agent framework

Date: 2026-11-04 · Status: Accepted

## Context

Each turn follows five fixed steps: build the agent views, call the agents, validate the proposals, let Lodestar arbitrate, then run the engine and log the result. The flow has no dynamic branching.

The engineering standards say to warn before adding a third-party dependency and to name one alternative. An agent framework is a large dependency with its own model of state.

Framework capabilities below are from memory and were not rechecked on 2026-11-04.

## Decision

We will write the supervisor as a plain Python module in `src/linkfall/supervisor/`.

- An explicit state machine covers the turn phases.
- Every agent call has a timeout and a token budget.
- A `ModelClient` Protocol has one implementation, a client for an OpenAI-compatible HTTP endpoint. Tests use a fake client.
- Agents run one after another by default, because the target machine has no GPU. Concurrency is a later change, measured against a latency budget that a later ADR sets.
- We request schema-constrained output when the model server supports it, and we validate the result anyway.

No agent framework is added.

## Alternatives considered

- **LangGraph.** Considered for graph state, checkpoints and tracing. Rejected because five fixed steps don't need a graph, and our event log already checkpoints each turn. Revisit if we add branching sub-crews, or pauses for the human inside a turn.
- **CrewAI.** Considered for its role-based crew model. Rejected because it hides prompts and control flow, which makes the engine boundary harder to test. Revisit only for a throwaway comparison.

## Consequences

- Pro: fewer dependencies, and the whole loop is readable in one sitting.
- Pro: unit tests run against a fake model client with no server.
- Con: we write retries, timeouts and tracing ourselves. Mitigation: keep the module small and log every model call to the event log.
- Undo: moderate. The `ModelClient` Protocol and the event log limit the change to the supervisor module.

## Related

0002 (engine and agents), 0004 (containers).
