"""
Improved item effects system with proper separation of concerns
Triggers determine WHEN effects happen
Effects determine WHAT happens
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar, List, Optional, Tuple

from grid_system import ItemShape

# battle_engine imports this module, so the simulator can only be named for
# type checking. Same arrangement as event_system.py.
if TYPE_CHECKING:
    from battle_engine import BattleSimulator

# ============= EFFECTS (What happens) =============


class Effect(ABC):
    """Base class for all effects"""

    @abstractmethod
    def apply(self, source, target, battle_state: "BattleSimulator"):
        """Apply this effect"""
        pass


@dataclass
class AttackEffect(Effect):
    """Deal damage to target"""

    min_damage: int
    max_damage: int
    accuracy: float = 0.85
    crit_chance: float = 0.05
    special: Optional[str] = None  # "bypass_block", "crash", etc

    def apply(self, source, target, battle_state: "BattleSimulator"):
        # Battle system will implement damage dealing
        return {
            "type": "attack",
            "min_damage": self.min_damage,
            "max_damage": self.max_damage,
            "accuracy": self.accuracy,
            "crit_chance": self.crit_chance,
            "special": self.special,
        }


@dataclass
class HealEffect(Effect):
    """Heal the target"""

    min_heal: int
    max_heal: int
    target_type: str = "self"  # "self", "lowest_ally", "all_allies"

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {
            "type": "heal",
            "min_heal": self.min_heal,
            "max_heal": self.max_heal,
            "target_type": self.target_type,
        }


@dataclass
class BlockEffect(Effect):
    """Gain Block, the resource that absorbs damage a point at a time."""

    block_amount: int
    target_type: str = "self"

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {
            "type": "block",
            "amount": self.block_amount,
            "target_type": self.target_type,
        }


@dataclass
class PreventDamageEffect(Effect):
    """Stop an incoming attack dead, up to `amount`.

    Not the same thing as Block, though both reduce damage. Block is a
    stacking resource that absorbs 1 damage per stack and is spent doing it
    (see BlockEffect). This reduces damage on one attack outright and is spent on
    nothing.
    """

    amount: int

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {"type": "prevent_damage", "amount": self.amount}


@dataclass
class CpuDrainEffect(Effect):
    """Take CPU off somebody."""

    amount: float
    target_type: str

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {
            "type": "cpu_drain",
            "amount": self.amount,
            "target_type": self.target_type,
        }


@dataclass
class BuffEffect(Effect):
    """Put stacks of a buff on a player."""

    buff_name: str
    value: float
    target_type: str

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {
            "type": "buff",
            "buff_name": self.buff_name,
            "value": self.value,
            "target_type": self.target_type,
        }


@dataclass
class ModifyEffect(Effect):
    """Change a number on some items.

    "Items inside trigger 10% faster", "+15% accuracy", "costs 1 less CPU".
    Nobody carries these and they do not stack, so they are not buffs. Each
    says which items it reaches, and the engine already keeps a field for it:
    `speed_mult`, `accuracy_bonus`, `damage_mult`, `cpu_discount`.

    Heat looks like a counter-example and is not. Heat is a stack a player
    carries which happens to speed their items up. This is a number on the
    items themselves, carried by no one.
    """

    stat: str
    value: float

    #: Who it reaches, the same word every other effect uses. `star` and
    #: `diamond` are the aura zones an item draws on its own map; `contained`
    #: is what a container holds; `own` is everything the player has.
    target_type: str

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {
            "type": "modify",
            "stat": self.stat,
            "value": self.value,
            "target_type": self.target_type,
        }


@dataclass
class ModifyPerEffect(Effect):
    """Change a number on the item projecting the aura, once for each item
    the aura falls on.

    The other direction from ModifyEffect. "Star items trigger 20% faster"
    changes what the zone lands on; "Triggers 15% faster for each Star Food"
    changes the item projecting it, and how much depends on what is standing
    there. 37 items in the source game are written this way against 22 the
    other, so this is the commoner half.

    `counting` narrows what is worth counting: a kind an item carries, or a
    category it belongs to, or empty for anything at all. It reads the same
    tags weapons do, so "nature" and "holy" work as well as "melee".

    Nothing it counts can be changed by another aura -- a kind and a category
    are fixed before a battle -- so it does not matter what order the auras
    are worked out in.
    """

    stat: str
    value: float
    zone: str  # "star" or "diamond"

    #: What is worth counting. `"any"` counts every item standing in the zone.
    #: `{"any": [...]}` counts an item matching any of the tags, and
    #: `{"all": [...]}` one matching every tag. A tag is a kind an item
    #: carries or the category it belongs to, so "nature" and "pet" both work.
    #: An item counts once however many tags it matches.
    counting: object

    def matches(self, tags: set) -> bool:
        """Whether an item carrying `tags` is worth counting."""
        if self.counting == "any":
            return True
        wanted = {t.lower() for t in next(iter(self.counting.values()))}
        return (
            bool(wanted & tags)
            if "any" in self.counting
            else wanted <= tags
        )

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {
            "type": "modify_per",
            "stat": self.stat,
            "value": self.value,
            "zone": self.zone,
            "counting": self.counting,
        }


DEBUFFS = frozenset({"throttled", "memory_leaked", "rate_limited"})

# Section 3.1. Ours for Heat, Empower, Luck, Regeneration, Spikes, Vampirism
# and Mana.
BUFFS = frozenset({
    "optimized",
    "monitored",
    "calibrated",
    "regenerating",
    "spiked",
    "draining",
    "credits",
})

# What an item modifier can change. Each is a field the engine already keeps,
# so a modifier that parses has somewhere to land.
# Names the catalogue uses that nothing implements yet. Listing them is what
# lets an unknown name be a typo rather than a shrug: one of these loads as a
# gap the loader counts, anything else stops the load. Take a name off this
# list when you build it. See BACKLOG.md.
UNBUILT_TRIGGERS = frozenset({
    "on_attack",
    "on_crit",
    "on_damage",
    "on_damage_dealt",
    "on_big_damage",
    "round_start",
})

UNBUILT_EFFECTS = frozenset({
    "adaptive_buff",
    "battle_start",
    "damage_bonus",
    "damage_immunity",
    "damage_reduction",
    "deploy_phase",
    "enemy_debuff",
    "free_refresh",
    "gold_gain",
    "lifesteal",
    "multicast",
    "shop_discount",
    "spawn_companion",
    "special",
})

# How an item deals its damage. An item can carry other tags too -- holy,
# nature, fire -- which say what it is made of rather than how it swings.
WEAPON_KINDS = frozenset({"melee", "ranged", "magic"})

MODIFIER_TARGETS = frozenset({"star", "diamond", "contained", "own"})

MODIFIERS = frozenset({
    "trigger_speed",
    "accuracy",
    "damage",
    "cpu_cost",
    "damage_reduction",
})


@dataclass
class DebuffEffect(Effect):
    """Apply a debuff to enemies"""

    debuff_name: str  # One of DEBUFFS
    value: float
    duration: float = -1  # -1 is "to the end of the battle", which is all of them
    accuracy: float = 1.0
    target_type: str = "enemy"

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {
            "type": "debuff",
            "debuff_name": self.debuff_name,
            "value": self.value,
            "duration": self.duration,
            "accuracy": self.accuracy,
            "target_type": self.target_type,
        }


@dataclass
class ChanceEffect(Effect):
    """One roll, and everything behind it happens or none of it does.

    The source game writes a chance in front of a whole clause -- "12% chance
    to deal +6 damage and gain 1 Heat" -- so this holds effects rather than
    sitting on one. It is ChanceTrigger's shape, a level down: there the roll
    decides whether a trigger fires, here whether part of what it does
    happens.

    Rolling per effect instead would let the damage land and the Heat not,
    which no item in the source game can do.
    """

    chance: float
    effects: List[Effect] = field(default_factory=list)

    def happens(self, battle_state: "BattleSimulator") -> bool:
        return self.chance >= 1.0 or battle_state.rng.random() < self.chance

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {"type": "chance", "chance": self.chance}


@dataclass
class ModifyPerStatusEffect(Effect):
    """Change a number on this item, once for each stack of a status held.

    "Triggers 10% faster for each Luck", "Deals +1 damage for each Blind of
    your opponent". The counting direction of an aura asks the grid; this asks
    the player.
    """

    stat: str
    value: float
    status: str
    whose: str  # "self" or "enemy"

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {"type": "modify_per_status", "stat": self.stat,
                "value": self.value, "status": self.status, "whose": self.whose}


@dataclass
class EffectDamageEffect(Effect):
    """Damage that is not an attack.

    It does not roll for accuracy, no shield answers it and Block does not
    absorb it -- there is no weapon involved. `lifesteal` heals the owner that
    share of what lands, which is how the source game writes it: "Deal 10
    Effect-damage with 100% lifesteal".
    """

    amount: float
    lifesteal: float

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {"type": "effect_damage", "amount": self.amount,
                "lifesteal": self.lifesteal}


@dataclass
class MaxHealthEffect(Effect):
    """Raise the ceiling, and heal by the same amount.

    Gaining maximum health in the source game gives you the health with it,
    rather than leaving a gap to fill.
    """

    amount: int

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {"type": "max_health", "amount": self.amount}


@dataclass
class CleanseEffect(Effect):
    """Take N of a status off somebody.

    Two axes, and every combination works: what to take -- a buff or a debuff,
    named or any -- and who to take it from. Taking a debuff off yourself is
    called "cleanse" and taking a buff off your opponent is called "remove",
    but that is the wording differing, not the mechanic.
    """

    count: int

    #: What to take: "debuff" or "buff" for any of that kind, or the name of
    #: one. A name says which kind it is by itself, since no buff and debuff
    #: share one, so there is nothing to state twice and no way to write the
    #: contradiction that two fields allowed.
    removes: str

    target_type: str  # "self" or "enemy"

    def named(self) -> bool:
        """Whether it takes one particular status rather than any"""
        return self.removes not in ("debuff", "buff")

    def kind(self) -> str:
        """Which pool it draws from: `debuff` or `buff`"""
        if not self.named():
            return self.removes
        return "debuff" if self.removes in DEBUFFS else "buff"

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {
            "type": "cleanse",
            "count": self.count,
            "removes": self.removes,
            "named": self.named(),
            "kind": self.kind(),
            "target_type": self.target_type,
        }


@dataclass
class StunEffect(Effect):
    """Prevent target from acting"""

    stun_duration: float
    accuracy: float = 0.5
    target_type: str = "enemy"

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {
            "type": "stun",
            "duration": self.stun_duration,
            "accuracy": self.accuracy,
            "target_type": self.target_type,
        }


@dataclass
class ReflectEffect(Effect):
    """Reflect damage back to attacker"""

    reflect_percent: float  # 0.3 = 30% reflect

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {"type": "reflect", "percent": self.reflect_percent}


@dataclass
class StatModEffect(Effect):
    """Modify a stat (passive effect)"""

    stat_name: str  # "max_cpu", "cpu_regen", "max_health"
    value: float

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {"type": "stat_mod", "stat": self.stat_name, "value": self.value}


@dataclass
class ConsumeEffect(Effect):
    """Consume the item (remove it from battle)"""

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {
            "type": "consume",
            "item_id": source.uid if hasattr(source, "uid") else None,
        }


# ============= TRIGGERS (When effects happen) =============


class Trigger(ABC):
    """Base class for all triggers

    **A field the item catalogue supplies has no default.** The catalogue is
    transcribed by hand from a wiki, and a default cannot be told apart from
    a transcription that lost a value -- which is how a shield came to roll
    30% for 8 with no CPU drain, and an on-hit effect came to have no chance.
    An item that genuinely has no value for something writes it anyway: `0`
    for a shield that takes no CPU, `1.0` for an effect that always happens.

    Runtime state is different and keeps its default. `fired` and
    `current_cooldown` are the engine's own bookkeeping, not something an
    item can say.
    """

    def __init__(self, effects: List[Effect] = None):
        self.effects = effects or []

    @abstractmethod
    def should_activate(
        self, event_type: str, source, target, battle_state: "BattleSimulator"
    ) -> bool:
        """Check if this trigger should activate"""
        pass

    @abstractmethod
    def get_cpu_cost(self) -> float:
        """Get CPU cost for this trigger"""
        pass


@dataclass
class TimerTrigger(Trigger):
    """Activates on a timer"""

    cooldown: float
    cpu_cost: float
    effects: List[Effect] = field(default_factory=list)

    # Runtime state
    current_cooldown: float = 0.0

    def should_activate(
        self, event_type: str, source, target, battle_state: "BattleSimulator"
    ) -> bool:
        if event_type != "timer_tick":
            return False
        return self.current_cooldown <= 0

    def get_cpu_cost(self) -> float:
        return self.cpu_cost


@dataclass
class BattleStartTrigger(Trigger):
    """Activates once at battle start"""

    effects: List[Effect] = field(default_factory=list)

    def should_activate(
        self, event_type: str, source, target, battle_state: "BattleSimulator"
    ) -> bool:
        return event_type == "battle_start"

    def get_cpu_cost(self) -> float:
        return 0  # Battle start effects are usually free


@dataclass
class HealthThresholdTrigger(Trigger):
    """Fires once, when the owner's health falls past a fraction of its
    maximum.

    **Falling past the line is the trigger, not being below it.** Nearly every
    item with one says "(once)" in its text, and the ones that do not consume
    themselves instead, which comes to the same thing. This is why `fired` is
    part of the trigger rather than left to a `ConsumeEffect` to imply: an
    item that heals below 50% and is not a potion would otherwise heal on
    every tick it spent down there.

    **It is not a damage trigger**, though it is easy to mistake for one.
    So it is checked wherever health falls rather than raised as an event
    by whatever did the falling
    """

    threshold: float  # Fraction of max health, so 0.5 is "below 50%"
    effects: List[Effect] = field(default_factory=list)

    # Runtime state, cleared between battles by rebuilding the spec
    fired: bool = False

    def should_activate(
        self, event_type: str, source, target, battle_state: "BattleSimulator"
    ) -> bool:
        if event_type != "health_threshold" or self.fired:
            return False
        # The first time health is under the line is the moment it crossed,
        # since a battle starts at full health.
        return target.quota < self.threshold * target.max_quota

    def get_cpu_cost(self) -> float:
        return 0  # Nothing is spent noticing your own health


@dataclass
class DamageDealtTrigger(Trigger):
    """Activates when this item deals damage"""

    chance: float = 1.0  # Chance to trigger
    effects: List[Effect] = field(default_factory=list)

    def should_activate(
        self, event_type: str, source, target, battle_state: "BattleSimulator"
    ) -> bool:
        if event_type != "damage_dealt":
            return False
        return battle_state.rng.random() < self.chance

    def get_cpu_cost(self) -> float:
        return 0  # On-hit effects are usually free


@dataclass
class ChanceTrigger(Trigger):
    """A trigger that fires its effects based on a % chance"""

    chance: float
    effects: List[Effect] = field(default_factory=list)

    # The event this trigger answers to. Subclasses name it.
    event_name: ClassVar[str] = ""

    def should_activate(
        self, event_type: str, source, target, battle_state: "BattleSimulator"
    ) -> bool:
        if event_type != self.event_name:
            return False
        if self.chance >= 1.0:
            return True
        return battle_state.rng.random() < self.chance

    def get_cpu_cost(self) -> float:
        return 0  # Whatever caused the event has already paid


@dataclass
class OnHitTrigger(ChanceTrigger):
    """Activates when this item's attack hits. Doesn't fire after a miss."""
    event_name: ClassVar[str] = "on_hit"


@dataclass
class OnAttackedTrigger(ChanceTrigger):
    """Activates when the owner is attacked, and the attack hit.

    It says which kinds of attack reach it. Every shield in the source game is
    written "On attacked (Melee)", and three are "(Melee/Ranged)", so it is a
    property of the shield rather than a rule about shields.
    """

    event_name: ClassVar[str] = "on_attacked"

    #: The weapon kinds this answers to. Anything else passes it by.
    answers_to: frozenset = frozenset()


@dataclass
class AuraTrigger(Trigger):
    """Fires when an item standing in this item's zone activates.

    The third direction an aura works. The other two treat a zone as somewhere
    to reach -- what it falls on, and what it counts. Here the zone is the
    cause: "Star item activates:", "6 Star item activations:".

    `after` is how many activations it waits for, so 1 fires on every one and
    6 fires on every sixth. `counting` is the same syntax the counting
    direction uses, so a trigger can wait on any item or only on a Food.
    """

    zone: str = "star"
    counting: object = "any"
    after: int = 1
    effects: List[Effect] = field(default_factory=list)

    # Runtime state: how many have happened since it last fired.
    seen: int = 0

    def matches(self, tags: set) -> bool:
        """Whether an item carrying `tags` is one this waits on."""
        if self.counting == "any":
            return True
        wanted = {t.lower() for t in next(iter(self.counting.values()))}
        return bool(wanted & tags) if "any" in self.counting else wanted <= tags

    def should_activate(
        self, event_type: str, source, target, battle_state: "BattleSimulator"
    ) -> bool:
        return event_type == "item_activated"

    def get_cpu_cost(self) -> int:
        return 0  # The item that activated has already paid


@dataclass
class AfterTrigger(Trigger):
    """Fires once, a fixed time into the battle. "After 12s: ..."

    Not a cooldown. A timer trigger reschedules itself forever; this one is
    scheduled at the start and never again.
    """

    delay: float = 0.0
    effects: List[Effect] = field(default_factory=list)

    def should_activate(
        self, event_type: str, source, target, battle_state: "BattleSimulator"
    ) -> bool:
        return event_type == "after"

    def get_cpu_cost(self) -> int:
        return 0


@dataclass
class OnAttackTrigger(ChanceTrigger):
    """Fires whenever this item attacks, whether it hits or misses.

    The sibling of OnHitTrigger, and the distinction matters: "'On attack'
    effects will always trigger when a weapon successfully attempts to attack
    (AKA when not out of stamina)." A miss still counts.
    """

    event_name: ClassVar[str] = "on_attack"


@dataclass
class PassiveTrigger(Trigger):
    """Always active (for stat modifications)"""

    effects: List[Effect] = field(default_factory=list)

    def should_activate(
        self, event_type: str, source, target, battle_state: "BattleSimulator"
    ) -> bool:
        return event_type == "passive_apply"

    def get_cpu_cost(self) -> float:
        return 0  # Passives don't cost CPU


@dataclass
class KillTrigger(Trigger):
    """Activates when this item gets a kill"""

    effects: List[Effect] = field(default_factory=list)

    def should_activate(
        self, event_type: str, source, target, battle_state: "BattleSimulator"
    ) -> bool:
        return event_type == "enemy_killed"

    def get_cpu_cost(self) -> float:
        return 0  # Kill effects are usually free


# ============= ITEM SPECIFICATION =============


@dataclass(frozen=True)
class Recipe:
    """One way to make an item.

    The ingredients are consumed. A catalyst has to be there and has to be
    touching, but it is still there afterwards -- the Mana Orb that makes a
    Spectral Dagger out of a Dagger is not used up.
    """

    ingredients: Tuple[str, ...]
    catalysts: Tuple[str, ...] = ()

    def parts(self) -> Tuple[str, ...]:
        """Every item the recipe needs on the grid, consumed or not."""
        return self.ingredients + self.catalysts


@dataclass
class ItemSpec:
    """Complete specification for an item"""

    id: str
    name: str
    category: str  # "problem", "defense", "infrastructure"
    player_class: str
    cost: int

    # Shape for multi-square items (required for all items)
    shape: ItemShape
    slug: str

    # List of triggers, each with their own effects
    triggers: List[Trigger] = field(default_factory=list)

    # Item properties
    rarity: str = "common"  # common, uncommon, rare, epic, legendary, godly

    # How the client draws this item while it has no artwork. Both are names,
    # not values: see item_looks.py for the ones that exist. A container has
    # neither, because it is drawn as the ground the items sit on.
    color: str = ""
    pattern: str = ""

    # Whether to make the item available in the shop
    in_shop: bool = True

    # What the item is, as tags: how it swings and what it is made of. Read
    # from the catalogue, where they arrive as one comma-separated string.
    kinds: frozenset = field(default_factory=frozenset)

    @property
    def is_melee(self) -> bool:
        """Whether it swings rather than shooting or casting.

        Spiked and Draining both turn on this, and so does every shield in the
        source game, which rolls only against melee.
        """
        return "melee" in self.kinds

    # The ways this item can be made, if any. Crafting any one of them makes it.
    # Ingredients are consumed; a catalyst is needed but survives. A slug here
    # that is not in the catalogue names an item we do not have, and that
    # recipe can never be completed.
    recipe: Tuple["Recipe", ...] = ()

    # Never sold, however its rarity rolls. Crafting is the only way to get one.
    recipe_only: bool = False

    # Offered only while the player holds this item. Empty means always.
    shop_needs: str = ""

