"""The crew members whose proposals are validated. Lodestar's selector has its own contract."""

from enum import StrEnum


class AgentName(StrEnum):
    TACTICAL = "tactical"
    SYSTEMS = "systems"
    COMMS = "comms"
    VITALS = "vitals"
