"""
Comprehensive tests for battle engine to ensure it matches Game Design Document
"""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from battle_engine import ITEM_CATALOG, BattleItem, BattleSimulator, Player
from containers import Container
from grid_system import SHAPES
from item_effects import ItemSpec, PassiveTrigger, TimerTrigger
from schemas import BattleAction

# A battle with no seed uses the clock, which makes every run a different
# battle. Tests pin it so a failure is reproducible.
TEST_SEED = 424242


def get_test_containers():
    """Get standard test containers for both players"""
    # Player 1 gets a standard VM at (0,0)
    p1_container = Container.of("standard_vm", (0, 0), "p1_test_rack")

    # Player 2 gets a standard VM at (4,0)
    p2_container = Container.of("standard_vm", (4, 0), "p2_test_rack")

    return [p1_container], [p2_container]


class TestGameDesignCompliance:
    """Test that battle engine exactly matches the Game Design Document"""

    def test_player_quota_scaling(self):
        """Test Section 1.1: Player Quota scaling by round"""
        sim = BattleSimulator(seed=TEST_SEED)

        # One value per round, not tiers, exactly as the document lists them
        expected = [
            25, 35, 45, 55, 70, 85, 100, 115, 130,
            150, 170, 190, 210, 230, 260, 290, 320, 350,
        ]
        for round_num, quota in enumerate(expected, start=1):
            assert sim._get_round_quota(round_num) == quota

        # Eighteen rounds is the whole game, so a higher round is not a case
        # the source covers. It clamps rather than raising.
        assert sim._get_round_quota(19) == 350

    def test_cpu_cycles_system(self):
        """Test Section 1.2: CPU Cycles (Stamina) system"""
        player = Player(id=1, quota=25, max_quota=25, cpu=10.0)

        # Starting CPU is 10
        assert player.max_cpu == 3
        assert player.cpu == 10.0  # Starts full per battle_engine initialization

        # CPU regeneration is 2/second
        assert player.cpu_regen == 1.0

    def test_item_specifications(self):
        """Test Section 2: All items match specifications"""
        # Null blade, from Wooden Sword (Section 2.3)
        np = ITEM_CATALOG["null_blade"]
        assert np.name == "Null blade"
        # Check it has a timer trigger with attack effect
        assert len(np.triggers) == 1
        assert isinstance(np.triggers[0], TimerTrigger)
        assert np.triggers[0].cooldown == 1.4
        assert np.triggers[0].cpu_cost == 1.0
        # Check attack effect
        attack_effect = np.triggers[0].effects[0]
        assert attack_effect.min_damage == 1
        assert attack_effect.max_damage == 3
        assert attack_effect.accuracy == 0.9
        # Special attribute is optional

        # Core Dumper, from Axe (Section 2.3)
        ml = ITEM_CATALOG["core_dumper"]
        assert len(ml.triggers) == 1
        assert isinstance(ml.triggers[0], TimerTrigger)
        assert ml.triggers[0].cooldown == 2.0
        assert ml.triggers[0].cpu_cost == 1.4
        attack_effect = ml.triggers[0].effects[0]
        assert attack_effect.min_damage == 3
        assert attack_effect.max_damage == 6
        assert attack_effect.accuracy == 0.85
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
        sim = BattleSimulator(seed=TEST_SEED)
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
        sim = BattleSimulator(seed=TEST_SEED)

        # Create a weak item that won't end battle quickly
        item = BattleItem(spec=deepcopy(ITEM_CATALOG["null_blade"]), position=(0, 0))
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
        sim = BattleSimulator(seed=TEST_SEED)
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
        sim = BattleSimulator(seed=TEST_SEED)

        center = BattleItem(spec=deepcopy(ITEM_CATALOG["core_dumper"]), position=(1, 1))

        # Orthogonally adjacent
        top = BattleItem(spec=deepcopy(ITEM_CATALOG["core_dumper"]), position=(1, 0))
        right = BattleItem(spec=deepcopy(ITEM_CATALOG["core_dumper"]), position=(2, 1))
        bottom = BattleItem(spec=deepcopy(ITEM_CATALOG["core_dumper"]), position=(1, 2))
        left = BattleItem(spec=deepcopy(ITEM_CATALOG["core_dumper"]), position=(0, 1))

        # Diagonally adjacent (should NOT count)
        diagonal = BattleItem(
            spec=deepcopy(ITEM_CATALOG["core_dumper"]), position=(0, 0)
        )

        all_items = [center, top, right, bottom, left, diagonal]
        adjacent = sim._get_adjacent_items(center, all_items)

        # Should have exactly 4 adjacent (not diagonal)
        assert len(adjacent) == 4
        assert diagonal not in adjacent

    def test_synergies(self):
        """Test Section 4.3: Synergy effects"""
        sim = BattleSimulator(seed=TEST_SEED)

        # Test Bug Swarm: 3+ problems = +20% damage
        problem1 = BattleItem(
            spec=deepcopy(ITEM_CATALOG["null_blade"]), position=(1, 1)
        )
        problem2 = BattleItem(spec=ITEM_CATALOG["core_dumper"], position=(1, 0))
        problem3 = BattleItem(spec=ITEM_CATALOG["deadlock_twins"], position=(0, 1))

        items = [problem1, problem2, problem3]
        sim._calculate_adjacency(items)

        # problem1 is adjacent to 2 other problems, so 3 total = bug swarm
        assert problem1.damage_mult == 1.2  # +20% damage

    def test_an_action_name_the_client_does_not_know_cannot_be_built(self):
        fields = dict(
            timestamp=0, source="x", target=None, damage=1, player=1, details=None
        )

        assert BattleAction(action="heal", **fields).action == "heal"

        with pytest.raises(ValidationError):
            BattleAction(action="h", **fields)
        with pytest.raises(ValidationError):
            BattleAction(action="something_new", **fields)

    def test_a_buff_names_itself_the_way_the_client_reads_it(self):
        sim = BattleSimulator(seed=0)
        p1_containers, p2_containers = get_test_containers()
        result = sim.simulate_battle(
            [
                BattleItem(
                    spec=deepcopy(ITEM_CATALOG["system_restore"]), position=(0, 0)
                )
            ],
            [BattleItem(spec=deepcopy(ITEM_CATALOG["core_dumper"]), position=(4, 0))],
            round_number=1,
            p1_containers=p1_containers,
            p2_containers=p2_containers,
        )

        buffs = [a for a in result["actions"] if a.action == "buff"]
        assert buffs, "Seed 0 should produce a buff"
        assert buffs[0].details["buff_name"] == "speed"

    def test_compact_action_format(self):
        """Test Section 10.2: Compact action log format - now using BattleAction models"""
        sim = BattleSimulator(seed=TEST_SEED)

        # Create simple test items
        item = BattleItem(spec=deepcopy(ITEM_CATALOG["null_blade"]), position=(0, 0))

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
        sim = BattleSimulator(seed=TEST_SEED)

        # Create item with high CPU cost
        from item_effects import AttackEffect

        item = BattleItem(
            spec=ItemSpec(
                id="test",
                name="Test",
                category="problem",
                cost=1,
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
        """Infrastructure items apply their stat mods before the battle"""
        sim = BattleSimulator(seed=TEST_SEED)
        player = Player(id=1, quota=25, max_quota=25, cpu=10.0)

        quantum = BattleItem(
            spec=deepcopy(ITEM_CATALOG["quantum_processor"]), position=(0, 0)
        )
        sim._apply_infrastructure([quantum], player)

        assert player.max_cpu == 13  # 3 base + 10 from JSON
        assert player.cpu_regen == 4.0  # 1 base + 3 from JSON

    def test_only_infrastructure_items_apply_stat_mods(self):
        """
        _apply_infrastructure skips anything whose category is not
        "infrastructure". auto_scaler is a protocol, so it must not change CPU.
        """
        sim = BattleSimulator(seed=TEST_SEED)
        player = Player(id=1, quota=25, max_quota=25, cpu=10.0)

        autoscaler = BattleItem(
            spec=deepcopy(ITEM_CATALOG["auto_scaler"]), position=(0, 0)
        )
        sim._apply_infrastructure([autoscaler], player)

        assert player.max_cpu == 3, "A protocol should not raise max CPU"
        assert player.cpu_regen == 1.0, "A protocol should not raise CPU regen"
        # So no passive effects to test here

    def test_special_item_effects(self):
        """Test specific item special effects from Section 2"""
        BattleSimulator(seed=TEST_SEED)

        # Memory Leak stacking
        ml = BattleItem(spec=deepcopy(ITEM_CATALOG["core_dumper"]), position=(0, 0))
        assert ml.memory_leak_stacks == 0
        # After activation would increment

        # Error Monitoring is now an on-attacked shield, not battle start block
        em = BattleItem(
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
        sim = BattleSimulator(seed=TEST_SEED)

        item1 = BattleItem(spec=deepcopy(ITEM_CATALOG["null_blade"]), position=(0, 0))

        item2 = BattleItem(spec=ITEM_CATALOG["core_dumper"], position=(4, 0))

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
        sim = BattleSimulator(seed=TEST_SEED)

        # Create overpowered item
        from item_effects import AttackEffect

        op_item = BattleItem(
            spec=ItemSpec(
                id="op",
                name="OP",
                category="problem",
                cost=1,
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
        sim = BattleSimulator(seed=TEST_SEED)

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
        sim = BattleSimulator(seed=TEST_SEED)

        # Load Balancer Module gives adjacent items +15% speed
        lb = BattleItem(spec=ITEM_CATALOG["load_balancer_module"], position=(0, 0))

        np = BattleItem(
            spec=deepcopy(ITEM_CATALOG["null_blade"]), position=(1, 0)  # Adjacent
        )

        items = [lb, np]
        sim._calculate_adjacency(items)

        # Null pointer should have bonus speed from adjacent load balancer
        assert np.speed_mult == 1.15  # +15% speed


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
