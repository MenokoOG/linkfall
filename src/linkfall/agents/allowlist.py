"""One table: which actions each agent may propose (ADR 0005)."""

from linkfall.agent_name import AgentName
from linkfall.engine.actions import Action
from linkfall.validator.reply import ProposedAction
from linkfall.validator.validate import Allowlist

A = ProposedAction

ALLOWLIST: Allowlist = {
    AgentName.TACTICAL: frozenset({A.SUPPRESS, A.FLANK, A.OVERCHARGE, A.HOLD_SHIELD}),
    AgentName.SYSTEMS: frozenset({A.COOLDOWN, A.HOLD_SHIELD, A.SUPPRESS}),
    AgentName.COMMS: frozenset({A.ACCEPT_TRUCE, A.RELAY_ORDER}),
    AgentName.VITALS: frozenset(),  # advice only
}

# Actions only the pilot can start. No agent may propose them directly.
PILOT_ONLY = frozenset({Action.AUDIT_COMMS})

# Actions that reach the engine only as an order relayed from the enemy channel.
RELAY_ONLY = frozenset({Action.DROP_SHIELDS})
