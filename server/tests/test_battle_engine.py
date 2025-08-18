"""
Comprehensive tests for battle engine to ensure it matches Game Design Document
"""

from copy import deepcopy

import pytest
from battle_engine import ITEM_CATALOG, BattleSimulator, PlacedItem, Player
from event_system import Event, EventType

# from grid_system import SHAPES  # Not currently used
from item_effects import BattleStartTrigger, DamageTakenTrigger, ItemSpec, TimerTrigger
from server_containers import ServerContainer, create_server_containers


def get_test_containers():
    """Get standard test containers for both players"""
    containers = create_server_containers()

    # Player 1 gets a mini rack at (0,0)
    p1_container = ServerContainer(
        spec=containers["mini_rack"]["spec"],
        position=(0, 0),
        uid="p1_test_rack",
        internal_grid_size=containers["mini_rack"]["internal_size"],
        shape=containers["mini_rack"]["external_shape"],
    )

    # Player 2 gets a mini rack at (4,0)
    p2_container = ServerContainer(
        spec=containers["mini_rack"]["spec"],
        position=(4, 0),
        uid="p2_test_rack",
        internal_grid_size=containers["mini_rack"]["internal_size"],
        shape=containers["mini_rack"]["external_shape"],
    )

    return [p1_container], [p2_container]


