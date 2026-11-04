"""Seeded random numbers as a pure function of an integer state.

A 32-bit generator (mulberry32 family, same as the prototype). The state lives in
State.rng_state, so replay and fingerprints cover it.
"""

_MASK = 0xFFFFFFFF
_STEP = 0x6D2B79F5
_RANGE = 4294967296


def seed_state(seed: int) -> int:
    return seed & _MASK


def next_float(rng_state: int) -> tuple[float, int]:
    """Return (value in [0, 1), next rng_state)."""
    s = (rng_state + _STEP) & _MASK
    t = ((s ^ (s >> 15)) * (s | 1)) & _MASK
    t ^= (t + (((t ^ (t >> 7)) * (t | 61)) & _MASK)) & _MASK
    return ((t ^ (t >> 14)) & _MASK) / _RANGE, s
