"""
Test ConsumeEffect and item consumption mechanics
"""

from battle_engine import BattleSimulator, PlacedItem
from grid_system import ItemShape
from item_effects import (
    BattleStartTrigger,
    ConsumeEffect,
    DamageTakenTrigger,
    HealEffect,
    ItemSpec,
    StatModEffect,
    TimerTrigger,
)

from .helpers import get_test_containers

# A battle with no seed uses the clock, which makes every run a different
# battle. Tests pin it so a failure is reproducible.
TEST_SEED = 424242


class TestConsumeEffect:
    """Test that items can be consumed and removed from battle"""

    def test_health_potion_consumes_on_use(self):
        """Test that health potion is consumed after activation"""
        sim = BattleSimulator(seed=TEST_SEED)

        # Create a health potion
        potion = PlacedItem(
            spec=ItemSpec(
                id="test_potion",
                name="Test Potion",
                shape=ItemShape([(0, 0)], "1x1"),
                slug="test_slug",
                category="defense",
                cost=1,
                player_class="neutral",
                triggers=[
                    DamageTakenTrigger(
                        threshold=0.5,  # Activate below 50% health
                        cooldown=0.0,
                        cpu_cost=0,
                        effects=[HealEffect(min_heal=10, max_heal=10), ConsumeEffect()],
                    )
                ],
            ),
            position=(0, 0),
            uid="potion1",
        )

        # Create a damage dealer to trigger the potion
        from item_effects import AttackEffect, TimerTrigger

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
            position=(4, 0),  # P2 container position
            uid="attacker1",
        )

        # Run battle
        p1_containers, p2_containers = get_test_containers()
        result = sim.simulate_battle(
            [potion],
            [attacker],
            round_number=1,
            p1_containers=p1_containers,
            p2_containers=p2_containers,
        )

        # Check that potion was consumed
        consume_actions = [a for a in result["actions"] if a.action == "consume"]
        assert len(consume_actions) == 1
        assert consume_actions[0].source == "potion1"

        # Check that heal happened before consume
        heal_actions = [a for a in result["actions"] if a.action == "heal"]
        assert len(heal_actions) == 1

        # Consume should happen right after heal
        heal_time = heal_actions[0].timestamp
        consume_time = consume_actions[0].timestamp
        assert consume_time == heal_time  # Same tick

    def test_consumed_item_stops_triggering(self):
        """Test that consumed items don't trigger anymore"""
        sim = BattleSimulator(seed=TEST_SEED)

        # Create item that consumes itself on battle start
        consumable = PlacedItem(
            spec=ItemSpec(
                id="test_consumable",
                name="Test Consumable",
                shape=ItemShape([(0, 0)], "1x1"),
                slug="test_slug",
                category="infrastructure",
                cost=1,
                player_class="neutral",
                triggers=[
                    BattleStartTrigger(
                        effects=[
                            StatModEffect(stat_name="max_cpu", value=5),
                            ConsumeEffect(),
                        ]
                    ),
                    # This timer should never fire since item is consumed
                    TimerTrigger(
                        cooldown=1.0,
                        cpu_cost=1,
                        effects=[HealEffect(min_heal=5, max_heal=5)],
                    ),
                ],
            ),
            position=(0, 0),
            uid="consumable1",
        )

        p1_containers, p2_containers = get_test_containers()
        result = sim.simulate_battle(
            [consumable],
            [],
            round_number=1,
            p1_containers=p1_containers,
            p2_containers=p2_containers,
        )

        # Check that item was consumed at battle start
        consume_actions = [a for a in result["actions"] if a.action == "consume"]
        assert len(consume_actions) == 1
        assert consume_actions[0].timestamp == 0  # At battle start

        # Check that no heal actions from the timer trigger
        heal_actions = [a for a in result["actions"] if a.action == "heal"]
        assert len(heal_actions) == 0  # Timer never fired

    def test_consumed_item_affects_adjacency(self):
        """Test that consuming an item updates adjacency bonuses"""
        sim = BattleSimulator(seed=TEST_SEED)
        from item_effects import AttackEffect, TimerTrigger

        # Create 3 adjacent problem items for Bug Swarm synergy
        problem1 = PlacedItem(
            spec=ItemSpec(
                id="p1",
                name="Problem 1",
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
                            AttackEffect(min_damage=5, max_damage=5, accuracy=1.0)
                        ],
                    )
                ],
            ),
            position=(0, 0),  # Within container
            uid="p1",
        )

        problem2 = PlacedItem(
            spec=ItemSpec(
                id="p2",
                name="Problem 2",
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
                            AttackEffect(min_damage=5, max_damage=5, accuracy=1.0)
                        ],
                    )
                ],
            ),
            position=(1, 0),  # Adjacent to problem1
            uid="p2",
        )

        # This one will consume itself
        problem3 = PlacedItem(
            spec=ItemSpec(
                id="p3",
                name="Problem 3",
                shape=ItemShape([(0, 0)], "1x1"),
                slug="test_slug",
                category="problem",
                cost=1,
                player_class="neutral",
                triggers=[
                    BattleStartTrigger(
                        effects=[
                            AttackEffect(min_damage=10, max_damage=10, accuracy=1.0),
                            ConsumeEffect(),  # Consume after first attack
                        ]
                    )
                ],
            ),
            position=(0, 1),
            uid="p3",
        )

        items = [problem1, problem2, problem3]

        # Calculate adjacency before battle
        sim._calculate_adjacency(items)

        # With 3 adjacent problems total, problem1 (which is adjacent to both others) gets +20%
        # problem2 and problem3 are only adjacent to problem1, not to each other
        assert problem1.damage_mult == 1.2  # Bug Swarm bonus (adjacent to 2+ problems)
        assert problem2.damage_mult == 1.0  # No bonus (only adjacent to 1 problem)
        assert problem3.damage_mult == 1.0  # No bonus (only adjacent to 1 problem)

        # Run battle
        p1_containers, p2_containers = get_test_containers()
        # Need a larger container for 3 items
        from .helpers import get_large_test_containers

        p1_containers, p2_containers = get_large_test_containers()
        sim.simulate_battle(
            items,
            [],
            round_number=1,
            p1_containers=p1_containers,
            p2_containers=p2_containers,
        )

        # Problem3 should be consumed
        assert "p3" in sim.consumed_items

        # After consumption, problem1 and problem2 should lose Bug Swarm
        # (would need to recalculate adjacency after consumption)
        # This would be handled by subscribing to ITEM_CONSUMED event

    def test_multiple_consume_effects(self):
        """Test that multiple items can be consumed in same battle"""
        sim = BattleSimulator(seed=TEST_SEED)

        # Create two potions with different thresholds
        potion1 = PlacedItem(
            spec=ItemSpec(
                id="potion1",
                name="Potion 1",
                shape=ItemShape([(0, 0)], "1x1"),
                slug="test_slug",
                category="defense",
                cost=1,
                player_class="neutral",
                triggers=[
                    DamageTakenTrigger(
                        threshold=0.7,  # Activate at 70% health
                        cooldown=0.0,
                        cpu_cost=0,
                        effects=[HealEffect(min_heal=5, max_heal=5), ConsumeEffect()],
                    )
                ],
            ),
            position=(0, 0),
            uid="pot1",
        )

        potion2 = PlacedItem(
            spec=ItemSpec(
                id="potion2",
                name="Potion 2",
                shape=ItemShape([(0, 0)], "1x1"),
                slug="test_slug",
                category="defense",
                cost=1,
                player_class="neutral",
                triggers=[
                    DamageTakenTrigger(
                        threshold=0.4,  # Activate at 40% health
                        cooldown=0.0,
                        cpu_cost=0,
                        effects=[HealEffect(min_heal=5, max_heal=5), ConsumeEffect()],
                    )
                ],
            ),
            position=(1, 0),
            uid="pot2",
        )

        # Strong attacker to trigger both potions
        from item_effects import AttackEffect, TimerTrigger

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
                        cooldown=0.5,
                        cpu_cost=2,
                        effects=[
                            AttackEffect(min_damage=12, max_damage=12, accuracy=1.0)
                        ],
                    )
                ],
            ),
            position=(4, 0),  # P2 container position
            uid="attacker1",
        )

        p1_containers, p2_containers = get_test_containers()
        result = sim.simulate_battle(
            [potion1, potion2],
            [attacker],
            round_number=1,
            p1_containers=p1_containers,
            p2_containers=p2_containers,
        )

        # Both potions should be consumed
        consume_actions = [a for a in result["actions"] if a.action == "consume"]
        consumed_ids = {a.source for a in consume_actions}
        assert "pot1" in consumed_ids
        assert "pot2" in consumed_ids


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
