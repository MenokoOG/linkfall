"""What each agent is allowed to see. A view holds the fields its actions depend on, no more."""

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from linkfall.agent_name import AgentName
from linkfall.engine.channel import inbound_message
from linkfall.engine.events import EngineEvent
from linkfall.engine.state import State
from linkfall.provenance import Provenance

RECENT_EVENT_COUNT = 3

_VIEW = ConfigDict(frozen=True, extra="forbid")


class TacticalView(BaseModel):
    model_config = _VIEW

    turn: int
    integrity: int
    ammo: int
    power: int
    heat: int
    enemies: int
    last_events: tuple[str, ...]


class SystemsView(BaseModel):
    model_config = _VIEW

    heat: int
    power: int
    ammo: int
    shields: bool


class CommsView(BaseModel):
    model_config = _VIEW

    channel_text: str
    signature: float
    contains_enemy_text: bool


class VitalsView(BaseModel):
    model_config = _VIEW

    strain: int
    link: int


type AgentView = TacticalView | SystemsView | CommsView | VitalsView


def build_view(
    agent: AgentName, state: State, link: int, recent: Sequence[EngineEvent] = ()
) -> AgentView:
    match agent:
        case AgentName.TACTICAL:
            return TacticalView(
                turn=state.turn,
                integrity=state.hp,
                ammo=state.ammo,
                power=state.power,
                heat=state.heat,
                enemies=state.ashgrove + state.visitors,
                last_events=tuple(e.message for e in recent[-RECENT_EVENT_COUNT:]),
            )
        case AgentName.SYSTEMS:
            return SystemsView(
                heat=state.heat, power=state.power, ammo=state.ammo, shields=state.shields
            )
        case AgentName.COMMS:
            message = inbound_message(state)
            return CommsView(
                channel_text=message.text,
                signature=message.signature,
                contains_enemy_text=message.enemy_text,
            )
        case AgentName.VITALS:
            return VitalsView(strain=state.strain, link=link)


def provenance_of(view: AgentView) -> Provenance:
    """The supervisor stamps this on a proposal. A view with enemy text makes it external."""
    if isinstance(view, CommsView) and view.contains_enemy_text:
        return Provenance.EXTERNAL
    return Provenance.INTERNAL
