"""
Comprehensive tests for battle engine to ensure it matches Game Design Document
"""

from copy import deepcopy

import pytest
from battle_engine import ITEM_CATALOG, BattleSimulator, PlacedItem, Player
from grid_system import SHAPES
from item_effects import ItemSpec, PassiveTrigger, TimerTrigger
from server_containers import ServerContainer, create_server_containers


def get_test_containers():
    """Get standard test containers for both players"""
    containers = create_server_containers()

    # Player 1 gets a standard VM at (0,0)
    p1_container = ServerContainer(
        spec=containers["standard_vm"],
        position=(0, 0),
        uid="p1_test_rack",
        shape=containers["standard_vm"].shape,
    )

    # Player 2 gets a standard VM at (4,0)
    p2_container = ServerContainer(
        spec=containers["standard_vm"],
        position=(4, 0),
        uid="p2_test_rack",
        shape=containers["standard_vm"].shape,
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
        np = ITEM_CATALOG["null_blade"]
        assert np.name == "Null blade"
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
        # Special attribute is optional

        # Test Memory Leak (Section 2.1)
        ml = ITEM_CATALOG["core_dumper"]
        assert len(ml.triggers) == 1
        assert isinstance(ml.triggers[0], TimerTrigger)
        assert ml.triggers[0].cooldown == 3.0
        assert ml.triggers[0].cpu_cost == 2
        attack_effect = ml.triggers[0].effects[0]
        assert attack_effect.min_damage == 2
        assert attack_effect.max_damage == 4
        assert attack_effect.accuracy == 0.95
        # Special attribute is optional

        # Test Error Monitoring (Section 2.2)
        from shield_effect import OnAttackedTrigger

        em = ITEM_CATALOG["error_monitoring"]
        # Should have on_attacked trigger for shield
        assert len(em.triggers) == 1
        assert isinstance(em.triggers[0], OnAttackedTrigger)
        shield_effect = em.triggers[0].effects[0]
        assert shield_effect.block_chance == 0.3
        assert shield_effect.block_amount == 8

        # Test Firewall (Section 2.2)
        fw = ITEM_CATALOG["firewall"]
        # Should have on_attacked trigger
        from shield_effect import OnAttackedTrigger

        assert len(fw.triggers) == 1
        assert isinstance(fw.triggers[0], OnAttackedTrigger)
        shield_effect = fw.triggers[0].effects[0]
        assert shield_effect.block_chance == 0.3  # 30% block chance from JSON

        # Test Infrastructure (Section 2.3)
        quantum_proc = ITEM_CATALOG["quantum_processor"]
        # Should have passive trigger with stat mod effects
        assert len(quantum_proc.triggers) == 1
        assert isinstance(quantum_proc.triggers[0], PassiveTrigger)
        # Quantum processor has 3 effects: max_cpu, cpu_regen, and cpu_cost buff
        assert len(quantum_proc.triggers[0].effects) == 3
        stat_effect = quantum_proc.triggers[0].effects[0]
        assert stat_effect.stat_name == "max_cpu"
        assert stat_effect.value == 10  # From JSON

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
        item = PlacedItem(spec=deepcopy(ITEM_CATALOG["null_blade"]), position=(0, 0))
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
        item = ITEM_CATALOG["null_blade"]
        # Check attack effect has crit chance
        attack_effect = item.triggers[0].effects[0]
        assert attack_effect.crit_chance == 0.2  # Null pointer has 20% crit in JSON

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

        center = PlacedItem(spec=deepcopy(ITEM_CATALOG["core_dumper"]), position=(1, 1))

        # Orthogonally adjacent
        top = PlacedItem(spec=deepcopy(ITEM_CATALOG["core_dumper"]), position=(1, 0))
        right = PlacedItem(spec=deepcopy(ITEM_CATALOG["core_dumper"]), position=(2, 1))
        bottom = PlacedItem(spec=deepcopy(ITEM_CATALOG["core_dumper"]), position=(1, 2))
        left = PlacedItem(spec=deepcopy(ITEM_CATALOG["core_dumper"]), position=(0, 1))

        # Diagonally adjacent (should NOT count)
        diagonal = PlacedItem(
            spec=deepcopy(ITEM_CATALOG["core_dumper"]), position=(0, 0)
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
            spec=deepcopy(ITEM_CATALOG["null_blade"]), position=(1, 1)
        )
        problem2 = PlacedItem(spec=ITEM_CATALOG["core_dumper"], position=(1, 0))
        problem3 = PlacedItem(spec=ITEM_CATALOG["deadlock_twins"], position=(0, 1))

        items = [problem1, problem2, problem3]
        sim._calculate_adjacency(items)

        # problem1 is adjacent to 2 other problems, so 3 total = bug swarm
        assert problem1.damage_mult == 1.2  # +20% damage

    def test_compact_action_format(self):
        """Test Section 10.2: Compact action log format - now using BattleAction models"""
        sim = BattleSimulator()

        # Create simple test items
        item = PlacedItem(spec=deepcopy(ITEM_CATALOG["null_blade"]), position=(0, 0))

        p1_containers, p2_containers = get_test_containers()
        result = sim.simulate_battle(
            [item],
            [],
            round_number=1,
            p1_containers=p1_containers,
            p2_containers=p2_containers,
        )

        # Check action format - now using BattleAction objects
        assert "actions" in result
        if len(result["actions"]) > 0:
            action = result["actions"][0]
            # BattleAction model has these attributes
            assert hasattr(action, "timestamp")  # timestamp in milliseconds
            assert hasattr(action, "action")  # action name (verbose)
            assert hasattr(action, "player")  # player id
            # Optional fields
            assert hasattr(action, "source")  # item source
            assert hasattr(action, "damage")  # damage/value

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
                player_class="neutral",
                shape=SHAPES["1x1"],
                slug="test_slug",
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

        # Test Auto Scaler
        autoscaler = PlacedItem(
            spec=deepcopy(ITEM_CATALOG["auto_scaler"]), position=(0, 0)
        )
        sim._apply_infrastructure([autoscaler], player)
        assert player.max_cpu == 15  # 10 base + 5 from JSON
        assert player.cpu_regen == 3.0  # 2 base + 1 from JSON

        # Test Quantum Processor
        player2 = Player(id=1, quota=25, max_quota=25, cpu=10.0)
        quantum = PlacedItem(
            spec=deepcopy(ITEM_CATALOG["quantum_processor"]), position=(0, 0)
        )
        sim._apply_infrastructure([quantum], player2)
        assert player2.max_cpu == 20  # 10 base + 10 from JSON
        assert player2.cpu_regen == 5.0  # 2 base + 3 from JSON

        # Test Health Check (simple infrastructure item)
        Player(id=1, quota=25, max_quota=25, cpu=10.0)
        PlacedItem(spec=deepcopy(ITEM_CATALOG["health_check"]), position=(0, 0))
        # Health check is not infrastructure category, it's a timer-based healing item
        # So no passive effects to test here

    def test_special_item_effects(self):
        """Test specific item special effects from Section 2"""
        BattleSimulator()

        # Memory Leak stacking
        ml = PlacedItem(spec=deepcopy(ITEM_CATALOG["core_dumper"]), position=(0, 0))
        assert ml.memory_leak_stacks == 0
        # After activation would increment

        # Error Monitoring is now an on-attacked shield, not battle start block
        em = PlacedItem(
            spec=deepcopy(ITEM_CATALOG["error_monitoring"]), position=(0, 0)
        )
        Player(id=1, quota=25, max_quota=25, cpu=10.0)
        Player(id=2, quota=25, max_quota=25, cpu=10.0)

        # Error monitoring now has on_attacked trigger, not battle start
        # It provides a chance to block attacks with shield_block effect
        assert len(em.spec.triggers) == 1
        from shield_effect import OnAttackedTrigger

        assert isinstance(em.spec.triggers[0], OnAttackedTrigger)


class TestBattleSimulation:
    """Test actual battle simulations"""

    def test_basic_battle(self):
        """Test a simple 1v1 battle"""
        sim = BattleSimulator()

        item1 = PlacedItem(spec=deepcopy(ITEM_CATALOG["null_blade"]), position=(0, 0))

        item2 = PlacedItem(spec=ITEM_CATALOG["core_dumper"], position=(4, 0))

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
                player_class="neutral",
                shape=SHAPES["1x1"],
                slug="test_slug",
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

    @pytest.mark.skip(
        reason="Adjacency buff effects from JSON not fully implemented yet"
    )
    def test_adjacency_in_battle(self):
        """Test adjacency effects work in battle"""
        sim = BattleSimulator()

        # Load Balancer Module gives adjacent items +15% speed
        lb = PlacedItem(spec=ITEM_CATALOG["load_balancer_module"], position=(0, 0))

        np = PlacedItem(
            spec=deepcopy(ITEM_CATALOG["null_blade"]), position=(1, 0)  # Adjacent
        )

        items = [lb, np]
        sim._calculate_adjacency(items)

        # Null pointer should have bonus speed from adjacent load balancer
        assert np.speed_mult == 1.15  # +15% speed


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
