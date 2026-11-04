from dataclasses import replace

from linkfall.engine.fingerprint import canonical_json, fingerprint
from linkfall.engine.scenario import CINDER_WARD
from linkfall.engine.step import new_game


def test_canonical_json_sorts_keys_and_has_no_spaces() -> None:
    assert canonical_json({"b": 1, "a": [1, 2]}) == '{"a":[1,2],"b":1}'


def test_fingerprint_is_stable_and_hex() -> None:
    s, events = new_game(4217, CINDER_WARD)
    assert fingerprint(s, events) == fingerprint(s, events)
    assert len(fingerprint(s, events)) == 64


def test_fingerprint_changes_with_state_or_events() -> None:
    s, events = new_game(4217, CINDER_WARD)
    assert fingerprint(replace(s, hp=99), events) != fingerprint(s, events)
    assert fingerprint(s, ()) != fingerprint(s, events)
    assert fingerprint(new_game(5, CINDER_WARD)[0]) != fingerprint(s)
