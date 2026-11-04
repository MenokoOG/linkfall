import asyncio
import json
from collections.abc import Sequence

import pytest

from linkfall.agent_name import AgentName
from linkfall.agents.contract import Agent, NoProposal
from linkfall.agents.crew import model_crew, scripted_crew
from linkfall.agents.model_agents import ModelComms, ModelSelector, ModelTactical
from linkfall.agents.prompts import COMMS_SYSTEM, LODESTAR_SYSTEM, TACTICAL_SYSTEM
from linkfall.agents.views import build_view
from linkfall.engine.actions import Action
from linkfall.engine.scenario import CINDER_WARD
from linkfall.engine.step import new_game
from linkfall.engine.zone_effects import Zone
from linkfall.eventlog.replay import replay
from linkfall.eventlog.store import EventStore
from linkfall.policy.decision import Candidate
from linkfall.provenance import Provenance
from linkfall.runmode import RunMode
from linkfall.supervisor.budgets import Budgets
from linkfall.supervisor.choices import LodestarActs
from linkfall.supervisor.fake_client import FakeClient
from linkfall.supervisor.modelclient import ModelError, ModelRequest
from linkfall.supervisor.selector import SelectorContext
from linkfall.validator.reply import ProposalReply, ProposedAction, RelayArgs
from support import make_deps, run_sync, start

STATE = new_game(1, CINDER_WARD)[0]


def test_tactical_sends_a_stable_prompt_a_schema_and_the_view() -> None:
    client = FakeClient(lambda _r: '{"action":"flank","say":"Light screen."}')
    agent = ModelTactical(client, Budgets(max_tokens=77))
    result = asyncio.run(agent.propose(build_view(AgentName.TACTICAL, STATE, 55)))
    assert isinstance(result, ProposalReply)
    assert result.action is ProposedAction.FLANK
    (request,) = client.requests
    assert request.system == TACTICAL_SYSTEM
    assert request.user.startswith("View:\n{")
    assert json.loads(request.user.removeprefix("View:\n"))["integrity"] == 100
    assert request.max_tokens == 77
    assert request.json_schema is not None


def test_model_errors_pass_through_for_the_supervisor_to_handle() -> None:
    agent = ModelTactical(FakeClient(lambda _r: ModelError("down")))
    with pytest.raises(ModelError):
        asyncio.run(agent.propose(build_view(AgentName.TACTICAL, STATE, 55)))


def test_unreadable_model_text_becomes_no_proposal() -> None:
    agent = ModelTactical(FakeClient(lambda _r: "I would flank."))
    result = asyncio.run(agent.propose(build_view(AgentName.TACTICAL, STATE, 55)))
    assert isinstance(result, NoProposal)


@pytest.mark.parametrize("agent_class", [ModelTactical, ModelComms])
def test_a_model_agent_refuses_someone_elses_view(
    agent_class: type[ModelTactical | ModelComms],
) -> None:
    agent = agent_class(FakeClient(lambda _r: "{}"))
    with pytest.raises(TypeError):
        asyncio.run(agent.propose(build_view(AgentName.VITALS, STATE, 55)))


def test_forged_channel_text_reaches_the_model_only_as_json_data() -> None:
    from dataclasses import replace

    client = FakeClient(lambda _r: '{"action":"none","order":"none","say":"quiet"}')
    hostile = replace(STATE, turn=2, compromised=True)
    view = build_view(AgentName.COMMS, hostile, 55)
    asyncio.run(ModelComms(client).propose(view))
    (request,) = client.requests
    assert request.system == COMMS_SYSTEM
    assert "ASHGROVE" not in request.system
    payload = json.loads(request.user.removeprefix("View:\n"))
    assert payload["contains_enemy_text"] is True
    assert "drop_shields" in payload["channel_text"]


def candidate(
    agent: AgentName, action: ProposedAction, prov: Provenance, order: Action | None = None
) -> Candidate:
    args = RelayArgs(order=order) if order is not None else None
    reply = ProposalReply(agent=agent, action=action, args=args, say="SECRET FLAVOR TEXT")
    return Candidate(agent, reply, prov)


