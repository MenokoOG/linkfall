# 0005: Typed agent contract with filtered views

Date: 2026-11-04 · Status: Accepted, amended by 0011 (view contents, agent return type)

## Context

ADR 0002 says agents propose and the engine decides. This ADR sets the interface between them. The crew mixes two kinds of agent. Tactical and Comms need language, so they call a model. Systems and Vitals read numbers, so they can be plain code. Callers should not care which kind they are talking to.

Small local models on a CPU have short usable context and slow output. Each agent therefore needs a small, filtered view of the world and a short, strict output.

Two other paths feed text to agents: enemy channel text reaches Comms, and model output reaches the validator. Both are untrusted.

## Decision

We will define the agent interface once, in `src/linkfall/agents/contract.py`, with strict types.

```python
class Agent(Protocol):
    name: str
    kind: Literal["llm", "rules"]

    async def propose(self, view: AgentView) -> Proposal: ...
```

- **`AgentView`** is a frozen pydantic model, built by `views.py` as a projection of the engine state for one agent. Tactical sees enemies, integrity, ammo and the last 3 events. Systems sees heat, power and shields. Comms sees channel text and a signature score the engine generates. Vitals sees strain and the link value. Target size is about 600 tokens or less per view. That target is a hypothesis until measured.
- **`Proposal`** holds `agent`, `action`, typed `args`, `say` (flavor text, 140 characters or fewer, never read by the engine) and `provenance`. The supervisor sets `provenance` to `internal` or `external`. An agent whose input held enemy text is stamped `external`. A model can't set or change it. The supervisor also records latency and token counts. The model doesn't report them.
- **Allowlists** live in one table in `contracts.py`. Tactical may propose suppress, flank, overcharge and hold_shield. Systems may propose cooldown, hold_shield and suppress. Comms may propose `accept_truce` and `relay_order`, where `relay_order.order` is an enum of engine actions. Vitals gives advice only. Pilot actions (`audit_comms`, `dismiss`, signing a held proposal) are not agent proposals. They arrive through the API as enum-validated pilot inputs and are logged as pilot events. JSON Schema is generated from the pydantic models.
- **Output control.** We request schema-constrained decoding when the model server supports it, and we validate the result either way.
- **Failure behavior.** Each agent call has a timeout (the value is set after we measure the target machine) and no retry. A timeout, a malformed reply or a disallowed action becomes a "no proposal" event with a reason in the log. The turn goes on without that agent.
- **Swapping.** Systems and Vitals start as `rules` agents. Moving one to a model is a config change, and the same contract tests run against both.

## Alternatives considered

- **Free text, parsed afterward.** Considered because it is easy to prompt. Rejected because parsing errors become silent behavior. Revisit never.
- **Provider tool calling.** Considered because it comes with the server. Rejected because agents have no tools, and support differs across local servers. Revisit if tool calling proves reliable on the chosen model.
- **One model call that writes every crew member's lines.** Considered because it is the cheapest on a CPU. Rejected because it removes the separate views and the isolation between agents, which are the point of the showcase. Revisit as an optional fast mode if latency is unacceptable.

## Consequences

- Pro: agents are swappable and testable with fakes, and the UI can render each agent's proposal on its own card.
- Pro: a poisoned input can only produce a proposal from the agent's allowlist, and Comms can't propose a shield change directly. It can only relay an order, which carries `external` provenance.
- Con: schema-constrained decoding support is unverified for the chosen server. Mitigation: validation runs regardless, and the model-selection ADR checks support.
- Con: the allowlist table duplicates some engine knowledge. Mitigation: one source file, and a test that every engine action is reachable by at least one agent.
- Undo: moderate. Every agent module depends on the contract.

OWASP Top 10 for LLM Applications 2025: LLM01, LLM05 and LLM06 are bounded as in ADR 0002. LLM10 is bounded by the per-call timeout and token cap.

## Related

0002 (engine owns state), 0003 (supervisor), 0006 (autonomy policy).