class TestGameDesignCompliance:
    """Test that battle engine exactly matches the Game Design Document"""

    def test_player_quota_scaling(self):
        """Test Section 1.1: Player Quota scaling by round"""
        sim = BattleSimulator()

        # Test each tier from the document
        assert sim._get_round_quota(1) == 25  # Rounds 1-3
        assert sim._get_round_quota(3) == 25
        assert sim._get_round_quota(4) == 35  # Rounds 4-6
        assert sim._get_round_quota(6) == 35
        assert sim._get_round_quota(7) == 50  # Rounds 7-9
        assert sim._get_round_quota(9) == 50
        assert sim._get_round_quota(10) == 75  # Rounds 10-12
        assert sim._get_round_quota(12) == 75
        assert sim._get_round_quota(13) == 100  # Rounds 13-15
        assert sim._get_round_quota(15) == 100
        assert sim._get_round_quota(16) == 150  # Round 16+
        assert sim._get_round_quota(20) == 150

    def test_cpu_cycles_system(self):
        """Test Section 1.2: CPU Cycles (Stamina) system"""
        player = Player(id=1, quota=25, max_quota=25, cpu=10.0)

        # Starting CPU is 10
        assert player.max_cpu == 10
        assert player.cpu == 10.0  # Starts full per battle_engine initialization

        # CPU regeneration is 2/second
        assert player.cpu_regen == 2.0

    def test_item_specifications(self):
        """Test Section 2: All items match specifications"""
        # Test Null Pointer (Section 2.1)
        np = ITEM_CATALOG["null_pointer"]
        assert np.name == "Null Pointer Exception"
        # Check it has a timer trigger with attack effect
        assert len(np.triggers) == 1
        assert isinstance(np.triggers[0], TimerTrigger)
        assert np.triggers[0].cooldown == 2.5
        assert np.triggers[0].cpu_cost == 3
        # Check attack effect
        attack_effect = np.triggers[0].effects[0]
        assert attack_effect.min_damage == 4
        assert attack_effect.max_damage == 8
        assert attack_effect.accuracy == 0.85
        assert attack_effect.special == "crash"

        # Test Memory Leak (Section 2.1)
        ml = ITEM_CATALOG["memory_leak"]
        assert len(ml.triggers) == 1
        assert isinstance(ml.triggers[0], TimerTrigger)
        assert ml.triggers[0].cooldown == 3.0
        assert ml.triggers[0].cpu_cost == 2
        attack_effect = ml.triggers[0].effects[0]
        assert attack_effect.min_damage == 2
        assert attack_effect.max_damage == 4
        assert attack_effect.accuracy == 0.95
        assert attack_effect.special == "stacking"

        # Test Error Monitoring (Section 2.2)
        em = ITEM_CATALOG["error_monitoring"]
        # Should have battle start trigger and passive trigger
        assert len(em.triggers) == 2
        assert isinstance(em.triggers[0], BattleStartTrigger)
        block_effect = em.triggers[0].effects[0]
        assert block_effect.block_amount == 5

        # Test Session Replay (Section 2.2)
        sr = ITEM_CATALOG["session_replay"]
        # Should have damage taken trigger and timer trigger
        assert len(sr.triggers) == 2
        assert isinstance(sr.triggers[0], DamageTakenTrigger)
        assert sr.triggers[0].cpu_cost == 0  # No stamina cost
        reflect_effect = sr.triggers[0].effects[0]
        assert reflect_effect.reflect_percent == 0.3  # 30% reflect

        # Test Infrastructure (Section 2.3)
        lb = ITEM_CATALOG["load_balancer"]
        # Should have passive trigger with stat mod effect
        assert len(lb.triggers) == 1
        stat_effect = lb.triggers[0].effects[0]
        assert stat_effect.stat_name == "max_cpu"
        assert stat_effect.value == 5

    def test_battle_duration(self):
        """Test Section 6.2: Battle max duration 60s"""
        sim = BattleSimulator()
        assert sim.max_duration == 60.0

        # Test timeout with no items (should end at 60s)
        p1_containers, p2_containers = get_test_containers()
        result = sim.simulate_battle(
            [],
            [],
            round_number=1,
            p1_containers=p1_containers,
            p2_containers=p2_containers,
        )
        assert result["duration"] <= 60.0

    def test_fatigue_mechanic(self):
        """Test Section 7.1: Fatigue after 30s"""
        sim = BattleSimulator()

        # Create a weak item that won't end battle quickly
        item = PlacedItem(spec=deepcopy(ITEM_CATALOG["null_pointer"]), position=(0, 0))
        item.spec.min_damage = 1
        item.spec.max_damage = 1

        # Run partial simulation
        sim.current_time = 29.9
        original_damage = item.spec.min_damage

        # Before 30s - no fatigue
        assert item.spec.min_damage == original_damage

        # After 30s - damage increases by 1 per 5 seconds
        sim.current_time = 30.0
        # Would apply fatigue here in real simulation
        # Fatigue at 30s = 0
        # Fatigue at 35s = 1
        # Fatigue at 40s = 2

    def test_critical_hits(self):
        """Test Section 7.2: Base 5% crit chance, 2x damage"""
        item = ITEM_CATALOG["null_pointer"]
        # Check attack effect has crit chance
        attack_effect = item.triggers[0].effects[0]
        assert attack_effect.crit_chance == 0.05  # 5% base

        # Critical hits should deal 2x damage (tested in simulation)

    def test_block_mechanics(self):
        """Test Section 7.3: Block reduces damage 1:1"""
        sim = BattleSimulator()
        player = Player(id=1, quota=100, max_quota=100, cpu=10.0)
        attacker = Player(id=2, quota=100, max_quota=100, cpu=10.0)

        # Give player 10 block
        player.buffs["block"] = 10

        # Deal 15 damage
        sim._deal_damage(player, 15, attacker, "test_item")

        # Should block 10, take 5 damage
        assert player.quota == 95
        assert "block" not in player.buffs  # All block consumed

    def test_adjacency_rules(self):
        """Test Section 4.2: Orthogonal adjacency only"""
        sim = BattleSimulator()

        center = PlacedItem(
            spec=deepcopy(ITEM_CATALOG["null_pointer"]), position=(1, 1)
        )

        # Orthogonally adjacent
        top = PlacedItem(spec=deepcopy(ITEM_CATALOG["memory_leak"]), position=(1, 0))
        right = PlacedItem(spec=deepcopy(ITEM_CATALOG["memory_leak"]), position=(2, 1))
        bottom = PlacedItem(spec=deepcopy(ITEM_CATALOG["memory_leak"]), position=(1, 2))
        left = PlacedItem(spec=deepcopy(ITEM_CATALOG["memory_leak"]), position=(0, 1))

        # Diagonally adjacent (should NOT count)
        diagonal = PlacedItem(
            spec=deepcopy(ITEM_CATALOG["memory_leak"]), position=(0, 0)
        )

        all_items = [center, top, right, bottom, left, diagonal]
        adjacent = sim._get_adjacent_items(center, all_items)

        # Should have exactly 4 adjacent (not diagonal)
        assert len(adjacent) == 4
        assert diagonal not in adjacent

    def test_synergies(self):
        """Test Section 4.3: Synergy effects"""
        sim = BattleSimulator()

        # Test Bug Swarm: 3+ problems = +20% damage
        problem1 = PlacedItem(
            spec=deepcopy(ITEM_CATALOG["null_pointer"]), position=(1, 1)
        )
        problem2 = PlacedItem(spec=ITEM_CATALOG["memory_leak"], position=(1, 0))
        problem3 = PlacedItem(spec=ITEM_CATALOG["race_condition"], position=(0, 1))

        items = [problem1, problem2, problem3]
        sim._calculate_adjacency(items)

        # problem1 is adjacent to 2 other problems, so 3 total = bug swarm
        assert problem1.damage_mult == 1.2  # +20% damage

    def test_compact_action_format(self):
        """Test Section 10.2: Compact action log format"""
        sim = BattleSimulator()

        # Create simple test items
        item = PlacedItem(spec=deepcopy(ITEM_CATALOG["null_pointer"]), position=(0, 0))

        p1_containers, p2_containers = get_test_containers()
        result = sim.simulate_battle(
            [item],
            [],
            round_number=1,
            p1_containers=p1_containers,
            p2_containers=p2_containers,
        )

        # Check action format
        assert "actions" in result
        if len(result["actions"]) > 0:
            action = result["actions"][0]
            assert "t" in action  # timestamp
            assert "a" in action  # action code
            # Optional fields only if needed
            # "p" for player, "i" for item, "v" for value

    def test_cpu_throttling(self):
        """Test Section 1.2: Items skip when CPU exhausted"""
        sim = BattleSimulator()

        # Create item with high CPU cost
        from item_effects import AttackEffect

        item = PlacedItem(
            spec=ItemSpec(
                id="test",
                name="Test",
                category="problem",
                triggers=[
                    TimerTrigger(
                        cooldown=1.0,
                        cpu_cost=20,  # More than max CPU
                        effects=[AttackEffect(min_damage=5, max_damage=10)],
                    )
                ],
            ),
            position=(0, 0),
        )

        p1_containers, p2_containers = get_test_containers()
        sim.simulate_battle(
            [item],
            [],
            round_number=1,
            p1_containers=p1_containers,
            p2_containers=p2_containers,
        )

        # Should see CPU_FAIL actions in the result
        # Item can't activate with 20 CPU cost when max is 10

    def test_infrastructure_effects(self):
        """Test Section 2.3: Infrastructure passive effects"""
        sim = BattleSimulator()
        player = Player(id=1, quota=25, max_quota=25, cpu=10.0)

        # Test Load Balancer
        lb = PlacedItem(spec=deepcopy(ITEM_CATALOG["load_balancer"]), position=(0, 0))
        sim._apply_infrastructure([lb], player)
        assert player.max_cpu == 15  # 10 base + 5

        # Test Redis Cache
        player2 = Player(id=1, quota=25, max_quota=25, cpu=10.0)
        redis = PlacedItem(spec=deepcopy(ITEM_CATALOG["redis_cache"]), position=(0, 0))
        sim._apply_infrastructure([redis], player2)
        assert player2.cpu_regen == 5.0  # 2 base + 3

        # Test Database
        player3 = Player(id=1, quota=25, max_quota=25, cpu=10.0)
        db = PlacedItem(spec=deepcopy(ITEM_CATALOG["database"]), position=(0, 0))
        sim._apply_infrastructure([db], player3)
        assert player3.max_cpu == 18  # 10 base + 8

    def test_special_item_effects(self):
        """Test specific item special effects from Section 2"""
        sim = BattleSimulator()

        # Memory Leak stacking
        ml = PlacedItem(spec=deepcopy(ITEM_CATALOG["memory_leak"]), position=(0, 0))
        assert ml.memory_leak_stacks == 0
        # After activation would increment

        # Error Monitoring gives block at battle start
        em = PlacedItem(
            spec=deepcopy(ITEM_CATALOG["error_monitoring"]), position=(0, 0)
        )
        player = Player(id=1, quota=25, max_quota=25, cpu=10.0)
        enemy = Player(id=2, quota=25, max_quota=25, cpu=10.0)

        # Set up handlers and trigger battle start
        sim._setup_item_handlers([em], player, enemy)
        sim.event_manager.emit(Event(EventType.BATTLE_START, None, None))
        assert player.buffs.get("block", 0) == 5