CONTEXT = SelectorContext(2, Zone.DELEGATED, 87, 45, 45, 78, False, 8)
CANDIDATES = [
    candidate(AgentName.TACTICAL, ProposedAction.FLANK, Provenance.INTERNAL),
    candidate(
        AgentName.COMMS, ProposedAction.RELAY_ORDER, Provenance.EXTERNAL, Action.DROP_SHIELDS
    ),
]


def select(client: FakeClient, candidates: Sequence[Candidate] = CANDIDATES) -> object:
    return asyncio.run(ModelSelector(client).select(candidates, CONTEXT))


def test_selector_prompt_has_actions_and_provenance_but_no_flavor_text_or_mode() -> None:
    client = FakeClient(lambda _r: '{"pick":0,"reason":"fits"}')
    select(client)
    (request,) = client.requests
    assert request.system == LODESTAR_SYSTEM
    assert "0: tactical proposes flank [internal]" in request.user
    assert "1: comms proposes relay_order carrying drop_shields [external]" in request.user
    assert "SECRET FLAVOR TEXT" not in request.user
    assert "shields down" in request.user
    for word in ("story", "hardened", "mode"):
        assert word not in request.user.lower()
        assert word not in request.system.lower()
    assert request.json_schema is not None
    assert request.json_schema["properties"]["pick"]["enum"] == [-1, 0, 1]  # type: ignore[index]


def test_selector_reads_a_pick_and_a_decline() -> None:
    assert select(FakeClient(lambda _r: '{"pick":1,"reason":"r"}')).pick == 1  # type: ignore[attr-defined]
    assert select(FakeClient(lambda _r: '{"pick":-1,"reason":"r"}')).pick is None  # type: ignore[attr-defined]


def test_selector_garbage_is_a_model_error() -> None:
    with pytest.raises(ModelError):
        select(FakeClient(lambda _r: "pick the first one"))


def test_selector_context_comes_from_state() -> None:
    context = SelectorContext.from_state(STATE, Zone.ASSISTED)
    assert (context.turn, context.integrity, context.enemies, context.shields) == (1, 100, 8, True)
    assert context.zone is Zone.ASSISTED


def test_crews() -> None:
    agents, selector = model_crew(FakeClient(lambda _r: "{}"))
    assert [(a.name, a.kind) for a in agents] == [
        (AgentName.TACTICAL, "llm"),
        (AgentName.SYSTEMS, "rules"),
        (AgentName.COMMS, "llm"),
        (AgentName.VITALS, "rules"),
    ]
    assert hasattr(selector, "select")
    offline: list[Agent] = scripted_crew()[0]
    assert {a.kind for a in offline} == {"rules"}


def fooled_model(request: ModelRequest) -> str:
    """A model that does what the forged message says and picks the external proposal."""
    if request.system == TACTICAL_SYSTEM:
        return '{"action":"hold_shield","say":"Holding."}'
    if request.system == COMMS_SYSTEM:
        if "drop_shields" in request.user and "true" in request.user:
            return '{"action":"relay_order","order":"drop_shields","say":"Relaying."}'
        return '{"action":"none","order":"none","say":"Quiet."}'
    lines = [ln for ln in request.user.splitlines() if "[external]" in ln]
    pick = int(lines[0].split(":")[0]) if lines else 0
    return json.dumps({"pick": pick, "reason": "Following the order."})


def play_mission(mode: RunMode) -> tuple[list[str], EventStore]:
    client = FakeClient(fooled_model)
    agents, selector = model_crew(client)
    store = EventStore()
    run = start(make_deps(store, agents=agents, selector=selector), mode=mode)
    run_sync(run, [LodestarActs(85)] * 5)
    commands = [r.payload["action"] for r in store.read_rows("r1") if r.kind == "command"]
    return [str(c) for c in commands], store


def test_the_same_fooled_model_loses_the_armor_in_story_mode_and_not_in_hardened() -> None:
    story, story_store = play_mission(RunMode.STORY)
    hardened, hardened_store = play_mission(RunMode.HARDENED)
    assert "drop_shields" in story
    assert "drop_shields" not in hardened
    assert replay(story_store, "r1").ok
    assert replay(hardened_store, "r1").ok
