"""
Comprehensive tests for battle engine to ensure it matches Game Design Document
"""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from battle_engine import (
    ITEM_CATALOG,
    Timed,
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
    DEBUFFS,
    MODIFIERS,
    AttackEffect,
    BattleStartTrigger,
    BlockEffect,
    BuffEffect,
    CleanseEffect,
    ConditionEffect,
    CostEffect,
    CpuDrainEffect,
    DebuffEffect,
    GainDamageEffect,
    HealEffect,
    HealthThresholdTrigger,
    ItemSpec,
    LimitEffect,
    ModifyEffect,
    OnAttackedTrigger,
    OnHitTrigger,
    PassiveTrigger,
    PerCountEffect,
    PlayerModifyEffect,
    PreventDamageEffect,
    RandomStatusEffect,
    ReflectEffect,
    ResistEffect,
    StunEffect,
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

    def test_a_quota_never_goes_below_nothing(self):
        """Defeat is checked once a tick, so the last tick can overkill.

        Every blow due in that tenth of a second lands, and each one used to
        take the quota further into the negatives -- where it then decided the
        winner, so two fighters who both ran out in the same tick were settled
        by whose overkill was larger.
        """
        sim = BattleSimulator(seed=TEST_SEED)
        p1_containers, p2_containers = get_test_containers()
        blade = BattleItem(spec=deepcopy(ITEM_CATALOG["null_blade"]), position=(0, 0))
        blade.spec.min_damage = 200
        blade.spec.max_damage = 200

        result = sim.simulate_battle(
            [blade],
            [],
            round_number=1,
            p1_containers=p1_containers,
            p2_containers=p2_containers,
        )

        assert result["player2_quota"] == 0
        for action in result["actions"]:
            assert action.details["hp"][0] >= 0
            assert action.details["hp"][1] >= 0

    def test_every_action_says_where_both_fighters_stand(self):
        """The client draws a health bar and cannot be left to work it out.

        It used to start both fighters on a quota from a table of its own and
        subtract its way down. That table disagreed with this one from round
        two on -- 35 against 70 at round five -- so a battle went on for
        seconds after the screen had counted somebody to nothing.
        """
        sim = BattleSimulator(seed=TEST_SEED)
        p1_containers, p2_containers = get_test_containers()
        blade = BattleItem(spec=deepcopy(ITEM_CATALOG["null_blade"]), position=(0, 0))

        result = sim.simulate_battle(
            [blade],
            [],
            round_number=5,
            p1_containers=p1_containers,
            p2_containers=p2_containers,
        )

        for action in result["actions"]:
            assert action.details["max_hp"] == [70, 70]
        assert result["actions"][0].details["hp"] == [70, 70]
        assert result["actions"][-1].details["hp"][1] < 70

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
        # buffs (Section 3.1), and one gain at the start of battle for each
        # kind of item its star reaches.
        quantum_proc = ITEM_CATALOG["quantum_processor"]
        assert len(quantum_proc.triggers) == 2
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

        # Block is spent inside _take_damage, because it absorbs the damage
        # that is actually arriving.
        sim._take_damage(
            player, 15, source="test_item", action="damage",
            attacker=attacker, blockable=True,
        )
        assert player.block == 0, "all ten of it consumed"
        assert player.quota == 95, "the other five landed"

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
                        effects=[AttackEffect(min_damage=5, max_damage=10, accuracy=0.85, crit_chance=0.0)],
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
                            AttackEffect(min_damage=100, max_damage=100, accuracy=1.0, crit_chance=0.0)
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
        sim.player1, sim.player2 = target, attacker
        sim._take_damage(target, 15, source="sword", action="damage",
                         attacker=attacker, blockable=True)

        assert target.quota == 95, "10 of the 15 absorbed"
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
                   position=(1, 0), uid="boost", counting="any", cap=None):
        from item_effects import ModifyEffect, PassiveTrigger

        return BattleItem(
            spec=ItemSpec(
                id=uid, name="Aura", category="infrastructure", cost=1,
                player_class="neutral", slug=uid,
                shape=parse_map(["*##*"], "aura"),
                triggers=[PassiveTrigger(effects=[
                    ModifyEffect(stat=stat, value=value, target_type=target,
                                 counting=counting, cap=cap)])],
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
                                       target_type="star", counting="any",
                                       cap=None))
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


class _WithOneItem:
    """A battle with one item of the caller's making, and a hook to set
    the player up before it starts."""

    @staticmethod
    def _item(triggers, uid="item", position=(0, 0), category="problem"):
        return BattleItem(
            spec=ItemSpec(
                id=uid, name="Item", category=category, cost=1,
                player_class="neutral", shape=parse_map(["#"], "i"), slug=uid,
                kinds=frozenset({"melee"}), triggers=triggers,
            ),
            position=position, uid=uid,
        )

    def _run(self, items, seconds=6.0, hurt=None, buffs=None, against=()):
        p1, p2 = get_test_containers()
        sim = BattleSimulator(seed=TEST_SEED)
        sim.max_duration = seconds
        original = sim._setup_item_handlers

        def setup(its, owner, enemy):
            if owner.id == 1 and buffs:
                owner.buffs.update(buffs)
            result = original(its, owner, enemy)
            if owner.id == 1 and hurt is not None:
                owner.quota = hurt
            return result

        sim._setup_item_handlers = setup
        result = sim.simulate_battle(items, list(against), 18, p1, p2)
        return sim, result


class TestAfterATime(_WithOneItem):
    """Section 2.1: "After 12s" fires once, a fixed time in. Not a
    cooldown -- a timer trigger puts itself back on the heap and this
    one does not."""

    def test_after_fires_once_at_its_time(self):
        from item_effects import AfterTrigger, HealEffect

        sim, _ = self._run(
            [self._item([AfterTrigger(delay=3.0, effects=[HealEffect(5, 5)])])],
            hurt=100,
        )
        heals = [a for a in sim.actions if a.action == "heal"]
        assert len(heals) == 1, "once, not on a cooldown"
        assert heals[0].timestamp == 3000

    def test_after_does_not_fire_before_its_time(self):
        from item_effects import AfterTrigger, HealEffect

        sim, _ = self._run(
            [self._item([AfterTrigger(delay=5.0, effects=[HealEffect(5, 5)])])],
            seconds=2.0, hurt=100,
        )
        assert not [a for a in sim.actions if a.action == "heal"]


class TestOnAttack(_WithOneItem):
    """Section 1.3: an attack that missed was still an attack. This is
    the whole distinction from on_hit."""

    def test_on_attack_fires_whether_it_hits_or_misses(self):
        """The distinction from on_hit. A miss is still an attack."""
        from item_effects import AttackEffect, HealEffect, OnAttackTrigger

        def heals(accuracy):
            sim, _ = self._run([self._item([
                TimerTrigger(cooldown=1.0, cpu_cost=0, effects=[
                    AttackEffect(min_damage=1, max_damage=1, accuracy=accuracy,
                                 crit_chance=0.0)]),
                OnAttackTrigger(chance=1.0, effects=[HealEffect(1, 1)]),
            ])], hurt=100)
            return len([a for a in sim.actions if a.action == "heal"])

        assert heals(1.0) == heals(0.0) > 0, "a miss counts as an attack"


class TestCountingAStatusHeld(_WithOneItem):
    """Section 3.1: "Triggers 10% faster for each Luck". The counting
    direction of an aura asks the grid; this asks the player."""

    def _counting_item(self):
        from item_effects import ModifyPerStatusEffect, PassiveTrigger

        return self._item([PassiveTrigger(effects=[
            ModifyPerStatusEffect(stat="trigger_speed", value=0.1,
                                  status="calibrated", whose="self")])])

    def test_counting_a_status_changes_the_cooldown(self):
        """Read when the cooldown is worked out, not once at the start, so a
        status gained during the battle counts from then on."""
        sim, result = self._run([self._counting_item()], seconds=0.2)
        (item,) = result["player1_items"]
        owner = Player(id=1, quota=100, max_quota=100, cpu=3.0)
        sim.player1, sim.player2 = owner, Player(id=2, quota=100, max_quota=100, cpu=3.0)
        base = TimerTrigger(cooldown=2.0, cpu_cost=0)

        assert sim._cooldown_for(base, owner, item) == 2.0, "nothing held yet"
        owner.buffs["calibrated"] = 3
        assert sim._cooldown_for(base, owner, item) == pytest.approx(2.0 / 1.3)

    def test_counting_a_status_nobody_holds_changes_nothing(self):
        sim, result = self._run([self._counting_item()], seconds=0.2)
        (item,) = result["player1_items"]
        owner = Player(id=1, quota=100, max_quota=100, cpu=3.0)
        sim.player1, sim.player2 = owner, Player(id=2, quota=100, max_quota=100, cpu=3.0)
        assert sim._cooldown_for(TimerTrigger(cooldown=2.0, cpu_cost=0),
                                 owner, item) == 2.0


class TestEffectDamage(_WithOneItem):
    """Section 2.2: damage that is not an attack. No accuracy roll, no
    shield answers it, and Block does not absorb it."""

    def test_effect_damage_ignores_block(self):
        """No weapon is involved, so Block does not absorb it."""
        from item_effects import EffectDamageEffect

        p1, p2 = get_test_containers()
        sim = BattleSimulator(seed=TEST_SEED)
        sim.max_duration = 2.5
        original = sim._setup_item_handlers

        def setup(its, owner, enemy):
            result = original(its, owner, enemy)
            if owner.id == 2:
                owner.block = 100
            return result

        sim._setup_item_handlers = setup
        sim.simulate_battle([self._item([TimerTrigger(
            cooldown=1.0, cpu_cost=0,
            effects=[EffectDamageEffect(amount=7, lifesteal=0.0, per_status={}, whose={})])])],
            [], 18, p1, p2)

        hits = [a for a in sim.actions if a.action == "damage"]
        assert hits and all(a.damage == 7 for a in hits), "Block does not stop it"

    def test_lifesteal_heals_a_share_of_what_lands(self):
        from item_effects import EffectDamageEffect

        sim, _ = self._run([self._item([TimerTrigger(
            cooldown=1.0, cpu_cost=0,
            effects=[EffectDamageEffect(amount=10, lifesteal=0.5, per_status={}, whose={})])])],
            seconds=1.5, hurt=100)
        healed = [a for a in sim.actions if a.action == "heal"]
        assert healed and healed[0].damage == 5


