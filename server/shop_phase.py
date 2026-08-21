"""What a player's items do between battles.

The battle simulator answers events on a clock; the shop answers a round
beginning and an item changing hands. Neither the clock nor the events exist
here, so this is a small applier of its own rather than a branch inside
`_apply_effects`.

It is deliberately narrow. An item that says "Shop entered: Gain 3 Gold" is a
trigger and an effect, and belongs here. An item that says "Shop entered: Dig
up a random item" needs the shop to be able to make items and put them in a
bag, which is a feature and not an effect. See BACKLOG.md for what is waiting
on what.

There is no `buying`, and there was for a while. Two items say "On buy: ..."
and both need more than a trigger -- one gains a random effect, the other
splits into two items -- so nothing could have called it. A trigger nothing
fires still shows up in an item's description, which would have told the
player it works.
"""

from dataclasses import dataclass, field
from typing import List

from item_effects import GoldEffect, ItemSpec, SaleChanceEffect, ShopEnteredTrigger


@dataclass
class WhatHappened:
    """What the shop phase did, so a caller can tell the player.

    Returned rather than applied, because the session is the caller's and this
    has no business writing to it.
    """

    gold: int = 0
    sale_chance: float = 0.0
    said: List[str] = field(default_factory=list)


def entering_the_shop(specs: List[ItemSpec]) -> WhatHappened:
    """What the player's items do as the shop opens.

    `specs` is everything they hold, on the grid or in the chest: an item works
    the shop the same either way, which is the rule `held_item_types` already
    follows.
    """
    out = WhatHappened()
    for spec in specs:
        for trigger in spec.triggers:
            if not isinstance(trigger, ShopEnteredTrigger):
                continue
            for effect in trigger.effects:
                if isinstance(effect, GoldEffect):
                    out.gold += effect.amount
                    out.said.append(f"{spec.name}: {effect.amount:+d} gold")
    return out


def sale_chance_from(specs: List[ItemSpec]) -> float:
    """What the player's items add to the shop's chance of a sale.

    Standing rather than spent, so it is read fresh every time the shop is
    built rather than banked anywhere.
    """
    total = 0.0
    for spec in specs:
        for trigger in spec.triggers:
            for effect in getattr(trigger, "effects", []) or []:
                if isinstance(effect, SaleChanceEffect):
                    total += effect.amount
    return total
