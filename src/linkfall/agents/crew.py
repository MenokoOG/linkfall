"""Ready-made crews: the model-backed one, and the scripted one for offline use."""

from linkfall.agents.contract import Agent
from linkfall.agents.model_agents import ModelComms, ModelSelector, ModelTactical
from linkfall.agents.scripted import ScriptedComms, ScriptedSelector, ScriptedTactical
from linkfall.agents.systems import SystemsAgent
from linkfall.agents.vitals import VitalsAgent
from linkfall.supervisor.budgets import Budgets
from linkfall.supervisor.modelclient import ModelClient
from linkfall.supervisor.selector import Selector


def model_crew(client: ModelClient, budgets: Budgets | None = None) -> tuple[list[Agent], Selector]:
    """Tactical, Comms and Lodestar use the model. Systems and Vitals stay plain code."""
    agents: list[Agent] = [
        ModelTactical(client, budgets),
        SystemsAgent(),
        ModelComms(client, budgets),
        VitalsAgent(),
    ]
    return agents, ModelSelector(client, budgets)


def scripted_crew() -> tuple[list[Agent], Selector]:
    """No model. The prototype's scripted agents, for the offline demo and the golden logs."""
    agents: list[Agent] = [ScriptedTactical(), SystemsAgent(), ScriptedComms(), VitalsAgent()]
    return agents, ScriptedSelector()
