"""
Tests for the improved item effects system
"""

from dataclasses import dataclass

import pytest
from item_effects import (
    AttackEffect,
    BattleStartTrigger,
    BlockEffect,
    BuffEffect,
    DamageDealtTrigger,
    DamageTakenTrigger,
    DebuffEffect,
    HealEffect,
    ItemSpec,
    KillTrigger,
    PassiveTrigger,
    ReflectEffect,
    StatModEffect,
    StunEffect,
    TimerTrigger,
    create_example_items,
)


@dataclass
class MockPlayer:
    """Mock player for testing"""

    quota: int
    max_quota: int
    cpu: float = 10.0


@dataclass
class MockBattleState:
    """Mock battle state for testing"""

    current_time: float = 0.0


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
        assert trigger.should_activate("timer_tick", None, None, None) == True
        assert trigger.get_cpu_cost() == 3

        # Should not activate when on cooldown
        trigger.current_cooldown = 1.0
        assert trigger.should_activate("timer_tick", None, None, None) == False

        # Should not activate for wrong event type
        trigger.current_cooldown = 0.0
        assert trigger.should_activate("battle_start", None, None, None) == False

    def test_battle_start_trigger(self):
        """Test battle start trigger"""
        trigger = BattleStartTrigger(effects=[BlockEffect(block_amount=5)])

        assert trigger.should_activate("battle_start", None, None, None) == True
        assert trigger.should_activate("timer_tick", None, None, None) == False
        assert trigger.get_cpu_cost() == 0  # Battle start is free

    def test_damage_taken_trigger_no_threshold(self):
        """Test damage taken trigger without health threshold"""
        trigger = DamageTakenTrigger(
            threshold=None,
            cooldown=0.0,
            cpu_cost=2,
            effects=[ReflectEffect(reflect_percent=0.3)],
        )

        # Should always activate when damaged
        assert trigger.should_activate("damage_taken", None, None, None) == True
        assert trigger.get_cpu_cost() == 2

        # Should not activate for wrong event
        assert trigger.should_activate("timer_tick", None, None, None) == False

    def test_damage_taken_trigger_with_threshold(self):
        """Test damage taken trigger with health threshold"""
        player = MockPlayer(quota=25, max_quota=100)  # 25% health

        trigger = DamageTakenTrigger(
            threshold=0.3,  # Only below 30%
            cooldown=0.0,
            cpu_cost=3,
            effects=[HealEffect(min_heal=5, max_heal=5)],
        )

        # Should activate when below threshold
        assert trigger.should_activate("damage_taken", None, player, None) == True

        # Should not activate when above threshold
        player.quota = 40  # 40% health
        assert trigger.should_activate("damage_taken", None, player, None) == False

        # Should not activate when on cooldown
        player.quota = 25
        trigger.current_cooldown = 5.0
        assert trigger.should_activate("damage_taken", None, player, None) == False

    def test_damage_dealt_trigger(self):
        """Test damage dealt trigger with chance"""
        import random

        random.seed(42)  # For predictable testing

        trigger = DamageDealtTrigger(
            chance=0.5, effects=[StunEffect(stun_duration=1.0)]  # 50% chance
        )

        # Test multiple activations to verify chance
        activations = 0
        for _ in range(100):
            if trigger.should_activate("damage_dealt", None, None, None):
                activations += 1

        # Should be roughly 50% (allow some variance)
        assert 40 <= activations <= 60
        assert trigger.get_cpu_cost() == 0  # On-hit effects are free

    def test_passive_trigger(self):
        """Test passive trigger"""
        trigger = PassiveTrigger(effects=[StatModEffect(stat_name="max_cpu", value=5)])

        assert trigger.should_activate("passive_apply", None, None, None) == True
        assert trigger.should_activate("timer_tick", None, None, None) == False
        assert trigger.get_cpu_cost() == 0  # Passives are free

    def test_kill_trigger(self):
        """Test kill trigger"""
        trigger = KillTrigger(
            effects=[BuffEffect(buff_name="damage", value=2, duration=5.0)]
        )

        assert trigger.should_activate("enemy_killed", None, None, None) == True
        assert trigger.should_activate("damage_dealt", None, None, None) == False
        assert trigger.get_cpu_cost() == 0  # Kill effects are free


class TestItemSpecs:
    """Test complete item specifications"""

    def test_multi_trigger_item(self):
        """Test item with multiple triggers"""
        item = ItemSpec(
            id="complex_item",
            name="Complex Item",
            category="problem",
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
            tier=2,
            rarity="rare",
        )

        assert len(item.triggers) == 3
        assert item.category == "problem"
        assert item.tier == 2
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

    def test_example_items(self):
        """Test that example items are created correctly"""
        items = create_example_items()

        # Test Null Pointer
        null_pointer = items["null_pointer"]
        assert null_pointer.name == "Null Pointer Exception"
        assert len(null_pointer.triggers) == 1
        timer_trigger = null_pointer.triggers[0]
        assert isinstance(timer_trigger, TimerTrigger)
        assert timer_trigger.cooldown == 2.5
        assert timer_trigger.cpu_cost == 3

        # Test Error Monitoring with multiple triggers
        error_monitoring = items["error_monitoring"]
        assert len(error_monitoring.triggers) == 2
        assert isinstance(error_monitoring.triggers[0], BattleStartTrigger)
        assert isinstance(error_monitoring.triggers[1], PassiveTrigger)

        # Test Session Replay with mixed triggers
        session_replay = items["session_replay"]
        assert len(session_replay.triggers) == 2
        assert isinstance(session_replay.triggers[0], DamageTakenTrigger)
        assert isinstance(session_replay.triggers[1], TimerTrigger)

        # Test Alerting System with threshold
        alerting = items["alerting_system"]
        damage_trigger = alerting.triggers[0]
        assert isinstance(damage_trigger, DamageTakenTrigger)
        assert damage_trigger.threshold == 0.3
        assert damage_trigger.cooldown == 8.0
        assert len(damage_trigger.effects) == 2  # Heal + Block

        # Test Hybrid Assassin with complex triggers
        hybrid = items["hybrid_assassin"]
        assert len(hybrid.triggers) == 3
        assert hybrid.rarity == "legendary"

    def test_trigger_effect_combinations(self):
        """Test that triggers can have multiple effects"""
        items = create_example_items()

        # Memory Leak has attack + debuff
        memory_leak = items["memory_leak"]
        timer = memory_leak.triggers[0]
        assert len(timer.effects) == 2
        assert isinstance(timer.effects[0], AttackEffect)
        assert isinstance(timer.effects[1], DebuffEffect)

        # Alerting System has heal + block
        alerting = items["alerting_system"]
        damage_trigger = alerting.triggers[0]
        assert len(damage_trigger.effects) == 2
        assert isinstance(damage_trigger.effects[0], HealEffect)
        assert isinstance(damage_trigger.effects[1], BlockEffect)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
