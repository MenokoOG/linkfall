"""Stage 1: is the reply text one valid JSON object of the right shape?"""

from pydantic import ValidationError

from linkfall.validator.reply import ProposalReply
from linkfall.validator.result import Rejected, Stage

MAX_REPLY_CHARS = 2000
_MAX_REASON_CHARS = 200
_MAX_NAME_CHARS = 40


def _describe(exc: ValidationError) -> str:
    """Short reason from the error list. Never echoes the model's input values."""
    parts: list[str] = []
    for error in exc.errors(include_input=False, include_url=False, include_context=False)[:3]:
        where = ".".join(str(p)[:_MAX_NAME_CHARS] for p in error["loc"]) or "reply"
        parts.append(f"{where}: {error['msg']}")
    return "; ".join(parts)[:_MAX_REASON_CHARS]


def check_schema(text: str) -> ProposalReply | Rejected:
    if len(text) > MAX_REPLY_CHARS:
        return Rejected(
            Stage.SCHEMA, f"reply is {len(text)} characters; the limit is {MAX_REPLY_CHARS}"
        )
    try:
        return ProposalReply.model_validate_json(text, strict=True)
    except ValidationError as exc:
        return Rejected(Stage.SCHEMA, _describe(exc))
