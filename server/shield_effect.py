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


def create_shield_items():
    """Create example shield items matching Backpack Battles mechanics"""
    from item_effects import BuffEffect, ItemSpec, PassiveTrigger

    # Common Shield - Error Monitoring
    error_monitoring_shield = ItemSpec(
        id="error_monitoring_shield",
        name="Error Monitoring Shield",
        category="defense",
        triggers=[
            OnAttackedTrigger(
                effects=[
                    ShieldBlockEffect(block_chance=0.3, block_amount=8, cpu_steal=0.5)
                ]
            ),
            PassiveTrigger(
                effects=[
                    BuffEffect(
                        buff_name="accuracy_bonus",
                        value=0.1,
                        target_type="adjacent_problems",
                    )
                ]
            ),
        ],
        rarity="common",
    )

    # Uncommon Shield - Session Replay Shield
    session_replay_shield = ItemSpec(
        id="session_replay_shield",
        name="Session Replay Shield",
        category="defense",
        triggers=[
            OnAttackedTrigger(
                effects=[
                    ShieldBlockEffect(
                        block_chance=0.3,
                        block_amount=10,
                        cpu_steal=0.3,
                        counter_effect="reflect_30",
                    )
                ]
            )
        ],
        rarity="uncommon",
    )

    # Rare Shield - Firewall
    firewall_shield = ItemSpec(
        id="firewall_shield",
        name="Firewall",
        category="defense",
        triggers=[
            OnAttackedTrigger(
                effects=[
                    ShieldBlockEffect(
                        block_chance=0.3,
                        block_amount=12,
                        cpu_steal=0.7,
                        counter_effect="apply_throttled",
                    )
                ]
            ),
            PassiveTrigger(
                effects=[
                    BuffEffect(
                        buff_name="block_bonus", value=2, target_type="adjacent_shields"
                    )
                ]
            ),
        ],
        rarity="rare",
    )

    # Epic Shield - Distributed Denial Shield
    ddos_shield = ItemSpec(
        id="ddos_shield",
        name="DDoS Protection",
        category="defense",
        triggers=[
            OnAttackedTrigger(
                effects=[
                    ShieldBlockEffect(
                        block_chance=0.35,  # Slightly higher chance
                        block_amount=14,
                        cpu_steal=1.0,
                        counter_effect="crash_attacker",
                    )
                ]
            )
        ],
        rarity="epic",
    )

    # Legendary Shield - Quantum Firewall
    quantum_firewall = ItemSpec(
        id="quantum_firewall",
        name="Quantum Firewall",
        category="defense",
        triggers=[
            OnAttackedTrigger(
                effects=[
                    ShieldBlockEffect(
                        block_chance=0.4,  # 40% chance
                        block_amount=16,
                        cpu_steal=1.5,
                        counter_effect="teleport_damage",  # Redirects damage to random enemy
                    )
                ]
            ),
            PassiveTrigger(
                effects=[
                    BuffEffect(
                        buff_name="shield_share",
                        value=0.1,  # All shields gain +10% block chance
                        target_type="all_shields",
                    )
                ]
            ),
        ],
        rarity="legendary",
    )

    return {
        "error_monitoring_shield": error_monitoring_shield,
        "session_replay_shield": session_replay_shield,
        "firewall_shield": firewall_shield,
        "ddos_shield": ddos_shield,
        "quantum_firewall": quantum_firewall,
    }
