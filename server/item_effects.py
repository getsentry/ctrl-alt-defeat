"""
Improved item effects system with proper separation of concerns
Triggers determine WHEN effects happen
Effects determine WHAT happens
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar, List, Optional

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
    """Apply a buff"""

    buff_name: str  # "speed", "damage", "accuracy", etc
    value: float
    duration: Optional[float] = None  # None = permanent
    target_type: str = "self"

    def apply(self, source, target, battle_state: "BattleSimulator"):
        return {
            "type": "buff",
            "buff_name": self.buff_name,
            "value": self.value,
            "duration": self.duration,
            "target_type": self.target_type,
        }


DEBUFFS = frozenset({"throttled", "memory_leaked", "rate_limited"})


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
    """Activates when the owner is attacked, and the attack hit."""

    event_name: ClassVar[str] = "on_attacked"


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