class TestMaxHealth(_WithOneItem):
    """Section 2.2: raising the ceiling gives you the health with it."""

    def test_max_health_raises_the_ceiling_and_fills_it(self):
        from item_effects import BattleStartTrigger, MaxHealthEffect

        sim, result = self._run(
            [self._item([BattleStartTrigger(effects=[MaxHealthEffect(20)])])],
            seconds=0.2,
        )
        assert result["player1_quota"] == 370, "350 for round 18, plus 20"


class TestAnAuraNarrowsWhatItFallsOn(_WithOneItem):
    """Section 3.1: "Star Weapons deal +2 damage" is the star zone, narrowed.

    The source game writes the singular -- "The Star Weapon gains 10 damage" --
    when an item draws a one-square star, where the only weapon that can stand
    there is the one. It is the zone that is small, not the rule.
    """

    @staticmethod
    def _projector(counting, stat="damage", value=1.0):
        """An aura reaching the square to its right."""
        return BattleItem(
            spec=ItemSpec(
                id="aura", name="Aura", category="infrastructure", cost=1,
                player_class="neutral", slug="aura",
                shape=parse_map(["#*"], "aura"),
                triggers=[PassiveTrigger(effects=[ModifyEffect(
                    stat=stat, value=value, target_type="star",
                    counting=counting, cap=None)])],
            ),
            position=(0, 0), uid="aura",
        )

    @staticmethod
    def _swinger(kinds, uid="target"):
        return BattleItem(
            spec=ItemSpec(
                id=uid, name="Swinger", category="problem", cost=1,
                player_class="neutral", shape=parse_map(["#"], "s"), slug=uid,
                kinds=frozenset(kinds),
                triggers=[TimerTrigger(cooldown=1.0, cpu_cost=0, effects=[
                    AttackEffect(min_damage=10, max_damage=10, accuracy=1.0,
                                 crit_chance=0.0)])],
            ),
            position=(1, 0), uid=uid,
        )

    def _damage_dealt(self, counting, kinds):
        _, result = self._run(
            [self._projector(counting), self._swinger(kinds)], seconds=1.5
        )
        return 350 - result["player2_quota"]

    def test_an_item_the_filter_names_is_reached(self):
        assert self._damage_dealt({"any": ["melee"]}, ["melee"]) == 20, (
            "10 doubled by a +100% damage aura"
        )

    def test_an_item_the_filter_leaves_out_is_not(self):
        """The same zone, the same item standing in it, and no change."""
        assert self._damage_dealt({"any": ["melee"]}, ["ranged"]) == 10

    def test_a_filter_of_any_reaches_everything(self):
        assert self._damage_dealt("any", ["ranged"]) == 20

    def test_all_wants_every_tag_at_once(self):
        """`{"all": [...]}` is not `{"any": [...]}`: one tag is not enough."""
        assert self._damage_dealt({"all": ["melee", "holy"]}, ["melee"]) == 10
        assert self._damage_dealt(
            {"all": ["melee", "holy"]}, ["melee", "holy"]
        ) == 20

    def test_the_category_counts_as_a_tag(self):
        """"Star Food" names a category, "Star Weapons" a kind. Both read the
        same way."""
        assert self._damage_dealt({"any": ["problem"]}, ["ranged"]) == 20


class TestAModifierHandedOutAsItGoes(_WithOneItem):
    """A modifier under a timer or an on-hit is not an aura.

    "On hit: 25% chance to gain 1 damage" used to be settled by the aura pass
    -- once, in full, at the start of the battle, whether or not the item ever
    hit anything. A standing trigger is settled beforehand; everything else is
    applied where it happens.
    """

    @staticmethod
    def _granter(cooldown=1.0, cap=None, value=1.0):
        """Every `cooldown` seconds, the item to its right hits harder."""
        return BattleItem(
            spec=ItemSpec(
                id="granter", name="Granter", category="infrastructure", cost=1,
                player_class="neutral", slug="granter",
                shape=parse_map(["#*"], "granter"),
                triggers=[TimerTrigger(cooldown=cooldown, cpu_cost=0, effects=[
                    ModifyEffect(stat="damage", value=value,
                                 target_type="star", counting="any",
                                 cap=cap)])],
            ),
            position=(0, 0), uid="granter",
        )

    @staticmethod
    def _swinger():
        return BattleItem(
            spec=ItemSpec(
                id="swinger", name="Swinger", category="problem", cost=1,
                player_class="neutral", shape=parse_map(["#"], "s"),
                slug="swinger", kinds=frozenset({"melee"}),
                triggers=[TimerTrigger(cooldown=10.0, cpu_cost=0, effects=[
                    AttackEffect(min_damage=10, max_damage=10, accuracy=1.0,
                                 crit_chance=0.0)])],
            ),
            position=(1, 0), uid="swinger",
        )

    def _mult(self, granter, seconds=5.5):
        sim, result = self._run([granter, self._swinger()], seconds=seconds)
        swinger = next(i for i in sim.loadout[1] if i.uid == "swinger")
        return swinger.damage_mult, 350 - result["player2_quota"]

    def test_a_live_modifier_is_not_given_away_at_the_start(self):
        """Nothing has been handed out before the granter has ever fired."""
        mult, _ = self._mult(self._granter(cooldown=20.0))
        assert mult == 1.0

    def test_a_live_modifier_lands_once_it_is_handed_out(self):
        """Five grants of +100% by 5.5s."""
        mult, _ = self._mult(self._granter(cooldown=1.0))
        assert mult == 6.0

    def test_the_swing_carries_what_was_handed_out_before_it(self):
        """Nine grants of +100% had landed when the one swing came."""
        _, dealt = self._mult(self._granter(cooldown=1.0), seconds=10.5)
        assert dealt == 100

    def test_a_cap_stops_it_growing(self):
        """"up to 50%" is a limit on what one item has given another, so the
        sixth grant of +100% under a cap of +300% hands out nothing."""
        mult, _ = self._mult(self._granter(cooldown=1.0, cap=3.0))
        assert mult == 4.0

    def test_a_cap_hands_out_the_part_that_still_fits(self):
        """A grant that would overshoot is trimmed rather than refused."""
        mult, _ = self._mult(self._granter(cooldown=1.0, value=2.0, cap=3.0))
        assert mult == 4.0, "2.0, then the 1.0 that was left"

    def test_a_standing_modifier_is_still_settled_once(self):
        """A passive comes through _apply_effects as its handler goes on, and
        must not be applied a second time there."""
        aura = BattleItem(
            spec=ItemSpec(
                id="aura", name="Aura", category="infrastructure", cost=1,
                player_class="neutral", slug="aura",
                shape=parse_map(["#*"], "aura"),
                triggers=[PassiveTrigger(effects=[ModifyEffect(
                    stat="damage", value=1.0, target_type="star",
                    counting="any", cap=None)])],
            ),
            position=(0, 0), uid="aura",
        )
        mult, _ = self._mult(aura)
        assert mult == 2.0, "doubled once, not twice"


class TestDamageAnItemPicksUp(_WithOneItem):
    """"Gain 1 damage" adds to what a weapon swings and it keeps it.

    Flat, not a multiplier, which is why it is not a `modify`. It is kept
    apart from the item's own range because the source game reads it back --
    "remove 1 damage gained in battle from all opponent Weapons".
    """

    @staticmethod
    def _swinger(target="self", amount=5, uid="swinger", position=(0, 0)):
        return BattleItem(
            spec=ItemSpec(
                id=uid, name="Swinger", category="problem", cost=1,
                player_class="neutral", shape=parse_map(["#"], "s"), slug=uid,
                kinds=frozenset({"melee"}),
                triggers=[
                    TimerTrigger(cooldown=1.0, cpu_cost=0, effects=[
                        AttackEffect(min_damage=10, max_damage=10,
                                     accuracy=1.0, crit_chance=0.0)]),
                    OnHitTrigger(chance=1.0, effects=[GainDamageEffect(
                        amount=amount, target_type=target, counting="any")]),
                ],
            ),
            position=position, uid=uid,
        )

    def test_the_gain_is_kept_for_the_rest_of_the_battle(self):
        """10, then 15, then 20: each swing carries every gain before it."""
        _, result = self._run([self._swinger()], seconds=3.5)
        assert 350 - result["player2_quota"] == 45

    def test_it_adds_to_the_roll_rather_than_the_total(self):
        """A modifier takes the gain with it, because the gain is part of what
        the weapon swings."""
        aura = BattleItem(
            spec=ItemSpec(
                id="aura", name="Aura", category="infrastructure", cost=1,
                player_class="neutral", slug="aura",
                shape=parse_map(["#*"], "aura"),
                triggers=[PassiveTrigger(effects=[ModifyEffect(
                    stat="damage", value=1.0, target_type="star",
                    counting="any", cap=None)])],
            ),
            position=(0, 0), uid="aura",
        )
        _, result = self._run(
            [aura, self._swinger(position=(1, 0))], seconds=2.5
        )
        assert 350 - result["player2_quota"] == 50, "(10)x2 then (10+5)x2"

    def test_self_means_the_item_saying_it(self):
        """"Gain 1 damage" is the item talking about itself, so a second item
        beside it gains nothing."""
        sim, _ = self._run(
            [self._swinger(uid="a"), self._swinger(
                uid="b", position=(1, 0), amount=0)],
            seconds=1.5,
        )
        gained = {i.uid: i.damage_gained for i in sim.loadout[1]}
        assert gained == {"a": 5, "b": 0}


