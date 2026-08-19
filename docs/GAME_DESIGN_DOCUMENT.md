# Sentry Autobattler - Game Design Document
## Based on Backpack Battles Mechanics

## Core Concept
A Sentry-themed autobattler where players manage a "server rack" (backpack) filled with items that represent bugs/problems (weapons), monitoring tools (defensive items), and infrastructure (support items). Players have health, not items. Items activate on timers to attack the enemy player or provide buffs.

## 1. Battle System

### 1.1 Player Health (Infrastructure Integrity)
- **Health Progression by Round**:
  - Round 1: 25
  - Round 2: 35
  - Round 3: 45
  - Round 4: 55
  - Round 5: 70
  - Round 6: 85
  - Round 7: 100
  - Round 8: 115
  - Round 9: 130
  - Round 10: 150
  - Round 11: 170
  - Round 12: 190
  - Round 13: 210
  - Round 14: 230
  - Round 15: 260
  - Round 16: 290
  - Round 17: 320
  - Round 18: 350
- **Win Condition**: Reduce opponent's health to 0
- **Loss Penalty**: Lose health based on remaining enemy health

### 1.2 CPU Cycles (Stamina)
- **CPU Pool**: 3 cycles, raised by any item carrying a passive `max_cpu`
  effect — infrastructure most of all, but a container or a module may do it
  too, and each such item counts once
- **CPU Regeneration**: 1 cycle/second base rate, raised the same way by a
  passive `cpu_regen` effect. Modules and protocols are where most of it lives
- **CPU Usage**: Each item activation consumes CPU cycles, in fractions
- **Throttling**: When CPU hits 0, items skip activations but maintain schedule

**Regeneration is Backpack Battles': 1 per second.** Three things agree on it.
Its wiki says the Mecha Bat's 1.5 stamina every 3 seconds is "about 50% of the
player's default stamina allowance", which puts the allowance at 1 per second,
and calls the Bloodthorne expensive at "a full 0.9 stamina/second". Players
report the in-game indicator saying 1 per second. And the percentage buffs only
work out against a base of 1: Just Stats gives "+10% base stamina regeneration"
and is reported as taking it to 1.1, a Chipped Topaz's +8% to 1.08.

**The pool of 3 is ours.** Backpack Battles never publishes it — its wiki's
Game Mechanics page still lists "Stamina, passive gain, out of stamina" as
unwritten. A pool of 3 fits the shape of the game, where an epic bag's whole
effect is "+1 maximum stamina" and a legendary potion restores 2 when you run
dry, but it is a choice rather than a copy. Change it freely.

A typical weapon of ours drains 0.5 a second, so two run level with
regeneration and a third has to wait. That is the intended pressure.

### 1.3 Item Activation Flow
```
1. The cooldown comes due
2. Check CPU. Too little, and the item skips this activation
3. Roll accuracy, if the item attacks
4. Apply the effects whose timing matches the result
5. Reset the cooldown
```

**A miss does not cancel the activation.** The item still pays its CPU, and the
activation still counts. Only the effects that need a hit are lost. This is
Backpack Battles' rule: its wiki says "Weapons will still provide activations
regardless if their attack hits or misses", and separately that "'On attack'
effects will always trigger when a weapon successfully attempts to attack (AKA
when not out of stamina)."

So an effect has to say *when* it wants to happen, and there are three answers.
Each one is a trigger of its own, not a flag on the effect, because that is how
Backpack Battles writes them: an item's text starts "On hit:" or "On attack:".

| Trigger | Fires when | Backpack Battles examples |
|---|---|---|
| `on_attack` | The item attacks, whether it hits or misses | Critwood Staff, Magic Staff |
| `on_hit` | The attack lands | Hungry Blade, Hammer, socketed gems |
| `on_miss` | The attack fails | Broom, Fancy Fencing Rapier |

A shield's `on_attacked` trigger sits on the hit side. A shield never blocks an
attack that missed, because there was nothing to block.

Of the three, only `on_hit` is built. `on_attack` and `on_miss` are named in
the item catalogue but the loader drops them, so nothing uses them yet.

## 2. Item Categories & Mechanics

Items can have multiple effects with different triggers. Each effect specifies when it activates (trigger) and what it does (effect type).

