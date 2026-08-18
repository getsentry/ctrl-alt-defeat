"""
Tests for the improved item effects system
"""

import random
from dataclasses import dataclass, field

from battle_engine import ITEM_CATALOG
from grid_system import ItemShape
from item_effects import (
    AttackEffect,
    BattleStartTrigger,
    BlockEffect,
    BuffEffect,
    DamageDealtTrigger,
    HealthThresholdTrigger,
    DebuffEffect,
    HealEffect,
    ItemSpec,
    KillTrigger,
    OnHitTrigger,
    PassiveTrigger,
    ReflectEffect,
    StatModEffect,
    StunEffect,
    TimerTrigger,
)


@dataclass
class MockPlayer:
    """Mock player for testing"""

    quota: int
    max_quota: int
    cpu: float = 10.0


@dataclass
class MockBattleState:
    """Mock battle state for testing

    It carries its own seeded RNG because the real simulator does. Every roll
    in a battle comes off that one generator, so a test that reaches for the
    global `random` instead is not testing the thing that ships.
    """

    current_time: float = 0.0
    rng: random.Random = field(default_factory=lambda: random.Random(42))


class TestEffects:
    """Test individual effect types"""

    def test_attack_effect(self):
        """Test attack effect properties"""
        effect = AttackEffect(
            min_damage=5,
            max_damage=10,
            accuracy=0.9,
            crit_chance=0.1,
            special="bypass_block",
        )

        result = effect.apply(None, None, None)
        assert result["type"] == "attack"
        assert result["min_damage"] == 5
        assert result["max_damage"] == 10
        assert result["accuracy"] == 0.9
        assert result["crit_chance"] == 0.1
        assert result["special"] == "bypass_block"

    def test_heal_effect(self):
        """Test heal effect properties"""
        effect = HealEffect(min_heal=5, max_heal=8, target_type="lowest_ally")
        result = effect.apply(None, None, None)

        assert result["type"] == "heal"
        assert result["min_heal"] == 5
        assert result["max_heal"] == 8
        assert result["target_type"] == "lowest_ally"

    def test_block_effect(self):
        """Test block effect properties"""
        effect = BlockEffect(block_amount=10, target_type="all_allies")
        result = effect.apply(None, None, None)

        assert result["type"] == "block"
        assert result["amount"] == 10
        assert result["target_type"] == "all_allies"

    def test_buff_effect(self):
        """Test buff effect properties"""
        effect = BuffEffect(
            buff_name="speed", value=0.25, duration=5.0, target_type="adjacent"
        )
        result = effect.apply(None, None, None)

        assert result["type"] == "buff"
        assert result["buff_name"] == "speed"
        assert result["value"] == 0.25
        assert result["duration"] == 5.0
        assert result["target_type"] == "adjacent"

    def test_stat_mod_effect(self):
        """Test stat modification effect"""
        effect = StatModEffect(stat_name="max_cpu", value=5)
        result = effect.apply(None, None, None)

        assert result["type"] == "stat_mod"
        assert result["stat"] == "max_cpu"
        assert result["value"] == 5


class TestTriggers:
    """Test trigger conditions"""

    def test_timer_trigger(self):
        """Test timer trigger activation"""
        trigger = TimerTrigger(
            cooldown=2.0,
            cpu_cost=3,
            effects=[AttackEffect(min_damage=5, max_damage=10)],
        )

        # Should activate when cooldown is 0
        trigger.current_cooldown = 0.0
        assert trigger.should_activate("timer_tick", None, None, None) is True
        assert trigger.get_cpu_cost() == 3

        # Should not activate when on cooldown
        trigger.current_cooldown = 1.0
        assert trigger.should_activate("timer_tick", None, None, None) is False

        # Should not activate for wrong event type
        trigger.current_cooldown = 0.0
        assert trigger.should_activate("battle_start", None, None, None) is False

    def test_battle_start_trigger(self):
        """Test battle start trigger"""
        trigger = BattleStartTrigger(effects=[BlockEffect(block_amount=5)])

        assert trigger.should_activate("battle_start", None, None, None) is True
        assert trigger.should_activate("timer_tick", None, None, None) is False
        assert trigger.get_cpu_cost() == 0  # Battle start is free

    def test_a_threshold_fires_when_health_falls_past_the_line(self):
        player = MockPlayer(quota=25, max_quota=100)  # a quarter left
        trigger = HealthThresholdTrigger(
            threshold=0.3, effects=[HealEffect(min_heal=5, max_heal=5)]
        )
        assert trigger.should_activate("health_threshold", None, player, None) is True

    def test_it_stays_quiet_above_the_line(self):
        player = MockPlayer(quota=40, max_quota=100)
        trigger = HealthThresholdTrigger(
            threshold=0.3, effects=[HealEffect(min_heal=5, max_heal=5)]
        )
        assert trigger.should_activate("health_threshold", None, player, None) is False

    def test_it_fires_once_and_no_more(self):
        """Section 2.1: falling past the line is the trigger, not being below
        it. Nearly every item with a threshold says "(once)"."""
        player = MockPlayer(quota=25, max_quota=100)
        trigger = HealthThresholdTrigger(
            threshold=0.5, effects=[HealEffect(min_heal=5, max_heal=5)]
        )
        assert trigger.should_activate("health_threshold", None, player, None) is True

        trigger.fired = True  # what the engine sets when it runs the effects
        player.quota = 5  # even lower, and still below the line
        assert trigger.should_activate("health_threshold", None, player, None) is False

    def test_it_answers_to_nothing_else(self):
        player = MockPlayer(quota=1, max_quota=100)
        trigger = HealthThresholdTrigger(threshold=0.5, effects=[])
        for event in ["timer_tick", "damage_taken", "on_hit", "on_attacked"]:
            assert trigger.should_activate(event, None, player, None) is False

    def test_noticing_your_own_health_is_free(self):
        assert HealthThresholdTrigger(threshold=0.5).get_cpu_cost() == 0

    def test_damage_dealt_trigger(self):
        """Test damage dealt trigger with chance"""
        battle_state = MockBattleState()

        trigger = DamageDealtTrigger(
            chance=0.5, effects=[StunEffect(stun_duration=1.0)]  # 50% chance
        )

        # Test multiple activations to verify chance
        activations = 0
        for _ in range(100):
            if trigger.should_activate("damage_dealt", None, None, battle_state):
                activations += 1

        # Should be roughly 50% (allow some variance)
        assert 40 <= activations <= 60
        assert trigger.get_cpu_cost() == 0  # On-hit effects are free

    def test_passive_trigger(self):
        """Test passive trigger"""
        trigger = PassiveTrigger(effects=[StatModEffect(stat_name="max_cpu", value=5)])

        assert trigger.should_activate("passive_apply", None, None, None) is True
        assert trigger.should_activate("timer_tick", None, None, None) is False
        assert trigger.get_cpu_cost() == 0  # Passives are free

    def test_kill_trigger(self):
        """Test kill trigger"""
        trigger = KillTrigger(
            effects=[BuffEffect(buff_name="damage", value=2, duration=5.0)]
        )

        assert trigger.should_activate("enemy_killed", None, None, None) is True
        assert trigger.should_activate("damage_dealt", None, None, None) is False
        assert trigger.get_cpu_cost() == 0  # Kill effects are free


