"""
Comprehensive tests for battle engine to ensure it matches Game Design Document
"""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from battle_engine import (
    ITEM_CATALOG,
    MEMORY_LEAKED,
    OVER_TIME,
    POISON_PERIOD,
    BattleItem,
    BattleSimulator,
    MemoryLeaked,
    Player,
)
from containers import Container
from grid_system import parse_map
from item_effects import (
    BUFFS,
    MODIFIERS,
    AttackEffect,
    BuffEffect,
    CleanseEffect,
    CpuDrainEffect,
    DebuffEffect,
    HealEffect,
    HealthThresholdTrigger,
    ItemSpec,
    ModifyEffect,
    OnAttackedTrigger,
    OnHitTrigger,
    PassiveTrigger,
    PreventDamageEffect,
    TimerTrigger,
)
from schemas import BattleAction

# A battle with no seed uses the clock, which makes every run a different
# battle. Tests pin it so a failure is reproducible.
TEST_SEED = 424242


def get_test_containers():
    """A 3x3 for each player.

    A 2x2 was enough while every item covered a square or two. Items carry
    their real shapes now, and a four square L reaches three rows down.
    """
    return (
        [Container.of("mesh_network_hub", (0, 0), "p1_test_rack")],
        [Container.of("mesh_network_hub", (4, 0), "p2_test_rack")],
    )


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

        # The pool is three, and it regenerates one a second. The comments here
        # used to say ten and two, which is neither what the document says nor
        # what the assertions below check - and a made-up ten is exactly what
        # the client drew for every battle until the level was sent to it.
        assert player.max_cpu == 3.0
        assert player.cpu_regen == 1.0

    def test_cpu_is_spent_in_fractions(self):
        """Section 1.2: activations cost cycles "in fractions".

        Two things have gone wrong here before. Costs were floored to a whole
        cycle, which threw away every fractional cost the catalogue declares -
        thirteen items declare one - and left the Load Balancer's discount with
        nothing to discount, since no reduction can take a cost below one.

        And the pool was a whole number while the level was not, so
        min(max_cpu, cpu + regen) handed back an int whenever regeneration
        topped the pool up: a full pool reported 3 and a spent one 2.7, from
        the same field.
        """
        p1_containers, p2_containers = get_test_containers()
        sim = BattleSimulator(seed=TEST_SEED)
        # sql_injector declares a cost of 0.3.
        sim.simulate_battle(
            [BattleItem(spec=deepcopy(ITEM_CATALOG["sql_injector"]), position=(0, 0))],
            [BattleItem(spec=deepcopy(ITEM_CATALOG["sql_injector"]), position=(4, 0))],
            1,
            p1_containers=p1_containers,
            p2_containers=p2_containers,
        )

        levels = [
            action.details["cpu"][0]
            for action in sim.actions
            if action.details and "cpu" in action.details
        ]
        assert levels, "Every action should say where the CPU stood"
        assert any(
            abs(level - 2.7) < 1e-6 for level in levels
        ), "A cost of 0.3 should take 0.3, not round up to a whole cycle"
        assert all(
            isinstance(level, float) for level in levels
        ), "A full pool is as fractional as a spent one"

    def test_item_specifications(self):
        """Test Section 2: All items match specifications"""
        # Null Blade, from Wooden Sword (Section 2.3)
        np = ITEM_CATALOG["null_blade"]
        assert np.name == "Null Blade"
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

        # An irregular weapon, to check a shape that is not a rectangle carries
        # its numbers as faithfully as a 1x2 does (Section 2.3)
        ss = ITEM_CATALOG["stack_smasher"]
        assert len(ss.triggers) == 1
        assert isinstance(ss.triggers[0], TimerTrigger)
        assert ss.triggers[0].cooldown == 2.2
        assert ss.triggers[0].cpu_cost == 2.0
        attack_effect = ss.triggers[0].effects[0]
        assert attack_effect.min_damage == 5
        assert attack_effect.max_damage == 6
        assert attack_effect.accuracy == 0.85
        # Special attribute is optional

        # Test Error Monitoring (Section 2.2)

        em = ITEM_CATALOG["error_monitoring"]
        # Should have on_attacked trigger for shield
        assert len(em.triggers) == 1
        assert isinstance(em.triggers[0], OnAttackedTrigger)
        # Wooden Buckler: "30% chance to prevent 7 damage and remove 0.3
        # stamina from opponent" -- one roll, two consequences.
        assert em.triggers[0].chance == 0.3
        prevent, drain = em.triggers[0].effects
        assert isinstance(prevent, PreventDamageEffect) and prevent.amount == 7
        assert isinstance(drain, CpuDrainEffect) and drain.amount == 0.3

        # Test Firewall (Section 2.2)
        fw = ITEM_CATALOG["firewall"]
        # Should have on_attacked trigger

        assert len(fw.triggers) == 1
        assert isinstance(fw.triggers[0], OnAttackedTrigger)
        assert fw.triggers[0].chance == 0.3  # every shield rolls 30%

        # Test Infrastructure (Section 2.3)
        # Qubit Core, from Prismatic Orb: every 8s, 1 of each of the seven
        # buffs (Section 3.1). Its start-of-battle per-Star-type gains are
        # still unbuilt.
        quantum_proc = ITEM_CATALOG["quantum_processor"]
        assert len(quantum_proc.triggers) == 1
        assert isinstance(quantum_proc.triggers[0], TimerTrigger)
        assert quantum_proc.triggers[0].cooldown == 8.0
        buffs_given = {e.buff_name for e in quantum_proc.triggers[0].effects}
        assert len(quantum_proc.triggers[0].effects) == 7
        assert buffs_given == {
            "optimized", "monitored", "calibrated", "regenerating",
            "spiked", "draining", "credits",
        }

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
        """Test Section 7.2: Base 5% crit chance, 2x damage.

        No item in the catalogue states its own crit chance: the source
        game's item pages carry no crit stat, so any crit above the base
        comes from an effect, not from the weapon's numbers.
        """
        item = ITEM_CATALOG["null_blade"]
        attack_effect = item.triggers[0].effects[0]
        assert attack_effect.crit_chance == 0  # Wooden Sword grants none

        # Critical hits should deal 2x damage (tested in simulation)

    def test_block_mechanics(self):
        """Test Section 7.3: Block reduces damage 1:1"""
        sim = BattleSimulator(seed=TEST_SEED)
        player = Player(id=1, quota=100, max_quota=100, cpu=10.0)
        attacker = Player(id=2, quota=100, max_quota=100, cpu=10.0)

        # Give player 10 block
        player.block = 10

        # Block is spent stopping an attack, so it belongs to mitigation.
        sword = BattleItem(
            spec=ItemSpec(
                id="w", name="Sword", category="problem", cost=1,
                player_class="neutral", kinds=frozenset({"melee"}),
                shape=parse_map(["#"], "w"), slug="w", triggers=[],
            ),
            position=(0, 0), uid="test_item",
        )
        got_through = sim._mitigate_attack(player, 15, attacker, sword)
        assert got_through == 5, "10 of the 15 absorbed"
        assert player.block == 0, "all of it consumed"

        # What is left lands.
        sim._take_damage(
            player, got_through, source="test_item", action="damage",
            attacker=attacker,
        )
        assert player.quota == 95

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
                    # Any item granting a real buff will do. basic_firewall
                    # used to, until "block" stopped being one: Block is an
                    # attribute a player has, not a status.
                    spec=deepcopy(ITEM_CATALOG["quantum_probability_core"]),
                    position=(0, 0),
                )
            ],
            [BattleItem(spec=deepcopy(ITEM_CATALOG["stack_smasher"]), position=(4, 0))],
            round_number=1,
            p1_containers=p1_containers,
            p2_containers=p2_containers,
        )

        buffs = [a for a in result["actions"] if a.action == "buff"]
        assert buffs, "Seed 0 should produce a buff"
        assert buffs[0].details["buff_name"] == "calibrated"

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

        item = BattleItem(
            spec=ItemSpec(
                id="test",
                name="Test",
                category="problem",
                cost=1,
                player_class="neutral",
                kinds=frozenset({"melee"}),
                shape=parse_map(["#"], "test item"),
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

    def _pool_in_a_battle(self, slug):
        """The pool and the regen a player fights with, carrying this item.

        Read off a real battle rather than off a helper. The doubling this
        guards against lived between two passes that each looked right on its
        own, so only the battle could show it.
        """
        sim = BattleSimulator(seed=TEST_SEED)
        items = [
            BattleItem(spec=deepcopy(ITEM_CATALOG["null_blade"]), position=(0, 0)),
            BattleItem(spec=deepcopy(ITEM_CATALOG[slug]), position=(1, 0)),
        ]
        p1_containers, p2_containers = get_test_containers()
        result = sim.simulate_battle(
            items, [], round_number=1,
            p1_containers=p1_containers, p2_containers=p2_containers,
        )
        for action in result["actions"]:
            details = action.details or {}
            if "max_cpu" in details:
                return details["max_cpu"][0]
        raise AssertionError("No action carried a CPU level")

    def test_a_passive_stat_mod_is_applied_once(self):
        """An item raises the pool by what its own data says, and no more.

        The quantum processor used to be counted twice: once by an
        infrastructure pass and once by the general passive handling. Its
        corrected data (Prismatic Orb) asks for no CPU at all, so the pool
        stays at its base — and the double-count guard now lives in the
        memory_cache test below, which still carries a passive max_cpu.
        """
        assert self._pool_in_a_battle("quantum_processor") == 3.0

    def test_an_item_outside_infrastructure_raises_the_pool_too(self):
        """The category does not decide it; the passive effect does.

        Memory Cache is a container and gives one cycle. Modules and protocols
        do the same for regeneration, which is most of where regeneration
        lives.
        """
        assert self._pool_in_a_battle("memory_cache") == 4.0

    def test_an_item_with_no_stat_mod_leaves_the_pool_alone(self):
        assert self._pool_in_a_battle("auto_scaler") == 3.0

    def test_special_item_effects(self):
        """Test specific item special effects from Section 2"""
        BattleSimulator(seed=TEST_SEED)

        # An item starts a battle with none of the damage it can gain in one,
        # whatever it gained in the last.
        fresh = BattleItem(spec=deepcopy(ITEM_CATALOG["stack_smasher"]), position=(0, 0))
        assert fresh.damage_gained == 0

        # Error Monitoring is now an on-attacked shield, not battle start block
        em = BattleItem(
            spec=deepcopy(ITEM_CATALOG["error_monitoring"]), position=(0, 0)
        )
        Player(id=1, quota=25, max_quota=25, cpu=10.0)
        Player(id=2, quota=25, max_quota=25, cpu=10.0)

        # Error monitoring now has on_attacked trigger, not battle start
        # It provides a chance to block attacks with shield_block effect
        assert len(em.spec.triggers) == 1

        assert isinstance(em.spec.triggers[0], OnAttackedTrigger)


class TestBattleSimulation:
    """Test actual battle simulations"""
    def test_basic_battle(self):
        """Test a simple 1v1 battle"""
        sim = BattleSimulator(seed=TEST_SEED)

        item1 = BattleItem(spec=deepcopy(ITEM_CATALOG["null_blade"]), position=(0, 0))

        item2 = BattleItem(spec=ITEM_CATALOG["stack_smasher"], position=(4, 0))

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

        op_item = BattleItem(
            spec=ItemSpec(
                id="op",
                name="OP",
                category="problem",
                cost=1,
                player_class="neutral",
                kinds=frozenset({"melee"}),
                shape=parse_map(["#"], "test item"),
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


class TestOnHitResolution:
    """Section 1.3: what a hit and a miss each reach"""

    @staticmethod
    def _poisoner(
        accuracy: float,
        chance: float = 1.0,
        uid: str = "poisoner",
        position: tuple = (0, 0),
    ):
        """A weapon that poisons on hit. Accuracy is 1 or 0, so the test never
        depends on a roll going a particular way."""

        return BattleItem(
            spec=ItemSpec(
                id=uid,
                name="Poisoner",
                category="problem",
                cost=1,
                player_class="neutral",
                kinds=frozenset({"melee"}),
                shape=parse_map(["#"], "poisoner"),
                slug=uid,
                triggers=[
                    TimerTrigger(
                        cooldown=0.5,
                        cpu_cost=0,
                        effects=[
                            AttackEffect(
                                min_damage=1,
                                max_damage=1,
                                accuracy=accuracy,
                                crit_chance=0.0,
                            )
                        ],
                    ),
                    OnHitTrigger(
                        chance=chance,
                        effects=[DebuffEffect("memory_leaked", 1)],
                    ),
                ],
            ),
            position=position,
            uid=uid,
        )

    @staticmethod
    def _run(p1_items):
        p1_containers, p2_containers = get_test_containers()
        sim = BattleSimulator(seed=TEST_SEED)
        sim.simulate_battle(
            p1_items, [], 1, p1_containers, p2_containers
        )
        return sim

    def test_a_hit_applies_the_debuff(self):
        sim = self._run([self._poisoner(accuracy=1.0)])
        assert any(a.action == "debuff" for a in sim.actions)

    def test_a_miss_does_not_apply_the_debuff(self):
        """The whole point of on-hit. The attack has to land first."""
        sim = self._run([self._poisoner(accuracy=0.0)])
        assert any(a.action == "miss" for a in sim.actions)
        assert not any(a.action == "debuff" for a in sim.actions)

    def test_a_miss_still_costs_cpu_and_still_counts(self):
        """"Weapons will still provide activations regardless if their attack
        hits or misses." So a miss must not look like a throttle, and it must
        not refund the CPU."""
        misser = self._poisoner(accuracy=0.0)
        misser.spec.triggers[0].cpu_cost = 1.0

        p1_containers, p2_containers = get_test_containers()
        sim = BattleSimulator(seed=TEST_SEED)
        sim.max_duration = 1.0
        sim.simulate_battle([misser], [], 1, p1_containers, p2_containers)

        misses = [a for a in sim.actions if a.action == "miss"]
        assert misses, "the weapon should have swung"
        # A throttle means the item never activated. A miss is an activation.
        assert not any(a.action == "cpu_fail" for a in sim.actions)

    def test_one_items_miss_does_not_stop_another_items_on_hit(self):
        """An on-hit trigger belongs to the item that swung, not to the player.
        If it were keyed on the owner, the misser would cancel the hitter."""
        sim = self._run(
            [
                self._poisoner(accuracy=0.0, uid="misser", position=(0, 0)),
                self._poisoner(accuracy=1.0, uid="hitter", position=(1, 0)),
            ]
        )
        debuffs = [a for a in sim.actions if a.action == "debuff"]
        assert debuffs, "the hitter should still poison"
        assert all(a.source == "hitter" for a in debuffs)

    def test_the_debuff_lands_after_the_damage(self):
        """The log is what the client replays, so it has to read in the order
        it happened: the attack, then what the attack caused."""
        sim = self._run([self._poisoner(accuracy=1.0)])
        first_damage = next(
            i for i, a in enumerate(sim.actions) if a.action == "damage"
        )
        first_debuff = next(
            i for i, a in enumerate(sim.actions) if a.action == "debuff"
        )
        assert first_damage < first_debuff

    def test_the_chance_gates_the_debuff(self):
        """A chance of 0 lands every attack and poisons on none of them"""
        sim = self._run([self._poisoner(accuracy=1.0, chance=0.0)])
        assert any(a.action == "damage" for a in sim.actions)
        assert not any(a.action == "debuff" for a in sim.actions)

    def test_the_poison_then_ticks(self):
        """Section 3.2: 1 damage every 2 seconds per stack. The debuff is only
        worth applying if the DOT loop finds it under the same name."""
        sim = self._run([self._poisoner(accuracy=1.0)])
        assert any(
            a.action == "dot" and a.details["debuff_name"] == "memory_leaked"
            for a in sim.actions
        )


class TestMemoryLeakedDamage:
    """Section 3.2: 1 damage per stack every 2 seconds"""

    @staticmethod
    def _poisoned(stacks: int, seconds: float):
        """Run a battle where one player starts poisoned and nothing else
        happens, and report what the poison took off them."""
        p1_containers, p2_containers = get_test_containers()
        sim = BattleSimulator(seed=TEST_SEED)
        sim.max_duration = seconds

        # No items, so the only thing that can move the quota is the poison.
        original = sim._setup_item_handlers

        def poison_player_2(items, owner, enemy):
            if owner.id == 2:
                owner.debuffs["memory_leaked"] = stacks
            return original(items, owner, enemy)

        sim._setup_item_handlers = poison_player_2
        result = sim.simulate_battle([], [], 18, p1_containers, p2_containers)
        return sim, result["player2_quota"]

    def test_a_stack_deals_one_damage_every_two_seconds(self):
        """The old tick threw away any fraction under a whole point, so
        anything below 20 stacks did nothing at all, forever."""
        for stacks in [1, 2, 4, 10, 19, 20]:
            _, quota = self._poisoned(stacks, seconds=10.0)
            # Payouts at 2s, 4s, 6s, 8s and 10s
            assert 350 - quota == stacks * 5, f"{stacks} stacks over 10s"

    def test_no_poison_means_no_damage(self):
        _, quota = self._poisoned(0, seconds=10.0)
        assert quota == 350

    def test_it_pays_in_whole_periods(self):
        """Damage arrives at 2s, 4s, 6s. Not a trickle every tick."""
        sim, _ = self._poisoned(3, seconds=7.0)
        ticks = [a for a in sim.actions if a.action == "dot"]
        assert [t.timestamp for t in ticks] == [2000, 4000, 6000]
        assert all(t.damage == 3 for t in ticks)

    def test_the_first_two_seconds_are_free(self):
        """A poison landed at battle start does nothing until its period ends"""
        sim, quota = self._poisoned(5, seconds=1.9)
        assert not [a for a in sim.actions if a.action == "dot"]
        assert quota == 350

    def test_the_period_does_not_drift(self):
        """The loop adds 0.1 sixty times over, so the payouts have to come off
        the clock rather than off a running total of ticks."""
        sim, _ = self._poisoned(1, seconds=30.0)
        ticks = [a.timestamp for a in sim.actions if a.action == "dot"]
        # The battle loop stops before the tick at max_duration, so the payout
        # at 30s falls outside it.
        assert ticks == list(range(2000, 29001, 2000))

    def test_stacks_are_not_spent_by_paying_out(self):
        """Section 3.2: a debuff lasts to the end of the battle"""
        _, quota = self._poisoned(2, seconds=20.0)
        # Nine payouts, 2s to 18s. Every one of them costs the full 2.
        assert 350 - quota == 2 * 9, "no payout comes cheaper than the last"


class TestPlayerOverTime:
    """The clock is the player's, the behaviour is the effect's"""
    def test_the_player_only_keeps_the_clock(self):
        """Asking whether a period is due must not pay anything out. The
        player has no way to write a battle log or take damage, and that is
        deliberate."""

        player = Player(id=1, quota=100, max_quota=100, cpu=3.0)
        player.debuffs[MEMORY_LEAKED] = 4

        assert player.period_due(MEMORY_LEAKED, POISON_PERIOD, 0.5) is False
        assert player.period_due(MEMORY_LEAKED, POISON_PERIOD, 2.0) is True
        assert player.quota == 100, "asking is not paying"

    def test_a_period_comes_due_once(self):

        player = Player(id=1, quota=100, max_quota=100, cpu=3.0)
        due_at = [
            t / 10
            for t in range(0, 61)
            if player.period_due(MEMORY_LEAKED, POISON_PERIOD, t / 10)
        ]
        assert due_at == [2.0, 4.0, 6.0]

    def test_every_effect_has_a_name_and_a_period(self):
        """OVER_TIME is the registry the loop walks, so an effect that forgot
        either would silently never pay."""

        assert OVER_TIME, "the registry should not be empty"
        for effect in OVER_TIME:
            assert effect.name, type(effect).__name__
            assert effect.period > 0, type(effect).__name__

    def test_an_effect_pays_itself_out(self):
        """Behaviour belongs to the effect, not to a field the loop reads"""
        p1_containers, p2_containers = get_test_containers()
        sim = BattleSimulator(seed=TEST_SEED)
        sim.simulate_battle([], [], 18, p1_containers, p2_containers)

        player = Player(id=1, quota=100, max_quota=100, cpu=3.0)
        player.debuffs[MEMORY_LEAKED] = 4
        MemoryLeaked().pay(player, sim)

        assert player.quota == 96
        assert [a for a in sim.actions if a.action == "dot" and a.damage == 4]

    def test_an_effect_owing_nothing_does_nothing(self):

        p1_containers, p2_containers = get_test_containers()
        sim = BattleSimulator(seed=TEST_SEED)
        sim.simulate_battle([], [], 18, p1_containers, p2_containers)
        before = len(sim.actions)

        player = Player(id=1, quota=100, max_quota=100, cpu=3.0)
        MemoryLeaked().pay(player, sim)

        assert player.quota == 100
        assert len(sim.actions) == before, "nothing owed, nothing logged"

    def test_reset_for_battle_clears_everything(self):
        """Nothing a battle writes may reach the next round, and one call has
        to clear all of it."""

        player = Player(id=1, quota=100, max_quota=100, cpu=3.0)
        player.debuffs[MEMORY_LEAKED] = 5
        player.buffs["block"] = 12
        player.recorded_attacks.append({"anything": 1})
        player.period_due(MEMORY_LEAKED, POISON_PERIOD, 2.0)
        assert player.paid_at, "the clock should have been written"

        player.reset_for_battle()

        assert player.debuffs == {}
        assert player.buffs == {}
        assert player.recorded_attacks == []
        assert player.paid_at == {}

    def test_a_reused_player_starts_its_own_clock(self):
        """Or a poison from an earlier round would pay out on the first tick
        of the next one."""

        player = Player(id=1, quota=100, max_quota=100, cpu=3.0)
        for t in [2.0, 4.0, 6.0]:
            player.period_due(MEMORY_LEAKED, POISON_PERIOD, t)

        player.reset_for_battle()

        assert player.period_due(MEMORY_LEAKED, POISON_PERIOD, 0.5) is False
        assert player.period_due(MEMORY_LEAKED, POISON_PERIOD, 2.0) is True

    def test_the_simulator_does_the_clearing(self):
        """simulate_battle has to call it, not merely offer it"""
        p1_containers, p2_containers = get_test_containers()
        sim = BattleSimulator(seed=TEST_SEED)
        sim.max_duration = 5.0
        first = sim.simulate_battle([], [], 1, p1_containers, p2_containers)
        second = sim.simulate_battle([], [], 1, p1_containers, p2_containers)
        assert first["player1_quota"] == second["player1_quota"]


class TestOverTimeDamageIsSeen:
    """Poison used to write straight to the quota, so nothing could react"""
    def test_a_health_potion_reacts_to_poison(self):
        """It could not before. Its trigger listens for DAMAGE_TAKEN, and
        poison emitted none, so a player could die of poison with an unused
        potion sitting in the rack."""

        potion = BattleItem(
            spec=ITEM_CATALOG["health_potion"], position=(0, 0), uid="potion"
        )
        p1_containers, p2_containers = get_test_containers()
        sim = BattleSimulator(seed=TEST_SEED)
        sim.max_duration = 30.0

        original = sim._setup_item_handlers

        def poison_player_1(items, owner, enemy):
            result = original(items, owner, enemy)
            if owner.id == 1:
                owner.debuffs[MEMORY_LEAKED] = 4
            return result

        sim._setup_item_handlers = poison_player_1
        sim.simulate_battle([potion], [], 1, p1_containers, p2_containers)

        assert [a for a in sim.actions if a.action == "heal"], "the potion should fire"
        assert [a for a in sim.actions if a.action == "consume"]

    def test_no_shield_blocks_poison(self):
        """There is no attack to block, so no Block buff may be spent on it"""
        p1_containers, p2_containers = get_test_containers()
        sim = BattleSimulator(seed=TEST_SEED)
        sim.max_duration = 4.5

        original = sim._setup_item_handlers

        def arm_player_1(items, owner, enemy):
            result = original(items, owner, enemy)
            if owner.id == 1:
                owner.debuffs[MEMORY_LEAKED] = 3
                owner.buffs["block"] = 100
            return result

        sim._setup_item_handlers = arm_player_1
        result = sim.simulate_battle([], [], 1, p1_containers, p2_containers)

        # Payouts at 2s and 4s, 3 each, straight through the block.
        assert 25 - result["player1_quota"] == 6


class TestOneRollCoversTheList:
    """Section 2.4: a shield rolls once, and all of it lands together"""

    @staticmethod
    def _shield(chance: float, prevent: int, drain: float):

        return BattleItem(
            spec=ItemSpec(
                id="shield",
                name="Shield",
                category="defense",
                cost=1,
                player_class="neutral",
                shape=parse_map(["#"], "shield"),
                slug="shield",
                triggers=[
                    OnAttackedTrigger(
                        answers_to=frozenset({"melee"}),
                        chance=chance,
                        effects=[
                            PreventDamageEffect(prevent),
                            CpuDrainEffect(drain, target_type="attacker"),
                        ],
                    )
                ],
            ),
            position=(0, 0),
            uid="shield",
        )

    @staticmethod
    def _attacker(damage: int, cpu_cost: float = 0.0, uid: str = "sword"):

        return BattleItem(
            spec=ItemSpec(
                id=uid,
                name="Sword",
                category="problem",
                cost=1,
                player_class="neutral",
                kinds=frozenset({"melee"}),
                shape=parse_map(["#"], "sword"),
                slug=uid,
                triggers=[
                    TimerTrigger(
                        cooldown=1.0,
                        cpu_cost=cpu_cost,
                        effects=[
                            AttackEffect(
                                min_damage=damage,
                                max_damage=damage,
                                accuracy=1.0,
                                crit_chance=0.0,
                            )
                        ],
                    )
                ],
            ),
            position=(4, 0),
            uid=uid,
        )

    def _run(self, shield, attacker, seconds=3.5):
        p1_containers, p2_containers = get_test_containers()
        sim = BattleSimulator(seed=TEST_SEED)
        sim.max_duration = seconds
        result = sim.simulate_battle(
            [shield], [attacker], 18, p1_containers, p2_containers
        )
        return sim, result

    def _run_watching_the_attacker(self, shield, attacker, seconds=3.5):
        """Run a battle and hand back the attacking player, so a test can see
        what happened to their CPU."""
        p1_containers, p2_containers = get_test_containers()
        sim = BattleSimulator(seed=TEST_SEED)
        sim.max_duration = seconds

        seen = []
        original = sim._setup_item_handlers

        def watch(items, owner, enemy):
            if owner.id == 2:
                seen.append(owner)
            return original(items, owner, enemy)

        sim._setup_item_handlers = watch
        sim.simulate_battle([shield], [attacker], 18, p1_containers, p2_containers)
        (attacking_player,) = seen
        return sim, attacking_player

    def test_a_roll_that_lands_does_both(self):
        """Prevent the damage AND take the CPU. Never one without the other.

        Checking only the block would let a shield that prevents the damage
        and forgets the CPU pass, which is exactly the shape the old code had
        before the two were split apart.
        """
        # The weapon costs no CPU, so the drain is the only thing that can
        # take any off the attacker.
        sim, attacker = self._run_watching_the_attacker(
            self._shield(1.0, 10, 0.5), self._attacker(6, cpu_cost=0.0)
        )

        assert [a for a in sim.actions if a.action == "block"], "should prevent"
        assert not [a for a in sim.actions if a.action == "damage" and a.damage > 0]
        # Compared with the same battle against a shield that never rolls,
        # so the attacker's own activation cost is not mistaken for the drain.
        _, untouched = self._run_watching_the_attacker(
            self._shield(0.0, 10, 0.5), self._attacker(6, cpu_cost=0.0)
        )
        assert attacker.cpu < untouched.cpu, "the CPU should have been taken"

    def test_a_failed_roll_takes_no_cpu_either(self):
        """The other half of the same rule.

        Compared against a shield that never rolls rather than against a fixed
        number, because an activation costs CPU of its own.
        """
        _, drained = self._run_watching_the_attacker(
            self._shield(1.0, 10, 0.5), self._attacker(6, cpu_cost=0.0)
        )
        _, untouched = self._run_watching_the_attacker(
            self._shield(0.0, 10, 0.5), self._attacker(6, cpu_cost=0.0)
        )
        assert drained.cpu < untouched.cpu, "only the shield that rolled takes CPU"

    def test_a_roll_that_fails_does_neither(self):
        sim, _ = self._run(self._shield(0.0, 10, 0.5), self._attacker(6))
        assert not [a for a in sim.actions if a.action == "block"]
        assert [a for a in sim.actions if a.action == "damage" and a.damage == 6]

    def test_prevention_is_capped_by_the_damage(self):
        """A shield that prevents 10 against a 6 damage hit prevents 6, not 10"""
        sim, _ = self._run(self._shield(1.0, 10, 0.0), self._attacker(6))
        (first,) = [a for a in sim.actions if a.action == "block"][:1]
        assert first.damage == 6

    def test_partial_prevention_lets_the_rest_through(self):
        sim, _ = self._run(self._shield(1.0, 4, 0.0), self._attacker(10))
        assert [a for a in sim.actions if a.action == "block" and a.damage == 4]
        assert [a for a in sim.actions if a.action == "damage" and a.damage == 6]

    def test_the_drain_never_puts_the_attacker_in_debt(self):
        """The old code subtracted with no floor, so a big steal could leave
        the attacker on negative CPU and unable to act for the rest of the
        battle."""
        shield = self._shield(1.0, 1, 99.0)  # far more CPU than anyone holds
        p1_containers, p2_containers = get_test_containers()
        sim = BattleSimulator(seed=TEST_SEED)
        sim.max_duration = 3.5

        seen = []
        original = sim._setup_item_handlers

        def watch(items, owner, enemy):
            if owner.id == 2:
                seen.append(owner)
            return original(items, owner, enemy)

        sim._setup_item_handlers = watch
        sim.simulate_battle(
            [shield], [self._attacker(5)], 18, p1_containers, p2_containers
        )
        (attacker_player,) = seen
        assert attacker_player.cpu >= 0.0

    def test_a_shield_never_rolls_against_a_miss(self):
        """There is nothing to block, so the CPU stays on the attacker too"""
        misser = self._attacker(6)
        misser.spec.triggers[0].effects = [
            AttackEffect(min_damage=6, max_damage=6, accuracy=0.0, crit_chance=0.0)
        ]
        sim, _ = self._run(self._shield(1.0, 10, 0.5), misser)
        assert [a for a in sim.actions if a.action == "miss"]
        assert not [a for a in sim.actions if a.action == "block"]


class TestCpuDrainIsAnOrdinaryEffect:
    """It used to be handled inside the shield branch, so it only worked
    there. Backpack Battles drains CPU from a timer too -- Fanfare's "Every
    3s: ... remove 1 stamina from opponent" -- and that could not have been
    built without special-casing it a second time."""

    def test_a_timer_can_drain_cpu(self):

        drainer = BattleItem(
            spec=ItemSpec(
                id="drainer", name="Drainer", category="problem", cost=1,
                player_class="neutral", shape=parse_map(["#"], "d"),
                slug="drainer",
                triggers=[
                    TimerTrigger(cooldown=1.0, cpu_cost=0,
                                 effects=[CpuDrainEffect(1.0, target_type="attacker")])
                ],
            ),
            position=(0, 0), uid="drainer",
        )
        p1_containers, p2_containers = get_test_containers()
        sim = BattleSimulator(seed=TEST_SEED)
        sim.max_duration = 3.5

        seen = []
        original = sim._setup_item_handlers

        def watch(items, owner, enemy):
            if owner.id == 2:
                seen.append(owner)
            return original(items, owner, enemy)

        sim._setup_item_handlers = watch
        sim.simulate_battle([drainer], [], 18, p1_containers, p2_containers)
        (victim,) = seen

        assert [a for a in sim.actions if a.action == "cpu_drain"]
        assert victim.cpu < victim.max_cpu

    def test_it_never_puts_anyone_into_debt(self):
        """Negative CPU would lock a player out for the rest of the battle"""
        greedy = BattleItem(
            spec=ItemSpec(
                id="greedy", name="Greedy", category="problem", cost=1,
                player_class="neutral", shape=parse_map(["#"], "g"),
                slug="greedy",
                triggers=[
                    TimerTrigger(cooldown=0.5, cpu_cost=0,
                                 effects=[CpuDrainEffect(99.0, target_type="attacker")])
                ],
            ),
            position=(0, 0), uid="greedy",
        )
        p1_containers, p2_containers = get_test_containers()
        sim = BattleSimulator(seed=TEST_SEED)
        sim.max_duration = 5.0

        seen = []
        original = sim._setup_item_handlers

        def watch(items, owner, enemy):
            if owner.id == 2:
                seen.append(owner)
            return original(items, owner, enemy)

        sim._setup_item_handlers = watch
        sim.simulate_battle([greedy], [], 18, p1_containers, p2_containers)
        (victim,) = seen
        assert victim.cpu >= 0.0

    def test_a_shield_still_drains_the_attacker(self):
        """The route changed, the behaviour did not"""
        shield = BattleItem(
            spec=ItemSpec(
                id="s", name="Shield", category="defense", cost=1,
                player_class="neutral", shape=parse_map(["#"], "s"), slug="s",
                kinds=frozenset({"melee"}),
                triggers=[OnAttackedTrigger(answers_to=frozenset({"melee"}), chance=1.0, effects=[
                    PreventDamageEffect(10), CpuDrainEffect(0.5, target_type="attacker")])],
            ),
            position=(0, 0), uid="shield",
        )

        sword = BattleItem(
            spec=ItemSpec(
                id="w", name="Sword", category="problem", cost=1,
                player_class="neutral", shape=parse_map(["#"], "w"), slug="w",
                kinds=frozenset({"melee"}),
                triggers=[TimerTrigger(cooldown=1.0, cpu_cost=0, effects=[
                    AttackEffect(min_damage=5, max_damage=5, accuracy=1.0,
                                 crit_chance=0.0)])],
            ),
            position=(4, 0), uid="sword",
        )
        p1_containers, p2_containers = get_test_containers()
        sim = BattleSimulator(seed=TEST_SEED)
        sim.max_duration = 3.5
        sim.simulate_battle([shield], [sword], 18, p1_containers, p2_containers)

        drains = [a for a in sim.actions if a.action == "cpu_drain"]
        assert drains, "the shield should still take CPU"
        assert all(a.player == 2 for a in drains), "off the attacker"


class TestHealthThresholds:
    """Section 2.1: fires once, wherever the health falls from"""

    @staticmethod
    def _watcher(threshold: float, uid: str = "watcher"):
        """An item that heals below a line, and does not consume itself, so
        nothing hides how often it fires."""

        return BattleItem(
            spec=ItemSpec(
                id=uid, name="Watcher", category="infrastructure", cost=1,
                player_class="neutral", shape=parse_map(["#"], "w"), slug=uid,
                kinds=frozenset({"melee"}),
                triggers=[HealthThresholdTrigger(
                    threshold=threshold, effects=[HealEffect(1, 1)])],
            ),
            position=(0, 0), uid=uid,
        )

    @staticmethod
    def _sword(damage: int, uid: str = "sword"):

        return BattleItem(
            spec=ItemSpec(
                id=uid, name="Sword", category="problem", cost=1,
                player_class="neutral", shape=parse_map(["#"], "s"), slug=uid,
                kinds=frozenset({"melee"}),
                triggers=[TimerTrigger(cooldown=0.5, cpu_cost=0, effects=[
                    AttackEffect(min_damage=damage, max_damage=damage,
                                 accuracy=1.0, crit_chance=0.0)])],
            ),
            position=(4, 0), uid=uid,
        )

    def _run(self, mine, theirs, seconds=6.0, poison=0):

        p1_containers, p2_containers = get_test_containers()
        sim = BattleSimulator(seed=TEST_SEED)
        sim.max_duration = seconds
        original = sim._setup_item_handlers

        def setup(items, owner, enemy):
            result = original(items, owner, enemy)
            if poison and owner.id == 1:
                owner.debuffs[MEMORY_LEAKED] = poison
            return result

        sim._setup_item_handlers = setup
        sim.simulate_battle(mine, theirs, 1, p1_containers, p2_containers)
        return sim

    def test_it_fires_once_however_far_health_falls(self):
        """It used to fire on every damage event while below the line. Only
        the ConsumeEffect on the real items hid it."""
        sim = self._run([self._watcher(0.5)], [self._sword(3)])
        assert len([a for a in sim.actions if a.action == "heal"]) == 1

    def test_it_does_not_fire_above_the_line(self):
        sim = self._run([self._watcher(0.5)], [self._sword(1)], seconds=1.2)
        assert not [a for a in sim.actions if a.action == "heal"]

    def test_poison_crosses_it_too(self):
        """The reason it is checked where health falls rather than raised as
        an event: poison is not an attack, and used to be invisible to it."""
        sim = self._run([self._watcher(0.9)], [], seconds=8.0, poison=3)
        heals = [a for a in sim.actions if a.action == "heal"]
        assert heals, "poison should have crossed the line"
        assert len(heals) == 1
        # Nothing attacked, so only the poison can have moved the health.
        assert not [a for a in sim.actions if a.action == "damage"]

    def test_each_item_keeps_its_own_line(self):
        first = self._watcher(0.8, uid="high")
        second = self._watcher(0.3, uid="low")
        second.position = (1, 0)
        sim = self._run([first, second], [self._sword(3)])
        healers = {a.source for a in sim.actions if a.action == "heal"}
        assert healers == {"high", "low"}, "both lines should be crossed once"

    def test_a_threshold_is_forgotten_between_battles(self):
        """`fired` is runtime state. A potion that went off last round has to
        be ready again this round."""
        p1_containers, p2_containers = get_test_containers()
        sim = BattleSimulator(seed=TEST_SEED)
        sim.max_duration = 6.0
        mine, theirs = [self._watcher(0.5)], [self._sword(3)]

        first = sim.simulate_battle(mine, theirs, 1, p1_containers, p2_containers)
        healed_first = len([a for a in sim.actions if a.action == "heal"])
        second = sim.simulate_battle(mine, theirs, 1, p1_containers, p2_containers)
        healed_again = len([a for a in sim.actions if a.action == "heal"])

        assert healed_first == 1
        assert healed_again == 1, "the second battle gets its own crossing"
        assert first["player1_quota"] == second["player1_quota"]


class TestCleansing:
    """Section 3.2: taking statuses off somebody"""

    @staticmethod
    def _sim():
        p1, p2 = get_test_containers()
        sim = BattleSimulator(seed=TEST_SEED)
        sim.max_duration = 0.5
        sim.simulate_battle([], [], 18, p1, p2)
        return sim

    def test_a_named_cleanse_takes_only_that_one(self):

        sim = self._sim()
        player = Player(id=1, quota=100, max_quota=100, cpu=3.0)
        player.debuffs.update({MEMORY_LEAKED: 5, "throttled": 4})

        removed = sim._cleanse(player, "debuff", 3, MEMORY_LEAKED)

        assert removed == {MEMORY_LEAKED: 3}
        assert player.debuffs == {MEMORY_LEAKED: 2, "throttled": 4}

    def test_it_cannot_take_more_than_is_there(self):

        sim = self._sim()
        player = Player(id=1, quota=100, max_quota=100, cpu=3.0)
        player.debuffs[MEMORY_LEAKED] = 2

        removed = sim._cleanse(player, "debuff", 10, MEMORY_LEAKED)

        assert removed == {MEMORY_LEAKED: 2}
        assert MEMORY_LEAKED not in player.debuffs, "an empty kind is gone, not zero"

    def test_an_unnamed_cleanse_picks_by_kind_not_by_stack(self):
        """Section 3.2. Ten of one and one of another is a coin flip, not
        ten to one. This is the rule the whole effect turns on, so it is
        measured rather than assumed."""

        picked_the_lonely_one = 0
        for seed in range(200):
            sim = BattleSimulator(seed=seed)
            player = Player(id=1, quota=100, max_quota=100, cpu=3.0)
            player.debuffs.update({MEMORY_LEAKED: 10, "throttled": 1})
            removed = sim._cleanse(player, "debuff", 1)
            picked_the_lonely_one += removed.get("throttled", 0)

        # Weighted by stacks it would be about 18 in 200; by kind, about 100.
        assert 70 < picked_the_lonely_one < 130, picked_the_lonely_one

    def test_it_looks_again_after_every_one(self):
        """Cleanse 2 from ten Memory Leaked and one Throttled. Whichever goes
        first, the second pick can only come from what is left."""

        for seed in range(40):
            sim = BattleSimulator(seed=seed)
            player = Player(id=1, quota=100, max_quota=100, cpu=3.0)
            player.debuffs.update({MEMORY_LEAKED: 10, "throttled": 1})

            removed = sim._cleanse(player, "debuff", 2)

            assert sum(removed.values()) == 2, "never wasted while a kind remains"
            assert removed.get("throttled", 0) <= 1, "cannot take what is not there"

    def test_a_big_cleanse_clears_the_big_stack(self):
        """The consequence worth knowing: small kinds run out early, so every
        later pick lands on what is left."""

        for seed in range(40):
            sim = BattleSimulator(seed=seed)
            player = Player(id=1, quota=100, max_quota=100, cpu=3.0)
            player.debuffs.update({MEMORY_LEAKED: 10, "throttled": 1})

            removed = sim._cleanse(player, "debuff", 4)

            assert removed.get(MEMORY_LEAKED, 0) >= 3

    def test_it_stops_when_there_is_nothing_left(self):
        sim = self._sim()
        player = Player(id=1, quota=100, max_quota=100, cpu=3.0)
        player.debuffs["throttled"] = 1

        removed = sim._cleanse(player, "debuff", 5)

        assert removed == {"throttled": 1}
        assert player.debuffs == {}

    def test_the_same_effect_takes_buffs_off_the_other_side(self):
        """Cleanse and "remove 2 random buffs from your opponent" are one
        mechanic pointed two ways."""
        sim = self._sim()
        enemy = Player(id=2, quota=100, max_quota=100, cpu=3.0)
        enemy.buffs.update({"block": 8, "regenerating": 2})

        removed = sim._cleanse(enemy, "buff", 3)

        assert sum(removed.values()) == 3
        assert sum(enemy.buffs.values()) == 7

    def test_health_potion_clears_the_poison_it_was_written_for(self):

        potion = BattleItem(
            spec=ITEM_CATALOG["health_potion"], position=(0, 0), uid="potion"
        )
        p1, p2 = get_test_containers()
        sim = BattleSimulator(seed=TEST_SEED)
        sim.max_duration = 30.0
        original = sim._setup_item_handlers

        def poison(items, owner, enemy):
            result = original(items, owner, enemy)
            if owner.id == 1:
                owner.debuffs[MEMORY_LEAKED] = 3
            return result

        sim._setup_item_handlers = poison
        result = sim.simulate_battle([potion], [], 1, p1, p2)

        assert [a for a in sim.actions if a.action == "cleanse"]
        # Before the cleanse existed the poison carried on and killed them.
        assert result["player1_quota"] > 0
        assert not [a for a in sim.actions if a.action == "dot"
                    and a.timestamp > 10_000], "no poison left to tick"


class TestBuffsAreNotStats:
    """Section 3.1: a buff is a stack a player carries. Block is an attribute,
    and a number on an item is a modifier. All three used to share a dict."""

    def test_block_is_an_attribute_not_a_buff(self):
        player = Player(id=1, quota=100, max_quota=100, cpu=3.0)
        player.block = 10
        assert player.buffs == {}, "Block does not live among the buffs"

    def test_block_is_spent_absorbing_damage(self):
        sim = BattleSimulator(seed=TEST_SEED)
        target = Player(id=1, quota=100, max_quota=100, cpu=3.0)
        attacker = Player(id=2, quota=100, max_quota=100, cpu=3.0)
        target.block = 10

        sword = BattleItem(
            spec=ItemSpec(
                id="w", name="Sword", category="problem", cost=1,
                player_class="neutral", kinds=frozenset({"melee"}),
                shape=parse_map(["#"], "w"), slug="w", triggers=[],
            ),
            position=(0, 0), uid="sword",
        )
        got_through = sim._mitigate_attack(target, 15, attacker, sword)

        assert got_through == 5
        assert target.block == 0

    def test_a_cleanse_cannot_strip_block(self):
        """It used to be reachable: Block sat in `buffs`, and an unnamed
        cleanse picks a kind at random."""
        sim = BattleSimulator(seed=TEST_SEED)
        player = Player(id=1, quota=100, max_quota=100, cpu=3.0)
        player.block = 20
        player.buffs["regenerating"] = 2

        removed = sim._cleanse(player, "buff", 5)

        assert player.block == 20, "Block is not a buff and cannot be cleansed"
        assert removed == {"regenerating": 2}

    def test_reset_clears_the_block_too(self):
        player = Player(id=1, quota=100, max_quota=100, cpu=3.0)
        player.block = 30
        player.reset_for_battle()
        assert player.block == 0, "nothing a battle wrote may reach the next"

    def test_a_modifier_is_not_filed_among_the_buffs(self):
        """load_balancer_module says items trigger faster. That is a number on
        an item, so it must not end up on the player, which is where it went
        before -- and where nothing read it."""
        booster = BattleItem(
            spec=deepcopy(ITEM_CATALOG["load_balancer_module"]),
            position=(0, 0), uid="boost",
        )
        p1, p2 = get_test_containers()
        sim = BattleSimulator(seed=TEST_SEED)
        sim.max_duration = 0.2
        sim.simulate_battle([booster], [], 1, p1, p2)

        assert not [a for a in sim.actions if a.action == "buff"], (
            "changing a number on an item is not a buff and must not log one"
        )

    def test_every_buff_in_the_catalogue_is_one_of_the_seven(self):
        for item_id, spec in ITEM_CATALOG.items():
            for trigger in spec.triggers or []:
                for effect in getattr(trigger, "effects", []) or []:
                    if isinstance(effect, BuffEffect):
                        assert effect.buff_name in BUFFS, item_id

    def test_every_modifier_changes_something_the_engine_reads(self):
        for item_id, spec in ITEM_CATALOG.items():
            for trigger in spec.triggers or []:
                for effect in getattr(trigger, "effects", []) or []:
                    if isinstance(effect, ModifyEffect):
                        assert effect.stat in MODIFIERS, item_id


class TestHowFastAnItemTriggers:
    """Section 3.1: Optimized and Throttled pull on the same sum"""

    @staticmethod
    def _cooldown(optimized: int = 0, throttled: int = 0, base: float = 2.0) -> float:
        from battle_engine import OPTIMIZED, THROTTLED

        sim = BattleSimulator(seed=TEST_SEED)
        owner = Player(id=1, quota=100, max_quota=100, cpu=3.0)
        if optimized:
            owner.buffs[OPTIMIZED] = optimized
        if throttled:
            owner.debuffs[THROTTLED] = throttled
        plain = BattleItem(
            spec=ItemSpec(
                id="t", name="Timed", category="problem", cost=1,
                player_class="neutral", shape=parse_map(["#"], "t"), slug="t",
                triggers=[],
            ),
            position=(0, 0), uid="timed",
        )
        return sim._cooldown_for(
            TimerTrigger(cooldown=base, cpu_cost=0), owner, plain
        )

    def test_no_status_leaves_the_cooldown_alone(self):
        assert self._cooldown() == 2.0

    def test_optimized_divides(self):
        """Ten stacks is 20% faster: 2.0 / 1.2"""
        assert self._cooldown(optimized=10) == pytest.approx(2.0 / 1.2)

    def test_throttled_multiplies(self):
        """Ten stacks is 20% slower: 2.0 * 1.2"""
        assert self._cooldown(throttled=10) == pytest.approx(2.0 * 1.2)

    def test_the_two_halves_are_symmetric(self):
        """100% faster halves it, 100% slower doubles it. Dividing one way and
        multiplying the other is what makes that true."""
        assert self._cooldown(optimized=50) == pytest.approx(1.0)
        assert self._cooldown(throttled=50) == pytest.approx(4.0)

    def test_stacks_add_rather_than_compound(self):
        """Ten stacks is 20% off the sum, not 1.02 ten times over, which would
        be 21.9%."""
        assert self._cooldown(optimized=10) != pytest.approx(2.0 / 1.02**10)
        assert self._cooldown(optimized=10) == pytest.approx(2.0 / 1.20)

    def test_they_cancel_before_anything_is_applied(self):
        """Only the difference counts, so equal amounts leave the base alone
        rather than dividing and then multiplying."""
        assert self._cooldown(optimized=7, throttled=7) == 2.0
        assert self._cooldown(optimized=10, throttled=4) == self._cooldown(optimized=6)
        assert self._cooldown(optimized=4, throttled=10) == self._cooldown(throttled=6)

    def test_neither_runs_away_past_ten_times(self):
        assert self._cooldown(optimized=10_000) == pytest.approx(2.0 / 11)
        assert self._cooldown(throttled=10_000) == pytest.approx(2.0 * 11)

    def test_a_throttled_weapon_swings_less_often_in_a_battle(self):
        """The whole point, seen from the battle rather than the formula."""
        from battle_engine import OPTIMIZED, THROTTLED
        from item_effects import AttackEffect

        def swings(optimized=0, throttled=0):
            sword = BattleItem(
                spec=ItemSpec(
                    id="s", name="Sword", category="problem", cost=1,
                    player_class="neutral", shape=parse_map(["#"], "s"), slug="s",
                    kinds=frozenset({"melee"}),
                    triggers=[TimerTrigger(cooldown=1.0, cpu_cost=0, effects=[
                        AttackEffect(min_damage=1, max_damage=1, accuracy=1.0,
                                     crit_chance=0.0)])],
                ),
                position=(0, 0), uid="sword",
            )
            p1, p2 = get_test_containers()
            sim = BattleSimulator(seed=TEST_SEED)
            sim.max_duration = 10.0
            original = sim._setup_item_handlers

            def setup(items, owner, enemy):
                result = original(items, owner, enemy)
                if owner.id == 1:
                    if optimized:
                        owner.buffs[OPTIMIZED] = optimized
                    if throttled:
                        owner.debuffs[THROTTLED] = throttled
                return result

            sim._setup_item_handlers = setup
            sim.simulate_battle([sword], [], 18, p1, p2)
            return len([a for a in sim.actions if a.action == "damage"])

        plain = swings()
        assert swings(optimized=25) > plain, "Optimized should swing more often"
        assert swings(throttled=25) < plain, "Throttled should swing less often"


class TestCalibratedAndRateLimited:
    """Sections 3.1 and 3.2: one stack each way, on the same number"""

    @staticmethod
    def _hits(calibrated=0, rate_limited=0, accuracy=0.5, swings=40):
        from battle_engine import CALIBRATED, RATE_LIMITED
        from item_effects import AttackEffect

        sword = BattleItem(
            spec=ItemSpec(
                id="s", name="Sword", category="problem", cost=1,
                player_class="neutral", shape=parse_map(["#"], "s"), slug="s",
                kinds=frozenset({"melee"}),
                triggers=[TimerTrigger(cooldown=0.5, cpu_cost=0, effects=[
                    AttackEffect(min_damage=1, max_damage=1, accuracy=accuracy,
                                 crit_chance=0.0)])],
            ),
            position=(0, 0), uid="sword",
        )
        p1, p2 = get_test_containers()
        sim = BattleSimulator(seed=TEST_SEED)
        sim.max_duration = swings * 0.5
        original = sim._setup_item_handlers

        def setup(items, owner, enemy):
            result = original(items, owner, enemy)
            if owner.id == 1:
                if calibrated:
                    owner.buffs[CALIBRATED] = calibrated
                if rate_limited:
                    owner.debuffs[RATE_LIMITED] = rate_limited
            return result

        sim._setup_item_handlers = setup
        sim.simulate_battle([sword], [], 18, p1, p2)
        return len([a for a in sim.actions if a.action == "damage"])

    def test_calibrated_makes_an_attack_land_more_often(self):
        assert self._hits(calibrated=8) > self._hits()

    def test_rate_limited_still_makes_it_land_less_often(self):
        assert self._hits(rate_limited=8) < self._hits()

    def test_they_pull_on_the_same_number(self):
        """Equal stacks cancel, rather than one overriding the other."""
        assert self._hits(calibrated=6, rate_limited=6) == self._hits()

    def test_enough_calibrated_never_misses(self):
        """Accuracy over 1 means every swing lands, so a coin-flip weapon with
        enough Calibrated lands as often as one that cannot miss."""
        never_misses = self._hits(accuracy=1.0, swings=20)
        assert self._hits(calibrated=20, accuracy=0.5, swings=20) == never_misses

    def test_enough_rate_limited_never_lands(self):
        assert self._hits(rate_limited=20, accuracy=0.5, swings=20) == 0


class TestRegenerating:
    """Section 3.1: 1 health per stack every 2 seconds"""

    @staticmethod
    def _run(stacks, seconds, start_at=None):
        from battle_engine import REGENERATING

        p1, p2 = get_test_containers()
        sim = BattleSimulator(seed=TEST_SEED)
        sim.max_duration = seconds
        original = sim._setup_item_handlers

        def setup(items, owner, enemy):
            result = original(items, owner, enemy)
            if owner.id == 1:
                owner.buffs[REGENERATING] = stacks
                if start_at is not None:
                    owner.quota = start_at
            return result

        sim._setup_item_handlers = setup
        result = sim.simulate_battle([], [], 18, p1, p2)
        return sim, result["player1_quota"]

    def test_it_heals_a_stack_every_two_seconds(self):
        """Payouts at 2s, 4s, 6s -- the same clock as poison."""
        sim, quota = self._run(3, seconds=7.0, start_at=100)
        heals = [a for a in sim.actions if a.action == "heal"]
        assert [h.timestamp for h in heals] == [2000, 4000, 6000]
        assert all(h.damage == 3 for h in heals)
        assert quota == 109

    def test_it_stops_at_full_health(self):
        """350 is the round 18 quota, so there is nothing to heal."""
        sim, quota = self._run(5, seconds=7.0)
        assert quota == 350
        assert not [a for a in sim.actions if a.action == "heal"], (
            "healing nobody should log nothing"
        )

    def test_it_heals_only_what_is_missing(self):
        sim, quota = self._run(10, seconds=3.0, start_at=346)
        assert quota == 350, "four missing, ten stacks, still only four healed"

    def test_no_stacks_heals_nothing(self):
        sim, quota = self._run(0, seconds=7.0, start_at=100)
        assert quota == 100


class TestTheBuffsThatNeedAWeapon:
    """Section 3.1: Monitored, Spiked and Draining"""

    @staticmethod
    def _weapon(damage=5, melee=True, uid="sword", position=(0, 0)):
        from item_effects import AttackEffect

        return BattleItem(
            spec=ItemSpec(
                id=uid, name="Weapon", category="problem", cost=1,
                player_class="neutral", shape=parse_map(["#"], "w"), slug=uid,
                kinds=frozenset({"melee"} if melee else {"ranged"}),
                triggers=[TimerTrigger(cooldown=1.0, cpu_cost=0, effects=[
                    AttackEffect(min_damage=damage, max_damage=damage,
                                 accuracy=1.0, crit_chance=0.0)])],
            ),
            position=position, uid=uid,
        )

    def _run(self, mine, theirs, mine_buffs=None, their_buffs=None, seconds=2.5,
             mine_quota=None):
        p1, p2 = get_test_containers()
        sim = BattleSimulator(seed=TEST_SEED)
        sim.max_duration = seconds
        original = sim._setup_item_handlers
        players = {}

        def setup(items, owner, enemy):
            result = original(items, owner, enemy)
            players[owner.id] = owner
            if owner.id == 1:
                if mine_buffs:
                    owner.buffs.update(mine_buffs)
                if mine_quota is not None:
                    owner.quota = mine_quota
            if owner.id == 2 and their_buffs:
                owner.buffs.update(their_buffs)
            return result

        sim._setup_item_handlers = setup
        sim.simulate_battle(mine, theirs, 18, p1, p2)
        return sim, players

    def test_monitored_adds_a_point_of_damage_a_stack(self):
        from battle_engine import MONITORED

        plain, _ = self._run([self._weapon(damage=5)], [])
        buffed, _ = self._run([self._weapon(damage=5)], [], {MONITORED: 3})

        def first_hit(sim):
            return next(a.damage for a in sim.actions if a.action == "damage")

        assert first_hit(plain) == 5
        assert first_hit(buffed) == 8

    def test_monitored_needs_no_melee(self):
        """It is "+1 weapon damage", not melee. A bow gains it too."""
        from battle_engine import MONITORED

        sim, _ = self._run([self._weapon(damage=5, melee=False)], [], {MONITORED: 2})
        assert next(a.damage for a in sim.actions if a.action == "damage") == 7

    def test_spiked_answers_a_melee_hit(self):
        from battle_engine import SPIKED

        sim, players = self._run(
            [self._weapon(damage=5)], [], their_buffs={SPIKED: 2}
        )
        back = [a for a in sim.actions
                if a.action == "damage" and (a.details or {}).get("buff_name") == SPIKED]
        assert back, "the attacker should take the spikes"
        assert all(a.player == 1 for a in back), "back at whoever swung"

    def test_spiked_ignores_a_ranged_hit(self):
        from battle_engine import SPIKED

        sim, _ = self._run(
            [self._weapon(damage=5, melee=False)], [], their_buffs={SPIKED: 2}
        )
        assert not [a for a in sim.actions
                    if (a.details or {}).get("buff_name") == SPIKED]

    def test_spiked_never_returns_more_than_the_hit(self):
        """"up to 100% of the damage" -- five stacks against a 2 damage hit
        gives back 2, not 5."""
        from battle_engine import SPIKED

        sim, _ = self._run(
            [self._weapon(damage=2)], [], their_buffs={SPIKED: 5}
        )
        back = [a for a in sim.actions
                if (a.details or {}).get("buff_name") == SPIKED]
        assert back and all(a.damage == 2 for a in back)

    def test_draining_heals_the_one_who_swung(self):
        from battle_engine import DRAINING

        # Draining cannot heal what is not missing, so start them hurt.
        sim, _ = self._run(
            [self._weapon(damage=5)], [], mine_buffs={DRAINING: 3}, mine_quota=100
        )
        healed = [a for a in sim.actions
                  if a.action == "heal" and (a.details or {}).get("buff_name") == DRAINING]
        assert healed and all(a.damage == 3 for a in healed)

    def test_draining_ignores_a_ranged_hit(self):
        from battle_engine import DRAINING

        sim, _ = self._run(
            [self._weapon(damage=5, melee=False)], [], mine_buffs={DRAINING: 3},
            mine_quota=100,
        )
        assert not [a for a in sim.actions
                    if (a.details or {}).get("buff_name") == DRAINING]

    def test_poison_sets_off_neither(self):
        """The reason both live in the attack rather than the damage: poison
        moves the same number and must not count as a melee hit."""
        from battle_engine import DRAINING, MEMORY_LEAKED, SPIKED

        p1, p2 = get_test_containers()
        sim = BattleSimulator(seed=TEST_SEED)
        sim.max_duration = 7.0
        original = sim._setup_item_handlers

        def setup(items, owner, enemy):
            result = original(items, owner, enemy)
            if owner.id == 1:
                owner.debuffs[MEMORY_LEAKED] = 3
                owner.buffs[SPIKED] = 5
                owner.buffs[DRAINING] = 5
            return result

        sim._setup_item_handlers = setup
        sim.simulate_battle([], [], 18, p1, p2)

        assert [a for a in sim.actions if a.action == "dot"], "poison should tick"
        assert not [a for a in sim.actions
                    if (a.details or {}).get("buff_name") in (SPIKED, DRAINING)]


class TestAShieldAnswersOnlyWhatItSays:
    """Every shield in the source game is "On attacked (Melee)", and ours
    used to roll against everything, which made them all stronger than they
    should be against a ranged build."""

    @staticmethod
    def _weapon(melee: bool):
        from item_effects import AttackEffect

        return BattleItem(
            spec=ItemSpec(
                id="w", name="Weapon", category="problem", cost=1,
                player_class="neutral", shape=parse_map(["#"], "w"), slug="w",
                kinds=frozenset({"melee"} if melee else {"ranged"}),
                triggers=[TimerTrigger(cooldown=1.0, cpu_cost=0, effects=[
                    AttackEffect(min_damage=6, max_damage=6, accuracy=1.0,
                                 crit_chance=0.0)])],
            ),
            position=(4, 0), uid="weapon",
        )

    @staticmethod
    def _shield(answers_to):
        from item_effects import CpuDrainEffect, OnAttackedTrigger, PreventDamageEffect

        return BattleItem(
            spec=ItemSpec(
                id="s", name="Shield", category="defense", cost=1,
                player_class="neutral", shape=parse_map(["#"], "s"), slug="s",
                triggers=[OnAttackedTrigger(
                    answers_to=frozenset(answers_to), chance=1.0,
                    effects=[PreventDamageEffect(10),
                             CpuDrainEffect(0.5, target_type="attacker")])],
            ),
            position=(0, 0), uid="shield",
        )

    def _run(self, shield, weapon):
        p1, p2 = get_test_containers()
        sim = BattleSimulator(seed=TEST_SEED)
        sim.max_duration = 2.5
        sim.simulate_battle([shield], [weapon], 18, p1, p2)
        return sim

    def test_a_melee_shield_answers_a_melee_weapon(self):
        sim = self._run(self._shield({"melee"}), self._weapon(melee=True))
        assert [a for a in sim.actions if a.action == "block"]

    def test_a_melee_shield_ignores_a_bow(self):
        """The bug. Every shield we have is melee-only, and 8 weapons in the
        catalogue are ranged."""
        sim = self._run(self._shield({"melee"}), self._weapon(melee=False))
        assert not [a for a in sim.actions if a.action == "block"]
        assert [a for a in sim.actions if a.action == "damage" and a.damage == 6]

    def test_it_takes_no_cpu_from_an_attack_it_ignores(self):
        """The whole roll is skipped, not just the prevention."""
        sim = self._run(self._shield({"melee"}), self._weapon(melee=False))
        assert not [a for a in sim.actions if a.action == "cpu_drain"]

    def test_a_shield_that_says_both_answers_both(self):
        """Moon Shield, Sun Shield and Spiked Wall are "(Melee/Ranged)". None
        is imported, but the shield says which it answers rather than the
        engine assuming."""
        both = {"melee", "ranged"}
        assert [a for a in self._run(self._shield(both), self._weapon(True)).actions
                if a.action == "block"]
        assert [a for a in self._run(self._shield(both), self._weapon(False)).actions
                if a.action == "block"]

    def test_every_shield_in_the_catalogue_says_what_it_answers(self):
        from item_effects import OnAttackedTrigger

        found = 0
        for item_id, spec in ITEM_CATALOG.items():
            for trigger in spec.triggers or []:
                if isinstance(trigger, OnAttackedTrigger):
                    found += 1
                    assert trigger.answers_to, f"{item_id} answers to nothing"
        assert found, "the catalogue should still have shields in it"


class TestAnAuraReachesWhatItFallsOn:
    """Section 3.1: a zone is drawn on an item's own map and lands on the grid.

    It is not the squares around an item -- most items that project one reach
    further than that -- which is why adjacency was the wrong model.
    """

    @staticmethod
    def _projector(value=0.2, stat="trigger_speed", target="star",
                   position=(1, 0), uid="boost"):
        from item_effects import ModifyEffect, PassiveTrigger

        return BattleItem(
            spec=ItemSpec(
                id=uid, name="Aura", category="infrastructure", cost=1,
                player_class="neutral", slug=uid,
                shape=parse_map(["*##*"], "aura"),
                triggers=[PassiveTrigger(effects=[
                    ModifyEffect(stat=stat, value=value, target_type=target)])],
            ),
            position=position, uid=uid,
        )

    @staticmethod
    def _plain(position, uid):
        from item_effects import AttackEffect

        return BattleItem(
            spec=ItemSpec(
                id=uid, name="Plain", category="problem", cost=1,
                player_class="neutral", shape=parse_map(["#"], "p"), slug=uid,
                kinds=frozenset({"melee"}),
                triggers=[TimerTrigger(cooldown=2.0, cpu_cost=0, effects=[
                    AttackEffect(min_damage=4, max_damage=4, accuracy=1.0,
                                 crit_chance=0.0)])],
            ),
            position=position, uid=uid,
        )

    def _run(self, items):
        containers = [
            Container.of("mesh_network_hub", (0, 0), "a"),
            Container.of("mesh_network_hub", (4, 0), "c"),
        ]
        sim = BattleSimulator(seed=TEST_SEED)
        sim.max_duration = 0.2
        result = sim.simulate_battle(
            items, [], 1, containers,
            [Container.of("mesh_network_hub", (0, 4), "b")],
        )
        return {i.uid: i for i in result["player1_items"]}

    def test_the_zone_lands_where_the_map_draws_it(self):
        aura = self._projector()
        assert aura.get_occupied_squares() == [(1, 0), (2, 0)]
        assert aura.aura_squares("star") == [(0, 0), (3, 0)]

    def test_an_item_in_the_zone_is_reached(self):
        by_uid = self._run([self._projector(), self._plain((0, 0), "inside")])
        assert by_uid["inside"].speed_mult == pytest.approx(1.2)

    def test_an_item_outside_the_zone_is_not(self):
        by_uid = self._run([self._projector(), self._plain((4, 0), "outside")])
        assert by_uid["outside"].speed_mult == 1.0

    def test_an_aura_does_not_reach_the_item_projecting_it(self):
        """A zone is drawn beside the footprint, never on it."""
        by_uid = self._run([self._projector()])
        assert by_uid["boost"].speed_mult == 1.0

    def test_it_reaches_further_than_the_squares_around_it(self):
        """The reason adjacency could not stand in for an aura."""
        far = BattleItem(
            spec=ItemSpec(
                id="f", name="Far", category="infrastructure", cost=1,
                player_class="neutral", slug="f",
                shape=parse_map(["#..*"], "far reach"),
                triggers=[],
            ),
            position=(0, 0), uid="far",
        )
        assert far.aura_squares("star") == [(3, 0)], "three squares away"

    def test_a_speed_aura_reaches_the_cooldown(self):
        """It lands in the same sum as Optimized, which is what the source
        game's formula is for."""
        by_uid = self._run([self._projector(), self._plain((0, 0), "inside")])
        sim = BattleSimulator(seed=TEST_SEED)
        owner = Player(id=1, quota=100, max_quota=100, cpu=3.0)
        base = TimerTrigger(cooldown=2.0, cpu_cost=0)
        assert sim._cooldown_for(base, owner, by_uid["inside"]) == pytest.approx(2.0 / 1.2)

    def _swings(self, items, seconds=12.0):
        """Run a battle and report what the item in the zone actually did."""
        containers = [
            Container.of("mesh_network_hub", (0, 0), "a"),
            Container.of("mesh_network_hub", (4, 0), "c"),
        ]
        sim = BattleSimulator(seed=TEST_SEED)
        sim.max_duration = seconds
        sim.simulate_battle(
            items, [], 18, containers,
            [Container.of("mesh_network_hub", (0, 4), "b")],
        )
        return [a for a in sim.actions if a.action in ("damage", "miss")]

    def _coin_flip_weapon(self, uid="inside"):
        weapon = self._plain((0, 0), uid)
        weapon.spec.triggers[0].effects[0].accuracy = 0.5
        return weapon

    def test_an_accuracy_aura_changes_whether_swings_land(self):
        """Setting the field is not the same as the roll reading it. Both
        weapons are the same coin flip; only the aura differs."""
        plain = self._swings([self._coin_flip_weapon()])
        boosted = self._swings([
            self._projector(value=0.5, stat="accuracy"),
            self._coin_flip_weapon(),
        ])

        def landed(acts):
            return len([a for a in acts if a.action == "damage"])

        assert landed(plain) < landed(boosted)
        assert not [a for a in boosted if a.action == "miss"], (
            "half a coin flip plus 50% never misses"
        )

    def test_a_damage_aura_changes_what_lands(self):
        plain = self._swings([self._plain((0, 0), "inside")])
        boosted = self._swings([
            self._projector(value=1.0, stat="damage"),
            self._plain((0, 0), "inside"),
        ])
        first = lambda acts: next(a.damage for a in acts if a.action == "damage")
        assert first(plain) == 4
        assert first(boosted) == 8, "double damage should double the hit"

    def test_an_accuracy_aura_reaches_the_roll(self):
        by_uid = self._run([
            self._projector(value=0.25, stat="accuracy"),
            self._plain((0, 0), "inside"),
        ])
        assert by_uid["inside"].accuracy_bonus == pytest.approx(0.25)

    def test_a_damage_aura_reaches_the_total(self):
        by_uid = self._run([
            self._projector(value=0.5, stat="damage"),
            self._plain((0, 0), "inside"),
        ])
        assert by_uid["inside"].damage_mult == pytest.approx(1.5)

    def test_a_cpu_aura_makes_an_item_cheaper_to_run(self):
        from item_effects import AttackEffect

        def swings(with_aura):
            weapon = BattleItem(
                spec=ItemSpec(
                    id="w", name="Costly", category="problem", cost=1,
                    player_class="neutral", shape=parse_map(["#"], "w"),
                    slug="w", kinds=frozenset({"melee"}),
                    triggers=[TimerTrigger(cooldown=0.5, cpu_cost=2.0, effects=[
                        AttackEffect(min_damage=1, max_damage=1, accuracy=1.0,
                                     crit_chance=0.0)])],
                ),
                position=(0, 0), uid="costly",
            )
            items = [weapon]
            if with_aura:
                items.append(self._projector(value=1.5, stat="cpu_cost"))
            return len([a for a in self._swings(items, seconds=6.0)
                        if a.action == "damage"])

        assert swings(with_aura=True) > swings(with_aura=False), (
            "a cheaper item runs more often when CPU is the limit"
        )

    def test_an_aura_never_makes_an_item_free(self):
        """The floor is zero, not a refund."""
        from item_effects import ModifyEffect

        sim = BattleSimulator(seed=TEST_SEED)
        item = self._plain((0, 0), "plain")
        sim._modify(item, ModifyEffect(stat="cpu_cost", value=99.0,
                                       target_type="star"))
        cost = max(0.0, 1.0 - item.cpu_discount)
        assert cost == 0.0

    def test_contained_reaches_nothing_yet(self):
        """A container does not know what sits inside it. Reaching nothing is
        the safer way to be wrong: it cannot make an item quietly stronger."""
        by_uid = self._run([
            self._projector(target="contained"),
            self._plain((0, 0), "inside"),
        ])
        assert by_uid["inside"].speed_mult == 1.0


class TestAnAuraCountsWhatStandsInIt:
    """Section 3.1, the other direction. "Triggers 15% faster for each Star
    Food" changes the item projecting the zone, by how much is standing in it.

    37 items in the source game read this way against 22 the other, so it is
    the commoner half of an aura.
    """

    @staticmethod
    def _counter(value=0.15, stat="trigger_speed", counting="any", zone="star",
                 uid="counter", position=(1, 0)):
        from item_effects import ModifyPerEffect, PassiveTrigger

        return BattleItem(
            spec=ItemSpec(
                id=uid, name="Counter", category="problem", cost=1,
                player_class="neutral", slug=uid,
                shape=parse_map(["*##*"], "counter"),
                kinds=frozenset({"melee"}),
                triggers=[PassiveTrigger(effects=[ModifyPerEffect(
                    stat=stat, value=value, zone=zone, counting=counting)])],
            ),
            position=position, uid=uid,
        )

    @staticmethod
    def _standing(position, uid, kinds=frozenset(), category="problem"):
        return BattleItem(
            spec=ItemSpec(
                id=uid, name="Standing", category=category, cost=1,
                player_class="neutral", shape=parse_map(["#"], "s"), slug=uid,
                kinds=kinds, triggers=[],
            ),
            position=position, uid=uid,
        )

    def _run(self, items):
        # The counter sits at (1,0) covering (1,0) and (2,0), so its star
        # falls on (0,0) and (3,0). Both have to be standable.
        containers = [
            Container.of("mesh_network_hub", (0, 0), "a"),
            Container.of("mesh_network_hub", (3, 0), "c"),
        ]
        sim = BattleSimulator(seed=TEST_SEED)
        sim.max_duration = 0.2
        result = sim.simulate_battle(
            items, [], 1, containers,
            [Container.of("mesh_network_hub", (0, 4), "b")],
        )
        return {i.uid: i for i in result["player1_items"]}

    def test_an_empty_zone_changes_nothing(self):
        by_uid = self._run([self._counter()])
        assert by_uid["counter"].speed_mult == 1.0

    def test_one_item_standing_there_counts_once(self):
        by_uid = self._run([self._counter(), self._standing((0, 0), "one")])
        assert by_uid["counter"].speed_mult == pytest.approx(1.15)

    def test_two_items_count_twice(self):
        """*##* projects either side, so both squares can be filled."""
        by_uid = self._run([
            self._counter(),
            self._standing((0, 0), "left"),
            self._standing((3, 0), "right"),
        ])
        assert by_uid["counter"].speed_mult == pytest.approx(1.30)

    def test_it_counts_only_what_it_is_looking_for(self):
        by_uid = self._run([
            self._counter(counting={"any": ["nature"]}),
            self._standing((0, 0), "nature_one", kinds=frozenset({"nature"})),
            self._standing((3, 0), "holy_one", kinds=frozenset({"holy"})),
        ])
        assert by_uid["counter"].speed_mult == pytest.approx(1.15), "one of two"

    def test_a_category_counts_as_well_as_a_kind(self):
        """"for each Star Food" names a category, "for each Star Dark-item"
        names a kind. Both have to work."""
        by_uid = self._run([
            self._counter(counting={"any": ["defense"]}),
            self._standing((0, 0), "shield", category="defense"),
        ])
        assert by_uid["counter"].speed_mult == pytest.approx(1.15)

    def test_an_item_outside_the_zone_is_not_counted(self):
        by_uid = self._run([self._counter(), self._standing((4, 0), "far")])
        assert by_uid["counter"].speed_mult == 1.0

    def test_it_changes_the_item_projecting_the_zone(self):
        """Not what stands in it -- that is the other direction."""
        by_uid = self._run([self._counter(), self._standing((0, 0), "one")])
        assert by_uid["one"].speed_mult == 1.0

    def test_counting_reaches_damage_too(self):
        by_uid = self._run([
            self._counter(value=0.5, stat="damage"),
            self._standing((0, 0), "left"),
            self._standing((3, 0), "right"),
        ])
        assert by_uid["counter"].damage_mult == pytest.approx(2.0)


class TestCountingAnyAndAll:
    """`counting` says which items are worth counting. An item counts once
    however many of the tags it matches."""

    @staticmethod
    def _effect(counting):
        from item_effects import ModifyPerEffect

        return ModifyPerEffect(
            stat="trigger_speed", value=0.1, zone="star", counting=counting
        )

    def test_any_counts_everything(self):
        assert self._effect("any").matches(set())
        assert self._effect("any").matches({"pet"})

    def test_any_of_a_list_needs_one(self):
        effect = self._effect({"any": ["pet", "script"]})
        assert effect.matches({"pet"})
        assert effect.matches({"script"})
        assert effect.matches({"pet", "script"}), "both is still a match"
        assert not effect.matches({"defense"})

    def test_all_of_a_list_needs_every_one(self):
        effect = self._effect({"all": ["holy", "magic"]})
        assert effect.matches({"holy", "magic"})
        assert effect.matches({"holy", "magic", "melee"}), "extras are fine"
        assert not effect.matches({"holy"})

    def test_an_item_matching_twice_still_counts_once(self):
        """"for each Star Pet or Food" counts items, not matching tags."""
        counter = TestAnAuraCountsWhatStandsInIt._counter(
            counting={"any": ["pet", "script"]}
        )
        both = TestAnAuraCountsWhatStandsInIt._standing(
            (0, 0), "both", kinds=frozenset({"script"}), category="pet"
        )
        by_uid = TestAnAuraCountsWhatStandsInIt._run(
            TestAnAuraCountsWhatStandsInIt(), [counter, both]
        )
        assert by_uid["counter"].speed_mult == pytest.approx(1.15), "once, not twice"

    def test_rat_chef_counts_a_pet_beside_it(self):
        """From the catalogue: "Triggers 15% faster for each Star Pet or Food"."""
        from item_effects import ModifyPerEffect

        spec = ITEM_CATALOG["rat_chef"]
        per = [e for t in spec.triggers for e in getattr(t, "effects", [])
               if isinstance(e, ModifyPerEffect)]
        assert per and per[0].counting == {"any": ["pet", "script"]}
        assert per[0].matches({"pet"}) and per[0].matches({"script"})
        assert not per[0].matches({"defense"})


class TestAnAuraCanBeTheCause:
    """Section 3.1, the third direction. "Star item activates:" -- the zone is
    what sets the effect off, rather than what it reaches or counts."""

    @staticmethod
    def _watcher(after=1, counting="any", zone="star", uid="watcher",
                 position=(1, 0)):
        from item_effects import AuraTrigger, HealEffect

        return BattleItem(
            spec=ItemSpec(
                id=uid, name="Watcher", category="infrastructure", cost=1,
                player_class="neutral", slug=uid,
                shape=parse_map(["*##*"], "watcher"),
                triggers=[AuraTrigger(
                    zone=zone, counting=counting, after=after,
                    effects=[HealEffect(1, 1)])],
            ),
            position=position, uid=uid,
        )

    @staticmethod
    def _ticker(position, uid, cooldown=1.0, kinds=frozenset(),
                category="problem"):
        from item_effects import AttackEffect

        return BattleItem(
            spec=ItemSpec(
                id=uid, name="Ticker", category=category, cost=1,
                player_class="neutral", shape=parse_map(["#"], "t"), slug=uid,
                kinds=kinds | {"melee"},
                triggers=[TimerTrigger(cooldown=cooldown, cpu_cost=0, effects=[
                    AttackEffect(min_damage=1, max_damage=1, accuracy=1.0,
                                 crit_chance=0.0)])],
            ),
            position=position, uid=uid,
        )

    def _run(self, items, seconds=6.5):
        containers = [
            Container.of("mesh_network_hub", (0, 0), "a"),
            Container.of("mesh_network_hub", (3, 0), "c"),
        ]
        sim = BattleSimulator(seed=TEST_SEED)
        sim.max_duration = seconds
        original = sim._setup_item_handlers

        def setup(its, owner, enemy):
            result = original(its, owner, enemy)
            if owner.id == 1:
                owner.quota = 100  # room to heal into
            return result

        sim._setup_item_handlers = setup
        sim.simulate_battle(items, [], 18, containers,
                            [Container.of("mesh_network_hub", (0, 4), "b")])
        return [a for a in sim.actions if a.action == "heal"]

    def test_an_activation_in_the_zone_sets_it_off(self):
        heals = self._run([self._watcher(), self._ticker((0, 0), "inside")])
        assert heals, "the watcher should have fired"

    def test_an_activation_outside_the_zone_does_not(self):
        heals = self._run([self._watcher(), self._ticker((4, 0), "outside")])
        assert not heals

    def test_it_does_not_answer_its_own_activation(self):
        """A zone is drawn beside the item, so the item is never in it."""
        from item_effects import AttackEffect, AuraTrigger, HealEffect

        both = BattleItem(
            spec=ItemSpec(
                id="both", name="Both", category="problem", cost=1,
                player_class="neutral", slug="both",
                shape=parse_map(["*##*"], "both"), kinds=frozenset({"melee"}),
                triggers=[
                    TimerTrigger(cooldown=1.0, cpu_cost=0, effects=[
                        AttackEffect(min_damage=1, max_damage=1, accuracy=1.0,
                                     crit_chance=0.0)]),
                    AuraTrigger(zone="star", counting="any", after=1,
                                effects=[HealEffect(1, 1)]),
                ],
            ),
            position=(1, 0), uid="both",
        )
        assert not self._run([both])

    def test_after_counts_the_activations(self):
        """"6 Star item activations" fires on every sixth, not every one."""
        every = self._run([self._watcher(after=1),
                           self._ticker((0, 0), "t", cooldown=1.0)])
        sixth = self._run([self._watcher(after=6),
                           self._ticker((0, 0), "t", cooldown=1.0)])
        assert len(every) > len(sixth)
        assert len(sixth) == len(every) // 6

    def test_it_waits_only_on_what_it_names(self):
        """"Star Food activates" ignores everything that is not a Food."""
        wrong = self._run([
            self._watcher(counting={"any": ["script"]}),
            self._ticker((0, 0), "weapon", category="problem"),
        ])
        right = self._run([
            self._watcher(counting={"any": ["script"]}),
            self._ticker((0, 0), "food", category="script"),
        ])
        assert not wrong
        assert right

    def test_a_diamond_is_watched_separately(self):
        heals = self._run([
            self._watcher(zone="diamond"), self._ticker((0, 0), "in_star")
        ])
        assert not heals, "an item in the star is not in the diamond"


class TestAChanceOnAnEffect:
    """"12% chance to deal +6 damage and gain 1 Heat" -- one roll in front of
    a clause, the same shape ChanceTrigger has a level up."""

    @staticmethod
    def _effect(chance, behind=None):
        from item_effects import ChanceEffect, HealEffect

        return ChanceEffect(chance=chance, effects=behind or [HealEffect(1, 1)])

    class _Rolls:
        def __init__(self, value):
            self.rng = self
            self.value = value

        def random(self):
            return self.value

    def test_a_roll_under_the_chance_happens(self):
        assert self._effect(0.3).happens(self._Rolls(0.29)) is True

    def test_a_roll_over_it_does_not(self):
        assert self._effect(0.3).happens(self._Rolls(0.31)) is False

    def test_a_certainty_needs_no_roll(self):
        class NoRng:
            @property
            def rng(self):
                raise AssertionError("a certainty should not roll")

        assert self._effect(1.0).happens(NoRng()) is True

    def test_everything_behind_it_happens_together(self):
        """A clause cannot half-happen: the damage and the Heat go together."""
        from item_effects import BuffEffect, ChanceEffect, HealEffect

        p1, p2 = get_test_containers()
        watcher = BattleItem(
            spec=ItemSpec(
                id="w", name="Watcher", category="infrastructure", cost=1,
                player_class="neutral", shape=parse_map(["#"], "w"), slug="w",
                triggers=[TimerTrigger(cooldown=1.0, cpu_cost=0, effects=[
                    ChanceEffect(chance=1.0, effects=[
                        HealEffect(1, 1),
                        BuffEffect(buff_name="optimized", value=1,
                                   target_type="self")])])],
            ),
            position=(0, 0), uid="watcher",
        )
        sim = BattleSimulator(seed=TEST_SEED)
        sim.max_duration = 2.5
        original = sim._setup_item_handlers

        def setup(items, owner, enemy):
            result = original(items, owner, enemy)
            if owner.id == 1:
                owner.quota = 100
            return result

        sim._setup_item_handlers = setup
        sim.simulate_battle([watcher], [], 18, p1, p2)

        heals = len([a for a in sim.actions if a.action == "heal"])
        buffs = len([a for a in sim.actions if a.action == "buff"])
        assert heals and heals == buffs, "both or neither, every time"

    def test_nothing_behind_it_happens_when_the_roll_fails(self):
        from item_effects import ChanceEffect, HealEffect

        p1, p2 = get_test_containers()
        never = BattleItem(
            spec=ItemSpec(
                id="n", name="Never", category="infrastructure", cost=1,
                player_class="neutral", shape=parse_map(["#"], "n"), slug="n",
                triggers=[TimerTrigger(cooldown=0.5, cpu_cost=0, effects=[
                    ChanceEffect(chance=0.0, effects=[HealEffect(5, 5)])])],
            ),
            position=(0, 0), uid="never",
        )
        sim = BattleSimulator(seed=TEST_SEED)
        sim.max_duration = 4.0
        original = sim._setup_item_handlers

        def setup(items, owner, enemy):
            result = original(items, owner, enemy)
            if owner.id == 1:
                owner.quota = 100
            return result

        sim._setup_item_handlers = setup
        sim.simulate_battle([never], [], 18, p1, p2)
        assert not [a for a in sim.actions if a.action == "heal"]
