# Sentry Autobattler - Game Design Document
## Based on Backpack Battles Mechanics

## Core Concept
A Sentry-themed autobattler where players manage a "server rack" (backpack) filled with items that represent bugs/problems (weapons), monitoring tools (defensive items), and infrastructure (support items). Players have health, not items. Items activate on timers to attack the enemy player or provide buffs.

## 1. Battle System

### 1.1 Player Quota (Health)
- **Starting Quota**: 25 requests
- **Quota Scaling**: Increases each round
  - Round 1-3: 25 quota
  - Round 4-6: 35 quota
  - Round 7-9: 50 quota
  - Round 10-12: 75 quota
  - Round 13-15: 100 quota
  - Round 16+: 150 quota
- **Win Condition**: Exhaust opponent's quota (reduce to 0)
- **Loss Penalty**: Lose 10-20 quota based on remaining enemy quota

### 1.2 CPU Cycles (Stamina)
- **Starting CPU**: 10 cycles/second
- **CPU Pool**: Increases with infrastructure items
- **CPU Usage**: Each item activation consumes CPU cycles
- **CPU Regeneration**: 2 cycles/second base rate
- **Throttling**: When CPU hits 0, items skip activations but maintain schedule

### 1.3 Item Activation Flow
```
1. Check cooldown timer
2. Check stamina availability
3. Roll accuracy check (if applicable)
4. Apply effects (damage/buff/debuff)
5. Trigger on-hit effects (if successful)
6. Reset cooldown
```

## 2. Item Categories & Mechanics

Items can have multiple effects with different triggers. Each effect specifies when it activates (trigger) and what it does (effect type).

### 2.1 Effect Triggers
- **ON_TIMER**: Activates on a cooldown timer (like weapons)
- **ON_BATTLE_START**: Activates once at battle start
- **ON_ATTACKED**: Activates when owner is attacked (% chance)
- **ON_DAMAGED**: Activates when the owner takes damage
- **ON_DEAL_DAMAGE**: Activates when this item deals damage
- **ON_HIT**: Activates when an attack successfully hits
- **ON_KILL**: Activates when getting a kill
- **ON_HEALTH_THRESHOLD**: Activates at specific health %
- **PASSIVE**: Always active (e.g., stat modifiers)

### 2.2 Effect Types
- **DAMAGE**: Deal damage to enemies
- **HEAL**: Restore health
- **BLOCK**: Prevent damage
- **BUFF/DEBUFF**: Apply status effects
- **MODIFY_STAT**: Change max CPU, CPU regen, etc.
- **REFLECT**: Return damage to attacker
- **CONSUME**: Remove item from battle after use
- **STEAL**: Take buffs from enemy
- **CLEANSE**: Remove debuffs

### 2.3 Weapons (Problems/Bugs)
Attack items that deal damage. All weapons:
- Activate on timer when CPU is available
- Can have "on hit" effects that trigger after successful attacks
- Can gain damage/effects from buffs

#### Weapon Types:
- **Melee**: Standard attacks, often with on-hit effects
- **Ranged**: May have different accuracy/crit mechanics

#### Examples:
- **Null Pointer Exception** (Common Melee)
  - Damage: 4-8
  - Cooldown: 2.5s
  - CPU Cost: 3
  - Accuracy: 85%
  - On Crit: 20% chance to "crash" for 15 damage

- **Memory Leak** (Uncommon Melee)
  - Damage: 2-4 (increases by +1 each activation)
  - Cooldown: 3.0s
  - CPU Cost: 2
  - Accuracy: 95%
  - On Hit: Apply "memory_leaked" debuff

- **SQL Injection** (Rare Ranged)
  - Damage: 8-12
  - Cooldown: 4.0s
  - CPU Cost: 5
  - Special: Bypasses 50% of shields

### 2.4 Shields (Monitoring/Defense)
Defensive items that have a chance to block attacks. Shield mechanics:
- **30% base chance** to activate when attacked
- Block a specific amount of damage (7-14 typically)
- Can remove attacker's CPU (0.3-0.7)
- May have additional effects when blocking

#### Examples:
- **Error Monitoring** (Common Shield)
  - 30% chance to activate on attack
  - Blocks 8 damage
  - Removes 0.5 CPU from attacker
  - Passive: Adjacent problems gain +10% accuracy

- **Session Replay** (Uncommon Shield)
  - 30% chance to activate on attack
  - Blocks 10 damage
  - Reflects 30% of blocked damage back
  - Records last 3 attacks for replay

