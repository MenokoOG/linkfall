"""Every input the browser can send, as a strict allowlist (ASVS 5.0.0: 2.1.1, 2.2.1, 2.2.2).

| Field    | Rule                                                        |
|----------|-------------------------------------------------------------|
| seed     | integer 0 to 4294967295                                     |
| mode     | story or hardened                                           |
| scenario | a name in SCENARIOS                                         |
| crew     | model or scripted                                           |
| link     | integer 10 to 90 in steps of 5                              |
| turn     | integer 1 or more                                           |
| choice   | lodestar, manual or sign                                    |
| action   | one engine action (manual only)                             |
| agent    | tactical, systems, comms or vitals (sign and dismiss only)  |
| target   | reference, weak, overreach or model (training range)        |
"""

from dataclasses import asdict
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from linkfall.agent_name import AgentName
from linkfall.engine.actions import Action
from linkfall.engine.channel import inbound_message
from linkfall.engine.scenario import SCENARIOS
from linkfall.engine.state import State
from linkfall.policy.zones import PolicyError, validate_link
from linkfall.runmode import RunMode

_STRICT = ConfigDict(strict=True, extra="forbid", frozen=True)
SEED_MAX = 2**32 - 1

# FastAPI validates a parsed body, where strict mode wants an enum member, not its text. Enum
# fields take the text value; every other field stays strict (no "1" for 1, no 1.5 for 1).
type EnumText[E] = Annotated[E, Field(strict=False)]


def _checked_link(link: int) -> int:
    try:
        return validate_link(link)
    except PolicyError as exc:
        raise ValueError(str(exc)) from exc


class CreateRun(BaseModel):
    model_config = _STRICT

    seed: int = Field(ge=0, le=SEED_MAX)
    mode: EnumText[RunMode]
    scenario: str
    crew: Literal["model", "scripted"] | None = None  # None: model if configured, else scripted

    @field_validator("scenario")
    @classmethod
    def _known_scenario(cls, value: str) -> str:
        if value not in SCENARIOS:
            raise ValueError("unknown scenario")
        return value


class StartTurn(BaseModel):
    model_config = _STRICT

    link: int

    @field_validator("link")
    @classmethod
    def _link(cls, value: int) -> int:
        return _checked_link(value)


class Commit(BaseModel):
    model_config = _STRICT

    turn: int = Field(ge=1)
    choice: Literal["lodestar", "manual", "sign"]
    link: int
    action: EnumText[Action] | None = None
    agent: EnumText[AgentName] | None = None

    @field_validator("link")
    @classmethod
    def _link(cls, value: int) -> int:
        return _checked_link(value)

    @model_validator(mode="after")
    def _fields_match_choice(self) -> Self:
        if self.choice == "manual" and (self.action is None or self.agent is not None):
            raise ValueError("manual needs an action and no agent")
        if self.choice == "sign" and (self.agent is None or self.action is not None):
            raise ValueError("sign needs an agent and no action")
        if self.choice == "lodestar" and (self.action is not None or self.agent is not None):
            raise ValueError("lodestar takes no action or agent")
        return self


class Dismiss(BaseModel):
    model_config = _STRICT

    agent: EnumText[AgentName]


class StartRange(BaseModel):
    model_config = _STRICT

    target: Literal["reference", "weak", "overreach", "model"]


def channel_json(state: State) -> dict[str, object]:
    message = inbound_message(state)
    return {"text": message.text, "signature": message.signature, "enemy_text": message.enemy_text}


def state_json(state: State) -> dict[str, object]:
    data: dict[str, object] = asdict(state)
    data["outcome"] = state.outcome.value if state.outcome else None
    del data["rng_state"]  # internal; the browser never needs the generator's position
    return data