### 2.1 Effect Triggers
- **ON_TIMER**: Activates on a cooldown timer (like weapons)
- **ON_BATTLE_START**: Activates once at battle start
- **ON_ATTACKED**: Activates when the owner is attacked, and only when that
  attack hits (% chance)
- **ON_HEALTH_THRESHOLD**: Activates once, when health falls past a fraction
  of its maximum
- **ON_ATTACK**: Activates whenever the item attacks, hit or miss
- **ON_HIT**: Activates when the item's own attack lands
- **ON_MISS**: Activates when the item's own attack fails
- **ON_DEAL_DAMAGE**: Activates when this item deals damage
- **ON_KILL**: Activates when getting a kill
- **PASSIVE**: Always active (e.g., stat modifiers)

ON_ATTACK, ON_HIT and ON_MISS belong to the item that attacked. One item's
miss never stops another item's on-hit effect. See Section 1.3 for the order.

**There is no "when I take damage" trigger**, and that is deliberate rather
than an omission. Backpack Battles has none: an item that reacts to its owner
being hurt is either a shield, which needs an attack to roll against, or a
health threshold, which needs only a number. Nothing in the game reacts to an
instance of damage as such.

#### Health thresholds

Written "Health drops below 50%". Three rules, all of them from the source
game's own wording:

- **It fires once a battle.** Being below the line is not the trigger;
  *falling past it* is. Whether it should re-arm after healing back above the
  line is an open question: "(once)" appears on 13 threshold clauses in the
  source game and on no other kind of trigger, which suggests the default
  re-arms and "(once)" pins it to one. Every item we have consumes itself, so
  the distinction cannot yet be observed. See BACKLOG.md.
- **It is checked wherever health falls**, not when an attack lands. Poison,
  fatigue and an attack all move the same number, and a threshold cannot care
  which did it. Checking it at the one place health goes down means a new
  source of damage cannot forget to announce itself.
- **The subject can be either player.** "Health drops below 50%" watches the
  owner; "Opponent drops below 30%" watches the other side. Only the owner is
  built.

### 2.2 Effect Types
- **DAMAGE**: Deal damage to enemies
- **HEAL**: Restore health
- **BLOCK**: Gain Block, the resource that absorbs damage a point at a time
- **PREVENT_DAMAGE**: Stop one attack outright, keeping nothing
- **CPU_DRAIN**: Take CPU off somebody, never below 0
- **BUFF/DEBUFF**: Apply status effects
- **MODIFY_STAT**: Change max CPU, CPU regen, etc.
- **REFLECT**: Return damage to attacker
- **CONSUME**: Remove item from battle after use
- **CLEANSE**: Remove statuses from somebody. Taking a debuff off yourself and
  taking a buff off your opponent are the same effect with a different target,
  so STEAL is not separate.

### 2.3 Weapons (Problems/Bugs)
Attack items that deal damage. All weapons:
- Activate on timer when CPU is available
- Can have "on hit" effects that trigger after successful attacks
- Can gain damage/effects from buffs

#### Weapon Types:
- **Melee**: Standard attacks, often with on-hit effects
- **Ranged**: May have different accuracy/crit mechanics

#### Examples:

Every number here comes from the Backpack Battles item it is based on,
including CPU cost, which that game calls stamina. CPU costs are fractional
as a result.

- **Null blade** (Common Melee, from Wooden Sword)
  - Damage: 1-3
  - Cooldown: 1.4s
  - CPU Cost: 1.0
  - Accuracy: 90%
  - Sockets: 1
  - On Crit: 20% chance to "crash" for 15 damage

- **Stack Smasher** (Rare Melee, from Axe)
  - Damage: 3-6 (increases by +1 each activation)
  - Cooldown: 2.0s
  - CPU Cost: 1.4
  - Accuracy: 85%
  - Sockets: 2
  - On Hit: Apply "memory_leaked" debuff

- **SQL Injector** (Unique Ranged, from Villain Sword)
  - Damage: 2-4
  - Cooldown: 1.3s
  - CPU Cost: 0.3
  - Accuracy: 90%
  - Sockets: 1
  - Special: Bypasses 50% of shields