class TestOnceForEachThatCounts(_WithOneItem):
    """"Heal 4 per Star Vampiric-item" does the effects again, once each.

    Counting nothing does nothing, which is what multiplying by zero means and
    needs no case of its own.
    """

    @staticmethod
    def _counter(counting="any", where="star"):
        """Heals 4 for each item standing to its right or below."""
        return BattleItem(
            spec=ItemSpec(
                id="counter", name="Counter", category="infrastructure",
                cost=1, player_class="neutral", slug="counter",
                shape=parse_map(["#*", "*."], "counter"),
                triggers=[BattleStartTrigger(effects=[PerCountEffect(
                    where=where, counting=counting,
                    effects=[HealEffect(min_heal=4, max_heal=4)])])],
            ),
            position=(0, 0), uid="counter",
        )

    @staticmethod
    def _standing(uid, position, kinds=("melee",), category="problem"):
        return BattleItem(
            spec=ItemSpec(
                id=uid, name="Standing", category=category, cost=1,
                player_class="neutral", shape=parse_map(["#"], "s"), slug=uid,
                kinds=frozenset(kinds), triggers=[],
            ),
            position=position, uid=uid,
        )

    def _healed(self, items, hurt=100):
        _, result = self._run(items, seconds=0.3, hurt=hurt)
        return result["player1_quota"] - hurt

    def test_it_happens_once_for_each_item_that_counts(self):
        assert self._healed([
            self._counter(),
            self._standing("a", (1, 0)),
            self._standing("b", (0, 1)),
        ]) == 8

    def test_counting_nothing_does_nothing(self):
        assert self._healed([self._counter()]) == 0

    def test_the_filter_narrows_what_counts(self):
        assert self._healed([
            self._counter({"any": ["ranged"]}),
            self._standing("a", (1, 0), kinds=("melee",)),
            self._standing("b", (0, 1), kinds=("ranged",)),
        ]) == 4

    def test_it_counts_where_it_is_told_to(self):
        """`own` is the whole loadout, not a zone, so the counter counts
        itself as well."""
        assert self._healed([
            self._counter(where="own"),
            self._standing("a", (1, 0)),
        ]) == 8


class TestSpendingAStatus(_WithOneItem):
    """"Use 3 Mana to deal +7 damage": all of it or none of it.

    Nothing is spent when the price cannot be met in full, so a clause cannot
    leave its owner poorer for nothing.
    """

    @staticmethod
    def _spender(costs, gain=20):
        return BattleItem(
            spec=ItemSpec(
                id="spender", name="Spender", category="problem", cost=1,
                player_class="neutral", shape=parse_map(["#"], "s"),
                slug="spender", kinds=frozenset({"melee"}),
                triggers=[BattleStartTrigger(effects=[CostEffect(
                    costs=costs,
                    effects=[BlockEffect(block_amount=gain)])])],
            ),
            position=(0, 0), uid="spender",
        )

    def _after(self, costs, buffs):
        sim, _ = self._run([self._spender(costs)], seconds=0.3, buffs=buffs)
        return dict(sim.player1.buffs), sim.player1.block

    def test_it_pays_and_the_clause_happens(self):
        buffs, block = self._after({"credits": 3}, {"credits": 5})
        assert buffs == {"credits": 2}
        assert block == 20

    def test_it_pays_nothing_when_it_cannot_pay_in_full(self):
        buffs, block = self._after({"credits": 3}, {"credits": 2})
        assert buffs == {"credits": 2}, "the two it had are still there"
        assert block == 0

    def test_a_price_of_several_is_paid_together(self):
        buffs, block = self._after(
            {"credits": 1, "calibrated": 1}, {"credits": 2, "calibrated": 1}
        )
        assert buffs == {"credits": 1}, "calibrated is spent to nothing"
        assert block == 20

    def test_one_half_of_a_price_it_cannot_meet_is_not_spent(self):
        buffs, block = self._after(
            {"credits": 1, "calibrated": 5}, {"credits": 2, "calibrated": 1}
        )
        assert buffs == {"credits": 2, "calibrated": 1}
        assert block == 0


class TestAConditionOnAClause(_WithOneItem):
    """"If your health is above 70%, gain 1 Empower. Otherwise, heal for 8."

    One effect holds the whole sentence, so the two halves cannot both happen.
    A condition reads a state and spends nothing, which is what tells it from
    a cost.
    """

    @staticmethod
    def _asker(**kwargs):
        settings = dict(
            subject="health", whose="self", status="", test="above",
            amount=0.7,
            effects=[BlockEffect(block_amount=20)],
            otherwise=[HealEffect(min_heal=8, max_heal=8)],
        )
        settings.update(kwargs)
        return BattleItem(
            spec=ItemSpec(
                id="asker", name="Asker", category="problem", cost=1,
                player_class="neutral", shape=parse_map(["#"], "a"),
                slug="asker", kinds=frozenset({"melee"}),
                triggers=[BattleStartTrigger(effects=[
                    ConditionEffect(**settings)])],
            ),
            position=(0, 0), uid="asker",
        )

    def _run_asker(self, hurt=350, buffs=None, **kwargs):
        sim, result = self._run(
            [self._asker(**kwargs)], seconds=0.3, hurt=hurt, buffs=buffs
        )
        return sim.player1.block, result["player1_quota"] - hurt

    def test_the_first_half_happens_when_it_holds(self):
        block, healed = self._run_asker(hurt=350)
        assert (block, healed) == (20, 0)

    def test_the_other_half_happens_when_it_does_not(self):
        block, healed = self._run_asker(hurt=100)
        assert (block, healed) == (0, 8)

    def test_a_condition_on_a_status_counts_stacks(self):
        block, _ = self._run_asker(
            subject="status", status="credits", test="at_least", amount=3,
            buffs={"credits": 3},
        )
        assert block == 20

    def test_a_condition_spends_nothing(self):
        """This is what tells a condition from a cost."""
        sim, _ = self._run(
            [self._asker(subject="status", status="credits",
                         test="at_least", amount=3)],
            seconds=0.3, buffs={"credits": 5},
        )
        assert sim.player1.buffs == {"credits": 5}

    def test_none_asks_whether_there_are_any(self):
        """"If you have no debuffs, gain 25 Block.\""""
        block, _ = self._run_asker(
            subject="status", status="throttled", test="none",
        )
        assert block == 20


class TestStunning(_WithOneItem):
    """Backpack Battles' Stun page: "Stun pauses all cooldowns for a certain
    amount of time." Nothing is lost and nothing is reset.
    """

    @staticmethod
    def _swinger(uid="swinger", position=(0, 0), owner_stun=None):
        triggers = [TimerTrigger(cooldown=1.0, cpu_cost=0, effects=[
            AttackEffect(min_damage=10, max_damage=10, accuracy=1.0,
                         crit_chance=0.0)])]
        return BattleItem(
            spec=ItemSpec(
                id=uid, name="Swinger", category="problem", cost=1,
                player_class="neutral", shape=parse_map(["#"], "s"), slug=uid,
                kinds=frozenset({"melee"}), triggers=triggers,
            ),
            position=position, uid=uid,
        )

    @staticmethod
    def _stunner(duration, at=0.5, uid="stunner", position=(1, 0),
                 target="self"):
        from item_effects import AfterTrigger

        return BattleItem(
            spec=ItemSpec(
                id=uid, name="Stunner", category="problem", cost=1,
                player_class="neutral", shape=parse_map(["#"], "s"), slug=uid,
                kinds=frozenset({"melee"}),
                triggers=[AfterTrigger(delay=at, effects=[
                    StunEffect(duration=duration, target_type=target)])],
            ),
            position=position, uid=uid,
        )

    def test_a_stun_holds_a_wait_still(self):
        """Five swings in 5.5s, and a 2s stun leaves three."""
        _, plain = self._run([self._swinger()], seconds=5.5)
        _, stunned = self._run(
            [self._swinger(), self._stunner(2.0)], seconds=5.5
        )
        assert 350 - plain["player2_quota"] == 50
        assert 350 - stunned["player2_quota"] == 30

    def test_the_wait_is_taken_up_where_it_stopped(self):
        """The stun lands at 0.5s, half way through the first wait, and holds
        until 2.5s. The swing comes at 3.0s: the half second still owed is
        still owed, so nothing is lost and nothing is reset.
        """
        sim, _ = self._run(
            [self._swinger(), self._stunner(2.0)], seconds=4.0
        )
        swings = [a.timestamp for a in sim.actions if a.action == "damage"]
        assert swings == [3000], swings

    def test_a_stun_holds_the_stunning_item_too(self):
        """"Stun pauses all cooldowns" is all of them. An item that stuns its
        own side waits along with everything else, which is why two stunners
        set to fire at different times cannot overlap: the first pushes the
        second out past its own end.
        """
        sim, _ = self._run(
            [self._swinger(), self._stunner(2.0),
             self._stunner(1.0, at=0.6, uid="second", position=(2, 0))],
            seconds=5.5,
        )
        assert sim.stunned_until == {1: pytest.approx(3.6)}, (
            "the second fires at 2.6s, not 0.6s"
        )

    def _both_stunning(self, second_duration):
        """Two stunners of player 1's, both firing at 0.5s, against a swinger
        of player 2's. Neither stunner is held, because a stun holds the waits
        of the player it lands on and these land on the other one.
        """
        sim, result = self._run(
            [self._stunner(2.0, position=(0, 0), target="enemy"),
             self._stunner(second_duration, at=0.5, uid="second",
                           position=(1, 0), target="enemy")],
            seconds=5.5,
            against=[self._swinger(position=(4, 0))],
        )
        return sim, result

    def test_two_stuns_at_once_do_not_add(self):
        """The Stun page: they "exist concurrently and as separate debuffs
        based on when they were applied and when they individually expire", so
        one landing inside a longer one is worth nothing at all."""
        sim, _ = self._both_stunning(1.0)
        assert sim.stunned_until == {2: 2.5}, "the shorter one adds nothing"

    def test_a_later_stun_reaching_further_pushes_the_rest(self):
        """Two seconds and three seconds, both from 0.5s: the longer is worth
        the second it adds beyond the shorter, and no more."""
        sim, _ = self._both_stunning(3.0)
        assert sim.stunned_until == {2: 3.5}

    def test_a_stun_reaches_only_the_player_it_lands_on(self):
        """The other player's waits are not on hold."""
        sim, _ = self._run(
            [self._swinger(), self._stunner(2.0)], seconds=3.0
        )
        assert sim.stunned_until == {1: 2.5}


