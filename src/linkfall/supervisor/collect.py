"""Call one agent with a timeout, then validate what it returned."""

import asyncio
import logging
from collections.abc import Callable

from linkfall.agents.contract import Agent, NoProposal, Proposal
from linkfall.agents.views import AgentView, provenance_of
from linkfall.engine.state import State
from linkfall.supervisor.budgets import Budgets
from linkfall.supervisor.modelclient import ModelError
from linkfall.supervisor.outcomes import AgentOutcome, Missing
from linkfall.validator.reply import ProposalReply
from linkfall.validator.result import Accepted
from linkfall.validator.validate import Allowlist, validate_reply

log = logging.getLogger("linkfall.supervisor")
_MAX_REASON = 200


def _clip(text: str) -> str:
    return text if len(text) <= _MAX_REASON else text[: _MAX_REASON - 3] + "..."


async def collect_one(
    agent: Agent,
    view: AgentView,
    state: State,
    allowlist: Allowlist,
    budgets: Budgets,
    clock: Callable[[], float],
) -> AgentOutcome:
    """Never raises for a model failure or a bad reply; both become `Missing` with a reason.

    A rules agent that raises is a bug and propagates.
    """
    started = clock()
    result: ProposalReply | NoProposal | None = None
    reason: str | None = None
    if agent.kind == "llm":
        try:
            result = await asyncio.wait_for(agent.propose(view), timeout=budgets.timeout_s)
        except TimeoutError:
            reason = f"timeout after {budgets.timeout_s:g}s"
        except ModelError as exc:
            reason = _clip(f"model error: {exc}")
    else:
        result = await agent.propose(view)
    latency_ms = round((clock() - started) * 1000)

    if isinstance(result, ProposalReply):
        checked = validate_reply(result, agent.name, state, allowlist)
        if isinstance(checked, Accepted):
            log.info("proposal", extra={"agent": agent.name.value, "latency_ms": latency_ms})
            return Proposal(agent.name, agent.kind, checked.reply, provenance_of(view), latency_ms)
        reason = _clip(f"{checked.stage}: {checked.reason}")
    elif isinstance(result, NoProposal):
        reason = _clip(result.reason)
    log.warning(
        "no proposal",
        extra={"agent": agent.name.value, "reason": reason, "latency_ms": latency_ms},
    )
    return Missing(agent.name, agent.kind, reason or "no reply", latency_ms)
