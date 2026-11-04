import pytest

from linkfall.engine.zone_effects import Zone
from linkfall.policy.zones import PolicyError, validate_link, zone_for_link


@pytest.mark.parametrize(
    ("link", "zone"),
    [
        (10, Zone.MANUAL),
        (25, Zone.MANUAL),
        (30, Zone.ASSISTED),
        (55, Zone.ASSISTED),
        (60, Zone.DELEGATED),
        (90, Zone.DELEGATED),
    ],
)
def test_zone_boundaries(link: int, zone: Zone) -> None:
    assert zone_for_link(link) is zone


@pytest.mark.parametrize("bad", [-10, 0, 5, 12, 32, 95, 100, 1000])
def test_links_outside_10_to_90_step_5_are_refused(bad: int) -> None:
    with pytest.raises(PolicyError):
        validate_link(bad)
    with pytest.raises(PolicyError):
        zone_for_link(bad)


def test_bool_and_non_int_links_are_refused() -> None:
    with pytest.raises(PolicyError):
        validate_link(True)
    with pytest.raises(PolicyError):
        validate_link(55.0)  # type: ignore[arg-type]
