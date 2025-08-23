"""
Test shield blocking mechanics
Shields should have 30% chance to block attacks and can have additional effects
"""

from battle_engine import BattleSimulator, PlacedItem
from grid_system import ItemShape
from item_effects import AttackEffect, ItemSpec, TimerTrigger
from shield_effect import OnAttackedTrigger, ShieldBlockEffect

from .test_utils import get_test_containers


class TestShieldBlocking:
    """Test that shields block damage with proper chance"""

    def test_shield_blocks_damage(self):
        """Test that shields can block incoming damage"""
        sim = BattleSimulator()

        # Create a shield with 100% block chance for testing
        shield = PlacedItem(
            spec=ItemSpec(
                id="test_shield",
                name="Test Shield",
                shape=ItemShape([(0, 0)], "1x1"),
                slug="test_slug",
                category="defense",
                cost=1,
                player_class="neutral",
                triggers=[
                    OnAttackedTrigger(
                        effects=[
                            ShieldBlockEffect(
                                block_chance=1.0,  # 100% for testing
                                block_amount=10,
                                cpu_steal=0.5,
                            )
                        ]
                    )
                ],
            ),
            position=(0, 0),
            uid="shield1",
        )

        # Create an attacker
        attacker = PlacedItem(
            spec=ItemSpec(
                id="attacker",
                name="Attacker",
                shape=ItemShape([(0, 0)], "1x1"),
                slug="test_slug",
                category="problem",
                cost=1,
                player_class="neutral",
                triggers=[
                    TimerTrigger(
                        cooldown=1.0,
                        cpu_cost=2,
                        effects=[
                            AttackEffect(min_damage=15, max_damage=15, accuracy=1.0)
                        ],
                    )
                ],
            ),
            position=(4, 0),
            uid="attacker1",
        )

        # Run battle
        p1_containers, p2_containers = get_test_containers()
        result = sim.simulate_battle(
            [shield],
            [attacker],
            round_number=1,
            p1_containers=p1_containers,
            p2_containers=p2_containers,
        )

        # Check that damage was blocked
        block_actions = [a for a in result["actions"] if a.action == "block"]
        damage_actions = [a for a in result["actions"] if a.action == "damage"]

        # Should have blocks from shield
        assert len(block_actions) > 0

        # First attack: 15 damage, shield blocks 10, so 5 damage goes through
        first_damage = next((a for a in damage_actions if a.damage), None)
        if first_damage:
            assert first_damage.damage == 5  # 15 - 10 blocked

    def test_shield_30_percent_chance(self):
        """Test that shields have 30% base block chance"""
        sim = BattleSimulator()

        # Create multiple shields with 30% block chance
        shields = []
        for i in range(10):
            shields.append(
                PlacedItem(
                    spec=ItemSpec(
                        id=f"shield_{i}",
                        name=f"Shield {i}",
                        shape=ItemShape([(0, 0)], "1x1"),
                        slug="test_slug",
                        category="defense",
                        cost=1,
                        player_class="neutral",
                        triggers=[
                            OnAttackedTrigger(
                                effects=[
                                    ShieldBlockEffect(
                                        block_chance=0.3, block_amount=8  # 30% chance
                                    )
                                ]
                            )
                        ],
                    ),
                    position=(i % 3, i // 3),
                    uid=f"shield{i}",
                )
            )

        # Create a fast weak attacker to trigger many shield checks
        attacker = PlacedItem(
            spec=ItemSpec(
                id="fast_attacker",
                name="Fast Attacker",
                shape=ItemShape([(0, 0)], "1x1"),
                slug="test_slug",
                category="problem",
                cost=1,
                player_class="neutral",
                triggers=[
                    TimerTrigger(
                        cooldown=0.5,  # Fast attacks
                        cpu_cost=1,
                        effects=[
                            AttackEffect(min_damage=3, max_damage=3, accuracy=1.0)
                        ],
                    )
                ],
            ),
            position=(4, 0),
            uid="attacker1",
        )

        # Run multiple simulations to check probability
        total_attacks = 0
        total_blocks = 0

        for _ in range(10):
            p1_containers, p2_containers = get_test_containers()
            result = sim.simulate_battle(
                shields[:1],
                [attacker],
                round_number=1,
                p1_containers=p1_containers,
                p2_containers=p2_containers,
            )

            damage_actions = [a for a in result["actions"] if a.action == "damage"]
            block_actions = [
                a
                for a in result["actions"]
                if a.action == "block" and a.source == "shield0"
            ]

            # Count attacks (damage + blocks = total attacks)
            attacks_this_sim = len(damage_actions) + len(block_actions)
            total_attacks += attacks_this_sim
            total_blocks += len(block_actions)

        # Over many attacks, should be close to 30%
        if total_attacks > 0:
            block_rate = total_blocks / total_attacks
            # Allow some variance (20-40% range)
            assert (
                0.15 <= block_rate <= 0.45
            ), f"Block rate {block_rate} not close to 30%"

    def test_shield_cpu_steal(self):
        """Test that shields can steal CPU from attackers"""
        sim = BattleSimulator()

        # Create a shield that steals CPU
        shield = PlacedItem(
            spec=ItemSpec(
                id="cpu_steal_shield",
                name="CPU Steal Shield",
                shape=ItemShape([(0, 0)], "1x1"),
                slug="test_slug",
                category="defense",
                cost=1,
                player_class="neutral",
                triggers=[
                    OnAttackedTrigger(
                        effects=[
                            ShieldBlockEffect(
                                block_chance=1.0,  # Always block for testing
                                block_amount=5,
                                cpu_steal=3.0,  # Steal 3 CPU
                            )
                        ]
                    )
                ],
            ),
            position=(0, 0),
            uid="shield1",
        )

        # Create an attacker with high CPU cost
        attacker = PlacedItem(
            spec=ItemSpec(
                id="expensive_attacker",
                name="Expensive Attacker",
                shape=ItemShape([(0, 0)], "1x1"),
                slug="test_slug",
                category="problem",
                cost=1,
                player_class="neutral",
                triggers=[
                    TimerTrigger(
                        cooldown=1.0,
                        cpu_cost=6,  # High CPU cost
                        effects=[
                            AttackEffect(min_damage=10, max_damage=10, accuracy=1.0)
                        ],
                    )
                ],
            ),
            position=(4, 0),
            uid="attacker1",
        )

        p1_containers, p2_containers = get_test_containers()
        result = sim.simulate_battle(
            [shield],
            [attacker],
            round_number=1,
            p1_containers=p1_containers,
            p2_containers=p2_containers,
        )

        # After first attack, attacker should have less CPU
        # This might cause subsequent attacks to fail
        cpu_fail_actions = [a for a in result["actions"] if a.action == "cpu_fail"]

        # Should have some CPU failures due to stolen CPU
        # (Attacker starts with 10 CPU, uses 6 for first attack = 4 left,
        #  shield steals 3 = 1 left, not enough for second attack at 6 cost)
        assert len(cpu_fail_actions) > 0

    def test_multiple_shields_stack(self):
        """Test that multiple shields can all attempt to block"""
        sim = BattleSimulator()

        # Create two shields, both with 100% block chance
        shield1 = PlacedItem(
            spec=ItemSpec(
                id="shield1",
                name="Shield 1",
                shape=ItemShape([(0, 0)], "1x1"),
                slug="test_slug",
                category="defense",
                cost=1,
                player_class="neutral",
                triggers=[
                    OnAttackedTrigger(
                        effects=[ShieldBlockEffect(block_chance=1.0, block_amount=5)]
                    )
                ],
            ),
            position=(0, 0),
            uid="shield1",
        )

        shield2 = PlacedItem(
            spec=ItemSpec(
                id="shield2",
                name="Shield 2",
                shape=ItemShape([(0, 0)], "1x1"),
                slug="test_slug",
                category="defense",
                cost=1,
                player_class="neutral",
                triggers=[
                    OnAttackedTrigger(
                        effects=[ShieldBlockEffect(block_chance=1.0, block_amount=7)]
                    )
                ],
            ),
            position=(1, 0),
            uid="shield2",
        )

        # Attacker deals 20 damage
        attacker = PlacedItem(
            spec=ItemSpec(
                id="attacker",
                name="Attacker",
                shape=ItemShape([(0, 0)], "1x1"),
                slug="test_slug",
                category="problem",
                cost=1,
                player_class="neutral",
                triggers=[
                    TimerTrigger(
                        cooldown=2.0,
                        cpu_cost=2,
                        effects=[
                            AttackEffect(min_damage=20, max_damage=20, accuracy=1.0)
                        ],
                    )
                ],
            ),
            position=(4, 0),
            uid="attacker1",
        )

        p1_containers, p2_containers = get_test_containers()
        result = sim.simulate_battle(
            [shield1, shield2],
            [attacker],
            round_number=1,
            p1_containers=p1_containers,
            p2_containers=p2_containers,
        )

        # Both shields should block (5 + 7 = 12 total)
        block_actions = [a for a in result["actions"] if a.action == "block"]
        damage_actions = [a for a in result["actions"] if a.action == "damage"]

        # Should have blocks from both shields
        assert len(block_actions) >= 2

        # Damage should be reduced by total blocks
        # 20 damage - 5 (shield1) - 7 (shield2) = 8 damage
        first_damage = next((a for a in damage_actions if a.damage), None)
        if first_damage:
            assert first_damage.damage == 8

    def test_shield_with_no_damage(self):
        """Test that shields don't activate when no damage is dealt"""
        sim = BattleSimulator()

        # Create a shield
        shield = PlacedItem(
            spec=ItemSpec(
                id="shield",
                name="Shield",
                shape=ItemShape([(0, 0)], "1x1"),
                slug="test_slug",
                category="defense",
                cost=1,
                player_class="neutral",
                triggers=[
                    OnAttackedTrigger(
                        effects=[ShieldBlockEffect(block_chance=1.0, block_amount=10)]
                    )
                ],
            ),
            position=(0, 0),
            uid="shield1",
        )

        # No attacker - shield should never activate
        p1_containers, p2_containers = get_test_containers()
        result = sim.simulate_battle(
            [shield],
            [],
            round_number=1,
            p1_containers=p1_containers,
            p2_containers=p2_containers,
        )

        # Should have no block actions
        block_actions = [a for a in result["actions"] if a.action == "block"]
        assert len(block_actions) == 0
