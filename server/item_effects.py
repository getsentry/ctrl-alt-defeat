"""
Improved item effects system with proper separation of concerns
Triggers determine WHEN effects happen
Effects determine WHAT happens
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional

from grid_system import ItemShape

# ============= EFFECTS (What happens) =============


class Effect(ABC):
    """Base class for all effects"""

    @abstractmethod
    def apply(self, source, target, battle_state):
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

    def apply(self, source, target, battle_state):
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

    def apply(self, source, target, battle_state):
        return {
            "type": "heal",
            "min_heal": self.min_heal,
            "max_heal": self.max_heal,
            "target_type": self.target_type,
        }


@dataclass
class BlockEffect(Effect):
    """Add block/shield to target"""

    block_amount: int
    target_type: str = "self"

    def apply(self, source, target, battle_state):
        return {
            "type": "block",
            "amount": self.block_amount,
            "target_type": self.target_type,
        }


@dataclass
class BuffEffect(Effect):
    """Apply a buff"""

    buff_name: str  # "speed", "damage", "accuracy", etc
    value: float
    duration: Optional[float] = None  # None = permanent
    target_type: str = "self"

    def apply(self, source, target, battle_state):
        return {
            "type": "buff",
            "buff_name": self.buff_name,
            "value": self.value,
            "duration": self.duration,
            "target_type": self.target_type,
        }


@dataclass
class DebuffEffect(Effect):
    """Apply a debuff to enemies"""

    debuff_name: str  # "slow", "vulnerable", "poison", etc
    value: float
    duration: float
    accuracy: float = 1.0
    target_type: str = "enemy"

    def apply(self, source, target, battle_state):
        return {
            "type": "debuff",
            "debuff_name": self.debuff_name,
            "value": self.value,
            "duration": self.duration,
            "accuracy": self.accuracy,
            "target_type": self.target_type,
        }


@dataclass
class StunEffect(Effect):
    """Prevent target from acting"""

    stun_duration: float
    accuracy: float = 0.5
    target_type: str = "enemy"

    def apply(self, source, target, battle_state):
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

    def apply(self, source, target, battle_state):
        return {"type": "reflect", "percent": self.reflect_percent}


@dataclass
class StatModEffect(Effect):
    """Modify a stat (passive effect)"""

    stat_name: str  # "max_cpu", "cpu_regen", "max_health"
    value: float

    def apply(self, source, target, battle_state):
        return {"type": "stat_mod", "stat": self.stat_name, "value": self.value}


@dataclass
class ConsumeEffect(Effect):
    """Consume the item (remove it from battle)"""

    def apply(self, source, target, battle_state):
        return {
            "type": "consume",
            "item_id": source.uid if hasattr(source, "uid") else None,
        }


# ============= TRIGGERS (When effects happen) =============


class Trigger(ABC):
    """Base class for all triggers"""

    def __init__(self, effects: List[Effect] = None):
        self.effects = effects or []

    @abstractmethod
    def should_activate(self, event_type: str, source, target, battle_state) -> bool:
        """Check if this trigger should activate"""
        pass

    @abstractmethod
    def get_cpu_cost(self) -> int:
        """Get CPU cost for this trigger"""
        pass


@dataclass
class TimerTrigger(Trigger):
    """Activates on a timer"""

    cooldown: float
    cpu_cost: int
    effects: List[Effect] = field(default_factory=list)

    # Runtime state
    current_cooldown: float = 0.0

    def should_activate(self, event_type: str, source, target, battle_state) -> bool:
        if event_type != "timer_tick":
            return False
        return self.current_cooldown <= 0

    def get_cpu_cost(self) -> int:
        return self.cpu_cost


@dataclass
class BattleStartTrigger(Trigger):
    """Activates once at battle start"""

    effects: List[Effect] = field(default_factory=list)

    def should_activate(self, event_type: str, source, target, battle_state) -> bool:
        return event_type == "battle_start"

    def get_cpu_cost(self) -> int:
        return 0  # Battle start effects are usually free


@dataclass
class DamageTakenTrigger(Trigger):
    """Activates when owner takes damage"""

    threshold: Optional[float] = None  # Only activate below X% health
    cooldown: float = 0.0  # Optional cooldown
    cpu_cost: int = 0
    effects: List[Effect] = field(default_factory=list)

    # Runtime state
    current_cooldown: float = 0.0

    def should_activate(self, event_type: str, source, target, battle_state) -> bool:
        if event_type != "damage_taken":
            return False
        if self.current_cooldown > 0:
            return False
        if self.threshold:
            # Check if health is below threshold
            health_percent = target.quota / target.max_quota
            return health_percent < self.threshold
        return True

    def get_cpu_cost(self) -> int:
        return self.cpu_cost


@dataclass
class DamageDealtTrigger(Trigger):
    """Activates when this item deals damage"""

    chance: float = 1.0  # Chance to trigger
    effects: List[Effect] = field(default_factory=list)

    def should_activate(self, event_type: str, source, target, battle_state) -> bool:
        if event_type != "damage_dealt":
            return False
        import random

        # Use battle_state's RNG if available, otherwise fall back to random
        rng = getattr(battle_state, "rng", random)
        return rng.random() < self.chance

    def get_cpu_cost(self) -> int:
        return 0  # On-hit effects are usually free


@dataclass
class PassiveTrigger(Trigger):
    """Always active (for stat modifications)"""

    effects: List[Effect] = field(default_factory=list)

    def should_activate(self, event_type: str, source, target, battle_state) -> bool:
        return event_type == "passive_apply"

    def get_cpu_cost(self) -> int:
        return 0  # Passives don't cost CPU


@dataclass
class KillTrigger(Trigger):
    """Activates when this item gets a kill"""

    effects: List[Effect] = field(default_factory=list)

    def should_activate(self, event_type: str, source, target, battle_state) -> bool:
        return event_type == "enemy_killed"

    def get_cpu_cost(self) -> int:
        return 0  # Kill effects are usually free


# ============= ITEM SPECIFICATION =============


@dataclass
class ItemSpec:
    """Complete specification for an item"""

    id: str
    name: str
    category: str  # "problem", "defense", "infrastructure"

    # Shape for multi-square items (required for all items)
    shape: ItemShape
    slug: str

    # List of triggers, each with their own effects
    triggers: List[Trigger] = field(default_factory=list)

    # Item properties
    rarity: str = "common"  # common, uncommon, rare, epic, legendary, godly

    # Adjacency bonuses this item provides to neighbors
    adjacency_bonus: Optional[dict] = None


# ============= EXAMPLE ITEMS =============


def create_example_items():
    """Create example items from JSON configuration or fallback to hardcoded"""
    from config_loader import create_items_from_config

    return create_items_from_config()
