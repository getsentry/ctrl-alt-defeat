"""
Event-driven system for battle mechanics
Handles immediate triggers and timer-based events efficiently
"""

import heapq
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Union

# Avoid circular imports
if TYPE_CHECKING:
    from battle_engine import BattleItem, Player


class EventType(Enum):
    """All possible events in the battle system"""

    BATTLE_START = "battle_start"
    BATTLE_END = "battle_end"
    DAMAGE_DEALT = "damage_dealt"
    HEALTH_FELL = "health_fell"  # A player's health went down, from any source
    ON_ATTACKED = "on_attacked"  # Before damage when a player is hit
    ON_HIT = "on_hit"  # An attack landed, for the attacking item's on-hit effects
    PLAYER_DEATH = "player_death"  # A player died (check target to see which one)
    TIMER_TICK = "timer_tick"
    ITEM_ACTIVATED = "item_activated"
    ITEM_CONSUMED = "item_consumed"  # Item removed from battle (potions, etc)
    BUFF_APPLIED = "buff_applied"
    DEBUFF_APPLIED = "debuff_applied"
    CPU_EXHAUSTED = "cpu_exhausted"
    CPU_REGENERATED = "cpu_regenerated"


@dataclass
class EventData:
    """Type-safe event data"""

    damage: Optional[int] = None
    heal: Optional[int] = None
    item_id: Optional[str] = None
    buff_name: Optional[str] = None
    buff_value: Optional[int] = None
    previous_health: Optional[int] = None
    current_health: Optional[int] = None
    attacker_item_id: Optional[str] = None  # For ON_ATTACKED and ON_HIT events
    pending_damage: Optional[int] = None  # Damage before blocks/mitigation


@dataclass
class Event:
    """Represents a single event in the battle"""

    event_type: EventType
    source: Optional[
        Union["Player", "BattleItem"]
    ]  # The entity that triggered the event
    target: Optional[Union["Player", "BattleItem"]]  # The entity affected by the event
    data: EventData = field(default_factory=EventData)  # Type-safe event data
    timestamp: float = 0.0


@dataclass
class TimerEvent:
    """Represents a scheduled timer event"""

    activation_time: float
    item_id: str
    callback: Callable

    def __lt__(self, other):
        """For heap ordering - earliest time first"""
        return self.activation_time < other.activation_time


class EventManager:
    """Manages all events and triggers in the battle system"""

    def __init__(self):
        # Event listeners - maps event type to list of callbacks
        self.listeners: Dict[EventType, List[Callable]] = {
            event_type: [] for event_type in EventType
        }

        # Priority queue for timer events
        self.timer_queue: List[TimerEvent] = []

        # Track current time
        self.current_time: float = 0.0

        # Event history for replay/debugging
        self.event_history: List[Event] = []

    def subscribe(
        self,
        event_type: EventType,
        callback: Callable,
        condition: Optional[Callable] = None,
    ) -> None:
        """
        Subscribe to an event type

        Args:
            event_type: The type of event to listen for
            callback: Function to call when event occurs
            condition: Optional condition that must be true for callback to run
        """
        if condition:
            # Wrap callback with condition check
            def conditional_callback(event: Event):
                if condition(event):
                    return callback(event)
                return None

            self.listeners[event_type].append(conditional_callback)
        else:
            self.listeners[event_type].append(callback)

    def unsubscribe(self, event_type: EventType, callback: Callable) -> None:
        """Remove a callback from an event type"""
        if callback in self.listeners[event_type]:
            self.listeners[event_type].remove(callback)

    def emit(self, event: Event) -> List[Optional[Dict]]:
        """
        Emit an event and trigger all listeners

        Returns list of results from callbacks
        """
        event.timestamp = self.current_time
        self.event_history.append(event)

        results = []
        for callback in self.listeners[event.event_type]:
            result = callback(event)
            if result is not None:
                results.append(result)

        return results

    def schedule_timer(
        self, activation_time: float, item_id: str, callback: Callable
    ) -> None:
        """Schedule a timer event"""
        timer_event = TimerEvent(activation_time, item_id, callback)
        heapq.heappush(self.timer_queue, timer_event)

    def cancel_timer(self, item_id: str) -> bool:
        """Cancel all timer events for a specific item"""
        # Note: This is O(n) - could optimize with additional tracking
        original_queue = self.timer_queue
        self.timer_queue = [t for t in original_queue if t.item_id != item_id]
        heapq.heapify(self.timer_queue)
        return len(original_queue) != len(self.timer_queue)

    def process_timers(self, current_time: float) -> List[Optional[Dict]]:
        """
        Process all timer events up to current time

        Returns list of results from timer callbacks
        """
        self.current_time = current_time
        results = []

        while self.timer_queue and self.timer_queue[0].activation_time <= current_time:
            timer_event = heapq.heappop(self.timer_queue)
            result = timer_event.callback()
            if result is not None:
                results.append(result)

        return results

    def clear(self) -> None:
        """Clear all events and timers"""
        for event_type in EventType:
            self.listeners[event_type] = []
        self.timer_queue = []
        self.event_history = []
        self.current_time = 0.0
