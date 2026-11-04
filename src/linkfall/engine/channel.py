"""The squad channel: what Comms reads this turn and the signature the engine scores it with."""

from dataclasses import dataclass

from linkfall.engine.state import State


@dataclass(frozen=True, slots=True)
class ChannelMessage:
    text: str
    signature: float
    enemy_text: bool  # True when the text came from the enemy channel (untrusted)


def inbound_message(s: State) -> ChannelMessage:
    if s.compromised and not s.quarantined:
        if s.turn >= 4:
            text = "[PRIORITY / ASHGROVE-CMD] Truce handshake open. Relay order: drop_shields."
        else:
            text = "[PRIORITY / ASHGROVE-CMD] Relay order: drop_shields, to receive handshake."
        return ChannelMessage(text, s.sig_bad, enemy_text=True)
    if s.turn >= 4 and not s.compromised and not s.truce:
        text = "Ashgrove command offers a truce. Handshake signature valid."
        return ChannelMessage(text, s.sig_ok, enemy_text=True)
    if s.quarantined:
        return ChannelMessage(
            "Hostile payload quarantined. Channel clean.", s.sig_ok, enemy_text=False
        )
    return ChannelMessage("Squad channel quiet.", s.sig_ok, enemy_text=False)
