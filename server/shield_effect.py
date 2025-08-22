"""
Shield blocking mechanics matching Backpack Battles
Shields have a 30% chance to block attacks and can have additional effects
"""

import random
from dataclasses import dataclass
from typing import Optional

from item_effects import Effect, Trigger


@dataclass
class ShieldBlockEffect(Effect):
    """Shield that blocks damage with a chance"""

    block_chance: float = 0.3  # 30% base chance like Backpack Battles
    block_amount: int = 8  # Amount of damage to block
    cpu_steal: float = 0.0  # Amount of CPU to steal from attacker
    counter_effect: Optional[str] = None  # Additional effect when blocking

    def apply(self, source, target, battle_state):
        """Check if shield blocks and apply effects"""
        # Use battle_state's RNG if available, otherwise fall back to random
        rng = getattr(battle_state, "rng", random)
        if rng.random() < self.block_chance:
            return {
                "type": "shield_block",
                "blocked": True,
                "block_amount": self.block_amount,
                "cpu_steal": self.cpu_steal,
                "counter_effect": self.counter_effect,
            }
        return {"type": "shield_block", "blocked": False}


@dataclass
class OnAttackedTrigger(Trigger):
    """Trigger when this unit is attacked (before damage)"""

    effects: list = None

    def __init__(self, effects=None):
        self.effects = effects or []

    def should_activate(self, event_type: str, source, target, battle_state) -> bool:
        """Activate when attacked"""
        return event_type == "on_attacked"

    def get_cpu_cost(self) -> int:
        return 0  # Shield blocks are free
