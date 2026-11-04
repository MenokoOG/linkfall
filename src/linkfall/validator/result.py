"""The two possible answers from the validator."""

from dataclasses import dataclass
from enum import StrEnum

from linkfall.validator.reply import ProposalReply


class Stage(StrEnum):
    SCHEMA = "schema"
    IDENTITY = "identity"
    ALLOWLIST = "allowlist"
    RULES = "rules"


@dataclass(frozen=True, slots=True)
class Accepted:
    reply: ProposalReply


@dataclass(frozen=True, slots=True)
class Rejected:
    stage: Stage
    reason: str
