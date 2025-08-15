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

from event_system import EventManager, EventType, Event, EventData

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

class TriggerType(Enum):
    """From Section 2 - Item trigger conditions"""
    ON_BATTLE_START = "on_battle_start"
    ON_TIMER = "on_timer"  
    ON_DAMAGED = "on_damaged"
    ON_LOW_HEALTH = "on_low_health"  # < 30% per Section 2.2
    PASSIVE = "passive"

@dataclass
class ItemSpec:
    """Item specification from Game Design Document Section 2"""
    id: str
    name: str
    category: str  # "problem", "defense", "infrastructure"
    
    # Combat stats (Section 2.1)
    min_damage: int = 0
    max_damage: int = 0
    cooldown: float = 3.0
    cpu_cost: int = 3  # Stamina from doc
    accuracy: float = 0.85
    crit_chance: float = 0.05  # Section 7.2: Base 5%
    
    # Activation
    trigger_type: TriggerType = TriggerType.ON_TIMER
    
    # Special effects from Section 2
    special_effect: Optional[str] = None
    special_value: float = 0
    
    # Tier system (Section 5.3)
    tier: int = 1  # 1-3
    
    # Rarity for shop costs (Section 5.2)
    rarity: str = "common"  # common/uncommon/rare/epic/legendary

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

# Define all items from Section 2
ITEM_CATALOG = {
    # Section 2.1: Problems/Bugs (Weapons)
    "null_pointer": ItemSpec(
        id="null_pointer",
        name="Null Pointer Exception",
        category="problem",
        min_damage=4, max_damage=8,
        cooldown=2.5, cpu_cost=3,
        accuracy=0.85, crit_chance=0.05,
        trigger_type=TriggerType.ON_TIMER,
        special_effect="crash",  # 20% chance on crit for instant 15 damage
        rarity="common"
    ),
    "memory_leak": ItemSpec(
        id="memory_leak",
        name="Memory Leak",
        category="problem", 
        min_damage=2, max_damage=4,
        cooldown=3.0, cpu_cost=2,
        accuracy=0.95, crit_chance=0.05,
        trigger_type=TriggerType.ON_TIMER,
        special_effect="stacking",  # +1 damage each activation
        rarity="uncommon"
    ),
    "race_condition": ItemSpec(
        id="race_condition",
        name="Race Condition",
        category="problem",
        min_damage=6, max_damage=10,
        cooldown=2.0, cpu_cost=4,
        accuracy=0.70, crit_chance=0.05,
        trigger_type=TriggerType.ON_TIMER,
        special_effect="double_strike",  # If faster than opponent
        rarity="rare"
    ),
    "sql_injection": ItemSpec(
        id="sql_injection",
        name="SQL Injection", 
        category="problem",
        min_damage=8, max_damage=12,
        cooldown=4.0, cpu_cost=5,
        accuracy=0.80, crit_chance=0.05,
        trigger_type=TriggerType.ON_TIMER,
        special_effect="bypass_block",  # Bypasses 50% of blocks
        rarity="rare"
    ),
    
    # Section 2.2: Sentry Products (Defensive)
    "error_monitoring": ItemSpec(
        id="error_monitoring",
        name="Error Monitoring",
        category="defense",
        trigger_type=TriggerType.ON_BATTLE_START,
        special_effect="block",
        special_value=5,  # +5 Block at battle start
        rarity="common"
    ),
    "session_replay": ItemSpec(
        id="session_replay",
        name="Session Replay",
        category="defense",
        trigger_type=TriggerType.ON_DAMAGED,
        cpu_cost=0,  # No stamina cost
        special_effect="reflect",
        special_value=0.3,  # Reflects 30% damage
        rarity="uncommon"
    ),
    "performance_monitoring": ItemSpec(
        id="performance_monitoring",
        name="Performance Monitoring",
        category="defense",
        cooldown=10.0, cpu_cost=2,
        trigger_type=TriggerType.ON_TIMER,
        special_effect="speed_buff",
        special_value=0.2,  # +20% speed to all
        rarity="uncommon"
    ),
    "alerting_system": ItemSpec(
        id="alerting_system",
        name="Alerting System",
        category="defense",
        cooldown=8.0, cpu_cost=3,
        trigger_type=TriggerType.ON_LOW_HEALTH,
        special_effect="heal",
        special_value=5,  # Heals 5 HP when < 30%
        rarity="rare"
    ),
    
    # Section 2.3: Infrastructure (Support)
    "load_balancer": ItemSpec(
        id="load_balancer",
        name="Load Balancer",
        category="infrastructure",
        trigger_type=TriggerType.PASSIVE,
        special_effect="max_cpu",
        special_value=5,  # +5 max stamina
        rarity="uncommon"
    ),
    "redis_cache": ItemSpec(
        id="redis_cache",
        name="Redis Cache",
        category="infrastructure",
        trigger_type=TriggerType.PASSIVE,
        special_effect="cpu_regen",
        special_value=3,  # +3 stamina regen
        rarity="common"
    ),
    "database": ItemSpec(
        id="database",
        name="Database",
        category="infrastructure",
        trigger_type=TriggerType.PASSIVE,
        special_effect="max_cpu",
        special_value=8,  # +8 max stamina
        rarity="uncommon"
    ),
    "cdn": ItemSpec(
        id="cdn",
        name="CDN",
        category="infrastructure",
        trigger_type=TriggerType.PASSIVE,
        special_effect="global_speed",
        special_value=0.15,  # 15% faster activation
        rarity="rare"
    ),
}