- **Firewall** (Rare Shield)
  - 30% chance to activate on attack
  - Blocks 12 damage
  - On Block: Apply "throttled" debuff to attacker
  - Passive: +2 block to adjacent shields

### 2.5 Accessories (Infrastructure/Support)
Items providing passive bonuses, periodic effects, or conditional triggers.

#### Trigger Types:
- Start of battle effects
- Periodic triggers (every X seconds)
- Conditional triggers (health %, resource thresholds)
- Shop interaction effects

#### Examples:
- **Load Balancer** (Uncommon Accessory)
  - Passive: +5 max CPU
  - Every 5s: Redistribute 1 CPU to lowest item

- **Redis Cache** (Common Accessory)
  - Passive: +3 CPU regeneration
  - Start of battle: First activation of adjacent items is free

- **CDN** (Rare Accessory)
  - All items activate 15% faster
  - Adjacent items gain "First Strike" at battle start

- **Kubernetes Cluster** (Legendary Accessory)
  - Every 3s: Spawn a temporary "Pod" that attacks for 3 damage
  - Passive: +2 max pods per infrastructure item

### 2.6 Consumables (Potions/One-Time Items)
Items that are consumed after triggering once.

#### Trigger Conditions:
- Health drops below X%
- Battle start
- After X seconds
- On specific event

#### Examples:
- **Health Potion** (Common)
  - Trigger: Health < 50%
  - Effect: Heal 15-20 HP
  - Consumed after use

- **Emergency Repair** (Rare)
  - Trigger: Health < 20%
  - Effect: Heal 30 HP + 10 Block
  - Consumed after use

- **CPU Booster** (Uncommon)
  - Trigger: Battle start
  - Effect: +10 max CPU for battle
  - Consumed after use

- **Bug Bomb** (Epic)
  - Trigger: After 5 seconds
  - Effect: Deal 25 damage, spawn 3 mini-bugs
  - Consumed after use

### 2.7 Food Items (Resource Regeneration)
Items that provide healing and resource regeneration. Food mechanics:
- **Trigger 10% faster for each adjacent food of DIFFERENT type**
- Each unique food type adjacent gives the speed bonus
- Multi-square foods have more adjacency slots for bonuses
- Provide healing, CPU regen, or buff generation

#### Examples:
- **Coffee** (Common Food) - 1x1
  - Every 5s: Regenerate 2 CPU
  - Adjacent items gain +5% speed

- **Energy Drink** (Uncommon Food) - 1x2
  - Every 4s: Regenerate 3 CPU + 1 Heat
  - If overheated: Cleanse 2 debuffs
  - Larger size = more adjacency slots

- **Server Room Pizza** (Rare Food) - 2x2
  - Every 6s: Heal 4 HP to all units
  - Takes 4 grid squares (more adjacency!)
  
- **Debug Donuts** (Epic Food) - L-shaped (3 squares)
  - Every 4s: Heal 3 HP + 1 CPU
  - Irregular shape for strategic placement

### 2.8 Pets (Automated Helpers)
Special items that provide periodic effects or triggered abilities.

#### Pet Mechanics:
- Activate every X seconds or on specific conditions
- Speed increased by 15% per adjacent pet
- Can have evolution/growth mechanics

#### Examples:
- **Debugger Duck** (Rare Pet)
  - Every 3s: Remove 1 bug from enemy
  - Gains +1 damage per bug removed

- **Sentry Dog** (Epic Pet)
  - Every 4s: Bark for 3 damage + 1 Intimidate
  - On enemy kill: Howl (all pets attack immediately)

- **AI Assistant** (Legendary Pet)
  - Every 2s: Copy effect of random adjacent item
  - Learns patterns: -0.1s cooldown per activation

## 3. Buffs & Debuffs

### 3.1 Buffs
- **Optimized** (Heat): Items trigger 2% faster per stack
- **Cached**: Next activation costs no stamina
- **Monitored** (Empower): +1 damage per stack
- **Load Balanced**: Damage distributed across multiple hits
- **Encrypted** (Shield): Blocks next X damage
- **Overclocked**: +50% speed but costs double CPU
- **Regenerating**: Heal 1 HP per second per stack

