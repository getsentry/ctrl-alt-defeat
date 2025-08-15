"""
Tests for the event-driven battle system
"""

import pytest
from dataclasses import dataclass
from event_system import (
    EventManager, EventType, Event, TimerEvent, ItemEventHandler
)

class TestEventManager:
    """Test the core event manager functionality"""
    
    def test_subscribe_and_emit(self):
        """Test basic event subscription and emission"""
        manager = EventManager()
        results = []
        
        def handler(event):
            results.append(event.data["value"])
            return event.data["value"] * 2
        
        manager.subscribe(EventType.DAMAGE_DEALT, handler)
        
        event = Event(
            event_type=EventType.DAMAGE_DEALT,
            source="attacker",
            target="defender",
            data={"value": 10}
        )
        
        returned = manager.emit(event)
        
        assert results == [10]
        assert returned == [20]
    
    def test_multiple_subscribers(self):
        """Test multiple subscribers to same event"""
        manager = EventManager()
        results = []
        
        def handler1(event):
            results.append("handler1")
        
        def handler2(event):
            results.append("handler2")
        
        manager.subscribe(EventType.BATTLE_START, handler1)
        manager.subscribe(EventType.BATTLE_START, handler2)
        
        event = Event(EventType.BATTLE_START, None, None)
        manager.emit(event)
        
        assert results == ["handler1", "handler2"]
    
    def test_conditional_subscription(self):
        """Test conditional event subscription"""
        manager = EventManager()
        results = []
        
        def handler(event):
            results.append(event.data["value"])
        
        # Only handle events where value > 5
        condition = lambda e: e.data.get("value", 0) > 5
        
        manager.subscribe(EventType.DAMAGE_DEALT, handler, condition)
        
        # This should not trigger
        event1 = Event(EventType.DAMAGE_DEALT, None, None, {"value": 3})
        manager.emit(event1)
        assert results == []
        
        # This should trigger
        event2 = Event(EventType.DAMAGE_DEALT, None, None, {"value": 10})
        manager.emit(event2)
        assert results == [10]
    
    def test_unsubscribe(self):
        """Test unsubscribing from events"""
        manager = EventManager()
        results = []
        
        def handler(event):
            results.append("called")
        
        manager.subscribe(EventType.BATTLE_END, handler)
        
        # First emission should work
        manager.emit(Event(EventType.BATTLE_END, None, None))
        assert len(results) == 1
        
        # Unsubscribe
        manager.unsubscribe(EventType.BATTLE_END, handler)
        
        # Second emission should not trigger
        manager.emit(Event(EventType.BATTLE_END, None, None))
        assert len(results) == 1
    
    def test_timer_scheduling(self):
        """Test timer event scheduling"""
        manager = EventManager()
        results = []
        
        def timer_callback():
            results.append(manager.current_time)
            return "activated"
        
        # Schedule timers at different times
        manager.schedule_timer(1.0, "item1", lambda: results.append(1.0))
        manager.schedule_timer(0.5, "item2", lambda: results.append(0.5))
        manager.schedule_timer(1.5, "item3", lambda: results.append(1.5))
        
        # Process up to time 0.7
        manager.process_timers(0.7)
        assert results == [0.5]
        
        # Process up to time 1.2
        manager.process_timers(1.2)
        assert results == [0.5, 1.0]
        
        # Process remaining
        manager.process_timers(2.0)
        assert results == [0.5, 1.0, 1.5]
    
    def test_timer_cancellation(self):
        """Test cancelling timer events"""
        manager = EventManager()
        results = []
        
        manager.schedule_timer(1.0, "item1", lambda: results.append("item1"))
        manager.schedule_timer(2.0, "item2", lambda: results.append("item2"))
        manager.schedule_timer(3.0, "item1", lambda: results.append("item1-2"))
        
        # Cancel all timers for item1
        cancelled = manager.cancel_timer("item1")
        assert cancelled == True
        
        # Process all timers
        manager.process_timers(5.0)
        
        # Only item2 should have fired
        assert results == ["item2"]
    
    def test_event_history(self):
        """Test that events are recorded in history"""
        manager = EventManager()
        
        event1 = Event(EventType.BATTLE_START, "player1", "player2")
        event2 = Event(EventType.DAMAGE_DEALT, "item1", "player2", {"damage": 10})
        
        manager.current_time = 0.0
        manager.emit(event1)
        
        manager.current_time = 1.5
        manager.emit(event2)
        
        assert len(manager.event_history) == 2
        assert manager.event_history[0].timestamp == 0.0
        assert manager.event_history[1].timestamp == 1.5
        assert manager.event_history[1].data["damage"] == 10
    
    def test_clear(self):
        """Test clearing all events and timers"""
        manager = EventManager()
        
        # Add some state
        manager.subscribe(EventType.BATTLE_START, lambda e: None)
        manager.schedule_timer(1.0, "item1", lambda: None)
        manager.emit(Event(EventType.BATTLE_START, None, None))
        
        # Clear everything
        manager.clear()
        
        assert all(len(listeners) == 0 for listeners in manager.listeners.values())
        assert len(manager.timer_queue) == 0
        assert len(manager.event_history) == 0
        assert manager.current_time == 0.0

