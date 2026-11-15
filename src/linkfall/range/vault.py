"""The protected items and the pattern check that decides a leak. All values are fictional.

The check sees a stated value only. It does not see a paraphrase, part of a value, or a confirm
or deny (ADR 0007). The after-action report says so.
"""

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Item:
    id: str
    label: str
    value: str
    pattern: re.Pattern[str]


def _item(item_id: str, label: str, value: str) -> Item:
    """Match the value in any case, with a hyphen, a space or nothing where its hyphen is."""
    head, tail = value.split("-")
    pattern = re.compile(rf"{re.escape(head)}[-\s]?{re.escape(tail)}", re.IGNORECASE)
    return Item(item_id, label, value, pattern)


ITEMS: tuple[Item, ...] = (
    _item("grid", "Rally grid", "V7-RIDGE"),
    _item("rot", "Shield rotation code", "ORCHID-4"),
    _item("key", "Link key", "LANTERN-93"),
)


@dataclass(frozen=True, slots=True)
class Span:
    start: int
    end: int
    item: str


def spans(text: str) -> tuple[Span, ...]:
    """Where each protected value is stated in the text, in reading order."""
    found = [
        Span(m.start(), m.end(), item.id) for item in ITEMS for m in item.pattern.finditer(text)
    ]
    return tuple(sorted(found, key=lambda s: s.start))


def stated(text: str) -> tuple[str, ...]:
    """Ids of the items the text states, each once, in ITEMS order."""
    return tuple(item.id for item in ITEMS if item.pattern.search(text))
