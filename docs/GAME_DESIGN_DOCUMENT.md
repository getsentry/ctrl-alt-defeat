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
- **Throttling**: When CPU hits 0, items skip activations

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

### 2.1 Problems/Bugs (Weapons)
Attack items that damage the opponent's health directly.

#### Examples:
- **Null Pointer Exception**
  - Damage: 4-8
  - Cooldown: 2.5s
  - Stamina: 3
  - Accuracy: 85%
  - Special: 20% chance to "crash" (instant 15 damage) on crit

- **Memory Leak**
  - Damage: 2-4
  - Cooldown: 3s
  - Stamina: 2
  - Accuracy: 95%
  - Special: Damage increases by +1 each activation (stacks)

- **Race Condition**
  - Damage: 6-10
  - Cooldown: 2s
  - Stamina: 4
  - Accuracy: 70%
  - Special: Double strike if faster than opponent

- **SQL Injection**
  - Damage: 8-12
  - Cooldown: 4s
  - Stamina: 5
  - Accuracy: 80%
  - Special: Bypasses 50% of blocks/shields

### 2.2 Sentry Products (Defensive Items)
Items that protect, heal, or provide defensive buffs.

#### Examples:
- **Error Monitoring**
  - Effect: +5 Block at battle start
  - Cooldown: Passive
  - Special: Adjacent problems gain +10% accuracy

- **Session Replay**
  - Effect: Reflects 30% of damage taken
  - Cooldown: When damaged
  - Stamina: 0
  - Special: Records last 3 attacks, can "replay" them

- **Performance Monitoring**
  - Effect: +20% speed buff to all items
  - Cooldown: 10s
  - Stamina: 2
  - Special: Reduces cooldowns by 0.5s when adjacent to problems

- **Alerting System**
  - Effect: Heals 5 HP
  - Cooldown: 8s
  - Stamina: 3
  - Trigger: When health < 30%

### 2.3 Infrastructure (Support Items)
Items that provide stamina, modify other items, or provide utility.

#### Examples:
- **Load Balancer**
  - Effect: +5 max stamina
  - Special: Distributes stamina cost across adjacent items

- **Redis Cache**
  - Effect: +3 stamina regeneration
  - Special: First activation of adjacent items is free each battle

- **Database**
  - Effect: +8 max stamina
  - Special: Stores "damage stacks" for adjacent problems

- **CDN**
  - Effect: All items activate 15% faster
  - Special: Adjacent items gain "First Strike" (activate at 0s)

## 3. Buffs & Debuffs

### 3.1 Buffs
- **Optimized** (Heat): Items trigger 2% faster per stack
- **Cached**: Next activation costs no stamina
- **Monitored** (Empower): +1 damage per stack
- **Load Balanced**: Damage distributed across multiple hits
- **Encrypted** (Shield): Blocks next X damage

### 3.2 Debuffs  
- **Throttled** (Cold): Items trigger 2% slower per stack
- **Memory Leaked** (Poison): 1 damage every 2 seconds
- **Rate Limited** (Blind): -5% accuracy per stack
- **Crashed** (Stun): Cannot activate for X seconds
- **Corrupted**: Next healing effect damages instead

## 4. Item Placement & Adjacency

### 4.1 Grid System
- **Main Server Room**: 7x9 grid (63 slots) - your data center floor
- **Server Racks** (Items that provide storage):
  - **Mini Rack**: 2x2 item, provides 3x4 internal storage (Cost: 8g)
  - **Standard Rack**: 2x3 item, provides 4x5 internal storage (Cost: 15g)
  - **Enterprise Rack**: 3x3 item, provides 5x6 internal storage (Cost: 25g)
- **Item Shapes**: Various sizes (1x1, 2x1, 2x2, 1x3, etc.)
- **Rotation**: Items can be rotated before placement

### 4.2 Adjacency Rules
- Items touching orthogonally are "adjacent" (within same space)
- Diagonal touching doesn't count
- Some items have "directional" effects (e.g., points at specific side)
- Items inside a rack can be adjacent to each other
- Items inside a rack are NOT adjacent to items outside (rack walls block adjacency)

