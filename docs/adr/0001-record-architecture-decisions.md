# 0001: Record architecture decisions

Date: 2026-11-04 · Status: Proposed

## Context

LINKFALL is a production-scoped, public portfolio project. Choices about the engine, the agents, the models and the container layout will change over months. Without a record, the reasons disappear and the repo drifts.

The engineering standards for every repo require ADRs in `docs/adr/`, and require this record to be the first one.

## Decision

We will keep architecture decisions in `docs/adr/NNNN-kebab-title.md`, in Nygard format: context, decision, alternatives considered, consequences, related.

- Numbers are four digits and sequential. Titles are 8 words or fewer.
- ADRs are append-only. A changed decision gets a new ADR, and the old one is marked "Superseded by NNNN".
- Status moves from Proposed to Accepted only after Lawrence says yes.
- Style choices, bug fixes and routine version bumps get no ADR.
- Each ADR gets one line in the local `DECISIONS.md`, which stays out of the public repo.

## Alternatives considered

- **Rely on commit history.** Considered because it costs nothing. Rejected because commits say what changed and rarely why. Revisit never.
- **Wiki or Notion pages.** Considered for easy editing. Rejected because they drift from the code and skip pull request review. Revisit if more than one person maintains the repo.
- **MADR template with more sections.** Considered for its structure. Rejected because Nygard is lighter for a one-person project. Revisit if ADRs start to run long.

## Consequences

- Pro: the reasons behind each call survive, and reviewers see them in the same PR as the code.
- Pro: the repo shows how decisions were made, which matters for a portfolio.
- Con: writing costs time. Mitigation: the skip rule and the 8-word title limit.
- Undo: trivial. Delete the folder.

## Related

None. This is the first record.