class TestItemSpecs:
    """Test complete item specifications"""

    def test_multi_trigger_item(self):
        """Test item with multiple triggers"""
        item = ItemSpec(
            id="complex_item",
            name="Complex Item",
            shape=ItemShape([(0, 0)], "1x1"),
            slug="test_slug",
            category="problem",
            cost=1,
            player_class="neutral",
            triggers=[
                BattleStartTrigger(
                    effects=[BuffEffect(buff_name="speed", value=0.5, duration=3.0)]
                ),
                TimerTrigger(
                    cooldown=2.0,
                    cpu_cost=3,
                    effects=[
                        AttackEffect(min_damage=5, max_damage=10),
                        DebuffEffect(debuff_name="slow", value=0.2, duration=2.0),
                    ],
                ),
                KillTrigger(effects=[HealEffect(min_heal=3, max_heal=5)]),
            ],
            rarity="rare",
        )

        assert len(item.triggers) == 3
        assert item.category == "problem"
        assert item.rarity == "rare"

        # Test first trigger (battle start)
        battle_start = item.triggers[0]
        assert isinstance(battle_start, BattleStartTrigger)
        assert len(battle_start.effects) == 1
        assert isinstance(battle_start.effects[0], BuffEffect)

        # Test second trigger (timer)
        timer = item.triggers[1]
        assert isinstance(timer, TimerTrigger)
        assert timer.cooldown == 2.0
        assert timer.cpu_cost == 3
        assert len(timer.effects) == 2

        # Test third trigger (kill)
        kill = item.triggers[2]
        assert isinstance(kill, KillTrigger)
        assert len(kill.effects) == 1
        assert isinstance(kill.effects[0], HealEffect)

    def test_trigger_effect_combinations(self):
        """Test that triggers can have multiple effects"""
        # One timer, one attack
        stack_smasher = ITEM_CATALOG["stack_smasher"]
        timer = stack_smasher.triggers[0]
        assert len(timer.effects) == 1
        assert isinstance(timer.effects[0], AttackEffect)

        # DDoS Attack has attack effect
        ddos = ITEM_CATALOG["denier_of_service"]
        if ddos:  # Check if exists in JSON
            timer = ddos.triggers[0]
            assert len(timer.effects) >= 1
            assert isinstance(timer.effects[0], AttackEffect)


class TestOnHitTrigger:
    """Section 1.3: an on-hit trigger fires only when the attack lands"""

    def test_fires_on_a_hit(self):
        """With no chance given, a landed hit always reaches the effects"""
        trigger = OnHitTrigger(effects=[DebuffEffect("memory_leaked", 2)])
        assert trigger.should_activate("on_hit", None, None, None) is True

    def test_ignores_every_other_event(self):
        """It must not answer a timer tick or a miss"""
        trigger = OnHitTrigger(effects=[DebuffEffect("memory_leaked", 2)])
        for event in ["timer_tick", "battle_start", "damage_taken", "on_attacked"]:
            assert trigger.should_activate(event, None, None, None) is False

    def test_chance_is_rolled_after_the_hit(self):
        """Virus Injector's 70% is a second roll, taken once accuracy passed"""
        trigger = OnHitTrigger(chance=0.7, effects=[DebuffEffect("memory_leaked", 2)])

        class Rolls(MockBattleState):
            """A battle whose next roll is known"""

            def __init__(self, value):
                self.rng = self
                self.value = value

            def random(self):
                return self.value

        assert trigger.should_activate("on_hit", None, None, Rolls(0.69)) is True
        assert trigger.should_activate("on_hit", None, None, Rolls(0.71)) is False

    def test_costs_no_cpu(self):
        """The activation that landed the hit already paid"""
        assert OnHitTrigger(chance=0.7).get_cpu_cost() == 0

    def test_debuff_lasts_the_whole_battle(self):
        """Section 3.2: no debuff wears off, so a duration is never needed"""
        assert DebuffEffect("memory_leaked", 2).duration == -1
