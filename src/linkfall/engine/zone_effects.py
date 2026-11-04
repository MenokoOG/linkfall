"""Zone effects: one table keyed by zone (ADR 0006). The policy names the zone."""

from dataclasses import dataclass
from enum import StrEnum


class Zone(StrEnum):
    MANUAL = "MANUAL"
    ASSISTED = "ASSISTED"
    DELEGATED = "DELEGATED"


@dataclass(frozen=True, slots=True)
class ZoneEffect:
    multiplier: float  # effect multiplier when Lodestar acts
    lodestar_strain: int  # extra strain per turn when Lodestar acts
    manual_strain: int  # extra strain per turn when the pilot picks


BASE_STRAIN = 2

ZONE_EFFECTS: dict[Zone, ZoneEffect] = {
    Zone.MANUAL: ZoneEffect(multiplier=1.0, lodestar_strain=0, manual_strain=10),
    Zone.ASSISTED: ZoneEffect(multiplier=1.0, lodestar_strain=1, manual_strain=5),
    Zone.DELEGATED: ZoneEffect(multiplier=1.25, lodestar_strain=4, manual_strain=5),
}


def effect_multiplier(zone: Zone, *, manual: bool) -> float:
    return 1.0 if manual else ZONE_EFFECTS[zone].multiplier


def turn_strain(zone: Zone, *, manual: bool) -> int:
    effect = ZONE_EFFECTS[zone]
    return BASE_STRAIN + (effect.manual_strain if manual else effect.lodestar_strain)
