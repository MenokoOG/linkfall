from linkfall.engine.rng import next_float, seed_state
from linkfall.engine.rounding import round2, round_half_up


def test_seed_state_wraps_to_32_bits() -> None:
    assert seed_state(2**32 + 5) == 5


def test_same_state_gives_same_value_and_next_state() -> None:
    assert next_float(4217) == next_float(4217)


def test_values_stay_in_unit_interval_and_state_advances() -> None:
    state = seed_state(1)
    seen: set[int] = set()
    for _ in range(1000):
        value, state = next_float(state)
        assert 0.0 <= value < 1.0
        seen.add(state)
    assert len(seen) == 1000


def test_first_step_advances_state_by_the_generator_constant() -> None:
    _, state = next_float(seed_state(4217))
    assert state == (4217 + 0x6D2B79F5) & 0xFFFFFFFF


def test_round_half_up_matches_javascript() -> None:
    assert [round_half_up(x) for x in (2.5, 3.75, 5.0, 0.49, -0.5)] == [3, 4, 5, 0, 0]


def test_round2() -> None:
    assert round2(0.945) == 0.95
    assert round2(0.7149) == 0.71
