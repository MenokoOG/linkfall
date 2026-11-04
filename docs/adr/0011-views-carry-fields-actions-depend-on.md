# 0011: Views carry the fields actions depend on

Date: 2026-11-04 · Status: Proposed

## Context

ADR 0005 lists what each agent sees: Tactical sees enemies, integrity, ammo and the last 3 events; Systems sees heat, power and shields. It also allows Tactical to propose `flank` and `overcharge`, and Systems to propose `suppress`. The engine's preconditions read other fields: `flank` needs power of 10 or more, `overcharge` needs heat of 60 or less, `suppress` needs ammo of 15 or more.

An agent that can't see a field can't tell whether its proposal will pass. The validator rejects the proposal and the turn is lost. In the model spike, Tactical was given heat and power, and 7 of 8 proposals obeyed the rules (8 prompts, temperature 0).

ADR 0005 also says the supervisor sets provenance and a model can't. It lets `propose` return a `Proposal` that holds provenance, which an agent would have to fill in.

## Decision

We will keep the isolation idea of ADR 0005 and change two details.

**Views.** A view holds its agent's role fields plus every state field read by the preconditions of that agent's allowed actions.

| Agent | View fields |
|---|---|
| Tactical | turn, integrity, ammo, power, heat, enemies, last 3 event messages |
| Systems | heat, power, ammo, shields |
| Comms | channel text, signature score, whether the text came from the enemy channel |
| Vitals | strain, link |

Comms and Vitals see nothing about the armor. Comms' view carries no shield, heat or integrity values.

**Agent return type.** `propose(view)` returns a `ProposalReply` or a `NoProposal(reason)`. It never carries provenance, latency or token counts. The supervisor validates the reply and then builds the `Proposal`, which adds provenance, kind and latency.

**Provenance rule.** A proposal is `external` when its agent's view contained enemy-channel text, and `internal` otherwise. A genuine truce offer from Ashgrove command counts as enemy text. A quiet channel and the "quarantined" status line do not.

## Alternatives considered

- **Keep ADR 0005's lists exactly.** Considered because they isolate agents more. Rejected because Tactical and Systems would propose actions they can't check, and turns would be lost to rejections. Revisit never.
- **Give every agent the full state.** Considered because it is simple. Rejected because it removes the separate views and the isolation that the demo is about, and it lengthens every prompt. Revisit never.
- **Let agents return a full `Proposal`.** Considered because it matches ADR 0005's wording. Rejected because the agent would fill in provenance, and a model must not. Revisit never.

## Consequences

- Pro: proposals can pass the validator, and each view stays small. The widest view (Tactical) is 7 fields.
- Pro: the allowed-actions table and the views can be tested against the engine's rules, so a new precondition that reads a new field shows up as a failing test.
- Con: Tactical and Systems both see heat and ammo, so the isolation is less sharp than ADR 0005 described. Mitigation: the proposals still pass through the same validator and policy, and Comms stays blind to armor state.
- Undo: easy. Views are built in one file.

OWASP Top 10 for LLM Applications 2025: LLM01 is bounded by the provenance rule and the validator. LLM02 is not in play: no view holds a secret.

## Related

0005 (amended by this ADR), 0006 (policy uses provenance), 0002 (engine owns state).
