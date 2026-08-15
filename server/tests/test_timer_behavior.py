"""
Test timer item behavior with CPU throttling
"""

from battle_engine import BattleItem, BattleSimulator
from grid_system import ItemShape
from item_effects import AttackEffect, ItemSpec, TimerTrigger

from .helpers import get_test_containers

# A battle with no seed uses the clock, which makes every run a different
# battle. Tests pin it so a failure is reproducible.
TEST_SEED = 424242


class TestTimerScheduling:
    """Test that timer items maintain schedule even when CPU throttled"""

    def test_timer_maintains_schedule_when_throttled(self):
        """Timer items should stay on schedule even if CPU isn't available"""
        sim = BattleSimulator(seed=TEST_SEED)

        # Create a high CPU cost item with 1 second cooldown
        item = BattleItem(
            spec=ItemSpec(
                id="test",
                name="Test Item",
                shape=ItemShape([(0, 0)], "1x1"),
                slug="test_slug",
                category="problem",
                cost=1,
                player_class="neutral",
                triggers=[
                    TimerTrigger(
                        cooldown=1.0,  # 1 second cooldown
                        cpu_cost=15,  # More than max CPU (10)
                        effects=[
                            AttackEffect(min_damage=10, max_damage=10, accuracy=1.0)
                        ],
                    )
                ],
            ),
            position=(0, 0),
        )

        # Run battle for 5 seconds
        p1_containers, p2_containers = get_test_containers()
        result = sim.simulate_battle(
            [item],
            [],
            round_number=1,
            p1_containers=p1_containers,
            p2_containers=p2_containers,
        )

        # Count CPU_FAIL actions
        cpu_fails = [a for a in result["actions"] if a.action == "cpu_fail"]

        # With 1 second cooldown over 5 seconds, should attempt ~5 times
        # All should fail due to insufficient CPU
        assert len(cpu_fails) >= 4  # At least 4 attempts

        # Check timing - failures should be ~1 second apart
        if len(cpu_fails) >= 2:
            time_diff = (cpu_fails[1].timestamp - cpu_fails[0].timestamp) / 1000.0
            assert 0.9 <= time_diff <= 1.1  # Within 10% of expected cooldown

    def test_timer_activates_when_cpu_available(self):
        """Timer items should activate when CPU regenerates enough"""
        sim = BattleSimulator(seed=42)  # Fixed seed for deterministic behavior

        # Create item that costs 7 CPU with 1 second cooldown
        # This will sometimes succeed and sometimes fail
        item = BattleItem(
            spec=ItemSpec(
                id="test",
                name="Test Item",
                shape=ItemShape([(0, 0)], "1x1"),
                slug="test_slug",
                category="problem",
                cost=1,
                player_class="neutral",
                triggers=[
                    TimerTrigger(
                        cooldown=1.0,  # 1 second cooldown
                        cpu_cost=7,  # More than half of max CPU
                        effects=[
                            AttackEffect(min_damage=5, max_damage=5, accuracy=1.0)
                        ],
                    )
                ],
            ),
            position=(0, 0),
        )

        # With 2 CPU/sec regen and 7 CPU cost:
        # - First activation at 0s should succeed (start with 10 CPU)
        # - Second attempt at 1s: have 5 CPU (10 - 7 + 2*1), should fail
        # - Third attempt at 2s: have 7 CPU (5 + 2*1), should succeed
        # - Fourth attempt at 3s: have 2 CPU (7 - 7 + 2*1), should fail

        p1_containers, p2_containers = get_test_containers()
        result = sim.simulate_battle(
            [item],
            [],
            round_number=1,
            p1_containers=p1_containers,
            p2_containers=p2_containers,
        )

        # Check for mix of successes and failures
        damages = [a for a in result["actions"] if a.action == "damage"]
        cpu_fails = [a for a in result["actions"] if a.action == "cpu_fail"]

        # Should have some successes and some failures
        assert len(damages) > 0
        assert len(cpu_fails) > 0

        # Verify timing is maintained (all events ~1 second apart)
        all_item_events = sorted(
            [
                a
                for a in result["actions"]
                if hasattr(a, "source") and a.source == item.uid
            ],
            key=lambda x: x.timestamp,
        )

        if len(all_item_events) >= 2:
            # Filter out CPU fail events at same timestamp
            unique_times = []
            seen_times = set()
            for event in all_item_events:
                if event.timestamp not in seen_times:
                    unique_times.append(event.timestamp)
                    seen_times.add(event.timestamp)

            # Check time differences between unique timestamps
            if len(unique_times) >= 2:
                for i in range(1, len(unique_times)):
                    time_diff = (unique_times[i] - unique_times[i - 1]) / 1000.0
                    # Should be close to 1 second cooldown
                    assert (
                        0.8 <= time_diff <= 1.2
                    ), f"Time diff {time_diff} not close to 1.0"

    def test_multiple_items_maintain_independent_schedules(self):
        """Multiple timer items should maintain independent schedules"""
        sim = BattleSimulator(seed=123)  # Fixed seed for deterministic behavior

        # Create two items with different cooldowns (low damage to ensure long battle)
        item1 = BattleItem(
            spec=ItemSpec(
                id="item1",
                name="Fast Item",
                shape=ItemShape([(0, 0)], "1x1"),
                slug="test_slug",
                category="problem",
                cost=1,
                player_class="neutral",
                triggers=[
                    TimerTrigger(
                        cooldown=1.0,  # 1 second
                        cpu_cost=3,
                        effects=[
                            AttackEffect(min_damage=1, max_damage=1, accuracy=1.0)
                        ],
                    )
                ],
            ),
            position=(0, 0),
            uid="item1",
        )

        item2 = BattleItem(
            spec=ItemSpec(
                id="item2",
                name="Slow Item",
                shape=ItemShape([(0, 0)], "1x1"),
                slug="test_slug",
                category="problem",
                cost=1,
                player_class="neutral",
                triggers=[
                    TimerTrigger(
                        cooldown=3.0,  # 3 seconds
                        cpu_cost=4,
                        effects=[
                            AttackEffect(min_damage=1, max_damage=1, accuracy=1.0)
                        ],
                    )
                ],
            ),
            position=(1, 0),
            uid="item2",
        )

        p1_containers, p2_containers = get_test_containers()
        result = sim.simulate_battle(
            [item1, item2],
            [],
            round_number=1,
            p1_containers=p1_containers,
            p2_containers=p2_containers,
        )

        # Get all events for each item
        item1_events = [
            a for a in result["actions"] if hasattr(a, "source") and a.source == "item1"
        ]
        item2_events = [
            a for a in result["actions"] if hasattr(a, "source") and a.source == "item2"
        ]

        # Item1 (1s cooldown) should have ~3x more events than item2 (3s cooldown)
        # Over 6 seconds: item1 ~6 events, item2 ~2 events
        ratio = len(item1_events) / max(1, len(item2_events))
        assert 2.0 <= ratio <= 4.0, f"Event ratio {ratio} not in expected range"

        # Verify each maintains its schedule
        for events, expected_cooldown in [(item1_events, 1.0), (item2_events, 3.0)]:
            sorted_events = sorted(events, key=lambda x: x.timestamp)
            if len(sorted_events) >= 2:
                time_diff = (
                    sorted_events[1].timestamp - sorted_events[0].timestamp
                ) / 1000.0
                # Allow for some floating point error and tick granularity
                assert (
                    abs(time_diff - expected_cooldown) <= 0.2
                    or abs(time_diff - expected_cooldown - 0.1) <= 0.2
                )


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