class TestWhatTheCatalogueNowDoes(_WithOneItem):
    """The items these mechanics were built for, run as they stand.

    Everything above tests a mechanic on an item made for the purpose. These
    take the catalogue's own items and check each one does what the source
    game's wording says, which is the only thing that says the translation
    was right.
    """

    @staticmethod
    def _real(item_id, position=(0, 0), uid=None):
        return BattleItem(
            spec=ITEM_CATALOG[item_id], position=position, uid=uid or item_id
        )

    @staticmethod
    def _star_squares(item_id, how_many):
        """Squares of an item's star that a 3x3 rack at the origin can hold.

        A star is drawn around the item on its own map, so half of it reaches
        off the left and top edges. Those are real squares in a real rack and
        nowhere in the one these tests use.
        """
        spec = ITEM_CATALOG[item_id]
        covered = set(spec.shape.squares)
        free = [
            (x, y) for x, y in spec.shape.star
            if 0 <= x <= 2 and 0 <= y <= 2 and (x, y) not in covered
        ]
        assert len(free) >= how_many, f"{item_id}: only {len(free)} in the rack"
        return free[:how_many]

    @staticmethod
    def _holy(uid, position):
        """Something for a Star Holy-item aura to land on."""
        return BattleItem(
            spec=ItemSpec(
                id=uid, name="Holy", category="protocol", cost=1,
                player_class="neutral", shape=parse_map(["#"], "h"), slug=uid,
                kinds=frozenset({"holy"}), triggers=[],
            ),
            position=position, uid=uid,
        )

    def test_holy_armor_gains_regeneration_for_each_star_holy_item(self):
        """"Gain 65 Block. Gain 2 Regeneration for each Star Holy-item.\""""
        one, two, three = self._star_squares("sanctified_firewall", 3)
        plain = BattleItem(
            spec=ItemSpec(
                id="p", name="Plain", category="problem", cost=1,
                player_class="neutral", shape=parse_map(["#"], "p"), slug="p",
                kinds=frozenset({"melee"}), triggers=[]),
            position=three, uid="p",
        )
        sim, _ = self._run(
            [self._real("sanctified_firewall"),
             self._holy("h1", one), self._holy("h2", two), plain],
            seconds=0.2,
        )
        assert sim.player1.block == 65
        assert sim.player1.buffs["regenerating"] == 4, (
            "2 for each of the two Holy items, and nothing for the third"
        )

    def test_gold_armor_pays_only_when_it_cleansed_everything(self):
        """"Cleanse 5 debuffs. If you have no debuffs, gain 25 Block.\""""
        sim, _ = self._run([self._real("gold_armor")], seconds=2.4,
                           buffs=None)
        assert sim.player1.block == 145, "120 at the start, then 25 with no debuffs"

    def test_gold_armor_holds_the_block_back_while_a_debuff_is_left(self):
        sim = BattleSimulator(seed=TEST_SEED)
        sim.max_duration = 2.4
        p1, p2 = get_test_containers()
        original = sim._setup_item_handlers

        def setup(items, owner, enemy):
            result = original(items, owner, enemy)
            if owner.id == 1:
                owner.debuffs["memory_leaked"] = 9
            return result

        sim._setup_item_handlers = setup
        sim.simulate_battle([self._real("gold_armor")], [], 18, p1, p2)
        assert sim.player1.debuffs["memory_leaked"] == 4, "five cleansed"
        assert sim.player1.block == 120, "one clause, and its condition failed"

    def test_hero_shield_gives_its_star_weapon_both_kinds_of_bonus(self):
        """"Star weapons deal +2 + 15% damage." A flat gain and a modifier."""
        (where,) = self._star_squares("rate_limiter", 1)
        weapon = BattleItem(
            spec=ItemSpec(
                id="w", name="Weapon", category="problem", cost=1,
                player_class="neutral", shape=parse_map(["#"], "w"), slug="w",
                kinds=frozenset({"melee"}), triggers=[]),
            position=where, uid="w",
        )
        sim, _ = self._run(
            [self._real("rate_limiter"), weapon], seconds=0.2
        )
        got = next(i for i in sim.loadout[1] if i.uid == "w")
        assert got.damage_gained == 2
        assert got.damage_mult == pytest.approx(1.15)

    def test_gloves_of_power_trade_speed_for_damage(self):
        """"Star Weapons deal +20% damage but attack 10% slower.\""""
        (where,) = self._star_squares("gloves_of_power", 1)
        weapon = BattleItem(
            spec=ItemSpec(
                id="w", name="Weapon", category="problem", cost=1,
                player_class="neutral", shape=parse_map(["#"], "w"), slug="w",
                kinds=frozenset({"ranged"}), triggers=[]),
            position=where, uid="w",
        )
        sim, _ = self._run(
            [self._real("gloves_of_power"), weapon], seconds=0.2
        )
        got = next(i for i in sim.loadout[1] if i.uid == "w")
        assert got.damage_mult == pytest.approx(1.2)
        assert got.speed_mult == pytest.approx(0.9)

    def test_bloodthorne_buys_its_buffs_with_regeneration(self):
        """"On hit: Use 1 Regeneration to gain 1 Vampirism and 1 Spikes.\""""
        sim, _ = self._run(
            [self._real("bloodthorne")], seconds=2.0,
            buffs={"regenerating": 1},
        )
        assert sim.player1.buffs.get("draining") == 1
        assert sim.player1.buffs.get("spiked") == 1
        assert "regenerating" not in sim.player1.buffs, "spent"

    def test_bloodthorne_gains_nothing_it_cannot_pay_for(self):
        sim, _ = self._run([self._real("bloodthorne")], seconds=2.0)
        assert "draining" not in sim.player1.buffs
        assert "spiked" not in sim.player1.buffs

    def test_carrot_needs_its_four_luck(self):
        """"If you have at least 4 Luck: 55% chance to gain 1 Empower.\""""
        without, _ = self._run([self._real("auto_rollback")], seconds=6.0)
        with_luck, _ = self._run(
            [self._real("auto_rollback")], seconds=6.0,
            buffs={"calibrated": 4},
        )
        assert "monitored" not in without.player1.buffs
        assert with_luck.player1.buffs.get("monitored", 0) > 0
        assert with_luck.player1.buffs["calibrated"] == 4, "a condition spends nothing"

    def test_vampiric_gloves_wait_four_seconds(self):
        """"After 4s: Gain 5 Vampirism, Star items trigger 35% faster.\""""
        early, _ = self._run([self._real("vampiric_gloves")], seconds=3.5)
        late, _ = self._run([self._real("vampiric_gloves")], seconds=4.5)
        assert "draining" not in early.player1.buffs
        assert late.player1.buffs["draining"] == 5

    def test_jynx_torquilla_stops_at_fifty_percent(self):
        """"Star items trigger 5% faster (up to 50%)." Ten grants, and the
        eleventh hands out nothing."""
        (where,) = self._star_squares("jynx_torquilla", 1)
        standing = BattleItem(
            spec=ItemSpec(
                id="s", name="Standing", category="problem", cost=1,
                player_class="neutral", shape=parse_map(["#"], "s"), slug="s",
                kinds=frozenset({"melee"}), triggers=[]),
            position=where, uid="s",
        )
        sim, _ = self._run(
            [self._real("jynx_torquilla"), standing], seconds=40.0
        )
        got = next(i for i in sim.loadout[1] if i.uid == "s")
        assert got.speed_mult == pytest.approx(1.5)

    def test_snowmaster_swaps_the_cold_for_empower_at_ten(self):
        """"Inflict 1 Cold. If your opponent has at least 10 Cold, gain 1
        Empower instead." Instead, so never both."""
        sim, _ = self._run([self._real("snowmaster")], seconds=20.0)
        assert sim.player2.debuffs["throttled"] == 10, "it stopped at ten"
        assert sim.player1.buffs["monitored"] > 0, "and turned to Empower"

    def test_sloth_wakes_up_at_twenty_five_seconds(self):
        """"Gain 10 of each buff and stun the opponent for 1.5s.\""""
        before, _ = self._run([self._real("sloth")], seconds=24.0)
        after, _ = self._run([self._real("sloth")], seconds=26.0)
        assert before.player1.buffs == {}
        assert after.player1.buffs == {name: 10 for name in BUFFS}
        assert after.stunned_until == {2: pytest.approx(26.5)}


class TestSomethingThatRunsOut(_WithOneItem):
    """Section 3.1: a buff, a debuff or a modifier can carry a clock.

    "Inflict 5 Blind for 2s", "Gain 2 Empower for 8s", "-25% damage for 7s".
    Nearly everything in the source game lasts the battle and writes -1; the
    few that run out say a number.
    """

    def _at(self, effect, seconds):
        sim, _ = self._run(
            [self._item([BattleStartTrigger(effects=[effect])])], seconds=seconds
        )
        return sim

    def test_stacks_are_handed_back_when_the_time_comes(self):
        early = self._at(BuffEffect("monitored", 5, "self", duration=2.0), 1.5)
        late = self._at(BuffEffect("monitored", 5, "self", duration=2.0), 2.5)
        assert early.player1.buffs["monitored"] == 5
        assert "monitored" not in late.player1.buffs

    def test_stacks_with_no_clock_stay(self):
        assert self._at(BuffEffect("monitored", 5, "self"), 9.0) \
            .player1.buffs["monitored"] == 5

    def test_only_what_it_granted_is_taken_back(self):
        """Two grants, one of them timed, and the untimed stacks stay."""
        sim, _ = self._run(
            [self._item([BattleStartTrigger(effects=[
                BuffEffect("monitored", 3, "self"),
                BuffEffect("monitored", 5, "self", duration=2.0),
            ])])],
            seconds=2.5,
        )
        assert sim.player1.buffs["monitored"] == 3

    def test_it_cannot_take_back_what_a_cleanse_already_took(self):
        """Floored at nothing, so an expiry cannot push a count negative."""
        sim, _ = self._run(
            [self._item([
                BattleStartTrigger(effects=[
                    BuffEffect("monitored", 5, "self", duration=2.0)]),
                TimerTrigger(cooldown=1.0, cpu_cost=0, effects=[
                    CleanseEffect(count=4, removes="monitored",
                                  target_type="self")]),
            ])],
            seconds=2.5,
        )
        assert sim.player1.buffs.get("monitored", 0) == 0

    def test_a_debuff_can_run_out_too(self):
        sim = self._at(
            DebuffEffect("rate_limited", 5, duration=2.0, target_type="enemy"),
            2.5,
        )
        assert "rate_limited" not in sim.player2.debuffs


