"""
Every mechanic verified against the spec
Event-driven system with priority queue for timers
"""

import random
import time
import uuid
from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, TypedDict

from config_loader import config_loader
from containers import Container, PlacementValidator
from event_system import Event, EventData, EventManager, EventType
from grid_system import ItemShape, Rotation
from item_effects import (
    AttackEffect,
    BattleStartTrigger,
    BlockEffect,
    BuffEffect,
    ConsumeEffect,
    DamageTakenTrigger,
    DebuffEffect,
    Effect,
    HealEffect,
    CpuDrainEffect,
    ItemSpec,
    OnAttackedTrigger,
    OnHitTrigger,
    PassiveTrigger,
    PreventDamageEffect,
    ReflectEffect,
    StatModEffect,
    TimerTrigger,
)
from schemas import BattleAction

MEMORY_LEAKED = "memory_leaked"
POISON_PERIOD = 2.0


class OverTimeEffect(ABC):
    """Something a player's own state does to them, once each period.

    Backpack Battles has three, and no more. They are worth listing, because
    the shape of this class is decided by the third:

    | Effect       | Period | Amount                        | Driven by     |
    |--------------|--------|-------------------------------|---------------|
    | Poison       | 2s     | 1 damage per stack            | a stack count |
    | Regeneration | 2s     | 1 health per stack            | a stack count |
    | Fatigue      | 1s     | escalating, from nightfall    | its own last  |

    Fatigue's amount comes from what it dealt last time, not from any stack,
    so no arrangement of "damage per stack" and "heal per stack" fields can
    hold it. Each effect therefore works out its own payout and applies it.

    None of the stat buffs belong here. Heat, Cold, Blind, Luck and Empower do
    not tick -- they are read at the moment they matter, when an activation is
    scheduled or an accuracy roll is made. Spikes and Vampirism are reactive,
    not periodic. An over-time effect is one that happens on a clock.

    `pay` routes through the simulator rather than writing to the player, so
    the damage travels the same road as every other kind and everything
    watching a player's health still sees it. Section 3.2 of the design
    document, and "Where a trigger belongs" in docs/effects.md.
    """

    #: The buff or debuff behind it, which is also its key in `Player.paid_at`
    name: str = ""

    #: Seconds between payouts
    period: float = 0.0

    @abstractmethod
    def pay(self, player: "Player", battle: "BattleSimulator") -> None:
        """Called once per period. Do nothing if nothing is owed."""


class MemoryLeaked(OverTimeEffect):
    """Poison. Section 3.2: 1 damage per stack, every 2 seconds."""

    name = MEMORY_LEAKED
    period = POISON_PERIOD

    def pay(self, player: "Player", battle: "BattleSimulator") -> None:
        # Read when it pays, so a stack applied since the last payout counts
        # in full at this one. Paying spends none of them.
        stacks = player.debuffs.get(self.name, 0)
        if stacks <= 0:
            return

        battle._take_damage(
            player,
            stacks,
            source="system",  # No one item is behind it once stacked
            action="dot",
            attacker=None,  # The stacks are the source
            details={"debuff_name": self.name},
        )


#: Every over-time effect in the game, in the order they pay out.
#: Regeneration and Fatigue are not built yet -- see the table on
#: OverTimeEffect for how each one fits.
OVER_TIME: List[OverTimeEffect] = [MemoryLeaked()]


# BattleItem will reference the new ItemSpec from item_effects.py


@dataclass
class BattleItem:
    """An item placed in the server room/rack (Section 4)"""

    spec: ItemSpec
    position: Tuple[int, int]  # Grid position (top-left for multi-square items)
    uid: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    rotation: Rotation = field(default=Rotation.NONE)

    # Battle state
    current_cooldown: float = 0.0
    memory_leak_stacks: int = 0  # For Memory Leak special

    # Modifiers from adjacency (Section 4.3)
    damage_mult: float = 1.0
    accuracy_bonus: float = 0.0
    speed_mult: float = 1.0
    cpu_discount: int = 0

    @property
    def shape(self) -> ItemShape:
        """Get shape from spec"""
        return self.spec.shape

    def get_occupied_squares(self) -> List[Tuple[int, int]]:
        """Get all grid squares this item occupies"""
        rotated_shape = self.shape.rotate(self.rotation)
        return [
            (self.position[0] + dx, self.position[1] + dy)
            for dx, dy in rotated_shape.squares
        ]


