"""
Items: everything the player can buy, keep in the chest, or place on the grid.

An item's numbers all come from its spec in the JSON catalogue, so `Item.of` is
the one place that reads a spec. Every item the server sends carries the same
fields, whether it sits in the shop, in the chest or on the grid.

An item on the grid also has a position and a rotation, and that is the only
difference between the two types. So a position is never null, and nothing has
to work out what a missing one means.
"""

from typing import Dict

from pydantic import BaseModel, Field, computed_field, field_validator

from config_loader import config_loader
from grid_system import ItemShape, Rotation
from item_effects import ItemSpec
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
    special_effect: str = ""


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
                if getattr(effect, "special", ""):
                    stats.special_effect = effect.special
            if hasattr(effect, "min_heal"):
                stats.min_heal = max(stats.min_heal, effect.min_heal)
                stats.max_heal = max(stats.max_heal, effect.max_heal)
            if hasattr(effect, "block_amount"):
                stats.block_amount = max(stats.block_amount, effect.block_amount)
    return stats


def describe(stats: ItemStats) -> str:
    """One line of prose about what an item does, for the tooltip"""
    if stats.min_damage > 0:
        text = f"Deals {stats.min_damage}-{stats.max_damage} damage"
        if stats.cooldown > 0:
            text += f" every {stats.cooldown}s"
        if stats.cpu_cost > 0:
            text += f" (costs {stats.cpu_cost} CPU)"
    elif stats.min_heal > 0:
        text = f"Heals {stats.min_heal}-{stats.max_heal} HP"
        if stats.cooldown > 0:
            text += f" every {stats.cooldown}s"
    elif stats.block_amount > 0:
        text = f"Blocks {stats.block_amount} damage when attacked"
    else:
        text = ""

    if stats.special_effect:
        if text:
            return f"{text}. Special: {stats.special_effect}"
        return f"Special: {stats.special_effect}"
    return text


def shape_of(spec: ItemSpec) -> Shape:
    """The squares an item of this spec covers, as offsets from its anchor"""
    return [(x, y) for x, y in spec.shape.squares]


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
    description: str = Field(description="What the item does, in prose")
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
    special_effect: str = Field(description="Special effect name, empty if none")

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
            description=describe(stats),
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
