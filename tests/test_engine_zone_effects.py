from linkfall.engine.zone_effects import Zone, effect_multiplier, turn_strain


def test_lodestar_multiplier_only_in_delegated() -> None:
    assert effect_multiplier(Zone.ASSISTED, manual=False) == 1.0
    assert effect_multiplier(Zone.DELEGATED, manual=False) == 1.25


def test_manual_pick_never_gets_the_bonus() -> None:
    assert effect_multiplier(Zone.DELEGATED, manual=True) == 1.0


def test_strain_costs_match_prototype() -> None:
    assert turn_strain(Zone.ASSISTED, manual=False) == 3
    assert turn_strain(Zone.DELEGATED, manual=False) == 6
    assert turn_strain(Zone.ASSISTED, manual=True) == 7
    assert turn_strain(Zone.MANUAL, manual=True) == 12