@dataclass
class Player:
    """Player state per Section 1"""

    id: int  # 1 or 2

    # Section 1.1: Player Quota (Health)
    quota: int  # Current
    max_quota: int  # Based on round

    # Section 1.2: CPU Cycles (Stamina)
    cpu: float  # Current cycles
    max_cpu: int = 3
    cpu_regen: float = 1.0  # Per second

    # Section 3: Buffs & Debuffs
    buffs: Dict[str, int] = field(default_factory=dict)
    debuffs: Dict[str, int] = field(default_factory=dict)

    # Session Replay special tracking
    recorded_attacks: List[Dict] = field(default_factory=list)

    # When each over-time effect last paid out, keyed by the buff or debuff
    # behind it.
    paid_at: Dict[str, float] = field(default_factory=dict)

    def reset_for_battle(self) -> None:
        """Forget everything the last battle left here.

        One call clears every field a battle writes, so nothing can survive
        into a later round. Adding a new piece of battle state means clearing
        it here, and nowhere else.
        """
        self.buffs.clear()
        self.debuffs.clear()
        self.recorded_attacks.clear()
        self.paid_at.clear()

    def period_due(self, name: str, period: float, now: float) -> bool:
        """True once per period, on the period, timed from the battle start.

        The epsilon is for the battle loop, which adds its tick to a float:
        twenty tenths of a second come to 1.9999999999999998. Without it every
        period would pay one tick late, and the lateness would compound.
        """
        due_at = self.paid_at.get(name, 0.0) + period
        if now + 1e-9 < due_at:
            return False
        self.paid_at[name] = due_at
        return True


ITEM_CATALOG = config_loader.items


class BattleResult(TypedDict):
    """Type definition for simulate_battle return value"""

    winner: int  # 1 for player1, 2 for player2
    duration: float  # Battle duration in seconds
    player1_quota: int  # Player 1's remaining quota
    player2_quota: int  # Player 2's remaining quota
    actions: List[BattleAction]  # Battle action timeline with BattleAction objects
    seed: int  # RNG seed used for the battle
    player1_items: List[BattleItem]  # Player 1's loadout
    player2_items: List[BattleItem]  # Player 2's loadout
    player1_containers: List[Container]  # Player 1's containers
    player2_containers: List[Container]  # Player 2's containers