### 3.2 Debuffs  
- **Throttled** (Cold): Items trigger 2% slower per stack
- **Memory Leaked** (Poison): 1 damage every 2 seconds
- **Rate Limited** (Blind): -5% accuracy per stack
- **Crashed** (Stun): Cannot activate for X seconds
- **Corrupted**: Next healing effect damages instead
- **Lagged**: Delays next X activations by 0.5s
- **Vulnerable**: Take +2 damage from all sources

## 4. Item Placement & Adjacency

### 4.1 Grid System
- **Main Server Room**: 7x9 grid (63 slots)
- **Server Racks** (Storage containers):
  - **Mini Rack**: 2x2 item, provides 3x4 internal storage
  - **Standard Rack**: 2x3 item, provides 4x5 internal storage
  - **Enterprise Rack**: 3x3 item, provides 5x6 internal storage
- **Item Shapes**: 
  - Simple: 1x1, 2x1, 1x2, 2x2, 3x1, 1x3
  - Complex: L-shapes, T-shapes, irregular patterns
  - Large items can take 3-6+ squares
- **Rotation**: Items can be rotated before placement

### 4.2 Multi-Square Items
- **Items can occupy multiple grid squares** (e.g., a "Server Blade" might be 1x3)
- **Each square of the item counts for adjacency** - a 1x3 item has more adjacent slots than a 1x1
- **Example**: A 2x2 item has 12 adjacent slots (all orthogonally adjacent squares)
- **Strategic placement**: Larger items provide more adjacency opportunities

#### Multi-Square Item Examples:
- **Server Blade** (1x3): Long horizontal server component
- **Rack Mount** (2x2): Square equipment taking 4 spaces
- **L-Shaped Cable** (3 squares in L): Fits around corners
- **Database Cluster** (2x3): Large 6-square infrastructure
- **Pizza Slice** (3 squares triangular): Irregular food shape
- **Monitor Array** (T-shape, 4 squares): Central monitoring system

### 4.3 Adjacency Rules
- **Orthogonal only**: Items touching horizontally or vertically are "adjacent"
- **No diagonals**: Diagonal touching doesn't count
- **Multi-square adjacency**: ALL squares of an item check for adjacency
- **Container rules**:
  - Items inside a rack can be adjacent to each other
  - Items inside a rack are NOT adjacent to items outside

### 4.4 Synergies
- **Bug Swarm**: 3+ problems adjacent = all gain +20% damage
  - Multi-square problems count as one item but have more adjacency
- **Shield Wall**: 3+ shields adjacent = +10% block chance each
  - Large shields provide better coverage
- **Full Stack**: Problem + Defense + Infrastructure = 30% faster
  - Each category only needs one item regardless of size
- **Monitoring Suite**: 3+ Sentry products = +10 HP at battle start
- **Food Court**: Different food types adjacent = +10% trigger speed per unique type
  - Large foods can touch more different food types
- **Pet Paradise**: Pets gain +1 effect power per adjacent pet
  - Multi-square pets still count as one pet

## 5. Economy & Progression

### 5.1 Gold System
- **Starting Gold**: 10
- **Gold Per Round**:
  - Rounds 1-3: 12g
  - Rounds 4-6: 14g
  - Rounds 7-9: 16g
  - Rounds 10-12: 18g
  - Rounds 13+: 20g
- **Selling Items**: 50% of purchase price

### 5.2 Shop System
- **Slots**: 5 items per refresh
- **Reroll Cost**: 2 gold
- **Item Costs**:
  - Common: 3-4g
  - Uncommon: 5-7g
  - Rare: 8-11g
  - Epic: 12-16g
  - Legendary: 18-25g
  - Godly: 30+g

### 5.3 Recipe System (Item Combining)
- **How it Works**: Place recipe items adjacent to each other in your server rack
- **Combination Timing**: Items combine automatically during the next shop phase
- **Orange Glow**: Adjacent combinable items show an orange glowing connection
- **Lock Items**: Right-click items to prevent them from combining
- **Two Ways to Get Combined Items**:
  - Combine the required items (cheaper but requires finding components)
  - Buy directly from shop if lucky (more expensive but immediate)
- **Catalyst Items**: Some recipes use a catalyst that remains after combination

### 5.4 Example Sentry-Themed Recipes

#### Weapon Recipes
- **Stack Overflow** (Epic): Memory Leak + Buffer Overflow
- **Kernel Panic** (Legendary): Null Pointer + Race Condition + Segfault
- **DDoS Attack** (Epic): Flood Attack + Bot Swarm
- **Zero Day Exploit** (Godly): SQL Injection + XSS Attack + Buffer Overflow