### 4.3 Synergy Examples
- **Bug Swarm**: 3+ problems adjacent = all gain +20% damage
- **Full Stack**: Problem + Defense + Infrastructure touching = all activate 30% faster
- **Monitoring Suite**: 3+ Sentry products = +10 HP at battle start
- **Chaos Engineering**: Alternating problems/defenses = both gain +15% effectiveness

## 5. Economy & Progression

### 5.1 Gold System
- **Starting Gold**: 10
- **Gold Per Round** (fixed amounts):
  - Rounds 1-3: 12g
  - Rounds 4-6: 14g
  - Rounds 7-9: 16g
  - Rounds 10-12: 18g
  - Rounds 13+: 20g
- **No win/loss bonus** - gold is fixed per round
- **Gold Generation Items**: Some items (like "Bitcoin Miner") generate extra gold
- **Selling Items**: 50% of purchase price (rounded down)

### 5.2 Shop System
- **Slots**: 5 items per refresh
- **Reroll Cost**: 2 gold
- **Item Costs**:
  - Common: 3g
  - Uncommon: 5g
  - Rare: 8g
  - Epic: 12g
  - Legendary: 20g

### 5.3 Item Tiers
- **Tier 1**: Base stats
- **Tier 2**: 1.5x stats (combine 3 tier 1)
- **Tier 3**: 2.2x stats (combine 3 tier 2)

## 6. Battle Phases

### 6.1 Preparation Phase (60 seconds)
1. View shop
2. Buy/sell items
3. Arrange inventory
4. View opponent's last build (in ranked)

### 6.2 Battle Phase (60 seconds max)
1. Items activate based on cooldowns
2. Stamina management occurs automatically
3. Battle ends when a player reaches 0 HP or time expires
4. If time expires, player with more HP wins

## 7. Special Mechanics

### 7.1 Fatigue
- After 30 seconds, all damage increases by 1 per 5 seconds
- Prevents stalemates

### 7.2 Critical Hits
- Base 5% chance
- Deals 2x damage
- Some items modify crit chance/damage

### 7.3 Block vs Damage
- Block reduces incoming damage 1:1
- Some damage types bypass block
- Block doesn't carry over between attacks

## 8. Classes/Heroes (Future)

### 8.1 The Debugger
- **Passive**: Problems have +10% crit chance
- **Special**: Can "breakpoint" an enemy item for 3s once per battle

### 8.2 The SRE
- **Passive**: +2 stamina regeneration
- **Special**: Infrastructure items cost 1 less gold

### 8.3 The Security Engineer
- **Passive**: Defensive items activate 20% faster
- **Special**: Start battle with 5 block

## 9. Leaderboards & Progression

### 9.1 Leaderboard System
- **Global Leaderboard**: All players
- **Weekly Leaderboard**: Resets each week
- **Friends Leaderboard**: Compare with friends
- **Metrics Displayed**:
  - Total Wins
  - Win Rate (%)
  - Current Win Streak
  - Best Win Streak
  - Average Round Reached
  - Total Games Played

### 9.2 Time-Based Leaderboards
- **Daily**: Top performers each day
- **Weekly**: Best stats for the week
- **Monthly**: Long-term consistency
- **All-Time**: Career totals

### 9.3 Player Progression
- Account level (based on games played)
- Item unlock system (start with basic set)
- Achievement system
- No ranked mode initially - pure leaderboard competition

## 10. Technical Implementation Notes

### 10.1 Client-Server Architecture
- **Client**: Manages inventory locally, sends final state
- **Server**: Validates builds, simulates battles, returns replay
- **Battle Simulation**: Deterministic, tick-based (10 ticks/second)

### 10.2 Battle Replay Format
```json
{
  "events": [
    {
      "timestamp": 0.0,
      "type": "item_activate",
      "item_id": "null_pointer_1",
      "target": "player_2",
      "damage": 6,
      "stamina_cost": 3
    }
  ],
  "winner": "player_1",
  "final_healths": {
    "player_1": 15,
    "player_2": 0
  }
}
```

## 11. Monetization (Optional for Hackweek)
- **Battle Pass**: Cosmetic server rack skins
- **Item Skins**: Visual variants of items
- **Emotes**: For battle victories
- **No Pay-to-Win**: All gameplay items earnable through play

## 12. Sentry-Specific Theming

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