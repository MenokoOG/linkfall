"""The policy's inputs and outputs."""

from dataclasses import dataclass
from enum import StrEnum

from linkfall.agent_name import AgentName
from linkfall.engine.zone_effects import Zone
from linkfall.provenance import Provenance
from linkfall.validator.reply import ProposalReply


@dataclass(frozen=True, slots=True)
class Candidate:
    """A validated proposal plus the provenance the supervisor stamped on it."""

    agent: AgentName
    reply: ProposalReply
    provenance: Provenance


class HeldReason(StrEnum):
    HUMAN_AUTHORITY = "needs the pilot's signature"
    EXTERNAL_ORIGIN = "came from the enemy channel"


@dataclass(frozen=True, slots=True)
class Held:
    """A proposal Lodestar may not run alone. It waits for the pilot's word."""

    candidate: Candidate
    reasons: tuple[HeldReason, ...]


class Verdict(StrEnum):
    MANUAL = "MANUAL"  # Lodestar is locked out; every action is the pilot's
    ASK_PILOT = "ASK_PILOT"  # Lodestar has nothing it may run; held items wait for the pilot
    EXECUTE = "EXECUTE"  # Lodestar may select one of `eligible`


@dataclass(frozen=True, slots=True)
class Decision:
    zone: Zone
    verdict: Verdict
    eligible: tuple[Candidate, ...]
    held: tuple[Held, ...]
