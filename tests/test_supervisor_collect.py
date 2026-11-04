import asyncio
import logging

import pytest

from linkfall.agent_name import AgentName
from linkfall.agents.allowlist import ALLOWLIST
from linkfall.agents.contract import Proposal
from linkfall.agents.systems import SystemsAgent
from linkfall.agents.views import build_view
from linkfall.engine.scenario import CINDER_WARD
from linkfall.engine.step import new_game
from linkfall.provenance import Provenance
from linkfall.supervisor.budgets import Budgets
from linkfall.supervisor.collect import collect_one
from linkfall.supervisor.outcomes import Missing
from linkfall.validator.reply import ProposalReply, ProposedAction
from support import Behaviour, model_error

STATE = new_game(1, CINDER_WARD)[0]
TACTICAL_VIEW = build_view(AgentName.TACTICAL, STATE, 55)
FAST = Budgets(timeout_s=0.05)


def ticking_clock() -> "callable":  # type: ignore[valid-type]
    ticks = iter(x * 0.25 for x in range(100))
    return lambda: next(ticks)


def reply(action: ProposedAction | None, agent: AgentName = AgentName.TACTICAL) -> ProposalReply:
    return ProposalReply(agent=agent, action=action, say="ok")


def run(agent: Behaviour, budgets: Budgets = FAST) -> Proposal | Missing:
    return asyncio.run(
        collect_one(agent, TACTICAL_VIEW, STATE, ALLOWLIST, budgets, ticking_clock())
    )


def test_a_good_reply_becomes_a_proposal_stamped_by_the_supervisor() -> None:
    outcome = run(Behaviour(AgentName.TACTICAL, lambda _v: reply(ProposedAction.FLANK)))
    assert isinstance(outcome, Proposal)
    assert outcome.provenance is Provenance.INTERNAL
    assert outcome.kind == "llm"
    assert outcome.latency_ms == 250


def test_a_slow_model_agent_times_out_and_the_reason_says_so() -> None:
    slow = Behaviour(AgentName.TACTICAL, lambda _v: reply(ProposedAction.FLANK), delay_s=1.0)
    outcome = run(slow)
    assert isinstance(outcome, Missing)
    assert outcome.reason == "timeout after 0.05s"


def test_a_model_error_becomes_missing_with_the_message() -> None:
    outcome = run(Behaviour(AgentName.TACTICAL, lambda _v: model_error("connection refused")))
    assert isinstance(outcome, Missing)
    assert outcome.reason == "model error: connection refused"


def test_long_error_text_is_clipped() -> None:
    outcome = run(Behaviour(AgentName.TACTICAL, lambda _v: model_error("x" * 1000)))
    assert isinstance(outcome, Missing)
    assert len(outcome.reason) <= 200


def test_a_bug_in_a_model_agent_is_not_swallowed() -> None:
    with pytest.raises(RuntimeError, match="boom"):
        run(Behaviour(AgentName.TACTICAL, lambda _v: RuntimeError("boom")))


def test_a_rules_agent_bug_propagates() -> None:
    with pytest.raises(TypeError):
        asyncio.run(
            collect_one(SystemsAgent(), TACTICAL_VIEW, STATE, ALLOWLIST, FAST, ticking_clock())
        )


def test_validator_rejections_become_missing_with_stage_and_reason() -> None:
    not_allowed = run(Behaviour(AgentName.TACTICAL, lambda _v: reply(ProposedAction.COOLDOWN)))
    assert isinstance(not_allowed, Missing)
    assert not_allowed.reason.startswith("allowlist:")
    wrong_id = run(
        Behaviour(AgentName.TACTICAL, lambda _v: reply(ProposedAction.FLANK, AgentName.COMMS))
    )
    assert isinstance(wrong_id, Missing)
    assert wrong_id.reason.startswith("identity:")


def test_a_failed_precondition_is_reported_with_the_numbers() -> None:
    from dataclasses import replace

    hot = replace(STATE, heat=85)
    view = build_view(AgentName.TACTICAL, hot, 55)
    agent = Behaviour(AgentName.TACTICAL, lambda _v: reply(ProposedAction.OVERCHARGE))
    outcome = asyncio.run(collect_one(agent, view, hot, ALLOWLIST, FAST, ticking_clock()))
    assert isinstance(outcome, Missing)
    assert outcome.reason == "rules: overcharge: heat 85 is above 60"


def test_no_proposal_from_the_agent_keeps_its_reason() -> None:
    from linkfall.agents.contract import NoProposal

    outcome = run(Behaviour(AgentName.TACTICAL, lambda _v: NoProposal("schema: bad json")))
    assert isinstance(outcome, Missing)
    assert outcome.reason == "schema: bad json"


def test_failures_are_logged_with_context(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="linkfall.supervisor"):
        run(Behaviour(AgentName.TACTICAL, lambda _v: model_error("down")))
    record = caplog.records[-1]
    assert record.getMessage() == "no proposal"
    assert record.__dict__["agent"] == "tactical"
    assert "down" in record.__dict__["reason"]
