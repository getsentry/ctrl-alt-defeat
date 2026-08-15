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
    DAMAGE_TAKEN = "damage_taken"
    ON_ATTACKED = "on_attacked"  # Before damage, for shields to block
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
    attacker_item_id: Optional[str] = None  # For ON_ATTACKED event
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


class ItemEventHandler:
    """Handles item-specific event logic"""

    def __init__(self, item, owner, event_manager: EventManager):
        self.item = item
        self.owner = owner
        self.event_manager = event_manager
        self.is_active = True

        # Subscribe to relevant events based on item trigger type
        self._setup_triggers()

    def _setup_triggers(self):
        """Set up event subscriptions based on item trigger type"""
        from battle_engine import TriggerType

        if self.item.spec.trigger_type == TriggerType.ON_BATTLE_START:
            self.event_manager.subscribe(EventType.BATTLE_START, self._on_battle_start)

        elif self.item.spec.trigger_type == TriggerType.ON_DAMAGED:
            # Subscribe with owner check
            self.event_manager.subscribe(
                EventType.DAMAGE_TAKEN,
                self._on_damage_taken,
                condition=lambda e: e.target == self.owner,
            )

        elif self.item.spec.trigger_type == TriggerType.ON_LOW_HEALTH:
            # Subscribe to health decrease events
            self.event_manager.subscribe(
                EventType.HEALTH_LOW,
                self._on_low_health,
                condition=lambda e: e.target == self.owner
                and self._check_activation_conditions(),
            )

        elif self.item.spec.trigger_type == TriggerType.ON_TIMER:
            # Schedule initial timer
            self._schedule_next_activation()

    def _check_activation_conditions(self) -> bool:
        """Check if item can activate (cooldown, CPU, etc)"""
        if not self.is_active:
            return False

        if self.item.current_cooldown > 0:
            return False

        # Check CPU cost
        cpu_cost = max(1, self.item.spec.cpu_cost - self.item.cpu_discount)
        if self.owner.cpu < cpu_cost:
            return False

        return True

    def _schedule_next_activation(self):
        """Schedule the next timer activation"""
        if not self.is_active:
            return

        # Apply speed modifiers
        speed = self.item.speed_mult

        # Calculate next activation time
        next_time = self.event_manager.current_time + (self.item.spec.cooldown / speed)

        # Schedule timer
        self.event_manager.schedule_timer(next_time, self.item.uid, self._on_timer)

    def _on_battle_start(self, event: Event):
        """Handle battle start trigger"""
        if self._check_activation_conditions():
            return self._activate()

    def _on_damage_taken(self, event: Event):
        """Handle damage taken trigger"""
        if self._check_activation_conditions():
            # Pass damage info to activation
            return self._activate(event.data)

    def _on_low_health(self, event: Event):
        """Handle low health trigger"""
        # Check if we're still below threshold
        health_percent = self.owner.quota / self.owner.max_quota
        if health_percent < 0.3 and self._check_activation_conditions():
            return self._activate()

    def _on_timer(self):
        """Handle timer trigger"""
        if self._check_activation_conditions():
            result = self._activate()
            # Schedule next activation
            self._schedule_next_activation()
            return result

    def _activate(self, context: Optional[Dict[str, Union[str, int]]] = None):
        """Actually activate the item"""
        # This will be implemented by the battle system
        return {"item": self.item, "owner": self.owner, "context": context or {}}

    def deactivate(self):
        """Deactivate this handler and cancel timers"""
        self.is_active = False
        self.event_manager.cancel_timer(self.item.uid)