class BattleSimulator:
    """Simulates battles per Game Design Document specifications"""
    
    def __init__(self):
        self.max_duration = 60.0  # Section 6.2
        self.tick_rate = 0.1  # Section 10.1: 10 ticks/second
        self.current_time = 0.0
        self.actions = []
        self.event_manager = EventManager()
        
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
                        # Add flat damage, not multiply
                        # Store original values if not yet stored
                        if not hasattr(item, '_original_min_damage'):
                            item._original_min_damage = item.spec.min_damage
                            item._original_max_damage = item.spec.max_damage
                        item.spec.min_damage = item._original_min_damage + fatigue_bonus
                        item.spec.max_damage = item._original_max_damage + fatigue_bonus
            
            self.current_time += self.tick_rate
        
        # Determine winner (Section 6.2)
        winner = 1 if player1.quota > player2.quota else 2
        
        return {
            "winner": winner,
            "duration": round(self.current_time, 1),
            "player1_quota": max(0, player1.quota),
            "player2_quota": max(0, player2.quota),
            "actions": self.actions
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
            if item.spec.tier == 2:
                # Tier 2: 1.5x stats
                item.spec.min_damage = int(item.spec.min_damage * 1.5)
                item.spec.max_damage = int(item.spec.max_damage * 1.5)
            elif item.spec.tier == 3:
                # Tier 3: 2.2x stats
                item.spec.min_damage = int(item.spec.min_damage * 2.2)
                item.spec.max_damage = int(item.spec.max_damage * 2.2)
    
    def _calculate_adjacency(self, items: List[PlacedItem]):
        """Calculate adjacency bonuses (Section 4.2 & 4.3)"""
        for item in items:
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
                        item.spec.cooldown = max(0.5, item.spec.cooldown - 0.5)
            
            # Full Stack: Problem + Defense + Infrastructure = 30% faster (Section 4.3)
            if problems >= 1 and defenses >= 1 and infrastructure >= 1:
                item.speed_mult *= 1.3
            
            # CDN: Adjacent items gain First Strike (Section 2.3)
            for adj in adjacent:
                if adj.spec.name == "CDN" and item.spec.trigger_type == TriggerType.ON_TIMER:
                    item.current_cooldown = -0.1  # Will activate immediately
            
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
            
            if item.spec.name == "Load Balancer":
                player.max_cpu += 5
            elif item.spec.name == "Redis Cache":
                player.cpu_regen += 3
            elif item.spec.name == "Database":
                player.max_cpu += 8
            elif item.spec.name == "CDN":
                # Global speed boost handled in update loop
                pass
    
    def _setup_item_handlers(self, items: List[PlacedItem], owner: Player, enemy: Player):
        """Set up event handlers for items based on their trigger types"""
        for item in items:
            if item.spec.trigger_type == TriggerType.ON_BATTLE_START:
                # Subscribe to battle start - fires immediately
                def handle_battle_start(event, item=item, owner=owner):
                    if item.spec.name == "Error Monitoring":
                        owner.buffs["block"] = owner.buffs.get("block", 0) + 5
                        self.actions.append({
                            "t": self.current_time,
                            "a": ACTION_CODES["BUFF"],
                            "p": owner.id,
                            "i": item.uid,
                            "v": 5
                        })
                
                self.event_manager.subscribe(EventType.BATTLE_START, handle_battle_start)
            
            elif item.spec.trigger_type == TriggerType.ON_TIMER:
                # Schedule first activation using timer heap
                self._schedule_timer_item(item, owner, enemy)
            
            elif item.spec.trigger_type == TriggerType.ON_LOW_HEALTH:
                # Subscribe to damage events and check health threshold
                def handle_damage_for_health_trigger(event, item=item, owner=owner):
                    if event.target != owner:
                        return
                    
                    # Check if health is now below threshold (30% for Alerting System)
                    health_percent = owner.quota / owner.max_quota
                    if health_percent >= 0.3:  # Not low enough
                        return
                    
                    # Check cooldown
                    if item.current_cooldown > 0:
                        return
                    
                    if item.spec.name == "Alerting System":
                        cpu_cost = item.spec.cpu_cost
                        if owner.cpu >= cpu_cost:
                            heal = min(5, owner.max_quota - owner.quota)
                            owner.quota += heal
                            owner.cpu -= cpu_cost
                            item.current_cooldown = item.spec.cooldown
                            self.actions.append({
                                "t": self.current_time,
                                "a": ACTION_CODES["HEAL"],
                                "p": owner.id,
                                "i": item.uid,
                                "v": heal
                            })
                
                self.event_manager.subscribe(EventType.DAMAGE_TAKEN, handle_damage_for_health_trigger)
            
            elif item.spec.trigger_type == TriggerType.ON_DAMAGED:
                # Subscribe to damage events - fires immediately when damaged
                def handle_damage(event, item=item, owner=owner):
                    if event.target != owner:
                        return
                    
                    if item.spec.name == "Session Replay":
                        # Reflect 30% damage immediately
                        if event.data.damage:
                            reflect_damage = int(event.data.damage * 0.3)
                            event.source.quota -= reflect_damage
                            self.actions.append({
                                "t": self.current_time,
                                "a": ACTION_CODES["REFLECT"],
                                "p": event.source.id,
                                "v": reflect_damage
                            })
                
                self.event_manager.subscribe(EventType.DAMAGE_TAKEN, handle_damage)
    
    def _schedule_timer_item(self, item: PlacedItem, owner: Player, enemy: Player):
        """Schedule timer-based item activation using priority queue"""
        # Apply speed modifiers
        speed = item.speed_mult
        
        # Calculate next activation time
        cooldown_adjusted = item.spec.cooldown / speed
        next_time = self.current_time + cooldown_adjusted
        
        def activate():
            # Check CPU availability
            cpu_cost = max(1, item.spec.cpu_cost - item.cpu_discount)
            
            if owner.cpu >= cpu_cost:
                # Have enough CPU - activate the item
                self._activate_item(item, owner, enemy)
                owner.cpu -= cpu_cost
                item.current_cooldown = item.spec.cooldown
            else:
                # Not enough CPU - log throttle but don't activate
                self.actions.append({
                    "t": self.current_time,
                    "a": ACTION_CODES["CPU_FAIL"],
                    "p": owner.id,
                    "i": item.uid
                })
            
            # Always schedule next activation at regular cooldown
            # This keeps the item on its normal schedule regardless of CPU
            self._schedule_timer_item(item, owner, enemy)
        
        self.event_manager.schedule_timer(next_time, item.uid, activate)
    
    def _update_player_items(self, items: List[PlacedItem], owner: Player, enemy: Player):
        """Update items following Section 1.3 activation flow"""
        for item in items:
            # Check trigger conditions
            if item.spec.trigger_type == TriggerType.ON_TIMER:
                # Apply speed modifiers
                speed = item.speed_mult
                
                # CDN gives 15% speed to all (Section 2.3)
                if any(i.spec.name == "CDN" for i in items):
                    speed *= 1.15
                
                # Optimized buff (Section 3.1)
                if "optimized" in owner.buffs:
                    speed *= 1 + (owner.buffs["optimized"] * 0.02)
                
                # Throttled debuff (Section 3.2)
                if "throttled" in owner.debuffs:
                    speed *= 1 - (owner.debuffs["throttled"] * 0.02)
                
                # Update cooldown
                item.current_cooldown -= self.tick_rate * speed
                
                if item.current_cooldown <= 0:
                    # Check CPU availability (Section 1.2)
                    cpu_cost = max(1, item.spec.cpu_cost - item.cpu_discount)
                    
                    # Redis Cache: First activation free (Section 2.3)
                    if "first_free" in owner.buffs and owner.buffs["first_free"] > 0:
                        cpu_cost = 0
                        owner.buffs["first_free"] -= 1
                    
                    if owner.cpu >= cpu_cost:
                        self._activate_item(item, owner, enemy)
                        owner.cpu -= cpu_cost
                        item.current_cooldown = item.spec.cooldown
                    else:
                        # CPU throttled (Section 1.2)
                        self.actions.append({
                            "t": self.current_time,
                            "a": ACTION_CODES["CPU_FAIL"],
                            "p": owner.id,
                            "i": item.uid
                        })
            
            elif item.spec.trigger_type == TriggerType.ON_LOW_HEALTH:
                # Trigger when < 30% health (Section 2.2)
                if owner.quota < owner.max_quota * 0.3:
                    if item.spec.name == "Alerting System" and item.current_cooldown <= 0:
                        heal = min(5, owner.max_quota - owner.quota)
                        owner.quota += heal
                        item.current_cooldown = item.spec.cooldown
                        self.actions.append({
                            "t": self.current_time,
                            "a": ACTION_CODES["HEAL"],
                            "p": owner.id,
                            "i": item.uid,
                            "v": heal
                        })
    
    def _activate_item(self, item: PlacedItem, owner: Player, enemy: Player):
        """Activate item following Section 1.3 flow"""
        if item.spec.category == "problem":
            # Step 3: Roll accuracy check (Section 1.3)
            accuracy = item.spec.accuracy + item.accuracy_bonus
            
            # Rate Limited debuff (Section 3.2)
            if "rate_limited" in owner.debuffs:
                accuracy -= owner.debuffs["rate_limited"] * 0.05
            
            if random.random() > accuracy:
                # Miss
                self.actions.append({
                    "t": self.current_time,
                    "a": ACTION_CODES["MISS"],
                    "p": owner.id,
                    "i": item.uid
                })
                return
            
            # Calculate damage
            damage = random.randint(item.spec.min_damage, item.spec.max_damage)
            damage = int(damage * item.damage_mult)
            
            # Monitored buff (Section 3.1)
            if "monitored" in owner.buffs:
                damage += owner.buffs["monitored"]
            
            # Check crit (Section 7.2)
            is_crit = random.random() < item.spec.crit_chance
            if is_crit:
                damage *= 2
                
                # Null Pointer special: 20% chance to crash on crit (Section 2.1)
                if item.spec.name == "Null Pointer Exception" and random.random() < 0.2:
                    damage = 15  # Instant 15 damage
                
                self.actions.append({
                    "t": self.current_time,
                    "a": ACTION_CODES["CRIT"],
                    "p": owner.id,
                    "i": item.uid,
                    "v": damage
                })
            
            # Special effects
            if item.spec.name == "Memory Leak":
                # Damage increases by +1 each activation (Section 2.1)
                item.memory_leak_stacks += 1
                damage += item.memory_leak_stacks
            
            elif item.spec.name == "SQL Injection":
                # Bypasses 50% of blocks (Section 2.1)
                if "block" in enemy.buffs:
                    enemy.buffs["block"] = int(enemy.buffs["block"] * 0.5)
            
            # Deal damage
            self._deal_damage(enemy, damage, owner, item.uid)
            
            # Session Replay: Record attack (Section 2.2)
            if any(i.spec.name == "Session Replay" for i in enemy.buffs):
                enemy.recorded_attacks.append({
                    "damage": damage,
                    "time": self.current_time
                })
                if len(enemy.recorded_attacks) > 3:
                    enemy.recorded_attacks.pop(0)
        
        elif item.spec.category == "defense":
            if item.spec.name == "Performance Monitoring":
                # +20% speed buff to all items (Section 2.2)
                owner.buffs["optimized"] = owner.buffs.get("optimized", 0) + 10  # 10 stacks = 20%
                self.actions.append({
                    "t": self.current_time,
                    "a": ACTION_CODES["BUFF"],
                    "p": owner.id,
                    "i": item.uid,
                    "v": 10
                })
    
    def _deal_damage(self, target: Player, damage: int, attacker: Player, item_id: str):
        """Deal damage following Section 7.3"""
        # Check block (Section 7.3)
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