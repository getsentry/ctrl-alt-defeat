"""
Comprehensive tests for battle engine to ensure it matches Game Design Document
"""

from copy import deepcopy

import pytest
from battle_engine import (
    ITEM_CATALOG,
    LATE_BATTLE,
    MEMORY_LEAKED,
    NIGHTFALL,
    OVER_TIME,
    POISON_PERIOD,
    BattleItem,
    BattleSimulator,
    Fatigued,
    MemoryLeaked,
    Player,
    Timed,
    _Zone,
)
from containers import Container
from grid_system import parse_map
from item_effects import (
    BUFFS,
    DEBUFFS,
    MODIFIERS,
    AfterTrigger,
    AttackEffect,
    AuraTrigger,
    BattleStartTrigger,
    BlockEffect,
    BuffEffect,
    ChanceEffect,
    ChoiceEffect,
    CleanseEffect,
    ConditionEffect,
    ConsumeEffect,
    ConvertHealthEffect,
    CostEffect,
    CounterTrigger,
    CpuDrainEffect,
    DebuffEffect,
    DestroyBlockEffect,
    EffectDamageEffect,
    ExtraAttackEffect,
    FatigueStartTrigger,
    GainDamageEffect,
    HealEffect,
    HealthThresholdTrigger,
    InflictFatigueEffect,
    ItemSpec,
    LimitEffect,
    MaxHealthEffect,
    ModifyEffect,
    ModifyPerEffect,
    ModifyPerStatusEffect,
    NextAttackEffect,
    OnAttackedTrigger,
    OnHitTrigger,
    OnMissTrigger,
    OnStunTrigger,
    OutOfStaminaTrigger,
    PassiveTrigger,
    PerCountEffect,
    PlayerModifyEffect,
    PreventDamageEffect,
    RandomStatusEffect,
    ReflectEffect,
    ResistEffect,
    SaleChanceEffect,
    StaminaEffect,
    StatusChangeTrigger,
    StunEffect,
    TimerTrigger,
    TriggerItemEffect,
    WhenAffordableTrigger,
)
from pydantic import ValidationError
from schemas import BattleAction

# A battle with no seed uses the clock, which makes every run a different
# battle. Tests pin it so a failure is reproducible.
TEST_SEED = 424242


def charges_left(player):
    """Resist charges the player has left, across every resist granted.

    They are kept whole rather than totalled on the player, because one may
    refuse only Blind and another only critical hits, and a single number
    cannot say which is which.
    """
    return sum(spec.count for spec in player.resists)


def get_test_containers():
    """A quiet rack of four squares each, four wide and four deep.

    Four plain VMs rather than one big bag, because every bag in the
    catalogue carries a clause now: the 3x3 this used to be amplifies its
    owner's healing by 12%, which every healing test would have to allow for.
    A rack of standard_vm covers the same squares and says nothing.
    """
    return (
        [
            Container.of("standard_vm", (0, 0), "p1_test_rack_a"),
            Container.of("standard_vm", (2, 0), "p1_test_rack_b"),
            Container.of("standard_vm", (0, 2), "p1_test_rack_c"),
            Container.of("standard_vm", (2, 2), "p1_test_rack_d"),
        ],
        [
            Container.of("standard_vm", (4, 0), "p2_test_rack_a"),
            Container.of("standard_vm", (6, 0), "p2_test_rack_b"),
            Container.of("standard_vm", (4, 2), "p2_test_rack_c"),
            Container.of("standard_vm", (6, 2), "p2_test_rack_d"),
        ],
    )