class BattleSimulator:
    """Simulates battles per Game Design Document specifications"""

    def __init__(self, seed: Optional[int] = None):
        self.max_duration = 60.0  # Section 6.2
        self.tick_rate = 0.1  # Section 10.1: 10 ticks/second
        self.current_time = 0.0
        self.actions: List[BattleAction] = []
        self.event_manager = EventManager()
        self.consumed_items = set()  # Track consumed item UIDs

        # Initialize RNG with seed for deterministic battles
        self.seed = (
            seed if seed is not None else int(time.time() * 1000000) % 2147483647
        )
        self.rng = random.Random(self.seed)

    def _time_ms(self) -> int:
        """Convert current time to milliseconds for BattleAction

        Rounds rather than truncates. The loop adds `tick_rate` to a float
        sixty times a second, so by six seconds the clock reads
        5.999999999999995. Truncating that logged a 6.0s event at 5999ms, and
        every later event drifted the same way. The client replays off these
        timestamps, so the error was visible.
        """
        return round(self.current_time * 1000)

    def simulate_battle(
        self,
        p1_items: List[BattleItem],
        p2_items: List[BattleItem],
        round_number: int = 1,
        p1_containers: Optional[List[Container]] = None,
        p2_containers: Optional[List[Container]] = None,
    ) -> BattleResult:
        """
        Simulate battle following Section 1.3 Item Activation Flow
        Returns compact action log per Section 10.2
        """
        # Get quota based on round (Section 1.1)
        quota = self._get_round_quota(round_number)

        # Initialize players
        # Both start on a full pool. Naming the number here would let it drift
        # from max_cpu, which is what happened when the pool was last changed.
        player1 = Player(id=1, quota=quota, max_quota=quota, cpu=0.0)
        player2 = Player(id=2, quota=quota, max_quota=quota, cpu=0.0)
        player1.cpu = float(player1.max_cpu)
        player2.cpu = float(player2.max_cpu)

        # Deep copy items to avoid mutation
        p1_items = deepcopy(p1_items)
        p2_items = deepcopy(p2_items)

        # ALWAYS validate with containers - containers are REQUIRED
        if p1_containers is None or p2_containers is None:
            raise ValueError("Containers are required for battle simulation")

        if not self._validate_placement_with_containers(p1_items, p1_containers):
            raise ValueError(
                "Invalid placement for player 1 items - items overlap or are outside containers"
            )
        if not self._validate_placement_with_containers(p2_items, p2_containers):
            raise ValueError(
                "Invalid placement for player 2 items - items overlap or are outside containers"
            )

        # Reset state
        self.current_time = 0.0
        self.actions = []
        self.event_manager.clear()
        self.consumed_items = set()
        player1.reset_for_battle()
        player2.reset_for_battle()

        # Calculate adjacency (Section 4.2 & 4.3)
        self._calculate_adjacency(p1_items)
        self._calculate_adjacency(p2_items)

        # Apply infrastructure effects (Section 2.3)
        self._apply_infrastructure(p1_items, player1)
        self._apply_infrastructure(p2_items, player2)

        # Set up event handlers for items
        self._setup_item_handlers(p1_items, player1, player2)
        self._setup_item_handlers(p2_items, player2, player1)

        # Emit battle start event
        self.event_manager.emit(Event(EventType.BATTLE_START, None, None))
        self.actions.append(
            BattleAction(
                timestamp=0,
                source="system",
                action="battle_start",
                target=None,
                damage=None,
                player=0,  # 0 for system events
                details=None,
            )
        )

        # Main battle loop (Section 6.2)
        while self.current_time < self.max_duration:
            # CPU regeneration (Section 1.2)
            player1.cpu = min(
                player1.max_cpu, player1.cpu + player1.cpu_regen * self.tick_rate
            )
            player2.cpu = min(
                player2.max_cpu, player2.cpu + player2.cpu_regen * self.tick_rate
            )

            # Process timer events efficiently with heap
            self.event_manager.current_time = self.current_time
            self.event_manager.process_timers(self.current_time)

            # Pay out over-time effects (Sections 3.1 and 3.2)
            self._apply_over_time(player1)
            self._apply_over_time(player2)

            # Check for defeat
            if player1.quota <= 0:
                self.actions.append(
                    BattleAction(
                        timestamp=self._time_ms(),
                        source="system",
                        action="player_defeated",
                        target=None,
                        damage=None,
                        player=1,
                        details=None,
                    )
                )
                break
            if player2.quota <= 0:
                self.actions.append(
                    BattleAction(
                        timestamp=self._time_ms(),
                        source="system",
                        action="player_defeated",
                        target=None,
                        damage=None,
                        player=2,
                        details=None,
                    )
                )
                break

            # Apply fatigue (Section 7.1)
            if self.current_time >= 30:
                # Damage increases by 1 per 5 seconds after 30s
                fatigue_bonus = int((self.current_time - 30) / 5)
                # Apply to all items
                for item in p1_items + p2_items:
                    if item.spec.category == "problem":
                        # Apply fatigue to all attack effects in all triggers
                        for trigger in item.spec.triggers:
                            for effect in trigger.effects:
                                if hasattr(
                                    effect, "min_damage"
                                ):  # Check if it's an attack effect
                                    # Store original values if not yet stored
                                    if not hasattr(effect, "_original_min_damage"):
                                        effect._original_min_damage = effect.min_damage
                                        effect._original_max_damage = effect.max_damage
                                    effect.min_damage = (
                                        effect._original_min_damage + fatigue_bonus
                                    )
                                    effect.max_damage = (
                                        effect._original_max_damage + fatigue_bonus
                                    )

            self.current_time += self.tick_rate

        # Determine winner (Section 6.2)
        winner = 1 if player1.quota > player2.quota else 2

        return BattleResult(
            winner=winner,
            duration=round(self.current_time, 1),
            player1_quota=max(0, player1.quota),
            player2_quota=max(0, player2.quota),
            actions=self.actions,
            seed=self.seed,  # Include seed for replay/debugging
            player1_items=p1_items,  # Include player 1 loadout
            player2_items=p2_items,  # Include player 2 (enemy) loadout
            player1_containers=p1_containers,  # Include player 1 containers
            player2_containers=p2_containers,  # Include player 2 containers
        )

    # Quota per round, from Backpack Battles. Eighteen rounds is the whole game
    # there, so a higher round clamps to the last rather than extrapolating.
    ROUND_QUOTA = (
        25, 35, 45, 55, 70, 85, 100, 115, 130,
        150, 170, 190, 210, 230, 260, 290, 320, 350,
    )

    def _get_round_quota(self, round_num: int) -> int:
        """Get quota based on round number (Section 1.1)"""
        index = min(max(round_num, 1), len(self.ROUND_QUOTA)) - 1
        return self.ROUND_QUOTA[index]

    def _calculate_adjacency(self, items: List[BattleItem]):
        """Calculate adjacency bonuses (Section 4.2 & 4.3)"""
        for item in items:
            if item.uid in self.consumed_items:
                continue  # Skip consumed items
            adjacent = self._get_adjacent_items(item, items)

            # Count categories
            problems = sum(1 for i in adjacent if i.spec.category == "problem")
            defenses = sum(1 for i in adjacent if i.spec.category == "defense")
            infrastructure = sum(
                1 for i in adjacent if i.spec.category == "infrastructure"
            )

            # Bug Swarm: 3+ problems = +20% damage (Section 4.3)
            if (
                item.spec.category == "problem" and problems >= 2
            ):  # 2 because we need 3 total
                item.damage_mult *= 1.2

            # Error Monitoring: Adjacent problems gain +10% accuracy (Section 2.2)
            if item.spec.category == "problem":
                for adj in adjacent:
                    if adj.spec.name == "Error Monitoring":
                        item.accuracy_bonus += 0.1

            # Performance Monitoring: Reduces cooldowns by 0.5s when adjacent to problems
            if item.spec.category == "problem":
                for adj in adjacent:
                    if adj.spec.name == "Performance Monitoring":
                        # Reduce cooldown for all timer triggers
                        for trigger in item.spec.triggers:
                            if isinstance(trigger, TimerTrigger):
                                trigger.cooldown = max(0.5, trigger.cooldown - 0.5)

            # Full Stack: Problem + Defense + Infrastructure = 30% faster (Section 4.3)
            if problems >= 1 and defenses >= 1 and infrastructure >= 1:
                item.speed_mult *= 1.3

            # CDN: Adjacent items gain First Strike (Section 2.3)
            for adj in adjacent:
                if adj.spec.name == "CDN":
                    # Set initial cooldown for timer triggers to activate immediately
                    for trigger in item.spec.triggers:
                        if isinstance(trigger, TimerTrigger):
                            trigger.current_cooldown = -0.1  # Will activate immediately

            # Load Balancer: Distributes stamina cost (Section 2.3)
            if any(adj.spec.name == "Load Balancer" for adj in adjacent):
                item.cpu_discount = max(1, item.cpu_discount + 1)

    def _get_adjacent_items(
        self, item: BattleItem, all_items: List[BattleItem]
    ) -> List[BattleItem]:
        """Get orthogonally adjacent items supporting multi-square items"""
        adjacent = []

        # Get all squares occupied by this item
        item_squares = set(item.get_occupied_squares())

        # Get all adjacent squares (orthogonal only)
        adjacent_squares = set()
        for x, y in item_squares:
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                adj_square = (x + dx, y + dy)
                if adj_square not in item_squares:  # Don't include item's own squares
                    adjacent_squares.add(adj_square)

        # Check which items occupy these adjacent squares
        for other in all_items:
            if other.uid == item.uid:
                continue
            if other.uid in self.consumed_items:
                continue  # Skip consumed items

            # Get squares occupied by the other item
            other_squares = set(other.get_occupied_squares())

            # If any of the other item's squares are adjacent to this item
            if adjacent_squares & other_squares:  # Set intersection
                adjacent.append(other)

        return adjacent

    def _apply_infrastructure(self, items: List[BattleItem], player: Player):
        """Apply infrastructure passive effects (Section 2.3)"""
        for item in items:
            if item.spec.category != "infrastructure":
                continue

            # Apply passive effects immediately
            for trigger in item.spec.triggers:
                if isinstance(trigger, PassiveTrigger):
                    for effect in trigger.effects:
                        if isinstance(effect, StatModEffect):
                            if effect.stat_name == "max_cpu":
                                player.max_cpu += effect.value
                            elif effect.stat_name == "cpu_regen":
                                player.cpu_regen += effect.value

    def _setup_item_handlers(
        self, items: List[BattleItem], owner: Player, enemy: Player
    ):
        """Set up event handlers for items based on their triggers"""
        for item in items:
            if item.uid in self.consumed_items:
                continue  # Skip consumed items
            # Each item can have multiple triggers with multiple effects
            for trigger in item.spec.triggers:
                if isinstance(trigger, BattleStartTrigger):
                    # Subscribe to battle start - fires immediately
                    def handle_battle_start(
                        event, trigger=trigger, item=item, owner=owner
                    ):
                        self._apply_effects(trigger.effects, item, owner, enemy)

                    self.event_manager.subscribe(
                        EventType.BATTLE_START, handle_battle_start
                    )

                elif isinstance(trigger, TimerTrigger):
                    # Create unique ID for this trigger-timer combination
                    trigger_index = item.spec.triggers.index(trigger)
                    trigger_uid = f"{item.uid}_trigger_{trigger_index}"
                    # Schedule first activation using timer heap
                    self._schedule_timer_trigger(
                        trigger, item, owner, enemy, trigger_uid
                    )

                elif isinstance(trigger, DamageTakenTrigger):
                    # Subscribe to damage events - check threshold if needed
                    def handle_damage_taken(
                        event, trigger=trigger, item=item, owner=owner
                    ):
                        if event.target != owner:
                            return

                        # Skip if item is consumed
                        if item.uid in self.consumed_items:
                            return

                        # Check if trigger should activate
                        if not trigger.should_activate(
                            "damage_taken", owner, owner, None
                        ):
                            return

                        # Check CPU cost
                        cpu_cost = trigger.get_cpu_cost()
                        if owner.cpu >= cpu_cost:
                            self._apply_effects(trigger.effects, item, owner, enemy)
                            owner.cpu -= cpu_cost
                            trigger.current_cooldown = trigger.cooldown

                    self.event_manager.subscribe(
                        EventType.DAMAGE_TAKEN, handle_damage_taken
                    )

                elif isinstance(trigger, OnHitTrigger):
                    # Fires only for this item's own landed attacks. Another
                    # item's miss must never cost this one its on-hit effect,
                    # so the attacker is checked by uid rather than by owner.
                    def handle_on_hit(event, trigger=trigger, item=item, owner=owner):
                        if event.data.attacker_item_id != item.uid:
                            return
                        if item.uid in self.consumed_items:
                            return
                        # The chance roll lives here, after accuracy passed.
                        if not trigger.should_activate("on_hit", item, enemy, self):
                            return
                        self._apply_effects(trigger.effects, item, owner, enemy)

                    self.event_manager.subscribe(EventType.ON_HIT, handle_on_hit)

                elif isinstance(trigger, PassiveTrigger):
                    # Apply passive effects immediately
                    self._apply_effects(trigger.effects, item, owner, enemy)

                elif isinstance(trigger, OnAttackedTrigger):
                    def handle_on_attacked(
                        event, trigger=trigger, item=item, owner=owner
                    ):
                        if event.target != owner:
                            return
                        if item.uid in self.consumed_items:
                            return
                        if not trigger.should_activate(
                            "on_attacked", item, owner, self
                        ):
                            return

                        prevented = 0
                        remaining = event.data.pending_damage
                        for effect in trigger.effects:
                            if isinstance(effect, PreventDamageEffect):
                                stopped = min(effect.amount, remaining)
                                prevented += stopped
                                remaining -= stopped
                            else:
                                self._apply_effects([effect], item, owner, enemy)

                        if prevented:
                            self.actions.append(
                                BattleAction(
                                    timestamp=self._time_ms(),
                                    source=item.uid,
                                    action="block",
                                    target=None,
                                    damage=prevented,
                                    player=owner.id,
                                    details=None,
                                )
                            )
                        return {"blocked": prevented}

                    self.event_manager.subscribe(
                        EventType.ON_ATTACKED, handle_on_attacked
                    )

    def _schedule_timer_trigger(
        self,
        trigger: TimerTrigger,
        item: BattleItem,
        owner: Player,
        enemy: Player,
        trigger_uid: str,
    ):
        """Schedule timer-based trigger activation using priority queue"""
        # Apply speed modifiers
        speed = item.speed_mult

        # Calculate next activation time
        cooldown_adjusted = trigger.cooldown / speed
        next_time = self.current_time + cooldown_adjusted

        def activate():
            # Skip if item is consumed
            if item.uid in self.consumed_items:
                return

            # Check CPU availability
            cpu_cost = max(1, trigger.get_cpu_cost() - item.cpu_discount)

            if owner.cpu >= cpu_cost:
                # Have enough CPU - apply the effects
                self._apply_effects(trigger.effects, item, owner, enemy)
                owner.cpu -= cpu_cost
                trigger.current_cooldown = trigger.cooldown
            else:
                # Not enough CPU - log throttle but don't activate
                self.actions.append(
                    BattleAction(
                        timestamp=self._time_ms(),
                        source=item.uid,
                        action="cpu_fail",
                        target=None,
                        damage=None,
                        player=owner.id,
                        details={"reason": "Insufficient CPU"},
                    )
                )

            # Always schedule next activation at regular cooldown (unless consumed)
            # This keeps the item on its normal schedule regardless of CPU
            if item.uid not in self.consumed_items:
                self._schedule_timer_trigger(trigger, item, owner, enemy, trigger_uid)

        self.event_manager.schedule_timer(next_time, trigger_uid, activate)

    def _apply_effects(
        self, effects: List[Effect], item: BattleItem, owner: Player, enemy: Player
    ):
        """Apply a list of effects from a trigger"""
        for effect in effects:
            # Pass item as source for ConsumeEffect to work
            result = effect.apply(item, enemy, self)

            if isinstance(effect, AttackEffect):
                # Handle attack effect
                self._process_attack(result, item, owner, enemy)
            elif isinstance(effect, HealEffect):
                # Handle heal effect
                heal = self.rng.randint(result["min_heal"], result["max_heal"])
                owner.quota = min(owner.max_quota, owner.quota + heal)
                self.actions.append(
                    BattleAction(
                        timestamp=self._time_ms(),
                        source=item.uid,
                        action="heal",
                        target=None,
                        damage=heal,  # Use damage field for heal amount
                        player=owner.id,
                        details=None,
                    )
                )
            elif isinstance(effect, BlockEffect):
                # Handle block effect
                owner.buffs["block"] = owner.buffs.get("block", 0) + result["amount"]
                self.actions.append(
                    BattleAction(
                        timestamp=self._time_ms(),
                        source=item.uid,
                        action="block",
                        target=None,
                        damage=result["amount"],  # Block amount
                        player=owner.id,
                        details=None,
                    )
                )
            elif isinstance(effect, BuffEffect):
                # Handle buff effect
                owner.buffs[result["buff_name"]] = (
                    owner.buffs.get(result["buff_name"], 0) + result["value"]
                )
                self.actions.append(
                    BattleAction(
                        timestamp=self._time_ms(),
                        source=item.uid,
                        action="buff",
                        target=None,
                        damage=(
                            int(result["value"] * 100)
                            if isinstance(result["value"], float)
                            else result["value"]
                        ),  # Convert float to int percentage
                        player=owner.id,
                        details={
                            "buff_name": result["buff_name"],
                            "actual_value": result["value"],
                        },
                    )
                )
            elif isinstance(effect, DebuffEffect):
                # Handle debuff effect
                if self.rng.random() < result["accuracy"]:
                    enemy.debuffs[result["debuff_name"]] = (
                        enemy.debuffs.get(result["debuff_name"], 0) + result["value"]
                    )
                    self.actions.append(
                        BattleAction(
                            timestamp=self._time_ms(),
                            source=item.uid,
                            action="debuff",
                            target=None,
                            damage=(
                                int(result["value"] * 100)
                                if isinstance(result["value"], float)
                                else result["value"]
                            ),  # Convert float to int percentage
                            player=enemy.id,
                            details={
                                "debuff_name": result["debuff_name"],
                                "actual_value": result["value"],
                            },
                        )
                    )
            elif isinstance(effect, ReflectEffect):
                # Reflect is handled in damage events
                owner.buffs["reflect"] = result["percent"]
            elif isinstance(effect, StatModEffect):
                # Handle stat modification
                if result["stat"] == "max_cpu":
                    owner.max_cpu += result["value"]
                elif result["stat"] == "cpu_regen":
                    owner.cpu_regen += result["value"]
            elif isinstance(effect, CpuDrainEffect):
                # Backpack Battles calls it removing stamina. Nobody can be
                # put into debt by it, so it floors at zero rather than going
                # negative and locking the loser out for the rest of the
                # battle.
                drained = owner if result["target_type"] == "self" else enemy
                drained.cpu = max(0.0, drained.cpu - result["amount"])
                self.actions.append(
                    BattleAction(
                        timestamp=self._time_ms(),
                        source=item.uid,
                        action="cpu_drain",
                        target=None,
                        damage=None,
                        player=drained.id,
                        details={"amount": result["amount"]},
                    )
                )
            elif isinstance(effect, ConsumeEffect):
                # Mark item for removal and emit event
                self._consume_item(item, owner)
            else:
                raise TypeError(
                    f"{item.spec.id}: {type(effect).__name__} has no handler "
                    f"in _apply_effects"
                )

    def _process_attack(
        self, attack_data: dict, item: BattleItem, owner: Player, enemy: Player
    ):
        """Process an attack effect"""
        # Check accuracy
        accuracy = attack_data["accuracy"] + item.accuracy_bonus
        if "rate_limited" in owner.debuffs:
            accuracy -= owner.debuffs["rate_limited"] * 0.05

        if self.rng.random() > accuracy:
            # Miss
            self.actions.append(
                BattleAction(
                    timestamp=self._time_ms(),
                    source=item.uid,
                    action="miss",
                    target=None,
                    damage=None,
                    player=owner.id,
                    details=None,
                )
            )
            return

        # Calculate damage
        damage = self.rng.randint(attack_data["min_damage"], attack_data["max_damage"])
        damage = int(damage * item.damage_mult)

        # Check crit
        is_crit = self.rng.random() < attack_data["crit_chance"]
        if is_crit:
            damage *= 2

            # Special crit effects
            if attack_data.get("special") == "crash" and self.rng.random() < 0.2:
                damage = 15  # Instant 15 damage

            self.actions.append(
                BattleAction(
                    timestamp=self._time_ms(),
                    source=item.uid,
                    action="critical_hit",
                    target=None,
                    damage=damage,
                    player=owner.id,
                    details=None,
                )
            )

        # Handle special attack types
        if attack_data.get("special") == "stacking":
            # Memory leak stacking damage
            item.memory_leak_stacks += 1
            damage += item.memory_leak_stacks
        elif attack_data.get("special") == "bypass_block":
            # SQL injection bypasses blocks
            if "block" in enemy.buffs:
                enemy.buffs["block"] = int(enemy.buffs["block"] * 0.5)

        # Shields roll and Block is spent, both because this was an attack.
        damage = self._mitigate_attack(enemy, damage, owner, item.uid)
        self._take_damage(
            enemy, damage, source=item.uid, action="damage", attacker=owner
        )

        # The attack landed, so this item's on-hit triggers may now run.
        # Emitted after the damage, so the log reads in the
        # order it happened and an on-hit effect can see the result.
        self.event_manager.emit(
            Event(
                EventType.ON_HIT,
                owner,
                enemy,
                EventData(damage=damage, attacker_item_id=item.uid),
            )
        )

    def _mitigate_attack(
        self, target: Player, damage: int, attacker: Player, item_id: str
    ) -> int:
        """Everything standing between an attack and the quota (Section 7.3).

        Belongs to the attack, not to the damage. A shield rolls because it
        was attacked, and Block is spent stopping a blow. Neither has anything
        to say about damage that comes from inside, which is why poison does
        not come through here.
        """
        # Shields roll first, and only against an attack that hit -- this is
        # reached after the accuracy check, so a miss never gets here.
        block_results = self.event_manager.emit(
            Event(
                EventType.ON_ATTACKED,
                attacker,
                target,
                EventData(pending_damage=damage, attacker_item_id=item_id),
            )
        )
        prevented = sum(
            result["blocked"]
            for result in block_results
            if result and result.get("blocked")
        )
        damage = max(0, damage - prevented)

        # Then Block, the resource, which is spent a point at a time.
        held = target.buffs.get("block", 0)
        if held > 0 and damage > 0:
            absorbed = min(damage, held)
            damage -= absorbed
            target.buffs["block"] = held - absorbed
            if target.buffs["block"] <= 0:
                del target.buffs["block"]

            self.actions.append(
                BattleAction(
                    timestamp=self._time_ms(),
                    source="system",  # Block is the player's, not an item's
                    action="block",
                    target=None,
                    damage=absorbed,
                    player=target.id,
                    details={"type": "buff_block"},
                )
            )

        return damage

    def _take_damage(
        self,
        target: Player,
        damage: int,
        source: str,
        action: str,
        attacker: Optional[Player] = None,
        details: Optional[Dict] = None,
    ):
        """Put damage on a player and tell everyone watching.

        The one place a quota goes down. Whatever the damage was mitigated by
        on its way here, it lands the same and is seen the same, so an item
        that reacts to its owner being hurt reacts to all of it.
        """
        old_quota = target.quota
        target.quota -= damage

        self.actions.append(
            BattleAction(
                timestamp=self._time_ms(),
                source=source,
                action=action,
                target=None,  # Target is implicit from the player field
                damage=damage,
                player=target.id,
                details=details,
            )
        )

        self.event_manager.emit(
            Event(
                EventType.DAMAGE_TAKEN,
                attacker,
                target,
                EventData(
                    damage=damage,
                    item_id=source,
                    previous_health=old_quota,
                    current_health=target.quota,
                ),
            )
        )

    def _apply_over_time(self, player: Player):
        """Pay out whatever a player's own state owes right now."""
        for effect in OVER_TIME:
            if player.period_due(effect.name, effect.period, self.current_time):
                effect.pay(player, self)

    def _consume_item(self, item: BattleItem, owner: Player):
        """Consume an item (remove it from battle)"""
        if item.uid in self.consumed_items:
            return  # Already consumed

        # Mark as consumed
        self.consumed_items.add(item.uid)

        # Log the consumption
        self.actions.append(
            BattleAction(
                timestamp=self._time_ms(),
                source=item.uid,
                action="consume",
                target=None,
                damage=None,
                player=owner.id,
                details=None,
            )
        )

        # Emit event so adjacency can be recalculated
        self.event_manager.emit(
            Event(EventType.ITEM_CONSUMED, owner, None, EventData(item_id=item.uid))
        )

        # Cancel any scheduled timers for this item
        for trigger_index in range(len(item.spec.triggers)):
            trigger_uid = f"{item.uid}_trigger_{trigger_index}"
            self.event_manager.cancel_timer(trigger_uid)

    def _validate_placement_with_containers(
        self, items: List[BattleItem], containers: Optional[List[Container]] = None
    ) -> bool:
        """
        Validate that items are properly placed:
        1. Servers cannot overlap each other
        2. Regular items MUST be placed on server-provided squares
        3. Regular items cannot overlap each other
        """
        validator = PlacementValidator()

        # First, place all containers (servers)
        if containers:
            for container in containers:
                if not validator.add_container(container):
                    return False  # Container overlaps or out of bounds

        # Track squares occupied by regular items
        item_occupied = set()

        # Now validate regular items
        for item in items:
            # Get all squares this item occupies
            item_squares = item.get_occupied_squares()

            for x, y in item_squares:
                # Check that this square is provided by a container
                if (x, y) not in validator.available_squares:
                    return False  # Not on a server!

                # Check for overlap with other items
                if (x, y) in item_occupied:
                    return False  # Overlapping with another item

                item_occupied.add((x, y))

        return True