class TestHealthTriggers:
    """Test health-based triggers work correctly"""
    
    def test_health_threshold_triggers(self):
        """Test that health triggers fire at correct thresholds"""
        manager = EventManager()
        
        @dataclass
        class MockPlayer:
            quota: int
            max_quota: int
            cpu: float = 10.0
        
        player = MockPlayer(quota=100, max_quota=100)
        triggered = []
        
        # Subscribe to low health
        def on_low_health(event):
            triggered.append(("low", event.target.quota))
        
        manager.subscribe(
            EventType.HEALTH_LOW,
            on_low_health,
            condition=lambda e: e.target.quota / e.target.max_quota < 0.3
        )
        
        # Damage player to 50 HP (50%) - should not trigger
        player.quota = 50
        manager.emit(Event(EventType.HEALTH_LOW, None, player))
        assert triggered == []
        
        # Damage to 29 HP (29%) - should trigger
        player.quota = 29
        manager.emit(Event(EventType.HEALTH_LOW, None, player))
        assert triggered == [("low", 29)]
        
        # If health is restored above threshold, should not trigger again
        player.quota = 40
        triggered.clear()
        manager.emit(Event(EventType.HEALTH_LOW, None, player))
        assert triggered == []
    
    def test_multiple_health_items(self):
        """Test multiple health items with first one healing above threshold"""
        manager = EventManager()
        
        @dataclass
        class MockPlayer:
            quota: int
            max_quota: int
            cpu: float = 10.0
        
        player = MockPlayer(quota=25, max_quota=100)  # 25% health
        activations = []
        
        def heal_potion1(event):
            # First potion heals to 35%
            if event.target.quota / event.target.max_quota < 0.3:
                event.target.quota = 35
                activations.append("potion1")
                return "healed"
        
        def heal_potion2(event):
            # Second potion only activates if still < 30%
            if event.target.quota / event.target.max_quota < 0.3:
                event.target.quota += 10
                activations.append("potion2")
                return "healed"
        
        # Both potions subscribe
        manager.subscribe(EventType.HEALTH_LOW, heal_potion1)
        manager.subscribe(EventType.HEALTH_LOW, heal_potion2)
        
        # Emit health low event
        manager.emit(Event(EventType.HEALTH_LOW, None, player))
        
        # Only first potion should activate
        assert activations == ["potion1"]
        assert player.quota == 35

class TestTimerOptimization:
    """Test the timer heap optimization"""
    
    def test_timer_heap_ordering(self):
        """Test that timer events are processed in correct order"""
        manager = EventManager()
        order = []
        
        # Add timers in random order
        manager.schedule_timer(3.0, "c", lambda: order.append("c"))
        manager.schedule_timer(1.0, "a", lambda: order.append("a"))
        manager.schedule_timer(2.0, "b", lambda: order.append("b"))
        manager.schedule_timer(1.5, "d", lambda: order.append("d"))
        
        # Process all at once
        manager.process_timers(5.0)
        
        # Should be processed in time order
        assert order == ["a", "d", "b", "c"]
    
    def test_timer_efficiency(self):
        """Test that only relevant timers are processed each tick"""
        manager = EventManager()
        processed = []
        
        # Schedule many timers
        for i in range(100):
            time = i * 0.5
            manager.schedule_timer(time, f"item_{i}", lambda i=i: processed.append(i))
        
        # Process only up to time 2.0
        manager.process_timers(2.0)
        
        # Should only process first 5 timers (0, 0.5, 1.0, 1.5, 2.0)
        assert len(processed) == 5
        assert processed == [0, 1, 2, 3, 4]
        
        # Remaining timers should still be in queue
        assert len(manager.timer_queue) == 95

class TestIntegration:
    """Test integration between events and items"""
    
    def test_damage_chain_reaction(self):
        """Test that damage can trigger chain reactions"""
        manager = EventManager()
        
        @dataclass
        class MockPlayer:
            quota: int
            max_quota: int
            cpu: float = 10.0
        
        player1 = MockPlayer(quota=100, max_quota=100)
        player2 = MockPlayer(quota=100, max_quota=100)
        
        actions = []
        
        # Reflect damage handler (like Session Replay)
        def reflect_damage(event):
            if event.target == player2:
                damage = event.data.get("damage", 0)
                reflect = int(damage * 0.3)
                actions.append(f"reflect_{reflect}")
                
                # Deal reflect damage back
                player1.quota -= reflect
                manager.emit(Event(
                    EventType.DAMAGE_DEALT,
                    player2,
                    player1,
                    {"damage": reflect, "type": "reflect"}
                ))
        
        # Subscribe to damage events
        manager.subscribe(EventType.DAMAGE_DEALT, reflect_damage)
        
        # Initial damage
        player2.quota -= 20
        manager.emit(Event(
            EventType.DAMAGE_DEALT,
            player1,
            player2,
            {"damage": 20}
        ))
        
        # Should have reflected 6 damage
        assert actions == ["reflect_6"]
        assert player1.quota == 94
        assert player2.quota == 80

if __name__ == "__main__":
    pytest.main([__file__, "-v"])