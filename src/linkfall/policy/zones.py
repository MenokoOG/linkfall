"""The pilot's link value and the zone it puts Lodestar in."""

from linkfall.engine.zone_effects import Zone

LINK_MIN = 10
LINK_MAX = 90
LINK_STEP = 5
ASSISTED_FROM = 30
DELEGATED_FROM = 60


class PolicyError(ValueError):
    """The caller passed a value the policy refuses to guess about."""


def validate_link(link: int) -> int:
    if isinstance(link, bool) or not isinstance(link, int):
        raise PolicyError("link must be an integer")
    if not LINK_MIN <= link <= LINK_MAX or (link - LINK_MIN) % LINK_STEP != 0:
        raise PolicyError(
            f"link must be {LINK_MIN} to {LINK_MAX} in steps of {LINK_STEP}, got {link}"
        )
    return link


def zone_for_link(link: int) -> Zone:
    validate_link(link)
    if link < ASSISTED_FROM:
        return Zone.MANUAL
    return Zone.ASSISTED if link < DELEGATED_FROM else Zone.DELEGATED
