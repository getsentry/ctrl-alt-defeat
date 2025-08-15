"""
Item effects system - Items can have multiple effects with different triggers
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict
from enum import Enum

class TriggerType(Enum):
    """When an effect triggers"""
    ON_BATTLE_START = "on_battle_start"
    ON_TIMER = "on_timer"  
    ON_DAMAGED = "on_damaged"  # When this item's owner takes damage
    ON_DEAL_DAMAGE = "on_deal_damage"  # When this item deals damage
    ON_ALLY_DEATH = "on_ally_death"  # When an ally item dies (if items can die)
    ON_ENEMY_DEATH = "on_enemy_death"  # When an enemy item dies
    PASSIVE = "passive"  # Always active (like +max CPU)

class EffectType(Enum):
    """What the effect does"""
    DAMAGE = "damage"  # Deal damage to enemy
    HEAL = "heal"  # Heal owner
    BLOCK = "block"  # Add block/shield
    BUFF = "buff"  # Apply buff to owner/allies
    DEBUFF = "debuff"  # Apply debuff to enemies
    MODIFY_STAT = "modify_stat"  # Change max CPU, CPU regen, etc
    REFLECT = "reflect"  # Reflect damage back
    STUN = "stun"  # Prevent activation
    CLEANSE = "cleanse"  # Remove debuffs
    RESURRECT = "resurrect"  # Bring back defeated items (if applicable)

@dataclass
class ItemEffect:
    """A single effect that an item can have"""
    trigger: TriggerType
    effect_type: EffectType
    
    # Effect parameters
    value: float = 0  # Damage amount, heal amount, buff value, etc
    value_min: Optional[float] = None  # For random ranges
    value_max: Optional[float] = None
    
    # Trigger parameters
    cooldown: float = 0.0  # For ON_TIMER triggers
    cpu_cost: int = 0  # CPU/stamina cost to activate
    accuracy: float = 1.0  # Chance to hit (for damage effects)
    crit_chance: float = 0.05  # Chance for critical hit
    
    # Conditional parameters
    health_threshold: Optional[float] = None  # Only trigger below X% health
    target: str = "enemy"  # "enemy", "self", "all_allies", "all_enemies", "lowest_health_ally"
    
    # Special parameters
    special: Optional[str] = None  # Special behavior like "stacking", "bypass_block"
    duration: float = 0  # For buffs/debuffs
    
    # Runtime state
    current_cooldown: float = 0.0
    stacks: int = 0  # For stacking effects like Memory Leak

@dataclass
class ItemSpec:
    """Complete specification for an item with multiple effects"""
    id: str
    name: str
    category: str  # "problem", "defense", "infrastructure"
    
    # Item can have multiple effects
    effects: List[ItemEffect] = field(default_factory=list)
    
    # Item properties
    tier: int = 1  # 1-3
    rarity: str = "common"  # common/uncommon/rare/epic/legendary
    
    # Adjacency bonuses this item provides
    adjacency_bonus: Optional[Dict[str, float]] = None  # e.g. {"accuracy": 0.1}

# Example items with multiple effects
EXAMPLE_ITEMS = {
    "null_pointer": ItemSpec(
        id="null_pointer",
        name="Null Pointer Exception",
        category="problem",
        effects=[
            ItemEffect(
                trigger=TriggerType.ON_TIMER,
                effect_type=EffectType.DAMAGE,
                value_min=4,
                value_max=8,
                cooldown=2.5,
                cpu_cost=3,
                accuracy=0.85,
                special="crash"  # 20% chance to crash for 15 damage on crit
            )
        ],
        rarity="common"
    ),
    
    "error_monitoring": ItemSpec(
        id="error_monitoring",
        name="Error Monitoring",
        category="defense",
        effects=[
            ItemEffect(
                trigger=TriggerType.ON_BATTLE_START,
                effect_type=EffectType.BLOCK,
                value=5,
                target="self"
            ),
            ItemEffect(
                trigger=TriggerType.PASSIVE,
                effect_type=EffectType.BUFF,
                special="adjacent_accuracy",  # Adjacent problems gain +10% accuracy
                value=0.1
            )
        ],
        rarity="common"
    ),
    
    "session_replay": ItemSpec(
        id="session_replay",
        name="Session Replay",
        category="defense",
        effects=[
            ItemEffect(
                trigger=TriggerType.ON_DAMAGED,
                effect_type=EffectType.REFLECT,
                value=0.3,  # Reflect 30% of damage
                cpu_cost=0,
                target="attacker"
            ),
            ItemEffect(
                trigger=TriggerType.ON_TIMER,
                effect_type=EffectType.DAMAGE,
                value=3,  # Can also replay recorded attacks
                cooldown=5.0,
                cpu_cost=2,
                special="replay_last_attack"
            )
        ],
        rarity="uncommon"
    ),
    
    "hybrid_weapon": ItemSpec(
        id="hybrid_weapon",
        name="Hybrid Attacker",
        category="problem",
        effects=[
            # Main attack
            ItemEffect(
                trigger=TriggerType.ON_TIMER,
                effect_type=EffectType.DAMAGE,
                value_min=5,
                value_max=10,
                cooldown=3.0,
                cpu_cost=4,
                accuracy=0.9
            ),
            # Bonus damage on battle start
            ItemEffect(
                trigger=TriggerType.ON_BATTLE_START,
                effect_type=EffectType.DAMAGE,
                value=8,
                cpu_cost=0,
                accuracy=1.0
            ),
            # Heal when low health
            ItemEffect(
                trigger=TriggerType.ON_DAMAGED,
                effect_type=EffectType.HEAL,
                value=3,
                health_threshold=0.3,  # Only when below 30% health
                cpu_cost=2,
                target="self"
            )
        ],
        rarity="epic"
    ),
    
    "load_balancer": ItemSpec(
        id="load_balancer",
        name="Load Balancer",
        category="infrastructure",
        effects=[
            ItemEffect(
                trigger=TriggerType.PASSIVE,
                effect_type=EffectType.MODIFY_STAT,
                special="max_cpu",
                value=5
            ),
            ItemEffect(
                trigger=TriggerType.PASSIVE,
                effect_type=EffectType.BUFF,
                special="distribute_cpu_cost",  # Reduce CPU cost of adjacent items
                value=1
            )
        ],
        rarity="uncommon"
    )
}