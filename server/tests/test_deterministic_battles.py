"""
Test deterministic battle system with seeded RNG
Same seed + same items = same result every time
"""

from copy import deepcopy

import pytest
from battle_engine import BattleSimulator, PlacedItem
from grid_system import ItemShape
from item_effects import AttackEffect, ItemSpec, TimerTrigger
from shield_effect import OnAttackedTrigger, ShieldBlockEffect

from .test_utils import get_test_containers


class TestDeterministicBattles:
    """Test that battles are deterministic with the same seed"""

    def test_same_seed_same_result(self):
        """Test that same seed produces identical battle results"""
        # Create test items
        attacker = PlacedItem(
            spec=ItemSpec(
                id="attacker",
                name="Test Attacker",
                shape=ItemShape([(0, 0)], "1x1"),
                slug="test_slug",
                category="problem",
                player_class="neutral",
                triggers=[
                    TimerTrigger(
                        cooldown=1.0,
                        cpu_cost=2,
                        effects=[
                            AttackEffect(
                                min_damage=3,
                                max_damage=10,
                                accuracy=0.8,
                                crit_chance=0.2,
                            )
                        ],
                    )
                ],
            ),
            position=(0, 0),
            uid="attacker1",
        )

        defender = PlacedItem(
            spec=ItemSpec(
                id="defender",
                name="Test Defender",
                shape=ItemShape([(0, 0)], "1x1"),
                slug="test_slug",
                category="problem",
                player_class="neutral",
                triggers=[
                    TimerTrigger(
                        cooldown=1.5,
                        cpu_cost=3,
                        effects=[
                            AttackEffect(
                                min_damage=4,
                                max_damage=8,
                                accuracy=0.9,
                                crit_chance=0.1,
                            )
                        ],
                    )
                ],
            ),
            position=(4, 0),  # P2 container position
            uid="defender1",
        )

        # Run battle with seed 12345
        sim1 = BattleSimulator(seed=12345)
        p1_containers, p2_containers = get_test_containers()
        result1 = sim1.simulate_battle(
            [deepcopy(attacker)],
            [deepcopy(defender)],
            round_number=1,
            p1_containers=p1_containers,
            p2_containers=p2_containers,
        )

        # Run again with same seed
        sim2 = BattleSimulator(seed=12345)
        p1_containers, p2_containers = get_test_containers()
        result2 = sim2.simulate_battle(
            [deepcopy(attacker)],
            [deepcopy(defender)],
            round_number=1,
            p1_containers=p1_containers,
            p2_containers=p2_containers,
        )

        # Results should be identical
        assert result1["winner"] == result2["winner"]
        assert result1["duration"] == result2["duration"]
        assert result1["player1_quota"] == result2["player1_quota"]
        assert result1["player2_quota"] == result2["player2_quota"]
        assert result1["seed"] == result2["seed"] == 12345

        # Actions should be identical
        assert len(result1["actions"]) == len(result2["actions"])
        for i, (action1, action2) in enumerate(
            zip(result1["actions"], result2["actions"])
        ):
            assert action1 == action2, f"Action {i} differs: {action1} != {action2}"

    def test_different_seed_different_result(self):
        """Test that different seeds produce different results (probabilistically)"""
        # Create test items with RNG-heavy mechanics
        rng_item = PlacedItem(
            spec=ItemSpec(
                id="rng_heavy",
                name="RNG Heavy",
                shape=ItemShape([(0, 0)], "1x1"),
                slug="test_slug",
                category="problem",
                player_class="neutral",
                triggers=[
                    TimerTrigger(
                        cooldown=0.5,
                        cpu_cost=1,
                        effects=[
                            AttackEffect(
                                min_damage=1,
                                max_damage=20,
                                accuracy=0.5,
                                crit_chance=0.5,
                            )
                        ],
                    )
                ],
            ),
            position=(0, 0),
            uid="rng1",
        )

        # Run with different seeds
        results = []
        for seed in [100, 200, 300, 400, 500]:
            sim = BattleSimulator(seed=seed)
            p1_containers, p2_containers = get_test_containers()
            # Create P2 item at correct position
            p2_rng_item = deepcopy(rng_item)
            p2_rng_item.position = (4, 0)  # P2 container position
            result = sim.simulate_battle(
                [deepcopy(rng_item)],
                [p2_rng_item],
                round_number=1,
                p1_containers=p1_containers,
                p2_containers=p2_containers,
            )
            results.append(result)

        # At least some results should differ
        unique_winners = set(r["winner"] for r in results)
        # unique_durations = set(r["duration"] for r in results)
        unique_quotas = set((r["player1_quota"], r["player2_quota"]) for r in results)

        # With 5 different seeds and high RNG, we should see some variation
        # This could theoretically fail but is extremely unlikely
        assert (
            len(unique_winners) > 1 or len(unique_quotas) > 2
        ), "Different seeds should produce different results"

    def test_shield_blocking_deterministic(self):
        """Test that shield blocking is deterministic with same seed"""
        # Shield with 50% block chance
        shield = PlacedItem(
            spec=ItemSpec(
                id="shield",
                name="Test Shield",
                shape=ItemShape([(0, 0)], "1x1"),
                slug="test_slug",
                category="defense",
                player_class="neutral",
                triggers=[
                    OnAttackedTrigger(
                        effects=[
                            ShieldBlockEffect(
                                block_chance=0.5, block_amount=5  # 50% chance
                            )
                        ]
                    )
                ],
            ),
            position=(0, 0),
            uid="shield1",
        )

        # Fast attacker to trigger many shield checks
        attacker = PlacedItem(
            spec=ItemSpec(
                id="attacker",
                name="Fast Attacker",
                shape=ItemShape([(0, 0)], "1x1"),
                slug="test_slug",
                category="problem",
                player_class="neutral",
                triggers=[
                    TimerTrigger(
                        cooldown=0.3,
                        cpu_cost=1,
                        effects=[
                            AttackEffect(min_damage=3, max_damage=3, accuracy=1.0)
                        ],
                    )
                ],
            ),
            position=(4, 0),  # P2 container position
            uid="attacker1",
        )

        # Run with same seed multiple times
        seed = 54321
        results = []
        for _ in range(3):
            sim = BattleSimulator(seed=seed)
            p1_containers, p2_containers = get_test_containers()
            result = sim.simulate_battle(
                [deepcopy(shield)],
                [deepcopy(attacker)],
                round_number=1,
                p1_containers=p1_containers,
                p2_containers=p2_containers,
            )
            results.append(result)

        # All results should be identical
        for i in range(1, len(results)):
            assert results[0]["winner"] == results[i]["winner"]
            assert results[0]["player1_quota"] == results[i]["player1_quota"]
            assert results[0]["player2_quota"] == results[i]["player2_quota"]

            # Count blocks in each result
            blocks_0 = len([a for a in results[0]["actions"] if a.action == "block"])
            blocks_i = len([a for a in results[i]["actions"] if a.action == "block"])
            assert (
                blocks_0 == blocks_i
            ), f"Block count differs: {blocks_0} != {blocks_i}"

    def test_complex_battle_deterministic(self):
        """Test complex battle with multiple items and effects is deterministic"""
        # Create a complex battle setup
        p1_items = [
            PlacedItem(
                spec=ItemSpec(
                    id="item1",
                    name="Item 1",
                    shape=ItemShape([(0, 0)], "1x1"),
                    slug="test_slug",
                    category="problem",
                    player_class="neutral",
                    triggers=[
                        TimerTrigger(
                            cooldown=1.0,
                            cpu_cost=2,
                            effects=[
                                AttackEffect(
                                    min_damage=2,
                                    max_damage=8,
                                    accuracy=0.7,
                                    crit_chance=0.15,
                                )
                            ],
                        )
                    ],
                ),
                position=(0, 0),
                uid="p1_1",
            ),
            PlacedItem(
                spec=ItemSpec(
                    id="item2",
                    name="Item 2",
                    shape=ItemShape([(0, 0)], "1x1"),
                    slug="test_slug",
                    category="defense",
                    player_class="neutral",
                    triggers=[
                        OnAttackedTrigger(
                            effects=[
                                ShieldBlockEffect(block_chance=0.3, block_amount=4)
                            ]
                        )
                    ],
                ),
                position=(1, 0),
                uid="p1_2",
            ),
        ]

        p2_items = [
            PlacedItem(
                spec=ItemSpec(
                    id="item3",
                    name="Item 3",
                    shape=ItemShape([(0, 0)], "1x1"),
                    slug="test_slug",
                    category="problem",
                    player_class="neutral",
                    triggers=[
                        TimerTrigger(
                            cooldown=0.8,
                            cpu_cost=3,
                            effects=[
                                AttackEffect(
                                    min_damage=3,
                                    max_damage=7,
                                    accuracy=0.85,
                                    crit_chance=0.1,
                                )
                            ],
                        )
                    ],
                ),
                position=(4, 0),  # P2 container position
                uid="p2_1",
            ),
            PlacedItem(
                spec=ItemSpec(
                    id="item4",
                    name="Item 4",
                    shape=ItemShape([(0, 0)], "1x1"),
                    slug="test_slug",
                    category="problem",
                    player_class="neutral",
                    triggers=[
                        TimerTrigger(
                            cooldown=1.2,
                            cpu_cost=2,
                            effects=[
                                AttackEffect(
                                    min_damage=4,
                                    max_damage=6,
                                    accuracy=0.95,
                                    crit_chance=0.05,
                                )
                            ],
                        )
                    ],
                ),
                position=(5, 0),  # P2 container position
                uid="p2_2",
            ),
        ]

        # Run battle with same seed twice
        seed = 999999
        sim1 = BattleSimulator(seed=seed)
        p1_containers, p2_containers = get_test_containers()
        result1 = sim1.simulate_battle(
            deepcopy(p1_items),
            deepcopy(p2_items),
            round_number=1,
            p1_containers=p1_containers,
            p2_containers=p2_containers,
        )

        sim2 = BattleSimulator(seed=seed)
        p1_containers, p2_containers = get_test_containers()
        result2 = sim2.simulate_battle(
            deepcopy(p1_items),
            deepcopy(p2_items),
            round_number=1,
            p1_containers=p1_containers,
            p2_containers=p2_containers,
        )

        # Everything should match
        assert result1["winner"] == result2["winner"]
        assert result1["duration"] == result2["duration"]
        assert result1["player1_quota"] == result2["player1_quota"]
        assert result1["player2_quota"] == result2["player2_quota"]
        assert len(result1["actions"]) == len(result2["actions"])

        # Every action should be identical
        for i, (a1, a2) in enumerate(zip(result1["actions"], result2["actions"])):
            assert a1 == a2, f"Action {i} differs: {a1} != {a2}"

    def test_seed_in_result(self):
        """Test that seed is included in battle result"""
        sim = BattleSimulator(seed=77777)
        item = PlacedItem(
            spec=ItemSpec(
                id="test",
                name="Test",
                shape=ItemShape([(0, 0)], "1x1"),
                slug="test_slug",
                category="problem",
                player_class="neutral",
                triggers=[
                    TimerTrigger(
                        cooldown=1.0,
                        cpu_cost=1,
                        effects=[
                            AttackEffect(min_damage=5, max_damage=5, accuracy=1.0)
                        ],
                    )
                ],
            ),
            position=(0, 0),
        )

        p1_containers, p2_containers = get_test_containers()
        result = sim.simulate_battle(
            [item],
            [],
            round_number=1,
            p1_containers=p1_containers,
            p2_containers=p2_containers,
        )
        assert "seed" in result
        assert result["seed"] == 77777

    def test_auto_generated_seed(self):
        """Test that auto-generated seeds are different"""
        # Create simulators without specifying seed
        sim1 = BattleSimulator()
        sim2 = BattleSimulator()

        # Seeds should be different (extremely high probability)
        assert sim1.seed != sim2.seed

        # Seeds should be valid integers
        assert isinstance(sim1.seed, int)
        assert isinstance(sim2.seed, int)
        assert 0 <= sim1.seed <= 2147483647
        assert 0 <= sim2.seed <= 2147483647


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
