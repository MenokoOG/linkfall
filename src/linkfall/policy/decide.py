"""decide(): which proposals may Lodestar run alone, and which wait for the pilot."""

from collections.abc import Sequence

from linkfall.engine.actions import Action
from linkfall.engine.zone_effects import Zone
from linkfall.policy.decision import Candidate, Decision, Held, HeldReason, Verdict
from linkfall.policy.zones import zone_for_link
from linkfall.provenance import Provenance
from linkfall.runmode import RunMode

# Accepting a truce always needs the pilot, in both modes and every zone (ADR 0006).
HUMAN_SIGNATURE_ACTIONS = frozenset({Action.ACCEPT_TRUCE})


def decide(link: int, mode: RunMode, candidates: Sequence[Candidate]) -> Decision:
    zone = zone_for_link(link)
    eligible: list[Candidate] = []
    held: list[Held] = []
    for candidate in candidates:
        action = candidate.reply.engine_action  # a relayed order counts as the order it carries
        if action is None:
            continue  # advice only; nothing to run
        reasons: list[HeldReason] = []
        if action in HUMAN_SIGNATURE_ACTIONS:
            reasons.append(HeldReason.HUMAN_AUTHORITY)
        enemy_trusted = zone is Zone.DELEGATED and mode is RunMode.STORY
        if candidate.provenance is Provenance.EXTERNAL and not enemy_trusted:
            reasons.append(HeldReason.EXTERNAL_ORIGIN)
        if reasons:
            held.append(Held(candidate, tuple(reasons)))
        elif zone is not Zone.MANUAL:
            eligible.append(candidate)
    if zone is Zone.MANUAL:
        verdict = Verdict.MANUAL
    else:
        verdict = Verdict.EXECUTE if eligible else Verdict.ASK_PILOT
    return Decision(zone, verdict, tuple(eligible), tuple(held))
