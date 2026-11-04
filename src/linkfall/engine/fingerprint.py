"""A SHA-256 fingerprint of a state and its ordered events, for replay checks (ADR 0007)."""

import hashlib
import json
from collections.abc import Sequence
from dataclasses import asdict

from linkfall.engine.events import EngineEvent
from linkfall.engine.state import State


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def fingerprint(state: State, events: Sequence[EngineEvent] = ()) -> str:
    payload = {"state": asdict(state), "events": [asdict(e) for e in events]}
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