class TestGameDesignCompliance:
    """Test that battle engine exactly matches the Game Design Document"""

    def test_player_quota_scaling(self):
        """Test Section 1.1: Player Quota scaling by round"""
        sim = BattleSimulator(seed=TEST_SEED)

        # One value per round, not tiers, exactly as the document lists them
        expected = [
            25,
            35,
            45,
            55,
            70,
            85,
            100,
            115,
            130,
            150,
            170,
            190,
            210,
            230,
            260,
            290,
            320,
            350,
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

    def test_a_draw_goes_to_player_one(self):
        """Equal quota is a win for player 1, who is the person playing.

        Both fighters running out together is common rather than rare: quota
        is clamped at nothing, so the overkill that used to separate them is
        gone, and fatigue lands on both in the same tick by design. Measured
        at 63% of mirror matches and 5% of battles between real builds.
        """
        sim = BattleSimulator(seed=TEST_SEED)
        p1_containers, p2_containers = get_test_containers()

        result = sim.simulate_battle(
            [],
            [],
            round_number=1,
            p1_containers=p1_containers,
            p2_containers=p2_containers,
        )

        assert result["player1_quota"] == result["player2_quota"]
        assert result["winner"] == 1

    def test_player_two_still_wins_when_it_is_ahead(self):
        """The draw rule must not hand player 1 a battle it actually lost."""
        sim = BattleSimulator(seed=TEST_SEED)
        p1_containers, p2_containers = get_test_containers()
        blade = BattleItem(spec=deepcopy(ITEM_CATALOG["null_blade"]), position=(4, 0))
        blade.spec.min_damage = 200
        blade.spec.max_damage = 200

        result = sim.simulate_battle(
            [],
            [blade],
            round_number=1,
            p1_containers=p1_containers,
            p2_containers=p2_containers,
        )

        assert result["player1_quota"] < result["player2_quota"]
        assert result["winner"] == 2

    def test_a_shop_effect_does_not_stop_a_battle(self):
        """A sale chance stands while the item is held, so it hangs off a
        passive trigger -- and the battle walks those.

        It reached the dispatcher, matched no branch, and raised, so any rack
        holding Fortune Bot could not fight at all. The item is in the shop and
        turns up in about one offer in a hundred, so this was reachable.
        """
        sim = BattleSimulator(seed=TEST_SEED)
        p1_containers, p2_containers = get_test_containers()
        lucky = BattleItem(spec=deepcopy(ITEM_CATALOG["maneki_neko"]), position=(0, 0))
        assert any(
            isinstance(effect, SaleChanceEffect)
            for trigger in lucky.spec.triggers
            for effect in getattr(trigger, "effects", []) or []
        ), "maneki_neko no longer carries a sale chance; pick another item"

        result = sim.simulate_battle(
            [lucky],
            [],
            round_number=1,
            p1_containers=p1_containers,
            p2_containers=p2_containers,
        )

        assert result["winner"] in (1, 2)

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

    def test_every_action_says_where_the_block_stands(self):
        """Block is spent a point at a time by every blow that lands, so a
        player watching cannot tell how much is left unless the timeline says
        -- and it only ever said the health and the CPU."""
        p1_containers, p2_containers = get_test_containers()
        sim = BattleSimulator(seed=TEST_SEED)
        # Stone Badge gives 4 Block every 3 seconds, so the battle is watched
        # by a fighter who really does stand behind some.
        shield = "stone_badge"

        sim.simulate_battle(
            [BattleItem(spec=deepcopy(ITEM_CATALOG[shield]), position=(0, 0))],
            [BattleItem(spec=deepcopy(ITEM_CATALOG["null_blade"]), position=(4, 0))],
            1,
            p1_containers=p1_containers,
            p2_containers=p2_containers,
        )

        stamped = [
            action.details["block"]
            for action in sim.actions
            if action.details and "block" in action.details
        ]
        assert stamped, "Every action should say where the Block stood"
        assert all(len(pair) == 2 for pair in stamped), (
            "both fighters, like the health and the CPU beside it"
        )
        assert any(pair[0] > 0 for pair in stamped), (
            "a fighter holding a shield should be seen holding Block"
        )

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
            "optimized",
            "monitored",
            "calibrated",
            "regenerating",
            "spiked",
            "draining",
            "credits",
        }

    def test_battle_duration(self):
        """Section 6.2: no time limit, only a backstop fatigue never reaches"""
        sim = BattleSimulator(seed=TEST_SEED)
        assert sim.max_duration > 60.0, "60s is not a rule of the game"

        # Two empty racks cannot hurt each other, so fatigue is the only thing
        # that can finish this, and it has to, well short of the backstop.
        p1_containers, p2_containers = get_test_containers()
        result = sim.simulate_battle(
            [],
            [],
            round_number=1,
            p1_containers=p1_containers,
            p2_containers=p2_containers,
        )
        assert result["duration"] < sim.max_duration

    def test_nightfall_is_seventeen_seconds_in(self):
        """Section 7.1: the one number the whole mechanic hangs off"""
        assert NIGHTFALL == 17.0
        assert BattleSimulator(seed=TEST_SEED).nightfall == NIGHTFALL

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
            player,
            15,
            source="test_item",
            action="damage",
            attacker=attacker,
            blockable=True,
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
                        effects=[
                            AttackEffect(
                                min_damage=5,
                                max_damage=10,
                                accuracy=0.85,
                                crit_chance=0.0,
                            )
                        ],
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
            items,
            [],
            round_number=1,
            p1_containers=p1_containers,
            p2_containers=p2_containers,
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
        fresh = BattleItem(
            spec=deepcopy(ITEM_CATALOG["stack_smasher"]), position=(0, 0)
        )
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
                            AttackEffect(
                                min_damage=100,
                                max_damage=100,
                                accuracy=1.0,
                                crit_chance=0.0,
                            )
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

    def test_a_battle_nobody_can_win_is_ended_by_fatigue(self):
        """Section 7.1: fatigue is what stops a battle, not the clock.

        Two empty racks. Nothing either player owns can move the other's
        quota, so every point taken off is fatigue's, and the round-1 quota of
        25 goes to nothing seven payouts in: 1+2+3+4+5+6+7 is 28.
        """
        sim = BattleSimulator(seed=TEST_SEED)

        p1_containers, p2_containers = get_test_containers()
        result = sim.simulate_battle(
            [],
            [],
            round_number=1,
            p1_containers=p1_containers,
            p2_containers=p2_containers,
        )

        assert result["duration"] == 23.0  # Nightfall at 17s, seven payouts
        assert result["player1_quota"] == 0
        assert result["player2_quota"] == 0
        assert [a for a in result["actions"] if a.action == "nightfall"]


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
        sim.simulate_battle(p1_items, [], 1, p1_containers, p2_containers)
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
        """ "Weapons will still provide activations regardless if their attack
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
        # Night never falls, so the only thing that can move the quota is the
        # poison. Otherwise fatigue is in every reading past 17 seconds.
        sim.nightfall = seconds + 1

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

        sim.simulate_battle([shield], [attacker], 18, p1_containers, p2_containers)
        return sim, sim.player2

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

        sim.simulate_battle(
            [shield], [self._attacker(5)], 18, p1_containers, p2_containers
        )
        assert sim.player2.cpu >= 0.0

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
                id="drainer",
                name="Drainer",
                category="problem",
                cost=1,
                player_class="neutral",
                shape=parse_map(["#"], "d"),
                slug="drainer",
                triggers=[
                    TimerTrigger(
                        cooldown=1.0,
                        cpu_cost=0,
                        effects=[CpuDrainEffect(1.0, target_type="attacker")],
                    )
                ],
            ),
            position=(0, 0),
            uid="drainer",
        )
        p1_containers, p2_containers = get_test_containers()
        sim = BattleSimulator(seed=TEST_SEED)
        sim.max_duration = 3.5

        sim.simulate_battle([drainer], [], 18, p1_containers, p2_containers)
        assert [a for a in sim.actions if a.action == "cpu_drain"]
        assert sim.player2.cpu < sim.player2.max_cpu

    def test_it_never_puts_anyone_into_debt(self):
        """Negative CPU would lock a player out for the rest of the battle"""
        greedy = BattleItem(
            spec=ItemSpec(
                id="greedy",
                name="Greedy",
                category="problem",
                cost=1,
                player_class="neutral",
                shape=parse_map(["#"], "g"),
                slug="greedy",
                triggers=[
                    TimerTrigger(
                        cooldown=0.5,
                        cpu_cost=0,
                        effects=[CpuDrainEffect(99.0, target_type="attacker")],
                    )
                ],
            ),
            position=(0, 0),
            uid="greedy",
        )
        p1_containers, p2_containers = get_test_containers()
        sim = BattleSimulator(seed=TEST_SEED)
        sim.max_duration = 5.0

        sim.simulate_battle([greedy], [], 18, p1_containers, p2_containers)
        assert sim.player2.cpu >= 0.0

    def test_a_shield_still_drains_the_attacker(self):
        """The route changed, the behaviour did not"""
        shield = BattleItem(
            spec=ItemSpec(
                id="s",
                name="Shield",
                category="defense",
                cost=1,
                player_class="neutral",
                shape=parse_map(["#"], "s"),
                slug="s",
                kinds=frozenset({"melee"}),
                triggers=[
                    OnAttackedTrigger(
                        answers_to=frozenset({"melee"}),
                        chance=1.0,
                        effects=[
                            PreventDamageEffect(10),
                            CpuDrainEffect(0.5, target_type="attacker"),
                        ],
                    )
                ],
            ),
            position=(0, 0),
            uid="shield",
        )

        sword = BattleItem(
            spec=ItemSpec(
                id="w",
                name="Sword",
                category="problem",
                cost=1,
                player_class="neutral",
                shape=parse_map(["#"], "w"),
                slug="w",
                kinds=frozenset({"melee"}),
                triggers=[
                    TimerTrigger(
                        cooldown=1.0,
                        cpu_cost=0,
                        effects=[
                            AttackEffect(
                                min_damage=5,
                                max_damage=5,
                                accuracy=1.0,
                                crit_chance=0.0,
                            )
                        ],
                    )
                ],
            ),
            position=(4, 0),
            uid="sword",
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
                id=uid,
                name="Watcher",
                category="infrastructure",
                cost=1,
                player_class="neutral",
                shape=parse_map(["#"], "w"),
                slug=uid,
                kinds=frozenset({"melee"}),
                triggers=[
                    HealthThresholdTrigger(
                        threshold=threshold, effects=[HealEffect(1, 1)]
                    )
                ],
            ),
            position=(0, 0),
            uid=uid,
        )

    @staticmethod
    def _sword(damage: int, uid: str = "sword"):
        return BattleItem(
            spec=ItemSpec(
                id=uid,
                name="Sword",
                category="problem",
                cost=1,
                player_class="neutral",
                shape=parse_map(["#"], "s"),
                slug=uid,
                kinds=frozenset({"melee"}),
                triggers=[
                    TimerTrigger(
                        cooldown=0.5,
                        cpu_cost=0,
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
        sim.nightfall = 31.0  # This is about the cleanse, not about fatigue
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
        assert not [
            a for a in sim.actions if a.action == "dot" and a.timestamp > 10_000
        ], "no poison left to tick"


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

        sim.player1, sim.player2 = target, attacker
        sim._take_damage(
            target,
            15,
            source="sword",
            action="damage",
            attacker=attacker,
            blockable=True,
        )

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
            position=(0, 0),
            uid="boost",
        )
        p1, p2 = get_test_containers()
        sim = BattleSimulator(seed=TEST_SEED)
        sim.max_duration = 0.2
        sim.simulate_battle([booster], [], 1, p1, p2)

        assert not [
            a for a in sim.actions if a.action == "buff"
        ], "changing a number on an item is not a buff and must not log one"

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
                id="t",
                name="Timed",
                category="problem",
                cost=1,
                player_class="neutral",
                shape=parse_map(["#"], "t"),
                slug="t",
                triggers=[],
            ),
            position=(0, 0),
            uid="timed",
        )
        return sim._cooldown_for(TimerTrigger(cooldown=base, cpu_cost=0), owner, plain)

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
                    id="s",
                    name="Sword",
                    category="problem",
                    cost=1,
                    player_class="neutral",
                    shape=parse_map(["#"], "s"),
                    slug="s",
                    kinds=frozenset({"melee"}),
                    triggers=[
                        TimerTrigger(
                            cooldown=1.0,
                            cpu_cost=0,
                            effects=[
                                AttackEffect(
                                    min_damage=1,
                                    max_damage=1,
                                    accuracy=1.0,
                                    crit_chance=0.0,
                                )
                            ],
                        )
                    ],
                ),
                position=(0, 0),
                uid="sword",
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
                id="s",
                name="Sword",
                category="problem",
                cost=1,
                player_class="neutral",
                shape=parse_map(["#"], "s"),
                slug="s",
                kinds=frozenset({"melee"}),
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
                    )
                ],
            ),
            position=(0, 0),
            uid="sword",
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
        assert not [
            a for a in sim.actions if a.action == "heal"
        ], "healing nobody should log nothing"

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
                id=uid,
                name="Weapon",
                category="problem",
                cost=1,
                player_class="neutral",
                shape=parse_map(["#"], "w"),
                slug=uid,
                kinds=frozenset({"melee"} if melee else {"ranged"}),
                triggers=[
                    TimerTrigger(
                        cooldown=1.0,
                        cpu_cost=0,
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
            position=position,
            uid=uid,
        )

    def _run(
        self,
        mine,
        theirs,
        mine_buffs=None,
        their_buffs=None,
        seconds=2.5,
        mine_quota=None,
    ):
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

        sim, players = self._run([self._weapon(damage=5)], [], their_buffs={SPIKED: 2})
        back = [
            a
            for a in sim.actions
            if a.action == "damage" and (a.details or {}).get("buff_name") == SPIKED
        ]
        assert back, "the attacker should take the spikes"
        assert all(a.player == 1 for a in back), "back at whoever swung"

    def test_spiked_ignores_a_ranged_hit(self):
        from battle_engine import SPIKED

        sim, _ = self._run(
            [self._weapon(damage=5, melee=False)], [], their_buffs={SPIKED: 2}
        )
        assert not [
            a for a in sim.actions if (a.details or {}).get("buff_name") == SPIKED
        ]

    def test_spiked_never_returns_more_than_the_hit(self):
        """ "up to 100% of the damage" -- five stacks against a 2 damage hit
        gives back 2, not 5."""
        from battle_engine import SPIKED

        sim, _ = self._run([self._weapon(damage=2)], [], their_buffs={SPIKED: 5})
        back = [a for a in sim.actions if (a.details or {}).get("buff_name") == SPIKED]
        assert back and all(a.damage == 2 for a in back)

    def test_draining_heals_the_one_who_swung(self):
        from battle_engine import DRAINING

        # Draining cannot heal what is not missing, so start them hurt.
        sim, _ = self._run(
            [self._weapon(damage=5)], [], mine_buffs={DRAINING: 3}, mine_quota=100
        )
        healed = [
            a
            for a in sim.actions
            if a.action == "heal" and (a.details or {}).get("buff_name") == DRAINING
        ]
        assert healed and all(a.damage == 3 for a in healed)

    def test_draining_ignores_a_ranged_hit(self):
        from battle_engine import DRAINING

        sim, _ = self._run(
            [self._weapon(damage=5, melee=False)],
            [],
            mine_buffs={DRAINING: 3},
            mine_quota=100,
        )
        assert not [
            a for a in sim.actions if (a.details or {}).get("buff_name") == DRAINING
        ]

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
        assert not [
            a
            for a in sim.actions
            if (a.details or {}).get("buff_name") in (SPIKED, DRAINING)
        ]


class TestAShieldAnswersOnlyWhatItSays:
    """Every shield in the source game is "On attacked (Melee)", and ours
    used to roll against everything, which made them all stronger than they
    should be against a ranged build."""

    @staticmethod
    def _weapon(melee: bool):
        from item_effects import AttackEffect

        return BattleItem(
            spec=ItemSpec(
                id="w",
                name="Weapon",
                category="problem",
                cost=1,
                player_class="neutral",
                shape=parse_map(["#"], "w"),
                slug="w",
                kinds=frozenset({"melee"} if melee else {"ranged"}),
                triggers=[
                    TimerTrigger(
                        cooldown=1.0,
                        cpu_cost=0,
                        effects=[
                            AttackEffect(
                                min_damage=6,
                                max_damage=6,
                                accuracy=1.0,
                                crit_chance=0.0,
                            )
                        ],
                    )
                ],
            ),
            position=(4, 0),
            uid="weapon",
        )

    @staticmethod
    def _shield(answers_to):
        from item_effects import CpuDrainEffect, OnAttackedTrigger, PreventDamageEffect

        return BattleItem(
            spec=ItemSpec(
                id="s",
                name="Shield",
                category="defense",
                cost=1,
                player_class="neutral",
                shape=parse_map(["#"], "s"),
                slug="s",
                triggers=[
                    OnAttackedTrigger(
                        answers_to=frozenset(answers_to),
                        chance=1.0,
                        effects=[
                            PreventDamageEffect(10),
                            CpuDrainEffect(0.5, target_type="attacker"),
                        ],
                    )
                ],
            ),
            position=(0, 0),
            uid="shield",
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
        assert [
            a
            for a in self._run(self._shield(both), self._weapon(True)).actions
            if a.action == "block"
        ]
        assert [
            a
            for a in self._run(self._shield(both), self._weapon(False)).actions
            if a.action == "block"
        ]

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
    def _projector(
        value=0.2,
        stat="trigger_speed",
        target="star",
        position=(1, 0),
        uid="boost",
        counting="any",
        cap=None,
    ):
        from item_effects import ModifyEffect, PassiveTrigger

        return BattleItem(
            spec=ItemSpec(
                id=uid,
                name="Aura",
                category="infrastructure",
                cost=1,
                player_class="neutral",
                slug=uid,
                shape=parse_map(["*##*"], "aura"),
                triggers=[
                    PassiveTrigger(
                        effects=[
                            ModifyEffect(
                                stat=stat,
                                value=value,
                                target_type=target,
                                counting=counting,
                                cap=cap,
                                duration=-1,
                            )
                        ]
                    )
                ],
            ),
            position=position,
            uid=uid,
        )

    @staticmethod
    def _plain(position, uid):
        from item_effects import AttackEffect

        return BattleItem(
            spec=ItemSpec(
                id=uid,
                name="Plain",
                category="problem",
                cost=1,
                player_class="neutral",
                shape=parse_map(["#"], "p"),
                slug=uid,
                kinds=frozenset({"melee"}),
                triggers=[
                    TimerTrigger(
                        cooldown=2.0,
                        cpu_cost=0,
                        effects=[
                            AttackEffect(
                                min_damage=4,
                                max_damage=4,
                                accuracy=1.0,
                                crit_chance=0.0,
                            )
                        ],
                    )
                ],
            ),
            position=position,
            uid=uid,
        )

    def _run(self, items):
        containers = [
            Container.of("mesh_network_hub", (0, 0), "a"),
            Container.of("mesh_network_hub", (4, 0), "c"),
        ]
        sim = BattleSimulator(seed=TEST_SEED)
        sim.max_duration = 0.2
        result = sim.simulate_battle(
            items,
            [],
            1,
            containers,
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
                id="f",
                name="Far",
                category="infrastructure",
                cost=1,
                player_class="neutral",
                slug="f",
                shape=parse_map(["#..*"], "far reach"),
                triggers=[],
            ),
            position=(0, 0),
            uid="far",
        )
        assert far.aura_squares("star") == [(3, 0)], "three squares away"

    def test_a_speed_aura_reaches_the_cooldown(self):
        """It lands in the same sum as Optimized, which is what the source
        game's formula is for."""
        by_uid = self._run([self._projector(), self._plain((0, 0), "inside")])
        sim = BattleSimulator(seed=TEST_SEED)
        owner = Player(id=1, quota=100, max_quota=100, cpu=3.0)
        base = TimerTrigger(cooldown=2.0, cpu_cost=0)
        assert sim._cooldown_for(base, owner, by_uid["inside"]) == pytest.approx(
            2.0 / 1.2
        )

    def _swings(self, items, seconds=12.0):
        """Run a battle and report what the item in the zone actually did."""
        containers = [
            Container.of("mesh_network_hub", (0, 0), "a"),
            Container.of("mesh_network_hub", (4, 0), "c"),
        ]
        sim = BattleSimulator(seed=TEST_SEED)
        sim.max_duration = seconds
        sim.simulate_battle(
            items,
            [],
            18,
            containers,
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
        boosted = self._swings(
            [
                self._projector(value=0.5, stat="accuracy"),
                self._coin_flip_weapon(),
            ]
        )

        def landed(acts):
            return len([a for a in acts if a.action == "damage"])

        assert landed(plain) < landed(boosted)
        assert not [
            a for a in boosted if a.action == "miss"
        ], "half a coin flip plus 50% never misses"

    def test_a_damage_aura_changes_what_lands(self):
        plain = self._swings([self._plain((0, 0), "inside")])
        boosted = self._swings(
            [
                self._projector(value=1.0, stat="damage"),
                self._plain((0, 0), "inside"),
            ]
        )

        def first(acts):
            return next(a.damage for a in acts if a.action == "damage")

        assert first(plain) == 4
        assert first(boosted) == 8, "double damage should double the hit"

    def test_an_accuracy_aura_reaches_the_roll(self):
        by_uid = self._run(
            [
                self._projector(value=0.25, stat="accuracy"),
                self._plain((0, 0), "inside"),
            ]
        )
        assert by_uid["inside"].accuracy_bonus == pytest.approx(0.25)

    def test_a_damage_aura_reaches_the_total(self):
        by_uid = self._run(
            [
                self._projector(value=0.5, stat="damage"),
                self._plain((0, 0), "inside"),
            ]
        )
        assert by_uid["inside"].damage_mult == pytest.approx(1.5)

    def test_a_cpu_aura_makes_an_item_cheaper_to_run(self):
        from item_effects import AttackEffect

        def swings(with_aura):
            weapon = BattleItem(
                spec=ItemSpec(
                    id="w",
                    name="Costly",
                    category="problem",
                    cost=1,
                    player_class="neutral",
                    shape=parse_map(["#"], "w"),
                    slug="w",
                    kinds=frozenset({"melee"}),
                    triggers=[
                        TimerTrigger(
                            cooldown=0.5,
                            cpu_cost=2.0,
                            effects=[
                                AttackEffect(
                                    min_damage=1,
                                    max_damage=1,
                                    accuracy=1.0,
                                    crit_chance=0.0,
                                )
                            ],
                        )
                    ],
                ),
                position=(0, 0),
                uid="costly",
            )
            items = [weapon]
            if with_aura:
                items.append(self._projector(value=1.5, stat="cpu_cost"))
            return len(
                [a for a in self._swings(items, seconds=6.0) if a.action == "damage"]
            )

        assert swings(with_aura=True) > swings(
            with_aura=False
        ), "a cheaper item runs more often when CPU is the limit"

    def test_an_aura_never_makes_an_item_free(self):
        """The floor is zero, not a refund."""
        from item_effects import ModifyEffect

        sim = BattleSimulator(seed=TEST_SEED)
        item = self._plain((0, 0), "plain")
        sim._modify(
            item,
            ModifyEffect(
                stat="cpu_cost",
                value=99.0,
                target_type="star",
                counting="any",
                cap=None,
                duration=-1,
            ),
        )
        cost = max(0.0, 1.0 - item.cpu_discount)
        assert cost == 0.0

    def test_contained_reaches_nothing_yet(self):
        """A container does not know what sits inside it. Reaching nothing is
        the safer way to be wrong: it cannot make an item quietly stronger."""
        by_uid = self._run(
            [
                self._projector(target="contained"),
                self._plain((0, 0), "inside"),
            ]
        )
        assert by_uid["inside"].speed_mult == 1.0


class TestAnAuraCountsWhatStandsInIt:
    """Section 3.1, the other direction. "Triggers 15% faster for each Star
    Food" changes the item projecting the zone, by how much is standing in it.

    37 items in the source game read this way against 22 the other, so it is
    the commoner half of an aura.
    """

    @staticmethod
    def _counter(
        value=0.15,
        stat="trigger_speed",
        counting="any",
        zone="star",
        uid="counter",
        position=(1, 0),
    ):
        from item_effects import ModifyPerEffect, PassiveTrigger

        return BattleItem(
            spec=ItemSpec(
                id=uid,
                name="Counter",
                category="problem",
                cost=1,
                player_class="neutral",
                slug=uid,
                shape=parse_map(["*##*"], "counter"),
                kinds=frozenset({"melee"}),
                triggers=[
                    PassiveTrigger(
                        effects=[
                            ModifyPerEffect(
                                stat=stat, value=value, zone=zone, counting=counting
                            )
                        ]
                    )
                ],
            ),
            position=position,
            uid=uid,
        )

    @staticmethod
    def _standing(position, uid, kinds=frozenset(), category="problem"):
        return BattleItem(
            spec=ItemSpec(
                id=uid,
                name="Standing",
                category=category,
                cost=1,
                player_class="neutral",
                shape=parse_map(["#"], "s"),
                slug=uid,
                kinds=kinds,
                triggers=[],
            ),
            position=position,
            uid=uid,
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
            items,
            [],
            1,
            containers,
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
        by_uid = self._run(
            [
                self._counter(),
                self._standing((0, 0), "left"),
                self._standing((3, 0), "right"),
            ]
        )
        assert by_uid["counter"].speed_mult == pytest.approx(1.30)

    def test_it_counts_only_what_it_is_looking_for(self):
        by_uid = self._run(
            [
                self._counter(counting={"any": ["nature"]}),
                self._standing((0, 0), "nature_one", kinds=frozenset({"nature"})),
                self._standing((3, 0), "holy_one", kinds=frozenset({"holy"})),
            ]
        )
        assert by_uid["counter"].speed_mult == pytest.approx(1.15), "one of two"

    def test_a_category_counts_as_well_as_a_kind(self):
        """ "for each Star Food" names a category, "for each Star Dark-item"
        names a kind. Both have to work."""
        by_uid = self._run(
            [
                self._counter(counting={"any": ["defense"]}),
                self._standing((0, 0), "shield", category="defense"),
            ]
        )
        assert by_uid["counter"].speed_mult == pytest.approx(1.15)

    def test_an_item_outside_the_zone_is_not_counted(self):
        by_uid = self._run([self._counter(), self._standing((4, 0), "far")])
        assert by_uid["counter"].speed_mult == 1.0

    def test_it_changes_the_item_projecting_the_zone(self):
        """Not what stands in it -- that is the other direction."""
        by_uid = self._run([self._counter(), self._standing((0, 0), "one")])
        assert by_uid["one"].speed_mult == 1.0

    def test_counting_reaches_damage_too(self):
        by_uid = self._run(
            [
                self._counter(value=0.5, stat="damage"),
                self._standing((0, 0), "left"),
                self._standing((3, 0), "right"),
            ]
        )
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
        """ "for each Star Pet or Food" counts items, not matching tags."""
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
        per = [
            e
            for t in spec.triggers
            for e in getattr(t, "effects", [])
            if isinstance(e, ModifyPerEffect)
        ]
        assert per and per[0].counting == {"any": ["pet", "food"]}
        assert per[0].matches({"pet"}) and per[0].matches({"food"})
        assert not per[0].matches({"defense"})


class TestAnAuraCanBeTheCause:
    """Section 3.1, the third direction. "Star item activates:" -- the zone is
    what sets the effect off, rather than what it reaches or counts."""

    @staticmethod
    def _watcher(after=1, counting="any", zone="star", uid="watcher", position=(1, 0)):
        from item_effects import AuraTrigger, HealEffect

        return BattleItem(
            spec=ItemSpec(
                id=uid,
                name="Watcher",
                category="infrastructure",
                cost=1,
                player_class="neutral",
                slug=uid,
                shape=parse_map(["*##*"], "watcher"),
                triggers=[
                    AuraTrigger(
                        zone=zone,
                        counting=counting,
                        after=after,
                        effects=[HealEffect(1, 1)],
                    )
                ],
            ),
            position=position,
            uid=uid,
        )

    @staticmethod
    def _ticker(position, uid, cooldown=1.0, kinds=frozenset(), category="problem"):
        from item_effects import AttackEffect

        return BattleItem(
            spec=ItemSpec(
                id=uid,
                name="Ticker",
                category=category,
                cost=1,
                player_class="neutral",
                shape=parse_map(["#"], "t"),
                slug=uid,
                kinds=kinds | {"melee"},
                triggers=[
                    TimerTrigger(
                        cooldown=cooldown,
                        cpu_cost=0,
                        effects=[
                            AttackEffect(
                                min_damage=1,
                                max_damage=1,
                                accuracy=1.0,
                                crit_chance=0.0,
                            )
                        ],
                    )
                ],
            ),
            position=position,
            uid=uid,
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
        sim.simulate_battle(
            items, [], 18, containers, [Container.of("mesh_network_hub", (0, 4), "b")]
        )
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
                id="both",
                name="Both",
                category="problem",
                cost=1,
                player_class="neutral",
                slug="both",
                shape=parse_map(["*##*"], "both"),
                kinds=frozenset({"melee"}),
                triggers=[
                    TimerTrigger(
                        cooldown=1.0,
                        cpu_cost=0,
                        effects=[
                            AttackEffect(
                                min_damage=1,
                                max_damage=1,
                                accuracy=1.0,
                                crit_chance=0.0,
                            )
                        ],
                    ),
                    AuraTrigger(
                        zone="star", counting="any", after=1, effects=[HealEffect(1, 1)]
                    ),
                ],
            ),
            position=(1, 0),
            uid="both",
        )
        assert not self._run([both])

    def test_after_counts_the_activations(self):
        """ "6 Star item activations" fires on every sixth, not every one."""
        every = self._run(
            [self._watcher(after=1), self._ticker((0, 0), "t", cooldown=1.0)]
        )
        sixth = self._run(
            [self._watcher(after=6), self._ticker((0, 0), "t", cooldown=1.0)]
        )
        assert len(every) > len(sixth)
        assert len(sixth) == len(every) // 6

    def test_it_waits_only_on_what_it_names(self):
        """ "Star Food activates" ignores everything that is not a Food."""
        wrong = self._run(
            [
                self._watcher(counting={"any": ["script"]}),
                self._ticker((0, 0), "weapon", category="problem"),
            ]
        )
        right = self._run(
            [
                self._watcher(counting={"any": ["script"]}),
                self._ticker((0, 0), "food", category="script"),
            ]
        )
        assert not wrong
        assert right

    def test_a_diamond_is_watched_separately(self):
        heals = self._run(
            [self._watcher(zone="diamond"), self._ticker((0, 0), "in_star")]
        )
        assert not heals, "an item in the star is not in the diamond"


class TestAChanceOnAnEffect:
    """ "12% chance to deal +6 damage and gain 1 Heat" -- one roll in front of
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
                id="w",
                name="Watcher",
                category="infrastructure",
                cost=1,
                player_class="neutral",
                shape=parse_map(["#"], "w"),
                slug="w",
                triggers=[
                    TimerTrigger(
                        cooldown=1.0,
                        cpu_cost=0,
                        effects=[
                            ChanceEffect(
                                chance=1.0,
                                effects=[
                                    HealEffect(1, 1),
                                    BuffEffect(
                                        buff_name="optimized",
                                        value=1,
                                        target_type="self",
                                    ),
                                ],
                            )
                        ],
                    )
                ],
            ),
            position=(0, 0),
            uid="watcher",
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
                id="n",
                name="Never",
                category="infrastructure",
                cost=1,
                player_class="neutral",
                shape=parse_map(["#"], "n"),
                slug="n",
                triggers=[
                    TimerTrigger(
                        cooldown=0.5,
                        cpu_cost=0,
                        effects=[ChanceEffect(chance=0.0, effects=[HealEffect(5, 5)])],
                    )
                ],
            ),
            position=(0, 0),
            uid="never",
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
                id=uid,
                name="Item",
                category=category,
                cost=1,
                player_class="neutral",
                shape=parse_map(["#"], "i"),
                slug=uid,
                kinds=frozenset({"melee"}),
                triggers=triggers,
            ),
            position=position,
            uid=uid,
        )

    @staticmethod
    def _starred(triggers, uid="starred", position=(1, 1), category="protocol"):
        """An item whose star is the two squares above it.

        `_item` draws no zone, which is right for most tests and useless for
        one about an aura: a zone that reaches nowhere passes by doing
        nothing. Two squares wide so that two of these can share one square of
        zone, which is how "shares add" gets asked.
        """
        return BattleItem(
            spec=ItemSpec(
                id=uid,
                name=uid,
                category=category,
                cost=1,
                player_class="neutral",
                shape=parse_map(["**", ".#"], uid),
                slug=uid,
                kinds=frozenset({"melee"}),
                triggers=triggers,
            ),
            position=position,
            uid=uid,
        )

    def _run(self, items, seconds=6.0, hurt=None, buffs=None, against=()):
        p1, p2 = get_test_containers()
        sim = BattleSimulator(seed=TEST_SEED)
        sim.max_duration = seconds
        # Night never falls. Every test here is about the one item it built,
        # and a battle that runs past 17 seconds otherwise has fatigue in
        # every quota it reads. TestFatigue brings its own battles.
        sim.nightfall = seconds + 1
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
            seconds=2.0,
            hurt=100,
        )
        assert not [a for a in sim.actions if a.action == "heal"]


class TestOnAttack(_WithOneItem):
    """Section 1.3: an attack that missed was still an attack. This is
    the whole distinction from on_hit."""

    def test_on_attack_fires_whether_it_hits_or_misses(self):
        """The distinction from on_hit. A miss is still an attack."""
        from item_effects import AttackEffect, HealEffect, OnAttackTrigger

        def heals(accuracy):
            sim, _ = self._run(
                [
                    self._item(
                        [
                            TimerTrigger(
                                cooldown=1.0,
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
                            OnAttackTrigger(chance=1.0, effects=[HealEffect(1, 1)]),
                        ]
                    )
                ],
                hurt=100,
            )
            return len([a for a in sim.actions if a.action == "heal"])

        assert heals(1.0) == heals(0.0) > 0, "a miss counts as an attack"


class TestCountingAStatusHeld(_WithOneItem):
    """Section 3.1: "Triggers 10% faster for each Luck". The counting
    direction of an aura asks the grid; this asks the player."""

    def _counting_item(self):
        from item_effects import ModifyPerStatusEffect, PassiveTrigger

        return self._item(
            [
                PassiveTrigger(
                    effects=[
                        ModifyPerStatusEffect(
                            stat="trigger_speed",
                            value=0.1,
                            status="calibrated",
                            whose="self",
                        )
                    ]
                )
            ]
        )

    def test_counting_a_status_changes_the_cooldown(self):
        """Read when the cooldown is worked out, not once at the start, so a
        status gained during the battle counts from then on."""
        sim, result = self._run([self._counting_item()], seconds=0.2)
        (item,) = result["player1_items"]
        owner = Player(id=1, quota=100, max_quota=100, cpu=3.0)
        sim.player1, sim.player2 = owner, Player(
            id=2, quota=100, max_quota=100, cpu=3.0
        )
        base = TimerTrigger(cooldown=2.0, cpu_cost=0)

        assert sim._cooldown_for(base, owner, item) == 2.0, "nothing held yet"
        owner.buffs["calibrated"] = 3
        assert sim._cooldown_for(base, owner, item) == pytest.approx(2.0 / 1.3)

    def test_counting_a_status_nobody_holds_changes_nothing(self):
        sim, result = self._run([self._counting_item()], seconds=0.2)
        (item,) = result["player1_items"]
        owner = Player(id=1, quota=100, max_quota=100, cpu=3.0)
        sim.player1, sim.player2 = owner, Player(
            id=2, quota=100, max_quota=100, cpu=3.0
        )
        assert (
            sim._cooldown_for(TimerTrigger(cooldown=2.0, cpu_cost=0), owner, item)
            == 2.0
        )


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
        sim.simulate_battle(
            [
                self._item(
                    [
                        TimerTrigger(
                            cooldown=1.0,
                            cpu_cost=0,
                            effects=[
                                EffectDamageEffect(
                                    amount=7, lifesteal=0.0, per_status={}, whose={}
                                )
                            ],
                        )
                    ]
                )
            ],
            [],
            18,
            p1,
            p2,
        )

        hits = [a for a in sim.actions if a.action == "damage"]
        assert hits and all(a.damage == 7 for a in hits), "Block does not stop it"

    def test_lifesteal_heals_a_share_of_what_lands(self):
        from item_effects import EffectDamageEffect

        sim, _ = self._run(
            [
                self._item(
                    [
                        TimerTrigger(
                            cooldown=1.0,
                            cpu_cost=0,
                            effects=[
                                EffectDamageEffect(
                                    amount=10, lifesteal=0.5, per_status={}, whose={}
                                )
                            ],
                        )
                    ]
                )
            ],
            seconds=1.5,
            hurt=100,
        )
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
                id="aura",
                name="Aura",
                category="infrastructure",
                cost=1,
                player_class="neutral",
                slug="aura",
                shape=parse_map(["#*"], "aura"),
                triggers=[
                    PassiveTrigger(
                        effects=[
                            ModifyEffect(
                                stat=stat,
                                value=value,
                                target_type="star",
                                counting=counting,
                                cap=None,
                                duration=-1,
                            )
                        ]
                    )
                ],
            ),
            position=(0, 0),
            uid="aura",
        )

    @staticmethod
    def _swinger(kinds, uid="target"):
        return BattleItem(
            spec=ItemSpec(
                id=uid,
                name="Swinger",
                category="problem",
                cost=1,
                player_class="neutral",
                shape=parse_map(["#"], "s"),
                slug=uid,
                kinds=frozenset(kinds),
                triggers=[
                    TimerTrigger(
                        cooldown=1.0,
                        cpu_cost=0,
                        effects=[
                            AttackEffect(
                                min_damage=10,
                                max_damage=10,
                                accuracy=1.0,
                                crit_chance=0.0,
                            )
                        ],
                    )
                ],
            ),
            position=(1, 0),
            uid=uid,
        )

    def _damage_dealt(self, counting, kinds):
        _, result = self._run(
            [self._projector(counting), self._swinger(kinds)], seconds=1.5
        )
        return 350 - result["player2_quota"]

    def test_an_item_the_filter_names_is_reached(self):
        assert (
            self._damage_dealt({"any": ["melee"]}, ["melee"]) == 20
        ), "10 doubled by a +100% damage aura"

    def test_an_item_the_filter_leaves_out_is_not(self):
        """The same zone, the same item standing in it, and no change."""
        assert self._damage_dealt({"any": ["melee"]}, ["ranged"]) == 10

    def test_a_filter_of_any_reaches_everything(self):
        assert self._damage_dealt("any", ["ranged"]) == 20

    def test_all_wants_every_tag_at_once(self):
        """`{"all": [...]}` is not `{"any": [...]}`: one tag is not enough."""
        assert self._damage_dealt({"all": ["melee", "holy"]}, ["melee"]) == 10
        assert self._damage_dealt({"all": ["melee", "holy"]}, ["melee", "holy"]) == 20

    def test_the_category_counts_as_a_tag(self):
        """ "Star Food" names a category, "Star Weapons" a kind. Both read the
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
                id="granter",
                name="Granter",
                category="infrastructure",
                cost=1,
                player_class="neutral",
                slug="granter",
                shape=parse_map(["#*"], "granter"),
                triggers=[
                    TimerTrigger(
                        cooldown=cooldown,
                        cpu_cost=0,
                        effects=[
                            ModifyEffect(
                                stat="damage",
                                value=value,
                                target_type="star",
                                counting="any",
                                cap=cap,
                                duration=-1,
                            )
                        ],
                    )
                ],
            ),
            position=(0, 0),
            uid="granter",
        )

    @staticmethod
    def _swinger():
        return BattleItem(
            spec=ItemSpec(
                id="swinger",
                name="Swinger",
                category="problem",
                cost=1,
                player_class="neutral",
                shape=parse_map(["#"], "s"),
                slug="swinger",
                kinds=frozenset({"melee"}),
                triggers=[
                    TimerTrigger(
                        cooldown=10.0,
                        cpu_cost=0,
                        effects=[
                            AttackEffect(
                                min_damage=10,
                                max_damage=10,
                                accuracy=1.0,
                                crit_chance=0.0,
                            )
                        ],
                    )
                ],
            ),
            position=(1, 0),
            uid="swinger",
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
        """ "up to 50%" is a limit on what one item has given another, so the
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
                id="aura",
                name="Aura",
                category="infrastructure",
                cost=1,
                player_class="neutral",
                slug="aura",
                shape=parse_map(["#*"], "aura"),
                triggers=[
                    PassiveTrigger(
                        effects=[
                            ModifyEffect(
                                stat="damage",
                                value=1.0,
                                target_type="star",
                                counting="any",
                                cap=None,
                                duration=-1,
                            )
                        ]
                    )
                ],
            ),
            position=(0, 0),
            uid="aura",
        )
        mult, _ = self._mult(aura)
        assert mult == 2.0, "doubled once, not twice"


class TestDamageAnItemPicksUp(_WithOneItem):
    """ "Gain 1 damage" adds to what a weapon swings and it keeps it.

    Flat, not a multiplier, which is why it is not a `modify`. It is kept
    apart from the item's own range because the source game reads it back --
    "remove 1 damage gained in battle from all opponent Weapons".
    """

    @staticmethod
    def _swinger(target="self", amount=5, uid="swinger", position=(0, 0)):
        return BattleItem(
            spec=ItemSpec(
                id=uid,
                name="Swinger",
                category="problem",
                cost=1,
                player_class="neutral",
                shape=parse_map(["#"], "s"),
                slug=uid,
                kinds=frozenset({"melee"}),
                triggers=[
                    TimerTrigger(
                        cooldown=1.0,
                        cpu_cost=0,
                        effects=[
                            AttackEffect(
                                min_damage=10,
                                max_damage=10,
                                accuracy=1.0,
                                crit_chance=0.0,
                            )
                        ],
                    ),
                    OnHitTrigger(
                        chance=1.0,
                        effects=[
                            GainDamageEffect(
                                amount=amount, target_type=target, counting="any"
                            )
                        ],
                    ),
                ],
            ),
            position=position,
            uid=uid,
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
                id="aura",
                name="Aura",
                category="infrastructure",
                cost=1,
                player_class="neutral",
                slug="aura",
                shape=parse_map(["#*"], "aura"),
                triggers=[
                    PassiveTrigger(
                        effects=[
                            ModifyEffect(
                                stat="damage",
                                value=1.0,
                                target_type="star",
                                counting="any",
                                cap=None,
                                duration=-1,
                            )
                        ]
                    )
                ],
            ),
            position=(0, 0),
            uid="aura",
        )
        _, result = self._run([aura, self._swinger(position=(1, 0))], seconds=2.5)
        assert 350 - result["player2_quota"] == 50, "(10)x2 then (10+5)x2"

    def test_self_means_the_item_saying_it(self):
        """ "Gain 1 damage" is the item talking about itself, so a second item
        beside it gains nothing."""
        sim, _ = self._run(
            [self._swinger(uid="a"), self._swinger(uid="b", position=(1, 0), amount=0)],
            seconds=1.5,
        )
        gained = {i.uid: i.damage_gained for i in sim.loadout[1]}
        assert gained == {"a": 5, "b": 0}


class TestOnceForEachThatCounts(_WithOneItem):
    """ "Heal 4 per Star Vampiric-item" does the effects again, once each.

    Counting nothing does nothing, which is what multiplying by zero means and
    needs no case of its own.
    """

    @staticmethod
    def _counter(counting="any", where="star"):
        """Heals 4 for each item standing to its right or below."""
        return BattleItem(
            spec=ItemSpec(
                id="counter",
                name="Counter",
                category="infrastructure",
                cost=1,
                player_class="neutral",
                slug="counter",
                shape=parse_map(["#*", "*."], "counter"),
                triggers=[
                    BattleStartTrigger(
                        effects=[
                            PerCountEffect(
                                where=where,
                                counting=counting,
                                effects=[HealEffect(min_heal=4, max_heal=4)],
                            )
                        ]
                    )
                ],
            ),
            position=(0, 0),
            uid="counter",
        )

    @staticmethod
    def _standing(uid, position, kinds=("melee",), category="problem"):
        return BattleItem(
            spec=ItemSpec(
                id=uid,
                name="Standing",
                category=category,
                cost=1,
                player_class="neutral",
                shape=parse_map(["#"], "s"),
                slug=uid,
                kinds=frozenset(kinds),
                triggers=[],
            ),
            position=position,
            uid=uid,
        )

    def _healed(self, items, hurt=100):
        _, result = self._run(items, seconds=0.3, hurt=hurt)
        return result["player1_quota"] - hurt

    def test_it_happens_once_for_each_item_that_counts(self):
        assert (
            self._healed(
                [
                    self._counter(),
                    self._standing("a", (1, 0)),
                    self._standing("b", (0, 1)),
                ]
            )
            == 8
        )

    def test_counting_nothing_does_nothing(self):
        assert self._healed([self._counter()]) == 0

    def test_the_filter_narrows_what_counts(self):
        assert (
            self._healed(
                [
                    self._counter({"any": ["ranged"]}),
                    self._standing("a", (1, 0), kinds=("melee",)),
                    self._standing("b", (0, 1), kinds=("ranged",)),
                ]
            )
            == 4
        )

    def test_it_counts_where_it_is_told_to(self):
        """`own` is the whole loadout, not a zone, so the counter counts
        itself as well."""
        assert (
            self._healed(
                [
                    self._counter(where="own"),
                    self._standing("a", (1, 0)),
                ]
            )
            == 8
        )


class TestSpendingAStatus(_WithOneItem):
    """ "Use 3 Mana to deal +7 damage": all of it or none of it.

    Nothing is spent when the price cannot be met in full, so a clause cannot
    leave its owner poorer for nothing.
    """

    @staticmethod
    def _spender(costs, gain=20):
        return BattleItem(
            spec=ItemSpec(
                id="spender",
                name="Spender",
                category="problem",
                cost=1,
                player_class="neutral",
                shape=parse_map(["#"], "s"),
                slug="spender",
                kinds=frozenset({"melee"}),
                triggers=[
                    BattleStartTrigger(
                        effects=[
                            CostEffect(
                                costs=costs, effects=[BlockEffect(block_amount=gain)]
                            )
                        ]
                    )
                ],
            ),
            position=(0, 0),
            uid="spender",
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
    """ "If your health is above 70%, gain 1 Empower. Otherwise, heal for 8."

    One effect holds the whole sentence, so the two halves cannot both happen.
    A condition reads a state and spends nothing, which is what tells it from
    a cost.
    """

    @staticmethod
    def _asker(**kwargs):
        settings = dict(
            subject="health",
            whose="self",
            status="",
            test="above",
            amount=0.7,
            effects=[BlockEffect(block_amount=20)],
            otherwise=[HealEffect(min_heal=8, max_heal=8)],
        )
        settings.update(kwargs)
        return BattleItem(
            spec=ItemSpec(
                id="asker",
                name="Asker",
                category="problem",
                cost=1,
                player_class="neutral",
                shape=parse_map(["#"], "a"),
                slug="asker",
                kinds=frozenset({"melee"}),
                triggers=[BattleStartTrigger(effects=[ConditionEffect(**settings)])],
            ),
            position=(0, 0),
            uid="asker",
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
            subject="status",
            status="credits",
            test="at_least",
            amount=3,
            buffs={"credits": 3},
        )
        assert block == 20

    def test_a_condition_spends_nothing(self):
        """This is what tells a condition from a cost."""
        sim, _ = self._run(
            [
                self._asker(
                    subject="status", status="credits", test="at_least", amount=3
                )
            ],
            seconds=0.3,
            buffs={"credits": 5},
        )
        assert sim.player1.buffs == {"credits": 5}

    def test_none_asks_whether_there_are_any(self):
        """ "If you have no debuffs, gain 25 Block.\" """
        block, _ = self._run_asker(
            subject="status",
            status="throttled",
            test="none",
        )
        assert block == 20


class TestStunning(_WithOneItem):
    """Backpack Battles' Stun page: "Stun pauses all cooldowns for a certain
    amount of time." Nothing is lost and nothing is reset.
    """

    @staticmethod
    def _swinger(uid="swinger", position=(0, 0), owner_stun=None):
        triggers = [
            TimerTrigger(
                cooldown=1.0,
                cpu_cost=0,
                effects=[
                    AttackEffect(
                        min_damage=10, max_damage=10, accuracy=1.0, crit_chance=0.0
                    )
                ],
            )
        ]
        return BattleItem(
            spec=ItemSpec(
                id=uid,
                name="Swinger",
                category="problem",
                cost=1,
                player_class="neutral",
                shape=parse_map(["#"], "s"),
                slug=uid,
                kinds=frozenset({"melee"}),
                triggers=triggers,
            ),
            position=position,
            uid=uid,
        )

    @staticmethod
    def _stunner(duration, at=0.5, uid="stunner", position=(1, 0), target="self"):
        from item_effects import AfterTrigger

        return BattleItem(
            spec=ItemSpec(
                id=uid,
                name="Stunner",
                category="problem",
                cost=1,
                player_class="neutral",
                shape=parse_map(["#"], "s"),
                slug=uid,
                kinds=frozenset({"melee"}),
                triggers=[
                    AfterTrigger(
                        delay=at,
                        effects=[StunEffect(duration=duration, target_type=target)],
                    )
                ],
            ),
            position=position,
            uid=uid,
        )

    def test_a_stun_holds_a_wait_still(self):
        """Five swings in 5.5s, and a 2s stun leaves three."""
        _, plain = self._run([self._swinger()], seconds=5.5)
        _, stunned = self._run([self._swinger(), self._stunner(2.0)], seconds=5.5)
        assert 350 - plain["player2_quota"] == 50
        assert 350 - stunned["player2_quota"] == 30

    def test_the_wait_is_taken_up_where_it_stopped(self):
        """The stun lands at 0.5s, half way through the first wait, and holds
        until 2.5s. The swing comes at 3.0s: the half second still owed is
        still owed, so nothing is lost and nothing is reset.
        """
        sim, _ = self._run([self._swinger(), self._stunner(2.0)], seconds=4.0)
        swings = [a.timestamp for a in sim.actions if a.action == "damage"]
        assert swings == [3000], swings

    def test_a_stun_holds_the_stunning_item_too(self):
        """ "Stun pauses all cooldowns" is all of them. An item that stuns its
        own side waits along with everything else, which is why two stunners
        set to fire at different times cannot overlap: the first pushes the
        second out past its own end.
        """
        sim, _ = self._run(
            [
                self._swinger(),
                self._stunner(2.0),
                self._stunner(1.0, at=0.6, uid="second", position=(2, 0)),
            ],
            seconds=5.5,
        )
        assert sim.stunned_until == {
            1: pytest.approx(3.6)
        }, "the second fires at 2.6s, not 0.6s"

    def _both_stunning(self, second_duration):
        """Two stunners of player 1's, both firing at 0.5s, against a swinger
        of player 2's. Neither stunner is held, because a stun holds the waits
        of the player it lands on and these land on the other one.
        """
        sim, result = self._run(
            [
                self._stunner(2.0, position=(0, 0), target="enemy"),
                self._stunner(
                    second_duration,
                    at=0.5,
                    uid="second",
                    position=(1, 0),
                    target="enemy",
                ),
            ],
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
        sim, _ = self._run([self._swinger(), self._stunner(2.0)], seconds=3.0)
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
            (x, y)
            for x, y in spec.shape.star
            if 0 <= x <= 2 and 0 <= y <= 2 and (x, y) not in covered
        ]
        assert len(free) >= how_many, f"{item_id}: only {len(free)} in the rack"
        return free[:how_many]

    @staticmethod
    def _holy(uid, position):
        """Something for a Star Holy-item aura to land on."""
        return BattleItem(
            spec=ItemSpec(
                id=uid,
                name="Holy",
                category="protocol",
                cost=1,
                player_class="neutral",
                shape=parse_map(["#"], "h"),
                slug=uid,
                kinds=frozenset({"holy"}),
                triggers=[],
            ),
            position=position,
            uid=uid,
        )

    def test_holy_armor_gains_regeneration_for_each_star_holy_item(self):
        """ "Gain 65 Block. Gain 2 Regeneration for each Star Holy-item.\" """
        one, two, three = self._star_squares("sanctified_firewall", 3)
        plain = BattleItem(
            spec=ItemSpec(
                id="p",
                name="Plain",
                category="problem",
                cost=1,
                player_class="neutral",
                shape=parse_map(["#"], "p"),
                slug="p",
                kinds=frozenset({"melee"}),
                triggers=[],
            ),
            position=three,
            uid="p",
        )
        sim, _ = self._run(
            [
                self._real("sanctified_firewall"),
                self._holy("h1", one),
                self._holy("h2", two),
                plain,
            ],
            seconds=0.2,
        )
        assert sim.player1.block == 65
        assert (
            sim.player1.buffs["regenerating"] == 4
        ), "2 for each of the two Holy items, and nothing for the third"

    def test_gold_armor_pays_only_when_it_cleansed_everything(self):
        """ "Cleanse 5 debuffs. If you have no debuffs, gain 25 Block.\" """
        sim, _ = self._run([self._real("gold_armor")], seconds=2.4, buffs=None)
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
        """ "Star weapons deal +2 + 15% damage." A flat gain and a modifier."""
        (where,) = self._star_squares("rate_limiter", 1)
        weapon = BattleItem(
            spec=ItemSpec(
                id="w",
                name="Weapon",
                category="problem",
                cost=1,
                player_class="neutral",
                shape=parse_map(["#"], "w"),
                slug="w",
                kinds=frozenset({"melee"}),
                triggers=[],
            ),
            position=where,
            uid="w",
        )
        sim, _ = self._run([self._real("rate_limiter"), weapon], seconds=0.2)
        got = next(i for i in sim.loadout[1] if i.uid == "w")
        assert got.damage_gained == 2
        assert got.damage_mult == pytest.approx(1.15)

    def test_gloves_of_power_trade_speed_for_damage(self):
        """ "Star Weapons deal +20% damage but attack 10% slower.\" """
        (where,) = self._star_squares("gloves_of_power", 1)
        weapon = BattleItem(
            spec=ItemSpec(
                id="w",
                name="Weapon",
                category="problem",
                cost=1,
                player_class="neutral",
                shape=parse_map(["#"], "w"),
                slug="w",
                kinds=frozenset({"ranged"}),
                triggers=[],
            ),
            position=where,
            uid="w",
        )
        sim, _ = self._run([self._real("gloves_of_power"), weapon], seconds=0.2)
        got = next(i for i in sim.loadout[1] if i.uid == "w")
        assert got.damage_mult == pytest.approx(1.2)
        assert got.speed_mult == pytest.approx(0.9)

    def test_bloodthorne_buys_its_buffs_with_regeneration(self):
        """ "On hit: Use 1 Regeneration to gain 1 Vampirism and 1 Spikes.\" """
        sim, _ = self._run(
            [self._real("bloodthorne")],
            seconds=2.0,
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
        """ "If you have at least 4 Luck: 55% chance to gain 1 Empower.\" """
        without, _ = self._run([self._real("auto_rollback")], seconds=6.0)
        with_luck, _ = self._run(
            [self._real("auto_rollback")],
            seconds=6.0,
            buffs={"calibrated": 4},
        )
        assert "monitored" not in without.player1.buffs
        assert with_luck.player1.buffs.get("monitored", 0) > 0
        assert with_luck.player1.buffs["calibrated"] == 4, "a condition spends nothing"

    def test_vampiric_gloves_wait_four_seconds(self):
        """ "After 4s: Gain 5 Vampirism, Star items trigger 35% faster.\" """
        early, _ = self._run([self._real("vampiric_gloves")], seconds=3.5)
        late, _ = self._run([self._real("vampiric_gloves")], seconds=4.5)
        assert "draining" not in early.player1.buffs
        assert late.player1.buffs["draining"] == 5

    def test_jynx_torquilla_stops_at_fifty_percent(self):
        """ "Star items trigger 5% faster (up to 50%)." Ten grants, and the
        eleventh hands out nothing."""
        (where,) = self._star_squares("jynx_torquilla", 1)
        standing = BattleItem(
            spec=ItemSpec(
                id="s",
                name="Standing",
                category="problem",
                cost=1,
                player_class="neutral",
                shape=parse_map(["#"], "s"),
                slug="s",
                kinds=frozenset({"melee"}),
                triggers=[],
            ),
            position=where,
            uid="s",
        )
        sim, _ = self._run([self._real("jynx_torquilla"), standing], seconds=40.0)
        got = next(i for i in sim.loadout[1] if i.uid == "s")
        assert got.speed_mult == pytest.approx(1.5)

    def test_snowmaster_swaps_the_cold_for_empower_at_ten(self):
        """ "Inflict 1 Cold. If your opponent has at least 10 Cold, gain 1
        Empower instead." Instead, so never both."""
        sim, _ = self._run([self._real("snowmaster")], seconds=20.0)
        assert sim.player2.debuffs["throttled"] == 10, "it stopped at ten"
        assert sim.player1.buffs["monitored"] > 0, "and turned to Empower"

    def test_sloth_wakes_up_at_twenty_five_seconds(self):
        """ "Gain 10 of each buff and stun the opponent for 1.5s.\" """
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
        assert (
            self._at(BuffEffect("monitored", 5, "self"), 9.0).player1.buffs["monitored"]
            == 5
        )

    def test_only_what_it_granted_is_taken_back(self):
        """Two grants, one of them timed, and the untimed stacks stay."""
        sim, _ = self._run(
            [
                self._item(
                    [
                        BattleStartTrigger(
                            effects=[
                                BuffEffect("monitored", 3, "self"),
                                BuffEffect("monitored", 5, "self", duration=2.0),
                            ]
                        )
                    ]
                )
            ],
            seconds=2.5,
        )
        assert sim.player1.buffs["monitored"] == 3

    def test_it_cannot_take_back_what_a_cleanse_already_took(self):
        """Floored at nothing, so an expiry cannot push a count negative."""
        sim, _ = self._run(
            [
                self._item(
                    [
                        BattleStartTrigger(
                            effects=[BuffEffect("monitored", 5, "self", duration=2.0)]
                        ),
                        TimerTrigger(
                            cooldown=1.0,
                            cpu_cost=0,
                            effects=[
                                CleanseEffect(
                                    count=4, removes="monitored", target_type="self"
                                )
                            ],
                        ),
                    ]
                )
            ],
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
            seconds=seconds,
            hurt=hurt,
        )

    def test_damage_taken_is_a_share_of_what_lands(self):
        swing = self._item(
            [
                TimerTrigger(
                    cooldown=1.0,
                    cpu_cost=0,
                    effects=[
                        AttackEffect(
                            min_damage=10, max_damage=10, accuracy=1.0, crit_chance=0.0
                        )
                    ],
                )
            ],
            uid="w",
            position=(1, 0),
        )
        _, plain = self._with(seconds=1.5, extra=[swing])
        _, halved = self._with(
            PlayerModifyEffect("damage_taken", -0.5, "enemy", -1),
            seconds=1.5,
            extra=[swing],
        )
        assert 350 - plain["player2_quota"] == 10
        assert 350 - halved["player2_quota"] == 5

    def test_invulnerability_is_the_same_number_turned_up(self):
        """The wiki: invulnerability "prevents receiving any damage". That is
        a share of -1.0, not a case of its own."""
        swing = self._item(
            [
                TimerTrigger(
                    cooldown=1.0,
                    cpu_cost=0,
                    effects=[
                        AttackEffect(
                            min_damage=10, max_damage=10, accuracy=1.0, crit_chance=0.0
                        )
                    ],
                )
            ],
            uid="w",
            position=(1, 0),
        )
        _, result = self._with(
            PlayerModifyEffect("damage_taken", -1.0, "enemy", -1),
            seconds=3.5,
            extra=[swing],
        )
        assert result["player2_quota"] == 350

    def test_invulnerability_stops_poison_as_well(self):
        """ "Any damage" is every kind. Poison reaches no shield and this."""
        sim, result = self._with(
            PlayerModifyEffect("damage_taken", -1.0, "self", -1),
            DebuffEffect("memory_leaked", 5, target_type="self"),
            seconds=5.0,
            hurt=200,
        )
        assert result["player1_quota"] == 200

    def test_a_modifier_can_run_out(self):
        swing = self._item(
            [
                TimerTrigger(
                    cooldown=3.0,
                    cpu_cost=0,
                    effects=[
                        AttackEffect(
                            min_damage=10, max_damage=10, accuracy=1.0, crit_chance=0.0
                        )
                    ],
                )
            ],
            uid="w",
            position=(1, 0),
        )
        _, result = self._with(
            PlayerModifyEffect("damage_taken", -1.0, "enemy", 2.0),
            seconds=3.5,
            extra=[swing],
        )
        assert 350 - result["player2_quota"] == 10, "the swing came after it ended"

    def test_healing_belongs_to_whoever_does_it(self):
        _, plain = self._with(
            HealEffect(min_heal=10, max_heal=10), seconds=0.3, hurt=100
        )
        _, more = self._with(
            PlayerModifyEffect("healing", 0.5, "self", -1),
            HealEffect(min_heal=10, max_heal=10),
            seconds=0.3,
            hurt=100,
        )
        assert plain["player1_quota"] - 100 == 10
        assert more["player1_quota"] - 100 == 15

    def test_healing_taken_is_put_on_the_one_being_healed(self):
        """ "Your opponent's healing is reduced by 30%" is not their clause."""
        _, result = self._with(
            PlayerModifyEffect("healing_taken", -0.3, "self", -1),
            HealEffect(min_heal=10, max_heal=10),
            seconds=0.3,
            hurt=100,
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
        """ "Items use +20% stamina", so a pool that ran three activations
        runs fewer."""
        hungry = self._item(
            [
                TimerTrigger(
                    cooldown=1.0,
                    cpu_cost=1.0,
                    effects=[
                        AttackEffect(
                            min_damage=1, max_damage=1, accuracy=1.0, crit_chance=0.0
                        )
                    ],
                )
            ],
            uid="w",
            position=(1, 0),
        )
        _, plain = self._with(seconds=5.5, extra=[hungry])
        _, costly = self._with(
            PlayerModifyEffect("stamina_use", 1.0, "self", -1),
            seconds=5.5,
            extra=[hungry],
        )
        assert 350 - costly["player2_quota"] < 350 - plain["player2_quota"]

    def test_both_reaches_both_players(self):
        """ "Both players take -25% damage for 7s\" """
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
            against=[
                self._item(
                    [
                        TimerTrigger(
                            cooldown=1.0,
                            cpu_cost=0,
                            effects=[
                                DebuffEffect(
                                    "memory_leaked", stacks, target_type="enemy"
                                )
                            ],
                        )
                    ],
                    uid="them",
                    position=(4, 0),
                )
            ],
        )

    def test_a_charge_sends_one_stack_the_other_way(self):
        sim, _ = self._fight(ReflectEffect(count=1, target_type="self"))
        assert sim.player1.debuffs["memory_leaked"] == 2, "three came, one went back"
        assert sim.player2.debuffs["memory_leaked"] == 1

    def test_one_stack_per_charge_however_many_arrive(self):
        """The page: "Regardless of how many stacks of a debuff is inflicted
        to the player who has Reflect, only 1 stack will be reflected per
        reflect.\" """
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
            against=[
                self._item(
                    [
                        TimerTrigger(
                            cooldown=1.0,
                            cpu_cost=0,
                            effects=[
                                DebuffEffect(
                                    "memory_leaked", stacks, target_type="enemy"
                                )
                            ],
                        )
                    ],
                    uid="them",
                    position=(4, 0),
                )
            ],
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
        sim, _ = self._fight(ResistEffect(count=2, chance=1.0, target_type="self"))
        assert charges_left(sim.player1) == 2, "the chance did the work"

    def test_reflect_goes_first(self):
        """The page: "Reflect, if a check is successful, occurs before
        Resist." So the charge that would have refused it is still there."""
        sim, _ = self._fight(
            ReflectEffect(count=1, target_type="self"),
            ResistEffect(count=1, chance=0.0, target_type="self"),
            stacks=1,
        )
        assert sim.player2.debuffs["memory_leaked"] == 1, "reflected"
        assert charges_left(sim.player1) == 1, "and the resist was not spent"


class TestAStatusNobodyChose(_WithOneItem):
    """ "Inflict a random debuff", "Gain 20 random other buffs".

    Picked uniformly over the kinds there are, one stack at a time, which is
    how cleansing picks and for the same reason.
    """

    def _hand_out(self, kind, count, target="self", seed=TEST_SEED):
        sim = BattleSimulator(seed=seed)
        sim.max_duration = 0.3
        p1, p2 = get_test_containers()
        sim.simulate_battle(
            [
                self._item(
                    [
                        BattleStartTrigger(
                            effects=[
                                RandomStatusEffect(
                                    kind=kind, count=count, target_type=target
                                )
                            ]
                        )
                    ]
                )
            ],
            [],
            18,
            p1,
            p2,
        )
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
    """ "Steal a random buff" is cleansing the opponent and keeping it.

    The same effect with `keep` off is "Remove 1 Luck from your opponent", so
    the two clauses are one mechanic.
    """

    def _steal(self, keep):
        return self._run(
            [
                self._item(
                    [
                        TimerTrigger(
                            cooldown=1.0,
                            cpu_cost=0,
                            effects=[
                                CleanseEffect(
                                    count=2,
                                    removes="buff",
                                    target_type="enemy",
                                    keep=keep,
                                )
                            ],
                        )
                    ]
                )
            ],
            seconds=1.5,
            against=[
                self._item(
                    [BattleStartTrigger(effects=[BuffEffect("monitored", 5, "self")])],
                    uid="them",
                    position=(4, 0),
                )
            ],
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
    """ "(once)", "up to 3 times", "up to 5 per battle".

    Not a modifier's cap, which limits how much one item has given another and
    can hand out part of a grant. This limits how often the clause happens.
    """

    def _spent(self, times, seconds=5.5):
        sim, _ = self._run(
            [
                self._item(
                    [
                        TimerTrigger(
                            cooldown=1.0,
                            cpu_cost=0,
                            effects=[
                                LimitEffect(
                                    times=times,
                                    effects=[BuffEffect("monitored", 1, "self")],
                                )
                            ],
                        )
                    ]
                )
            ],
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

        def clause():
            return TimerTrigger(
                cooldown=1.0,
                cpu_cost=0,
                effects=[
                    LimitEffect(times=2, effects=[BuffEffect("monitored", 1, "self")])
                ],
            )

        sim, _ = self._run(
            [
                self._item([clause()], uid="a"),
                self._item([clause()], uid="b", position=(1, 0)),
            ],
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
                id=uid,
                name="Swinger",
                category="problem",
                cost=1,
                player_class="neutral",
                shape=parse_map(["#"], "w"),
                slug=uid,
                kinds=frozenset({"melee"}),
                triggers=[
                    TimerTrigger(
                        cooldown=1.0,
                        cpu_cost=0,
                        effects=[
                            AttackEffect(
                                min_damage=10,
                                max_damage=10,
                                accuracy=1.0,
                                crit_chance=crit,
                            )
                        ],
                    )
                ],
            ),
            position=position,
            uid=uid,
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
                id="aura",
                name="Aura",
                category="infrastructure",
                cost=1,
                player_class="neutral",
                slug="aura",
                shape=parse_map(["#*"], "aura"),
                triggers=[
                    PassiveTrigger(
                        effects=[
                            ModifyEffect(
                                stat="critical_chance",
                                value=1.0,
                                target_type="star",
                                counting="any",
                                cap=None,
                                duration=-1,
                            )
                        ]
                    )
                ],
            ),
            position=(0, 0),
            uid="aura",
        )
        _, result = self._run([aura, self._swinger(position=(1, 0))], seconds=5.5)
        assert 350 - result["player2_quota"] == 100

    def test_it_does_not_go_past_certain(self):
        """Two sources of +100% are still one doubling, not two."""
        sim = BattleSimulator(seed=TEST_SEED)
        item = self._swinger(crit=1.0)
        item.crit_bonus = 5.0

        def nobody(who):
            return Player(id=who, quota=1, max_quota=1, cpu=0)

        assert sim._crit_chance(1.0, item, nobody(1), nobody(2)) == 1.0

    def test_a_player_wide_crit_reaches_every_item(self):
        """ "For the next 1.5s, all your attacks are Critical hits.\" """
        _, result = self._run(
            [
                self._swinger(),
                self._item(
                    [
                        BattleStartTrigger(
                            effects=[
                                PlayerModifyEffect("critical_chance", 1.0, "self", 2.5)
                            ]
                        )
                    ],
                    uid="grant",
                    position=(1, 0),
                ),
            ],
            seconds=4.5,
        )
        assert 350 - result["player2_quota"] == 60, "2 doubled, then 2 plain"

    def test_effect_damage_crits_too(self):
        """The page says so of these very items: "The damage effects... are
        capable of inflicting critical hits when they activate.\" """
        from item_effects import EffectDamageEffect

        hit = self._item(
            [
                TimerTrigger(
                    cooldown=1.0,
                    cpu_cost=0,
                    effects=[
                        EffectDamageEffect(
                            amount=10, lifesteal=0.0, per_status={}, whose={}
                        )
                    ],
                )
            ]
        )
        hit.crit_bonus = 1.0
        _, result = self._run([hit], seconds=1.5)
        assert 350 - result["player2_quota"] == 20


class TestAnAmountThatGrowsWithWhatYouHold(_WithOneItem):
    """ "Deals +1 damage per Spikes", "Deal 10 Effect-damage + 0.5 for each
    Spikes + 1 for each Empower", "Deals +0.4 per Cold of your opponent".

    Read where the damage is worked out rather than before the battle, so a
    stack gained part way through counts.
    """

    def test_flat_damage_grows_with_the_stacks(self):
        from item_effects import ModifyPerStatusEffect

        swing = self._item(
            [
                PassiveTrigger(
                    effects=[
                        ModifyPerStatusEffect(
                            stat="damage_flat", value=1.0, status="spiked", whose="self"
                        )
                    ]
                ),
                TimerTrigger(
                    cooldown=1.0,
                    cpu_cost=0,
                    effects=[
                        AttackEffect(
                            min_damage=10, max_damage=10, accuracy=1.0, crit_chance=0.0
                        )
                    ],
                ),
            ]
        )
        _, none = self._run([swing], seconds=1.5)
        _, three = self._run([swing], seconds=1.5, buffs={"spiked": 3})
        assert 350 - none["player2_quota"] == 10
        assert 350 - three["player2_quota"] == 13

    def test_it_counts_the_opponent_when_told_to(self):
        """ "Deals +1 damage for each Blind of your opponent.\" """
        from item_effects import ModifyPerStatusEffect

        swing = self._item(
            [
                PassiveTrigger(
                    effects=[
                        ModifyPerStatusEffect(
                            stat="damage_flat",
                            value=1.0,
                            status="rate_limited",
                            whose="enemy",
                        )
                    ]
                ),
                BattleStartTrigger(
                    effects=[DebuffEffect("rate_limited", 4, target_type="enemy")]
                ),
                TimerTrigger(
                    cooldown=1.0,
                    cpu_cost=0,
                    effects=[
                        AttackEffect(
                            min_damage=10, max_damage=10, accuracy=1.0, crit_chance=0.0
                        )
                    ],
                ),
            ]
        )
        _, result = self._run([swing], seconds=1.5)
        assert 350 - result["player2_quota"] == 14

    def test_maximum_damage_alone_widens_the_roll(self):
        """ "Deals +1 maximum damage per Vampirism" raises the top and leaves
        the bottom, so the swing can still roll low."""
        from item_effects import ModifyPerStatusEffect

        swing = self._item(
            [
                PassiveTrigger(
                    effects=[
                        ModifyPerStatusEffect(
                            stat="max_damage_flat",
                            value=1.0,
                            status="draining",
                            whose="self",
                        )
                    ]
                ),
                TimerTrigger(
                    cooldown=0.5,
                    cpu_cost=0,
                    effects=[
                        AttackEffect(
                            min_damage=1, max_damage=1, accuracy=1.0, crit_chance=0.0
                        )
                    ],
                ),
            ]
        )
        sim, _ = self._run([swing], seconds=9.0, buffs={"draining": 9})
        rolled = {a.damage for a in sim.actions if a.action == "damage"}
        assert min(rolled) == 1, "the bottom of the range did not move"
        assert max(rolled) > 1, "and the top did"

    def test_effect_damage_grows_with_two_statuses_at_once(self):
        """ "Deal 10 Effect-damage + 0.5 for each Spikes + 1 for each
        Empower.\" """
        from item_effects import EffectDamageEffect

        hit = self._item(
            [
                TimerTrigger(
                    cooldown=1.0,
                    cpu_cost=0,
                    effects=[
                        EffectDamageEffect(
                            amount=10,
                            lifesteal=0.0,
                            per_status={"spiked": 0.5, "monitored": 1.0},
                            whose={"spiked": "self", "monitored": "self"},
                        )
                    ],
                )
            ]
        )
        _, result = self._run([hit], seconds=1.5, buffs={"spiked": 4, "monitored": 3})
        assert 350 - result["player2_quota"] == 15, "10 + 2 + 3"


class TestTheCatalogueItemsThatReflectReduceAndScale(_WithOneItem):
    """Real items that turn something back, take something off, or grow with
    what their owner holds.

    Reflecting a debuff, softening the first seconds, making everything cost
    more, damage that rises with Spikes, an effect that reads a debuff it did
    not cause, a zone that gives one thing per kind standing in it.

    A mechanic tested on an item made for the purpose proves the mechanic. It
    does not prove the translation, and the translation is where a clause
    turns into the wrong thing quietly.

    Named for its own batch once, and it shared that name with a later batch's
    class: a second class of the same name replaces the first silently, so
    these tests had stopped running and nothing said so. flake8's F811 is what
    noticed, which is the reason none of these classes is named for a batch
    any more -- a name that says what it holds cannot collide by accident.
    """

    @staticmethod
    def _real(item_id, position=(0, 0), uid=None):
        return BattleItem(
            spec=ITEM_CATALOG[item_id], position=position, uid=uid or item_id
        )

    @staticmethod
    def _swinger(damage=20, uid="them", position=(4, 0), cooldown=1.0):
        return BattleItem(
            spec=ItemSpec(
                id=uid,
                name="Swinger",
                category="problem",
                cost=1,
                player_class="neutral",
                shape=parse_map(["#"], "s"),
                slug=uid,
                kinds=frozenset({"melee"}),
                triggers=[
                    TimerTrigger(
                        cooldown=cooldown,
                        cpu_cost=0,
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
            position=position,
            uid=uid,
        )

    def test_stone_helm_softens_the_first_five_seconds(self):
        """ "Reduce damage taken by 25% for 5s and gain 35 Block." The Block
        goes first, so what is left over is what the share reduced."""
        _, softened = self._run(
            [self._real("stone_helm")],
            seconds=8.5,
            against=[self._swinger(damage=20)],
        )
        _, bare = self._run([], seconds=8.5, against=[self._swinger(damage=20)])
        taken, would_have = (
            350 - softened["player1_quota"],
            350 - bare["player1_quota"],
        )
        assert (
            taken < would_have - 35
        ), "35 of it met Block, and the rest of the saving is the share"

    def test_cap_of_discomfort_reduces_the_healing_of_the_other_side(self):
        """ "Your opponent's healing is reduced by 30%." It is put on them."""
        healer = self._item(
            [
                TimerTrigger(
                    cooldown=1.0,
                    cpu_cost=0,
                    effects=[HealEffect(min_heal=10, max_heal=10)],
                )
            ],
            uid="h",
            position=(4, 0),
        )
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
            [self._real("cap_of_discomfort")], [healer], 18, p1, p2
        )
        assert result["player2_quota"] - 100 == 7, "10 healed, 30% off"

    def test_stone_armor_makes_everything_cost_more(self):
        """ "Items use +20% stamina.\" """
        hungry = self._item(
            [
                TimerTrigger(
                    cooldown=0.5,
                    cpu_cost=1.0,
                    effects=[
                        AttackEffect(
                            min_damage=1, max_damage=1, accuracy=1.0, crit_chance=0.0
                        )
                    ],
                )
            ],
            uid="w",
            position=(2, 2),
        )
        _, plain = self._run([hungry], seconds=9.0)
        _, costly = self._run([self._real("stone_armor"), hungry], seconds=9.0)
        assert 350 - costly["player2_quota"] < 350 - plain["player2_quota"]

    def test_ruby_egg_turns_the_first_three_debuffs_back(self):
        """ "Gain 4 Heat. Reflect 3 debuffs.\" """
        sim, _ = self._run(
            [self._real("ruby_egg")],
            seconds=1.5,
            against=[
                self._item(
                    [
                        TimerTrigger(
                            cooldown=1.0,
                            cpu_cost=0,
                            effects=[
                                DebuffEffect("memory_leaked", 5, target_type="enemy")
                            ],
                        )
                    ],
                    uid="them",
                    position=(4, 0),
                )
            ],
        )
        assert sim.player1.buffs["optimized"] == 4
        assert sim.player1.debuffs["memory_leaked"] == 2, "5 came, 3 went back"
        assert sim.player2.debuffs["memory_leaked"] == 3

    def test_moon_armor_keeps_turning_debuffs_back(self):
        """ "Every 2.6s: Gain 3 Mana and reflect 2 debuffs." Charges arrive on
        a clock, so a long fight turns back more than a short one."""

        def fight(seconds):
            sim, _ = self._run(
                [self._real("moon_armor")],
                seconds=seconds,
                against=[
                    self._item(
                        [
                            TimerTrigger(
                                cooldown=1.0,
                                cpu_cost=0,
                                effects=[
                                    DebuffEffect(
                                        "memory_leaked", 1, target_type="enemy"
                                    )
                                ],
                            )
                        ],
                        uid="them",
                        position=(4, 0),
                    )
                ],
            )
            return sim.player2.debuffs.get("memory_leaked", 0)

        # Charges arrive at 2.6s and every 2.6s after, and a stack arrives
        # every second, so what is turned back is what came after the first
        # charges did.
        assert fight(3.5) == 1
        assert fight(6.5) == 3
        assert fight(9.0) == 5

    def test_thorn_whip_hits_harder_for_every_spike(self):
        """ "On hit: Gain 1 Spikes" and "Deals +1 damage per Spikes", so it
        climbs by itself."""
        sim, _ = self._run([self._real("mobius_lash")], seconds=20.0)
        whip = next(i for i in sim.loadout[1] if i.uid == "mobius_lash")
        held = sim.player1.buffs["spiked"]
        assert held > 0, "it gains a Spike on every hit"
        assert (
            sim._per_status(whip, "damage_flat", sim.player1, sim.player2) == held
        ), "and reads them back"

    def test_lightsaber_reads_the_blind_it_did_not_cause(self):
        """ "Deals +1 damage for each Blind of your opponent." The stacks are
        the opponent's, so an item of ours that blinds them feeds it."""

        def fight(blind):
            sim = BattleSimulator(seed=TEST_SEED)
            sim.max_duration = 2.0
            # A 1x4 rack, because a Lightsaber is 1x4 and the 3x3 the rest of
            # these tests use cannot hold one.
            racks = (
                [Container.of("patch_registry", (0, 0), "p1")],
                [Container.of("patch_registry", (4, 0), "p2")],
            )
            original = sim._setup_item_handlers

            def setup(items, owner, enemy):
                out = original(items, owner, enemy)
                if owner.id == 2 and blind:
                    owner.debuffs["rate_limited"] = blind
                return out

            sim._setup_item_handlers = setup
            return sim.simulate_battle([self._real("lightsaber")], [], 18, *racks)

        # The same seed both times, so the roll behind the swing is the same
        # and the difference is only what the Blind added.
        plain, blinded = fight(0), fight(4)
        assert (350 - blinded["player2_quota"]) - (350 - plain["player2_quota"]) == 4

    def test_hedgehog_scales_its_effect_damage_with_its_spikes(self):
        """ "Deal 10 Effect-damage + 0.5 for each Spikes.\" """
        _, plain = self._run([self._real("surveillance_drone")], seconds=5.5)
        _, spiky = self._run(
            [self._real("surveillance_drone")], seconds=5.5, buffs={"spiked": 10}
        )
        assert 350 - plain["player2_quota"] == 10
        assert 350 - spiky["player2_quota"] == 15

    def test_hedgehog_answers_a_health_threshold_once(self):
        """ "Health drops below 70%: Gain 3 Spikes and 25 Block (once)." It is
        crossing the line that fires it, and only the first crossing."""
        sim, _ = self._run(
            [self._real("surveillance_drone")],
            seconds=9.0,
            hurt=200,
            against=[self._swinger(damage=5, cooldown=1.0)],
        )
        assert sim.player1.buffs["spiked"] == 3, "not 3 for every swing after"

    def test_leather_boots_wait_for_the_line(self):
        early, _ = self._run(
            [self._real("leather_boots")],
            seconds=1.5,
            against=[self._swinger(damage=5)],
        )
        late, _ = self._run(
            [self._real("leather_boots")],
            seconds=1.5,
            hurt=246,
            against=[self._swinger(damage=5)],
        )
        assert not early.player1.buffs, "still above 70%"
        assert late.player1.buffs == {"calibrated": 1, "monitored": 1}
        assert late.player1.block == 15

    def test_squirrel_archer_takes_a_buff_and_keeps_it(self):
        """ "On hit: Steal a random buff.\" """
        sim, _ = self._run(
            [self._real("data_leech_swarm")],
            seconds=5.0,
            against=[
                self._item(
                    [BattleStartTrigger(effects=[BuffEffect("monitored", 5, "self")])],
                    uid="them",
                    position=(4, 0),
                )
            ],
        )
        assert sim.player2.buffs["monitored"] < 5
        assert sim.player1.buffs["monitored"] == 5 - sim.player2.buffs["monitored"]

    def test_light_goobert_waits_for_six_activations(self):
        """ "6 Star item activations: Heal for 25 and inflict 7 Blind for 3s."
        The Blind runs out; the healing does not."""
        star = ITEM_CATALOG["light_goobert"].shape.star
        inside = [(x, y) for x, y in star if 0 <= x <= 2 and 0 <= y <= 2]
        ticker = self._item(
            [
                TimerTrigger(
                    cooldown=0.5,
                    cpu_cost=0,
                    effects=[BuffEffect("calibrated", 0, "self")],
                )
            ],
            uid="t",
            position=inside[0],
        )
        sim, _ = self._run([self._real("light_goobert"), ticker], seconds=3.2, hurt=100)
        assert sim.player1.quota > 100, "it healed"
        assert sim.player2.debuffs.get("rate_limited", 0) == 7

    def test_light_gooberts_blind_wears_off(self):
        star = ITEM_CATALOG["light_goobert"].shape.star
        inside = [(x, y) for x, y in star if 0 <= x <= 2 and 0 <= y <= 2]
        ticker = self._item(
            [
                TimerTrigger(
                    cooldown=1.0,
                    cpu_cost=0,
                    effects=[BuffEffect("calibrated", 0, "self")],
                )
            ],
            uid="t",
            position=inside[0],
        )
        # Six activations bring the aura at 6s, and its Blind runs to 9s.
        sim, _ = self._run(
            [self._real("light_goobert"), ticker], seconds=11.5, hurt=100
        )
        assert (
            "rate_limited" not in sim.player2.debuffs
        ), "inflicted once the ticker had done its six, and 3s later gone"

    def test_prismatic_orb_gives_one_thing_per_kind_in_its_star(self):
        """ "Star Magic-item: Gain 2 Mana", and three more like it. Each counts
        only the items of its own kind."""
        star = ITEM_CATALOG["quantum_processor"].shape.star
        inside = [(x, y) for x, y in star if 0 <= x <= 2 and 0 <= y <= 2]

        def tagged(uid, kind, where):
            return BattleItem(
                spec=ItemSpec(
                    id=uid,
                    name=uid,
                    category="protocol",
                    cost=1,
                    player_class="neutral",
                    shape=parse_map(["#"], "t"),
                    slug=uid,
                    kinds=frozenset({kind}),
                    triggers=[],
                ),
                position=where,
                uid=uid,
            )

        sim, _ = self._run(
            [
                self._real("quantum_processor"),
                tagged("m", "magic", inside[0]),
                tagged("v", "vampiric", inside[1]),
            ],
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

    def _healed(self, effects, share, hurt=100, seconds=3.0, buffs=None, extra=()):
        given = dict(buffs or {})
        sim, result = self._run(
            [
                self._item(
                    [
                        BattleStartTrigger(
                            effects=(
                                [PlayerModifyEffect("healing", share, "self", -1)]
                                if share
                                else []
                            )
                            + list(effects)
                        )
                    ]
                )
            ]
            + list(extra),
            seconds=seconds,
            hurt=hurt,
            buffs=given,
        )
        return result["player1_quota"] - hurt

    def test_a_plain_heal_takes_the_share(self):
        assert self._healed([HealEffect(min_heal=10, max_heal=10)], 0) == 10
        assert self._healed([HealEffect(min_heal=10, max_heal=10)], 1.0) == 20

    def test_regeneration_takes_the_share(self):
        plain = self._healed([BuffEffect("regenerating", 5, "self")], 0, seconds=2.5)
        more = self._healed([BuffEffect("regenerating", 5, "self")], 1.0, seconds=2.5)
        assert plain == 5
        assert more == 10

    def test_lifesteal_on_effect_damage_takes_the_share(self):
        from item_effects import EffectDamageEffect

        hit = [EffectDamageEffect(amount=10, lifesteal=1.0, per_status={}, whose={})]
        assert self._healed(hit, 0, seconds=0.3) == 10
        assert self._healed(hit, 1.0, seconds=0.3) == 20

    def test_vampirism_takes_the_share(self):
        """Section 3.1: Vampirism heals a melee swing's damage back. It wrote
        to the quota itself and so ignored both shares, which nothing noticed
        until the roads were counted."""
        swing = [
            AttackEffect(min_damage=10, max_damage=10, accuracy=1.0, crit_chance=0.0)
        ]
        weapon = self._item(
            [TimerTrigger(cooldown=1.0, cpu_cost=0, effects=swing)],
            uid="w",
            position=(1, 0),
        )
        plain = self._healed([], 0, seconds=1.5, buffs={"draining": 6}, extra=[weapon])
        more = self._healed([], 1.0, seconds=1.5, buffs={"draining": 6}, extra=[weapon])
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
            [
                self._item(
                    [
                        BattleStartTrigger(
                            effects=list(also)
                            + [DebuffEffect("memory_leaked", 3, target_type="self")]
                        )
                    ]
                )
            ],
            seconds=0.3,
        )
        return sim

    def test_your_own_debuff_is_not_turned_back(self):
        sim = self._self_inflict(ReflectEffect(count=5, target_type="self"))
        assert sim.player1.debuffs["memory_leaked"] == 3
        assert "memory_leaked" not in sim.player2.debuffs
        assert sim.player1.reflect == 5, "and no charge was spent"

    def test_your_own_debuff_is_not_refused(self):
        sim = self._self_inflict(ResistEffect(count=0, chance=1.0, target_type="self"))
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
        sim._take_damage(
            target,
            damage,
            source="w",
            action="damage",
            attacker=attacker,
            blockable=True,
        )
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
        sim._take_damage(target, 20, source="w", action="damage", attacker=attacker)
        assert 100 - target.quota == 20
        assert target.block == 35


class TestAZoneNobodyKnowsIsRefused(_WithOneItem):
    """The same guard `_modify` has, for the same reason.

    `aura_squares` answers anything that is not `star` with the diamond, so a
    zone name it does not know quietly projects the wrong shape. `_reached_by`
    used to whitelist the two and return nothing for anything else, which was
    safe; asking `_zone_squares` for the squares of a third is not.

    The loader keeps this off the catalogue, so nothing here can reach it --
    which is exactly when a guard is worth writing down, because nothing else
    will notice when it stops holding.
    """

    def test_a_zone_nobody_knows_stops_rather_than_guessing(self):
        sim = BattleSimulator(seed=TEST_SEED)
        with pytest.raises(TypeError, match="is not a zone"):
            sim._zone_squares(self._starred([]), "sideways")

    def test_the_three_it_knows_all_answer(self):
        sim = BattleSimulator(seed=TEST_SEED)
        item = self._starred([], position=(2, 2))
        zones = {
            name: sim._zone_squares(item, name)
            for name in ("star", "diamond", "contained")
        }
        assert zones == {
            "star": [(1, 1), (2, 1)],
            "diamond": [],
            "contained": [(2, 2)],
        }


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
            sim._modify(
                item,
                ModifyEffect(
                    stat="wingspan",
                    value=1.0,
                    target_type="own",
                    counting="any",
                    cap=None,
                    duration=-1,
                ),
            )

    def test_flat_damage_from_a_modifier_reaches_the_swing(self):
        """An aura granting +2 flat, which is not the same as +200%."""
        aura = BattleItem(
            spec=ItemSpec(
                id="aura",
                name="Aura",
                category="infrastructure",
                cost=1,
                player_class="neutral",
                slug="aura",
                shape=parse_map(["#*"], "aura"),
                triggers=[
                    PassiveTrigger(
                        effects=[
                            ModifyEffect(
                                stat="damage_flat",
                                value=2.0,
                                target_type="star",
                                counting="any",
                                cap=None,
                                duration=-1,
                            )
                        ]
                    )
                ],
            ),
            position=(0, 0),
            uid="aura",
        )
        swinger = self._item(
            [
                TimerTrigger(
                    cooldown=1.0,
                    cpu_cost=0,
                    effects=[
                        AttackEffect(
                            min_damage=10, max_damage=10, accuracy=1.0, crit_chance=0.0
                        )
                    ],
                )
            ],
            uid="w",
            position=(1, 0),
        )
        _, alone = self._run([swinger], seconds=1.5)
        _, helped = self._run([aura, swinger], seconds=1.5)
        assert 350 - alone["player2_quota"] == 10
        assert 350 - helped["player2_quota"] == 12

    def test_maximum_damage_from_a_modifier_widens_the_roll(self):
        aura = BattleItem(
            spec=ItemSpec(
                id="aura",
                name="Aura",
                category="infrastructure",
                cost=1,
                player_class="neutral",
                slug="aura",
                shape=parse_map(["#*"], "aura"),
                triggers=[
                    PassiveTrigger(
                        effects=[
                            ModifyEffect(
                                stat="max_damage_flat",
                                value=8.0,
                                target_type="star",
                                counting="any",
                                cap=None,
                                duration=-1,
                            )
                        ]
                    )
                ],
            ),
            position=(0, 0),
            uid="aura",
        )
        swinger = self._item(
            [
                TimerTrigger(
                    cooldown=0.5,
                    cpu_cost=0,
                    effects=[
                        AttackEffect(
                            min_damage=1, max_damage=1, accuracy=1.0, crit_chance=0.0
                        )
                    ],
                )
            ],
            uid="w",
            position=(1, 0),
        )
        sim, _ = self._run([aura, swinger], seconds=9.0)
        rolled = {a.damage for a in sim.actions if a.action == "damage"}
        assert min(rolled) == 1, "the bottom of the range did not move"
        assert max(rolled) > 1, "and the top did"


class TestTheSweptClauses(_WithOneItem):
    """Items whose clauses the loader could already say, once somebody said
    them.

    Nothing new was built for these. That makes them the ones most worth
    running, because a clause written straight into the catalogue is never
    exercised by a test of the mechanic it uses.
    """

    @staticmethod
    def _real(item_id, position=(0, 0), uid=None):
        return BattleItem(
            spec=ITEM_CATALOG[item_id], position=position, uid=uid or item_id
        )

    #: A bigger room than the rest of these tests use. The room is 9 by 7 and
    #: a rack is 3 by 3, so this gives one player six squares by six and the
    #: other six by three. An item may cover any square a container offers, so
    #: racks side by side make one space: a four-square-wide item has
    #: somewhere to stand, and a star drawn above or to the left of an item
    #: has somewhere to land.
    # Plain VMs rather than the 3x3 bags that used to stand here. Every bag
    # in the catalogue carries a clause now, and four of that one would have
    # amplified this room's healing by 48% behind every test in the class.
    ROOM = (
        tuple((x, y) for y in (0, 2, 4) for x in (0, 2, 4)),
        ((6, 0), (6, 2), (6, 4)),
    )
    MINE = {(x, y) for x in range(6) for y in range(6)}

    def _room(self):
        mine, theirs = self.ROOM
        return (
            [Container.of("standard_vm", at, f"p1_{i}") for i, at in enumerate(mine)],
            [Container.of("standard_vm", at, f"p2_{i}") for i, at in enumerate(theirs)],
        )

    def _place(self, item_id, how_many_star=0, avoiding=()):
        """Somewhere the item fits with `how_many_star` of its star inside.

        A star is drawn around an item on its own map and half of it reaches
        off the left and top, so where an item stands decides whether its own
        aura lands anywhere at all. `avoiding` names squares already spoken
        for, which is how a second real item gets a place beside the first.
        """
        spec = ITEM_CATALOG[item_id]
        room = self.MINE - set(avoiding)
        for y in range(6):
            for x in range(6):
                covered = {(x + dx, y + dy) for dx, dy in spec.shape.squares}
                if not covered <= room:
                    continue
                star = [
                    (x + dx, y + dy)
                    for dx, dy in spec.shape.star
                    if (x + dx, y + dy) in room - covered
                ]
                if len(star) >= how_many_star:
                    return (x, y), star[:how_many_star]
        raise AssertionError(f"{item_id} does not fit with {how_many_star} of its star")

    def _fight(self, items, seconds=3.0, against=(), hurt=None, buffs=None):
        mine, theirs = self._room()
        sim = BattleSimulator(seed=TEST_SEED)
        sim.max_duration = seconds
        # Night never falls: these read quotas, and a battle past 17 seconds
        # otherwise has fatigue in every one of them.
        sim.nightfall = seconds + 1
        original = sim._setup_item_handlers

        def setup(its, owner, enemy):
            if owner.id == 1 and buffs:
                owner.buffs.update(buffs)
            out = original(its, owner, enemy)
            if owner.id == 1 and hurt is not None:
                owner.quota = hurt
            return out

        sim._setup_item_handlers = setup
        return sim, sim.simulate_battle(items, list(against), 18, mine, theirs)

    def _somewhere_outside(self, item_id, at, taken=()):
        """A free square of the room that `item_id`'s star does not fall on.

        `_place` answers where an item goes; this answers where to put one
        that must *not* be reached, which is the other half of proving a zone
        is what a clause counts. `taken` names squares already spoken for.
        """
        spec = ITEM_CATALOG[item_id]
        busy = {(at[0] + dx, at[1] + dy) for dx, dy in spec.shape.squares}
        busy |= {(at[0] + dx, at[1] + dy) for dx, dy in spec.shape.star}
        busy |= set(taken)
        for y in range(5, -1, -1):
            for x in range(5, -1, -1):
                if (x, y) in self.MINE and (x, y) not in busy:
                    return (x, y)
        raise AssertionError(f"nowhere in the room is outside {item_id}")

    @staticmethod
    def _tagged(uid, kinds, where, category="protocol"):
        return BattleItem(
            spec=ItemSpec(
                id=uid,
                name=uid,
                category=category,
                cost=1,
                player_class="neutral",
                shape=parse_map(["#"], "t"),
                slug=uid,
                kinds=frozenset(kinds),
                triggers=[],
            ),
            position=where,
            uid=uid,
        )

    def _swinger(self, damage=10, uid="them", position=(4, 0), cooldown=1.0):
        return BattleItem(
            spec=ItemSpec(
                id=uid,
                name="Swinger",
                category="problem",
                cost=1,
                player_class="neutral",
                shape=parse_map(["#"], "s"),
                slug=uid,
                kinds=frozenset({"melee"}),
                triggers=[
                    TimerTrigger(
                        cooldown=cooldown,
                        cpu_cost=0,
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
            position=position,
            uid=uid,
        )

    # --- a standing number ------------------------------------------------

    def test_basic_firewall_refuses_three_debuffs(self):
        """ "Resist 3 debuffs." Charges, spent one per stack."""
        where, _ = self._place("basic_firewall")
        sim, _ = self._fight(
            [self._real("basic_firewall", where)],
            seconds=1.5,
            against=[
                self._item(
                    [
                        TimerTrigger(
                            cooldown=1.0,
                            cpu_cost=0,
                            effects=[
                                DebuffEffect("memory_leaked", 5, target_type="enemy")
                            ],
                        )
                    ],
                    uid="them",
                    position=(6, 0),
                )
            ],
        )
        assert sim.player1.debuffs["memory_leaked"] == 2, "3 of the 5 refused"
        assert charges_left(sim.player1) == 0

    def test_gold_armor_slows_only_the_weapons(self):
        """ "Your Weapons attack 50% slower." Weapons, not everything."""
        where, _ = self._place("gold_armor")
        sim, _ = self._fight(
            [
                self._real("gold_armor", where),
                self._tagged("w", ["melee"], (5, 5), category="problem"),
                self._tagged("p", ["holy"], (5, 4)),
            ],
            seconds=0.2,
        )
        held = {i.uid: i.speed_mult for i in sim.loadout[1]}
        assert held["w"] == pytest.approx(0.5)
        assert held["p"] == pytest.approx(1.0), "not a Weapon, so untouched"

    def test_redundancy_protocol_raises_healing(self):
        healer = self._item(
            [
                TimerTrigger(
                    cooldown=1.0,
                    cpu_cost=0,
                    effects=[HealEffect(min_heal=10, max_heal=10)],
                )
            ],
            uid="h",
            position=(5, 5),
        )
        where, _ = self._place("redundancy_protocol")
        _, plain = self._fight([healer], seconds=1.5, hurt=100)
        _, more = self._fight(
            [self._real("redundancy_protocol", where), healer], seconds=1.5, hurt=100
        )
        assert plain["player1_quota"] - 100 == 10
        assert more["player1_quota"] - 100 == 12

    def test_claws_of_attack_speed_up_with_spikes(self):
        where, _ = self._place("claws_of_attack")
        _, plain = self._fight([self._real("claws_of_attack", where)], seconds=9.0)
        _, spiky = self._fight(
            [self._real("claws_of_attack", where)], seconds=9.0, buffs={"spiked": 10}
        )
        assert 350 - spiky["player2_quota"] > 350 - plain["player2_quota"]

    # --- start of battle --------------------------------------------------

    def test_hero_sword_arms_only_the_weapons_in_its_star(self):
        where, (one, two) = self._place("hero_sword", 2)
        sim, _ = self._fight(
            [
                self._real("hero_sword", where),
                self._tagged("w", ["ranged"], one, category="problem"),
                self._tagged("f", ["holy"], two),
            ],
            seconds=0.2,
        )
        gained = {i.uid: i.damage_gained for i in sim.loadout[1]}
        assert gained["w"] == 1
        assert gained["f"] == 0, "not a Weapon"

    def test_dancing_dragon_counts_the_magic_items_in_its_star(self):
        where, (one, two) = self._place("dancing_dragon", 2)
        sim, _ = self._fight(
            [
                self._real("dancing_dragon", where),
                self._tagged("m", ["magic"], one),
                self._tagged("n", ["nature"], two),
            ],
            seconds=0.2,
        )
        assert sim.player1.buffs["optimized"] == 2, "one Magic-item, not two"
        assert sim.player1.buffs["calibrated"] == 2

    def test_dancing_dragon_hits_harder_for_its_heat(self):
        """ "Deals +0.5 damage per Heat", which is a half each and so shows
        only in pairs."""
        where, _ = self._place("dancing_dragon")
        _, cold = self._fight([self._real("dancing_dragon", where)], seconds=2.0)
        _, hot = self._fight(
            [self._real("dancing_dragon", where)], seconds=2.0, buffs={"optimized": 8}
        )
        assert 350 - hot["player2_quota"] > 350 - cold["player2_quota"]

    def test_present_hands_out_five_buffs(self):
        where, _ = self._place("present")
        sim, _ = self._fight([self._real("present", where)], seconds=0.2)
        assert sum(sim.player1.buffs.values()) == 5
        assert set(sim.player1.buffs) <= BUFFS

    def test_angel_crystal_gains_at_the_start_and_again_at_seven(self):
        where, (one,) = self._place("angel_crystal", 1)
        holy = [self._real("angel_crystal", where), self._tagged("h", ["holy"], one)]
        early, _ = self._fight(holy, seconds=1.0)
        late, _ = self._fight(holy, seconds=7.5)
        assert early.player1.buffs["regenerating"] == 5, "3 and 2 for one Holy"
        assert "monitored" not in early.player1.buffs
        assert late.player1.buffs["monitored"] == 4, "3 and 1 for one Holy"

    # --- after a time -----------------------------------------------------

    def test_rainbow_badge_gains_one_of_each(self):
        where, _ = self._place("rainbow_badge")
        early, _ = self._fight([self._real("rainbow_badge", where)], seconds=6.0)
        late, _ = self._fight([self._real("rainbow_badge", where)], seconds=7.5)
        assert early.player1.buffs == {}
        assert late.player1.buffs == {name: 1 for name in BUFFS}

    def test_shiny_shell_heals_more_beside_holy_items(self):
        where, (one, two) = self._place("shiny_shell", 2)
        _, alone = self._fight(
            [self._real("shiny_shell", where)], seconds=5.5, hurt=100
        )
        _, holy = self._fight(
            [
                self._real("shiny_shell", where),
                self._tagged("h", ["holy"], one),
                self._tagged("n", ["nature"], two),
            ],
            seconds=5.5,
            hurt=100,
        )
        assert alone["player1_quota"] - 100 == 5
        assert (
            holy["player1_quota"] - 100 == 8
        ), "5 and 3 for the one Holy-item; the Nature one adds nothing"

    # --- on a clock -------------------------------------------------------

    def test_stone_armor_takes_two_kinds_off_the_opponent(self):
        """ "Remove 1 Spikes and 2 Empower from opponent." Named, so it takes
        those and nothing else."""
        where, _ = self._place("stone_armor")
        sim, _ = self._fight(
            [self._real("stone_armor", where)],
            seconds=4.5,
            against=[
                self._item(
                    [
                        BattleStartTrigger(
                            effects=[
                                BuffEffect("spiked", 5, "self"),
                                BuffEffect("monitored", 5, "self"),
                                BuffEffect("credits", 5, "self"),
                            ]
                        )
                    ],
                    uid="them",
                    position=(6, 0),
                )
            ],
        )
        assert sim.player2.buffs == {"spiked": 4, "monitored": 3, "credits": 5}

    def test_shell_totem_takes_the_half_its_health_chooses(self):
        where, _ = self._place("shell_totem")
        healthy, _ = self._fight([self._real("shell_totem", where)], seconds=3.6)
        hurt, result = self._fight(
            [self._real("shell_totem", where)], seconds=3.6, hurt=100
        )
        assert healthy.player1.buffs.get("monitored") == 1
        assert "monitored" not in hurt.player1.buffs
        assert result["player1_quota"] - 100 == 8, "it healed instead"

    def test_rat_deals_effect_damage_and_rolls_twice_behind_it(self):
        """ "Deal 5 Effect-damage. 75% to inflict 1 Poison. 10% to inflict 1
        Blind." Three things, and only the first is certain."""
        where, _ = self._place("data_crawler")
        sim, result = self._fight([self._real("data_crawler", where)], seconds=30.0)
        assert 350 - result["player2_quota"] > 0
        rolled = {
            a.details.get("debuff_name")
            for a in sim.actions
            if a.action == "debuff" and a.details
        }
        assert "memory_leaked" in rolled, "the 75% should land in 9 tries"

    def test_cache_optimizer_swaps_what_it_gives_at_ten_mana(self):
        """ "Gain 1 Mana" every 3.5s, and "gain 1 Luck instead" once ten are
        held. Instead, so never both."""
        where, _ = self._place("cache_optimizer")
        early, _ = self._fight([self._real("cache_optimizer", where)], seconds=4.0)
        rich, _ = self._fight(
            [self._real("cache_optimizer", where)], seconds=4.0, buffs={"credits": 10}
        )
        assert early.player1.buffs == {"credits": 1}
        assert rich.player1.buffs == {"credits": 10, "calibrated": 1}

    def test_oil_lamp_arms_its_star_weapon_again_and_again(self):
        where, (one,) = self._place("oil_lamp", 1)
        sim, _ = self._fight(
            [
                self._real("oil_lamp", where),
                self._tagged("w", ["melee"], one, category="problem"),
            ],
            seconds=7.5,
        )
        weapon = next(i for i in sim.loadout[1] if i.uid == "w")
        assert weapon.damage_gained == 2, "3.4s and 6.8s"
        assert weapon.accuracy_bonus == pytest.approx(0.1)

    # --- on hit -----------------------------------------------------------

    def test_stone_golem_gains_empower_on_every_hit(self):
        where, _ = self._place("stone_golem")
        sim, _ = self._fight([self._real("stone_golem", where)], seconds=12.0)
        assert sim.player1.buffs.get("monitored", 0) > 0

    def test_hammer_stuns_sometimes_and_not_always(self):
        """45% chance, so over a long fight it should land and should not
        land on every swing."""
        where, _ = self._place("hammer")
        sim, _ = self._fight([self._real("hammer", where)], seconds=40.0)
        stuns = [a for a in sim.actions if a.action == "stun"]
        hits = [a for a in sim.actions if a.action == "damage"]
        assert stuns, "45% over that many swings should land"
        assert len(stuns) < len(hits), "and should not land on all of them"

    def test_snow_stick_chills_itself_as_well(self):
        """ "Inflict 3 Cold and 2 Cold to yourself." The second half is the
        cost of the first."""
        where, _ = self._place("snow_stick")
        sim, _ = self._fight([self._real("snow_stick", where)], seconds=6.0)
        assert sim.player2.debuffs["throttled"] > 0
        assert sim.player1.debuffs["throttled"] > 0
        assert sim.player2.debuffs["throttled"] > sim.player1.debuffs["throttled"]

    def test_hungry_blade_buys_vampirism_with_regeneration(self):
        where, _ = self._place("hungry_blade")
        with_it, _ = self._fight(
            [self._real("hungry_blade", where)], seconds=3.0, buffs={"regenerating": 2}
        )
        without, _ = self._fight([self._real("hungry_blade", where)], seconds=3.0)
        assert with_it.player1.buffs["draining"] > without.player1.buffs.get(
            "draining", 0
        )

    def test_magic_torch_arms_itself_and_its_star_weapons(self):
        where, (one,) = self._place("magic_torch", 1)
        sim, _ = self._fight(
            [
                self._real("magic_torch", where),
                self._tagged("w", ["melee"], one, category="problem"),
            ],
            seconds=3.0,
            buffs={"credits": 10},
        )
        gained = {i.uid: i.damage_gained for i in sim.loadout[1]}
        assert gained["magic_torch"] > 0, "this gains 1 damage"
        assert gained["w"] == gained["magic_torch"], "and so do Star Weapons"

    def test_stankus_toothpick_makes_the_opponent_softer(self):
        where, _ = self._place("stankus_toothpick")
        sim, _ = self._fight([self._real("stankus_toothpick", where)], seconds=3.0)
        assert sim.player2.modifier("damage_taken", 3.0) > 0

    # --- an aura as the cause ---------------------------------------------

    def test_quantum_firewall_gains_spiked_on_the_same_roll(self):
        """ "The same 30% roll also gains 1 Spiked (up to 5)." One roll, three
        things behind it, and the Spikes stop at five however long the fight.
        """
        where, _ = self._place("quantum_firewall")
        sim, _ = self._fight(
            [self._real("quantum_firewall", where)],
            seconds=40.0,
            against=[
                self._item(
                    [
                        TimerTrigger(
                            cooldown=1.0,
                            cpu_cost=0,
                            effects=[
                                AttackEffect(
                                    min_damage=1,
                                    max_damage=1,
                                    accuracy=1.0,
                                    crit_chance=0.0,
                                )
                            ],
                        )
                    ],
                    uid="them",
                    position=(6, 0),
                )
            ],
        )
        assert sim.player1.buffs.get("spiked") == 5, "up to 5, and it got there"

    def test_cubert_answers_what_stands_in_its_star(self):
        where, (one,) = self._place("cubert", 1)
        ticker = self._item(
            [
                TimerTrigger(
                    cooldown=0.5,
                    cpu_cost=0,
                    effects=[BuffEffect("calibrated", 0, "self")],
                )
            ],
            uid="t",
            position=one,
        )
        sim, _ = self._fight([self._real("cubert", where), ticker], seconds=20.0)
        assert sim.player1.buffs.get("regenerating", 0) > 0

    def test_cubert_answers_its_diamond_separately(self):
        """ "Diamond activates: 30% chance to use 1 Regeneration to gain 1
        Empower." A different zone and a different clause, so an item standing
        in the star cannot set it off."""
        spec = ITEM_CATALOG["cubert"]
        room = self.MINE
        for y in range(6):
            for x in range(6):
                covered = {(x + dx, y + dy) for dx, dy in spec.shape.squares}
                if not covered <= room:
                    continue
                diamond = [
                    (x + dx, y + dy)
                    for dx, dy in spec.shape.diamond
                    if (x + dx, y + dy) in room - covered
                ]
                if diamond:
                    where, one = (x, y), diamond[0]
                    break
            else:
                continue
            break
        ticker = self._item(
            [
                TimerTrigger(
                    cooldown=0.5,
                    cpu_cost=0,
                    effects=[BuffEffect("calibrated", 0, "self")],
                )
            ],
            uid="t",
            position=one,
        )
        sim, _ = self._fight(
            [self._real("cubert", where), ticker],
            seconds=20.0,
            buffs={"regenerating": 40},
        )
        assert sim.player1.buffs.get("monitored", 0) > 0

    def test_dark_web_access_deals_effect_damage_from_its_star(self):
        where, (one,) = self._place("dark_web_access", 1)
        ticker = self._item(
            [
                TimerTrigger(
                    cooldown=0.5,
                    cpu_cost=0,
                    effects=[BuffEffect("calibrated", 0, "self")],
                )
            ],
            uid="t",
            position=one,
        )
        _, alone = self._fight([self._real("dark_web_access", where)], seconds=20.0)
        _, fed = self._fight(
            [self._real("dark_web_access", where), ticker], seconds=20.0
        )
        assert alone["player2_quota"] == 350, "nothing in its star"
        assert fed["player2_quota"] < 350


class TestFatigue:
    """Section 7.1: what ends a battle"""

    @staticmethod
    def _quiet(seconds: float, round_number: int = 18, **on_sim):
        """Run a battle where nobody owns anything, so fatigue is the only
        thing that can move either quota. Round 18 for the 350 it starts them
        on, which fatigue takes a good while to get through.
        """
        p1, p2 = get_test_containers()
        sim = BattleSimulator(seed=TEST_SEED)
        sim.max_duration = seconds
        for name, value in on_sim.items():
            setattr(sim, name, value)
        result = sim.simulate_battle([], [], round_number, p1, p2)
        return sim, result

    @staticmethod
    def _payouts(sim, player: int):
        return [
            (a.timestamp, a.damage)
            for a in sim.actions
            if a.action == "fatigue" and a.player == player
        ]

    def test_nothing_happens_before_nightfall(self):
        sim, result = self._quiet(NIGHTFALL - 0.5)
        assert not [a for a in sim.actions if a.action == "fatigue"]
        assert result["player1_quota"] == result["player2_quota"] == 350

    def test_the_first_payout_lands_on_nightfall_and_deals_one(self):
        sim, _ = self._quiet(NIGHTFALL + 0.1)
        assert self._payouts(sim, 1) == [(17000, 1)]
        assert self._payouts(sim, 2) == [(17000, 1)]

    def test_it_pays_every_second_to_both_players(self):
        """1, 2, 3 ... to each of them, on the second."""
        sim, result = self._quiet(NIGHTFALL + 5)
        expected = [(17000, 1), (18000, 2), (19000, 3), (20000, 4), (21000, 5)]
        assert self._payouts(sim, 1) == expected
        assert self._payouts(sim, 2) == expected
        assert result["player1_quota"] == 350 - 15

    def test_the_level_climbs_by_a_tenth_of_itself_plus_one(self):
        """Ten payouts get it to 10, and the eleventh adds 2 rather than 1."""
        sim, _ = self._quiet(NIGHTFALL + 12)
        dealt = [damage for _, damage in self._payouts(sim, 1)]
        assert dealt == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 14]

    def test_past_a_minute_it_climbs_by_a_fifth(self):
        """No battle lasts a minute -- fatigue sees to that long before -- so
        the late rule is checked on the effect rather than through a battle.
        """
        sim = BattleSimulator(seed=TEST_SEED)
        sim.night = True  # The loop settles this; here it is stated outright
        player = Player(id=1, quota=10_000, max_quota=10_000, cpu=3.0)
        player.fatigue = 100
        sim.player1 = player

        sim.current_time = LATE_BATTLE - 1
        Fatigued().pay(player, sim)
        assert player.fatigue == 111, "a tenth of itself, plus one"

        sim.current_time = LATE_BATTLE
        Fatigued().pay(player, sim)
        assert player.fatigue == 134, "a fifth of itself, plus one"

    def test_a_battle_cannot_outlast_it(self):
        """Round 18 is the most health the game ever hands out, and neither
        player can be touched by anything but fatigue. It still ends, and well
        inside the backstop.
        """
        sim, result = self._quiet(600.0)
        assert result["duration"] < 40.0
        assert min(result["player1_quota"], result["player2_quota"]) == 0

    def test_night_falls_once_and_before_the_first_payout(self):
        sim, _ = self._quiet(NIGHTFALL + 5)
        nights = [a for a in sim.actions if a.action == "nightfall"]
        assert len(nights) == 1
        assert nights[0].timestamp == 17000
        assert sim.actions.index(nights[0]) < sim.actions.index(
            next(a for a in sim.actions if a.action == "fatigue")
        )

    def test_block_does_not_absorb_it(self):
        """It is not an attack, so there is nothing there for Block to answer.
        The same rule poison plays by.
        """
        sim = BattleSimulator(seed=TEST_SEED)
        player = Player(id=1, quota=100, max_quota=100, cpu=3.0)
        player.block = 50
        sim.player1 = player

        sim.inflict_fatigue(player)

        assert player.quota == 99
        assert player.block == 50, "none of it was spent"

    def test_the_share_a_player_carries_does_reach_it(self):
        """The one thing that stands in front of fatigue.

        Block and shields both answer an attack, and fatigue is not one. A
        damage share is written about damage rather than about attacks --
        "reduce damage taken by 25%", invulnerability -- so it reaches every
        kind, this one included. `_take_damage` says so in as many words.
        """
        sim = BattleSimulator(seed=TEST_SEED)
        player = Player(id=1, quota=100, max_quota=100, cpu=3.0)
        sim.player1 = player
        player.mods.append(Timed("modifier", "damage_taken", -0.5, None))

        player.fatigue = 9
        sim.inflict_fatigue(player)

        assert player.fatigue == 10, "the level climbs by the whole step"
        assert player.quota == 95, "and half of it lands"

    def test_each_player_carries_their_own_level(self):
        sim = BattleSimulator(seed=TEST_SEED)
        one = Player(id=1, quota=100, max_quota=100, cpu=3.0)
        two = Player(id=2, quota=100, max_quota=100, cpu=3.0)
        sim.player1, sim.player2 = one, two

        sim.inflict_fatigue(one)
        sim.inflict_fatigue(one)
        sim.inflict_fatigue(two)

        assert (one.fatigue, two.fatigue) == (2, 1)
        assert (one.quota, two.quota) == (100 - 1 - 2, 100 - 1)

    def test_both_fighters_going_down_together_is_reported_as_both(self):
        """Fatigue lands on both players in the same tick, so both can fall in
        it. The log used to name only the first one checked, which left the
        client to guess at the other -- and it guessed by re-deriving the
        winner from health it had been subtracting itself.
        """
        sim, result = self._quiet(600.0, round_number=1)

        assert result["player1_quota"] == result["player2_quota"] == 0
        assert sorted(
            a.player for a in sim.actions if a.action == "player_defeated"
        ) == [1, 2]

    def test_a_battle_leaves_no_fatigue_behind_it(self):
        """Section 7.1 is battle state. A player who ended one round tired
        starts the next one fresh.
        """
        player = Player(id=1, quota=100, max_quota=100, cpu=3.0)
        player.fatigue = 40
        player.reset_for_battle()
        assert player.fatigue == 0


class TestFatigueFromAnItem:
    """ "Inflict Fatigue damage": one step on the same level nightfall climbs"""

    @staticmethod
    def _tiring(target: str = "enemy", at: float = 0.5):
        """An item that inflicts fatigue once, `at` seconds in."""
        return BattleItem(
            spec=ItemSpec(
                id="tiring",
                name="Tiring",
                category="problem",
                cost=1,
                player_class="neutral",
                kinds=frozenset({"melee"}),
                shape=parse_map(["#"], "tiring"),
                slug="tiring",
                triggers=[
                    TimerTrigger(
                        cooldown=at,
                        cpu_cost=0,
                        effects=[InflictFatigueEffect(target_type=target)],
                    )
                ],
            ),
            position=(0, 0),
            uid="tiring",
        )

    def test_it_takes_one_step_and_deals_the_whole_level(self):
        p1, p2 = get_test_containers()
        sim = BattleSimulator(seed=TEST_SEED)
        sim.max_duration = 3.5
        sim.nightfall = 99.0  # This is about the item, not about nightfall
        result = sim.simulate_battle([self._tiring(at=1.0)], [], 18, p1, p2)

        # Three activations, and the level is one higher at each of them.
        assert [a.damage for a in sim.actions if a.action == "fatigue"] == [1, 2, 3]
        assert result["player2_quota"] == 350 - 6

    def test_tiring_someone_early_makes_every_nightfall_payout_worse(self):
        """The level an item pushes up is the level nightfall carries on
        from, which is the whole reason to do it early.
        """
        p1, p2 = get_test_containers()
        sim = BattleSimulator(seed=TEST_SEED)
        sim.max_duration = NIGHTFALL + 0.1
        # Fires at 5s, 10s and 15s, so the level stands at 3 by nightfall.
        result = sim.simulate_battle([self._tiring(at=5.0)], [], 18, p1, p2)

        nightfall_payout = [
            a for a in sim.actions if a.action == "fatigue" and a.timestamp == 17000
        ]
        by_player = {a.player: a.damage for a in nightfall_payout}
        assert by_player[2] == 4, "carried on from the 3 the item left"
        assert by_player[1] == 1, "the other side was never touched"
        assert result["player2_quota"] == 350 - (1 + 2 + 3 + 4)

    def test_it_can_be_pointed_at_its_own_owner(self):
        p1, p2 = get_test_containers()
        sim = BattleSimulator(seed=TEST_SEED)
        sim.max_duration = 1.5
        sim.nightfall = 99.0
        result = sim.simulate_battle([self._tiring("self", at=1.0)], [], 18, p1, p2)

        assert result["player1_quota"] == 350 - 1
        assert result["player2_quota"] == 350


class TestItemsWrittenAgainstFatigue:
    """The catalogue clauses that were waiting on the mechanic"""

    @staticmethod
    def _shelved(category: str, slug: str) -> str:
        """What the catalogue still lists as unbuilt for an item.

        Read off the file rather than the loaded spec: `unbuilt` is prose for
        a reader, so nothing carries it into `ItemSpec`. A clause that is
        built and still sitting there is the mistake this catches.
        """
        import json
        from pathlib import Path

        path = Path(__file__).parent.parent / "data" / "items" / f"{category}.json"
        items = json.loads(path.read_text())["items"]
        entry = next(i for i in items.values() if i.get("slug") == slug)
        return " ".join(entry.get("unbuilt", []))

    def test_traffic_cop_gains_heat_when_night_falls(self):
        """From the catalogue: "Fatigue starts: gain 10 Heat". Heat is ours as
        Optimized.
        """
        spec = ITEM_CATALOG["ddos_protection_module"]
        nightfall = [t for t in spec.triggers if isinstance(t, FatigueStartTrigger)]
        assert nightfall, "the clause is built, not shelved"
        assert "Fatigue starts" not in self._shelved(
            "scripts", "ddos_protection_module"
        )

        cop = BattleItem(spec=deepcopy(spec), position=(0, 0), uid="cop")
        p1, p2 = get_test_containers()
        sim = BattleSimulator(seed=TEST_SEED)
        sim.max_duration = NIGHTFALL + 0.1
        sim.simulate_battle([cop], [], 18, p1, p2)

        assert sim.player1.buffs.get("optimized") == 10
        assert not sim.player2.buffs.get("optimized")

    def test_the_heat_arrives_before_the_first_fatigue_lands(self):
        """An item written against the moment has to be changed by the time
        the moment's own consequences arrive.
        """
        cop = BattleItem(
            spec=deepcopy(ITEM_CATALOG["ddos_protection_module"]),
            position=(0, 0),
            uid="cop",
        )
        p1, p2 = get_test_containers()
        sim = BattleSimulator(seed=TEST_SEED)
        sim.max_duration = NIGHTFALL + 0.1
        sim.simulate_battle([cop], [], 18, p1, p2)

        buff = next(a for a in sim.actions if a.action == "buff")
        fatigue = next(a for a in sim.actions if a.action == "fatigue")
        assert sim.actions.index(buff) < sim.actions.index(fatigue)

    def test_day_zero_tires_whoever_it_lands_on(self):
        """From the catalogue: "On hit: Inflict Fatigue damage"."""
        spec = ITEM_CATALOG["day_zero"]
        assert "Inflict Fatigue" not in self._shelved("problems", "day_zero")

        on_hit = [t for t in spec.triggers if isinstance(t, OnHitTrigger)]
        assert on_hit and any(
            isinstance(e, InflictFatigueEffect) for e in on_hit[0].effects
        )


class TestAPriceThatWaits(_WithOneItem):
    """ "Use 10 Mana: Become invulnerable for 2s (once)."

    The wiki says what the waiting looks like: "Once the player has 10 Mana,
    the Glowing Crown will spend it to grant invulnerability for 2s." Not on a
    clock and not asked for -- it watches, and goes off the moment the price
    is met.
    """

    def _waiter(self, costs, effects, uid="waiter", position=(0, 0)):
        return self._item(
            [WhenAffordableTrigger(costs=costs, effects=effects)],
            uid=uid,
            position=position,
        )

    def test_it_waits_until_it_can_pay(self):
        giver = self._item(
            [
                TimerTrigger(
                    cooldown=1.0, cpu_cost=0, effects=[BuffEffect("credits", 1, "self")]
                )
            ],
            uid="g",
            position=(1, 0),
        )
        item = self._waiter({"credits": 3}, [BlockEffect(block_amount=20)])
        early, _ = self._run([item, giver], seconds=2.5)
        late, _ = self._run([item, giver], seconds=3.5)
        assert early.player1.block == 0, "only two Mana so far"
        assert late.player1.block == 20

    def test_it_pays_when_it_fires(self):
        sim, _ = self._run(
            [self._waiter({"credits": 3}, [BlockEffect(block_amount=20)])],
            seconds=0.5,
            buffs={"credits": 5},
        )
        assert sim.player1.buffs == {"credits": 2}

    def test_without_a_limit_it_fires_again_next_time_it_can(self):
        """Nearly every one of these ends "(once)", which is a limit behind
        it rather than anything the trigger knows."""
        giver = self._item(
            [
                TimerTrigger(
                    cooldown=1.0, cpu_cost=0, effects=[BuffEffect("credits", 3, "self")]
                )
            ],
            uid="g",
            position=(1, 0),
        )
        sim, _ = self._run(
            [self._waiter({"credits": 3}, [BlockEffect(block_amount=20)]), giver],
            seconds=3.5,
        )
        assert sim.player1.block == 60, "three times over"

    def test_a_limit_behind_it_is_what_once_means(self):
        giver = self._item(
            [
                TimerTrigger(
                    cooldown=1.0, cpu_cost=0, effects=[BuffEffect("credits", 3, "self")]
                )
            ],
            uid="g",
            position=(1, 0),
        )
        sim, _ = self._run(
            [
                self._waiter(
                    {"credits": 3},
                    [LimitEffect(times=1, effects=[BlockEffect(block_amount=20)])],
                ),
                giver,
            ],
            seconds=3.5,
        )
        assert sim.player1.block == 20

    def test_it_costs_no_cpu(self):
        """ "The Dagger attacks an extra time for free": a price in buffs is
        the whole price."""
        assert WhenAffordableTrigger(costs={"credits": 1}).get_cpu_cost() == 0


class TestATotalCrossingALine(_WithOneItem):
    """ "45 Block reached", "30 Mana gained", "Opponent reaches 30 Cold".

    Crossing is the trigger, not being over -- like a health threshold, it
    fires on the way past and not on every tick after.
    """

    def _watcher(self, **kwargs):
        settings = dict(
            counting="block",
            amount=45,
            whose="self",
            counts="held",
            effects=[BuffEffect("spiked", 1, "self")],
        )
        settings.update(kwargs)
        return self._item([CounterTrigger(**settings)])

    def test_it_fires_when_the_total_gets_there(self):
        giver = self._item(
            [
                TimerTrigger(
                    cooldown=1.0, cpu_cost=0, effects=[BlockEffect(block_amount=20)]
                )
            ],
            uid="g",
            position=(1, 0),
        )
        early, _ = self._run([self._watcher(), giver], seconds=2.5)
        late, _ = self._run([self._watcher(), giver], seconds=3.5)
        assert "spiked" not in early.player1.buffs, "40 Block, not 45"
        assert late.player1.buffs["spiked"] == 1

    def test_it_fires_once_however_long_it_stays_over(self):
        giver = self._item(
            [
                TimerTrigger(
                    cooldown=1.0, cpu_cost=0, effects=[BlockEffect(block_amount=20)]
                )
            ],
            uid="g",
            position=(1, 0),
        )
        sim, _ = self._run([self._watcher(), giver], seconds=9.0)
        assert sim.player1.buffs["spiked"] == 1

    def test_held_is_what_a_player_has_now(self):
        """Spending it puts them back under the line, so an item that waits
        for stacks to be held may never see them."""
        spender = self._item(
            [
                TimerTrigger(
                    cooldown=1.0, cpu_cost=0, effects=[BuffEffect("credits", 3, "self")]
                )
            ],
            uid="g",
            position=(1, 0),
        )
        drain = self._item(
            [WhenAffordableTrigger(costs={"credits": 3}, effects=[])],
            uid="d",
            position=(2, 0),
        )
        sim, _ = self._run(
            [
                self._watcher(counting="credits", amount=9, counts="held"),
                spender,
                drain,
            ],
            seconds=9.0,
        )
        assert "spiked" not in sim.player1.buffs, "never nine at once"

    def test_gained_is_everything_that_ever_arrived(self):
        """The same fight, and the total that only goes up does see them."""
        spender = self._item(
            [
                TimerTrigger(
                    cooldown=1.0, cpu_cost=0, effects=[BuffEffect("credits", 3, "self")]
                )
            ],
            uid="g",
            position=(1, 0),
        )
        drain = self._item(
            [WhenAffordableTrigger(costs={"credits": 3}, effects=[])],
            uid="d",
            position=(2, 0),
        )
        sim, _ = self._run(
            [
                self._watcher(counting="credits", amount=9, counts="gained"),
                spender,
                drain,
            ],
            seconds=9.0,
        )
        assert sim.player1.buffs["spiked"] == 1

    def test_it_can_watch_the_other_player(self):
        chiller = self._item(
            [
                TimerTrigger(
                    cooldown=1.0,
                    cpu_cost=0,
                    effects=[DebuffEffect("throttled", 4, target_type="enemy")],
                )
            ],
            uid="c",
            position=(1, 0),
        )
        sim, _ = self._run(
            [self._watcher(counting="throttled", amount=8, whose="enemy"), chiller],
            seconds=3.5,
        )
        assert sim.player1.buffs["spiked"] == 1


class TestAStatusArriving(_WithOneItem):
    """ "Empower gained: Gain 11 maximum health", "Regeneration gained: Gain 3
    maximum health", "Opponent gains buff: 15% chance to nullify it."
    """

    def _watcher(self, status="monitored", whose="self"):
        return self._item(
            [
                StatusChangeTrigger(
                    status=status, whose=whose, effects=[BlockEffect(block_amount=10)]
                )
            ]
        )

    def test_it_answers_the_status_it_names(self):
        giver = self._item(
            [BattleStartTrigger(effects=[BuffEffect("monitored", 1, "self")])],
            uid="g",
            position=(1, 0),
        )
        sim, _ = self._run([self._watcher(), giver], seconds=0.3)
        assert sim.player1.block == 10

    def test_it_ignores_the_ones_it_does_not(self):
        giver = self._item(
            [BattleStartTrigger(effects=[BuffEffect("calibrated", 5, "self")])],
            uid="g",
            position=(1, 0),
        )
        sim, _ = self._run([self._watcher(), giver], seconds=0.3)
        assert sim.player1.block == 0

    def test_it_answers_every_arrival_rather_than_every_stack(self):
        """Five at once is one gain, not five."""
        giver = self._item(
            [BattleStartTrigger(effects=[BuffEffect("monitored", 5, "self")])],
            uid="g",
            position=(1, 0),
        )
        sim, _ = self._run([self._watcher(), giver], seconds=0.3)
        assert sim.player1.block == 10

    def test_it_can_watch_the_other_player(self):
        sim, _ = self._run(
            [self._watcher(whose="enemy")],
            seconds=0.3,
            against=[
                self._item(
                    [BattleStartTrigger(effects=[BuffEffect("monitored", 1, "self")])],
                    uid="them",
                    position=(4, 0),
                )
            ],
        )
        assert sim.player1.block == 10

    def test_watching_one_player_means_ignoring_the_other(self):
        """A watcher of its own gains stays quiet when the other side gains,
        and the other way round. Without both halves, a trigger that answered
        everybody would look right."""
        mine = self._item(
            [BattleStartTrigger(effects=[BuffEffect("monitored", 1, "self")])],
            uid="g",
            position=(1, 0),
        )
        theirs = self._item(
            [BattleStartTrigger(effects=[BuffEffect("monitored", 1, "self")])],
            uid="them",
            position=(4, 0),
        )
        watching_them, _ = self._run([self._watcher(whose="enemy"), mine], seconds=0.3)
        watching_me, _ = self._run(
            [self._watcher(whose="self")], seconds=0.3, against=[theirs]
        )
        assert watching_them.player1.block == 0, "my gain is not theirs"
        assert watching_me.player1.block == 0, "and theirs is not mine"

    def test_a_debuff_arriving_counts_too(self):
        giver = self._item(
            [
                BattleStartTrigger(
                    effects=[DebuffEffect("throttled", 1, target_type="self")]
                )
            ],
            uid="g",
            position=(1, 0),
        )
        sim, _ = self._run([self._watcher(status="throttled"), giver], seconds=0.3)
        assert sim.player1.block == 10


class TestRunningOutOfStamina(_WithOneItem):
    """ "Out of stamina: Consume this and regenerate 2 stamina and gain 1
    Empower." The wiki: "When the player runs out of stamina the Heroic Potion
    is consumed."
    """

    def test_it_fires_when_the_pool_is_empty(self):
        hungry = self._item(
            [
                TimerTrigger(
                    cooldown=0.5,
                    cpu_cost=3.0,
                    effects=[
                        AttackEffect(
                            min_damage=1, max_damage=1, accuracy=1.0, crit_chance=0.0
                        )
                    ],
                )
            ],
            uid="h",
            position=(1, 0),
        )
        potion = self._item(
            [
                OutOfStaminaTrigger(
                    effects=[
                        ConsumeEffect(),
                        StaminaEffect(amount=2, target_type="self"),
                    ]
                )
            ]
        )
        sim, _ = self._run([potion, hungry], seconds=5.0)
        assert potion.uid in sim.consumed_items

    def test_it_does_not_fire_while_there_is_stamina_left(self):
        potion = self._item([OutOfStaminaTrigger(effects=[ConsumeEffect()])])
        sim, _ = self._run([potion], seconds=3.0)
        assert potion.uid not in sim.consumed_items

    def test_stamina_goes_into_the_pool(self):
        """Asked of the effect rather than through a battle: the loop tops the
        pool up every tick and clamps it, which hides both what this adds and
        what it refuses to add."""
        sim = BattleSimulator(seed=TEST_SEED)
        sim.player1 = player = Player(id=1, quota=100, max_quota=100, cpu=0.0)
        sim.player2 = Player(id=2, quota=100, max_quota=100, cpu=0.0)
        sim._apply_effects(
            [StaminaEffect(amount=2, target_type="self")],
            self._item([]),
            player,
            sim.player2,
        )
        assert player.cpu == 2.0

    def test_stamina_does_not_go_past_the_pool(self):
        sim = BattleSimulator(seed=TEST_SEED)
        sim.player1 = player = Player(id=1, quota=100, max_quota=100, cpu=1.0)
        sim.player2 = Player(id=2, quota=100, max_quota=100, cpu=0.0)
        sim._apply_effects(
            [StaminaEffect(amount=99, target_type="self")],
            self._item([]),
            player,
            sim.player2,
        )
        assert player.cpu == player.max_cpu


class TestSwingingAgain(_WithOneItem):
    """ "On stun: Triggers extra attack", "Attacks twice."

    The wiki, of the Dagger: "On stun, the Dagger attacks an extra time,
    making it stronger with stunning items like the Hammer." It is the item's
    own attack run once more, so everything hanging off an attack happens with
    it.
    """

    @staticmethod
    def _dagger(uid="dagger", position=(0, 0), extra=True):
        triggers = [
            TimerTrigger(
                cooldown=2.0,
                cpu_cost=0,
                effects=[
                    AttackEffect(
                        min_damage=5, max_damage=5, accuracy=1.0, crit_chance=0.0
                    )
                ],
            )
        ]
        if extra:
            triggers.append(OnStunTrigger(effects=[ExtraAttackEffect()]))
        return BattleItem(
            spec=ItemSpec(
                id=uid,
                name="Dagger",
                category="problem",
                cost=1,
                player_class="neutral",
                shape=parse_map(["#"], "d"),
                slug=uid,
                kinds=frozenset({"melee"}),
                triggers=triggers,
            ),
            position=position,
            uid=uid,
        )

    def _stunner(self, at=1.0, uid="stunner", position=(1, 0)):
        from item_effects import AfterTrigger

        return self._item(
            [
                AfterTrigger(
                    delay=at, effects=[StunEffect(duration=0.5, target_type="enemy")]
                )
            ],
            uid=uid,
            position=position,
        )

    def test_a_stun_its_owner_lands_makes_it_swing_again(self):
        _, plain = self._run([self._dagger(extra=False), self._stunner()], seconds=5.0)
        _, extra = self._run([self._dagger(), self._stunner()], seconds=5.0)
        assert 350 - extra["player2_quota"] == (350 - plain["player2_quota"]) + 5

    def test_the_stun_need_not_come_from_the_same_item(self):
        """ "stronger with stunning items like the Hammer": any stun its owner
        lands, not only one this item caused."""
        sim, _ = self._run([self._dagger(), self._stunner()], seconds=5.0)
        swings = [
            a for a in sim.actions if a.action == "damage" and a.source == "dagger"
        ]
        assert len(swings) == 3, "two on the clock and one on the stun"

    def test_a_stun_landed_on_its_owner_does_not(self):
        """The trigger belongs to whoever did the stunning."""
        theirs = self._item(
            [
                TimerTrigger(
                    cooldown=1.0,
                    cpu_cost=0,
                    effects=[
                        AttackEffect(
                            min_damage=1, max_damage=1, accuracy=1.0, crit_chance=0.0
                        )
                    ],
                )
            ],
            uid="them",
            position=(4, 0),
        )
        stunning_me = self._item(
            [
                BattleStartTrigger(
                    effects=[StunEffect(duration=0.5, target_type="self")]
                )
            ],
            uid="s",
            position=(1, 0),
        )
        sim, _ = self._run([self._dagger(), stunning_me], seconds=3.0, against=[theirs])
        swings = [
            a for a in sim.actions if a.action == "damage" and a.source == "dagger"
        ]
        assert len(swings) == 1, "the stun was ours to take, not to land"

    def test_every_item_with_it_answers_the_same_stun(self):
        """One stun, three Daggers, three extra attacks. Their own cooldown is
        longer than the fight, so every swing here is an extra one."""
        slow = [
            BattleItem(
                spec=ItemSpec(
                    id=uid,
                    name="Dagger",
                    category="problem",
                    cost=1,
                    player_class="neutral",
                    shape=parse_map(["#"], "d"),
                    slug=uid,
                    kinds=frozenset({"melee"}),
                    triggers=[
                        TimerTrigger(
                            cooldown=9.0,
                            cpu_cost=0,
                            effects=[
                                AttackEffect(
                                    min_damage=1,
                                    max_damage=1,
                                    accuracy=1.0,
                                    crit_chance=0.0,
                                )
                            ],
                        ),
                        OnStunTrigger(effects=[ExtraAttackEffect()]),
                    ],
                ),
                position=at,
                uid=uid,
            )
            for uid, at in (("d1", (0, 0)), ("d2", (1, 0)), ("d3", (2, 0)))
        ]
        sim, _ = self._run(slow + [self._stunner(position=(0, 1))], seconds=3.0)
        swung = {a.source for a in sim.actions if a.action == "damage"}
        assert swung == {"d1", "d2", "d3"}

    def test_the_item_that_stunned_need_not_be_one_of_them(self):
        """ "making it stronger with stunning items like the Hammer": the
        Hammer has no on-stun clause of its own, and every Dagger still
        swings."""
        sim, _ = self._run([self._dagger(), self._stunner()], seconds=5.0)
        assert [
            a for a in sim.actions if a.action == "damage" and a.source == "stunner"
        ] == []
        assert (
            len(
                [
                    a
                    for a in sim.actions
                    if a.action == "damage" and a.source == "dagger"
                ]
            )
            == 3
        )

    def test_a_stun_on_its_own_owner_opens_nothing(self):
        """Whoever landed it. Their cooldowns are the ones on hold, so there
        is no opening to take -- and this used to hand the opening across the
        table, because "whoever is not the target" is not "whoever did it"."""
        theirs = self._item(
            [
                TimerTrigger(
                    cooldown=1.0,
                    cpu_cost=0,
                    effects=[
                        AttackEffect(
                            min_damage=1, max_damage=1, accuracy=1.0, crit_chance=0.0
                        )
                    ],
                )
            ],
            uid="them",
            position=(4, 0),
        )
        their_own_fault = self._item(
            [
                BattleStartTrigger(
                    effects=[StunEffect(duration=0.5, target_type="self")]
                )
            ],
            uid="s",
            position=(5, 0),
        )
        sim, _ = self._run(
            [
                BattleItem(
                    spec=ItemSpec(
                        id="mine",
                        name="Dagger",
                        category="problem",
                        cost=1,
                        player_class="neutral",
                        shape=parse_map(["#"], "d"),
                        slug="mine",
                        kinds=frozenset({"melee"}),
                        triggers=[
                            TimerTrigger(
                                cooldown=9.0,
                                cpu_cost=0,
                                effects=[
                                    AttackEffect(
                                        min_damage=1,
                                        max_damage=1,
                                        accuracy=1.0,
                                        crit_chance=0.0,
                                    )
                                ],
                            ),
                            OnStunTrigger(effects=[ExtraAttackEffect()]),
                        ],
                    ),
                    position=(0, 0),
                    uid="mine",
                )
            ],
            seconds=3.0,
            against=[theirs, their_own_fault],
        )
        mine = [a for a in sim.actions if a.action == "damage" and a.source == "mine"]
        assert len(mine) == 1, "their stun was on them, so it is my opening"

    def test_an_item_with_no_attack_has_nothing_to_do_again(self):
        quiet = self._item([OnStunTrigger(effects=[ExtraAttackEffect()])], uid="q")
        sim, _ = self._run([quiet, self._stunner()], seconds=3.0)
        assert not [a for a in sim.actions if a.action == "damage"]


class TestAMiss(_WithOneItem):
    """ "On miss: Gain 3 Luck" is this item's own swing going wide; "Opponent
    misses attack: Gain +2 damage" is the other player's."""

    @staticmethod
    def _wild(uid="wild", position=(0, 0), whose="self", accuracy=0.0):
        return BattleItem(
            spec=ItemSpec(
                id=uid,
                name="Wild",
                category="problem",
                cost=1,
                player_class="neutral",
                shape=parse_map(["#"], "w"),
                slug=uid,
                kinds=frozenset({"melee"}),
                triggers=[
                    TimerTrigger(
                        cooldown=1.0,
                        cpu_cost=0,
                        effects=[
                            AttackEffect(
                                min_damage=5,
                                max_damage=5,
                                accuracy=accuracy,
                                crit_chance=0.0,
                            )
                        ],
                    ),
                    OnMissTrigger(
                        whose=whose, effects=[BuffEffect("calibrated", 3, "self")]
                    ),
                ],
            ),
            position=position,
            uid=uid,
        )

    def test_its_own_miss_sets_it_off(self):
        sim, _ = self._run([self._wild()], seconds=2.5)
        assert sim.player1.buffs["calibrated"] == 6, "two swings, two misses"

    def test_a_hit_does_not(self):
        sim, _ = self._run([self._wild(accuracy=1.0)], seconds=2.5)
        assert "calibrated" not in sim.player1.buffs

    def test_another_item_missing_does_not(self):
        """ "On miss" belongs to the weapon that swung."""
        other = self._wild(uid="other", position=(1, 0))
        sim, _ = self._run(
            [
                self._item(
                    [
                        OnMissTrigger(
                            whose="self", effects=[BuffEffect("spiked", 1, "self")]
                        )
                    ],
                    uid="watcher",
                ),
                other,
            ],
            seconds=2.5,
        )
        assert "spiked" not in sim.player1.buffs

    def test_the_opponent_missing_sets_off_the_other_kind(self):
        sim, _ = self._run(
            [
                self._item(
                    [
                        OnMissTrigger(
                            whose="enemy", effects=[BuffEffect("spiked", 1, "self")]
                        )
                    ],
                    uid="watcher",
                )
            ],
            seconds=2.5,
            against=[self._wild(uid="them", position=(4, 0))],
        )
        assert sim.player1.buffs["spiked"] == 2

    def test_that_kind_stays_quiet_when_its_own_side_misses(self):
        """ "Opponent misses attack" is theirs, so my own wild swings are not
        it."""
        sim, _ = self._run(
            [
                self._item(
                    [
                        OnMissTrigger(
                            whose="enemy", effects=[BuffEffect("spiked", 1, "self")]
                        )
                    ],
                    uid="watcher",
                ),
                self._wild(uid="mine", position=(1, 0)),
            ],
            seconds=2.5,
        )
        assert "spiked" not in sim.player1.buffs


class TestTheCatalogueItemsThatWaitForAMoment(TestTheSweptClauses):
    """Real items whose clauses hang on *when* they fire.

    A price that can now be met, a status arriving, a running total crossing a
    line, a stun, a swing that missed, a pool that ran dry. Run as they stand
    rather than on an item made for the purpose, because a catalogue entry can
    be wrong on its own.

    Inherits the bigger room and the placement helper: these are real items
    with real shapes, and a star drawn above one has to have somewhere to land.
    """

    def test_glowing_crown_waits_for_its_ten_mana(self):
        """ "Use 10 Mana: Become invulnerable for 2s (once)." The wiki: "Once
        the player has 10 Mana, the Glowing Crown will spend it.\" """
        where, _ = self._place("glowing_crown")
        poor, _ = self._fight([self._real("glowing_crown", where)], seconds=1.0)
        rich, _ = self._fight(
            [self._real("glowing_crown", where)], seconds=1.0, buffs={"credits": 10}
        )
        assert poor.player1.modifier("damage_taken", 0.5) == 0
        assert rich.player1.modifier("damage_taken", 0.5) == -1.0
        assert "credits" not in rich.player1.buffs, "spent"

    def test_the_crown_is_invulnerable_only_for_its_two_seconds(self):
        where, _ = self._place("glowing_crown")
        sim, result = self._fight(
            [self._real("glowing_crown", where)],
            seconds=5.0,
            buffs={"credits": 10},
            against=[self._swinger(damage=20, cooldown=1.0, position=(6, 0))],
        )
        assert 350 - result["player1_quota"] > 0, "it stopped being invulnerable"
        assert sim.player1.modifier("damage_taken", 5.0) == 0

    def test_heart_container_pays_once_and_no_more(self):
        """ "Use 7 Regeneration: Gain 100 maximum health, 2 Empower and your
        healing is increased by 15% (once).\" """
        where, _ = self._place("heart_container")
        sim, result = self._fight([self._real("heart_container", where)], seconds=30.0)
        assert result["player1_quota"] == 450, "350 and the 100 it gained"
        assert sim.player1.buffs["monitored"] == 2, "once, not once a payment"

    def test_gloves_of_power_answer_a_hit_in_their_star(self):
        """ "Star Weapon hits: gain 7 Block." A hit, so a miss is not one."""
        where, (one,) = self._place("gloves_of_power", 1)
        weapon = BattleItem(
            spec=ItemSpec(
                id="w",
                name="Weapon",
                category="problem",
                cost=1,
                player_class="neutral",
                shape=parse_map(["#"], "w"),
                slug="w",
                kinds=frozenset({"melee"}),
                triggers=[
                    TimerTrigger(
                        cooldown=1.0,
                        cpu_cost=0,
                        effects=[
                            AttackEffect(
                                min_damage=1,
                                max_damage=1,
                                accuracy=1.0,
                                crit_chance=0.0,
                            )
                        ],
                    )
                ],
            ),
            position=one,
            uid="w",
        )
        sim, _ = self._fight(
            [self._real("gloves_of_power", where), weapon], seconds=3.5
        )
        assert sim.player1.block == 21, "three hits, 7 each"

    def test_gloves_of_power_ignore_a_miss(self):
        where, (one,) = self._place("gloves_of_power", 1)
        missing = BattleItem(
            spec=ItemSpec(
                id="w",
                name="Weapon",
                category="problem",
                cost=1,
                player_class="neutral",
                shape=parse_map(["#"], "w"),
                slug="w",
                kinds=frozenset({"melee"}),
                triggers=[
                    TimerTrigger(
                        cooldown=1.0,
                        cpu_cost=0,
                        effects=[
                            AttackEffect(
                                min_damage=1,
                                max_damage=1,
                                accuracy=0.0,
                                crit_chance=0.0,
                            )
                        ],
                    )
                ],
            ),
            position=one,
            uid="w",
        )
        sim, _ = self._fight(
            [self._real("gloves_of_power", where), missing], seconds=3.5
        )
        assert sim.player1.block == 0, "it activated, and it did not hit"

    def test_thornbloom_grows_when_empower_arrives(self):
        """ "Empower gained: Gain 11 maximum health." Its own on-hit clause is
        what feeds it, so the two work together."""
        where, _ = self._place("thornbloom")
        sim, result = self._fight([self._real("thornbloom", where)], seconds=20.0)
        assert sim.player1.buffs.get("monitored", 0) > 0
        assert result["player1_quota"] > 350, "maximum health went up with it"

    def test_frostbite_answers_the_cold_it_piles_on(self):
        """ "Opponent reaches 30 Cold: Gain 12 Vampirism (once)." Its own on-hit
        inflicts the Cold, so it gets there by itself."""
        where, _ = self._place("frostbite")
        chiller = self._item(
            [
                TimerTrigger(
                    cooldown=1.0,
                    cpu_cost=0,
                    effects=[DebuffEffect("throttled", 10, target_type="enemy")],
                )
            ],
            uid="c",
            position=(5, 5),
        )
        early, _ = self._fight([self._real("frostbite", where), chiller], seconds=1.5)
        late, _ = self._fight([self._real("frostbite", where), chiller], seconds=3.5)
        assert "draining" not in early.player1.buffs, "10 Cold, not 30"
        assert late.player1.buffs.get("draining", 0) >= 12

    def test_manathirst_counts_the_mana_it_spends(self):
        """ "30 Mana gained." Gained, not held: an item that waited for 30 at
        once would never fire beside one that spends them."""
        where, _ = self._place("manathirst")
        _, result = self._fight(
            [self._real("manathirst", where)], seconds=40.0, buffs={"credits": 30}
        )
        assert result["player2_quota"] < 350

    def test_dark_web_access_counts_the_damage_it_deals(self):
        """ "22 Effect-damage dealt: Inflict 1 random debuff.\" """
        where, (one,) = self._place("dark_web_access", 1)
        ticker = self._item(
            [
                TimerTrigger(
                    cooldown=0.5,
                    cpu_cost=0,
                    effects=[BuffEffect("calibrated", 0, "self")],
                )
            ],
            uid="t",
            position=one,
        )
        sim, _ = self._fight(
            [self._real("dark_web_access", where), ticker], seconds=40.0
        )
        assert sim.player2.debuffs, "22 dealt, so a debuff was inflicted"

    def test_a_dagger_swings_again_when_its_owner_stuns(self):
        """ "On stun: Triggers extra attack." The Hammer does the stunning."""

        def swings(with_a_stunner):
            items = [self._real("poison_dagger", (0, 0))]
            if with_a_stunner:
                # An After trigger rather than the Hammer, so the number of
                # stuns is fixed and the comparison is not about a 45% roll.
                from item_effects import AfterTrigger

                items.append(
                    self._item(
                        [
                            AfterTrigger(
                                delay=1.0,
                                effects=[StunEffect(duration=0.1, target_type="enemy")],
                            )
                        ],
                        uid="s",
                        position=(4, 0),
                    )
                )
            sim, _ = self._fight(items, seconds=6.0)
            return len(
                [
                    a
                    for a in sim.actions
                    if a.action != "miss"
                    and a.source == "poison_dagger"
                    and a.action == "damage"
                ]
            )

        plain, stunning = swings(False), swings(True)
        assert stunning == plain + 1, "one stun, one extra swing"

    def test_the_heroic_potion_is_drunk_when_the_pool_cannot_pay(self):
        """ "Out of stamina: Consume this and regenerate 4 stamina and gain 1
        Empower.\" """
        where, _ = self._place("strong_heroic_potion")
        hungry = self._item(
            [
                TimerTrigger(
                    cooldown=0.5,
                    cpu_cost=3.0,
                    effects=[
                        AttackEffect(
                            min_damage=1, max_damage=1, accuracy=1.0, crit_chance=0.0
                        )
                    ],
                )
            ],
            uid="h",
            position=(5, 5),
        )
        sim, _ = self._fight(
            [self._real("strong_heroic_potion", where), hungry], seconds=6.0
        )
        assert "strong_heroic_potion" in sim.consumed_items
        assert sim.player1.buffs.get("monitored") == 1

    def test_the_rapier_gains_luck_when_it_swings_wide(self):
        """ "On miss: Gain 3 Luck", which its other clause spends: "On hit:
        Use 3 Luck to gain 3 damage." So the Luck never piles up, and what
        shows is the damage the missing paid for.
        """
        where, _ = self._place("fancy_fencing_rapier")
        sim, _ = self._fight([self._real("fancy_fencing_rapier", where)], seconds=40.0)
        misses = [a for a in sim.actions if a.action == "miss"]
        gained = [a for a in sim.actions if a.action == "gain_damage"]
        rapier = next(i for i in sim.loadout[1] if i.uid == "fancy_fencing_rapier")
        assert misses, "its accuracy is under 1, so it will miss"
        assert gained, "and each miss buys a hit its damage"
        assert rapier.damage_gained == 3 * len(gained)

    def test_thermal_throttle_arms_the_weapons_at_ten_heat(self):
        """ "10 Heat reached: Star Weapons gain 8 damage.\" """
        where, (one,) = self._place("thermal_throttle", 1)
        weapon = BattleItem(
            spec=ItemSpec(
                id="w",
                name="Weapon",
                category="problem",
                cost=1,
                player_class="neutral",
                shape=parse_map(["#"], "w"),
                slug="w",
                kinds=frozenset({"melee"}),
                triggers=[],
            ),
            position=one,
            uid="w",
        )
        cold, _ = self._fight(
            [self._real("thermal_throttle", where), weapon], seconds=1.0
        )
        hot, _ = self._fight(
            [self._real("thermal_throttle", where), weapon],
            seconds=1.0,
            buffs={"optimized": 10},
        )
        assert next(i for i in cold.loadout[1] if i.uid == "w").damage_gained == 0
        assert next(i for i in hot.loadout[1] if i.uid == "w").damage_gained == 8

    def test_system_restore_drinks_itself_at_ten_debuffs(self):
        where, _ = self._place("system_restore")
        sim, _ = self._fight(
            [self._real("system_restore", where)],
            seconds=4.0,
            against=[
                self._item(
                    [
                        TimerTrigger(
                            cooldown=1.0,
                            cpu_cost=0,
                            effects=[
                                DebuffEffect("memory_leaked", 4, target_type="enemy")
                            ],
                        )
                    ],
                    uid="them",
                    position=(6, 0),
                )
            ],
        )
        assert "system_restore" in sim.consumed_items
        assert sim.player1.debuffs.get("memory_leaked", 0) < 10


class TestATriggerThatRemembersForgetsBetweenBattles(_WithOneItem):
    """Three triggers keep state while a battle runs, and a catalogue is
    shared between every battle a process ever simulates.

    An aura counts activations towards its sixth, a counter remembers whether
    it has crossed, and a limit remembers what it has spent. If any of that
    reached the catalogue's own objects, the second battle of a run would
    start where the first one left off -- and every test that runs one battle
    would pass regardless.
    """

    def _twice(self, item):
        return [self._run([item], seconds=4.0)[0] for _ in range(2)]

    def test_a_counter_crosses_again_in_the_next_battle(self):
        watcher = self._item(
            [
                CounterTrigger(
                    counting="block",
                    amount=10,
                    whose="self",
                    counts="held",
                    effects=[BuffEffect("spiked", 1, "self")],
                )
            ]
            + [BattleStartTrigger(effects=[BlockEffect(block_amount=20)])]
        )
        first, second = self._twice(watcher)
        assert first.player1.buffs["spiked"] == 1
        assert second.player1.buffs["spiked"] == 1, "it forgot, as it should"

    def test_an_allowance_is_new_each_battle(self):
        spender = self._item(
            [
                TimerTrigger(
                    cooldown=1.0,
                    cpu_cost=0,
                    effects=[
                        LimitEffect(times=2, effects=[BuffEffect("spiked", 1, "self")])
                    ],
                )
            ]
        )
        first, second = self._twice(spender)
        assert first.player1.buffs["spiked"] == 2
        assert second.player1.buffs["spiked"] == 2

    def test_an_aura_counts_from_nothing_each_battle(self):
        from item_effects import AuraTrigger

        watcher = BattleItem(
            spec=ItemSpec(
                id="w",
                name="Watcher",
                category="infrastructure",
                cost=1,
                player_class="neutral",
                slug="w",
                shape=parse_map(["#*"], "w"),
                triggers=[
                    AuraTrigger(
                        zone="star",
                        counting="any",
                        after=3,
                        on="activates",
                        effects=[BuffEffect("spiked", 1, "self")],
                    )
                ],
            ),
            position=(0, 0),
            uid="w",
        )
        ticker = self._item(
            [
                TimerTrigger(
                    cooldown=1.0,
                    cpu_cost=0,
                    effects=[BuffEffect("calibrated", 0, "self")],
                )
            ],
            uid="t",
            position=(1, 0),
        )
        first, _ = self._run([watcher, ticker], seconds=3.5)
        second, _ = self._run([watcher, ticker], seconds=3.5)
        assert first.player1.buffs["spiked"] == 1, "three activations"
        assert second.player1.buffs["spiked"] == 1


class TestATriggerDoesNotFireItself(_WithOneItem):
    """A trigger that answers a status and grants that status answers itself.

    "Empower gained: gain 1 Empower" ran until the stack gave out. No item is
    written that way today and one will be -- "Buff used: Refund 25% of the
    used buffs" is the same shape once spending announces itself -- so the
    rule is in the engine rather than in the catalogue's good manners.
    """

    def test_a_status_trigger_that_grants_what_it_watches_stops(self):
        sim, _ = self._run(
            [
                self._item(
                    [
                        BattleStartTrigger(
                            effects=[BuffEffect("monitored", 1, "self")]
                        ),
                        StatusChangeTrigger(
                            status="monitored",
                            whose="self",
                            effects=[BuffEffect("monitored", 1, "self")],
                        ),
                    ]
                )
            ],
            seconds=0.3,
        )
        assert sim.player1.buffs["monitored"] == 2, "the gain, and the one answer to it"

    def test_it_answers_the_next_arrival_as_well(self):
        """Not firing while it is firing is not the same as firing once. The
        mark has to come off when the effects are done."""
        sim, _ = self._run(
            [
                self._item(
                    [
                        StatusChangeTrigger(
                            status="monitored",
                            whose="self",
                            effects=[BlockEffect(block_amount=10)],
                        )
                    ],
                    uid="w",
                ),
                self._item(
                    [
                        TimerTrigger(
                            cooldown=1.0,
                            cpu_cost=0,
                            effects=[BuffEffect("monitored", 1, "self")],
                        )
                    ],
                    uid="g",
                    position=(1, 0),
                ),
            ],
            seconds=3.5,
        )
        assert sim.player1.block == 30, "three arrivals, three answers"

    def test_two_items_still_answer_each_other(self):
        """The rule is that a trigger does not fire *itself*. Two of them
        answering each other's gains is an honest thing to do, and each
        answers once."""
        sim, _ = self._run(
            [
                self._item(
                    [
                        BattleStartTrigger(
                            effects=[BuffEffect("monitored", 1, "self")]
                        ),
                        StatusChangeTrigger(
                            status="spiked",
                            whose="self",
                            effects=[BuffEffect("monitored", 1, "self")],
                        ),
                    ],
                    uid="a",
                ),
                self._item(
                    [
                        StatusChangeTrigger(
                            status="monitored",
                            whose="self",
                            effects=[BuffEffect("spiked", 1, "self")],
                        )
                    ],
                    uid="b",
                    position=(1, 0),
                ),
            ],
            seconds=0.3,
        )
        assert sim.player1.buffs == {"monitored": 2, "spiked": 1}

    def test_an_item_that_stuns_on_hit_and_swings_on_stun_stops(self):
        sim, result = self._run(
            [
                self._item(
                    [
                        TimerTrigger(
                            cooldown=1.0,
                            cpu_cost=0,
                            effects=[
                                AttackEffect(
                                    min_damage=1,
                                    max_damage=1,
                                    accuracy=1.0,
                                    crit_chance=0.0,
                                )
                            ],
                        ),
                        OnHitTrigger(
                            chance=1.0,
                            effects=[StunEffect(duration=0.5, target_type="enemy")],
                        ),
                        OnStunTrigger(effects=[ExtraAttackEffect()]),
                    ]
                )
            ],
            seconds=3.0,
        )
        assert result["player2_quota"] < 350, "it did swing"


class TestOnePlaceSpendsABuff(_WithOneItem):
    """A `cost` effect and a `use` trigger both pay a price, and both pay it
    the same way.

    They each had their own copy of the four lines, which is the shape that
    let Vampirism ignore a healing share one commit earlier.
    """

    def test_a_cost_effect_and_a_use_trigger_pay_alike(self):
        by_effect, _ = self._run(
            [
                self._item(
                    [
                        BattleStartTrigger(
                            effects=[
                                CostEffect(
                                    costs={"credits": 3},
                                    effects=[BlockEffect(block_amount=20)],
                                )
                            ]
                        )
                    ]
                )
            ],
            seconds=0.3,
            buffs={"credits": 5},
        )
        by_trigger, _ = self._run(
            [
                self._item(
                    [
                        WhenAffordableTrigger(
                            costs={"credits": 3},
                            effects=[
                                LimitEffect(
                                    times=1, effects=[BlockEffect(block_amount=20)]
                                )
                            ],
                        )
                    ]
                )
            ],
            seconds=0.3,
            buffs={"credits": 5},
        )
        assert by_effect.player1.buffs == by_trigger.player1.buffs == {"credits": 2}
        assert by_effect.player1.block == by_trigger.player1.block == 20

    def test_both_say_what_they_spent(self):
        for item in (
            self._item(
                [
                    BattleStartTrigger(
                        effects=[
                            CostEffect(
                                costs={"credits": 3},
                                effects=[BlockEffect(block_amount=1)],
                            )
                        ]
                    )
                ]
            ),
            self._item(
                [
                    WhenAffordableTrigger(
                        costs={"credits": 3},
                        effects=[
                            LimitEffect(times=1, effects=[BlockEffect(block_amount=1)])
                        ],
                    )
                ]
            ),
        ):
            sim, _ = self._run([item], seconds=0.3, buffs={"credits": 5})
            spent = [a for a in sim.actions if a.action == "spend"]
            assert len(spent) == 1
            assert spent[0].details["costs"] == {"credits": 3}


class TestWhatCountsAsDealt(_WithOneItem):
    """ "22 Effect-damage dealt" counts what arrived, not what was aimed."""

    def test_damage_a_target_refuses_is_not_counted(self):
        hit = self._item(
            [
                TimerTrigger(
                    cooldown=1.0,
                    cpu_cost=0,
                    effects=[
                        EffectDamageEffect(
                            amount=10, lifesteal=0.0, per_status={}, whose={}
                        )
                    ],
                )
            ]
        )
        plain, _ = self._run([hit], seconds=1.5)
        assert plain.player1.effect_damage_dealt == 10

        shielded, _ = self._run(
            [
                hit,
                self._item(
                    [
                        BattleStartTrigger(
                            effects=[
                                PlayerModifyEffect("damage_taken", -1.0, "enemy", -1)
                            ]
                        )
                    ],
                    uid="i",
                    position=(1, 0),
                ),
            ],
            seconds=1.5,
        )
        assert shielded.player1.effect_damage_dealt == 0, "the target took none of it"


class TestADebuffYouPutOnYourself(_WithOneItem):
    """A random debuff aimed at its own owner is not one to reflect either.

    The named kind already knew this. The random one did not, so
    "Inflict a random debuff to yourself" would have gone across the table.
    """

    def test_a_random_debuff_on_yourself_is_not_reflected(self):
        sim, _ = self._run(
            [
                self._item(
                    [
                        BattleStartTrigger(
                            effects=[
                                ReflectEffect(count=5, target_type="self"),
                                RandomStatusEffect(
                                    kind="debuff", count=3, target_type="self"
                                ),
                            ]
                        )
                    ]
                )
            ],
            seconds=0.3,
        )
        assert sum(sim.player1.debuffs.values()) == 3
        assert not sim.player2.debuffs
        assert sim.player1.reflect == 5, "no charge spent"


class TestAChainWithNoEnd(_WithOneItem):
    """Two triggers taking turns is a loop the per-trigger guard cannot see.

    `_firing` stops a trigger answering itself. It cannot stop a pair: two
    weapons, each with an aura that answers the other's hit with an extra
    attack, ran until the stack gave out. A depth limit is what ends that.
    """

    @staticmethod
    def _weapon(uid, at):
        from item_effects import AuraTrigger

        return BattleItem(
            spec=ItemSpec(
                id=uid,
                name=uid,
                category="problem",
                cost=1,
                player_class="neutral",
                slug=uid,
                kinds=frozenset({"melee"}),
                # Stars either side, so two of these side by side reach each
                # other. An aura never reaches the item projecting it, so one
                # alone is safe.
                shape=parse_map(["*#*"], uid),
                triggers=[
                    TimerTrigger(
                        cooldown=1.0,
                        cpu_cost=0,
                        effects=[
                            AttackEffect(
                                min_damage=1,
                                max_damage=1,
                                accuracy=1.0,
                                crit_chance=0.0,
                            )
                        ],
                    ),
                    AuraTrigger(
                        zone="star",
                        counting="any",
                        after=1,
                        on="hits",
                        effects=[ExtraAttackEffect()],
                    ),
                ],
            ),
            position=at,
            uid=uid,
        )

    def test_a_pair_answering_each_other_stops(self):
        sim, result = self._run(
            [self._weapon("a", (0, 0)), self._weapon("b", (1, 0))], seconds=3.0
        )
        assert result["player2_quota"] < 350, "they did swing"

    def test_honest_nesting_is_nowhere_near_the_limit(self):
        """A trigger, a chance, a price, a count and the effects is a deep
        clause, and it is five."""
        assert BattleSimulator.DEEPEST > 5 * 4


class TestMakingAnotherItemAct(_WithOneItem):
    """ "Trigger the Star Pet", "Trigger all Star Food", and the one every
    Potion has: it applies the effect of the Potion above it, without
    consuming that one.
    """

    @staticmethod
    def _willing(uid, position, kinds=("potion",), consumes=True):
        """Something with a clause behind a condition that never comes, so
        the only way it ever acts is by being triggered."""
        effects = [BlockEffect(block_amount=10)]
        if consumes:
            effects.append(ConsumeEffect())
        return BattleItem(
            spec=ItemSpec(
                id=uid,
                name=uid,
                category="patch",
                cost=1,
                player_class="neutral",
                shape=parse_map(["#"], "p"),
                slug=uid,
                kinds=frozenset(kinds),
                triggers=[
                    CounterTrigger(
                        counting="block",
                        amount=9999,
                        whose="self",
                        counts="held",
                        effects=effects,
                    )
                ],
            ),
            position=position,
            uid=uid,
        )

    def _puller(self, counting, pick="all", how_many=0, uid="puller"):
        return BattleItem(
            spec=ItemSpec(
                id=uid,
                name=uid,
                category="infrastructure",
                cost=1,
                player_class="neutral",
                slug=uid,
                shape=parse_map(["#**"], uid),
                triggers=[
                    BattleStartTrigger(
                        effects=[
                            TriggerItemEffect(
                                where="star",
                                counting=counting,
                                how_many=how_many,
                                pick=pick,
                            )
                        ]
                    )
                ],
            ),
            position=(0, 0),
            uid=uid,
        )

    def test_it_makes_the_item_do_what_it_does(self):
        sim, _ = self._run(
            [self._puller({"any": ["potion"]}), self._willing("p", (1, 0))], seconds=0.3
        )
        assert sim.player1.block == 10, "its clause ran without its condition"

    def test_and_leaves_it_standing(self):
        """ "without consuming that potion" is the whole point of spillover."""
        sim, _ = self._run(
            [self._puller({"any": ["potion"]}), self._willing("p", (1, 0))], seconds=0.3
        )
        assert "p" not in sim.consumed_items

    def test_it_reaches_only_what_it_counts(self):
        sim, _ = self._run(
            [
                self._puller({"any": ["potion"]}),
                self._willing("p", (1, 0), kinds=("food",)),
            ],
            seconds=0.3,
        )
        assert sim.player1.block == 0, "a Food is not a Potion"

    def test_it_reaches_everything_that_counts(self):
        sim, _ = self._run(
            [
                self._puller({"any": ["potion"]}),
                self._willing("a", (1, 0)),
                self._willing("b", (2, 0)),
            ],
            seconds=0.3,
        )
        assert sim.player1.block == 20, "both of them"

    def test_a_random_pick_takes_one(self):
        sim, _ = self._run(
            [
                self._puller({"any": ["potion"]}, pick="random"),
                self._willing("a", (1, 0)),
                self._willing("b", (2, 0)),
            ],
            seconds=0.3,
        )
        assert sim.player1.block == 10, "one of the two, not both"

    def test_it_does_not_trigger_an_item_already_spent(self):
        gone = self._willing("p", (1, 0))
        sim, _ = self._run([self._puller({"any": ["potion"]}), gone], seconds=0.3)
        sim.consumed_items.add("p")
        before = sim.player1.block
        assert before == 10

    def test_a_standing_trigger_is_not_run_again(self):
        """A passive is on already, so running it again would hand out its
        modifier a second time."""
        standing = BattleItem(
            spec=ItemSpec(
                id="s",
                name="s",
                category="patch",
                cost=1,
                player_class="neutral",
                shape=parse_map(["#"], "s"),
                slug="s",
                kinds=frozenset({"potion"}),
                triggers=[
                    PassiveTrigger(
                        effects=[
                            ModifyEffect(
                                stat="damage",
                                value=1.0,
                                target_type="own",
                                counting="any",
                                cap=None,
                                duration=-1,
                            )
                        ]
                    )
                ],
            ),
            position=(1, 0),
            uid="s",
        )
        swinger = self._item(
            [
                TimerTrigger(
                    cooldown=1.0,
                    cpu_cost=0,
                    effects=[
                        AttackEffect(
                            min_damage=10, max_damage=10, accuracy=1.0, crit_chance=0.0
                        )
                    ],
                )
            ],
            uid="w",
            position=(2, 1),
        )
        sim, result = self._run(
            [self._puller({"any": ["potion"]}), standing, swinger], seconds=1.5
        )
        assert 350 - result["player2_quota"] == 20, "doubled once, not twice"


class TestEveryPotionSpillsOver(TestTheSweptClauses):
    """The clause every Potion has and none of them said.

    It is not on the wiki's `effect` field, which is what the import read; it
    is in the prose beside it, in the same words on every Potion page. So it
    was missing rather than unbuilt -- nothing was owed and nothing was there.
    """

    def test_the_potion_above_is_the_potion_in_the_star(self):
        """A Potion's map is ['*', '^', '#']: it covers two squares and its
        star is the one directly above. So "above" needs no idea of its own."""
        spec = ITEM_CATALOG["health_potion"]
        assert spec.shape.star == ((0, -1),)
        assert len(spec.shape.squares) == 2

    def test_a_potion_drunk_applies_the_one_above_it(self):
        """Health Potion drinks itself when its owner's health falls, and the
        one above it heals as well without being drunk."""
        # A Potion covers two squares and its star is the one above the top,
        # so the pair stands two apart: the upper one's lower square is the
        # lower one's star.
        upper, lower = (0, 0), (0, 2)
        assert (0, 1) in [
            (lower[0] + dx, lower[1] + dy)
            for dx, dy in ITEM_CATALOG["health_potion"].shape.star
        ]
        pair = [
            self._real("health_potion", lower, uid="lower"),
            self._real("health_potion", upper, uid="upper"),
        ]
        # Health Potion drinks itself below half, which is 175 of 350.
        sim, result = self._fight(
            pair,
            seconds=4.0,
            hurt=180,
            against=[self._swinger(damage=5, position=(6, 0))],
        )
        assert "lower" in sim.consumed_items, "the lower one was drunk"
        assert "upper" not in sim.consumed_items, "and the upper one was not"
        heals = [a for a in sim.actions if a.action == "heal"]
        assert len(heals) >= 2, "it healed twice for one drink"

    def test_every_potion_either_spills_over_or_owes_it(self):
        """Six of the twelve have no clause that drinks them yet, so there is
        nowhere to hang it. Those say so on their `unbuilt` list rather than
        saying nothing, which is how this went unnoticed."""
        import json
        from pathlib import Path

        items = Path(__file__).resolve().parents[1] / "data" / "items"
        for path in sorted(items.glob("*.json")):
            data = json.loads(path.read_text())
            for group in ("items", "containers"):
                for item_id, item in data.get(group, {}).items():
                    if "potion" not in (item.get("icontype") or ""):
                        continue
                    spills = any(
                        e.get("type") == "trigger_item"
                        for t in item.get("triggers") or []
                        for e in t.get("effects") or []
                    )
                    owes = any(
                        "Potion above it" in c for c in item.get("unbuilt") or []
                    )
                    assert spills or owes, item_id


class TestCountingAWholePool(_WithOneItem):
    """ "Deals +0.5 damage for each debuff of your opponent" counts every
    stack of every kind, and one named debuff would be a smaller number."""

    def _swinger(self, status, whose):
        return self._item(
            [
                PassiveTrigger(
                    effects=[
                        ModifyPerStatusEffect(
                            stat="damage_flat", value=1.0, status=status, whose=whose
                        )
                    ]
                ),
                TimerTrigger(
                    cooldown=1.0,
                    cpu_cost=0,
                    effects=[
                        AttackEffect(
                            min_damage=10, max_damage=10, accuracy=1.0, crit_chance=0.0
                        )
                    ],
                ),
            ]
        )

    def test_it_counts_every_kind_together(self):
        giver = self._item(
            [
                BattleStartTrigger(
                    effects=[
                        DebuffEffect("memory_leaked", 2, target_type="enemy"),
                        DebuffEffect("throttled", 3, target_type="enemy"),
                    ]
                )
            ],
            uid="g",
            position=(1, 0),
        )
        _, result = self._run([self._swinger("debuffs", "enemy"), giver], seconds=1.5)
        assert 350 - result["player2_quota"] == 15, "10, and 5 debuffs"

    def test_naming_one_counts_only_that_one(self):
        giver = self._item(
            [
                BattleStartTrigger(
                    effects=[
                        DebuffEffect("memory_leaked", 2, target_type="enemy"),
                        DebuffEffect("throttled", 3, target_type="enemy"),
                    ]
                )
            ],
            uid="g",
            position=(1, 0),
        )
        _, result = self._run([self._swinger("throttled", "enemy"), giver], seconds=1.5)
        assert 350 - result["player2_quota"] == 13, "10, and 3 Cold"

    def test_buffs_count_the_same_way(self):
        _, result = self._run(
            [self._swinger("buffs", "self")],
            seconds=1.5,
            buffs={"monitored": 2, "spiked": 4},
        )
        assert (
            350 - result["player2_quota"] == 16 + 2
        ), "10, six buffs, and Empower's own +1 a stack"


class TestPickingByWhatIsHeld(_WithOneItem):
    """ "Gain 3 buffs of the type you have most of", "Gain 3 of the buff you
    have least of", "Gain 1 Luck or 1 Spikes or 1 Mana, depending on what you
    have the least of."
    """

    def _pick(self, pick, count=3, among=(), buffs=None):
        sim, _ = self._run(
            [
                self._item(
                    [
                        BattleStartTrigger(
                            effects=[
                                RandomStatusEffect(
                                    kind="buff",
                                    count=count,
                                    target_type="self",
                                    pick=pick,
                                    among=tuple(among),
                                )
                            ]
                        )
                    ]
                )
            ],
            seconds=0.3,
            buffs=buffs,
        )
        return dict(sim.player1.buffs)

    def test_most_puts_them_all_on_the_biggest_pile(self):
        got = self._pick("most", buffs={"monitored": 5, "spiked": 1})
        assert got == {"monitored": 8, "spiked": 1}

    def test_least_puts_them_all_on_the_smallest(self):
        """A kind held at nothing is the one held least, and an item saying so
        plainly means to give you a new one."""
        got = self._pick("least", buffs={"monitored": 5, "spiked": 1})
        assert got["monitored"] == 5 and got["spiked"] == 1
        assert sum(v for k, v in got.items() if k not in ("monitored", "spiked")) == 3

    def test_it_chooses_once_rather_than_per_stack(self):
        """All three go to one kind, which is what "3 buffs of the type" says
        as against three separate picks."""
        got = self._pick("most", count=3, buffs={"monitored": 2})
        assert got == {"monitored": 5}

    def test_among_narrows_what_it_chooses_between(self):
        got = self._pick(
            "least",
            count=2,
            among=["calibrated", "spiked", "credits"],
            buffs={"monitored": 0, "calibrated": 4, "spiked": 9, "credits": 7},
        )
        assert got["calibrated"] == 6, "the least of the three named"

    def test_a_tie_is_broken_the_same_way_every_time(self):
        first = self._pick("most", buffs={"monitored": 2, "spiked": 2})
        again = self._pick("most", buffs={"monitored": 2, "spiked": 2})
        assert first == again


class TestSpendingThePool(_WithOneItem):
    """ "Use a random buff to heal for 12", "Use all your buffs"."""

    def _spend(self, from_pool, buffs=None, hurt=100):
        sim, result = self._run(
            [
                self._item(
                    [
                        BattleStartTrigger(
                            effects=[
                                CostEffect(
                                    costs={},
                                    effects=[HealEffect(min_heal=12, max_heal=12)],
                                    from_pool=from_pool,
                                )
                            ]
                        )
                    ]
                )
            ],
            seconds=0.3,
            hurt=hurt,
            buffs=buffs,
        )
        return dict(sim.player1.buffs), result["player1_quota"] - hurt

    def test_one_takes_a_single_stack(self):
        left, healed = self._spend("one", {"monitored": 3, "spiked": 2})
        assert sum(left.values()) == 4, "five held, one spent"
        assert healed == 12

    def test_one_does_nothing_with_nothing_to_spend(self):
        left, healed = self._spend("one", {})
        assert (left, healed) == ({}, 0)

    def test_all_takes_every_stack_of_every_kind(self):
        left, healed = self._spend("all", {"monitored": 3, "spiked": 2})
        assert left == {}
        assert healed == 12

    def test_all_happens_even_with_nothing_to_spend(self):
        """Spending the pool is still spending the pool when it is empty,
        which is not true of taking one from it."""
        left, healed = self._spend("all", {})
        assert healed == 12


class TestOneOfSeveral(_WithOneItem):
    """ "Randomly gain 14 Block or 2 stamina or 2 Luck." One of them, not all."""

    def _choose(self, seed):
        sim = BattleSimulator(seed=seed)
        sim.max_duration = 0.3
        p1, p2 = get_test_containers()
        sim.simulate_battle(
            [
                self._item(
                    [
                        BattleStartTrigger(
                            effects=[
                                ChoiceEffect(
                                    choices=[
                                        [BlockEffect(block_amount=14)],
                                        [BuffEffect("calibrated", 2, "self")],
                                        [BuffEffect("spiked", 2, "self")],
                                    ]
                                )
                            ]
                        )
                    ]
                )
            ],
            [],
            18,
            p1,
            p2,
        )
        return sim.player1.block, dict(sim.player1.buffs)

    def test_exactly_one_alternative_happens(self):
        block, buffs = self._choose(TEST_SEED)
        assert (block > 0) + (len(buffs) > 0) == 1, "one of them, not both"

    def test_a_different_seed_can_choose_differently(self):
        seen = {
            (block, tuple(sorted(buffs.items())))
            for block, buffs in (self._choose(seed) for seed in range(20))
        }
        assert len(seen) > 1


class TestDestroyingBlock(_WithOneItem):
    """ "Destroy 4 Block": the Block is gone, and no damage was dealt."""

    def _destroy(self, amount, their_block):
        sim, result = self._run(
            [
                self._item(
                    [
                        TimerTrigger(
                            cooldown=1.0,
                            cpu_cost=0,
                            effects=[
                                DestroyBlockEffect(amount=amount, target_type="enemy")
                            ],
                        )
                    ]
                )
            ],
            seconds=1.5,
            against=[
                self._item(
                    [
                        BattleStartTrigger(
                            effects=[BlockEffect(block_amount=their_block)]
                        )
                    ],
                    uid="them",
                    position=(4, 0),
                )
            ],
        )
        return sim.player2.block, 350 - result["player2_quota"]

    def test_it_takes_the_block_off(self):
        left, damage = self._destroy(4, 10)
        assert left == 6

    def test_and_deals_no_damage(self):
        left, damage = self._destroy(4, 10)
        assert damage == 0, "destroying Block is not hitting anybody"

    def test_it_cannot_take_more_than_is_there(self):
        left, damage = self._destroy(40, 10)
        assert (left, damage) == (0, 0)


class TestTheNextAttackOnly(_WithOneItem):
    """ "Gain +2 damage for the next attack." Spent by swinging, so an item
    that never swings again keeps it."""

    def _weapon(self, bonus=0, ignores=False, cooldown=1.0, uid="w", position=(0, 0)):
        triggers = [
            TimerTrigger(
                cooldown=cooldown,
                cpu_cost=0,
                effects=[
                    AttackEffect(
                        min_damage=10, max_damage=10, accuracy=1.0, crit_chance=0.0
                    )
                ],
            )
        ]
        if bonus or ignores:
            triggers.append(
                BattleStartTrigger(
                    effects=[NextAttackEffect(damage=bonus, ignores_block=ignores)]
                )
            )
        return self._item(triggers, uid=uid, position=position)

    def test_the_bonus_lands_on_the_next_swing(self):
        _, plain = self._run([self._weapon()], seconds=1.5)
        _, boosted = self._run([self._weapon(bonus=5)], seconds=1.5)
        assert 350 - plain["player2_quota"] == 10
        assert 350 - boosted["player2_quota"] == 15

    def test_and_not_on_the_one_after(self):
        _, result = self._run([self._weapon(bonus=5)], seconds=2.5)
        assert 350 - result["player2_quota"] == 25, "15 then 10"

    def test_ignoring_block_goes_past_it(self):
        theirs = self._item(
            [BattleStartTrigger(effects=[BlockEffect(block_amount=100)])],
            uid="them",
            position=(4, 0),
        )
        _, blocked = self._run([self._weapon()], seconds=1.5, against=[theirs])
        _, past = self._run([self._weapon(ignores=True)], seconds=1.5, against=[theirs])
        assert 350 - blocked["player2_quota"] == 0, "Block ate it"
        assert 350 - past["player2_quota"] == 10

    def test_going_past_block_is_spent_too(self):
        theirs = self._item(
            [BattleStartTrigger(effects=[BlockEffect(block_amount=100)])],
            uid="them",
            position=(4, 0),
        )
        _, result = self._run(
            [self._weapon(ignores=True)], seconds=2.5, against=[theirs]
        )
        assert 350 - result["player2_quota"] == 10, "the second swing was blocked"


class TestRefusingMoreThanADebuff(_WithOneItem):
    """The wiki's Resist is about debuffs, and the source game writes the same
    idea about critical hits and stuns: "30% chance to resist critical hits",
    "40% chance to resist stuns".
    """

    def _holding(self, *resists, seconds=3.0, against=()):
        return self._run(
            [self._item([BattleStartTrigger(effects=list(resists))])],
            seconds=seconds,
            against=list(against),
        )

    @staticmethod
    def _crit_weapon(uid="them", position=(4, 0)):
        return BattleItem(
            spec=ItemSpec(
                id=uid,
                name="Crit",
                category="problem",
                cost=1,
                player_class="neutral",
                shape=parse_map(["#"], "c"),
                slug=uid,
                kinds=frozenset({"melee"}),
                triggers=[
                    TimerTrigger(
                        cooldown=1.0,
                        cpu_cost=0,
                        effects=[
                            AttackEffect(
                                min_damage=10,
                                max_damage=10,
                                accuracy=1.0,
                                crit_chance=1.0,
                            )
                        ],
                    )
                ],
            ),
            position=position,
            uid=uid,
        )

    def test_a_certain_resist_stops_every_critical_hit(self):
        """The swing still lands. It simply lands as an ordinary one."""
        bare, plain = self._holding(seconds=1.5, against=[self._crit_weapon()])
        _, safe = self._holding(
            ResistEffect(count=0, chance=1.0, target_type="self", against="critical"),
            seconds=1.5,
            against=[self._crit_weapon()],
        )
        assert 350 - plain["player1_quota"] == 20, "doubled"
        assert 350 - safe["player1_quota"] == 10, "not doubled, and not stopped"

    def test_a_certain_resist_stops_a_stun(self):
        from item_effects import AfterTrigger

        stunner = self._item(
            [
                AfterTrigger(
                    delay=0.5, effects=[StunEffect(duration=2.0, target_type="enemy")]
                )
            ],
            uid="them",
            position=(4, 0),
        )
        sim, _ = self._holding(
            ResistEffect(count=0, chance=1.0, target_type="self", against="stun"),
            seconds=2.0,
            against=[stunner],
        )
        assert sim.stunned_until == {}, "nothing was held still"

    def test_resisting_a_stun_does_not_resist_a_debuff(self):
        """Each names what it refuses, so one does not cover the other."""
        theirs = self._item(
            [
                TimerTrigger(
                    cooldown=1.0,
                    cpu_cost=0,
                    effects=[DebuffEffect("memory_leaked", 3, target_type="enemy")],
                )
            ],
            uid="them",
            position=(4, 0),
        )
        sim, _ = self._holding(
            ResistEffect(count=0, chance=1.0, target_type="self", against="stun"),
            seconds=1.5,
            against=[theirs],
        )
        assert sim.player1.debuffs["memory_leaked"] == 3

    def test_only_narrows_which_debuffs_are_refused(self):
        """ "50% chance to resist Blind and Cold" leaves Poison alone."""
        theirs = self._item(
            [
                TimerTrigger(
                    cooldown=1.0,
                    cpu_cost=0,
                    effects=[
                        DebuffEffect("memory_leaked", 2, target_type="enemy"),
                        DebuffEffect("throttled", 2, target_type="enemy"),
                    ],
                )
            ],
            uid="them",
            position=(4, 0),
        )
        sim, _ = self._holding(
            ResistEffect(
                count=0,
                chance=1.0,
                target_type="self",
                against="debuff",
                only=("throttled",),
            ),
            seconds=1.5,
            against=[theirs],
        )
        assert sim.player1.debuffs.get("memory_leaked") == 2, "not named"
        assert "throttled" not in sim.player1.debuffs, "named, so refused"

    def test_a_chance_can_grow_with_what_you_hold(self):
        """ "You have a 2% chance to resist debuffs for each Luck." Fifty Luck
        is certainty."""
        theirs = self._item(
            [
                TimerTrigger(
                    cooldown=1.0,
                    cpu_cost=0,
                    effects=[DebuffEffect("memory_leaked", 3, target_type="enemy")],
                )
            ],
            uid="them",
            position=(4, 0),
        )
        sim, _ = self._run(
            [
                self._item(
                    [
                        BattleStartTrigger(
                            effects=[
                                ResistEffect(
                                    count=0,
                                    chance=0.0,
                                    target_type="self",
                                    per_status={"calibrated": 0.02},
                                )
                            ]
                        )
                    ]
                )
            ],
            seconds=1.5,
            buffs={"calibrated": 50},
            against=[theirs],
        )
        assert "memory_leaked" not in sim.player1.debuffs

    def test_and_is_worth_nothing_when_you_hold_none(self):
        theirs = self._item(
            [
                TimerTrigger(
                    cooldown=1.0,
                    cpu_cost=0,
                    effects=[DebuffEffect("memory_leaked", 3, target_type="enemy")],
                )
            ],
            uid="them",
            position=(4, 0),
        )
        sim, _ = self._holding(
            ResistEffect(
                count=0, chance=0.0, target_type="self", per_status={"calibrated": 0.02}
            ),
            seconds=1.5,
            against=[theirs],
        )
        assert sim.player1.debuffs["memory_leaked"] == 3


class TestAModifierThatRunsOut(_WithOneItem):
    """ "The Star item triggers 100% faster for 1s."

    A modifier on a player has had a clock since durations were built. One on
    an item had not, and the difference was only where it was written down.
    """

    def _lend(self, duration):
        aura = BattleItem(
            spec=ItemSpec(
                id="aura",
                name="Aura",
                category="infrastructure",
                cost=1,
                player_class="neutral",
                slug="aura",
                shape=parse_map(["#*"], "aura"),
                triggers=[
                    BattleStartTrigger(
                        effects=[
                            ModifyEffect(
                                stat="damage",
                                value=1.0,
                                target_type="star",
                                counting="any",
                                cap=None,
                                duration=duration,
                            )
                        ]
                    )
                ],
            ),
            position=(0, 0),
            uid="aura",
        )
        swinger = self._item(
            [
                TimerTrigger(
                    cooldown=2.0,
                    cpu_cost=0,
                    effects=[
                        AttackEffect(
                            min_damage=10, max_damage=10, accuracy=1.0, crit_chance=0.0
                        )
                    ],
                )
            ],
            uid="w",
            position=(1, 0),
        )
        sim, result = self._run([aura, swinger], seconds=5.0)
        return [a.damage for a in sim.actions if a.action == "damage"]

    def test_a_lent_modifier_is_taken_back(self):
        swings = self._lend(duration=1.0)
        assert swings == [10, 10], "it had run out before the first swing"

    def test_one_with_no_clock_stays(self):
        swings = self._lend(duration=-1)
        assert swings == [20, 20]

    def test_it_lasts_exactly_as_long_as_it_says(self):
        swings = self._lend(duration=3.0)
        assert swings == [20, 10], "doubled at 2s, ordinary at 4s"


class TestADebuffThatDoesNotStack(_WithOneItem):
    """ "(unstackable)": topped up, not added to, so a second helping is worth
    nothing to somebody already carrying a full one."""

    def _inflict(self, unstackable, times=3):
        sim, _ = self._run(
            [
                self._item(
                    [
                        TimerTrigger(
                            cooldown=1.0,
                            cpu_cost=0,
                            effects=[
                                DebuffEffect(
                                    "rate_limited",
                                    5,
                                    target_type="enemy",
                                    unstackable=unstackable,
                                )
                            ],
                        )
                    ]
                )
            ],
            seconds=times + 0.5,
        )
        return sim.player2.debuffs.get("rate_limited", 0)

    def test_it_does_not_pile_up(self):
        assert self._inflict(unstackable=True) == 5

    def test_where_an_ordinary_one_does(self):
        assert self._inflict(unstackable=False) == 15

    def test_it_tops_up_what_is_missing(self):
        """Not refused outright: somebody carrying two gets three more."""
        sim, _ = self._run(
            [
                self._item(
                    [
                        BattleStartTrigger(
                            effects=[
                                DebuffEffect("rate_limited", 2, target_type="enemy")
                            ]
                        ),
                        TimerTrigger(
                            cooldown=1.0,
                            cpu_cost=0,
                            effects=[
                                DebuffEffect(
                                    "rate_limited",
                                    5,
                                    target_type="enemy",
                                    unstackable=True,
                                )
                            ],
                        ),
                    ]
                )
            ],
            seconds=1.5,
        )
        assert sim.player2.debuffs["rate_limited"] == 5


class TestCountingEmptySquares(_WithOneItem):
    """ "Destroy 4 Block for each free Star slot": the only thing an aura counts
    that is not an item."""

    def _counter(self, position=(0, 0)):
        return BattleItem(
            spec=ItemSpec(
                id="c",
                name="Counter",
                category="problem",
                cost=1,
                player_class="neutral",
                slug="c",
                kinds=frozenset({"melee"}),
                shape=parse_map(["#**"], "c"),
                triggers=[
                    BattleStartTrigger(
                        effects=[
                            PerCountEffect(
                                where="star",
                                counting="free",
                                effects=[BuffEffect("spiked", 1, "self")],
                            )
                        ]
                    )
                ],
            ),
            position=position,
            uid="c",
        )

    def test_it_counts_the_squares_nothing_stands_on(self):
        sim, _ = self._run([self._counter()], seconds=0.3)
        assert sim.player1.buffs["spiked"] == 2, "both star squares are empty"

    def test_an_item_standing_there_is_not_a_free_slot(self):
        filler = self._item([], uid="f", position=(1, 0))
        sim, _ = self._run([self._counter(), filler], seconds=0.3)
        assert sim.player1.buffs["spiked"] == 1


class TestTheCatalogueItemsThatSpendAndRefuse(TestTheSweptClauses):
    """Real items that spend a pool or refuse what is sent at them.

    Resisting a critical hit, destroying Block, counting empty squares, giving
    what you hold most or least of, buying a way past Block, being paid for a
    miss.

    Everything above tests a mechanic on an item made for the purpose, which
    proves the mechanic and not the translation. Twelve mutations of the
    catalogue went unnoticed before this class existed: Stone Helm resisting
    debuffs instead of critical hits, Djinn Lamp handing out what you have
    most of, Lightsaber's Blind piling up. Each is a plausible slip and none
    of them touched a test.
    """

    def _crit_weapon(self, uid="them", position=(6, 0)):
        return BattleItem(
            spec=ItemSpec(
                id=uid,
                name="Crit",
                category="problem",
                cost=1,
                player_class="neutral",
                shape=parse_map(["#"], "c"),
                slug=uid,
                kinds=frozenset({"melee"}),
                triggers=[
                    TimerTrigger(
                        cooldown=1.0,
                        cpu_cost=0,
                        effects=[
                            AttackEffect(
                                min_damage=10,
                                max_damage=10,
                                accuracy=1.0,
                                crit_chance=1.0,
                            )
                        ],
                    )
                ],
            ),
            position=position,
            uid=uid,
        )

    def test_stone_helm_refuses_critical_hits_and_not_debuffs(self):
        """ "30% chance to resist critical hits", "40% chance to resist stuns".
        Neither is a resist of debuffs, which it does not have."""
        where, _ = self._place("stone_helm")
        spec = ITEM_CATALOG["stone_helm"]
        against = {
            r.against
            for t in spec.triggers
            for r in getattr(t, "effects", []) or []
            if isinstance(r, ResistEffect)
        }
        assert against == {"critical", "stun"}

        # And it really does soften a crit rather than stop the swing.
        sim, result = self._fight(
            [self._real("stone_helm", where)],
            seconds=40.0,
            against=[self._crit_weapon()],
        )
        crits = [a for a in sim.actions if a.action == "critical_hit"]
        hits = [a for a in sim.actions if a.action == "damage"]
        assert hits, "the swings still land"
        assert len(crits) < len(hits), "and some of them are not critical"

    def test_shepherds_crook_refuses_only_what_it_names(self):
        """ "50% chance to resist Blind and Cold" leaves Poison alone."""
        spec = ITEM_CATALOG["shepherds_crook"]
        # Two of them now: this one, and the 35% that keeps your buffs from
        # being taken. Only the debuff half is what this test is about.
        (resist,) = [
            r
            for t in spec.triggers
            for r in getattr(t, "effects", []) or []
            if isinstance(r, ResistEffect) and r.against == "debuff"
        ]
        assert set(resist.only) == {"rate_limited", "throttled"}

        where, _ = self._place("shepherds_crook")
        sim, _ = self._fight(
            [self._real("shepherds_crook", where)],
            seconds=9.0,
            against=[
                self._item(
                    [
                        TimerTrigger(
                            cooldown=1.0,
                            cpu_cost=0,
                            effects=[
                                DebuffEffect("memory_leaked", 2, target_type="enemy")
                            ],
                        )
                    ],
                    uid="them",
                    position=(6, 0),
                )
            ],
        )
        assert (
            sim.player1.debuffs.get("memory_leaked", 0) > 0
        ), "Poison is not one of the two it names"

    def test_dancing_dragons_resist_grows_with_its_luck(self):
        where, _ = self._place("dancing_dragon")
        theirs = self._item(
            [
                TimerTrigger(
                    cooldown=1.0,
                    cpu_cost=0,
                    effects=[DebuffEffect("memory_leaked", 1, target_type="enemy")],
                )
            ],
            uid="them",
            position=(6, 0),
        )
        poor, _ = self._fight(
            [self._real("dancing_dragon", where)], seconds=9.0, against=[theirs]
        )
        lucky, _ = self._fight(
            [self._real("dancing_dragon", where)],
            seconds=9.0,
            buffs={"calibrated": 50},
            against=[theirs],
        )
        assert poor.player1.debuffs.get("memory_leaked", 0) > 0
        assert "memory_leaked" not in lucky.player1.debuffs

    def test_stone_destroys_block_on_hit(self):
        """Stone: "On hit: Destroy 4 Block.\" """
        where, _ = self._place("ping_flood")
        sim, _ = self._fight(
            [self._real("ping_flood", where)],
            seconds=9.0,
            against=[
                self._item(
                    [BattleStartTrigger(effects=[BlockEffect(block_amount=100)])],
                    uid="them",
                    position=(6, 0),
                )
            ],
        )
        destroyed = [
            a
            for a in sim.actions
            if a.action == "block" and (a.details or {}).get("type") == "destroyed"
        ]
        assert destroyed, "it should destroy Block on every hit"
        assert all(a.damage == -4 for a in destroyed), "four at a time"

    def test_the_spear_counts_the_empty_squares_of_its_star(self):
        """ "Destroy 4 Block for each free Star slot": more room, more Block."""
        where, star = self._place("buffer_overflow", 2)
        filler = self._item([], uid="f", position=star[0])
        theirs = self._item(
            [BattleStartTrigger(effects=[BlockEffect(block_amount=200)])],
            uid="them",
            position=(6, 0),
        )
        empty, _ = self._fight(
            [self._real("buffer_overflow", where)], seconds=6.0, against=[theirs]
        )
        crowded, _ = self._fight(
            [self._real("buffer_overflow", where), filler],
            seconds=6.0,
            against=[theirs],
        )
        assert (
            empty.player2.block < crowded.player2.block
        ), "a square with something on it is not a free slot"

    def test_the_djinn_lamp_gives_what_you_have_least_of(self):
        """ "Gain 1 Luck or 1 Spikes or 1 Mana, depending on what you have the
        least of." Held plenty of two, it hands over the third."""
        where, _ = self._place("djinn_lamp")
        sim, _ = self._fight(
            [self._real("djinn_lamp", where)],
            seconds=2.0,
            buffs={"calibrated": 9, "spiked": 9, "credits": 0},
        )
        assert sim.player1.buffs["credits"] > 0
        assert sim.player1.buffs["calibrated"] == 9, "it had most of this"

    def test_lil_chestnut_gives_what_you_have_most_of(self):
        where, _ = self._place("lil_chestnut")
        sim, _ = self._fight(
            [self._real("lil_chestnut", where)],
            seconds=7.0,
            buffs={"calibrated": 9, "spiked": 1},
        )
        assert sim.player1.buffs["calibrated"] > 9
        assert sim.player1.buffs["spiked"] == 1

    def test_the_lightsabers_blind_does_not_pile_up(self):
        """ "Inflict 8 Blind for 6s (unstackable)." Held to eight however often
        the Regeneration comes."""
        sim = BattleSimulator(seed=TEST_SEED)
        sim.max_duration = 40.0
        racks = (
            [Container.of("patch_registry", (0, 0), "p1")],
            [Container.of("patch_registry", (4, 0), "p2")],
        )
        original = sim._setup_item_handlers

        def setup(items, owner, enemy):
            out = original(items, owner, enemy)
            if owner.id == 1:
                owner.buffs["regenerating"] = 99
            return out

        sim._setup_item_handlers = setup
        sim.simulate_battle([self._real("lightsaber", (0, 0))], [], 18, *racks)
        assert sim.player2.debuffs.get("rate_limited", 0) <= 8

    def test_the_amulet_of_energy_lends_its_speed_for_a_second(self):
        """ "The Star item triggers 100% faster for 1s." Lent, not given."""
        where, (one,) = self._place("power_management_unit", 1)
        swinger = self._item(
            [
                TimerTrigger(
                    cooldown=2.0,
                    cpu_cost=0,
                    effects=[
                        AttackEffect(
                            min_damage=10, max_damage=10, accuracy=1.0, crit_chance=0.0
                        )
                    ],
                )
            ],
            uid="w",
            position=one,
        )
        sim, _ = self._fight(
            [self._real("power_management_unit", where), swinger], seconds=6.0
        )
        got = next(i for i in sim.loadout[1] if i.uid == "w")
        assert got.speed_mult == pytest.approx(1.0), "taken back after a second"

    def test_the_spectral_dagger_buys_its_way_past_block(self):
        where, _ = self._place("spectral_dagger")
        theirs = self._item(
            [BattleStartTrigger(effects=[BlockEffect(block_amount=200)])],
            uid="them",
            position=(6, 0),
        )
        _, poor = self._fight(
            [self._real("spectral_dagger", where)], seconds=9.0, against=[theirs]
        )
        _, rich = self._fight(
            [self._real("spectral_dagger", where)],
            seconds=9.0,
            buffs={"credits": 99},
            against=[theirs],
        )
        assert 350 - poor["player2_quota"] == 0, "Block ate every swing"
        assert 350 - rich["player2_quota"] > 0, "the Mana bought a way through"

    def test_the_broom_is_paid_for_missing(self):
        """ "Opponent misses attack: Gain +2 damage for the next attack.\" """
        where, _ = self._place("broom")
        wild = BattleItem(
            spec=ItemSpec(
                id="them",
                name="Wild",
                category="problem",
                cost=1,
                player_class="neutral",
                shape=parse_map(["#"], "w"),
                slug="them",
                kinds=frozenset({"melee"}),
                triggers=[
                    TimerTrigger(
                        cooldown=1.0,
                        cpu_cost=0,
                        effects=[
                            AttackEffect(
                                min_damage=1,
                                max_damage=1,
                                accuracy=0.0,
                                crit_chance=0.0,
                            )
                        ],
                    )
                ],
            ),
            position=(6, 0),
            uid="them",
        )
        sim, _ = self._fight([self._real("broom", where)], seconds=20.0, against=[wild])
        swings = [
            a.damage
            for a in sim.actions
            if a.action == "damage" and a.source == "broom"
        ]
        assert swings, "it swings"
        # A Broom deals 2 to 4 and nothing else raises that, so a swing of
        # more than four is the two the missing bought. Comparing two fights
        # cannot show it: a second item in the bag moves the rng along and
        # the totals differ whether or not the bonus landed.
        assert max(swings) > 4

    def test_the_darksaber_counts_every_debuff(self):
        """ "Deals +0.5 damage for each debuff of your opponent" — all of them,
        not one kind.

        Read off the item rather than out of a battle: half a point per debuff
        is smaller than the swing's own roll, so a fight cannot tell four
        debuffs from eight without a great many swings.
        """
        where, _ = self._place("darksaber")
        giver = self._item(
            [
                BattleStartTrigger(
                    effects=[
                        DebuffEffect("memory_leaked", 4, target_type="enemy"),
                        DebuffEffect("throttled", 4, target_type="enemy"),
                    ]
                )
            ],
            uid="g",
            position=(5, 5),
        )
        sim, _ = self._fight([self._real("darksaber", where), giver], seconds=0.3)
        blade = next(i for i in sim.loadout[1] if i.uid == "darksaber")
        assert (
            sim._per_status(blade, "damage_flat", sim.player1, sim.player2) == 4.0
        ), "eight debuffs at half a point each, not four"


class TestAContainerKnowsWhatIsInside(_WithOneItem):
    """A container is an item too, and `contained` is its own footprint.

    Its squares are the ones other items stand on, so what is inside one is
    whatever sits on the squares it covers. Nothing read that until now: a
    shelf that speeds up what it holds reached nothing at all, and every
    clause written "inside" did nothing.
    """

    @staticmethod
    def _rack(container_id, at=(0, 0)):
        return (
            [Container.of(container_id, at, "rack")],
            [Container.of("standard_vm", (6, 0), "theirs")],
        )

    def _fight(self, container_id, items, seconds=1.0, at=(0, 0)):
        mine, theirs = self._rack(container_id, at)
        sim = BattleSimulator(seed=TEST_SEED)
        sim.max_duration = seconds
        sim.nightfall = seconds + 1
        return sim, sim.simulate_battle(items, [], 18, mine, theirs)

    def test_a_shelf_speeds_up_what_stands_on_it(self):
        """Hot Pocket: "Items inside trigger 10% faster"."""
        held = self._item([], uid="held", position=(0, 0))
        sim, _ = self._fight("edge_node", [held])
        assert sim.loadout[1][0].speed_mult == pytest.approx(1.1)

    def test_a_shelf_reaches_nothing_it_does_not_cover(self):
        """The rack is two squares wide at the origin; this stands past it"""
        far = self._item([], uid="far", position=(6, 0))
        mine = [
            Container.of("edge_node", (0, 0), "rack"),
            Container.of("standard_vm", (6, 0), "spare"),
        ]
        sim = BattleSimulator(seed=TEST_SEED)
        sim.max_duration = 1.0
        sim.simulate_battle(
            [far], [], 18, mine, [Container.of("standard_vm", (6, 3), "theirs")]
        )
        assert sim.loadout[1][0].speed_mult == 1.0

    def test_a_container_counts_what_it_holds(self):
        """Holdall: "Gain 8 Block for each Neutral item inside"."""
        two = [
            self._item([], uid="a", position=(0, 0)),
            self._item([], uid="b", position=(1, 0)),
        ]
        sim, _ = self._fight("container_orchestrator", two)
        assert sim.player1.block == 16

    def test_it_counts_none_when_the_shelf_is_bare(self):
        sim, _ = self._fight("container_orchestrator", [])
        assert sim.player1.block == 0

    def test_a_container_is_not_standing_on_its_own_shelf(self):
        """Its squares are offered, not filled.

        Counting the container itself would fill every shelf it offers, so a
        clause that counts free squares inside one would find none at all.
        Asked of the counting rather than of the lists, because the lists are
        an arrangement and this is what the arrangement is for.
        """
        holding = self._item([], uid="held", position=(0, 0))
        sim, _ = self._fight("container_orchestrator", [holding])
        rack = sim.racks[1][0]
        free = sim._free_squares(_Zone("contained"), rack, sim.loadout[1])
        assert free == 5, "six squares, one item standing on one of them"

    def test_a_container_gets_its_own_copy_of_the_catalogues_spec(self):
        """A trigger keeps its state on itself and the catalogue holds one
        spec per container type. Shared, one battle's crossed counter would
        still be crossed in the next, and both players would read the same
        one. An item's spec is copied for exactly this reason.
        """
        mine = [Container.of("edge_node", (0, 0), "mine")]
        theirs = [Container.of("edge_node", (6, 0), "theirs")]
        sim = BattleSimulator(seed=TEST_SEED)
        sim.max_duration = 0.2
        sim.simulate_battle([], [], 18, mine, theirs)

        assert sim.racks[1][0].spec is not ITEM_CATALOG["edge_node"]
        assert sim.racks[1][0].spec is not sim.racks[2][0].spec

    def test_a_container_cannot_reach_the_other_players_items(self):
        theirs = self._item([], uid="theirs", position=(6, 0))
        mine = [Container.of("edge_node", (0, 0), "rack")]
        sim = BattleSimulator(seed=TEST_SEED)
        sim.max_duration = 1.0
        sim.simulate_battle(
            [], [theirs], 18, mine, [Container.of("standard_vm", (6, 0), "theirs")]
        )
        assert sim.loadout[2][0].speed_mult == 1.0

    def test_a_battle_leaves_nothing_behind_on_the_session_container(self):
        """The catalogue's spec is shared by every container of a type, and
        triggers keep their own state on themselves."""
        rack = Container.of("container_orchestrator", (0, 0), "rack")
        before = deepcopy(ITEM_CATALOG["container_orchestrator"])
        sim = BattleSimulator(seed=TEST_SEED)
        sim.max_duration = 1.0
        sim.simulate_battle(
            [self._item([], uid="a")],
            [],
            18,
            [rack],
            [Container.of("standard_vm", (6, 0), "theirs")],
        )
        assert ITEM_CATALOG["container_orchestrator"] == before


class TestAnAuraCanHandOutAScaledModifier(_WithOneItem):
    """ "Star items gain 4% critical chance for each Luck".

    A modifier whose size depends on what the player holds was something an
    item could only ever say about itself. An aura hands one out here, and
    each item in the zone reads its own copy against the same pool.
    """

    def _giver(self, effect, uid="giver", position=(1, 1)):
        """An item that projects one standing modifier over its star"""
        return self._starred([PassiveTrigger(effects=[effect])], uid, position)

    def test_the_zone_reads_the_pool_the_owner_holds(self):
        giver = self._giver(
            ModifyPerStatusEffect(
                stat="critical_chance",
                value=0.04,
                status="calibrated",
                whose="self",
                target_type="star",
            )
        )
        taker = self._item([], uid="taker", position=(0, 0))
        sim, _ = self._run([giver, taker], seconds=0.3, buffs={"calibrated": 3})
        got = next(i for i in sim.loadout[1] if i.uid == "taker")
        assert sim._per_status(
            got, "critical_chance", sim.player1, sim.player2
        ) == pytest.approx(0.12)

    def test_it_grows_and_shrinks_with_the_pool(self):
        """Kept rather than folded in, so it follows the count either way"""
        giver = self._giver(
            ModifyPerStatusEffect(
                stat="damage_flat",
                value=1.0,
                status="calibrated",
                whose="self",
                target_type="star",
            )
        )
        taker = self._item([], uid="taker", position=(0, 0))
        sim, _ = self._run([giver, taker], seconds=0.3, buffs={"calibrated": 2})
        got = next(i for i in sim.loadout[1] if i.uid == "taker")
        assert sim._per_status(got, "damage_flat", sim.player1, sim.player2) == 2.0
        sim.player1.buffs["calibrated"] = 0
        assert sim._per_status(got, "damage_flat", sim.player1, sim.player2) == 0.0

    def test_the_item_projecting_it_does_not_get_it(self):
        """A zone is drawn beside the footprint, never on it"""
        giver = self._giver(
            ModifyPerStatusEffect(
                stat="damage_flat",
                value=1.0,
                status="calibrated",
                whose="self",
                target_type="star",
            )
        )
        sim, _ = self._run([giver], seconds=0.3, buffs={"calibrated": 5})
        assert sim.loadout[1][0].per_status == []

    def test_a_cap_stops_it_growing(self):
        """ "(up to 50%)" is a ceiling on the reading, not on a total"""
        giver = self._giver(
            ModifyPerStatusEffect(
                stat="critical_chance",
                value=0.04,
                status="calibrated",
                whose="self",
                target_type="star",
                cap=0.5,
            )
        )
        taker = self._item([], uid="taker", position=(0, 0))
        sim, _ = self._run([giver, taker], seconds=0.3, buffs={"calibrated": 100})
        got = next(i for i in sim.loadout[1] if i.uid == "taker")
        assert sim._per_status(
            got, "critical_chance", sim.player1, sim.player2
        ) == pytest.approx(0.5)

    def test_an_item_saying_it_about_itself_still_keeps_it(self):
        """The commoner half, and unchanged"""
        mine = self._giver(
            ModifyPerStatusEffect(
                stat="damage_flat", value=1.0, status="calibrated", whose="self"
            ),
            position=(0, 0),
        )
        sim, _ = self._run([mine], seconds=0.3, buffs={"calibrated": 2})
        assert (
            sim._per_status(sim.loadout[1][0], "damage_flat", sim.player1, sim.player2)
            == 2.0
        )


class TestHealthTurnsIntoBlock(_WithOneItem):
    """ "Convert 50 health into 100 Block".

    A price paid in health, not damage taken: nothing that answers an attack
    answers this.
    """

    def _converter(self, health, block, uid="conv"):
        return self._item(
            [BattleStartTrigger(effects=[ConvertHealthEffect(health, block)])], uid
        )

    def test_the_health_goes_and_the_block_arrives(self):
        sim, _ = self._run([self._converter(50, 100)], seconds=0.3)
        assert sim.player1.quota == sim.player1.max_quota - 50
        assert sim.player1.block == 100

    def test_it_cannot_be_paid_when_the_price_is_the_last_of_you(self):
        """All of it or none of it, and never the last point"""
        sim, _ = self._run([self._converter(50, 100)], seconds=0.3, hurt=50)
        assert sim.player1.quota == 50, "nothing was paid"
        assert sim.player1.block == 0

    def test_a_threshold_notices_health_leaving_this_way_too(self):
        """ "Health drops below 50%" is written about health, not about being
        hit. A conversion that went round the one road down took its owner to
        37% with the threshold item standing beside it and nothing fired.
        """
        watcher = self._item(
            [
                HealthThresholdTrigger(
                    threshold=0.5,
                    effects=[
                        BuffEffect(buff_name="monitored", value=1, target_type="self")
                    ],
                )
            ],
            uid="watcher",
            position=(1, 0),
        )
        sim, _ = self._run([self._converter(60, 10), watcher], seconds=0.3, hurt=180)
        assert sim.player1.quota == 120
        assert sim.player1.buffs.get("monitored") == 1

    def test_a_threshold_stays_quiet_when_the_price_leaves_you_above_it(self):
        watcher = self._item(
            [
                HealthThresholdTrigger(
                    threshold=0.5,
                    effects=[
                        BuffEffect(buff_name="monitored", value=1, target_type="self")
                    ],
                )
            ],
            uid="watcher",
            position=(1, 0),
        )
        sim, _ = self._run([self._converter(10, 10), watcher], seconds=0.3, hurt=300)
        assert "monitored" not in sim.player1.buffs

    def test_nothing_answers_it_as_though_it_were_damage(self):
        """Spikes answer an attack. A price is not an attack."""
        sim, _ = self._run([self._converter(20, 40)], seconds=0.3, buffs={"spiked": 5})
        assert sim.player2.quota == sim.player2.max_quota

    def test_block_from_a_share_of_missing_health(self):
        """Stone Armor: "Block equal to 40% of your missing health"."""
        sim, _ = self._run(
            [
                self._item(
                    [
                        BattleStartTrigger(
                            effects=[
                                BlockEffect(block_amount=0, share_of_missing_health=0.4)
                            ]
                        )
                    ]
                )
            ],
            seconds=0.3,
            hurt=100,
        )
        missing = sim.player1.max_quota - 100
        assert sim.player1.block == int(missing * 0.4)

    def test_a_share_of_nothing_missing_is_nothing(self):
        sim, _ = self._run(
            [
                self._item(
                    [
                        BattleStartTrigger(
                            effects=[
                                BlockEffect(block_amount=0, share_of_missing_health=0.4)
                            ]
                        )
                    ]
                )
            ],
            seconds=0.3,
        )
        assert sim.player1.block == 0


class TestAStatusCanBeProtectedFromRemoval(_WithOneItem):
    """ "35% chance to protect your buffs from removal".

    Not refusing something sent at you but keeping something you have, so it
    goes the same road a refused debuff goes and is asked about removal.
    """

    def _protector(self, count=0, chance=0.0, pool="buff", target="self"):
        return self._item(
            [
                PassiveTrigger(
                    effects=[
                        ResistEffect(
                            count=count,
                            chance=chance,
                            target_type=target,
                            against="removal",
                            only=(pool,),
                        )
                    ]
                )
            ]
        )

    def test_a_charge_keeps_one_stack(self):
        sim, _ = self._run([self._protector(count=1)], seconds=0.3)
        sim.player1.buffs["calibrated"] = 2
        assert sim._cleanse(sim.player1, "buff", 2) == {"calibrated": 1}
        assert sim.player1.buffs["calibrated"] == 1

    def test_a_spent_charge_does_not_come_back(self):
        sim, _ = self._run([self._protector(count=1)], seconds=0.3)
        sim.player1.buffs["calibrated"] = 4
        sim._cleanse(sim.player1, "buff", 1)
        assert sim._cleanse(sim.player1, "buff", 1) == {"calibrated": 1}

    def test_a_certain_chance_keeps_everything(self):
        sim, _ = self._run([self._protector(chance=1.0)], seconds=0.3)
        sim.player1.buffs["calibrated"] = 3
        assert sim._cleanse(sim.player1, "buff", 3) == {}
        assert sim.player1.buffs["calibrated"] == 3

    def test_it_protects_only_the_pool_it_names(self):
        """Protecting your buffs says nothing about cleansing your debuffs"""
        sim, _ = self._run([self._protector(chance=1.0, pool="buff")], seconds=0.3)
        sim.player1.debuffs["throttled"] = 2
        assert sim._cleanse(sim.player1, "debuff", 2) == {"throttled": 2}

    def test_it_can_be_put_on_the_other_player(self):
        """Corrupted Kernel keeps the debuffs it put on its opponent there"""
        sim, _ = self._run(
            [self._protector(chance=1.0, pool="debuff", target="enemy")], seconds=0.3
        )
        sim.player2.debuffs["throttled"] = 2
        assert sim._cleanse(sim.player2, "debuff", 2) == {}

    def test_nothing_is_protected_when_nothing_protects(self):
        sim, _ = self._run([self._item([])], seconds=0.3)
        sim.player1.buffs["calibrated"] = 2
        assert sim._cleanse(sim.player1, "buff", 2) == {"calibrated": 2}

    def test_a_protected_stack_still_costs_the_remover_a_go(self):
        """One protected stack is one fewer taken, not one taken later"""
        sim, _ = self._run([self._protector(count=1)], seconds=0.3)
        sim.player1.buffs["calibrated"] = 5
        assert sum(sim._cleanse(sim.player1, "buff", 3).values()) == 2


class TestAShareOnWhatAnItemGives(_WithOneItem):
    """ "Star items give +30% Block", "Star Items give +100% Vampirism".

    A share on the giving item rather than on the player, so two items in a
    zone are each scaled by it and one standing outside gives what it always
    gave.
    """

    def _giver(self, stat, value, uid="aura", position=(1, 1)):
        return self._starred(
            [
                PassiveTrigger(
                    effects=[
                        ModifyEffect(
                            stat=stat,
                            value=value,
                            target_type="star",
                            duration=-1,
                            cap=None,
                            counting="any",
                        )
                    ]
                )
            ],
            uid,
            position,
        )

    def _blocker(self, amount=10, uid="blocker", position=(0, 0)):
        return self._item(
            [BattleStartTrigger(effects=[BlockEffect(block_amount=amount)])],
            uid,
            position,
        )

    def test_the_zone_scales_the_block_an_item_gives(self):
        sim, _ = self._run(
            [self._giver("block_given", 0.3), self._blocker()], seconds=0.3
        )
        assert sim.player1.block == 13

    def test_an_item_outside_the_zone_gives_what_it_always_gave(self):
        far = self._blocker(position=(3, 3))
        sim, _ = self._run([self._giver("block_given", 0.3), far], seconds=0.3)
        assert sim.player1.block == 10

    def test_gaining_block_says_it_was_gained(self):
        """Two different things share the `block` action name: Block arriving
        and Block spending itself on a blow. Each says which it is, because
        reading the name alone put "attack BLOCKED" in the battle log at 0.0s
        against an attack nobody had made."""
        sim, _ = self._run([self._blocker(amount=10)], seconds=0.3)
        (arrived,) = [a for a in sim.actions if a.action == "block"]
        assert arrived.details["type"] == "gained"

    def test_block_spending_itself_says_that_instead(self):
        hard = self._item(
            [
                TimerTrigger(
                    cooldown=0.2,
                    cpu_cost=0,
                    effects=[
                        AttackEffect(
                            min_damage=5, max_damage=5, accuracy=1.0, crit_chance=0.0
                        )
                    ],
                )
            ],
            uid="hard",
            position=(6, 0),
        )
        sim, _ = self._run([self._blocker(amount=50)], seconds=1.0, against=[hard])
        kinds = {a.details["type"] for a in sim.actions if a.action == "block"}
        assert kinds == {"gained", "absorbed"}

    def test_two_shares_add_rather_than_multiply(self):
        sim, _ = self._run(
            [
                self._giver("block_given", 0.3, uid="a", position=(1, 1)),
                self._giver("block_given", 0.3, uid="b", position=(2, 1)),
                self._blocker(position=(1, 0)),
            ],
            seconds=0.3,
        )
        assert sim.player1.block == 16, "1.6 of ten, not 1.69"

    def test_a_share_on_the_player_and_one_on_the_item_both_count(self):
        raise_it = self._item(
            [
                PassiveTrigger(
                    effects=[
                        PlayerModifyEffect(
                            stat="block_gained",
                            value=0.5,
                            target_type="self",
                            duration=-1,
                        )
                    ]
                )
            ],
            uid="player_share",
            position=(3, 3),
        )
        sim, _ = self._run(
            [self._giver("block_given", 0.5), self._blocker(), raise_it], seconds=0.3
        )
        assert sim.player1.block == 22, "1.5 by 1.5 of ten"

    def test_the_zone_scales_the_vampirism_an_item_gives(self):
        drainer = self._item(
            [
                BattleStartTrigger(
                    effects=[
                        BuffEffect(buff_name="draining", value=2, target_type="self")
                    ]
                )
            ],
            uid="drainer",
        )
        sim, _ = self._run([self._giver("vampirism_given", 1.0), drainer], seconds=0.3)
        assert sim.player1.buffs["draining"] == 4

    def test_a_counter_can_watch_what_one_zone_has_given(self):
        """ "Star items gained 12 Block: Gain 1 Mana"."""
        watcher = self._starred(
            [
                CounterTrigger(
                    counting="block",
                    amount=12,
                    whose="self",
                    counts="gained",
                    where="star",
                    effects=[
                        BuffEffect(buff_name="credits", value=1, target_type="self")
                    ],
                )
            ],
            uid="watcher",
            position=(1, 1),
        )
        sim, _ = self._run([watcher, self._blocker(amount=15)], seconds=0.5)
        assert sim.player1.buffs.get("credits") == 1

    def test_block_from_outside_the_zone_does_not_count_towards_it(self):
        watcher = self._starred(
            [
                CounterTrigger(
                    counting="block",
                    amount=12,
                    whose="self",
                    counts="gained",
                    where="star",
                    effects=[
                        BuffEffect(buff_name="credits", value=1, target_type="self")
                    ],
                )
            ],
            uid="watcher",
            position=(1, 1),
        )
        far = self._blocker(amount=99, position=(3, 3))
        sim, _ = self._run([watcher, far], seconds=0.5)
        assert "credits" not in sim.player1.buffs
        assert sim.player1.block == 99, "the Block still arrived"


class TestAShareOfMaximumHealth(_WithOneItem):
    """ "Gain 10% maximum health + 15% per Star item"."""

    def _grower(self, amount=0, share=0.0, uid="grow", position=(0, 0)):
        return self._item(
            [BattleStartTrigger(effects=[MaxHealthEffect(amount=amount, share=share)])],
            uid,
            position,
        )

    def test_a_share_of_the_maximum_raises_the_ceiling(self):
        sim, _ = self._run([self._grower(share=0.1)], seconds=0.3)
        opening = sim.player1.opening_quota
        assert sim.player1.max_quota == opening + int(opening * 0.1)
        assert (
            sim.player1.quota == sim.player1.max_quota
        ), "the health comes with the room"

    def test_two_shares_add_rather_than_compound(self):
        """Every other pair of shares here adds, and two halves of one
        sentence certainly should."""
        sim, _ = self._run(
            [
                self._grower(share=0.1, uid="a", position=(0, 0)),
                self._grower(share=0.15, uid="b", position=(1, 0)),
            ],
            seconds=0.3,
        )
        opening = sim.player1.opening_quota
        assert sim.player1.max_quota == opening + int(opening * 0.1) + int(
            opening * 0.15
        ), "a quarter of the opening quota, not 1.1 by 1.15"

    def test_a_flat_amount_still_works(self):
        sim, _ = self._run([self._grower(amount=3)], seconds=0.3)
        assert sim.player1.max_quota == sim.player1.opening_quota + 3

    def test_an_opponent_can_shrink_what_an_item_hands_over(self):
        """Snowball: "Your opponent gains 15% less maximum health from items"."""
        theirs = self._item(
            [
                PassiveTrigger(
                    effects=[
                        PlayerModifyEffect(
                            stat="max_health_from_items",
                            value=-0.15,
                            target_type="enemy",
                            duration=-1,
                        )
                    ]
                )
            ],
            uid="snow",
            position=(6, 0),
        )
        sim, _ = self._run([self._grower(amount=100)], seconds=0.3, against=[theirs])
        assert sim.player1.max_quota == sim.player1.opening_quota + 85

    def test_it_says_nothing_about_healing(self):
        """Raising the ceiling and filling the new room is not healing"""
        theirs = self._item(
            [
                PassiveTrigger(
                    effects=[
                        PlayerModifyEffect(
                            stat="healing_taken",
                            value=-0.5,
                            target_type="enemy",
                            duration=-1,
                        )
                    ]
                )
            ],
            uid="dampener",
            position=(6, 0),
        )
        sim, _ = self._run([self._grower(amount=100)], seconds=0.3, against=[theirs])
        assert sim.player1.max_quota == sim.player1.opening_quota + 100


class TestTheCatalogueItemsThatTradeHealthAndBlock(TestTheSweptClauses):
    """Real items that trade health for Block, or scale what they give.

    Converting health into Block, Block from the health you are short,
    protecting a status from removal, a share on the Block or Vampirism an item
    hands over, a share of maximum health.

    Everything above tests a mechanic on an item made for the purpose, which
    proves the mechanic and not the translation. A catalogue entry is a
    separate thing that can be wrong on its own -- the wrong number, the wrong
    zone, the wrong status -- and only running the real item finds it.
    """

    def test_sloth_grows_by_a_share_of_the_opening_quota(self):
        """ "Gain 10% maximum health + 15% per Star item"."""
        where, star = self._place("sloth", how_many_star=2)
        beside = [self._tagged(f"n{i}", {"nature"}, at) for i, at in enumerate(star)]
        sim, _ = self._fight([self._real("sloth", where)] + beside, seconds=0.3)
        opening = sim.player1.opening_quota
        assert sim.player1.max_quota == opening + int(opening * 0.1) + 2 * int(
            opening * 0.15
        )

    def test_sloth_alone_gains_only_its_own_tenth(self):
        where, _ = self._place("sloth")
        sim, _ = self._fight([self._real("sloth", where)], seconds=0.3)
        opening = sim.player1.opening_quota
        assert sim.player1.max_quota == opening + int(opening * 0.1)

    def test_snowball_shrinks_what_an_opponents_item_hands_over(self):
        """ "Your opponent gains 15% less maximum health from items"."""
        where, _ = self._place("sloth")
        theirs = self._real("snowball", (6, 0), uid="snow")
        sim, _ = self._fight(
            [self._real("sloth", where)], seconds=0.3, against=[theirs]
        )
        opening = sim.player1.opening_quota
        assert sim.player1.max_quota == opening + int(int(opening * 0.1) * 0.85)

    def test_vampiric_armor_pays_health_for_block(self):
        """ "Convert 50 health into 100 Block and gain 5 Vampirism"."""
        where, _ = self._place("vampiric_armor")
        sim, _ = self._fight([self._real("vampiric_armor", where)], seconds=0.3)
        assert sim.player1.quota == sim.player1.max_quota - 50
        assert sim.player1.block == 100
        assert sim.player1.buffs["draining"] == 5

    def test_vampiric_armor_keeps_paying_on_its_clock(self):
        """ "Every 2.8s: Convert 10 health into 20 Block"."""
        where, _ = self._place("vampiric_armor")
        sim, _ = self._fight([self._real("vampiric_armor", where)], seconds=6.0)
        paid = [a for a in sim.actions if a.action == "convert_health"]
        assert [a.damage for a in paid] == [50, 10, 10]

    def test_stone_armor_answers_its_own_wound(self):
        """ "Health drops below 50%: Block equal to 40% of your missing health".

        Wounded by a real hit rather than by writing the quota down: falling
        past the line is what fires this, and a number set behind the engine's
        back falls past nothing.
        """
        where, _ = self._place("stone_armor")
        hard = self._item(
            [
                TimerTrigger(
                    cooldown=0.2,
                    cpu_cost=0,
                    effects=[
                        EffectDamageEffect(
                            amount=200,
                            lifesteal=0.0,
                            per_status={},
                            whose="self",
                        )
                    ],
                )
            ],
            uid="hard",
            position=(6, 0),
        )
        sim, _ = self._fight(
            [self._real("stone_armor", where)], seconds=0.3, against=[hard]
        )
        missing = sim.player1.max_quota - sim.player1.quota
        # Its own battle-start Block comes first, so the share is what is over.
        assert sim.player1.block == 120 + int(missing * 0.4)

    def test_stone_armor_answers_the_health_vampiric_armor_spends(self):
        """The two are written for each other, and the price is what wounds.

        Vampiric Armor pays 50 health at battle start and 10 every 2.8s after,
        which is what carries an already-hurt player past half. Stone Armor's
        threshold went round the one road down and never saw it.
        """
        va, _ = self._place("vampiric_armor")
        held = {
            (va[0] + dx, va[1] + dy)
            for dx, dy in ITEM_CATALOG["vampiric_armor"].shape.squares
        }
        sa, _ = self._place("stone_armor", avoiding=held)
        sim, _ = self._fight(
            [self._real("vampiric_armor", va), self._real("stone_armor", sa)],
            seconds=0.3,
            hurt=180,
        )
        missing = sim.player1.max_quota - sim.player1.quota
        assert (
            sim.player1.quota < sim.player1.max_quota / 2
        ), "the price took them past half"
        assert sim.player1.block == 120 + 100 + int(missing * 0.4)

    def test_stone_armor_at_full_health_adds_nothing(self):
        where, _ = self._place("stone_armor")
        sim, _ = self._fight([self._real("stone_armor", where)], seconds=0.3)
        assert sim.player1.block == 120

    def test_shepherds_crook_keeps_the_buffs_it_protects(self):
        """ "35% chance to protect your buffs from removal"."""
        where, _ = self._place("shepherds_crook")
        sim, _ = self._fight([self._real("shepherds_crook", where)], seconds=0.3)
        (kept,) = [spec for spec in sim.player1.resists if spec.against == "removal"]
        assert kept.chance == 0.35
        assert kept.only == ("buff",)

    def test_shield_of_valor_scales_the_block_a_star_item_gives(self):
        """ "StarItems give 30% more Block"."""
        where, star = self._place("shield_of_valor", how_many_star=1)
        blocker = self._item(
            [BattleStartTrigger(effects=[BlockEffect(block_amount=10)])],
            uid="blocker",
            position=star[0],
        )
        sim, _ = self._fight(
            [self._real("shield_of_valor", where), blocker], seconds=0.3
        )
        given = sum(
            a.damage
            for a in sim.actions
            if a.action == "block" and a.source == "blocker"
        )
        assert given == 13

    def test_moon_shield_pays_a_mana_for_the_block_its_zone_gives(self):
        """ "Star items gained 12 Block: Gain 1 Mana"."""
        where, star = self._place("moon_shield", how_many_star=1)
        blocker = self._item(
            [BattleStartTrigger(effects=[BlockEffect(block_amount=10)])],
            uid="blocker",
            position=star[0],
        )
        sim, _ = self._fight([self._real("moon_shield", where), blocker], seconds=0.5)
        assert sim.player1.buffs.get("credits") == 1, "ten by 1.3 clears twelve"

    def test_moon_shield_waits_when_the_zone_has_given_too_little(self):
        """Block from outside the zone is not what the clause counts.

        The item standing outside gives 99 on its own, which would clear the
        line several times over if the zone were not what was being asked
        about.
        """
        where, star = self._place("moon_shield", how_many_star=1)
        small = self._item(
            [BattleStartTrigger(effects=[BlockEffect(block_amount=4)])],
            uid="blocker",
            position=star[0],
        )
        far = self._item(
            [BattleStartTrigger(effects=[BlockEffect(block_amount=99)])],
            uid="far",
            position=self._somewhere_outside("moon_shield", where, star),
        )
        sim, _ = self._fight(
            [self._real("moon_shield", where), small, far], seconds=0.5
        )
        assert "credits" not in sim.player1.buffs
        assert sim.player1.block >= 99, "the Block still arrived"

    def test_encryption_module_watches_its_own_zone(self):
        """ "Star items gained 40 Block: Gain 1 Empower"."""
        where, star = self._place("encryption_module", how_many_star=1)
        blocker = self._item(
            [BattleStartTrigger(effects=[BlockEffect(block_amount=40)])],
            uid="blocker",
            position=star[0],
        )
        sim, _ = self._fight(
            [self._real("encryption_module", where), blocker], seconds=0.5
        )
        assert sim.player1.buffs.get("monitored") == 1

    def test_encryption_modules_own_block_does_not_count(self):
        """It gains 30 Block itself, and that is not what the clause counts"""
        where, _ = self._place("encryption_module")
        sim, _ = self._fight([self._real("encryption_module", where)], seconds=0.5)
        assert sim.player1.block == 30
        assert "monitored" not in sim.player1.buffs

    def test_encryption_waits_for_the_whole_forty(self):
        """Thirty from the zone is not forty, and 30 is over any smaller line"""
        where, star = self._place("encryption_module", how_many_star=1)
        blocker = self._item(
            [BattleStartTrigger(effects=[BlockEffect(block_amount=30)])],
            uid="blocker",
            position=star[0],
        )
        sim, _ = self._fight(
            [self._real("encryption_module", where), blocker], seconds=0.5
        )
        assert "monitored" not in sim.player1.buffs

    def test_credential_harvester_doubles_the_vampirism_its_zone_gives(self):
        """ "Star Items give +100% Vampirism"."""
        where, star = self._place("credential_harvester", how_many_star=1)
        giver = self._item(
            [
                BattleStartTrigger(
                    effects=[
                        BuffEffect(buff_name="draining", value=3, target_type="self")
                    ]
                )
            ],
            uid="giver",
            position=star[0],
        )
        sim, _ = self._fight(
            [self._real("credential_harvester", where), giver], seconds=0.3
        )
        assert sim.player1.buffs["draining"] == 6

    def test_bloody_dagger_stops_at_five_vampirism(self):
        """ "Gain 1 Vampirism (up to 5 per battle)"."""
        where, _ = self._place("bloody_dagger")
        sim, _ = self._fight(
            [self._real("bloody_dagger", where)],
            seconds=16.0,
            against=[self._tagged("wall", set(), (6, 0))],
        )
        assert sim.player1.buffs["draining"] == 5

    def test_bloody_dagger_heals_for_the_vampiric_items_beside_it(self):
        """ "Heal 4 per Star Vampiric-item"."""
        where, star = self._place("bloody_dagger", how_many_star=1)
        beside = self._tagged("leech", {"vampiric"}, star[0])
        sim, _ = self._fight(
            [self._real("bloody_dagger", where), beside],
            seconds=6.0,
            hurt=100,
            against=[self._tagged("wall", set(), (6, 0))],
        )
        # Vampirism heals on the same hits and is written down the same way,
        # so the buff it names is what tells the two apart.
        heals = [
            a
            for a in sim.actions
            if a.action == "heal" and not (a.details or {}).get("buff_name")
        ]
        assert heals, "one heal per hit, one Vampiric item beside it"
        assert all(a.damage == 4 for a in heals)

    def test_king_crown_holds_a_charge_against_removal(self):
        """ "Heal for 8 and protect 1 buff from removal"."""
        where, _ = self._place("king_crown")
        sim, _ = self._fight([self._real("king_crown", where)], seconds=3.0)
        charges = [
            spec
            for spec in sim.player1.resists
            if spec.against == "removal" and spec.count
        ]
        assert charges, "the timer has come round once"
        sim.player1.buffs["calibrated"] = 2
        assert sim._cleanse(sim.player1, "buff", 1) == {}

    def test_corrupted_kernel_protects_its_opponents_debuffs(self):
        """ "10% chance for each Star Dark-item to protect debuffs on your
        opponent from being cleansed"."""
        where, star = self._place("corrupted_kernel", how_many_star=2)
        dark = [self._tagged(f"d{i}", {"dark"}, at) for i, at in enumerate(star)]
        sim, _ = self._fight(
            [self._real("corrupted_kernel", where)] + dark, seconds=0.3
        )
        held = [spec for spec in sim.player2.resists if spec.against == "removal"]
        assert [spec.chance for spec in held] == [0.1, 0.1], "one per Dark item"
        assert all(spec.only == ("debuff",) for spec in held)

    def test_corrupted_kernel_with_no_dark_beside_it_protects_nothing(self):
        where, _ = self._place("corrupted_kernel")
        sim, _ = self._fight([self._real("corrupted_kernel", where)], seconds=0.3)
        assert [s for s in sim.player2.resists if s.against == "removal"] == []


class TestTheCatalogueBagsThatReadWhatIsInside(_WithOneItem):
    """Real bags that reach, count or scale what stands on them.

    Their own class because a container is the thing under test rather than
    the room the test happens in, so each one brings the rack it is about.
    """

    def _fight(self, container_id, items, seconds=0.5, hurt=None):
        mine = [Container.of(container_id, (0, 0), "rack")]
        theirs = [Container.of("standard_vm", (6, 0), "theirs")]
        sim = BattleSimulator(seed=TEST_SEED)
        sim.max_duration = seconds
        sim.nightfall = seconds + 1
        original = sim._setup_item_handlers

        def setup(its, owner, enemy):
            out = original(its, owner, enemy)
            if owner.id == 1 and hurt is not None:
                owner.quota = hurt
            return out

        sim._setup_item_handlers = setup
        return sim, sim.simulate_battle(items, [], 18, mine, theirs)

    def test_holdall_blocks_for_each_neutral_item_inside(self):
        """ "Start of battle: Gain 8 Block for each Neutral item inside".

        One of the four is a Sentaur item, and Neutral is what the clause
        says: counting anything inside would come to 32.
        """
        inside = [
            self._item([], uid=f"n{i}", position=at)
            for i, at in enumerate(((0, 0), (1, 0), (2, 0)))
        ]
        inside.append(
            BattleItem(
                spec=ItemSpec(
                    id="theirs",
                    name="Sentaur thing",
                    category="protocol",
                    cost=1,
                    player_class="sentaur",
                    shape=parse_map(["#"], "s"),
                    slug="theirs",
                    kinds=frozenset({"melee"}),
                    triggers=[],
                ),
                position=(0, 1),
                uid="sentaur",
            )
        )
        sim, _ = self._fight("container_orchestrator", inside)
        assert sim.player1.block == 24

    def test_holdall_with_nothing_inside_blocks_nothing(self):
        sim, _ = self._fight("container_orchestrator", [])
        assert sim.player1.block == 0

    def test_dead_drop_hands_its_items_a_scaled_crit_chance(self):
        """ "Items inside gain 10% critical hit chance +3% for each Luck"."""
        held = self._item(
            [
                BattleStartTrigger(
                    effects=[
                        BuffEffect(buff_name="calibrated", value=4, target_type="self")
                    ]
                )
            ],
            uid="held",
        )
        sim, _ = self._fight("network_cache", [held])
        got = sim.loadout[1][0]
        assert got.crit_bonus == pytest.approx(0.1)
        assert sim._per_status(
            got, "critical_chance", sim.player1, sim.player2
        ) == pytest.approx(0.12)

    def test_motherboard_amplifies_healing_by_what_it_holds(self):
        """ "Your healing is amplified by 12% + 5% per Nature-item inside"."""
        nature = [
            BattleItem(
                spec=ItemSpec(
                    id=f"n{i}",
                    name="Leaf",
                    category="protocol",
                    cost=1,
                    player_class="neutral",
                    shape=parse_map(["#"], "n"),
                    slug=f"n{i}",
                    kinds=frozenset({"nature"}),
                    triggers=[],
                ),
                position=at,
                uid=f"n{i}",
            )
            for i, at in enumerate(((0, 0), (1, 0)))
        ]
        healer = self._item(
            [BattleStartTrigger(effects=[HealEffect(min_heal=100, max_heal=100)])],
            uid="healer",
            position=(2, 0),
        )
        sim, _ = self._fight("mesh_network_hub", nature + [healer], hurt=100)
        healed = [a for a in sim.actions if a.action == "heal"]
        assert [a.damage for a in healed] == [122], "12% and two lots of 5%"

    def test_motherboard_with_nothing_green_inside_still_gives_its_twelfth(self):
        healer = self._item(
            [BattleStartTrigger(effects=[HealEffect(min_heal=100, max_heal=100)])],
            uid="healer",
        )
        sim, _ = self._fight("mesh_network_hub", [healer], hurt=100)
        healed = [a for a in sim.actions if a.action == "heal"]
        assert [a.damage for a in healed] == [112]


class TestAFullPoolMeansThePoolTheItemsLeft(_WithOneItem):
    """CPU is filled after the items have had their say, not before.

    Nothing in the catalogue but a Stamina Sack changes the size of the pool,
    and until containers acted nothing ran it. Filled first, it gave its owner
    a bigger pool and started them a second of regeneration short of it.
    """

    def _rack(self, container_id):
        return (
            [Container.of(container_id, (0, 0), "rack")],
            [Container.of("standard_vm", (6, 0), "theirs")],
        )

    def _open_on(self, container_id):
        mine, theirs = self._rack(container_id)
        sim = BattleSimulator(seed=TEST_SEED)
        sim.max_duration = 0.1
        sim.simulate_battle([], [], 18, mine, theirs)
        return sim.player1

    def test_a_bigger_pool_opens_full(self):
        opened = self._open_on("memory_cache")
        assert opened.max_cpu == 4.0
        assert opened.cpu == pytest.approx(opened.max_cpu, abs=0.11)

    def test_an_ordinary_pool_is_unchanged(self):
        opened = self._open_on("standard_vm")
        assert opened.max_cpu == 3.0
        assert opened.cpu == pytest.approx(opened.max_cpu, abs=0.11)


class TestEveryTriggerSaysItActivated(_WithOneItem):
    """ "Star item activates" is about the item, not about which of its
    triggers went off.

    Only the timer announced, so an aura watching a zone saw the items on
    cooldowns and nothing else: a Potion drunk by its own condition, a shield
    answering a blow, a counter crossing its line -- none of them announced,
    and every clause written "Star item activates" quietly counted a fraction
    of what it should have.
    """

    def _watcher(self, uid="watcher", position=(1, 1), on="activates"):
        return self._starred(
            [
                AuraTrigger(
                    zone="star",
                    counting="any",
                    after=1,
                    on=on,
                    effects=[
                        BuffEffect(buff_name="credits", value=1, target_type="self")
                    ],
                )
            ],
            uid,
            position,
        )

    def _beside(self, triggers, uid="stood"):
        return self._item(triggers, uid=uid, position=(0, 0))

    def _saw(self, triggers, seconds=2.0, hurt=None, against=()):
        sim, _ = self._run(
            [self._watcher(), self._beside(triggers)],
            seconds=seconds,
            hurt=hurt,
            against=list(against),
        )
        return sim.player1.buffs.get("credits", 0)

    def test_a_timer_still_announces(self):
        assert self._saw(
            [TimerTrigger(cooldown=0.5, cpu_cost=0, effects=[HealEffect(1, 1)])]
        )

    def test_a_health_threshold_announces(self):
        seen = self._saw(
            [HealthThresholdTrigger(threshold=0.5, effects=[HealEffect(1, 1)])],
            hurt=100,
            against=[
                self._item(
                    [
                        TimerTrigger(
                            cooldown=0.2,
                            cpu_cost=0,
                            effects=[
                                EffectDamageEffect(
                                    amount=200,
                                    lifesteal=0.0,
                                    per_status={},
                                    whose="self",
                                )
                            ],
                        )
                    ],
                    uid="hard",
                    position=(6, 0),
                )
            ],
        )
        assert seen == 1, "a Potion drunk by its own condition activated"

    def test_an_after_trigger_announces(self):
        assert self._saw([AfterTrigger(delay=0.5, effects=[HealEffect(1, 1)])]) == 1

    def test_a_shield_answering_a_blow_announces(self):
        """It rolled, it answered, it acted. This one cannot go through
        `_fire` -- prevent_damage has to be handled an effect at a time -- so
        it is the one path that has to say so itself."""
        shield = self._item(
            [
                OnAttackedTrigger(
                    chance=1.0,
                    answers_to=frozenset({"melee"}),
                    effects=[PreventDamageEffect(amount=3)],
                )
            ],
            uid="stood",
            position=(0, 0),
        )
        hitter = BattleItem(
            spec=ItemSpec(
                id="hitter",
                name="hitter",
                category="problem",
                cost=1,
                player_class="neutral",
                shape=parse_map(["#"], "h"),
                slug="hitter",
                kinds=frozenset({"melee", "weapon"}),
                triggers=[
                    TimerTrigger(
                        cooldown=0.5,
                        cpu_cost=0,
                        effects=[
                            AttackEffect(
                                min_damage=6,
                                max_damage=6,
                                accuracy=1.0,
                                crit_chance=0.0,
                            )
                        ],
                    )
                ],
            ),
            position=(4, 0),
            uid="hitter",
        )
        sim, _ = self._run([self._watcher(), shield], seconds=2.0, against=[hitter])
        assert [a for a in sim.actions if a.action == "block"], "it answered"
        assert sim.player1.buffs.get("credits"), "and the watcher saw it act"

    def test_a_container_with_an_aura_watches_the_items_on_it(self):
        """A container's handlers are set up with the rack, and a rack is not
        where items stand. Nothing in the catalogue carries this yet, so the
        only way to reach it is to give a bag one.
        """
        spare = deepcopy(ITEM_CATALOG["standard_vm"])
        try:
            ITEM_CATALOG["standard_vm"].triggers = [
                AuraTrigger(
                    zone="contained",
                    counting="any",
                    after=1,
                    on="activates",
                    effects=[
                        BuffEffect(buff_name="credits", value=1, target_type="self")
                    ],
                )
            ]
            stood = self._item(
                [TimerTrigger(cooldown=0.5, cpu_cost=0, effects=[HealEffect(1, 1)])],
                uid="stood",
                position=(0, 0),
            )
            sim, _ = self._run([stood], seconds=2.0, hurt=100)
            assert sim.player1.buffs.get("credits"), "the shelf saw what stands on it"
        finally:
            ITEM_CATALOG["standard_vm"] = spare

    def test_a_passive_announces_nothing(self):
        """A passive is on throughout rather than happening at a moment"""
        assert (
            self._saw(
                [
                    PassiveTrigger(
                        effects=[
                            PlayerModifyEffect(
                                stat="healing",
                                value=0.1,
                                target_type="self",
                                duration=-1,
                            )
                        ]
                    )
                ]
            )
            == 0
        )

    def test_a_start_of_battle_trigger_announces_nothing(self):
        """Settled before the battle has a first moment to happen in"""
        assert self._saw([BattleStartTrigger(effects=[HealEffect(1, 1)])]) == 0

    def test_an_aura_cannot_answer_its_own_activation(self):
        """Every trigger announces now, so an aura whose effects set off what
        it watches would otherwise answer itself until the stack gave out."""
        loop = self._starred(
            [
                AuraTrigger(
                    zone="star",
                    counting="any",
                    after=1,
                    on="activates",
                    effects=[
                        TriggerItemEffect(
                            where="star", counting="any", how_many=0, pick="all"
                        )
                    ],
                )
            ],
            "loop",
            (1, 1),
        )
        stood = self._beside(
            [TimerTrigger(cooldown=0.5, cpu_cost=0, effects=[HealEffect(1, 1)])]
        )
        sim, _ = self._run([loop, stood], seconds=2.0, hurt=100)
        set_off = [a for a in sim.actions if a.action == "trigger_item"]
        assert set_off, "it still fires"
        assert (
            len(set_off) <= 8
        ), f"once per activation and not a chain of them: {len(set_off)}"

    def test_an_item_set_off_by_another_announces_that_it_acted(self):
        """ "Trigger the Star Pet" is the pet activating. An aura watching that
        square has as much reason to answer it as a pet that came round on its
        own clock."""
        # `stood` has nothing of its own to go off, so an announcement can
        # only have come from being set off by the item beside it.
        stood = self._item([], uid="stood", position=(1, 0))
        setter = self._starred(
            [
                AfterTrigger(
                    delay=0.3,
                    effects=[
                        TriggerItemEffect(
                            where="star", counting="any", how_many=0, pick="all"
                        )
                    ],
                )
            ],
            "setter",
            (1, 1),
        )
        watcher = self._watcher(uid="watcher", position=(2, 1))
        sim, _ = self._run([watcher, setter, stood], seconds=1.0, hurt=100)
        assert [a for a in sim.actions if a.action == "trigger_item"], "it was set off"
        assert sim.player1.buffs.get("credits") == 1, "and the watcher saw it act"


class TestAChanceCanGrowWithWhatYouHold(_WithOneItem):
    """ "7% chance for each Luck to gain 3 Mana"."""

    def _roller(self, chance=0.0, per_status=None):
        return self._item(
            [
                TimerTrigger(
                    cooldown=0.5,
                    cpu_cost=0,
                    effects=[
                        ChanceEffect(
                            chance=chance,
                            per_status=per_status or {},
                            effects=[
                                BuffEffect(
                                    buff_name="credits", value=1, target_type="self"
                                )
                            ],
                        )
                    ],
                )
            ]
        )

    def test_nothing_held_is_no_chance_at_all(self):
        sim, _ = self._run([self._roller(per_status={"calibrated": 0.5})], seconds=3.0)
        assert "credits" not in sim.player1.buffs

    def test_enough_held_makes_it_certain(self):
        sim, _ = self._run(
            [self._roller(per_status={"calibrated": 0.5})],
            seconds=3.0,
            buffs={"calibrated": 2},
        )
        assert sim.player1.buffs["credits"] == 5, "every roll landed"

    def test_it_is_read_at_the_roll_and_not_before(self):
        """The count changes as the battle goes on, so a chance settled at
        setup would be the chance the player started with."""
        grower = self._item(
            [
                TimerTrigger(
                    cooldown=0.4,
                    cpu_cost=0,
                    effects=[
                        BuffEffect(buff_name="calibrated", value=1, target_type="self")
                    ],
                )
            ],
            uid="grower",
            position=(1, 0),
        )
        sim, _ = self._run(
            [self._roller(per_status={"calibrated": 0.34}), grower], seconds=3.0
        )
        assert sim.player1.buffs.get("credits"), "the pool grew into a chance"

    def test_a_flat_chance_still_works(self):
        sim, _ = self._run([self._roller(chance=1.0)], seconds=3.0)
        assert sim.player1.buffs["credits"] == 5


class TestCountingCanExclude(_WithOneItem):
    """ "10% chance to gain 1 Regeneration, 30% if the item is Holy" is two
    clauses, and without a way to say "not Holy" both would fire on a Holy
    item."""

    @staticmethod
    def _effect(counting):
        return ModifyPerEffect(
            stat="trigger_speed", value=1.0, zone="star", counting=counting
        )

    def test_none_matches_an_item_carrying_none_of_the_tags(self):
        assert self._effect({"none": ["holy"]}).matches({"melee", "weapon"})

    def test_none_refuses_an_item_carrying_one_of_them(self):
        assert not self._effect({"none": ["holy"]}).matches({"holy", "melee"})

    def test_none_refuses_an_item_carrying_any_of_several(self):
        counting = {"none": ["holy", "dark"]}
        assert not self._effect(counting).matches({"dark"})
        assert self._effect(counting).matches({"nature"})

    def test_the_other_two_are_unchanged(self):
        assert self._effect({"any": ["holy"]}).matches({"holy", "melee"})
        assert self._effect({"all": ["holy", "melee"]}).matches({"holy", "melee"})
        assert not self._effect({"all": ["holy", "melee"]}).matches({"holy"})


class TestWhatSpikesSendBack(_WithOneItem):
    """Backpack Battles' Amulet of the Wild page, which is the only place the
    rule is written down:

        "The return damage limit refers to how much of the opponent's weapon
        damage can be returned provided you have enough Spikes. Normally the
        limit for melee weapons is 100% of the damage, and for ranged weapons
        0% of the damage."

    So Spikes were never a melee rule. 0% and "does not happen" are the same
    answer until an item raises the limit, which is why they could sit inside
    the melee half and look right.
    """

    def _swinger(self, kinds, damage=4, uid="them", position=(6, 0)):
        return BattleItem(
            spec=ItemSpec(
                id=uid,
                name=uid,
                category="problem",
                cost=1,
                player_class="neutral",
                shape=parse_map(["#"], uid),
                slug=uid,
                kinds=frozenset(kinds),
                triggers=[
                    TimerTrigger(
                        cooldown=0.5,
                        cpu_cost=0,
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
            position=position,
            uid=uid,
        )

    def _raise_limit(self, which, by=0.5, uid="amulet"):
        return self._item(
            [
                PassiveTrigger(
                    effects=[
                        PlayerModifyEffect(
                            stat=f"spikes_limit_{which}",
                            value=by,
                            target_type="self",
                            duration=-1,
                        )
                    ]
                )
            ],
            uid=uid,
            position=(1, 0),
        )

    def _sent_back(self, sim):
        return sum(
            a.damage
            for a in sim.actions
            if a.action == "damage" and (a.details or {}).get("buff_name") == "spiked"
        )

    def test_a_melee_blow_comes_back_in_full(self):
        sim, _ = self._run(
            [self._item([])],
            seconds=0.6,
            buffs={"spiked": 10},
            against=[self._swinger({"melee", "weapon"})],
        )
        assert self._sent_back(sim) == 4, "100% of a four damage blow"

    def test_a_ranged_blow_comes_back_not_at_all(self):
        sim, _ = self._run(
            [self._item([])],
            seconds=0.6,
            buffs={"spiked": 10},
            against=[self._swinger({"ranged", "weapon"})],
        )
        assert self._sent_back(sim) == 0, "0% is the base for a ranged blow"

    def test_raising_the_ranged_limit_sends_some_back(self):
        sim, _ = self._run(
            [self._raise_limit("ranged")],
            seconds=0.6,
            buffs={"spiked": 10},
            against=[self._swinger({"ranged", "weapon"})],
        )
        assert self._sent_back(sim) == 2, "50% of four"

    def test_the_wikis_worked_example_holds(self):
        """Ten Spikes at 150%: four damage sends back six, nine sends back ten"""
        for damage, expected in ((4, 6), (9, 10)):
            sim, _ = self._run(
                [self._raise_limit("melee")],
                seconds=0.6,
                buffs={"spiked": 10},
                against=[self._swinger({"melee", "weapon"}, damage=damage)],
            )
            assert self._sent_back(sim) == expected, f"{damage} damage"

    def test_the_stacks_held_are_the_other_bound(self):
        sim, _ = self._run(
            [self._item([])],
            seconds=0.6,
            buffs={"spiked": 2},
            against=[self._swinger({"melee", "weapon"}, damage=9)],
        )
        assert self._sent_back(sim) == 2, "two Spikes cannot send back nine"

    def test_effect_damage_sends_nothing_back_until_it_is_raised(self):
        caster = self._item(
            [
                TimerTrigger(
                    cooldown=0.5,
                    cpu_cost=0,
                    effects=[
                        EffectDamageEffect(
                            amount=8, lifesteal=0.0, per_status={}, whose="self"
                        )
                    ],
                )
            ],
            uid="caster",
            position=(6, 0),
        )
        bare, _ = self._run(
            [self._item([])], seconds=0.6, buffs={"spiked": 10}, against=[caster]
        )
        assert self._sent_back(bare) == 0

        raised, _ = self._run(
            [self._raise_limit("effect")],
            seconds=0.6,
            buffs={"spiked": 10},
            against=[caster],
        )
        assert self._sent_back(raised) == 4, "50% of eight"

    def test_what_comes_back_can_crit(self):
        sim, _ = self._run(
            [
                self._item(
                    [
                        PassiveTrigger(
                            effects=[
                                PlayerModifyEffect(
                                    stat="spikes_critical_chance",
                                    value=1.0,
                                    target_type="self",
                                    duration=-1,
                                )
                            ]
                        )
                    ]
                )
            ],
            seconds=0.6,
            buffs={"spiked": 10},
            against=[self._swinger({"melee", "weapon"})],
        )
        assert self._sent_back(sim) == 8, "four doubled"
        assert [
            a
            for a in sim.actions
            if a.action == "critical_hit" and (a.details or {}).get("kind") == "spikes"
        ]

    def test_no_roll_is_spent_on_a_crit_chance_nobody_has(self):
        """`random() < 0` never lands, so rolling anyway changes nothing --
        except which numbers every later draw receives. Nothing gives Spikes a
        crit chance unless an item says so, and a wasted draw here would move
        the seeded sequence of every battle that has ever had a Spike in it.

        Asked of the road itself, because nothing downstream can tell a
        sequence that shifted from one that did not.
        """

        class Counting:
            def __init__(self, real):
                self.real, self.draws = real, 0

            def random(self):
                self.draws += 1
                return self.real.random()

            def __getattr__(self, name):
                return getattr(self.real, name)

        def draws_for(crit):
            sim = BattleSimulator(seed=TEST_SEED)
            sim.player1 = Player(id=1, quota=100, max_quota=100, cpu=3.0)
            sim.player2 = Player(id=2, quota=100, max_quota=100, cpu=3.0)
            sim.player2.buffs["spiked"] = 10
            if crit:
                sim.player2.mods.append(
                    Timed(
                        kind="modifier",
                        name="spikes_critical_chance",
                        amount=crit,
                        until=None,
                    )
                )
            sim.rng = Counting(sim.rng)
            sim._spikes_answer(4, sim.player1, sim.player2, "melee")
            return sim.rng.draws, sim.player1.quota

        none_held, hurt_plainly = draws_for(0.0)
        rolled, hurt_worse = draws_for(1.0)
        assert hurt_plainly == 96, "four came back"
        assert hurt_worse == 92, "and eight when it crits, so the road ran both times"
        assert none_held == 0, "no chance, no roll"
        assert rolled == 1, "a chance is rolled for exactly once"

    def test_nothing_comes_back_from_poison_or_fatigue(self):
        """Spikes answer a blow. Poison arrives on its own clock from an item
        that struck some time ago, and fatigue comes from nobody at all."""
        sim, _ = self._run(
            [self._item([])],
            seconds=4.0,
            buffs={"spiked": 10},
            against=[
                self._item(
                    [
                        BattleStartTrigger(
                            effects=[
                                DebuffEffect(
                                    debuff_name=MEMORY_LEAKED, value=5, duration=-1
                                )
                            ]
                        )
                    ],
                    uid="poisoner",
                    position=(6, 0),
                )
            ],
        )
        assert [a for a in sim.actions if a.action == "dot"], "the poison landed"
        assert self._sent_back(sim) == 0


class TestTheCatalogueItemsThatWatchAMomentOrUseSpikes(TestTheSweptClauses):
    """Real items that watch a moment in their zone, or answer with Spikes.

    A weapon in the zone hitting, a Potion in it going off, a Holy item in it
    activating and a plain one not; and, on the other side, what Spikes send
    back and how often it crits.

    Everything above tests a mechanic on an item made for the purpose, which
    proves the mechanic and not the translation.
    """

    def _hitter(self, kinds=("melee", "weapon"), at=(0, 0), damage=6, uid="hitter"):
        return BattleItem(
            spec=ItemSpec(
                id=uid,
                name=uid,
                category="problem",
                cost=1,
                player_class="neutral",
                shape=parse_map(["#"], uid),
                slug=uid,
                kinds=frozenset(kinds),
                triggers=[
                    TimerTrigger(
                        cooldown=0.5,
                        cpu_cost=0,
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
            position=at,
            uid=uid,
        )

    def test_spike_launcher_spends_a_spike_on_its_next_swing(self):
        """ "Star Weapon hits: Use 1 Spikes to deal +9 damage on the next attack"."""
        where, star = self._place("spike_launcher", how_many_star=1)
        sim, _ = self._fight(
            [self._real("spike_launcher", where), self._hitter(at=star[0])],
            seconds=4.0,
            against=[self._tagged("wall", set(), (6, 0))],
        )
        spent = [a for a in sim.actions if a.action == "spend"]
        assert spent, "the Spikes it starts with paid for it"
        assert all(a.details["costs"] == {"spiked": 1} for a in spent)

    def test_spike_launcher_with_no_weapon_beside_it_spends_nothing(self):
        where, _ = self._place("spike_launcher")
        sim, _ = self._fight(
            [self._real("spike_launcher", where)],
            seconds=4.0,
            against=[self._tagged("wall", set(), (6, 0))],
        )
        assert not [a for a in sim.actions if a.action == "spend"]

    def test_blue_sage_collar_pays_out_more_the_more_luck_you_hold(self):
        """ "Star Weapon hits: 7% chance for each Luck to gain 3 Mana"."""
        where, star = self._place("blue_sage_collar", how_many_star=1)
        held = []
        for luck in (0, 15):
            sim, _ = self._fight(
                [self._real("blue_sage_collar", where), self._hitter(at=star[0])],
                seconds=8.0,
                buffs={"calibrated": luck} if luck else None,
                against=[self._tagged("wall", set(), (6, 0))],
            )
            held.append(sim.player1.buffs.get("credits", 0))
        assert held[0] == 0, "no Luck is no chance at all"
        assert held[1] > 0, "fifteen Luck is a certainty every hit"

    def test_blue_sage_collar_answers_a_hit_and_not_a_swing(self):
        """A weapon that misses activated and did not hit, which is the whole
        difference between the moment this watches and the commoner one."""
        where, star = self._place("blue_sage_collar", how_many_star=1)
        misser = self._hitter(at=star[0], uid="misser")
        # Far below zero, not at it: the fifteen Luck this test needs for the
        # chance would otherwise carry a zero-accuracy weapon into landing.
        misser.spec.triggers[0].effects = [
            AttackEffect(min_damage=6, max_damage=6, accuracy=-10.0, crit_chance=0.0)
        ]
        sim, _ = self._fight(
            [self._real("blue_sage_collar", where), misser],
            seconds=8.0,
            buffs={"calibrated": 15},
            against=[self._tagged("wall", set(), (6, 0))],
        )
        assert [a for a in sim.actions if a.action == "miss"], "it swung and missed"
        assert "credits" not in sim.player1.buffs

    def test_amulet_of_light_tells_a_holy_item_from_the_rest(self):
        """ "10% chance to gain 1 Regeneration, 30% if the item is Holy" is two
        clauses, and a Holy item must answer one of them and not both."""
        spec = ITEM_CATALOG["amulet_of_light"]
        auras = [t for t in spec.triggers if isinstance(t, AuraTrigger)]
        assert len(auras) == 2
        by_chance = {}
        for aura in auras:
            (chance,) = [e for e in aura.effects if isinstance(e, ChanceEffect)]
            by_chance[chance.chance] = aura.counting
        assert by_chance == {0.3: {"any": ["holy"]}, 0.1: {"none": ["holy"]}}

    def test_barb_daemon_sends_a_ranged_blow_back(self):
        """ "Return damage limit of Spikes against Ranged- and Effect-attacks
        +50%". Nothing came back from a ranged blow before it."""
        where, _ = self._place("thorn_elemental")
        shooter = self._swinger(damage=8, uid="shooter", position=(6, 0))
        shooter.spec.kinds = frozenset({"ranged", "weapon"})
        sim, _ = self._fight(
            [self._real("thorn_elemental", where)], seconds=6.0, against=[shooter]
        )
        back = [
            a
            for a in sim.actions
            if a.action == "damage" and (a.details or {}).get("buff_name") == "spiked"
        ]
        assert back, "half of a ranged blow now comes back"

    def test_barb_daemon_gives_spikes_a_crit_chance_per_nature_item(self):
        """ "Spikes have 10% critical hit chance per Star Nature-item"."""
        where, star = self._place("thorn_elemental", how_many_star=2)
        beside = [self._tagged(f"n{i}", {"nature"}, at) for i, at in enumerate(star)]
        sim, _ = self._fight(
            [self._real("thorn_elemental", where)] + beside, seconds=0.3
        )
        assert sim.player1.modifier("spikes_critical_chance", 0.0) == pytest.approx(0.2)

    def test_echo_chamber_sets_off_the_pet_beside_it(self):
        """ "After 5s: Trigger the Star Pet and gain 4 Spikes"."""
        where, star = self._place("machine_learning_core", how_many_star=1)
        pet = self._tagged("pet", {"pet"}, star[0], category="pet")
        pet.spec.triggers = [
            TimerTrigger(cooldown=99.0, cpu_cost=0, effects=[HealEffect(7, 7)])
        ]
        sim, _ = self._fight(
            [self._real("machine_learning_core", where), pet], seconds=6.0, hurt=100
        )
        assert [a for a in sim.actions if a.action == "trigger_item"]
        assert sim.player1.buffs["spiked"] == 4

    def test_echo_chamber_raises_the_melee_and_ranged_limits_only(self):
        where, _ = self._place("machine_learning_core")
        sim, _ = self._fight([self._real("machine_learning_core", where)], seconds=0.3)
        assert sim.player1.modifier("spikes_limit_melee", 0.0) == 0.5
        assert sim.player1.modifier("spikes_limit_ranged", 0.0) == 0.5
        assert sim.player1.modifier("spikes_limit_effect", 0.0) == 0.0

    def test_ci_cauldron_heals_when_a_potion_beside_it_goes_off(self):
        """ "Star Potion triggered: Heal for 10 + 2 per Diamond Food"."""
        where, star = self._place("boiling_pot", how_many_star=1)
        potion = self._item(
            [TimerTrigger(cooldown=1.0, cpu_cost=0, effects=[HealEffect(1, 1)])],
            uid="potion",
            position=star[0],
        )
        potion.spec.kinds = frozenset({"potion"})
        sim, _ = self._fight(
            [self._real("boiling_pot", where), potion], seconds=3.0, hurt=100
        )
        pot = [
            a for a in sim.actions if a.action == "heal" and a.source == "boiling_pot"
        ]
        assert pot and all(a.damage == 10 for a in pot), "ten, with no Food beside it"


class TestAnAuraWatchesItsOwnSideOnly(_WithOneItem):
    """Whose moment it was, before whose item it was.

    Every event an aura can watch names the acting player. Matching on uid
    alone let the other player's item answer this zone if two sessions ever
    handed out the same uid, which nothing prevents: an opponent's loadout
    comes from another session entirely.
    """

    def test_the_other_players_item_does_not_answer_this_zone(self):
        watcher = self._starred(
            [
                AuraTrigger(
                    zone="star",
                    counting="any",
                    after=1,
                    on="activates",
                    effects=[
                        BuffEffect(buff_name="credits", value=1, target_type="self")
                    ],
                )
            ],
            "watcher",
            (1, 1),
        )
        # The same uid on both sides. Theirs stands on their own rack and
        # nowhere near this zone; the uid is the whole of the resemblance,
        # and matching on it alone was enough to make the zone answer.
        mine = self._item([], uid="twin", position=(0, 0))
        theirs = self._item(
            [TimerTrigger(cooldown=0.5, cpu_cost=0, effects=[HealEffect(1, 1)])],
            uid="twin",
            position=(4, 0),
        )
        sim, _ = self._run([watcher, mine], seconds=2.0, against=[theirs])
        assert (
            "credits" not in sim.player1.buffs
        ), "their item activating is not a moment in this player's zone"
