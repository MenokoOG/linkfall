"""Where a proposal's input came from. Only the supervisor sets it (ADR 0005)."""

from enum import StrEnum


class Provenance(StrEnum):
    INTERNAL = "internal"
    EXTERNAL = "external"  # the agent read text from the enemy channel
