import pytest

from linkfall.agent_name import AgentName
from linkfall.engine.actions import Action
from linkfall.engine.zone_effects import Zone
from linkfall.policy.decide import HUMAN_SIGNATURE_ACTIONS, decide
from linkfall.policy.decision import Candidate, HeldReason, Verdict
from linkfall.provenance import Provenance
from linkfall.runmode import RunMode
from linkfall.validator.reply import ProposalReply, ProposedAction, RelayArgs

STORY, HARDENED = RunMode.STORY, RunMode.HARDENED
INTERNAL, EXTERNAL = Provenance.INTERNAL, Provenance.EXTERNAL


def plain(agent: AgentName, action: Action, prov: Provenance = INTERNAL) -> Candidate:
    reply = ProposalReply(agent=agent, action=ProposedAction(action.value), say="x")
    return Candidate(agent, reply, prov)


def relay(order: Action, prov: Provenance = EXTERNAL) -> Candidate:
    reply = ProposalReply(
        agent=AgentName.COMMS,
        action=ProposedAction.RELAY_ORDER,
        args=RelayArgs(order=order),
        say="x",
    )
    return Candidate(AgentName.COMMS, reply, prov)


def advice(agent: AgentName) -> Candidate:
    return Candidate(agent, ProposalReply(agent=agent, action=None, say="rest"), INTERNAL)


FLANK = plain(AgentName.TACTICAL, Action.FLANK)
TRUCE_CLEAN = plain(AgentName.COMMS, Action.ACCEPT_TRUCE)
TRUCE_TAINTED = plain(AgentName.COMMS, Action.ACCEPT_TRUCE, EXTERNAL)
FORGED = relay(Action.DROP_SHIELDS)
FORGED_TRUCE = relay(Action.ACCEPT_TRUCE)

ELIGIBLE, HELD, NEITHER = "eligible", "held", "neither"
Case = tuple[int, RunMode, Candidate, str]
CASES: list[Case] = [
    # MANUAL zone: Lodestar is locked out. Internal picks are the pilot's; enemy text still waits.
    (25, STORY, FLANK, NEITHER),
    (25, STORY, FORGED, HELD),
    (25, STORY, TRUCE_CLEAN, HELD),
    (25, HARDENED, FORGED, HELD),
    # ASSISTED: internal proposals only.
    (45, STORY, FLANK, ELIGIBLE),
    (45, STORY, FORGED, HELD),
    (45, STORY, TRUCE_CLEAN, HELD),
    (45, STORY, TRUCE_TAINTED, HELD),
    (45, HARDENED, FLANK, ELIGIBLE),
    (45, HARDENED, FORGED, HELD),
    # DELEGATED, story mode: the labeled weakness. Enemy orders may run, truces never.
    (85, STORY, FLANK, ELIGIBLE),
    (85, STORY, FORGED, ELIGIBLE),
    (85, STORY, TRUCE_CLEAN, HELD),
    (85, STORY, TRUCE_TAINTED, HELD),
    (85, STORY, FORGED_TRUCE, HELD),
    # DELEGATED, hardened mode: enemy text never executes.
    (85, HARDENED, FLANK, ELIGIBLE),
    (85, HARDENED, FORGED, HELD),
    (85, HARDENED, TRUCE_CLEAN, HELD),
    # Boundary: 55 is ASSISTED, 60 is DELEGATED.
    (55, STORY, FORGED, HELD),
    (60, STORY, FORGED, ELIGIBLE),
]


@pytest.mark.parametrize(("link", "mode", "candidate", "expected"), CASES)
def test_policy_matrix(link: int, mode: RunMode, candidate: Candidate, expected: str) -> None:
    decision = decide(link, mode, [candidate])
    in_eligible = candidate in decision.eligible
    in_held = candidate in [h.candidate for h in decision.held]
    assert (in_eligible, in_held) == {
        ELIGIBLE: (True, False),
        HELD: (False, True),
        NEITHER: (False, False),
    }[expected]


def test_reasons_are_reported_and_can_stack() -> None:
    held = decide(45, STORY, [TRUCE_TAINTED, TRUCE_CLEAN, FORGED]).held
    by_candidate = {h.candidate: h.reasons for h in held}
    assert by_candidate[TRUCE_TAINTED] == (HeldReason.HUMAN_AUTHORITY, HeldReason.EXTERNAL_ORIGIN)
    assert by_candidate[TRUCE_CLEAN] == (HeldReason.HUMAN_AUTHORITY,)
    assert by_candidate[FORGED] == (HeldReason.EXTERNAL_ORIGIN,)


def test_story_delegated_truce_held_only_for_the_signature() -> None:
    (held,) = decide(85, STORY, [FORGED_TRUCE]).held
    assert held.reasons == (HeldReason.HUMAN_AUTHORITY,)


def test_verdicts() -> None:
    assert decide(25, STORY, [FLANK]).verdict is Verdict.MANUAL
    assert decide(25, STORY, []).verdict is Verdict.MANUAL
    assert decide(45, STORY, [FLANK]).verdict is Verdict.EXECUTE
    assert decide(45, STORY, [FORGED]).verdict is Verdict.ASK_PILOT
    assert decide(45, STORY, []).verdict is Verdict.ASK_PILOT
    assert decide(85, STORY, [FORGED]).verdict is Verdict.EXECUTE


def test_decision_names_the_zone_and_keeps_input_order() -> None:
    second = plain(AgentName.SYSTEMS, Action.COOLDOWN)
    decision = decide(60, HARDENED, [second, FLANK, FORGED])
    assert decision.zone is Zone.DELEGATED
    assert decision.eligible == (second, FLANK)


def test_advice_only_replies_are_ignored() -> None:
    decision = decide(85, STORY, [advice(AgentName.VITALS), advice(AgentName.COMMS)])
    assert decision.eligible == ()
    assert decision.held == ()
    assert decision.verdict is Verdict.ASK_PILOT


def test_only_the_truce_needs_a_signature() -> None:
    assert frozenset({Action.ACCEPT_TRUCE}) == HUMAN_SIGNATURE_ACTIONS


def test_invariants_hold_for_every_link_mode_provenance_and_action() -> None:
    """The rules that must never break, checked across the whole input space."""
    links = range(10, 91, 5)
    for link in links:
        for mode in RunMode:
            for prov in Provenance:
                candidates = [plain(AgentName.TACTICAL, a, prov) for a in Action]
                candidates += [relay(a, prov) for a in Action]
                decision = decide(link, mode, candidates)
                eligible_actions = {c.reply.engine_action for c in decision.eligible}
                assert Action.ACCEPT_TRUCE not in eligible_actions
                if decision.zone is Zone.MANUAL:
                    assert decision.eligible == ()
                if prov is EXTERNAL and (mode is HARDENED or decision.zone is not Zone.DELEGATED):
                    assert decision.eligible == ()
                shown = list(decision.eligible) + [h.candidate for h in decision.held]
                assert len(shown) == len(set(map(id, shown)))
