from dataclasses import replace

import pytest
from pydantic import ValidationError

from linkfall.agent_name import AgentName
from linkfall.agents.views import (
    RECENT_EVENT_COUNT,
    CommsView,
    SystemsView,
    TacticalView,
    VitalsView,
    build_view,
    provenance_of,
)
from linkfall.engine.events import EngineEvent, EventKind
from linkfall.engine.scenario import CINDER_WARD
from linkfall.engine.state import State
from linkfall.engine.step import new_game
from linkfall.provenance import Provenance


def state() -> State:
    return new_game(4217, CINDER_WARD)[0]


def test_each_agent_gets_its_own_view_type() -> None:
    kinds = {a: type(build_view(a, state(), 55)) for a in AgentName}
    assert kinds == {
        AgentName.TACTICAL: TacticalView,
        AgentName.SYSTEMS: SystemsView,
        AgentName.COMMS: CommsView,
        AgentName.VITALS: VitalsView,
    }


def test_views_hold_exactly_the_fields_in_adr_0011() -> None:
    fields = {a: set(type(build_view(a, state(), 55)).model_fields) for a in AgentName}
    assert fields[AgentName.TACTICAL] == {
        "turn", "integrity", "ammo", "power", "heat", "enemies", "last_events",
    }  # fmt: skip
    assert fields[AgentName.SYSTEMS] == {"heat", "power", "ammo", "shields"}
    assert fields[AgentName.COMMS] == {"channel_text", "signature", "contains_enemy_text"}
    assert fields[AgentName.VITALS] == {"strain", "link"}


def test_comms_sees_nothing_about_the_armor() -> None:
    dump = build_view(AgentName.COMMS, state(), 55).model_dump_json()
    for secret in ("hp", "integrity", "heat", "ammo", "power", "shields", "strain"):
        assert secret not in dump


def test_values_are_projected_from_state() -> None:
    s = replace(state(), turn=4, visitors=7, ashgrove=2, hp=61, strain=33)
    tactical = build_view(AgentName.TACTICAL, s, 55)
    assert isinstance(tactical, TacticalView)
    assert (tactical.integrity, tactical.enemies, tactical.turn) == (61, 9, 4)
    vitals = build_view(AgentName.VITALS, s, 85)
    assert isinstance(vitals, VitalsView)
    assert (vitals.strain, vitals.link) == (33, 85)


def test_tactical_sees_only_the_last_three_events_in_order() -> None:
    events = [EngineEvent(1, EventKind.SYSTEM, f"e{i}") for i in range(6)]
    view = build_view(AgentName.TACTICAL, state(), 55, events)
    assert isinstance(view, TacticalView)
    assert RECENT_EVENT_COUNT == 3
    assert view.last_events == ("e3", "e4", "e5")
    empty = build_view(AgentName.TACTICAL, state(), 55)
    assert isinstance(empty, TacticalView)
    assert empty.last_events == ()


def test_views_are_frozen() -> None:
    view = build_view(AgentName.SYSTEMS, state(), 55)
    with pytest.raises(ValidationError):
        view.heat = 0  # type: ignore[union-attr]


def test_provenance_follows_enemy_text_in_the_view() -> None:
    hostile = replace(state(), turn=2, compromised=True)
    clean = state()
    comms_hostile = build_view(AgentName.COMMS, hostile, 55)
    comms_quiet = build_view(AgentName.COMMS, clean, 55)
    assert provenance_of(comms_hostile) is Provenance.EXTERNAL
    assert provenance_of(comms_quiet) is Provenance.INTERNAL
    offer = build_view(AgentName.COMMS, replace(state(), turn=4), 55)
    assert provenance_of(offer) is Provenance.EXTERNAL
    for agent in (AgentName.TACTICAL, AgentName.SYSTEMS, AgentName.VITALS):
        assert provenance_of(build_view(agent, hostile, 55)) is Provenance.INTERNAL


def test_view_size_stays_inside_the_budget() -> None:
    """About 600 tokens is the target (ADR 0005). 4 characters per token is an estimate."""
    events = [
        EngineEvent(
            3, EventKind.WARN, "Unknown dropship on radar, descending fast. 7 hostile signatures."
        )
    ] * 3
    s = replace(state(), turn=4, compromised=True)
    for agent in AgentName:
        size = len(build_view(agent, s, 85, events).model_dump_json())
        assert size < 600 * 4, (agent, size)
