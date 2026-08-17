"""
Items: everything the player can buy, keep in the chest, or place on the grid.

An item's numbers all come from its spec in the JSON catalogue, so `Item.of` is
the one place that reads a spec. Every item the server sends carries the same
fields, whether it sits in the shop, in the chest or on the grid.

An item on the grid also has a position and a rotation, and that is the only
difference between the two types. So a position is never null, and nothing has
to work out what a missing one means.
"""

from pydantic import BaseModel, Field, computed_field

from config_loader import config_loader
from grid_system import ItemShape, Rotation
from item_effects import ItemSpec
from utils import Position, Shape

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
    description: str = Field(description="What the item does, in prose")
    color: str = Field(description="Palette colour name, empty on a container")
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
            description=describe(stats),
            color=spec.color,
            pattern=spec.pattern,
            **stats.model_dump(),
        )

    @computed_field
    @property
    def price(self) -> int:
        """What buying it costs right now. Sent, so the shop cannot show
        one number while the server charges another."""
        return sale_price(self.cost) if self.on_sale else self.cost

    @property
    def sell_value(self) -> int:
        """What selling it pays, whether or not it was bought on sale.

        Not sent: nothing on the client shows it yet.
        """
        return sale_price(self.cost)

    def _item_fields(self) -> dict:
        """Just the fields an Item has, so a placed item can be rebuilt"""
        return {k: v for k, v in self.model_dump().items() if k in Item.model_fields}

    def placed_at(
        self, position: Position, rotation: Rotation = Rotation.NONE
    ) -> "PlacedItem":
        """The same item, now on the grid. Works on a placed item too."""
        return PlacedItem(
            **self._item_fields(),
            position=position,
            rotation=rotation,
        )


class PlacedItem(Item):
    """An item on the grid. It is the only kind that has a place and a facing."""

    position: Position = Field(description="[x, y] anchor on the grid")
    rotation: Rotation = Field(
        default=Rotation.NONE, description="Quarter turns clockwise from the shape"
    )

    def covered_squares(self) -> Shape:
        """The grid squares this item covers, once turned"""
        squares = self.shape
        if self.rotation is not Rotation.NONE:
            squares = ItemShape(squares=list(squares)).rotate(self.rotation).squares
        x, y = self.position
        return [(x + dx, y + dy) for dx, dy in squares]

    def stored(self) -> Item:
        """The same item, taken off the grid and put in the chest"""
        return Item(**self._item_fields())