class TestAModifierOnThePlayer(_WithOneItem):
    """Some clauses change a number nobody's item carries.

    "Your healing is amplified by 12%", "Both players take -25% damage for
    7s", "Items use +20% stamina". None sits on an item and none stacks as a
    buff does, so it is neither a modify nor a buff.
    """

    def _with(self, *effects, seconds=3.0, hurt=None, extra=()):
        return self._run(
            [self._item([BattleStartTrigger(effects=list(effects))])] + list(extra),
            seconds=seconds, hurt=hurt,
        )

    def test_damage_taken_is_a_share_of_what_lands(self):
        swing = self._item([TimerTrigger(cooldown=1.0, cpu_cost=0, effects=[
            AttackEffect(min_damage=10, max_damage=10, accuracy=1.0,
                         crit_chance=0.0)])], uid="w", position=(1, 0))
        _, plain = self._with(seconds=1.5, extra=[swing])
        _, halved = self._with(
            PlayerModifyEffect("damage_taken", -0.5, "enemy", -1),
            seconds=1.5, extra=[swing],
        )
        assert 350 - plain["player2_quota"] == 10
        assert 350 - halved["player2_quota"] == 5

    def test_invulnerability_is_the_same_number_turned_up(self):
        """The wiki: invulnerability "prevents receiving any damage". That is
        a share of -1.0, not a case of its own."""
        swing = self._item([TimerTrigger(cooldown=1.0, cpu_cost=0, effects=[
            AttackEffect(min_damage=10, max_damage=10, accuracy=1.0,
                         crit_chance=0.0)])], uid="w", position=(1, 0))
        _, result = self._with(
            PlayerModifyEffect("damage_taken", -1.0, "enemy", -1),
            seconds=3.5, extra=[swing],
        )
        assert result["player2_quota"] == 350

    def test_invulnerability_stops_poison_as_well(self):
        """"Any damage" is every kind. Poison reaches no shield and this."""
        sim, result = self._with(
            PlayerModifyEffect("damage_taken", -1.0, "self", -1),
            DebuffEffect("memory_leaked", 5, target_type="self"),
            seconds=5.0, hurt=200,
        )
        assert result["player1_quota"] == 200

    def test_a_modifier_can_run_out(self):
        swing = self._item([TimerTrigger(cooldown=3.0, cpu_cost=0, effects=[
            AttackEffect(min_damage=10, max_damage=10, accuracy=1.0,
                         crit_chance=0.0)])], uid="w", position=(1, 0))
        _, result = self._with(
            PlayerModifyEffect("damage_taken", -1.0, "enemy", 2.0),
            seconds=3.5, extra=[swing],
        )
        assert 350 - result["player2_quota"] == 10, "the swing came after it ended"

    def test_healing_belongs_to_whoever_does_it(self):
        _, plain = self._with(HealEffect(min_heal=10, max_heal=10),
                              seconds=0.3, hurt=100)
        _, more = self._with(PlayerModifyEffect("healing", 0.5, "self", -1),
                             HealEffect(min_heal=10, max_heal=10),
                             seconds=0.3, hurt=100)
        assert plain["player1_quota"] - 100 == 10
        assert more["player1_quota"] - 100 == 15

    def test_healing_taken_is_put_on_the_one_being_healed(self):
        """"Your opponent's healing is reduced by 30%" is not their clause."""
        _, result = self._with(
            PlayerModifyEffect("healing_taken", -0.3, "self", -1),
            HealEffect(min_heal=10, max_heal=10),
            seconds=0.3, hurt=100,
        )
        assert result["player1_quota"] - 100 == 7

    def test_block_gained_is_a_share(self):
        sim, _ = self._with(
            PlayerModifyEffect("block_gained", 0.3, "self", -1),
            BlockEffect(block_amount=100),
            seconds=0.3,
        )
        assert sim.player1.block == 130

    def test_stamina_use_changes_what_an_item_costs(self):
        """"Items use +20% stamina", so a pool that ran three activations
        runs fewer."""
        hungry = self._item([TimerTrigger(cooldown=1.0, cpu_cost=1.0, effects=[
            AttackEffect(min_damage=1, max_damage=1, accuracy=1.0,
                         crit_chance=0.0)])], uid="w", position=(1, 0))
        _, plain = self._with(seconds=5.5, extra=[hungry])
        _, costly = self._with(
            PlayerModifyEffect("stamina_use", 1.0, "self", -1),
            seconds=5.5, extra=[hungry],
        )
        assert 350 - costly["player2_quota"] < 350 - plain["player2_quota"]

    def test_both_reaches_both_players(self):
        """"Both players take -25% damage for 7s\""""
        sim, _ = self._with(
            PlayerModifyEffect("damage_taken", -0.25, "both", 7.0), seconds=0.3
        )
        assert sim.player1.modifier("damage_taken", 0.2) == -0.25
        assert sim.player2.modifier("damage_taken", 0.2) == -0.25


class TestTurningADebuffBack(_WithOneItem):
    """Backpack Battles' Reflect page: "Reflect 2 means that you will cleanse
    the next 2 stacks of debuffs applied to you, and inflict them upon the
    opponent instead."
    """

    def _fight(self, *mine, stacks=3, seconds=1.5):
        """Player 2 inflicts; player 1 holds whatever is being tested."""
        return self._run(
            [self._item([BattleStartTrigger(effects=list(mine))])],
            seconds=seconds,
            against=[self._item([TimerTrigger(cooldown=1.0, cpu_cost=0, effects=[
                DebuffEffect("memory_leaked", stacks, target_type="enemy")])],
                uid="them", position=(4, 0))],
        )

    def test_a_charge_sends_one_stack_the_other_way(self):
        sim, _ = self._fight(ReflectEffect(count=1, target_type="self"))
        assert sim.player1.debuffs["memory_leaked"] == 2, "three came, one went back"
        assert sim.player2.debuffs["memory_leaked"] == 1

    def test_one_stack_per_charge_however_many_arrive(self):
        """The page: "Regardless of how many stacks of a debuff is inflicted
        to the player who has Reflect, only 1 stack will be reflected per
        reflect.\""""
        sim, _ = self._fight(ReflectEffect(count=2, target_type="self"), stacks=5)
        assert sim.player1.debuffs["memory_leaked"] == 3
        assert sim.player2.debuffs["memory_leaked"] == 2

    def test_charges_run_out(self):
        sim, _ = self._fight(ReflectEffect(count=1, target_type="self"), seconds=2.5)
        assert sim.player1.debuffs["memory_leaked"] == 5, "3 + 3, one reflected"
        assert sim.player2.debuffs["memory_leaked"] == 1
        assert sim.player1.reflect == 0

    def test_nothing_reflects_without_a_charge(self):
        sim, _ = self._fight()
        assert sim.player1.debuffs["memory_leaked"] == 3
        assert "memory_leaked" not in sim.player2.debuffs


class TestRefusingADebuff(_WithOneItem):
    """Backpack Battles' Resist page: "Resist prevents a debuff to be
    inflicted." A chance is checked before a charge is spent, and Reflect goes
    before both.
    """

    def _fight(self, *mine, stacks=3):
        return self._run(
            [self._item([BattleStartTrigger(effects=list(mine))])],
            seconds=1.5,
            against=[self._item([TimerTrigger(cooldown=1.0, cpu_cost=0, effects=[
                DebuffEffect("memory_leaked", stacks, target_type="enemy")])],
                uid="them", position=(4, 0))],
        )

    def test_a_charge_refuses_one_stack(self):
        sim, _ = self._fight(ResistEffect(count=1, chance=0.0, target_type="self"))
        assert sim.player1.debuffs["memory_leaked"] == 2
        assert "memory_leaked" not in sim.player2.debuffs, "refused, not returned"

    def test_a_certain_chance_refuses_everything(self):
        sim, _ = self._fight(ResistEffect(count=0, chance=1.0, target_type="self"))
        assert "memory_leaked" not in sim.player1.debuffs

    def test_a_chance_is_checked_before_a_charge_is_spent(self):
        """The page: "All percent chance methods are added together"... and
        the stacks are the backup."""
        sim, _ = self._fight(
            ResistEffect(count=2, chance=1.0, target_type="self")
        )
        assert sim.player1.resist == 2, "the chance did the work"

    def test_reflect_goes_first(self):
        """The page: "Reflect, if a check is successful, occurs before
        Resist." So the charge that would have refused it is still there."""
        sim, _ = self._fight(
            ReflectEffect(count=1, target_type="self"),
            ResistEffect(count=1, chance=0.0, target_type="self"),
            stacks=1,
        )
        assert sim.player2.debuffs["memory_leaked"] == 1, "reflected"
        assert sim.player1.resist == 1, "and the resist was not spent"


