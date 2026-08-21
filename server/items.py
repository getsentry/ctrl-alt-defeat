"""
Items: everything the player can buy, keep in the chest, or place on the grid.

An item's numbers all come from its spec in the JSON catalogue, so `Item.of` is
the one place that reads a spec. Every item the server sends carries the same
fields, whether it sits in the shop, in the chest or on the grid.

An item on the grid also has a position and a rotation, and that is the only
difference between the two types. So a position is never null, and nothing has
to work out what a missing one means.
"""

from typing import Dict, Iterator, List, Tuple

from pydantic import BaseModel, Field, computed_field, field_validator

import describe
from config_loader import config_loader
from grid_system import ItemShape, Rotation
from item_effects import (
    AttackEffect,
    BlockEffect,
    HealEffect,
    ItemSpec,
    TimerTrigger,
    Trigger,
)
from item_looks import PATTERNS, hex_of
from utils import Position, Shape

# A colour on the wire is what Godot's Color.html() can read, or nothing at all
# for a container. The client draws whatever arrives without checking it, so
# anything it could not draw has to be stopped here.
HEX_COLOR = r"^(#[0-9A-Fa-f]{6})?$"

# What an item of each rarity costs in the shop.
# Backpack Battles puts one shop item in ten on sale at half price.
SALE_CHANCE = 0.10


