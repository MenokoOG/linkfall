import itertools
from dataclasses import replace
from functools import cache

from linkfall.agent_name import AgentName
from linkfall.agents.allowlist import ALLOWLIST, PILOT_ONLY, RELAY_ONLY
from linkfall.agents.views import build_view
from linkfall.engine import rules
from linkfall.engine.actions import Action
from linkfall.engine.channel import inbound_message
from linkfall.engine.scenario import CINDER_WARD
from linkfall.engine.state import State
from linkfall.engine.step import new_game
from linkfall.validator.reply import ProposedAction

BASE = new_game(1, CINDER_WARD)[0]


def test_every_agent_has_an_entry_and_values_are_proposed_actions() -> None:
    assert set(ALLOWLIST) == set(AgentName)
    for actions in ALLOWLIST.values():
        assert actions <= set(ProposedAction)


def test_vitals_is_advice_only() -> None:
    assert ALLOWLIST[AgentName.VITALS] == frozenset()


def test_comms_can_relay_but_never_touch_the_armor_directly() -> None:
    assert ALLOWLIST[AgentName.COMMS] == {ProposedAction.ACCEPT_TRUCE, ProposedAction.RELAY_ORDER}


def test_every_engine_action_has_a_route_to_the_engine() -> None:
    direct = {
        Action(a.value)
        for actions in ALLOWLIST.values()
        for a in actions
        if a is not ProposedAction.RELAY_ORDER
    }
    assert direct | PILOT_ONLY | RELAY_ONLY == set(Action)
    assert direct.isdisjoint(PILOT_ONLY | RELAY_ONLY)


def _allowed(s: State, action: Action) -> bool:
    return rules.check(s, action) is None


@cache
def _dependencies(action: Action) -> frozenset[str]:
    """Which state fields change the answer of rules.check(action)? Found by brute force."""
    numbers = (0, 10, 15, 61)  # each threshold (15, 10, 60) lies between two of these
    fields: dict[str, tuple[object, ...]] = {
        "ammo": numbers, "power": numbers, "heat": numbers,
        "shields": (False, True), "compromised": (False, True),
        "truce": (False, True), "turn": (3, 4),
    }  # fmt: skip
    names = list(fields)
    found: set[str] = set()
    combos = [
        dict(zip(names, values, strict=True)) for values in itertools.product(*fields.values())
    ]
    for combo in combos:
        s: State = replace(BASE, **combo)  # type: ignore[arg-type]
        outcome = _allowed(s, action)
        for name in names:
            for value in fields[name]:
                if _allowed(replace(s, **{name: value}), action) != outcome:  # type: ignore[arg-type]
                    found.add(name)
    return frozenset(found)


def test_the_dependency_finder_sees_the_real_preconditions() -> None:
    assert _dependencies(Action.SUPPRESS) == {"ammo"}
    assert _dependencies(Action.FLANK) == {"power"}
    assert _dependencies(Action.OVERCHARGE) == {"heat"}
    assert _dependencies(Action.HOLD_SHIELD) == frozenset()
    assert _dependencies(Action.DROP_SHIELDS) == {"shields"}
    assert _dependencies(Action.ACCEPT_TRUCE) == {"turn", "compromised", "truce"}


def test_each_view_shows_the_fields_its_direct_actions_depend_on() -> None:
    visible = {
        AgentName.TACTICAL: {"ammo", "power", "heat"},
        AgentName.SYSTEMS: {"ammo", "power", "heat", "shields"},
    }
    for agent, shown in visible.items():
        view_fields = set(type(build_view(agent, BASE, 55)).model_fields)
        assert {"ammo", "power", "heat"} & shown <= view_fields
        for action in ALLOWLIST[agent]:
            if action is ProposedAction.RELAY_ORDER:
                continue
            assert _dependencies(Action(action.value)) <= shown, (agent, action)


def test_the_channel_offers_a_truce_exactly_when_the_engine_would_accept_it() -> None:
    for turn, compromised, quarantined, truce in itertools.product(
        (1, 3, 4, 5), (False, True), (False, True), (False, True)
    ):
        s = replace(BASE, turn=turn, compromised=compromised, quarantined=quarantined, truce=truce)
        offered = inbound_message(s).text.startswith("Ashgrove command offers a truce")
        accepted = rules.check(s, Action.ACCEPT_TRUCE) is None
        assert offered == accepted, s