class TestAStatusNobodyChose(_WithOneItem):
    """"Inflict a random debuff", "Gain 20 random other buffs".

    Picked uniformly over the kinds there are, one stack at a time, which is
    how cleansing picks and for the same reason.
    """

    def _hand_out(self, kind, count, target="self", seed=TEST_SEED):
        sim = BattleSimulator(seed=seed)
        sim.max_duration = 0.3
        p1, p2 = get_test_containers()
        sim.simulate_battle(
            [self._item([BattleStartTrigger(effects=[
                RandomStatusEffect(kind=kind, count=count, target_type=target)])])],
            [], 18, p1, p2)
        return sim

    def test_it_hands_out_as_many_as_it_says(self):
        sim = self._hand_out("buff", 5)
        assert sum(sim.player1.buffs.values()) == 5

    def test_it_picks_from_the_pool_its_kind_names(self):
        sim = self._hand_out("debuff", 6, target="enemy")
        assert set(sim.player2.debuffs) <= DEBUFFS
        assert not sim.player2.buffs

    def test_it_spreads_over_the_kinds_rather_than_picking_one(self):
        """Enough draws that landing on one kind every time would be a
        thousand-to-one, so this is testing that it looks again each time."""
        sim = self._hand_out("buff", 30)
        assert len(sim.player1.buffs) > 1

    def test_a_different_seed_picks_differently(self):
        one = self._hand_out("buff", 3, seed=TEST_SEED)
        two = self._hand_out("buff", 3, seed=TEST_SEED + 77)
        assert dict(one.player1.buffs) != dict(two.player1.buffs)


class TestTakingWhatYouRemoved(_WithOneItem):
    """"Steal a random buff" is cleansing the opponent and keeping it.

    The same effect with `keep` off is "Remove 1 Luck from your opponent", so
    the two clauses are one mechanic.
    """

    def _steal(self, keep):
        return self._run(
            [self._item([TimerTrigger(cooldown=1.0, cpu_cost=0, effects=[
                CleanseEffect(count=2, removes="buff", target_type="enemy",
                              keep=keep)])])],
            seconds=1.5,
            against=[self._item([BattleStartTrigger(effects=[
                BuffEffect("monitored", 5, "self")])], uid="them",
                position=(4, 0))],
        )[0]

    def test_what_is_taken_is_kept(self):
        sim = self._steal(keep=True)
        assert sim.player2.buffs["monitored"] == 3
        assert sim.player1.buffs["monitored"] == 2

    def test_removing_without_keeping_gains_nothing(self):
        sim = self._steal(keep=False)
        assert sim.player2.buffs["monitored"] == 3
        assert not sim.player1.buffs


class TestOnlySoManyTimes(_WithOneItem):
    """"(once)", "up to 3 times", "up to 5 per battle".

    Not a modifier's cap, which limits how much one item has given another and
    can hand out part of a grant. This limits how often the clause happens.
    """

    def _spent(self, times, seconds=5.5):
        sim, _ = self._run(
            [self._item([TimerTrigger(cooldown=1.0, cpu_cost=0, effects=[
                LimitEffect(times=times, effects=[
                    BuffEffect("monitored", 1, "self")])])])],
            seconds=seconds,
        )
        return sim.player1.buffs.get("monitored", 0)

    def test_it_stops_at_its_allowance(self):
        assert self._spent(times=3) == 3

    def test_once_means_once(self):
        assert self._spent(times=1) == 1

    def test_an_allowance_it_cannot_reach_is_no_limit(self):
        assert self._spent(times=99) == 5, "five activations in 5.5s"

    def test_two_items_have_an_allowance_each(self):
        """Kept per effect, not per clause, so a second copy of an item is
        not held back by the first one's spending."""
        clause = lambda: TimerTrigger(cooldown=1.0, cpu_cost=0, effects=[
            LimitEffect(times=2, effects=[BuffEffect("monitored", 1, "self")])])
        sim, _ = self._run(
            [self._item([clause()], uid="a"),
             self._item([clause()], uid="b", position=(1, 0))],
            seconds=5.5,
        )
        assert sim.player1.buffs["monitored"] == 4


class TestCriticalHits(_WithOneItem):
    """Backpack Battles' Critical hits page: "All sources of damage start with
    a 0% crit chance, and may only gain crit chance through outside sources.
    At 100% crit chance, an item's attacks are guaranteed to become critical.
    Crit chance does not exceed 100%."
    """

    @staticmethod
    def _swinger(crit=0.0, uid="w", position=(0, 0)):
        return BattleItem(
            spec=ItemSpec(
                id=uid, name="Swinger", category="problem", cost=1,
                player_class="neutral", shape=parse_map(["#"], "w"), slug=uid,
                kinds=frozenset({"melee"}),
                triggers=[TimerTrigger(cooldown=1.0, cpu_cost=0, effects=[
                    AttackEffect(min_damage=10, max_damage=10, accuracy=1.0,
                                 crit_chance=crit)])],
            ),
            position=position, uid=uid,
        )

    def test_nothing_crits_on_its_own(self):
        _, result = self._run([self._swinger()], seconds=5.5)
        assert 350 - result["player2_quota"] == 50, "five plain swings"

    def test_a_certain_crit_doubles_the_damage(self):
        _, result = self._run([self._swinger(crit=1.0)], seconds=5.5)
        assert 350 - result["player2_quota"] == 100

    def test_crit_chance_comes_from_outside(self):
        """An aura granting it is what "outside sources" means."""
        aura = BattleItem(
            spec=ItemSpec(
                id="aura", name="Aura", category="infrastructure", cost=1,
                player_class="neutral", slug="aura",
                shape=parse_map(["#*"], "aura"),
                triggers=[PassiveTrigger(effects=[ModifyEffect(
                    stat="critical_chance", value=1.0, target_type="star",
                    counting="any", cap=None)])],
            ),
            position=(0, 0), uid="aura",
        )
        _, result = self._run(
            [aura, self._swinger(position=(1, 0))], seconds=5.5
        )
        assert 350 - result["player2_quota"] == 100

    def test_it_does_not_go_past_certain(self):
        """Two sources of +100% are still one doubling, not two."""
        sim = BattleSimulator(seed=TEST_SEED)
        item = self._swinger(crit=1.0)
        item.crit_bonus = 5.0
        nobody = lambda who: Player(id=who, quota=1, max_quota=1, cpu=0)
        assert sim._crit_chance(1.0, item, nobody(1), nobody(2)) == 1.0

    def test_a_player_wide_crit_reaches_every_item(self):
        """"For the next 1.5s, all your attacks are Critical hits.\""""
        _, result = self._run(
            [self._swinger(),
             self._item([BattleStartTrigger(effects=[PlayerModifyEffect(
                 "critical_chance", 1.0, "self", 2.5)])],
                uid="grant", position=(1, 0))],
            seconds=4.5,
        )
        assert 350 - result["player2_quota"] == 60, "2 doubled, then 2 plain"

    def test_effect_damage_crits_too(self):
        """The page says so of these very items: "The damage effects... are
        capable of inflicting critical hits when they activate.\""""
        from item_effects import EffectDamageEffect

        hit = self._item([TimerTrigger(cooldown=1.0, cpu_cost=0, effects=[
            EffectDamageEffect(amount=10, lifesteal=0.0, per_status={},
                               whose={})])])
        hit.crit_bonus = 1.0
        _, result = self._run([hit], seconds=1.5)
        assert 350 - result["player2_quota"] == 20


class TestAnAmountThatGrowsWithWhatYouHold(_WithOneItem):
    """"Deals +1 damage per Spikes", "Deal 10 Effect-damage + 0.5 for each
    Spikes + 1 for each Empower", "Deals +0.4 per Cold of your opponent".

    Read where the damage is worked out rather than before the battle, so a
    stack gained part way through counts.
    """

    def test_flat_damage_grows_with_the_stacks(self):
        from item_effects import ModifyPerStatusEffect

        swing = self._item([
            PassiveTrigger(effects=[ModifyPerStatusEffect(
                stat="damage_flat", value=1.0, status="spiked", whose="self")]),
            TimerTrigger(cooldown=1.0, cpu_cost=0, effects=[
                AttackEffect(min_damage=10, max_damage=10, accuracy=1.0,
                             crit_chance=0.0)]),
        ])
        _, none = self._run([swing], seconds=1.5)
        _, three = self._run([swing], seconds=1.5, buffs={"spiked": 3})
        assert 350 - none["player2_quota"] == 10
        assert 350 - three["player2_quota"] == 13

    def test_it_counts_the_opponent_when_told_to(self):
        """"Deals +1 damage for each Blind of your opponent.\""""
        from item_effects import ModifyPerStatusEffect

        swing = self._item([
            PassiveTrigger(effects=[ModifyPerStatusEffect(
                stat="damage_flat", value=1.0, status="rate_limited",
                whose="enemy")]),
            BattleStartTrigger(effects=[
                DebuffEffect("rate_limited", 4, target_type="enemy")]),
            TimerTrigger(cooldown=1.0, cpu_cost=0, effects=[
                AttackEffect(min_damage=10, max_damage=10, accuracy=1.0,
                             crit_chance=0.0)]),
        ])
        _, result = self._run([swing], seconds=1.5)
        assert 350 - result["player2_quota"] == 14

    def test_maximum_damage_alone_widens_the_roll(self):
        """"Deals +1 maximum damage per Vampirism" raises the top and leaves
        the bottom, so the swing can still roll low."""
        from item_effects import ModifyPerStatusEffect

        swing = self._item([
            PassiveTrigger(effects=[ModifyPerStatusEffect(
                stat="max_damage_flat", value=1.0, status="draining",
                whose="self")]),
            TimerTrigger(cooldown=0.5, cpu_cost=0, effects=[
                AttackEffect(min_damage=1, max_damage=1, accuracy=1.0,
                             crit_chance=0.0)]),
        ])
        sim, _ = self._run([swing], seconds=9.0, buffs={"draining": 9})
        rolled = {a.damage for a in sim.actions if a.action == "damage"}
        assert min(rolled) == 1, "the bottom of the range did not move"
        assert max(rolled) > 1, "and the top did"

    def test_effect_damage_grows_with_two_statuses_at_once(self):
        """"Deal 10 Effect-damage + 0.5 for each Spikes + 1 for each
        Empower.\""""
        from item_effects import EffectDamageEffect

        hit = self._item([TimerTrigger(cooldown=1.0, cpu_cost=0, effects=[
            EffectDamageEffect(amount=10, lifesteal=0.0,
                               per_status={"spiked": 0.5, "monitored": 1.0},
                               whose={"spiked": "self", "monitored": "self"})])])
        _, result = self._run([hit], seconds=1.5,
                              buffs={"spiked": 4, "monitored": 3})
        assert 350 - result["player2_quota"] == 15, "10 + 2 + 3"