#### Shield Recipes  
- **Full Stack Monitoring** (Rare): Error Monitoring + Performance Monitoring
- **Enterprise Firewall** (Epic): Firewall + Load Balancer
- **Chaos Engineering Shield** (Legendary): Error Shield + Crash Report + Debug Mode

#### Infrastructure Recipes
- **Kubernetes Cluster** (Epic): Docker Container + Load Balancer + Auto-Scaler
- **CDN Network** (Rare): Cache Server + Edge Node
- **Observability Platform** (Legendary): Logging + Metrics + Tracing
- **CI/CD Pipeline** (Epic): Test Suite + Deploy Script + Version Control

#### Pet Recipes (Sentry Mascots)
- **Debug Duck Pro** (Rare): Debug Duck + Stack Trace
- **Error Hound Elite** (Epic): Sentry Dog + Alert System
- **Chaos Monkey** (Legendary): Test Monkey + Random Failure Generator
- **AI Assistant Plus** (Godly): AI Assistant + Machine Learning Model

#### Potion/Consumable Recipes
- **Emergency Hotfix** (Rare): Quick Fix + Deploy Script
- **Full Recovery** (Epic): Health Check + Backup System
- **CPU Overclock** (Rare): CPU Booster + Energy Drink
- **Memory Cleaner** (Epic): Garbage Collector + Memory Optimizer

#### Special Combinations
- **Sentry Suite** (Godly): Error Monitoring + Performance Monitoring + Session Replay + Profiling
- **DevOps Toolkit** (Legendary): CI/CD Pipeline + Kubernetes Cluster + Monitoring
- **Bug Apocalypse** (Godly): 4 different bug types combined
- **Perfect Infrastructure** (Godly): Load Balancer + CDN + Kubernetes + Firewall

## 6. Battle Phases

### 6.1 Preparation Phase (60 seconds)
1. View shop
2. Buy/sell items
3. Arrange inventory
4. View opponent's last build

### 6.2 Battle Phase (60 seconds max)
1. Items activate based on triggers
2. CPU management occurs automatically
3. Battle ends when a player reaches 0 HP
4. If time expires, player with more HP wins

## 7. Special Mechanics

### 7.1 Fatigue
- After 30 seconds, all damage increases by 1 per 5 seconds
- Prevents stalemates

### 7.2 Critical Hits
- Base 5% chance
- Deals 2x damage
- Can trigger special effects

### 7.3 Shield Blocking
- Shields have 30% base chance to block
- Block prevents X damage (varies by shield)
- Can trigger counter-effects

### 7.4 Item Consumption
- Some items are consumed after use
- Consumed items are removed from battle
- Adjacency bonuses update when items are consumed

## 8. Classes/Heroes (Future)

### 8.1 The Debugger
- **Passive**: Problems have +10% crit chance
- **Special**: Can "breakpoint" an enemy item for 3s

### 8.2 The SRE
- **Passive**: +2 stamina regeneration
- **Special**: Infrastructure items cost 1 less gold

### 8.3 The Security Engineer
- **Passive**: Shields have +10% block chance
- **Special**: Start battle with 5 block

### 8.4 The Data Scientist
- **Passive**: Pets activate 20% faster
- **Special**: Can "analyze" shop for better items

## 9. Technical Implementation

### 9.1 Architecture
- **Client**: Godot 4 web export
- **Server**: Python FastAPI
- **Battle Simulation**: Server-side, deterministic

### 9.2 Event System
- Event-driven architecture for triggers
- Priority queue for timer-based events
- Immediate evaluation for reactive triggers

### 9.3 Item Effect System
- Separation of triggers (WHEN) and effects (WHAT)
- Items can have multiple triggers
- Each trigger can have multiple effects
- Proper type safety with no Any types

## 10. Sentry-Specific Theming

### Visual Style
- Server racks instead of backpacks
- Items look like server components, monitoring dashboards
- Problems appear as error alerts, red warning lights
- Infrastructure as actual server hardware

### Sound Design
- Error sounds for problems activating
- Success chimes for monitoring catches
- Server fan sounds for infrastructure
- Alert sounds for critical events

### Easter Eggs
- Rare "Sentry Logo" item that provides team-wide benefits
- "Getsentry" mode where all items are Sentry products
- Special animations for Sentry employee accounts