"""
Test full battle scenarios with realistic item loadouts
These tests simulate complete battles between two players with different strategies
"""

from copy import deepcopy

import pytest
from battle_engine import ACTION_CODES, BattleSimulator, PlacedItem, Player
from item_effects import (
    AttackEffect,
    BattleStartTrigger,
    BlockEffect,
    BuffEffect,
    ConsumeEffect,
    DamageTakenTrigger,
    DebuffEffect,
    HealEffect,
    ItemSpec,
    PassiveTrigger,
    StatModEffect,
    TimerTrigger,
    create_example_items,
)
from shield_effect import OnAttackedTrigger, ShieldBlockEffect

from .test_utils import get_large_test_containers, get_test_containers


class TestFullBattleScenarios:
    """Test complete battles with different strategies and loadouts"""

    def test_aggressive_vs_defensive(self):
        """Test aggressive damage dealer vs defensive tank build"""
        # Player 1: Aggressive build (high damage, low defense)
        p1_items = [
            PlacedItem(
                spec=ItemSpec(
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
                                    crit_chance=0.2,
                                )
                            ],
                        )
                    ],
                ),
                position=(0, 0),
                uid="p1_null",
            ),
            PlacedItem(
                spec=ItemSpec(
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
                                    special="stacking",
                                )
                            ],
                        )
                    ],
                ),
                position=(1, 0),  # Adjacent for Bug Swarm
                uid="p1_leak",
            ),
            PlacedItem(
                spec=ItemSpec(
                    id="race_condition",
                    name="Race Condition",
                    category="problem",
                    triggers=[
                        TimerTrigger(
                            cooldown=1.5,
                            cpu_cost=4,
                            effects=[
                                AttackEffect(
                                    min_damage=3,
                                    max_damage=6,
                                    accuracy=0.75,
                                    crit_chance=0.3,
                                )
                            ],
                        )
                    ],
                ),
                position=(0, 1),  # Adjacent for Bug Swarm
                uid="p1_race",
            ),
        ]

        # Player 2: Defensive build (shields, healing, moderate damage)
        p2_items = [
            PlacedItem(
                spec=ItemSpec(
                    id="error_shield",
                    name="Error Monitoring Shield",
                    category="defense",
                    triggers=[
                        OnAttackedTrigger(
                            effects=[
                                ShieldBlockEffect(
                                    block_chance=0.3, block_amount=8, cpu_steal=0.5
                                )
                            ]
                        )
                    ],
                ),
                position=(3, 0),
                uid="p2_shield1",
            ),
            PlacedItem(
                spec=ItemSpec(
                    id="firewall",
                    name="Firewall",
                    category="defense",
                    triggers=[
                        OnAttackedTrigger(
                            effects=[
                                ShieldBlockEffect(
                                    block_chance=0.3, block_amount=10, cpu_steal=0.7
                                )
                            ]
                        )
                    ],
                ),
                position=(4, 0),  # Adjacent shields
                uid="p2_shield2",
            ),
            PlacedItem(
                spec=ItemSpec(
                    id="health_check",
                    name="Health Check",
                    category="infrastructure",
                    triggers=[
                        TimerTrigger(
                            cooldown=4.0,
                            cpu_cost=2,
                            effects=[HealEffect(min_heal=3, max_heal=5)],
                        )
                    ],
                ),
                position=(3, 1),
                uid="p2_heal",
            ),
            PlacedItem(
                spec=ItemSpec(
                    id="counter_attack",
                    name="Counter Attack",
                    category="problem",
                    triggers=[
                        TimerTrigger(
                            cooldown=3.0,
                            cpu_cost=3,
                            effects=[
                                AttackEffect(min_damage=5, max_damage=7, accuracy=0.9)
                            ],
                        )
                    ],
                ),
                position=(5, 0),
                uid="p2_counter",
            ),
        ]

        # Run battle with fixed seed for consistency
        sim = BattleSimulator(seed=12345)
        p1_containers, p2_containers = get_large_test_containers()
        result = sim.simulate_battle(
            p1_items,
            p2_items,
            round_number=5,
            p1_containers=p1_containers,
            p2_containers=p2_containers,
        )

        # Battle should complete
        assert result["winner"] in [1, 2]
        assert result["duration"] <= 60.0

        # Check that appropriate actions occurred
        actions = result["actions"]
        damage_actions = [a for a in actions if a["a"] == ACTION_CODES["DAMAGE"]]
        block_actions = [a for a in actions if a["a"] == ACTION_CODES["BLOCK"]]
        heal_actions = [a for a in actions if a["a"] == ACTION_CODES["HEAL"]]

        # Should have damage from both sides
        p1_damage = [a for a in damage_actions if a["p"] == 2]
        p2_damage = [a for a in damage_actions if a["p"] == 1]
        assert len(p1_damage) > 0, "Player 1 should deal damage"
        assert len(p2_damage) > 0, "Player 2 should deal damage"

        # Defensive player should have blocks and heals
        assert len(block_actions) > 0, "Shields should block some attacks"
        assert len(heal_actions) > 0, "Health Check should heal"

    def test_synergy_focused_builds(self):
        """Test builds that rely on item synergies"""
        # Player 1: Bug Swarm synergy (3+ problems adjacent)
        p1_items = [
            PlacedItem(
                spec=ItemSpec(
                    id="bug1",
                    name="Bug 1",
                    category="problem",
                    triggers=[
                        TimerTrigger(
                            cooldown=2.0,
                            cpu_cost=2,
                            effects=[
                                AttackEffect(min_damage=3, max_damage=5, accuracy=0.85)
                            ],
                        )
                    ],
                ),
                position=(0, 0),  # Top-left of P1 container
                uid="p1_bug1",
            ),
            PlacedItem(
                spec=ItemSpec(
                    id="bug2",
                    name="Bug 2",
                    category="problem",
                    triggers=[
                        TimerTrigger(
                            cooldown=2.0,
                            cpu_cost=2,
                            effects=[
                                AttackEffect(min_damage=3, max_damage=5, accuracy=0.85)
                            ],
                        )
                    ],
                ),
                position=(1, 0),  # Adjacent (right)
                uid="p1_bug2",
            ),
            PlacedItem(
                spec=ItemSpec(
                    id="bug3",
                    name="Bug 3",
                    category="problem",
                    triggers=[
                        TimerTrigger(
                            cooldown=2.0,
                            cpu_cost=2,
                            effects=[
                                AttackEffect(min_damage=3, max_damage=5, accuracy=0.85)
                            ],
                        )
                    ],
                ),
                position=(0, 1),  # Adjacent (below)
                uid="p1_bug3",
            ),
        ]

        # Player 2: Mixed synergy (Full Stack: problem + defense + infrastructure)
        p2_items = [
            PlacedItem(
                spec=ItemSpec(
                    id="problem",
                    name="Problem",
                    category="problem",
                    triggers=[
                        TimerTrigger(
                            cooldown=1.8,
                            cpu_cost=3,
                            effects=[
                                AttackEffect(min_damage=4, max_damage=6, accuracy=0.9)
                            ],
                        )
                    ],
                ),
                position=(4, 0),  # P2 container top-left
                uid="p2_problem",
            ),
            PlacedItem(
                spec=ItemSpec(
                    id="defense",
                    name="Defense",
                    category="defense",
                    triggers=[
                        OnAttackedTrigger(
                            effects=[
                                ShieldBlockEffect(block_chance=0.4, block_amount=6)
                            ]
                        )
                    ],
                ),
                position=(5, 0),  # Adjacent in P2
                uid="p2_defense",
            ),
            PlacedItem(
                spec=ItemSpec(
                    id="infrastructure",
                    name="Infrastructure",
                    category="infrastructure",
                    triggers=[
                        PassiveTrigger(
                            effects=[StatModEffect(stat_name="max_cpu", value=5)]
                        )
                    ],
                ),
                position=(4, 1),  # Adjacent in P2
                uid="p2_infra",
            ),
        ]

        sim = BattleSimulator(seed=54321)
        p1_containers, p2_containers = get_large_test_containers()
        result = sim.simulate_battle(
            p1_items,
            p2_items,
            round_number=3,
            p1_containers=p1_containers,
            p2_containers=p2_containers,
        )

        # Battle should complete
        assert result["winner"] in [1, 2]

        # Check that synergies were applied (would need to check damage multipliers)
        # Bug Swarm should give +20% damage to p1_bug1 (center bug adjacent to 2 others)
        # Full Stack should give +30% speed to p2_problem

    def test_consumable_heavy_battle(self):
        """Test battle with consumable items (potions)"""
        # Player 1: Standard damage with health potions
        p1_items = [
            PlacedItem(
                spec=ItemSpec(
                    id="attacker",
                    name="Attacker",
                    category="problem",
                    triggers=[
                        TimerTrigger(
                            cooldown=2.0,
                            cpu_cost=3,
                            effects=[
                                AttackEffect(min_damage=6, max_damage=8, accuracy=0.9)
                            ],
                        )
                    ],
                ),
                position=(0, 0),
                uid="p1_attack",
            ),
            PlacedItem(
                spec=ItemSpec(
                    id="health_potion",
                    name="Health Potion",
                    category="defense",
                    triggers=[
                        DamageTakenTrigger(
                            threshold=0.5,  # Activate at 50% health
                            cooldown=0.0,
                            cpu_cost=0,
                            effects=[
                                HealEffect(min_heal=15, max_heal=20),
                                ConsumeEffect(),
                            ],
                        )
                    ],
                ),
                position=(1, 0),
                uid="p1_pot1",
            ),
            PlacedItem(
                spec=ItemSpec(
                    id="emergency_heal",
                    name="Emergency Heal",
                    category="defense",
                    triggers=[
                        DamageTakenTrigger(
                            threshold=0.2,  # Activate at 20% health
                            cooldown=0.0,
                            cpu_cost=0,
                            effects=[
                                HealEffect(min_heal=25, max_heal=30),
                                ConsumeEffect(),
                            ],
                        )
                    ],
                ),
                position=(0, 1),
                uid="p1_pot2",
            ),
        ]

        # Player 2: Burst damage with CPU booster
        p2_items = [
            PlacedItem(
                spec=ItemSpec(
                    id="cpu_booster",
                    name="CPU Booster",
                    category="infrastructure",
                    triggers=[
                        BattleStartTrigger(
                            effects=[
                                StatModEffect(stat_name="max_cpu", value=10),
                                ConsumeEffect(),
                            ]
                        )
                    ],
                ),
                position=(3, 0),
                uid="p2_boost",
            ),
            PlacedItem(
                spec=ItemSpec(
                    id="heavy_hitter",
                    name="Heavy Hitter",
                    category="problem",
                    triggers=[
                        TimerTrigger(
                            cooldown=1.5,
                            cpu_cost=5,  # High CPU cost
                            effects=[
                                AttackEffect(min_damage=8, max_damage=12, accuracy=0.85)
                            ],
                        )
                    ],
                ),
                position=(4, 0),
                uid="p2_heavy",
            ),
            PlacedItem(
                spec=ItemSpec(
                    id="quick_strike",
                    name="Quick Strike",
                    category="problem",
                    triggers=[
                        TimerTrigger(
                            cooldown=1.0,
                            cpu_cost=4,
                            effects=[
                                AttackEffect(min_damage=4, max_damage=6, accuracy=0.95)
                            ],
                        )
                    ],
                ),
                position=(3, 1),
                uid="p2_quick",
            ),
        ]

        sim = BattleSimulator(seed=99999)
        p1_containers, p2_containers = get_large_test_containers()
        result = sim.simulate_battle(
            p1_items,
            p2_items,
            round_number=7,
            p1_containers=p1_containers,
            p2_containers=p2_containers,
        )

        # Check that consumables were used
        consume_actions = [a for a in result["actions"] if a.get("a") == "consume"]
        assert len(consume_actions) > 0, "Some items should be consumed"

        # CPU booster should be consumed at battle start
        cpu_boost_consume = [a for a in consume_actions if a.get("i") == "p2_boost"]
        assert len(cpu_boost_consume) == 1
        assert cpu_boost_consume[0]["t"] == 0  # At battle start

    def test_late_game_high_powered_battle(self):
        """Test late game battle with high-powered items and high health"""
        # Player 1: Strong upgraded items
        p1_items = [
            PlacedItem(
                spec=ItemSpec(
                    id="upgraded_weapon",
                    name="Upgraded Weapon",
                    category="problem",
                    rarity="rare",
                    triggers=[
                        TimerTrigger(
                            cooldown=2.5,
                            cpu_cost=4,
                            effects=[
                                AttackEffect(min_damage=8, max_damage=12, accuracy=0.9)
                            ],  # High damage
                        )
                    ],
                ),
                position=(0, 0),
                uid="p1_weapon",
            ),
            PlacedItem(
                spec=ItemSpec(
                    id="upgraded_shield",
                    name="Upgraded Shield",
                    category="defense",
                    rarity="rare",
                    triggers=[
                        OnAttackedTrigger(
                            effects=[
                                ShieldBlockEffect(block_chance=0.4, block_amount=12)
                            ]
                        )
                    ],
                ),
                position=(1, 0),
                uid="p1_shield",
            ),
        ]

        # Player 2: Single very powerful item
        p2_items = [
            PlacedItem(
                spec=ItemSpec(
                    id="legendary_weapon",
                    name="Legendary Weapon",
                    category="problem",
                    rarity="legendary",
                    triggers=[
                        TimerTrigger(
                            cooldown=3.0,
                            cpu_cost=5,
                            effects=[
                                AttackEffect(
                                    min_damage=10,
                                    max_damage=15,
                                    accuracy=0.85,
                                    crit_chance=0.25,
                                )
                            ],  # Very high damage
                        )
                    ],
                ),
                position=(4, 0),  # P2 container position
                uid="p2_legendary",
            )
        ]

        # Late game round (round 15) - 100 health each
        sim = BattleSimulator(seed=111111)
        p1_containers, p2_containers = get_test_containers()
        result = sim.simulate_battle(
            p1_items,
            p2_items,
            round_number=15,
            p1_containers=p1_containers,
            p2_containers=p2_containers,
        )

        # Battle should take longer with higher health
        assert result["winner"] in [1, 2]

        # Check that high-powered items deal appropriate damage
        damage_actions = [
            a for a in result["actions"] if a["a"] == ACTION_CODES["DAMAGE"]
        ]

        # Upgraded weapon should deal 8-12 damage
        # Legendary weapon should deal 10-15 damage
        p2_legendary_damage = [
            a for a in damage_actions if a.get("i") == "p2_legendary" and a["p"] == 1
        ]
        if p2_legendary_damage:
            # Filter out 0 damage (blocked attacks) and get all damage values
            all_hits = [a["v"] for a in p2_legendary_damage]
            successful_hits = [v for v in all_hits if v > 0]

            if successful_hits:
                # Legendary weapon: 10-15 damage
                min_damage = min(successful_hits)
                max_damage = max(successful_hits)

                # Account for shields potentially blocking part of the damage
                # Just ensure we're seeing appropriate damage values
                assert (
                    max_damage >= 10
                ), f"Legendary weapon max damage should be at least 10, got {max_damage}"

    def test_fatigue_mechanic_stalemate(self):
        """Test that fatigue prevents infinite battles"""
        # Both players: Defensive builds with healing
        p1_items = [
            PlacedItem(
                spec=ItemSpec(
                    id="weak_attack",
                    name="Weak Attack",
                    category="problem",
                    triggers=[
                        TimerTrigger(
                            cooldown=3.0,
                            cpu_cost=2,
                            effects=[
                                AttackEffect(min_damage=2, max_damage=3, accuracy=0.95)
                            ],
                        )
                    ],
                ),
                position=(0, 0),
                uid="p1_weak",
            ),
            PlacedItem(
                spec=ItemSpec(
                    id="healer",
                    name="Healer",
                    category="infrastructure",
                    triggers=[
                        TimerTrigger(
                            cooldown=2.5,
                            cpu_cost=2,
                            effects=[HealEffect(min_heal=2, max_heal=3)],
                        )
                    ],
                ),
                position=(1, 0),
                uid="p1_heal",
            ),
        ]

        p2_items = [
            PlacedItem(
                spec=ItemSpec(
                    id="weak_attack2",
                    name="Weak Attack 2",
                    category="problem",
                    triggers=[
                        TimerTrigger(
                            cooldown=3.0,
                            cpu_cost=2,
                            effects=[
                                AttackEffect(min_damage=2, max_damage=3, accuracy=0.95)
                            ],
                        )
                    ],
                ),
                position=(4, 0),
                uid="p2_weak",
            ),
            PlacedItem(
                spec=ItemSpec(
                    id="healer2",
                    name="Healer 2",
                    category="infrastructure",
                    triggers=[
                        TimerTrigger(
                            cooldown=2.5,
                            cpu_cost=2,
                            effects=[HealEffect(min_heal=2, max_heal=3)],
                        )
                    ],
                ),
                position=(5, 0),
                uid="p2_heal",
            ),
        ]

        sim = BattleSimulator(seed=222222)
        p1_containers, p2_containers = get_test_containers()
        result = sim.simulate_battle(
            p1_items,
            p2_items,
            round_number=1,
            p1_containers=p1_containers,
            p2_containers=p2_containers,
        )

        # Battle should end despite healing (fatigue or timeout)
        assert result["winner"] in [1, 2]
        assert result["duration"] <= 60.0

        # After 30 seconds, fatigue should increase damage
        late_damage = [
            a
            for a in result["actions"]
            if a["a"] == ACTION_CODES["DAMAGE"] and a["t"] > 30
        ]
        if late_damage:
            # Damage should be higher than base (2-3) due to fatigue
            late_damage_values = [a["v"] for a in late_damage]
            max_late_damage = max(late_damage_values)
            assert max_late_damage > 3, "Fatigue should increase damage after 30s"

    def test_cpu_management_battle(self):
        """Test battle where CPU management is critical"""
        # Player 1: High CPU consumption build
        p1_items = [
            PlacedItem(
                spec=ItemSpec(
                    id="expensive1",
                    name="Expensive 1",
                    category="problem",
                    triggers=[
                        TimerTrigger(
                            cooldown=1.0,
                            cpu_cost=6,  # High cost
                            effects=[
                                AttackEffect(min_damage=7, max_damage=9, accuracy=0.9)
                            ],
                        )
                    ],
                ),
                position=(0, 0),
                uid="p1_exp1",
            ),
            PlacedItem(
                spec=ItemSpec(
                    id="expensive2",
                    name="Expensive 2",
                    category="problem",
                    triggers=[
                        TimerTrigger(
                            cooldown=1.2,
                            cpu_cost=5,
                            effects=[
                                AttackEffect(min_damage=6, max_damage=8, accuracy=0.85)
                            ],
                        )
                    ],
                ),
                position=(1, 0),
                uid="p1_exp2",
            ),
        ]

        # Player 2: Efficient build with CPU infrastructure
        p2_items = [
            PlacedItem(
                spec=ItemSpec(
                    id="cpu_infrastructure",
                    name="CPU Infrastructure",
                    category="infrastructure",
                    triggers=[
                        PassiveTrigger(
                            effects=[
                                StatModEffect(stat_name="max_cpu", value=8),
                                StatModEffect(stat_name="cpu_regen", value=2),
                            ]
                        )
                    ],
                ),
                position=(3, 0),
                uid="p2_cpu",
            ),
            PlacedItem(
                spec=ItemSpec(
                    id="efficient1",
                    name="Efficient 1",
                    category="problem",
                    triggers=[
                        TimerTrigger(
                            cooldown=1.5,
                            cpu_cost=2,  # Low cost
                            effects=[
                                AttackEffect(min_damage=4, max_damage=5, accuracy=0.95)
                            ],
                        )
                    ],
                ),
                position=(4, 0),
                uid="p2_eff1",
            ),
            PlacedItem(
                spec=ItemSpec(
                    id="efficient2",
                    name="Efficient 2",
                    category="problem",
                    triggers=[
                        TimerTrigger(
                            cooldown=1.5,
                            cpu_cost=2,
                            effects=[
                                AttackEffect(min_damage=4, max_damage=5, accuracy=0.95)
                            ],
                        )
                    ],
                ),
                position=(3, 1),
                uid="p2_eff2",
            ),
        ]

        sim = BattleSimulator(seed=333333)
        p1_containers, p2_containers = get_large_test_containers()
        result = sim.simulate_battle(
            p1_items,
            p2_items,
            round_number=5,
            p1_containers=p1_containers,
            p2_containers=p2_containers,
        )

        # Check CPU throttling
        cpu_fails = [a for a in result["actions"] if a["a"] == ACTION_CODES["CPU_FAIL"]]

        # Player 1 should have CPU failures due to high costs
        p1_cpu_fails = [a for a in cpu_fails if a["p"] == 1]
        assert len(p1_cpu_fails) > 0, "Player 1 should experience CPU throttling"

        # Player 2 should have fewer or no CPU failures due to infrastructure
        p2_cpu_fails = [a for a in cpu_fails if a["p"] == 2]
        assert len(p2_cpu_fails) < len(
            p1_cpu_fails
        ), "Player 2 should have better CPU management"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
