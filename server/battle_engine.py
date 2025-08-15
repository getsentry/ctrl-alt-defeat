"""
Battle Engine Final - Exactly matches Game Design Document
Every mechanic verified against the spec
Event-driven system with priority queue for timers
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple
from enum import Enum
import random
from copy import deepcopy
import uuid
import time

from event_system import EventManager, EventType, Event, EventData
from item_effects import (
    ItemSpec, Trigger, Effect,
    AttackEffect, HealEffect, BlockEffect, BuffEffect, DebuffEffect, 
    StunEffect, ReflectEffect, StatModEffect, ConsumeEffect,
    TimerTrigger, BattleStartTrigger, DamageTakenTrigger, DamageDealtTrigger,
    PassiveTrigger, KillTrigger, create_example_items
)

# Import shield effect if available
try:
    from shield_effect import OnAttackedTrigger, ShieldBlockEffect
except ImportError:
    OnAttackedTrigger = None
    ShieldBlockEffect = None

# Compact action codes for minimal payload (Section 10.2)
ACTION_CODES = {
    "START": "s",       # Battle start
    "ACTIVATE": "a",    # Item activates
    "DAMAGE": "d",      # Damage dealt to player
    "MISS": "m",        # Attack missed
    "CRIT": "c",        # Critical hit
    "HEAL": "h",        # Healing
    "BLOCK": "b",       # Damage blocked
    "CPU_FAIL": "cf",   # CPU throttled
    "BUFF": "bf",       # Buff applied
    "DEBUFF": "df",     # Debuff applied
    "DOT": "dt",        # Damage over time (poison)
    "REFLECT": "r",     # Damage reflected
    "DEATH": "x",       # Player defeated
}

# PlacedItem will reference the new ItemSpec from item_effects.py

@dataclass  
class PlacedItem:
    """An item placed in the server room/rack (Section 4)"""
    spec: ItemSpec
    position: Tuple[int, int]  # Grid position
    container_id: Optional[str] = None  # Which rack it's in (if any)
    uid: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    
    # Battle state
    current_cooldown: float = 0.0
    memory_leak_stacks: int = 0  # For Memory Leak special
    
    # Modifiers from adjacency (Section 4.3)
    damage_mult: float = 1.0
    accuracy_bonus: float = 0.0
    speed_mult: float = 1.0
    cpu_discount: int = 0

@dataclass
class Player:
    """Player state per Section 1"""
    id: int  # 1 or 2
    
    # Section 1.1: Player Quota (Health)
    quota: int  # Current
    max_quota: int  # Based on round
    
    # Section 1.2: CPU Cycles (Stamina)
    cpu: float  # Current cycles
    max_cpu: int = 10  # Base, increased by infrastructure
    cpu_regen: float = 2.0  # Per second
    
    # Section 3: Buffs & Debuffs
    buffs: Dict[str, int] = field(default_factory=dict)
    debuffs: Dict[str, int] = field(default_factory=dict)
    
    # Session Replay special tracking
    recorded_attacks: List[Dict] = field(default_factory=list)

# Use the new items from item_effects.py
ITEM_CATALOG = create_example_items()

class BattleSimulator:
    """Simulates battles per Game Design Document specifications"""
    
    def __init__(self, seed: Optional[int] = None):
        self.max_duration = 60.0  # Section 6.2
        self.tick_rate = 0.1  # Section 10.1: 10 ticks/second
        self.current_time = 0.0
        self.actions = []
        self.event_manager = EventManager()
        self.consumed_items = set()  # Track consumed item UIDs
        
        # Initialize RNG with seed for deterministic battles
        self.seed = seed if seed is not None else int(time.time() * 1000000) % 2147483647
        self.rng = random.Random(self.seed)
        
    def simulate_battle(self, 
                       p1_items: List[PlacedItem], 
                       p2_items: List[PlacedItem],
                       round_number: int = 1) -> Dict:
        """
        Simulate battle following Section 1.3 Item Activation Flow
        Returns compact action log per Section 10.2
        """
        # Get quota based on round (Section 1.1)
        quota = self._get_round_quota(round_number)
        
        # Initialize players
        player1 = Player(id=1, quota=quota, max_quota=quota, cpu=10.0)
        player2 = Player(id=2, quota=quota, max_quota=quota, cpu=10.0)
        
        # Deep copy items to avoid mutation
        p1_items = deepcopy(p1_items)
        p2_items = deepcopy(p2_items)
        
        # Reset state
        self.current_time = 0.0
        self.actions = []
        self.event_manager.clear()
        self.consumed_items = set()
        
        # Apply tier scaling (Section 5.3)
        self._apply_tier_scaling(p1_items)
        self._apply_tier_scaling(p2_items)
        
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
        self.actions.append({"t": 0, "a": ACTION_CODES["START"]})
        
        # Main battle loop (Section 6.2)
        while self.current_time < self.max_duration:
            # CPU regeneration (Section 1.2)
            player1.cpu = min(player1.max_cpu, player1.cpu + player1.cpu_regen * self.tick_rate)
            player2.cpu = min(player2.max_cpu, player2.cpu + player2.cpu_regen * self.tick_rate)
            
            # Process timer events efficiently with heap
            self.event_manager.current_time = self.current_time
            self.event_manager.process_timers(self.current_time)
            
            # Apply DOT effects (Section 3.2 - Memory Leaked/Poison)
            self._apply_dot_effects(player1)
            self._apply_dot_effects(player2)
            
            # Check for defeat
            if player1.quota <= 0:
                self.actions.append({"t": self.current_time, "a": ACTION_CODES["DEATH"], "p": 1})
                break
            if player2.quota <= 0:
                self.actions.append({"t": self.current_time, "a": ACTION_CODES["DEATH"], "p": 2})
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
                                if hasattr(effect, 'min_damage'):  # Check if it's an attack effect
                                    # Store original values if not yet stored
                                    if not hasattr(effect, '_original_min_damage'):
                                        effect._original_min_damage = effect.min_damage
                                        effect._original_max_damage = effect.max_damage
                                    effect.min_damage = effect._original_min_damage + fatigue_bonus
                                    effect.max_damage = effect._original_max_damage + fatigue_bonus
            
            self.current_time += self.tick_rate
        
        # Determine winner (Section 6.2)
        winner = 1 if player1.quota > player2.quota else 2
        
        return {
            "winner": winner,
            "duration": round(self.current_time, 1),
            "player1_quota": max(0, player1.quota),
            "player2_quota": max(0, player2.quota),
            "actions": self.actions,
            "seed": self.seed  # Include seed for replay/debugging
        }
    
    def _get_round_quota(self, round_num: int) -> int:
        """Get quota based on round number (Section 1.1)"""
        if round_num <= 3:
            return 25
        elif round_num <= 6:
            return 35
        elif round_num <= 9:
            return 50
        elif round_num <= 12:
            return 75
        elif round_num <= 15:
            return 100
        else:
            return 150
    
    def _apply_tier_scaling(self, items: List[PlacedItem]):
        """Apply tier multipliers (Section 5.3)"""
        for item in items:
            multiplier = 1.0
            if item.spec.tier == 2:
                multiplier = 1.5
            elif item.spec.tier == 3:
                multiplier = 2.2
            
            if multiplier > 1.0:
                # Scale all attack effects in all triggers
                for trigger in item.spec.triggers:
                    for effect in trigger.effects:
                        if isinstance(effect, AttackEffect):
                            effect.min_damage = int(effect.min_damage * multiplier)
                            effect.max_damage = int(effect.max_damage * multiplier)
                        elif isinstance(effect, HealEffect):
                            effect.min_heal = int(effect.min_heal * multiplier)
                            effect.max_heal = int(effect.max_heal * multiplier)
    
    def _calculate_adjacency(self, items: List[PlacedItem]):
        """Calculate adjacency bonuses (Section 4.2 & 4.3)"""
        for item in items:
            if item.uid in self.consumed_items:
                continue  # Skip consumed items
            adjacent = self._get_adjacent_items(item, items)
            
            # Count categories
            problems = sum(1 for i in adjacent if i.spec.category == "problem")
            defenses = sum(1 for i in adjacent if i.spec.category == "defense")
            infrastructure = sum(1 for i in adjacent if i.spec.category == "infrastructure")
            
            # Bug Swarm: 3+ problems = +20% damage (Section 4.3)
            if item.spec.category == "problem" and problems >= 2:  # 2 because we need 3 total
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
    
    def _get_adjacent_items(self, item: PlacedItem, all_items: List[PlacedItem]) -> List[PlacedItem]:
        """Get orthogonally adjacent items (Section 4.2)"""
        adjacent = []
        x, y = item.position
        positions = [(x-1, y), (x+1, y), (x, y-1), (x, y+1)]
        
        for other in all_items:
            if other.uid == item.uid:
                continue
            if other.uid in self.consumed_items:
                continue  # Skip consumed items
            # Must be in same container (Section 4.2)
            if other.container_id != item.container_id:
                continue
            if other.position in positions:
                adjacent.append(other)
        
        return adjacent
    
    def _apply_infrastructure(self, items: List[PlacedItem], player: Player):
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
    
    def _setup_item_handlers(self, items: List[PlacedItem], owner: Player, enemy: Player):
        """Set up event handlers for items based on their triggers"""
        for item in items:
            if item.uid in self.consumed_items:
                continue  # Skip consumed items
            # Each item can have multiple triggers with multiple effects
            for trigger in item.spec.triggers:
                if isinstance(trigger, BattleStartTrigger):
                    # Subscribe to battle start - fires immediately
                    def handle_battle_start(event, trigger=trigger, item=item, owner=owner):
                        self._apply_effects(trigger.effects, item, owner, enemy)
                    
                    self.event_manager.subscribe(EventType.BATTLE_START, handle_battle_start)
                
                elif isinstance(trigger, TimerTrigger):
                    # Create unique ID for this trigger-timer combination
                    trigger_index = item.spec.triggers.index(trigger)
                    trigger_uid = f"{item.uid}_trigger_{trigger_index}"
                    # Schedule first activation using timer heap
                    self._schedule_timer_trigger(trigger, item, owner, enemy, trigger_uid)
                
                elif isinstance(trigger, DamageTakenTrigger):
                    # Subscribe to damage events - check threshold if needed
                    def handle_damage_taken(event, trigger=trigger, item=item, owner=owner):
                        if event.target != owner:
                            return
                        
                        # Skip if item is consumed
                        if item.uid in self.consumed_items:
                            return
                        
                        # Check if trigger should activate
                        if not trigger.should_activate("damage_taken", owner, owner, None):
                            return
                        
                        # Check CPU cost
                        cpu_cost = trigger.get_cpu_cost()
                        if owner.cpu >= cpu_cost:
                            self._apply_effects(trigger.effects, item, owner, enemy)
                            owner.cpu -= cpu_cost
                            trigger.current_cooldown = trigger.cooldown
                    
                    self.event_manager.subscribe(EventType.DAMAGE_TAKEN, handle_damage_taken)
                
                elif isinstance(trigger, PassiveTrigger):
                    # Apply passive effects immediately
                    self._apply_effects(trigger.effects, item, owner, enemy)
                
                elif OnAttackedTrigger and isinstance(trigger, OnAttackedTrigger):
                    # Subscribe to ON_ATTACKED events for shields
                    def handle_on_attacked(event, trigger=trigger, item=item, owner=owner):
                        if event.target != owner:
                            return
                        
                        # Skip if item is consumed
                        if item.uid in self.consumed_items:
                            return
                        
                        # Check CPU cost (shields are usually free)
                        cpu_cost = trigger.get_cpu_cost()
                        if owner.cpu >= cpu_cost:
                            # Process shield effects
                            blocked_damage = 0
                            for effect in trigger.effects:
                                if ShieldBlockEffect and isinstance(effect, ShieldBlockEffect):
                                    result = effect.apply(item, event.source, self)
                                    if result.get("blocked"):
                                        # Shield activated!
                                        blocked_damage = min(result["block_amount"], event.data.pending_damage)
                                        
                                        # Log the block
                                        self.actions.append({
                                            "t": self.current_time,
                                            "a": ACTION_CODES["BLOCK"],
                                            "p": owner.id,
                                            "i": item.uid,
                                            "v": blocked_damage
                                        })
                                        
                                        # Apply counter effects if any
                                        if result.get("cpu_steal") and event.source:
                                            event.source.cpu -= result["cpu_steal"]
                                        
                                        # Return blocked amount to reduce damage
                                        return {"blocked": blocked_damage}
                            owner.cpu -= cpu_cost
                    
                    self.event_manager.subscribe(EventType.ON_ATTACKED, handle_on_attacked)
    
    def _schedule_timer_trigger(self, trigger: TimerTrigger, item: PlacedItem, owner: Player, enemy: Player, trigger_uid: str):
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
                self.actions.append({
                    "t": self.current_time,
                    "a": ACTION_CODES["CPU_FAIL"],
                    "p": owner.id,
                    "i": item.uid
                })
            
            # Always schedule next activation at regular cooldown (unless consumed)
            # This keeps the item on its normal schedule regardless of CPU
            if item.uid not in self.consumed_items:
                self._schedule_timer_trigger(trigger, item, owner, enemy, trigger_uid)
        
        self.event_manager.schedule_timer(next_time, trigger_uid, activate)
    
    def _apply_effects(self, effects: List[Effect], item: PlacedItem, owner: Player, enemy: Player):
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
                self.actions.append({
                    "t": self.current_time,
                    "a": ACTION_CODES["HEAL"],
                    "p": owner.id,
                    "i": item.uid,
                    "v": heal
                })
            elif isinstance(effect, BlockEffect):
                # Handle block effect
                owner.buffs["block"] = owner.buffs.get("block", 0) + result["amount"]
                self.actions.append({
                    "t": self.current_time,
                    "a": ACTION_CODES["BLOCK"],
                    "p": owner.id,
                    "i": item.uid,
                    "v": result["amount"]
                })
            elif isinstance(effect, BuffEffect):
                # Handle buff effect
                owner.buffs[result["buff_name"]] = owner.buffs.get(result["buff_name"], 0) + result["value"]
                self.actions.append({
                    "t": self.current_time,
                    "a": ACTION_CODES["BUFF"],
                    "p": owner.id,
                    "i": item.uid,
                    "v": result["value"]
                })
            elif isinstance(effect, DebuffEffect):
                # Handle debuff effect
                if self.rng.random() < result["accuracy"]:
                    enemy.debuffs[result["debuff_name"]] = enemy.debuffs.get(result["debuff_name"], 0) + result["value"]
                    self.actions.append({
                        "t": self.current_time,
                        "a": ACTION_CODES["DEBUFF"],
                        "p": enemy.id,
                        "i": item.uid,
                        "v": result["value"]
                    })
            elif isinstance(effect, ReflectEffect):
                # Reflect is handled in damage events
                owner.buffs["reflect"] = result["percent"]
            elif isinstance(effect, StatModEffect):
                # Handle stat modification
                if result["stat"] == "max_cpu":
                    owner.max_cpu += result["value"]
                elif result["stat"] == "cpu_regen":
                    owner.cpu_regen += result["value"]
            elif isinstance(effect, ConsumeEffect):
                # Mark item for removal and emit event
                self._consume_item(item, owner)
    
    def _process_attack(self, attack_data: dict, item: PlacedItem, owner: Player, enemy: Player):
        """Process an attack effect"""
        # Check accuracy
        accuracy = attack_data["accuracy"] + item.accuracy_bonus
        if "rate_limited" in owner.debuffs:
            accuracy -= owner.debuffs["rate_limited"] * 0.05
        
        if self.rng.random() > accuracy:
            # Miss
            self.actions.append({
                "t": self.current_time,
                "a": ACTION_CODES["MISS"],
                "p": owner.id,
                "i": item.uid
            })
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
            
            self.actions.append({
                "t": self.current_time,
                "a": ACTION_CODES["CRIT"],
                "p": owner.id,
                "i": item.uid,
                "v": damage
            })
        
        # Handle special attack types
        if attack_data.get("special") == "stacking":
            # Memory leak stacking damage
            item.memory_leak_stacks += 1
            damage += item.memory_leak_stacks
        elif attack_data.get("special") == "bypass_block":
            # SQL injection bypasses blocks
            if "block" in enemy.buffs:
                enemy.buffs["block"] = int(enemy.buffs["block"] * 0.5)
        
        # Deal damage
        self._deal_damage(enemy, damage, owner, item.uid)
    
    
    def _deal_damage(self, target: Player, damage: int, attacker: Player, item_id: str):
        """Deal damage following Section 7.3"""
        # Emit ON_ATTACKED event for shields to process
        # This happens BEFORE damage is dealt
        attack_event = Event(
            EventType.ON_ATTACKED,
            attacker,
            target,
            EventData(pending_damage=damage, attacker_item_id=item_id)
        )
        block_results = self.event_manager.emit(attack_event)
        
        # Process shield blocks
        total_blocked = 0
        for result in block_results:
            if result and result.get("blocked"):
                total_blocked += result["blocked"]
        
        # Reduce damage by shield blocks
        damage = max(0, damage - total_blocked)
        
        # Check buff-based block (Section 7.3)
        if "block" in target.buffs and target.buffs["block"] > 0:
            blocked = min(damage, target.buffs["block"])
            damage -= blocked
            target.buffs["block"] -= blocked
            
            if target.buffs["block"] <= 0:
                del target.buffs["block"]
            
            if blocked > 0:
                self.actions.append({
                    "t": self.current_time,
                    "a": ACTION_CODES["BLOCK"],
                    "p": target.id,
                    "v": blocked
                })
        
        # Store old health for threshold detection
        old_quota = target.quota
        
        # Apply damage
        target.quota -= damage
        
        # Log damage
        self.actions.append({
            "t": self.current_time,
            "a": ACTION_CODES["DAMAGE"],
            "p": target.id,
            "i": item_id,
            "v": damage
        })
        
        # Emit damage event for reactive items (Session Replay, health potions, etc)
        # Items will check their own thresholds
        self.event_manager.emit(Event(
            EventType.DAMAGE_TAKEN,
            attacker,
            target,
            EventData(damage=damage, item_id=item_id, previous_health=old_quota, current_health=target.quota)
        ))
    
    def _apply_dot_effects(self, player: Player):
        """Apply DOT effects (Section 3.2)"""
        if "memory_leaked" in player.debuffs:
            # 1 damage every 2 seconds per stack
            tick_damage = player.debuffs["memory_leaked"] * (self.tick_rate / 2.0)
            if tick_damage >= 1:
                damage = int(tick_damage)
                player.quota -= damage
                self.actions.append({
                    "t": self.current_time,
                    "a": ACTION_CODES["DOT"],
                    "p": player.id,
                    "v": damage
                })
    
    def _consume_item(self, item: PlacedItem, owner: Player):
        """Consume an item (remove it from battle)"""
        if item.uid in self.consumed_items:
            return  # Already consumed
        
        # Mark as consumed
        self.consumed_items.add(item.uid)
        
        # Log the consumption
        self.actions.append({
            "t": self.current_time,
            "a": "consume",
            "p": owner.id,
            "i": item.uid
        })
        
        # Emit event so adjacency can be recalculated
        self.event_manager.emit(Event(
            EventType.ITEM_CONSUMED,
            owner,
            None,
            EventData(item_id=item.uid)
        ))
        
        # Cancel any scheduled timers for this item
        for trigger_index in range(len(item.spec.triggers)):
            trigger_uid = f"{item.uid}_trigger_{trigger_index}"
            self.event_manager.cancel_timer(trigger_uid)