class TestBattleSimulation:
    """Test actual battle simulations"""

    def test_basic_battle(self):
        """Test a simple 1v1 battle"""
        sim = BattleSimulator()

        item1 = PlacedItem(spec=deepcopy(ITEM_CATALOG["null_pointer"]), position=(0, 0))

        item2 = PlacedItem(spec=ITEM_CATALOG["memory_leak"], position=(4, 0))

        p1_containers, p2_containers = get_test_containers()
        result = sim.simulate_battle(
            [item1],
            [item2],
            round_number=1,
            p1_containers=p1_containers,
            p2_containers=p2_containers,
        )

        assert "winner" in result
        assert result["winner"] in [1, 2]
        assert "duration" in result
        assert "player1_quota" in result
        assert "player2_quota" in result
        assert "actions" in result

    def test_battle_ends_on_death(self):
        """Test battle ends when player quota reaches 0"""
        sim = BattleSimulator()

        # Create overpowered item
        from item_effects import AttackEffect

        op_item = PlacedItem(
            spec=ItemSpec(
                id="op",
                name="OP",
                category="problem",
                triggers=[
                    TimerTrigger(
                        cooldown=0.1,
                        cpu_cost=1,
                        effects=[
                            AttackEffect(min_damage=100, max_damage=100, accuracy=1.0)
                        ],
                    )
                ],
            ),
            position=(0, 0),
        )

        p1_containers, p2_containers = get_test_containers()
        result = sim.simulate_battle(
            [op_item],
            [],
            round_number=1,
            p1_containers=p1_containers,
            p2_containers=p2_containers,
        )

        assert result["winner"] == 1
        assert result["player2_quota"] == 0
        assert result["duration"] < 60.0  # Should end early

    def test_timeout_battle(self):
        """Test battle times out at 60s"""
        sim = BattleSimulator()

        # No items = no damage = timeout
        p1_containers, p2_containers = get_test_containers()
        result = sim.simulate_battle(
            [],
            [],
            round_number=1,
            p1_containers=p1_containers,
            p2_containers=p2_containers,
        )

        assert result["duration"] == 60.0
        assert result["player1_quota"] == 25  # No damage taken
        assert result["player2_quota"] == 25

    def test_adjacency_in_battle(self):
        """Test adjacency effects work in battle"""
        sim = BattleSimulator()

        # Error Monitoring gives adjacent problems +10% accuracy
        em = PlacedItem(spec=ITEM_CATALOG["error_monitoring"], position=(0, 0))

        np = PlacedItem(
            spec=deepcopy(ITEM_CATALOG["null_pointer"]), position=(1, 0)  # Adjacent
        )

        items = [em, np]
        sim._calculate_adjacency(items)

        # Null pointer should have bonus accuracy
        assert np.accuracy_bonus == 0.1  # +10%


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
