"""The validator entry points. A reply is accepted whole or rejected with a reason; never edited."""

from collections.abc import Mapping

from linkfall.agent_name import AgentName
from linkfall.engine.state import State
from linkfall.validator.reply import ProposalReply, ProposedAction
from linkfall.validator.result import Accepted, Rejected, Stage
from linkfall.validator.rule_check import check_rules
from linkfall.validator.schema_check import check_schema

type Allowlist = Mapping[AgentName, frozenset[ProposedAction]]


def validate_reply(
    reply: ProposalReply, expected: AgentName, state: State, allowlist: Allowlist
) -> Accepted | Rejected:
    """Checks 2 to 4 for a reply that already has the right shape (rules agents use this)."""
    if reply.agent is not expected:
        return Rejected(Stage.IDENTITY, f"reply claims to be {reply.agent}, expected {expected}")
    if reply.action is not None and reply.action not in allowlist.get(expected, frozenset()):
        return Rejected(Stage.ALLOWLIST, f"{expected} may not propose {reply.action}")
    if (rejected := check_rules(state, reply)) is not None:
        return rejected
    return Accepted(reply)


def validate_text(
    text: str, expected: AgentName, state: State, allowlist: Allowlist
) -> Accepted | Rejected:
    """The full path for model output: size and schema first, then checks 2 to 4."""
    checked = check_schema(text)
    if isinstance(checked, Rejected):
        return checked
    return validate_reply(checked, expected, state, allowlist)