class TestWhatTheseTenLetTheCatalogueDo(_WithOneItem):
    """The items these mechanics were built for, run as they stand.

    A mechanic tested on an item made for the purpose proves the mechanic. It
    does not prove the translation, and the translation is where a clause
    turns into the wrong thing quietly.
    """

    @staticmethod
    def _real(item_id, position=(0, 0), uid=None):
        return BattleItem(spec=ITEM_CATALOG[item_id], position=position,
                          uid=uid or item_id)

    @staticmethod
    def _swinger(damage=20, uid="them", position=(4, 0), cooldown=1.0):
        return BattleItem(
            spec=ItemSpec(
                id=uid, name="Swinger", category="problem", cost=1,
                player_class="neutral", shape=parse_map(["#"], "s"), slug=uid,
                kinds=frozenset({"melee"}),
                triggers=[TimerTrigger(cooldown=cooldown, cpu_cost=0, effects=[
                    AttackEffect(min_damage=damage, max_damage=damage,
                                 accuracy=1.0, crit_chance=0.0)])],
            ),
            position=position, uid=uid,
        )

    def test_stone_helm_softens_the_first_five_seconds(self):
        """"Reduce damage taken by 25% for 5s and gain 35 Block." The Block
        goes first, so what is left over is what the share reduced."""
        _, softened = self._run(
            [self._real("stone_helm")], seconds=8.5,
            against=[self._swinger(damage=20)],
        )
        _, bare = self._run([], seconds=8.5, against=[self._swinger(damage=20)])
        taken, would_have = (350 - softened["player1_quota"],
                             350 - bare["player1_quota"])
        assert taken < would_have - 35, (
            "35 of it met Block, and the rest of the saving is the share"
        )

    def test_cap_of_discomfort_reduces_the_healing_of_the_other_side(self):
        """"Your opponent's healing is reduced by 30%." It is put on them."""
        healer = self._item([TimerTrigger(cooldown=1.0, cpu_cost=0, effects=[
            HealEffect(min_heal=10, max_heal=10)])], uid="h", position=(4, 0))
        sim = BattleSimulator(seed=TEST_SEED)
        sim.max_duration = 1.5
        p1, p2 = get_test_containers()
        original = sim._setup_item_handlers

        def setup(items, owner, enemy):
            out = original(items, owner, enemy)
            if owner.id == 2:
                owner.quota = 100
            return out

        sim._setup_item_handlers = setup
        result = sim.simulate_battle(
            [self._real("cap_of_discomfort")], [healer], 18, p1, p2)
        assert result["player2_quota"] - 100 == 7, "10 healed, 30% off"

    def test_stone_armor_makes_everything_cost_more(self):
        """"Items use +20% stamina.\""""
        hungry = self._item([TimerTrigger(cooldown=0.5, cpu_cost=1.0, effects=[
            AttackEffect(min_damage=1, max_damage=1, accuracy=1.0,
                         crit_chance=0.0)])], uid="w", position=(2, 2))
        _, plain = self._run([hungry], seconds=9.0)
        _, costly = self._run([self._real("stone_armor"), hungry], seconds=9.0)
        assert 350 - costly["player2_quota"] < 350 - plain["player2_quota"]

    def test_ruby_egg_turns_the_first_three_debuffs_back(self):
        """"Gain 4 Heat. Reflect 3 debuffs.\""""
        sim, _ = self._run(
            [self._real("ruby_egg")], seconds=1.5,
            against=[self._item([TimerTrigger(cooldown=1.0, cpu_cost=0, effects=[
                DebuffEffect("memory_leaked", 5, target_type="enemy")])],
                uid="them", position=(4, 0))],
        )
        assert sim.player1.buffs["optimized"] == 4
        assert sim.player1.debuffs["memory_leaked"] == 2, "5 came, 3 went back"
        assert sim.player2.debuffs["memory_leaked"] == 3

    def test_moon_armor_keeps_turning_debuffs_back(self):
        """"Every 2.6s: Gain 3 Mana and reflect 2 debuffs." Charges arrive on
        a clock, so a long fight turns back more than a short one."""
        def fight(seconds):
            sim, _ = self._run(
                [self._real("moon_armor")], seconds=seconds,
                against=[self._item([TimerTrigger(
                    cooldown=1.0, cpu_cost=0, effects=[DebuffEffect(
                        "memory_leaked", 1, target_type="enemy")])],
                    uid="them", position=(4, 0))],
            )
            return sim.player2.debuffs.get("memory_leaked", 0)

        # Charges arrive at 2.6s and every 2.6s after, and a stack arrives
        # every second, so what is turned back is what came after the first
        # charges did.
        assert fight(3.5) == 1
        assert fight(6.5) == 3
        assert fight(9.0) == 5

    def test_thorn_whip_hits_harder_for_every_spike(self):
        """"On hit: Gain 1 Spikes" and "Deals +1 damage per Spikes", so it
        climbs by itself."""
        sim, _ = self._run([self._real("mobius_lash")], seconds=20.0)
        whip = next(i for i in sim.loadout[1] if i.uid == "mobius_lash")
        held = sim.player1.buffs["spiked"]
        assert held > 0, "it gains a Spike on every hit"
        assert sim._per_status(whip, "damage_flat", sim.player1,
                               sim.player2) == held, "and reads them back"

    def test_lightsaber_reads_the_blind_it_did_not_cause(self):
        """"Deals +1 damage for each Blind of your opponent." The stacks are
        the opponent's, so an item of ours that blinds them feeds it."""
        def fight(blind):
            sim = BattleSimulator(seed=TEST_SEED)
            sim.max_duration = 2.0
            # A 1x4 rack, because a Lightsaber is 1x4 and the 3x3 the rest of
            # these tests use cannot hold one.
            racks = ([Container.of("patch_registry", (0, 0), "p1")],
                     [Container.of("patch_registry", (4, 0), "p2")])
            original = sim._setup_item_handlers

            def setup(items, owner, enemy):
                out = original(items, owner, enemy)
                if owner.id == 2 and blind:
                    owner.debuffs["rate_limited"] = blind
                return out

            sim._setup_item_handlers = setup
            return sim.simulate_battle(
                [self._real("lightsaber")], [], 18, *racks)

        # The same seed both times, so the roll behind the swing is the same
        # and the difference is only what the Blind added.
        plain, blinded = fight(0), fight(4)
        assert (350 - blinded["player2_quota"]) - (350 - plain["player2_quota"]) == 4

    def test_hedgehog_scales_its_effect_damage_with_its_spikes(self):
        """"Deal 10 Effect-damage + 0.5 for each Spikes.\""""
        _, plain = self._run([self._real("surveillance_drone")], seconds=5.5)
        _, spiky = self._run([self._real("surveillance_drone")], seconds=5.5,
                             buffs={"spiked": 10})
        assert 350 - plain["player2_quota"] == 10
        assert 350 - spiky["player2_quota"] == 15

    def test_hedgehog_answers_a_health_threshold_once(self):
        """"Health drops below 70%: Gain 3 Spikes and 25 Block (once)." It is
        crossing the line that fires it, and only the first crossing."""
        sim, _ = self._run(
            [self._real("surveillance_drone")], seconds=9.0, hurt=200,
            against=[self._swinger(damage=5, cooldown=1.0)],
        )
        assert sim.player1.buffs["spiked"] == 3, "not 3 for every swing after"

    def test_leather_boots_wait_for_the_line(self):
        early, _ = self._run(
            [self._real("leather_boots")], seconds=1.5,
            against=[self._swinger(damage=5)])
        late, _ = self._run(
            [self._real("leather_boots")], seconds=1.5, hurt=246,
            against=[self._swinger(damage=5)])
        assert not early.player1.buffs, "still above 70%"
        assert late.player1.buffs == {"calibrated": 1, "monitored": 1}
        assert late.player1.block == 15

    def test_squirrel_archer_takes_a_buff_and_keeps_it(self):
        """"On hit: Steal a random buff.\""""
        sim, _ = self._run(
            [self._real("data_leech_swarm")], seconds=5.0,
            against=[self._item([BattleStartTrigger(effects=[
                BuffEffect("monitored", 5, "self")])], uid="them",
                position=(4, 0))],
        )
        assert sim.player2.buffs["monitored"] < 5
        assert sim.player1.buffs["monitored"] == 5 - sim.player2.buffs["monitored"]

    def test_light_goobert_waits_for_six_activations(self):
        """"6 Star item activations: Heal for 25 and inflict 7 Blind for 3s."
        The Blind runs out; the healing does not."""
        star = ITEM_CATALOG["light_goobert"].shape.star
        inside = [(x, y) for x, y in star if 0 <= x <= 2 and 0 <= y <= 2]
        ticker = self._item([TimerTrigger(cooldown=0.5, cpu_cost=0, effects=[
            BuffEffect("calibrated", 0, "self")])], uid="t",
            position=inside[0])
        sim, _ = self._run(
            [self._real("light_goobert"), ticker], seconds=3.2, hurt=100
        )
        assert sim.player1.quota > 100, "it healed"
        assert sim.player2.debuffs.get("rate_limited", 0) == 7

    def test_light_gooberts_blind_wears_off(self):
        star = ITEM_CATALOG["light_goobert"].shape.star
        inside = [(x, y) for x, y in star if 0 <= x <= 2 and 0 <= y <= 2]
        ticker = self._item([TimerTrigger(cooldown=1.0, cpu_cost=0, effects=[
            BuffEffect("calibrated", 0, "self")])], uid="t",
            position=inside[0])
        # Six activations bring the aura at 6s, and its Blind runs to 9s.
        sim, _ = self._run(
            [self._real("light_goobert"), ticker], seconds=11.5, hurt=100
        )
        assert "rate_limited" not in sim.player2.debuffs, (
            "inflicted once the ticker had done its six, and 3s later gone"
        )

    def test_prismatic_orb_gives_one_thing_per_kind_in_its_star(self):
        """"Star Magic-item: Gain 2 Mana", and three more like it. Each counts
        only the items of its own kind."""
        star = ITEM_CATALOG["quantum_processor"].shape.star
        inside = [(x, y) for x, y in star if 0 <= x <= 2 and 0 <= y <= 2]
        def tagged(uid, kind, where):
            return BattleItem(
                spec=ItemSpec(
                    id=uid, name=uid, category="protocol", cost=1,
                    player_class="neutral", shape=parse_map(["#"], "t"),
                    slug=uid, kinds=frozenset({kind}), triggers=[]),
                position=where, uid=uid)
        sim, _ = self._run(
            [self._real("quantum_processor"),
             tagged("m", "magic", inside[0]),
             tagged("v", "vampiric", inside[1])],
            seconds=0.2,
        )
        assert sim.player1.buffs["credits"] == 2, "one Magic-item"
        assert sim.player1.buffs["draining"] == 1, "one Vampiric-item"
        assert not sim.player2.debuffs, "no Dark-item, so no random debuff"


