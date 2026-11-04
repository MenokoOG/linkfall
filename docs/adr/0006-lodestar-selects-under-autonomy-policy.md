# 0006: Lodestar selects proposals under autonomy policy

Date: 2026-11-04 · Status: Accepted

## Context

The pilot sets a link value from 10 to 90. The link decides how much Lodestar, the lead agent, may do alone. The interactive demo showed three zones and one deliberate weakness: at high link, Lodestar obeys priority orders that came from the enemy channel.

A model deciding by itself what runs would break ADR 0002. A rule-only Lodestar would remove the showcase. The design needs both: a model that picks, and rules that decide what it may pick.

The library's authority rule applies to the game as well: agents propose, humans sign.

## Decision

We will split Lodestar into a policy and a selector, in `src/linkfall/policy/` and `src/linkfall/agents/lodestar.py`.

- **Policy** is a pure function, `decide(link, mode, proposals) -> Decision`, and holds no state. It computes the zone and the eligible set, and returns one of `MANUAL`, `ASK_PILOT(options)` or `EXECUTE(candidates)`.
- **Selector** is the only model call Lodestar makes. It returns `{"pick": <index or null>, "reason": "<140 characters or fewer>"}`. The index must point into the eligible candidates. Anything else triggers the fallback: the first valid candidate in the order Tactical, then Systems.
- **Zones.** Below 30 the zone is MANUAL and Lodestar is not called. From 30 to 59 the zone is ASSISTED, and only `internal` proposals are eligible. From 60 up the zone is DELEGATED. In the demo this zone was called autonomous. We rename it, so the wording matches the guarded wording in the sibling project, which avoids calling agents autonomous.
- **Mode** is a run setting recorded in the event log header, so a replay is exact.
  - `story` is the default. In the delegated zone, `external` proposals are eligible. This is a deliberate, labeled weakness, because it is the lesson.
  - `hardened`: `external` proposals are never eligible for `EXECUTE`. They become `ASK_PILOT`.
- **Human authority.** `accept_truce`, and any future weapons release, always becomes `ASK_PILOT` in both modes. This changes the demo, where a high link accepted the truce alone.
- **Effects.** Zone effects (the effect multiplier, strain per turn, the cost of manual picks) are engine rules, driven by one config table keyed by zone. The policy only names the zone.

## Alternatives considered

- **Lodestar free to choose or write actions.** Considered because it is the most agentic. Rejected because of excessive agency (LLM06) and injection risk. Revisit never.
- **Rule-only Lodestar with no model.** Considered because it is cheap and fast. Rejected as the default because Lodestar's selection and reasoning text are a main part of the showcase. It remains the fallback path, and a no-model run is a useful eval baseline.
- **Learned trust scores per agent.** Considered for realism. Rejected because it adds state and hides the rules the player should be able to learn. Revisit if the game needs long campaigns.

## Consequences

- Pro: the whole policy matrix (link by mode by provenance by action) is a table-driven unit test with no model.
- Pro: red-team evals replay the same injection logs in `story` and `hardened` and compare outcomes. That comparison is the training range's core lesson.
- Pro: the human-authority rule is enforced in code, not in a prompt.
- Con: `story` mode ships a deliberate weakness. Mitigation: the UI and README label it, and `hardened` is one switch away.
- Con: the selector can still pick badly among eligible candidates. Mitigation: it picks only among candidates the policy already allows.
- Undo: moderate. The policy is isolated behind `decide`.

Evals for model behavior live with the repo tests (NIST AI RMF 1.0 mapping goes in the evals ADR).

## Related

0002 (engine owns state), 0005 (agent contract).
