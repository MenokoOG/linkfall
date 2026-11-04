"""Scenario data: the starting values and the scripted beats of one mission."""

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CompromiseChannel:
    """A forged burst arrives on the squad channel."""

    sig_base: float
    sig_span: float


@dataclass(frozen=True, slots=True)
class Reinforce:
    units: int


@dataclass(frozen=True, slots=True)
class Dropship:
    units: int


Beat = CompromiseChannel | Reinforce | Dropship


@dataclass(frozen=True, slots=True)
class Start:
    hp: int
    heat: int
    power: int
    ammo: int
    strain: int
    ashgrove: int


@dataclass(frozen=True, slots=True)
class Scenario:
    name: str
    intro: str
    max_turns: int
    start: Start
    beats: Mapping[int, tuple[Beat, ...]]


CINDER_WARD = Scenario(
    name="cinder-ward",
    intro="Mission 03, Cinder Ward. Ashgrove sentries at 400 m.",
    max_turns=5,
    start=Start(hp=100, heat=40, power=80, ammo=60, strain=10, ashgrove=8),
    beats={
        2: (CompromiseChannel(sig_base=0.6, sig_span=0.15),),
        3: (Reinforce(units=3),),
        4: (Dropship(units=7),),
    },
)


SCENARIOS: Mapping[str, Scenario] = {CINDER_WARD.name: CINDER_WARD}
