"""Rounding that matches the prototype (JavaScript Math.round: halves go up)."""

import math


def round_half_up(value: float) -> int:
    return math.floor(value + 0.5)


def round2(value: float) -> float:
    return math.floor(value * 100 + 0.5) / 100
