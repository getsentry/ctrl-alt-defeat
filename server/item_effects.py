"""
Improved item effects system with proper separation of concerns
Triggers determine WHEN effects happen
Effects determine WHAT happens
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, List, Optional

from grid_system import SHAPES

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

    # List of triggers, each with their own effects
    triggers: List[Trigger] = field(default_factory=list)

    # Item properties
    rarity: str = "common"  # common, uncommon, rare, epic, legendary, godly

    # Shape for multi-square items (None = default 1x1)
    shape: Optional[Any] = None  # ItemShape from grid_system

    # Adjacency bonuses this item provides to neighbors
    adjacency_bonus: Optional[dict] = None


# ============= EXAMPLE ITEMS =============


def create_example_items():
    """Create example items with the new system"""

    null_pointer = ItemSpec(
        id="null_pointer",
        name="Null Pointer Exception",
        category="problem",
        triggers=[
            TimerTrigger(
                cooldown=2.5,
                cpu_cost=3,
                effects=[
                    AttackEffect(
                        min_damage=4,
                        max_damage=8,
                        accuracy=0.85,
                        crit_chance=0.05,
                        special="crash",  # 20% to deal 15 damage on crit
                    )
                ],
            )
        ],
        rarity="common",
    )

    error_monitoring = ItemSpec(
        id="error_monitoring",
        name="Error Monitoring",
        category="defense",
        triggers=[
            BattleStartTrigger(
                effects=[BlockEffect(block_amount=5, target_type="self")]
            ),
            PassiveTrigger(
                effects=[
                    BuffEffect(
                        buff_name="adjacent_accuracy",
                        value=0.1,
                        target_type="adjacent_problems",
                    )
                ]
            ),
        ],
        rarity="common",
    )

    session_replay = ItemSpec(
        id="session_replay",
        name="Session Replay",
        category="defense",
        triggers=[
            DamageTakenTrigger(
                threshold=None,  # Always triggers
                cpu_cost=0,
                effects=[ReflectEffect(reflect_percent=0.3)],
            ),
            TimerTrigger(
                cooldown=5.0,
                cpu_cost=2,
                effects=[
                    AttackEffect(
                        min_damage=3,
                        max_damage=3,
                        accuracy=1.0,
                        special="replay",  # Replays last recorded attack
                    )
                ],
            ),
        ],
        rarity="uncommon",
    )

    alerting_system = ItemSpec(
        id="alerting_system",
        name="Alerting System",
        category="defense",
        triggers=[
            DamageTakenTrigger(
                threshold=0.3,  # Only when below 30% health
                cooldown=8.0,
                cpu_cost=3,
                effects=[
                    HealEffect(min_heal=5, max_heal=5, target_type="self"),
                    BlockEffect(block_amount=3, target_type="self"),
                ],
            )
        ],
        rarity="rare",
    )

    memory_leak = ItemSpec(
        id="memory_leak",
        name="Memory Leak",
        category="problem",
        triggers=[
            TimerTrigger(
                cooldown=3.0,
                cpu_cost=2,
                effects=[
                    AttackEffect(
                        min_damage=2,
                        max_damage=4,
                        accuracy=0.95,
                        special="stacking",  # Damage increases each hit
                    ),
                    DebuffEffect(
                        debuff_name="memory_leaked", value=1, duration=5.0, accuracy=1.0
                    ),
                ],
            )
        ],
        rarity="uncommon",
    )

    hybrid_assassin = ItemSpec(
        id="hybrid_assassin",
        name="Hybrid Assassin",
        category="problem",
        triggers=[
            # Opening burst
            BattleStartTrigger(
                effects=[AttackEffect(min_damage=10, max_damage=15, accuracy=1.0)]
            ),
            # Regular attacks
            TimerTrigger(
                cooldown=2.0,
                cpu_cost=4,
                effects=[
                    AttackEffect(min_damage=5, max_damage=8, accuracy=0.9),
                    StunEffect(stun_duration=0.5, accuracy=0.2),
                ],
            ),
            # Execute on low health enemies
            DamageDealtTrigger(
                chance=1.0,
                effects=[
                    AttackEffect(
                        min_damage=20,
                        max_damage=20,
                        accuracy=1.0,
                        special="execute_low_health",  # Only if target < 20% HP
                    )
                ],
            ),
        ],
        rarity="legendary",
    )

    load_balancer = ItemSpec(
        id="load_balancer",
        name="Load Balancer",
        category="infrastructure",
        triggers=[
            PassiveTrigger(
                effects=[
                    StatModEffect(stat_name="max_cpu", value=5),
                    BuffEffect(
                        buff_name="cpu_cost_reduction", value=1, target_type="adjacent"
                    ),
                ]
            )
        ],
        rarity="uncommon",
    )

    race_condition = ItemSpec(
        id="race_condition",
        name="Race Condition",
        category="problem",
        triggers=[
            TimerTrigger(
                cooldown=2.0,
                cpu_cost=4,
                effects=[
                    AttackEffect(
                        min_damage=6,
                        max_damage=10,
                        accuracy=0.70,
                        crit_chance=0.05,
                        special="double_strike",  # If faster than opponent
                    )
                ],
            )
        ],
        rarity="rare",
    )

    sql_injection = ItemSpec(
        id="sql_injection",
        name="SQL Injection",
        category="problem",
        triggers=[
            TimerTrigger(
                cooldown=4.0,
                cpu_cost=5,
                effects=[
                    AttackEffect(
                        min_damage=8,
                        max_damage=12,
                        accuracy=0.80,
                        crit_chance=0.05,
                        special="bypass_block",  # Bypasses 50% of blocks
                    )
                ],
            )
        ],
        rarity="rare",
    )

    redis_cache = ItemSpec(
        id="redis_cache",
        name="Redis Cache",
        category="infrastructure",
        triggers=[
            PassiveTrigger(
                effects=[
                    StatModEffect(stat_name="cpu_regen", value=3)  # +3 stamina regen
                ]
            )
        ],
        rarity="common",
    )

    database = ItemSpec(
        id="database",
        name="Database",
        category="infrastructure",
        triggers=[
            PassiveTrigger(
                effects=[StatModEffect(stat_name="max_cpu", value=8)]  # +8 max stamina
            )
        ],
        rarity="uncommon",
    )

    cdn = ItemSpec(
        id="cdn",
        name="CDN",
        category="infrastructure",
        triggers=[
            PassiveTrigger(
                effects=[
                    BuffEffect(
                        buff_name="global_speed",
                        value=0.15,  # 15% faster activation
                        target_type="all",
                    )
                ]
            )
        ],
        rarity="rare",
    )

    performance_monitoring = ItemSpec(
        id="performance_monitoring",
        name="Performance Monitoring",
        category="defense",
        triggers=[
            TimerTrigger(
                cooldown=10.0,
                cpu_cost=2,
                effects=[
                    BuffEffect(
                        buff_name="speed",
                        value=0.2,  # +20% speed to all
                        target_type="all",
                    )
                ],
            )
        ],
        rarity="uncommon",
    )

    # Example consumable items (potions)
    health_potion = ItemSpec(
        id="health_potion",
        name="Health Potion",
        category="defense",
        triggers=[
            DamageTakenTrigger(
                threshold=0.5,  # Activate when below 50% health
                cooldown=0.0,  # One-time use
                cpu_cost=0,  # Free to use
                effects=[
                    HealEffect(min_heal=15, max_heal=20, target_type="self"),
                    ConsumeEffect(),  # Remove item after use
                ],
            )
        ],
        rarity="common",
    )

    emergency_repair = ItemSpec(
        id="emergency_repair",
        name="Emergency Repair",
        category="defense",
        triggers=[
            DamageTakenTrigger(
                threshold=0.2,  # Activate when below 20% health (emergency!)
                cooldown=0.0,
                cpu_cost=0,
                effects=[
                    HealEffect(min_heal=30, max_heal=35, target_type="self"),
                    BlockEffect(block_amount=10, target_type="self"),
                    ConsumeEffect(),  # Remove item after use
                ],
            )
        ],
        rarity="rare",
    )

    cpu_booster = ItemSpec(
        id="cpu_booster",
        name="CPU Booster",
        category="infrastructure",
        triggers=[
            BattleStartTrigger(
                effects=[
                    StatModEffect(
                        stat_name="max_cpu", value=10
                    ),  # +10 max CPU for battle
                    ConsumeEffect(),  # Remove item after use
                ]
            )
        ],
        rarity="uncommon",
    )

    # ============= MULTI-SQUARE ITEMS =============

    # 2x2 Items
    server_blade = ItemSpec(
        id="server_blade",
        name="Server Blade",
        category="infrastructure",
        shape=SHAPES["2x2"] if SHAPES else None,  # 2x2 square
        triggers=[
            PassiveTrigger(
                effects=[
                    StatModEffect(
                        stat_name="max_cpu", value=12
                    ),  # More CPU than standard
                    StatModEffect(stat_name="cpu_regen", value=2),
                ]
            )
        ],
        rarity="uncommon",
    )

    database_cluster = ItemSpec(
        id="database_cluster",
        name="Database Cluster",
        category="infrastructure",
        shape=SHAPES["2x3"] if SHAPES else None,  # 2x3 rectangle (6 squares!)
        triggers=[
            PassiveTrigger(
                effects=[
                    StatModEffect(stat_name="max_cpu", value=20),  # Massive CPU boost
                    BuffEffect(
                        buff_name="data_consistency",
                        value=0.1,  # +10% accuracy to all
                        target_type="all",
                    ),
                ]
            )
        ],
        rarity="rare",
    )

    # L-shaped items
    network_cable = ItemSpec(
        id="network_cable",
        name="Network Cable",
        category="infrastructure",
        shape=SHAPES["L_shape"] if SHAPES else None,  # L-shaped (3 squares)
        triggers=[
            PassiveTrigger(
                effects=[
                    BuffEffect(
                        buff_name="connection_speed",
                        value=0.15,  # Adjacent items 15% faster
                        target_type="adjacent",
                    )
                ]
            )
        ],
        rarity="common",
    )

    # Food items with different shapes
    server_pizza = ItemSpec(
        id="server_pizza",
        name="Server Room Pizza",
        category="defense",  # Food is defensive
        shape=SHAPES["pizza_slice"] if SHAPES else None,  # Triangle shape (3 squares)
        triggers=[
            TimerTrigger(
                cooldown=6.0,
                cpu_cost=0,
                effects=[HealEffect(min_heal=4, max_heal=4, target_type="self")],
            )
        ],
        rarity="uncommon",
    )

    debug_donuts = ItemSpec(
        id="debug_donuts",
        name="Debug Donuts",
        category="defense",
        shape=SHAPES["2x2"] if SHAPES else None,  # 2x2 square
        triggers=[
            TimerTrigger(
                cooldown=4.0,
                cpu_cost=0,
                effects=[
                    HealEffect(min_heal=3, max_heal=3, target_type="self"),
                    StatModEffect(stat_name="cpu_regen", value=1),
                ],
            )
        ],
        rarity="rare",
    )

    energy_drink_sixpack = ItemSpec(
        id="energy_drink_sixpack",
        name="Energy Drink Six-Pack",
        category="defense",
        shape=SHAPES["3x2"] if SHAPES else None,  # 3x2 rectangle (6 cans!)
        triggers=[
            TimerTrigger(
                cooldown=3.0,
                cpu_cost=0,
                effects=[
                    StatModEffect(stat_name="cpu_regen", value=4),
                    BuffEffect(
                        buff_name="caffeinated",
                        value=0.2,  # +20% speed
                        duration=5.0,
                        target_type="all",
                    ),
                ],
            )
        ],
        rarity="epic",
    )

    # Large problem items
    distributed_dos = ItemSpec(
        id="distributed_dos",
        name="Distributed DoS Attack",
        category="problem",
        shape=SHAPES["T_shape"] if SHAPES else None,  # T-shaped (4 squares)
        triggers=[
            TimerTrigger(
                cooldown=3.0,
                cpu_cost=5,
                effects=[
                    AttackEffect(
                        min_damage=4,
                        max_damage=6,
                        accuracy=0.95,
                        special="multi_hit",  # Hits from multiple angles
                    ),
                    AttackEffect(min_damage=4, max_damage=6, accuracy=0.95),
                    AttackEffect(min_damage=4, max_damage=6, accuracy=0.95),
                ],
            )
        ],
        rarity="rare",
    )

    kernel_panic = ItemSpec(
        id="kernel_panic",
        name="Kernel Panic",
        category="problem",
        shape=SHAPES["2x2"] if SHAPES else None,  # 2x2 square
        triggers=[
            TimerTrigger(
                cooldown=5.0,
                cpu_cost=8,
                effects=[
                    AttackEffect(
                        min_damage=15,
                        max_damage=20,
                        accuracy=0.75,
                        crit_chance=0.15,
                        special="system_crash",
                    ),
                    StunEffect(stun_duration=1.0, accuracy=0.5),
                ],
            )
        ],
        rarity="epic",
    )

    # Banana-shaped item (homage to Backpack Battles)
    corrupted_data = ItemSpec(
        id="corrupted_data",
        name="Corrupted Data Stream",
        category="problem",
        shape=SHAPES["banana"] if SHAPES else None,  # Curved shape (4 squares)
        triggers=[
            TimerTrigger(
                cooldown=2.5,
                cpu_cost=3,
                effects=[
                    AttackEffect(min_damage=3, max_damage=5, accuracy=0.9),
                    DebuffEffect(
                        debuff_name="data_corruption",
                        value=2,
                        duration=4.0,
                        accuracy=1.0,
                    ),
                ],
            )
        ],
        rarity="uncommon",
    )

    # Large defensive items
    firewall_array = ItemSpec(
        id="firewall_array",
        name="Firewall Array",
        category="defense",
        shape=SHAPES["1x3"] if SHAPES else None,  # 1x3 vertical wall
        triggers=[
            BattleStartTrigger(
                effects=[BlockEffect(block_amount=15, target_type="self")]
            ),
            DamageTakenTrigger(
                threshold=None,
                cpu_cost=0,
                effects=[
                    DebuffEffect(
                        debuff_name="firewall_blocked",
                        value=1,
                        duration=2.0,
                        accuracy=0.3,
                        target_type="attacker",
                    )
                ],
            ),
        ],
        rarity="rare",
    )

    monitoring_dashboard = ItemSpec(
        id="monitoring_dashboard",
        name="Monitoring Dashboard",
        category="defense",
        shape=SHAPES["3x2"] if SHAPES else None,  # 3x2 wide display
        triggers=[
            PassiveTrigger(
                effects=[
                    BuffEffect(
                        buff_name="visibility",
                        value=0.15,  # +15% accuracy to all
                        target_type="all",
                    )
                ]
            ),
            TimerTrigger(
                cooldown=8.0,
                cpu_cost=3,
                effects=[
                    HealEffect(min_heal=8, max_heal=10, target_type="self"),
                    BlockEffect(block_amount=5, target_type="self"),
                ],
            ),
        ],
        rarity="epic",
    )

    return {
        "null_pointer": null_pointer,
        "error_monitoring": error_monitoring,
        "session_replay": session_replay,
        "alerting_system": alerting_system,
        "memory_leak": memory_leak,
        "hybrid_assassin": hybrid_assassin,
        "load_balancer": load_balancer,
        "race_condition": race_condition,
        "sql_injection": sql_injection,
        "redis_cache": redis_cache,
        "database": database,
        "cdn": cdn,
        "performance_monitoring": performance_monitoring,
        "health_potion": health_potion,
        "emergency_repair": emergency_repair,
        "cpu_booster": cpu_booster,
        # Multi-square items
        "server_blade": server_blade,
        "database_cluster": database_cluster,
        "network_cable": network_cable,
        "server_pizza": server_pizza,
        "debug_donuts": debug_donuts,
        "energy_drink_sixpack": energy_drink_sixpack,
        "distributed_dos": distributed_dos,
        "kernel_panic": kernel_panic,
        "corrupted_data": corrupted_data,
        "firewall_array": firewall_array,
        "monitoring_dashboard": monitoring_dashboard,
    }
