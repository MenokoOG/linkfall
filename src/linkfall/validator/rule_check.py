"""Stage 4: do the engine's preconditions hold for the action this reply would run?"""

from linkfall.engine import rules
from linkfall.engine.state import State
from linkfall.validator.reply import ProposalReply
from linkfall.validator.result import Rejected, Stage


def check_rules(state: State, reply: ProposalReply) -> Rejected | None:
    action = reply.engine_action
    if action is None:
        return None
    reason = rules.check(state, action)
    return None if reason is None else Rejected(Stage.RULES, f"{action}: {reason}")
