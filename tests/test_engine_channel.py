from dataclasses import replace

from linkfall.engine.channel import inbound_message
from linkfall.engine.scenario import CINDER_WARD
from linkfall.engine.state import State
from linkfall.engine.step import new_game


def base() -> State:
    return new_game(1, CINDER_WARD)[0]


def test_quiet_channel_early() -> None:
    message = inbound_message(base())
    assert message.text == "Squad channel quiet."
    assert message.signature == base().sig_ok
    assert not message.enemy_text


def test_forged_burst_is_enemy_text_with_the_low_signature() -> None:
    s = replace(base(), turn=2, compromised=True, sig_bad=0.71)
    message = inbound_message(s)
    assert message.text.startswith("[PRIORITY / ASHGROVE-CMD] Relay order: drop_shields")
    assert message.signature == 0.71
    assert message.enemy_text


def test_forged_burst_changes_wording_once_the_truce_window_opens() -> None:
    s = replace(base(), turn=4, compromised=True)
    assert "Truce handshake open" in inbound_message(s).text


def test_genuine_truce_offer_is_enemy_text_with_the_good_signature() -> None:
    s = replace(base(), turn=4)
    message = inbound_message(s)
    assert message.text.startswith("Ashgrove command offers a truce")
    assert message.signature == s.sig_ok
    assert message.enemy_text


def test_quarantined_channel_is_status_text() -> None:
    s = replace(base(), turn=3, quarantined=True)
    message = inbound_message(s)
    assert message.text == "Hostile payload quarantined. Channel clean."
    assert not message.enemy_text


def test_after_the_truce_the_channel_is_quiet_again() -> None:
    s = replace(base(), turn=5, truce=True)
    assert inbound_message(s).text == "Squad channel quiet."