- **Virus Injector** (Legendary Ranged, from Belladonna's Shade)
  - Damage: 4-11
  - Cooldown: 1.7s
  - CPU Cost: 0.7
  - Accuracy: 85%
  - Sockets: 1
  - On Hit: 70% chance to inflict 2 "memory_leaked"

  This is the worked example of an on-hit effect. The 70% roll happens only
  after the accuracy roll passes, so a miss never poisons. Belladonna's Shade
  inflicts a random debuff on the same roll, which is not built yet.

### 2.4 Shields (Monitoring/Defense)

A shield rolls once when its owner is attacked, and everything behind that
roll happens together.

```
On attacked: 30% chance to
  - prevent 9 damage
  - remove 0.3 CPU from the attacker
  - and gain 1 Spikes
```

**One roll, not one per consequence.** Backpack Battles writes its shields as
a single chance in front of a list — "30% chance to prevent 9 damage, remove
0.3 stamina from opponent, and gain 1 Spikes (up to 5)" — so a shield can
never prevent the damage and miss the CPU. The chance therefore belongs to the
`on_attacked` trigger, and each consequence is an effect of its own behind it.
This is the same shape as `on_hit` in Section 1.3, for the same reason.

- **30% chance.** Every shield in Backpack Battles rolls 30%, without
  exception, so this is the figure and not a base to modify.
- **Prevent** 7 to 15 damage, across the shields we have.
- **Remove** 0.3 to 0.9 CPU from the attacker. Every shield in the source game
  does this, and the attacker never goes below 0.

A shield only rolls against an attack that **hit**. There is nothing to block
otherwise, and Backpack Battles says so: "'On attacked' effects ... will only
occur when a weapon hits."

Every number comes from the source item and every one is stated. None has a
default, because a shield whose numbers never arrived would otherwise load as
a working item.

**Preventing is not Blocking.** Two mechanics reduce damage and they are not
the same. *Block* is a resource: it stacks, absorbs one damage per stack, and
is spent doing it ("Start of battle: Gain 45 Block"). *Preventing* stops one
attack outright and is spent on nothing. Backpack Battles keeps them apart,
and so do we: `BlockEffect` against `PreventDamageEffect`.

#### Examples:
- **Error Monitoring** (Common Shield, from Wooden Buckler)
  - 30% chance to activate on attack
  - Blocks 7 damage
  - Removes 0.3 CPU from attacker
  - Passive: problems in its star zone gain +10% accuracy

- **Session Replay** (Uncommon Shield)
  - 30% chance to activate on attack
  - Blocks 10 damage
  - Reflects 30% of blocked damage back
  - Records last 3 attacks for replay

- **Firewall** (Common Shield, from Wooden Buckler)
  - 30% chance to activate on attack
  - Blocks 7 damage
  - Removes 0.3 CPU from attacker

  It shares its source with Error Monitoring, so the two are identical.
  One of them has the wrong item recorded as its source.

- **Rate Limiter** (Rare Shield, from Hero Shield)
  - 30% chance to activate on attack
  - Blocks 15 damage
  - Removes 0.4 CPU from attacker
  - Hero Shield also buffs weapons at the start of the battle, which we
    do not have.

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
  - Start of battle: the first activation of items in its star zone is free

- **CDN** (Rare Accessory)
  - All items activate 15% faster
  - Items in its star zone gain "First Strike" at battle start

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
- **Trigger 10% faster for each food of a DIFFERENT type in its zone**
- Each unique type counts once, however many of it there are
- A larger food projects a larger zone, so it reaches more types
- Provide healing, CPU regen, or buff generation

#### Examples:
- **Coffee** (Common Food) - 1x1
  - Every 5s: Regenerate 2 CPU
  - Items in its star zone gain +5% speed

- **Energy Drink** (Uncommon Food) - 1x2
  - Every 4s: Regenerate 3 CPU + 1 Heat
  - If overheated: Cleanse 2 debuffs
  - Larger size = a larger zone

- **Server Room Pizza** (Rare Food) - 2x2
  - Every 6s: Heal 4 HP to all units
  - Takes 4 grid squares, so its zone reaches further

- **Debug Donuts** (Epic Food) - L-shaped (3 squares)
  - Every 4s: Heal 3 HP + 1 CPU
  - Irregular shape for strategic placement

### 2.8 Pets (Automated Helpers)
Special items that provide periodic effects or triggered abilities.

#### Pet Mechanics:
- Activate every X seconds or on specific conditions
- Speed increased by 15% per pet in its zone
- Can have evolution/growth mechanics

#### Examples:
- **Debugger Duck** (Rare Pet)
  - Every 3s: Remove 1 bug from enemy
  - Gains +1 damage per bug removed

- **Sentry Dog** (Epic Pet)
  - Every 4s: Bark for 3 damage + 1 Intimidate
  - On enemy kill: Howl (all pets attack immediately)

- **AI Assistant** (Legendary Pet)
  - Every 2s: Copy the effect of a random item in its zone
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

**Every debuff stacks, and none of them wears off.** A debuff lasts to the end
of the battle unless something says otherwise, so the only way out is a
cleanse. This is Backpack Battles' rule, word for word from its wiki:
"Debuffs are given until end of the combat unless otherwise specified. Every
debuff is stackable."

A `duration` on a debuff in the item catalogue therefore means nothing today.
Treat a missing duration and a duration of -1 as the same thing.

**There are three debuffs, and that is all of them.** Backpack Battles has
three, so we have three:

- **Throttled** (Cold): Items trigger 2% slower per stack
- **Memory Leaked** (Poison): 1 damage every 2 seconds, per stack
- **Rate Limited** (Blind): -5% accuracy per stack

An item that applies a *random* debuff draws from these three. There is no
fourth to draw.

#### Cleansing

The only way out of a debuff. One effect, on two axes: what to take, and who
to take it from.

| | Debuffs | Buffs |
|---|---|---|
| **Self** | "cleanse 4 Poison" | — |
| **Opponent** | — | "remove 2 random buffs" |

It reads as "Cleanse" when you take a debuff off yourself and "Remove" when
you take a buff off your opponent. Underneath it is one thing: take N of a
status off a target.

The two blank corners are what the items we have imported happen to use, not
a rule. Every combination works, and one of them is nearly in use already:
Corrupted Armor cleanses debuffs off itself and inflicts them on the
opponent.

**Named or not, in one field.** An item says what it takes: `debuff` or
`buff` for any of that kind, or the name of one. A name carries its own kind,
since no buff shares a name with a debuff, so nothing is stated twice and the
contradiction of naming a debuff while asking for a buff cannot be written.

A name the game does not have is refused rather than assumed to be the other
kind. Otherwise a misspelling would load cleanly and remove nothing for the
rest of the game.

**How an unnamed one picks: uniformly across the kinds present, never weighted
by how many of each.** One stack at a time, looking again after each. So
against 10 Memory Leaked and 1 Throttled, cleansing 2 is a coin flip on the
first, and if the Throttled goes then the second can only be Memory Leaked.

This is Backpack Battles' rule, which its wiki gives once: "if they have 50
Mana, 10 Luck and 1 Spike, and you try to remove a buff, it's just as likely
to remove 1 Spike as 1 Mana."

It has a consequence worth knowing before tuning anything. Cleansing one is
unreliable and cleansing many is close to certain, because the small kinds run
out early and every later pick lands on what is left. Against 10 Memory Leaked
and 1 Throttled, cleansing 1 wastes itself half the time while cleansing 4
always clears at least 3 Memory Leaked. The gap is far wider than four
times.

**Memory Leaked hits in whole periods, not smoothly.** Every two seconds it
deals damage equal to the stack count, and between those moments it deals
nothing. Two stacks means 2 damage at 2s, 2 more at 4s, and so on, not a
trickle of 0.1 per tick. The period is measured from the start of the battle,
so a stack applied at 3.5s pays out at 4s with all the others.

The count is read at the moment it pays. Stacks added between two payments
count in full at the next one, and no stack is spent by paying out.

## 4. Item Placement & Auras

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
- **Each square of the item is reached separately** - an aura landing on any one
  square of an item reaches that item
- **Strategic placement**: a larger item is easier to reach with an aura, and
  reaches further with its own

#### Multi-Square Item Examples:
- **Server Blade** (1x3): Long horizontal server component
- **Rack Mount** (2x2): Square equipment taking 4 spaces
- **L-Shaped Cable** (3 squares in L): Fits around corners
- **Database Cluster** (2x3): Large 6-square infrastructure
- **Pizza Slice** (3 squares triangular): Irregular food shape
- **Monitor Array** (T-shape, 4 squares): Central monitoring system

### 4.3 Auras

An item does not care what it is next to. It cares whose aura reaches it.

- **An aura is a set of squares** an item projects around itself, drawn on the
  item's map: `*` for the star zone, `+` for the diamond zone. The two are
  separate zones, and an item may have either, both or neither.
- **An aura reaches an item** when any square of the aura lands on any square
  that item covers. Touching is not required and distance is not a rule: the map
  says exactly which squares are reached. 118 items in the catalogue project an
  aura and 41 of those reach past the four squares around them, so "next to" is
  not a useful approximation of it.
- **An aura never reaches the item projecting it.** A square of the zone landing
  on the item's own footprint is dropped.
- **Turning an item turns its aura**, except where the map marks a square `^`.
  That square projects straight up in world space however the item is turned, and
  the projection is dropped only where it lands on the item's own squares.

**Undecided:** whether an aura stops at the edge of a container, or reaches into
any square regardless. Nothing depends on the answer yet.

`server/grid_system.py` reads all of this from the map. It returns the covered
squares today and throws the zones away, so nothing acts on an aura yet.

### 4.4 What an aura does

An aura carries the effect of the item projecting it. "Star Weapons gain 3
damage" means every weapon the star zone reaches gains 3 damage; "Chance-based
effects of the star items are 15% more likely" means the same shape of thing.
The wording on each item says what it grants and to what kind of item.

There are no synergies that count how many of a category sit beside each other.
An earlier version of this document described six, of which two were built
against orthogonal adjacency. Neither the six nor adjacency exist in the game
this one is based on, so both are gone.

## 5. Economy & Progression

### 5.1 Gold System
Gold handed out on entering the shop, from Backpack Battles. Round 1's figure
is also what a new game starts with. Round 8 is the spike, where the subclass
unlocks.

| Round | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Gold | 13 | 13 | 15 | 10 | 11 | 11 | 12 | 22 | 13 | 18 | 14 | 14 | 15 | 15 | 16 | 16 | 16 | 16 |

Eighteen rounds is the whole game, so there is no nineteenth figure.

- **Selling Items**: half the purchase price, rounded up

### 5.2 Shop System
- **Slots**: 5 items per refresh
- **Reroll Cost**: 1 gold for the first four rolls of a round, 2 gold after
- **Sales**: each item offered has a 10% chance of being half price, rounded
  up. The roll comes from the shop's seed, so the same seed always offers the
  same items at the same prices. An item bought on sale sells for what it cost.
- **Item Costs**: each item's own cost, taken from the Backpack Battles item
  it is based on. There is no price band per rarity: a Unique can cost 5 gold
  and a Rare 16.

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
- **Stack Overflow** (Epic): Stack Smasher + Buffer Overflow
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

### 6.3 Round Result

A round ends the moment one side reaches 0 HP, and its result is spent on the
run rather than on the next battle.

- **A win** banks one win. Bank **10** and the run is won.
- **A loss** spends one try. The run starts with **5** tries, and ends when the
  last one is spent.
- Neither carries over into the next battle: both players start the next round
  on that round's full health.

The result is shown over the finished battle, not on a screen of its own, so
the player reads the run against the battle that changed it. It shows:

1. Which way the round went.
2. **Wins**: one trophy per win the run is played for, lit up to the wins
   banked.
3. **Tries**: one heart per try the run starts with, lit down to the tries
   left.

The counters open on the totals from *before* the round and then move the one
icon the round changed, so the player sees the trophy light up or the heart go
out. The player clicks to move on to the post-battle screen.

## 7. Special Mechanics

### 7.1 Fatigue
- After 30 seconds, all damage increases by 1 per 5 seconds
- Prevents stalemates

### 7.2 Critical Hits
- Base 5% chance
- Deals 2x damage
- Can trigger special effects

### 7.3 Shield Blocking
See Section 2.4. One 30% roll per attack, and every consequence behind that
roll lands together or not at all. Nothing blocks damage that comes from a
player's own stacks — poison has no attack to block.

### 7.4 Item Consumption
- Some items are consumed after use
- Consumed items are removed from battle

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