def sale_price(cost: int) -> int:
    """Half price, rounded up. Also what an item sells for."""
    return -(-cost // 2)


class ItemStats(BaseModel):
    """
    The numbers a player sees on an item.

    A spec describes behaviour as triggers and effects. These are the summary of
    that behaviour, for the shop and for tooltips.
    """

    min_damage: int = 0
    max_damage: int = 0
    min_heal: int = 0
    max_heal: int = 0
    block_amount: int = 0
    cooldown: float = 0.0
    cpu_cost: float = 0.0


def stats_of(spec: ItemSpec) -> ItemStats:
    """Summarise a spec's triggers and effects as numbers"""
    stats = ItemStats()
    for trigger in spec.triggers or []:
        stats.cooldown = getattr(trigger, "cooldown", stats.cooldown)
        stats.cpu_cost = getattr(trigger, "cpu_cost", stats.cpu_cost)

        for effect in getattr(trigger, "effects", []) or []:
            if hasattr(effect, "min_damage"):
                stats.min_damage = max(stats.min_damage, effect.min_damage)
                stats.max_damage = max(stats.max_damage, effect.max_damage)
            if hasattr(effect, "min_heal"):
                stats.min_heal = max(stats.min_heal, effect.min_heal)
                stats.max_heal = max(stats.max_heal, effect.max_heal)
            if hasattr(effect, "block_amount"):
                stats.block_amount = max(stats.block_amount, effect.block_amount)
    return stats


def already_shown(trigger: Trigger, stats: ItemStats) -> bool:
    """Whether a trigger says only what the item's own numbers already say.

    Damage, healing, Block, the cooldown and the CPU each have a row of their
    own on the card, and they were read off this trigger to get there. A
    weapon whose whole behaviour is "every 1.7s (0.7 CPU): deal 2-3 damage"
    would then say all three of them twice.

    Only where the clause is the numbers and nothing else. "Deal 3-4 damage
    and never miss" is worth a line, because no row says the second half.
    """
    if not isinstance(trigger, TimerTrigger):
        return False
    if trigger.cooldown != stats.cooldown or trigger.cpu_cost != stats.cpu_cost:
        return False

    effects = trigger.effects or []
    if len(effects) != 1:
        return False

    effect = effects[0]
    if isinstance(effect, AttackEffect):
        return (
            effect.special is None
            and effect.accuracy < 1.0
            and effect.min_damage == stats.min_damage
            and effect.max_damage == stats.max_damage
        )
    if isinstance(effect, HealEffect):
        return (effect.min_heal == stats.min_heal
                and effect.max_heal == stats.max_heal)
    if isinstance(effect, BlockEffect):
        return effect.block_amount == stats.block_amount
    return False


def shape_of(spec: ItemSpec) -> Shape:
    """The squares an item of this spec covers, as offsets from its anchor"""
    return [(x, y) for x, y in spec.shape.squares]


class ZoneWants(BaseModel):
    """What one aura clause acts on, of the items standing in its zone.

    Both lists empty means everything standing there. Otherwise `any_of`
    matches an item carrying one of the tags and `all_of` one carrying all of
    them, where a tag is a kind an item carries or the category it belongs to
    (GDD 4.4).
    """

    any_of: List[str] = Field(
        default_factory=list, description="Matches an item carrying one of these"
    )
    all_of: List[str] = Field(
        default_factory=list, description="Matches an item carrying all of these"
    )

    @classmethod
    def of(cls, counting: object) -> "ZoneWants":
        if not isinstance(counting, dict):
            return cls()
        return cls(
            any_of=[tag.lower() for tag in counting.get("any", [])],
            all_of=[tag.lower() for tag in counting.get("all", [])],
        )


def aura_of(spec: ItemSpec) -> Dict[str, List[ZoneWants]]:
    """What each of an item's zones acts on, by zone.

    A zone can work three ways round (GDD 4.4) -- what it falls on, what it
    counts, and when something happens -- and all three narrow the same way, so
    all three are read the same way here.

    A zone the item draws but nothing acts through is absent. That is not the
    same as a zone that acts on everything, which is present and empty: one
    lights up when something stands in it and the other never does, and a
    client showing a player where their aura lands must not confuse them.
    """
    wants: Dict[str, List[ZoneWants]] = {}
    for trigger in spec.triggers or []:
        for zone, narrowed in _zones_named_by(trigger):
            wants.setdefault(zone, []).append(narrowed)
    return wants


#: The three fields an effect or a trigger can name a zone in. They differ
#: because they read differently in the sentence the effect came from -- a
#: modifier lands on a `target`, a count is taken `where`, an aura trigger
#: watches a `zone` -- and all three carry the same two words. The engine
#: reaches through all three; reading only `zone` here left 21 items, Edge
#: Cache among them, sending a client an aura it was never told the meaning
#: of, so nothing ever lit up under one.
ZONE_FIELDS = ("zone", "target_type", "where")


def _zones_named_by(source: object) -> Iterator[Tuple[str, ZoneWants]]:
    """Every zone this trigger or effect acts through, and what it narrows to.

    Recurses, because an effect can hold others -- a chance effect is a
    modifier behind a die roll, and the modifier is the one naming the zone.
    """
    for field in ZONE_FIELDS:
        zone = getattr(source, field, None)
        if zone in ("star", "diamond"):
            yield zone, ZoneWants.of(getattr(source, "counting", "any"))
    for effect in getattr(source, "effects", None) or []:
        yield from _zones_named_by(effect)


class Item(BaseModel):
    """An item in the shop or in the chest. It has no place on the grid yet."""

    id: str = Field(description="Unique item instance ID")
    item_type: str = Field(description="Item type, a key in the item catalogue")
    name: str = Field(description="Display name")
    slug: str = Field(description="URL-friendly identifier")
    category: str = Field(description="Item category")
    rarity: str = Field(description="Item rarity tier")
    cost: int = Field(description="Gold cost")
    is_container: bool = Field(description="Whether this item is a container")
    shape: Shape = Field(description="Covered squares, as [x, y] offsets")
    # The zones the item reaches into, in the same frame as `shape`, so a square
    # above or left of the item is negative. Sent so the client can show a
    # player what an item reaches; nothing draws them yet.
    star: Shape = Field(default_factory=list, description="Star zone, as [x, y] offsets")
    diamond: Shape = Field(
        default_factory=list, description="Diamond zone, as [x, y] offsets"
    )
    # Covered squares whose zone points straight up on the grid however the item
    # is turned. Sent because a client cannot work out the turned zone without
    # them: it would turn the zone with the item and put it in the wrong place.
    anchors: Shape = Field(
        default_factory=list, description="Covered squares whose zone points up"
    )
    # What an item can be narrowed by, with its category: "Star Pets" and "Star
    # nature-items" read the same way and both are matched from here. Lowered,
    # so the catalogue's casing does not reach the client.
    kinds: List[str] = Field(
        default_factory=list, description="The kinds this item carries"
    )
    traits: List[str] = Field(
        default_factory=list,
        description=(
            "The same kinds as a player reads them. Shown, never matched: "
            "`kinds` is what a zone asks for."
        ),
    )
    # What this item's zones act on, by zone. Sent so a client can show which
    # items an aura would actually reach rather than which squares it covers:
    # a zone narrowed to pets lands on a weapon and does nothing.
    aura: Dict[str, List[ZoneWants]] = Field(
        default_factory=dict, description="What each zone acts on, by zone"
    )
    color: str = Field(
        pattern=HEX_COLOR,
        description="Fill colour as #RRGGBB, empty on a container",
    )
    pattern: str = Field(description="Pattern name, empty on a container")
    min_damage: int = Field(description="Minimum damage dealt")
    max_damage: int = Field(description="Maximum damage dealt")
    min_heal: int = Field(description="Minimum healing given")
    max_heal: int = Field(description="Maximum healing given")
    block_amount: int = Field(description="Damage blocked")
    cooldown: float = Field(description="Activation cooldown in seconds")
    cpu_cost: float = Field(description="CPU cost to activate")
    on_sale: bool = Field(
        default=False, description="Whether the shop is offering this at half price"
    )
    effects: List[str] = Field(
        default_factory=list,
        description="What the item does, a line per trigger, in words",
    )

    @field_validator("pattern")
    @classmethod
    def known_pattern(cls, value: str) -> str:
        """A pattern is a name of something the client has a routine for.

        Unlike the colour it cannot be sent as a value, so a name the client
        has never heard of would simply draw nothing. Refuse it here, where
        there is somewhere to say why.
        """
        if value and value not in PATTERNS:
            raise ValueError(f"{value} is not a pattern the client can draw")
        return value

    @classmethod
    def of(cls, item_type: str, item_id: str, on_sale: bool = False) -> "Item":
        """Build an item of a type declared in the item catalogue"""
        spec = config_loader.items[item_type]
        stats = stats_of(spec)
        return cls(
            id=item_id,
            item_type=item_type,
            name=spec.name,
            slug=spec.slug,
            category=spec.category,
            rarity=spec.rarity,
            cost=spec.cost,
            on_sale=on_sale,
            # The catalogue gives a container its own category, so the flag
            # follows from it rather than from a second lookup.
            is_container=spec.category == "container",
            shape=shape_of(spec),
            star=[(x, y) for x, y in spec.shape.star],
            diamond=[(x, y) for x, y in spec.shape.diamond],
            anchors=[(x, y) for x, y in spec.shape.anchors],
            kinds=sorted(kind.lower() for kind in spec.kinds),
            traits=[describe.trait(kind)
                    for kind in sorted(kind.lower() for kind in spec.kinds)],
            aura=aura_of(spec),
            effects=describe.lines(
                spec, skipping=lambda trigger: already_shown(trigger, stats)),
            # The catalogue names a colour, the client is sent the value. That
            # way the client keeps no palette and a colour can be retuned
            # without shipping a new client.
            color=hex_of(spec.color) if spec.color else "",
            pattern=spec.pattern,
            **stats.model_dump(),
        )

    @computed_field
    @property
    def price(self) -> int:
        """What buying it costs right now. Sent, so the shop cannot show
        one number while the server charges another."""
        return sale_price(self.cost) if self.on_sale else self.cost

    @computed_field
    @property
    def sell_value(self) -> int:
        """What selling it pays, whether or not it was bought on sale.

        Sent for the prompt on the sell chest.
        """
        return sale_price(self.cost)

    def item_fields(self) -> dict:
        """Just the fields an Item has, so a placed item can be rebuilt."""
        return {k: v for k, v in self.model_dump().items() if k in Item.model_fields}

    def placed_at(
        self, position: Position, rotation: Rotation = Rotation.NONE
    ) -> "PlacedItem":
        """The same item, now on the grid. Works on a placed item too."""
        return PlacedItem(
            **self.item_fields(),
            position=position,
            rotation=rotation,
        )


class PlacedItem(Item):
    """An item on the grid. It is the only kind that has a place and a facing."""

    position: Position = Field(description="[x, y] anchor on the grid")
    rotation: Rotation = Field(
        default=Rotation.NONE, description="Quarter turns clockwise from the shape"
    )

    def _turned(self) -> ItemShape:
        """This item's shape and zones, turned the way it faces.

        Rebuilt whole rather than turning the squares alone, because the zones
        have to be settled against the footprint's corner. Turned on their own
        they land on top of the item.
        """
        shape = ItemShape(
            squares=list(self.shape),
            star=tuple(self.star),
            diamond=tuple(self.diamond),
            anchors=tuple(self.anchors),
        )
        return shape.rotate(self.rotation)

    def covered_squares(self) -> Shape:
        """The grid squares this item covers, once turned"""
        x, y = self.position
        return [(x + dx, y + dy) for dx, dy in self._turned().squares]

    def zone_squares(self) -> Dict[str, Shape]:
        """The grid squares this item's zones cover, once turned and placed"""
        x, y = self.position
        turned = self._turned()
        return {
            "star": [(x + dx, y + dy) for dx, dy in turned.star],
            "diamond": [(x + dx, y + dy) for dx, dy in turned.diamond],
        }

    def stored(self) -> Item:
        """The same item, taken off the grid and put in the chest"""
        return Item(**self.item_fields())