class TestHealingHasOneRoad(_WithOneItem):
    """Every source of healing goes through the same place.

    Two shares pull on healing and they are written on different items, so a
    source that writes to the quota itself would quietly ignore both. Damage
    already had one road for the same reason; this checks healing does too,
    source by source, because a leak here is silent.
    """

    def _healed(self, effects, share, hurt=100, seconds=3.0, buffs=None,
                extra=()):
        given = dict(buffs or {})
        sim, result = self._run(
            [self._item([BattleStartTrigger(effects=(
                [PlayerModifyEffect("healing", share, "self", -1)] if share
                else []) + list(effects))])] + list(extra),
            seconds=seconds, hurt=hurt, buffs=given,
        )
        return result["player1_quota"] - hurt

    def test_a_plain_heal_takes_the_share(self):
        assert self._healed([HealEffect(min_heal=10, max_heal=10)], 0) == 10
        assert self._healed([HealEffect(min_heal=10, max_heal=10)], 1.0) == 20

    def test_regeneration_takes_the_share(self):
        plain = self._healed([BuffEffect("regenerating", 5, "self")], 0,
                             seconds=2.5)
        more = self._healed([BuffEffect("regenerating", 5, "self")], 1.0,
                            seconds=2.5)
        assert plain == 5
        assert more == 10

    def test_lifesteal_on_effect_damage_takes_the_share(self):
        from item_effects import EffectDamageEffect

        hit = [EffectDamageEffect(amount=10, lifesteal=1.0, per_status={},
                                  whose={})]
        assert self._healed(hit, 0, seconds=0.3) == 10
        assert self._healed(hit, 1.0, seconds=0.3) == 20

    def test_vampirism_takes_the_share(self):
        """Section 3.1: Vampirism heals a melee swing's damage back. It wrote
        to the quota itself and so ignored both shares, which nothing noticed
        until the roads were counted."""
        swing = [AttackEffect(min_damage=10, max_damage=10, accuracy=1.0,
                              crit_chance=0.0)]
        weapon = self._item([TimerTrigger(cooldown=1.0, cpu_cost=0,
                                          effects=swing)],
                            uid="w", position=(1, 0))
        plain = self._healed([], 0, seconds=1.5, buffs={"draining": 6},
                             extra=[weapon])
        more = self._healed([], 1.0, seconds=1.5, buffs={"draining": 6},
                            extra=[weapon])
        assert plain == 6, "six of the ten drained"
        assert more == 12


class TestWhatReflectAndResistAnswerTo(_WithOneItem):
    """Both are for what the other player sends.

    "The next debuff inflicts your opponent instead of you" is about a debuff
    arriving from across the table. A clause that puts one on its own owner --
    "Inflict 3 Poison and 2 Poison to yourself" -- is not that, and turning it
    back would send your own poison to them.
    """

    def _self_inflict(self, *also):
        sim, _ = self._run(
            [self._item([BattleStartTrigger(effects=list(also) + [
                DebuffEffect("memory_leaked", 3, target_type="self")])])],
            seconds=0.3,
        )
        return sim

    def test_your_own_debuff_is_not_turned_back(self):
        sim = self._self_inflict(ReflectEffect(count=5, target_type="self"))
        assert sim.player1.debuffs["memory_leaked"] == 3
        assert "memory_leaked" not in sim.player2.debuffs
        assert sim.player1.reflect == 5, "and no charge was spent"

    def test_your_own_debuff_is_not_refused(self):
        sim = self._self_inflict(
            ResistEffect(count=0, chance=1.0, target_type="self"))
        assert sim.player1.debuffs["memory_leaked"] == 3


class TestWhatStandsInFrontOfTheQuota(_WithOneItem):
    """The order damage is worked through, and why it is that order.

    A share the target carries comes off first, and Block absorbs what is
    actually arriving. Block absorbs damage, so it has to absorb the damage
    that arrives rather than the number before the reduction.
    """

    @staticmethod
    def _players(block=0, share=0.0):
        sim = BattleSimulator(seed=TEST_SEED)
        target = Player(id=1, quota=100, max_quota=100, cpu=3.0)
        attacker = Player(id=2, quota=100, max_quota=100, cpu=3.0)
        sim.player1, sim.player2 = target, attacker
        target.block = block
        if share:
            target.mods.append(Timed("modifier", "damage_taken", share, None))
        return sim, target, attacker

    def _land(self, damage, block=0, share=0.0):
        sim, target, attacker = self._players(block, share)
        sim._take_damage(target, damage, source="w", action="damage",
                         attacker=attacker, blockable=True)
        return 100 - target.quota, target.block

    def test_block_absorbs_the_reduced_damage(self):
        """Twenty against a quarter off spends fifteen Block, not twenty."""
        took, left = self._land(20, block=35, share=-0.25)
        assert took == 0
        assert left == 20, "35 less the 15 that actually arrived"

    def test_without_a_share_block_absorbs_the_whole_blow(self):
        took, left = self._land(20, block=35)
        assert (took, left) == (0, 15)

    def test_what_block_cannot_hold_lands_reduced(self):
        took, left = self._land(20, block=5, share=-0.5)
        assert took == 5, "20 halved is 10, of which Block held 5"
        assert left == 0

    def test_invulnerability_spends_no_block_at_all(self):
        """Nothing arrives, so there is nothing for Block to absorb."""
        took, left = self._land(20, block=35, share=-1.0)
        assert (took, left) == (0, 35)

    def test_block_does_not_answer_damage_that_is_not_an_attack(self):
        """Effect-damage and poison are not absorbed, and the flag is off
        unless a caller says otherwise."""
        sim, target, attacker = self._players(block=35)
        sim._take_damage(target, 20, source="w", action="damage",
                         attacker=attacker)
        assert 100 - target.quota == 20
        assert target.block == 35


class TestAModifierThatNothingAppliesIsRefused(_WithOneItem):
    """A stat that loads and then does nothing is worse than one that will
    not load.

    `damage_flat` and `max_damage_flat` sat in MODIFIERS for a commit doing
    exactly that: an aura granting either parsed, settled, and changed no
    number at all. `_apply_effects` has had this guard since it caught three
    bugs; `_modify` did not.
    """

    def test_an_unknown_stat_stops_rather_than_doing_nothing(self):
        sim = BattleSimulator(seed=TEST_SEED)
        item = self._item([])
        with pytest.raises(TypeError, match="nothing here applies"):
            sim._modify(item, ModifyEffect(
                stat="wingspan", value=1.0, target_type="own",
                counting="any", cap=None))

    def test_flat_damage_from_a_modifier_reaches_the_swing(self):
        """An aura granting +2 flat, which is not the same as +200%."""
        aura = BattleItem(
            spec=ItemSpec(
                id="aura", name="Aura", category="infrastructure", cost=1,
                player_class="neutral", slug="aura",
                shape=parse_map(["#*"], "aura"),
                triggers=[PassiveTrigger(effects=[ModifyEffect(
                    stat="damage_flat", value=2.0, target_type="star",
                    counting="any", cap=None)])],
            ),
            position=(0, 0), uid="aura",
        )
        swinger = self._item([TimerTrigger(cooldown=1.0, cpu_cost=0, effects=[
            AttackEffect(min_damage=10, max_damage=10, accuracy=1.0,
                         crit_chance=0.0)])], uid="w", position=(1, 0))
        _, alone = self._run([swinger], seconds=1.5)
        _, helped = self._run([aura, swinger], seconds=1.5)
        assert 350 - alone["player2_quota"] == 10
        assert 350 - helped["player2_quota"] == 12

    def test_maximum_damage_from_a_modifier_widens_the_roll(self):
        aura = BattleItem(
            spec=ItemSpec(
                id="aura", name="Aura", category="infrastructure", cost=1,
                player_class="neutral", slug="aura",
                shape=parse_map(["#*"], "aura"),
                triggers=[PassiveTrigger(effects=[ModifyEffect(
                    stat="max_damage_flat", value=8.0, target_type="star",
                    counting="any", cap=None)])],
            ),
            position=(0, 0), uid="aura",
        )
        swinger = self._item([TimerTrigger(cooldown=0.5, cpu_cost=0, effects=[
            AttackEffect(min_damage=1, max_damage=1, accuracy=1.0,
                         crit_chance=0.0)])], uid="w", position=(1, 0))
        sim, _ = self._run([aura, swinger], seconds=9.0)
        rolled = {a.damage for a in sim.actions if a.action == "damage"}
        assert min(rolled) == 1, "the bottom of the range did not move"
        assert max(rolled) > 1, "and the top did"
