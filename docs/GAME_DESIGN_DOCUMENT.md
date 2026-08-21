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

**A battle opens on a full pool, and full means the pool the items left.** The
pool is filled after every item and container has had its say, not before: a
Stamina Sack that raises the ceiling to 4 and leaves its owner starting on 3
has given them a second of regeneration rather than a cycle.

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
- **AFTER**: Activates once, a fixed time into the battle. Not a cooldown: it
  is scheduled at the start and never rescheduled
- **ON_HIT**: Activates when the item's own attack lands
- **ON_MISS**: Activates when the item's own attack fails
- **ON_DEAL_DAMAGE**: Activates when this item deals damage
- **ON_KILL**: Activates when getting a kill
- **USE**: Fires as soon as its owner can pay a price in buffs, and pays it.
  "Use 10 Mana: Become invulnerable for 2s". Not on a clock and not asked for
  — it watches, and goes off the moment the price is met. Nearly every one
  ends "(once)", which is a LIMIT behind it rather than part of the trigger
- **COUNTER**: Fires when a running total first crosses a line. "45 Block
  reached", "30 Mana gained", "Opponent reaches 30 Cold". Two kinds of total:
  `held` is what a player has now, so spending puts them back under the line;
  `gained` is everything that ever arrived and only goes up. Crossing is the
  trigger, not being over
- **STATUS_GAINED**: Fires when somebody gains stacks of a buff or debuff.
  Once per arrival, not once per stack: five at a time is one gain
- **ON_STUN**: Fires when its owner stuns the other player — any stun they
  land, not only one this item caused
- **OUT_OF_STAMINA**: Fires when something wanted to run and the pool could not
  pay for it. Demand is the point, not a reading of zero: an item that cannot
  pay does not pay, so the pool never actually reaches nothing
- **ON_MISS**: Fires when an attack goes wide. `whose` says which — this
  item's own swing, or the other player's
- **SHOP_ENTERED**: Fires when the shop phase begins, once a round. Nothing
  here happens in a battle, so the shop reads these rather than the simulator
- **ON_BUY**: Fires once, as the item changes hands
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
- **EFFECT_DAMAGE**: Damage that is not an attack. No accuracy roll, no shield
  answers it, and Block does not absorb it. May carry lifesteal, healing its
  owner that share of what lands. It can still crit, and the healing doubles
  with the damage. Its amount can grow with what its owner holds: "Deal 10
  Effect-damage + 0.5 for each Spikes + 1 for each Empower"
- **MAX_HEALTH**: Raise the ceiling, and heal by the same amount, so gaining
  maximum health gives you the health with it
- **BUFF/DEBUFF**: Apply status effects
- **MODIFY_STAT**: Change max CPU or CPU regeneration, and nothing else. It is
  not the road to maximum health -- that is MAX_HEALTH, because a ceiling gained
  gives you the health with it and this would not. Three items said "Gain 20
  maximum health" through this and none of them did it
- **REFLECT**: Return damage to attacker
- **CONSUME**: Remove item from battle after use
- **CLEANSE**: Remove statuses from somebody. Taking a debuff off yourself and
  taking a buff off your opponent are the same effect with a different target,
  so STEAL is not separate. It can take any of a kind or one named status,
  and a name says which pool it draws from by itself, since no buff and debuff
  share one
- **GAIN_DAMAGE**: Flat damage an item picks up during a battle and keeps.
  "Gain 1 damage", "The Star Weapon gains 10 damage". It joins the weapon's
  roll rather than the total, so a modifier and a critical hit both carry it.
  Kept apart from the item's own range because the source game reads it back:
  "remove 1 damage gained in battle from all opponent Weapons"
- **PER_COUNT**: Everything behind it, once for each item that counts. "Gain 3
  Regeneration for each Star Holy-item". Doing the effects again is what "for
  each" means, so it works with every effect. Counting nothing does nothing
- **COST**: Everything behind it, if the owner can pay. "Use 3 Mana to deal +7
  damage". All of it or none of it, so a clause cannot leave its owner poorer
  for nothing. What the trigger already did stands either way: an attack that
  cannot buy its bonus is still an attack
- **CONDITION**: Everything behind it, if the player is in the state named,
  and `otherwise` if not. "If your health is above 70%, gain 1 Empower.
  Otherwise, heal for 8." One effect holds the whole sentence, so the two
  halves cannot both happen. A condition reads a state and spends nothing,
  which is what tells it from a cost
- **PLAYER_MODIFY**: Change a number on a player rather than on an item.
  "Your healing is amplified by 12%", "Items use +20% stamina", "Both players
  take -25% damage for 7s". None sits on an item and none stacks as a buff
  does, so it is neither MODIFY nor BUFF. Six of them: `damage_taken`,
  `healing`, `healing_taken`, `stamina_use`, `block_gained`,
  `critical_chance`. **Invulnerability is `damage_taken` at -1.0** -- the same
  sentence as "-25% damage" with the number turned up, so it is the same
  number and not a case of its own
- **REFLECT**: Gain charges that turn the next debuffs back on whoever sent
  them. One stack per charge, however many arrive at once. Checked before
  RESIST
- **RESIST**: Gain charges, or a standing chance, that refuse a debuff
  outright. Every chance is added together and checked before a charge is
  spent
- **RANDOM_STATUS**: Grant or inflict a status nobody chose, picked uniformly
  over the kinds there are, one stack at a time and looking again after each
- **LIMIT**: Everything behind it, but only so many times in a battle.
  "(once)", "up to 3 times", "up to 5 per battle". Counted per effect, so two
  items carrying the same clause have an allowance each. Not a modifier's
  `cap`, which limits how much one item has given another
- **GOLD**: Gain gold, which happens between battles and never in one
- **SALE_CHANCE**: Change how likely the shop is to mark an item down. A share
  added to the shop's own chance, standing for as long as the item is held
- **TRIGGER_ITEM**: Make other items do what they do, and leave them standing.
  It runs everything their own triggers would, less the standing ones (a
  passive is on already) and less any CONSUME, which is what "without
  consuming it" means
- **CHOICE**: One of several alternatives, picked at random, and not the
  others. "Randomly gain 14 Block or 2 stamina or 2 Luck." Each alternative is
  a list, because they are not always one effect each. Not RANDOM_STATUS,
  which picks a status out of the seven; this picks between clauses the item
  wrote out
- **DESTROY_BLOCK**: Take Block off somebody without dealing damage. The Block
  is simply gone, and a target with none loses nothing
- **NEXT_ATTACK**: Put damage, or the ability to go past Block, on this item's
  next swing and only the next one. Spent by swinging, so an item that never
  swings again keeps it. Not GAIN_DAMAGE, which an item keeps for the battle
- **STAMINA**: Put CPU straight into a player's pool. Not MODIFY_STAT, which
  changes how big the pool is or how fast it fills; this is the pool going up
  now
- **EXTRA_ATTACK**: Make an item swing again, immediately and for nothing.
  "On stun: Triggers extra attack", "Attacks twice". It is the item's own
  attack run once more, so accuracy, crits, on-hit effects and Spikes all
  happen with it
- **STUN**: Hold every one of a player's cooldowns still for a while. Nothing
  is lost and nothing is reset: an item mid-wait keeps the wait it had left.
  Two stuns at once do not add -- Backpack Battles keeps them as separate
  debuffs that expire separately, so what matters is the later of the two ends.
  It is not one of the three debuffs in Section 3.2: nothing stacks and nothing
  can cleanse it

### 2.3 Weapons (Problems/Bugs)
Attack items that deal damage. All weapons:
- Activate on timer when CPU is available
- Can have "on hit" effects that trigger after successful attacks
- Can gain damage/effects from buffs

#### Critical hits

Backpack Battles' Critical hits page, quoted because every part of it matters:

- **"Deal double their usual damage."** Not a share that can be tuned per item.
- **"All sources of damage start with a 0% crit chance, and may only gain crit
  chance through outside sources."** Every attack in the catalogue writes 0.
  A weapon that crits does so because something granted it.
- **"Crit chance does not exceed 100%."**
- It reaches more than weapons: "The damage effects of [certain items] are
  capable of inflicting critical hits when they activate", and "The lifesteal
  effects... are capable of inflicting critical hits, also doubling the healing
  to match the damage dealt."

`critical_chance` is therefore both an item modifier and a player one: "Star
items gain 5% critical hit chance for each Luck" is the first, and "for the
next 1.5s, all your attacks are Critical hits" is the second.

#### Weapon Types:
- **Melee**: Standard attacks, often with on-hit effects
- **Ranged**: May have different accuracy/crit mechanics

#### Examples:

Every number here comes from the Backpack Battles item it is based on,
including CPU cost, which that game calls stamina. CPU costs are fractional
as a result.

- **Null Blade** (Common Melee, from Wooden Sword)
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

- **Throttle Gate** (Rare Shield, from Hero Shield)
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

- **Turbo Button** (Uncommon)
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

**There are seven, and that is all of them.** Backpack Battles has seven, so
we have seven. Like debuffs they stack, and they last to the end of the
battle.

| Ours | Theirs | What it does |
|---|---|---|
| **Optimized** | Heat | Items trigger 2% faster per stack |
| **Monitored** | Empower | +1 damage per stack |
| **Compute** | Luck | +5% accuracy per stack (internal id stays `calibrated`) |
| **Regenerating** | Regeneration | Heal 1 HP per stack every 2 seconds |
| **Spiked** | Spikes | Sends a blow back, up to a stack a point — see below |
| **Draining** | Vampirism | Heal 1 per stack when hitting with a melee weapon |
| **Credits** | Mana | Spent by items that need it |

#### What Spikes send back

Two numbers bound it and the smaller wins: **the stacks held**, and **a share
of the damage that landed**. Backpack Battles' Amulet of the Wild page is the
only place the share is written down:

> The "return damage limit" refers to how much of the opponent's weapon damage
> can be returned provided you have enough Spikes. Normally the limit for melee
> weapons is 100% of the damage, and for ranged weapons 0% of the damage.

So Spikes are not a melee rule, though they look like one: 0% and "does not
happen" are the same answer until an item raises the limit. Effect-damage reads
as ranged does — nothing comes back until something says it does.

| Thrown by | Base limit |
|---|---|
| Melee | 100% of the damage |
| Ranged | 0% |
| Effect-damage | 0% |

A magic weapon reads as a ranged one. The wiki names melee and ranged and
gives ranged nothing, so the two ways of not being melee land on the same
answer and nothing comes back from either until an item says so.

"Return damage limit of Spikes against Ranged- and Effect-attacks +50%" raises
two of the three, so each kind is its own number rather than one that would
raise all three at once. The page's worked example holds: ten Spikes at 150%
against a four damage blow send back six, and against a nine damage blow send
back ten, because the stacks run out first.

**What comes back can crit**, doubling it. Nothing else gives it a chance, so
"Spikes have 10% critical hit chance per Star Nature-item" is the whole of it.

**Only a blow sets them off.** Poison arrives on its own clock from an item
that struck some time ago, and fatigue comes from no item at all; neither is
something to send back.

#### How fast an item triggers

Optimized and Throttled pull against each other, and everything that changes a
cooldown lands in the same sum. Backpack Battles' wiki gives the formula:

```
Faster = every speed-up added together      (Optimized is 2% a stack)
Slower = every slow-down added together     (Throttled is 2% a stack)

Faster > Slower:  cooldown = base / (1 + Faster - Slower)
Slower > Faster:  cooldown = base * (1 + Slower - Faster)
```

**They add, they do not multiply**, and they are not applied one after the
other. Ten Optimized is 20% off the sum, not 1.02 compounded ten times.

**The two halves are asymmetric on purpose.** Dividing on the way down and
multiplying on the way up means 100% faster halves a cooldown and 100% slower
doubles it, and nothing divides by zero when a slow-down reaches 100%. At
Faster equal to Slower both forms give the base, so they meet cleanly.

**The most either way is 1000%**, ten times faster or ten times slower.

**We work it out when the cooldown starts, and the source game works it out
continuously.** There, an item fills up at a rate, so gaining Optimized part
way through speeds up what is left of the fill. Here a timer is scheduled once
for the whole cooldown, so a stack gained during it counts towards the next
one instead. The steady state is the same; only a stack arriving mid-cooldown
differs.

#### Auras

An item can draw a zone on its own map, a star or a diamond, which lands on
the grid beside it and turns with it. A zone is not the squares around an
item: most items that project one reach further than that.

A zone works in three directions, and they are separate mechanics:

| Direction | Reads as | Items |
|---|---|---|
| What it falls on | "Star items trigger 20% faster" | 22 |
| What it counts | "Triggers 15% faster for each Star Food" | 37 |
| What happens in it | "Star item activates: ..." | 17 |

All three are built. The third is a trigger rather than an effect, since the
zone is the cause rather than the target: it waits on an item standing in the
zone activating, and `after` says how many activations it waits for, so 1
fires on every one and 6 on every sixth.

Counting looks for a kind an item carries or the category it belongs to, so
"for each Star Dark-item" and "for each Star Food" are the same question asked
of different tags. An item says what it counts three ways:

```
"counting": "any"                       every item standing in the zone
"counting": {"any": ["pet", "script"]}  "for each Star Pet or Food"
"counting": {"all": ["holy", "magic"]}  both tags at once
```

**An item counts once however many tags it matches.** "For each Star Pet or
Food" counts items, not matching tags, so something that is both is still one.

An item counting two different things in two different zones -- Boiling Pot is
"for each Star Potion and Diamond Food" -- writes two of these rather than one
with a list, because the zones differ as well as the tags. Nothing it counts can be changed by another aura, because a
kind and a category are settled before a battle starts, so the order the auras
are worked out in does not matter.

#### What is not a buff

Three things kept ending up in the same place as buffs, and none of them
belongs there.

**Core attributes.** Health, CPU and Block are what a player *has*, not
statuses laid on top. Block absorbs a point of damage per point of Block and
is spent doing it; it is a resource, not a stack that lingers.

**Item modifiers.** "Items inside trigger 10% faster", "+15% accuracy",
"costs 1 less CPU". These change an item, not a player, and the engine has
carried fields for them all along -- `speed_mult`, `accuracy_bonus`,
`cpu_discount`, `damage_mult`. An item modifier says which items it reaches:
the ones inside a container, the neighbours, everything the player owns.

The difference from a buff is worth stating, because Heat looks like a
counter-example and is not. Heat is a stack a *player* carries, and it happens
to make their items faster. "Items inside trigger 10% faster" is an item
modifier with a scope, carried by no one. In the source game 124 effects
change trigger speed and only Heat and Cold do it by stacking on a player.

**Trigger speed is one quantity**, written as a fraction, positive for faster.
The source game says "triggers 10% faster" and never speaks of reducing a
cooldown, so neither do we. Advancing a cooldown by a number of seconds is a
different thing again -- a jump rather than a rate -- and every item that does
it belongs to the Engineer, so it is out of reach and unbuilt.

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

### 3.3 Something that runs out

Nearly everything in the source game lasts the battle. The few that do not say
a number: "Inflict 5 Blind for 2s", "Gain 2 Empower for 8s", "Reduce damage
taken by 25% for 7s", "Become invulnerable for 2s".

- **A duration of -1 means the rest of the battle**, which is what almost every
  buff and debuff writes.
- **Stacks are granted normally and handed back when the time comes.** Only
  what that clause granted is taken away, and never below zero: a cleanse may
  have taken them first.
- **A modifier is read while it is live and written nowhere.** One place
  decides whether it still counts, which is the moment it is read.

### 3.3.1 Counting and choosing among statuses

Several clauses treat the buffs or debuffs somebody holds as one pool rather
than naming a kind.

- **Counting the pool.** "Deals +0.5 damage for each debuff of your opponent"
  counts every stack of every kind. Naming one debuff would be a different and
  smaller number, so `buffs` and `debuffs` are written where a name would go.
- **Choosing by what is held.** "Gain 3 buffs of the type you have most of",
  "Gain 3 of the buff you have least of". Chosen **once**, so all the stacks
  go to the one kind — three separate picks would be a different clause. A
  kind held at nothing counts as the one held least, because an item saying so
  plainly means to give you a new one. Ties break the same way every time.
- **Spending the pool.** "Use a random buff to heal for 12" takes one stack of
  a kind picked at random; "Use all your buffs" takes every stack of every
  kind. Spending the pool happens even when the pool is empty; taking one from
  it needs there to be one.

### 3.4 Refusing a debuff

Two things stand between a debuff and the player it was aimed at, and
Backpack Battles' Reflect page fixes their order: **"Reflect, if a check is
successful, occurs before Resist."**

1. **Reflect** turns it back. "Reflect 2 means that you will cleanse the next
   2 stacks of debuffs applied to you, and inflict them upon the opponent
   instead." One stack per charge, however many arrive at once: "Regardless of
   how many stacks of a debuff is inflicted to the player who has Reflect,
   only 1 stack will be reflected per reflect."
2. **Resist** refuses it. "Resist prevents a debuff to be inflicted." A chance
   is checked before a charge is spent, and every chance is added together:
   "All percent chance methods are added together to give a combined total
   chance to resist."

Both are counted in stacks and neither is a buff: nothing stacks them as one
and nothing cleanses them, so they are not among the seven in Section 3.1.

**Resist is written about four things, not one.** The wiki's page is about
debuffs, and the source game also writes "30% chance to resist critical hits"
and "40% chance to resist stuns". Each says what it refuses, so one does not
cover another. A resisted critical hit still lands — it simply lands as an
ordinary swing.

The fourth is **removal**: "35% chance to protect your buffs from removal",
"protect 1 buff from removal", "protect debuffs on your opponent from being
cleansed". It is not something sent at you but something you already have
being taken, and it works the same way round — a chance or a charge, checked
per stack, with every chance added together. It says which pool it protects,
buffs or debuffs, because a cleanse takes from one or the other. It can also
be granted to the *other* player, which is what protecting the debuffs you
put on them means.

A protected stack still costs the remover one of their count: taking three
from somebody who protects one takes two, not three later.

A resist may also **name which debuffs** it refuses ("50% chance to resist
Blind and Cold") or have a **chance that grows** with what its owner holds
("a 2% chance to resist debuffs for each Luck"). Both are why the resists a
player has been granted are kept whole rather than summed into one number:
one may refuse only Blind, another only critical hits, and a total cannot say
which is which.

**Unstackable.** A few debuffs say "(unstackable)". Those top the stacks up to
the number given and refresh the clock, rather than adding: a second helping
is worth nothing to somebody already carrying a full one, but somebody
carrying two of five gets three more.

Every debuff travels this one road, so a new source of debuffs cannot forget
to offer itself to either.

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
  says exactly which squares are reached. 117 items in the catalogue project an
  aura and 41 of those reach past the four squares around them, so "next to" is
  not a useful approximation of it.
- **An aura never reaches the item projecting it.** A square of the zone landing
  on the item's own footprint is dropped.
- **Turning an item turns its aura**, except where the map marks a square `^`.
  That square projects straight up in world space however the item is turned, and
  the projection is dropped only where it lands on the item's own squares.

**Undecided:** whether an aura stops at the edge of a container, or reaches into
any square regardless. Nothing depends on the answer yet.

`server/grid_system.py` reads all of this from the map, and returns the covered
squares and both zones.

#### What the client draws

The zone appears while the player is hovering an item, holding one or dragging
one, and not otherwise: it answers a question, so it is not on screen when
nobody has asked one. An item being moved draws its zone around the square
under the pointer, because where to put it is the question being asked; an item
standing still draws it around where it stands. An item on a shelf or lying in
the chest draws nothing, being nowhere on the board.

Every square of the zone carries a marker -- a **star** or a **diamond**, so
the two zones are told apart by shape and not only by colour, and both are
drawn through so the artwork underneath can still be read.

- **An outline** is a square the zone covers and is doing nothing with: empty,
  or holding an item this aura does not act on, or off the rack altogether. A
  zone half over bare floor is aura being wasted, and seeing that is how a
  player learns to place better.
- **A filled marker** is the aura acting on the item standing there.

**One filled marker per item, however many squares of the zone land on it**,
because that is how the rule works (Section 4.4). It is what makes the display
a measure rather than a decoration: count the filled markers and you are
counting the items your placement is worth.

Two things say the same answer a second way. The items an aura is acting on are
**drawn brighter** while the zone is up, because the marker says which square
and the player cares which item. And **a click swells the markers that caught
something**: a copy grows out of the marker over about an eighth of a second,
quickly but visibly, and then fades off over a fifth of a second while the
ordinary marker underneath stays put. Nothing shrinks -- a marker easing back
down reads as something deflating, where a big one going out over a small one
reads as the marker having answered.

**The aura nods too.** When a placement sets an aura going, the item projecting
it swells slightly and settles -- a smaller movement than the marker's, since
the marker is the answer and this only says whose aura it was. The item that
moves is the projector, because that is the one something has happened to: an
item dropped into a zone is not changed by landing there, while the item whose
zone it is has just gained a Star something. It works from both ends of the
same event -- a thing put into a zone, and a zone put over a thing -- because
the player may have been watching either, and an item landing in two zones at
once sets both going.
On a click and not on a hover, because it answers a question the player asked
by pressing something; an answer that came every time the pointer crossed an
item would be noise. Asking again too soon is ignored, so a held button does
not ask on every frame and a placement, which is also a click, swells once.

For that to be true rather than nearly true, the client is told what each zone
acts on and what tags each item carries -- a zone narrowed to pets lands on a
weapon and does nothing, and a marker that filled anyway would be lying about
the only thing it is for. A zone the item draws but nothing acts through is
sent as absent rather than as empty: 68 of the 117 items that draw a zone have
no aura clause built yet, and their markers never fill.

### 4.4 What an aura does

An aura carries the effect of the item projecting it. "Star Weapons gain 3
damage" means every weapon the star zone reaches gains 3 damage; "Chance-based
effects of the star items are 15% more likely" means the same shape of thing.
The wording on each item says what it grants and to what kind of item.

**A zone can be narrowed.** "Star items trigger 20% faster" reaches everything
standing in the zone; "Star Weapons deal +2 damage" reaches only the weapons.
What narrows it is a tag: a kind an item carries (melee, holy, nature, ice),
the category it belongs to, or the class it belongs to, so "Star Food", "Star
Weapons" and "each Neutral item" all read the same way. A filter can want any
of a list of tags or all of them, and an item matches once however many it
matches.

The source game writes the singular -- "The Star Weapon gains 10 damage" --
when an item draws a one-square star, where the only weapon that can stand
there is the one. It is the zone that is small, not the rule, so a zone
reaching two weapons reaches both.

**An aura is settled once, before the battle**, because nothing moves on the
grid during one. That holds only for a modifier under a standing trigger: a
passive, or a start-of-battle one, which is settled at the same moment. A
modifier under a timer or an on-hit is not an aura at all but something an
item hands out as it goes -- "On hit: 25% chance to gain 1 damage", "Every 3s:
Star items trigger 5% faster" -- and it is applied where it happens.

**Modifiers add, they never multiply.** Two auras of +20% come to +40%, not
+44%. This is the same rule Section 3.1 gives for speed, where everything that
speeds an item up is added before anything is divided, and it is what makes a
limit mean what it says: "5% faster (up to 50%)" is ten grants of 5%.

**What an item costs to run is changed by a share, not by a number of
cycles.** "Uses -15% stamina for each Star Holy-item" is a share, and it adds
to the player's own -- "Items use +20% stamina" -- rather than multiplying with
it. It was a flat subtraction for as long as nothing used it.

**A modifier on an item can carry a clock**, the way one on a player always
could. "The Star item triggers 100% faster for 1s" is lent rather than given,
and taken back when the time comes. A modifier with a clock is therefore not
settled with the standing ones before the battle — settling it once is exactly
wrong for something that has to be taken back.

**A modifier handed out again and again can carry a limit.** The limit is on
what one item has given another, not on what the receiver has been given by
everybody, so two items each granting 5% up to 50% reach 100% between them.
A grant that would overshoot is trimmed rather than refused.

**An aura can watch what an item in its zone *does*.** An activation is the
common one, but the source game also writes "Star Weapon hits", "Star Weapon
crits" and "Star Potion consumed", and those are different moments: a weapon
that missed activated and did not hit.

**Every trigger is an activation, not only a timer.** A Potion drunk by its own
condition activated; so did a shield that rolled and answered a blow, and a pet
another item set off. Only a standing trigger is not one: a passive is on
throughout rather than happening at a moment, and a start-of-battle one is
settled before the battle has a first moment to happen in.

**A zone watches its own side.** Every moment an aura can watch names the
player it happened to, and that is asked before whose item it was: two players'
loadouts come from two sessions, and nothing stops them handing out the same
identifier.

**A zone can be narrowed by what an item is *not*.** "10% chance to gain 1
Regeneration, 30% if the item is Holy" is two clauses, and without a way to say
"not Holy" a Holy item would answer both.

**A trigger can wait for several of its moment.** "After 4 hits, gain 1
Empower" fires on every fourth, and it is the item's *own* four: the Claws of
Attack page settles it -- "one every four hits, meaning only one empower every
6.4s" against its own 1.6s cooldown -- so it is counted on the trigger and not
on the player. A roll that failed is not one of the four.

**Not everything counted is a zone.** "Triggers 10% faster for each Ice item"
counts what the player has out, wherever it stands, which is `own` rather than
a shape on the grid.

**A zone can count its empty squares.** "Destroy 4 Block for each free Star
slot" counts the squares of the zone that no item stands on — the only thing
an aura counts that is not an item.

**Counting works three ways round.** A zone can decide what it falls on
(a modifier), what it counts (a modifier on the item projecting it, sized by
what stands in the zone), or when something happens (a trigger that fires when
an item in the zone activates). A fourth reads the player rather than the grid,
sizing a modifier by a status its owner holds.

**A zone can hand out a modifier that is itself sized by a status.** "Star
items gain 4% critical chance for each Luck" is the third and fourth ways at
once: which items get it is the grid's answer, and how much is the player's,
read as the battle goes on rather than settled before it. A ceiling on one of
these -- "(up to 50%)" -- is a ceiling on the reading and not on a total, so
the count can fall again and the modifier falls back with it.

**A zone can scale what the items in it *give*.** "Star items give +30% Block",
"Star Items give +100% Vampirism". The share sits on the giving item rather
than on the player, so two items in the zone are each scaled by it and one
standing outside gives what it always gave. A share on the player -- "you gain
25% more Block" -- is a separate thing, and the two add.

**A running total can be narrowed to a zone.** "Star items gained 12 Block"
counts what the items in the zone have handed over and no other Block, so a
shield gaining 30 on its own does not answer it. A zone answers for itself —
what it gave is the owner's, and it only ever goes up — so a total narrowed
this way cannot also name whose it is or ask for what is held.

**A chance can grow with what its owner holds.** "7% chance for each Luck to
gain 3 Mana" is read at the moment of the roll and not settled beforehand, so
Luck gained during a battle counts. The same shape a resist's growing chance
uses.

There are no synergies that count how many of a category sit beside each other.
An earlier version of this document described six, of which two were built
against orthogonal adjacency. Neither the six nor adjacency exist in the game
this one is based on, so both are gone.

### 4.5 What a container knows

**A container is an item.** It is bought from the same shop, built from the
same catalogue, stands on the same grid and carries clauses like anything
else, so it says when they happen the same way: a passive, a start of battle,
a timer.

**"Inside" is the container's own footprint.** Its squares are the ones other
items stand on, so what is inside one is whatever sits on the squares it
covers. That makes `inside` a zone like a star or a diamond, and everything a
zone can do it can do: reach what stands there ("Items inside trigger 10%
faster"), count what stands there ("Gain 8 Block for each Neutral item
inside"), or hand out a scaled modifier ("Items inside gain 10% critical hit
chance +3% for each Luck").

**A container is not standing on its own shelf.** Its squares are offered
rather than filled, so nothing counts it as an item on the grid: a clause
counting free squares would otherwise find none, and a shelf would hold one
more item than it does.

### 4.6 What a Potion does for the Potion above it

Every Potion, when it is drunk, also applies the effect of the Potion above
it, **without consuming that one**. The source game calls it potion spillover
and writes it on every Potion page.

**"The Potion above it" and "its star" are the same square.** A Potion's map is
`['*', '^', '#']`: it covers two squares, and its star is the one directly
above, marked `^` so the projection goes straight up however the item is
turned. So this is the star zone and needs no separate idea of "above" — which
is why a vertical stack is what the source game's own advice recommends.

**It does not chain.** The wiki says "the Potion above it" in the singular
every time, so a stack of four is four spillovers rather than one four deep.
Worth settling by playing: the Potion Belt's advice, "the entire setup should
be vertical to make the most of the Potion spillover", reads either way.

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
  up, **plus whatever the player's own items add** — Maneki Neko says "Sale
  chance +3%". The roll comes from the shop's seed, so the same seed and the
  same held items always give the same five items at the same prices. An item
  bought on sale sells for what it cost.
- **Item Costs**: each item's own cost, taken from the Backpack Battles item
  it is based on. There is no price band per rarity: a Unique can cost 5 gold
  and a Rare 16.

#### Items that do something in the shop

Some items act between battles rather than during one. Gold Armor gives 3 gold
when the shop opens; Maneki Neko makes sales likelier for as long as it is
held.

The battle simulator cannot run these. It knows about time passing, attacks
landing and health falling, and "the shop opened" is none of those. So
`server/shop_phase.py` handles them instead — a small thing of its own rather
than a branch inside the battle code.

- **Shop entered** is the source game's name for it, and **the battle ending
  is the moment**. Those are the same instant: a round ends, gold is paid, a
  shop appears. It fires there, once, where the round turns.

  Naming it for the shop and firing it at the battle's end is deliberate. The
  name is the player's word for when it happens; the battle's end is the only
  moment that happens once. "When the shop is opened" is not a moment at all —
  the shop is session state, it has no open, and a client may read it on every
  screen it draws.

  So a player who leaves the shop and comes back is not paid again, and
  rerolling does not pay either. That holds because of *where* it fires, not
  because anything guards it. Moving the call from where the round turns to
  where the shop is rebuilt — two places forty lines apart that look
  interchangeable — would quietly pay out on every reroll. There is a test
  that fails if anyone does.

  **A shop effect that grants something lasting** — a free reroll, a discount —
  should be session state set at that same moment and cleared when the next
  battle starts, so it cannot be hoarded across rounds or farmed by re-entering.
  Nothing in the catalogue asks for one yet.

  **Round one does not fire it, and does not need to.** The first shop is built
  when the session starts, before the player holds anything, so there is
  nothing that could pay out.
- **On buy** fires once, as the item changes hands.
- **Sale chance** is not a trigger. It is read off everything the player holds
  each time a shop is built.

**Most shop clauses are not effects, and cannot be written as one.** "Dig up a
random item", "Generate a low-quality Gemstone", "Create different items based
on the combined value" all need the shop to *make* an item and put it in the
player's bag, and nothing in the game does that except a purchase. Trade
offers do not exist. Neither does changing which items the shop draws from.
Those are features to build. BACKLOG.md lists which clause needs which.

### 5.3 Recipe System (Item Combining)
- **How it Works**: put a recipe's items together in your rack. One of them has
  to touch all the others; they do not all have to touch each other, or a Stone
  Golem could never be made -- four Stones cannot all touch one another, but all
  four can touch the Heart Container between them.
- **Combination Timing**: items combine as the next shop phase begins, straight
  after the battle. Nothing needs locking, because the rack is fixed from the
  moment the player starts the battle.
- **One step per shop phase**: a result does not go on to combine again in the
  same phase. 20 items are both a recipe's result and another's ingredient, so a
  chain takes a round for each step and the player sees each one.
- **Which one, when several could happen**: the item placed most recently
  decides, and an ingredient is only used once. A catalyst can serve more than
  one combination in the same phase.
- **Where the result goes**: onto the squares its ingredients freed, if it fits
  there. It never spreads into space the player was keeping for something else,
  so when it does not fit it goes to the chest.
- **Two Ways to Get Combined Items**:
  - Combine the required items (cheaper but requires finding components)
  - Buy directly from shop if lucky (more expensive but immediate)
- **Catalyst Items**: some recipes use a catalyst. It has to be there and has to
  be touching, and it is still there afterwards.
- **Craft-only items**: an item marked `recipe_only` is never sold, whatever its
  rarity would allow. Combining is the only way to get one.
- **Items that wait on another**: an item with `shop_needs` is stocked only while
  the player holds the item it names. The gemstones wait on a Coin Miner.

#### Telling the player before it happens

Combining is settled the moment the battle starts, so everything the player
needs to decide with has to be on screen before then. Two things answer that,
and they are different in kind:

- **`pending`**, on every response that can change the rack -- `/session`,
  purchase, sell, move, and the battle, whose `session_update` carries the rack
  as combining has just left it. It is worked out from the rack each time
  rather than stored, so no move can leave it behind. Each entry says what
  would be made, `have` of `need` parts, the ids of the ingredients and of the
  catalysts, and the parts still `missing`.
  - `have == need` is a combination that **will** happen. The complete entries
    are read from the same plan the combining itself uses, so what the player
    is shown and what happens cannot disagree.
  - `have < need` is progress towards one, and only counts parts that are
    already touching. Owning them is not enough.
- **`GET /catalogue/combining`**, a map of item type to the types it appears in
  a recipe with, and a name for every item type. The same for every player and
  every rack, so the client fetches it once and answers from it. It needs no
  session and no token. The names are there because the client holds no
  catalogue: it can name an item the server has sent it and nothing else, and
  "Long Poll 2/3" names a thing that does not exist yet.

The split is deliberate. `pending` needs the rules -- touching, counting,
deciding between two recipes that want the same item -- and those stay on the
server, because a second set of them on the client would drift and start
promising combinations that do not happen. The partner map needs none of them:
it only says these two go together, which is why the client may hold it. It has
to, since it is wanted on hover and while dragging, and a line every frame
cannot be a request every frame.

An item in no recipe is absent from the map, and a type that pairs with itself
appears in its own list -- a Hero Longsword eats two whetstones, so one
whetstone points at another. A `class:` part (Section 5.4) is every item that
answers it, so a Dead Cell points at all eight items that are on fire; none of
those eight points at another, because they answer the same one part and one
part takes one item.

#### What the client shows

All four are drawn over the shop screen at once, by one node above the shelf,
the rack and the chest -- because each of them joins an item in one of those
places to an item in another.

- An **arc of electricity** from the item under the pointer, or in hand, to
  every item it could combine with, wherever it is: the shop, the chest or the
  rack. Drawn from the partner map, so there can be several at once, and it
  says only that the two go together -- the parts may take several rounds to
  collect. It appears only while the player is hovering, holding or dragging
  something: it answers a question, so it is not there when nobody has asked
  one.
- An **orange glow** joining items that are about to combine, so the player can
  see it coming and break it up before starting the battle. Drawn from the
  `pending` entries where `have == need`, and drawn whatever the pointer is
  doing: it is a warning, not an answer.
- A **progress label** above the item the arcs come from -- "Long Poll 2/3" --
  from the `pending` entry the item is furthest along. The name comes from the
  catalogue's `names`, because what it will make does not exist yet and the
  client has nothing else to look it up in.

  A finished rack is named too, and named first: "Long Poll 3/3" over two items
  about to become a Long Poll. The glow already says *that* they are joining;
  only the label says *what into*, and a player deciding whether to break the
  pair up needs the second more than the first. Where an item is part of both a
  finished rack and an unfinished one, the finished one wins -- it is what is
  going to happen.

  It stays up for a moment and fades after the player stops reaching, because
  letting go of an item is how it is put down: the pointer leaves at the
  instant the answer is wanted. It stays where it was standing rather than
  following the item, which by then has been drawn again somewhere else.
- A **merge animation**, in four beats over about a second and three quarters.
  The items rattle where they stand, each on its own path, so it reads as
  something happening to them rather than to the screen. They fly into the
  middle of the squares they are about to free, brightening as they go. **The
  whole screen goes white** for a third of a second at the moment they stop
  being themselves -- one whiteout however many racks combined, because several
  at once is one event to look at. It covers the swap outright: the rack is
  drawn again from the server's answer underneath it. It rises fast, falls
  slowly, and stops short of solid white, because a screen that goes fully
  white and back is a blink nobody asked for. Then what
  they became stands up, overshooting its size, with rings struck outwards from
  it and **its name written over it** -- two items have just become a third the
  player has never held, and the thing they were watching a moment ago was the
  other two. A catalyst rattles with the rest, flares once, and stays where it
  is.
  Each beat has a sound: a rattle over a note bending upwards, a crack, and a
  struck chord. They are generated by `tools/create_sounds.py` like the rest of
  the game's audio, and are silent wherever animations are off.

Combining happens the moment the battle ends, but the player does not see the
rack again until they have watched the battle and closed the result screen. So
the shop screen plays it forwards from the two states the response already
carries, and never shows the result before the merge:

1. Draw **`battle_result.player_inventory`** -- the rack that fought, which is
   the rack before anything combined. This is the first thing painted.
2. Play every combination in `session_update.combinations`. They can run at once:
   an ingredient is never used twice and a result never feeds another
   combination in the same phase, so none of them waits on another.
3. Draw **`inventory`** -- what the player holds now.

Step 3 is what makes the animation safe. It ends on the server's answer, so a
bug in the animation, an interruption, or a player skipping it cannot leave the
wrong rack on screen. **A client that ignores `combinations` entirely is still
correct**: it draws `inventory` and cuts straight to the result.

Each combination says what was made and its id, the items consumed and the
catalysts kept -- whole items, with their positions, because the client has no
catalogue to look a name up in and two of a kind would be ambiguous -- the
squares that were freed, and where the result landed, `null` meaning the chest.

### 5.4 Recipes Come From the Data, Not This Document

Every recipe is imported from the Backpack Battles item it is based on and
lives on the item itself in `server/data/items/*.json`:

- `recipe`: a list of recipes — an item can have several, any one of which
  makes it. Each recipe is `{"ingredients": [...], "catalysts": [...]}` of
  item slugs; `catalysts` is present only when the recipe uses one (a
  catalyst joins the combination and survives it, Section 5.3). Ingredient
  order does not matter; duplicates are real (some recipes need two of the
  same item). A `class:` prefix is a wildcard for any item of that class:
  `class:fire` means any item whose `icontype` holds `fire` (Hot Cell and
  Thermal Torch craft this way, and eight items qualify). One part takes one
  item, so a second fire is no help. Every name is a catalogue slug or a
  wildcard: a source recipe needing an item we have not
  imported (Twine, Cauldron, Thor's Hammer, Goobling) is pruned at import,
  because a player could never complete it. The wiki corpus in
  `research/wiki_pages/` keeps the originals; re-run `research/parse_wiki.py`
  after importing a missing ingredient and the recipe comes back.
- `recipe_only: true`: never appears in the shop; crafting is the only way.
- `shop_needs: "<slug>"`: appears in the shop only while the player holds the
  named item. The fourteen gem modules all need the Crypto Mining Rig.
- Unique rarity is the treasure path: found through treasure chance effects,
  not sold. This is the `rarity` field, not a separate flag.

98 of the catalogue's items are craftable. Real examples, with our names:

- **Querystorm** (Godly): Denier of Service + Stray Voltage
- **Rubber Duck** (Epic): Cold Storage + Ctrl+Z + Ctrl+Z
- **Duct Tape Fix** (Epic): Hotfix Ampoule + API Token
- **Root Certificate** (Godly): Self-Signed Cert + Crypto Mining Rig
- **Rainbow Garbo Megaheap Alphadump** (Godly): Leech Garbo + Flare Garbo +
  Rubber Duck + Hardened Garbo

An earlier version of this section listed invented recipes over invented
items. The catalogue is the record; regenerate any listing from it.

### 5.5 SnubaCoin

Gold is spent inside a run and gone when the run ends. **SnubaCoin** is the
other one: it is paid out *for* a run, it survives the run, and it belongs to
the account rather than the session.

The name is not ours — Snuba is a real query layer with a real silly name, and
the game only reports it. The coin is a thick teal token with a magenta rim
and a **snorkel** struck into its face, made slightly badly on purpose.

#### One coin, everywhere

There is **one picture of the coin**, and it is used at every size and in
every place: the main menu balance, the crate, and the coins that fly during
the payout. There is no flat version for small sizes and no second drawing
for the animation. A currency that looks like two things is two currencies to
the player.

This is why the coin is **not** a mask, and does not belong to the
`trophy.svg` / `heart.svg` family. Those two are flat one-colour masks for one
reason: they toggle. Each trophy is lit or spent, each heart is lit or spent,
and the screen tints them. A balance never toggles, so the coin stays painted
art at every size.

At small sizes the snorkel on its face stops being legible, and that is fine.
The teal disc and the magenta rim are what has to read, and they do. The
player has to know it is a coin, not what is stamped on it.

Nothing spends SnubaCoin yet. It is shown, banked and counted, and character
skins are the intended first thing to buy. A balance the player cannot spend
is still worth paying, because it makes a finished run leave a mark; a run
that leaves nothing behind is a run the player has no reason to finish.

#### What a run pays

A run pays out once, when it ends, whichever way it ends:

| Reason | SnubaCoin |
|--------|-----------|
| Finishing the run at all | 3 |
| Each win banked | 1 each |
| Each try still unspent | 1 each |
| Winning the run (10 wins) | 5 |

A lost run on 2 wins and no tries pays **5**. A won run with 2 tries left pays
**20**. The spread is four times over, which is enough to make the better run
worth wanting without making a loss worth nothing.

#### A run that is abandoned

A player can also simply leave — close the window at 3 wins and never come
back. That run still pays, but it pays **1 per win and nothing else**: no
completion bonus, and nothing for the tries.

The reason is arithmetic. Give an abandoned run the whole table and quitting
at round 1 with 5 tries unspent pays 3 + 0 + 5 = **8**, while genuinely losing
on 2 wins pays 3 + 2 + 0 = **5**. Quitting would beat playing. Wins are the
only line on the table a player cannot collect by giving up early, so wins are
the only line an abandoned run gets.

It is paid **when the player starts their next run**. There is no quit signal
— the window closes and the session is never touched again — so the next
session start is both the first moment the server can know the last run is
over and a moment the player is there to see it.

Every part of that table is a thing the player already watched themselves
earn. Nothing is a number the game invented after the fact, and this is the
whole point of the payout: Section 6.4 pays the counters out one at a time,
so the player is paid in the same objects the run was counted in.

#### Where it lives

SnubaCoin is per account, not per session. It sits beside the totals the
`users` table already keeps (`total_games_played`, `total_wins`,
`total_losses`, `current_rank`), and the server is what adds to it. The
client never computes a balance; it shows what it is told, exactly as it does
for gold.

The main menu shows the balance. A guest account banks it the same as a
registered one, so a player who never signs up still keeps a total.

## 6. Battle Phases

### 6.1 Preparation Phase (60 seconds)
1. View shop
2. Buy/sell items
3. Arrange inventory
4. View opponent's last build

### 6.2 Battle Phase
1. Items activate based on triggers
2. CPU management occurs automatically
3. Battle ends when a player reaches 0 HP

There is no time limit. **Fatigue** (Section 7.1) is what ends a battle, and
it grows fast enough that no build survives much past forty seconds. The
engine keeps a backstop far beyond that so a bug in fatigue cannot hang the
simulation, and if a battle ever did reach it the player with more HP wins --
but that is a failure to notice, not a rule of the game.

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
out. The player clicks to move on to the shop.

If the round was the run's last — the 10th win banked, or the last try spent —
the click leads nowhere yet. The overlay stays where it is and carries on into
Section 6.4.

### 6.4 End of the Run

A run ends two ways, and both take the same exit:

- **Won**: the 10th win is banked.
- **Over**: the last try is spent.

Winning is not a special case that skips the ending. It is the better of the
two endings, and it uses the same one.

A finished run does not fight again. The server refuses the next battle rather
than simulating it, because a run whose ending has been shown and paid for is
over — and one that carried on would spend a sixth try it does not have, or
bank an 11th win and change what it had already been paid for.

#### It is not a screen

The end of a run is the **second beat of the round result**, drawn in the same
place, over the same finished battle. Section 6.3 has already put the Wins bar
and the Tries bar on screen and moved the one icon the round changed. Those
bars stay exactly where they are. Nothing is torn down and rebuilt.

This matters for one reason: the player is paid in the counters they are
already looking at. Move them to a screen of their own and the payout stops
being made out of the run and starts being a report about it.

The finished battle stays visible underneath. An eye marked **Hide** at the top
pulls the whole overlay away so the player can read the battle that ended the
run, and puts it back.

#### The beats

1. The round result settles (Section 6.3).
2. The title changes. **"Round won"** becomes **"Run won"**. **"Round lost"**
   becomes **"Run over"**. The ribbon flies off and the new title grows in its
   place, so the player sees the run take over from the round.
3. A **cold storage crate** slides in from the right, marked with its snorkel
   and the SnubaCoin balance the account already had.
4. The run pays out, one part at a time, in the order of Section 5.5's table.
   Each part is a banner that names it, and each banner is paid at the moment
   its coins fly.

   **Nothing flies as itself.** A counter pops off its bar, **turns into a
   SnubaCoin in the air**, and the coin is what travels to the crate. That
   turn is the payout in one gesture: the thing the run was counted in
   becomes the thing the run paid.

   - `RUN COMPLETE` — the flat 3. These coins have no counter to come from, so
     they come off the banner itself.
   - `10 WINS` (or `4 WINS`) — every lit trophy pops, turns and flies. Its
     slot goes dark behind it.
   - `2 TRIES LEFT` — every heart still lit does the same.
   - `RUN WON` — the 5 for winning, on a win only, off the banner.
5. The crate's number counts up as each part lands. It closes when the last
   one is in.
6. The player clicks. Every panel leaves the way it came in, and the game goes
   to the main menu.

**Click to continue is live from the first beat.** A player who has seen it
before can leave at any point, and the payout is banked in full whether they
watched it or not. The show is worth watching once and skippable forever
after.

#### Winning has to look different

The beats are identical for both endings. Only the dressing changes, and the
dressing is the whole reward:

| | Run over | Run won |
|---|---|---|
| Ribbon | Red | Blue |
| Title | "Run over" | "Run won" |
| Racks | Nothing | Both racks throw sparks |
| Wins bar | The few lit trophies fly | **All ten** fly together, in beams |
| Banners | Wins, tries left | Wins, tries left, and the run bonus |

A loss still pays, still gets a crate, and still gets its counters flown out
one at a time. A player who loses is not shown a smaller version of the win —
they are shown the same ceremony over a worse number.

#### What we are not building

Backpack Battles offers a third thing at 10 wins: a choice between taking the
win and carrying on into a survival mode. **We are not building that.** The
run ends at 10 wins.

## 7. Special Mechanics

### 7.1 Fatigue

Fatigue is what ends a battle. Nothing else in the game grows, so two builds
that cannot finish each other would stand there swinging forever.

**Nightfall is 17 seconds in.** The screen darkens and says so. From then on,
once a second, **both** players take fatigue damage.

**The level is the damage.** Each player carries their own fatigue level,
starting at 0. A payout raises the level and then deals all of it:

| When | The level goes up by |
|------|----------------------|
| Every second from nightfall | `level // 10 + 1` |
| Every second past 60 seconds | `level // 5 + 1` |
| Any other source (an item) | `1` |

So the nightfall sequence is 1, 2, 3 ... 11, 12, 13, 15, 16 ... — it is a tenth
of itself, rounded down, plus one. That doubles the level about every eight
seconds, and past a minute, when the divisor becomes a fifth, about every four.
Nothing heals through the tail of it.

**An item that inflicts fatigue raises the same level.** It takes one step
rather than a growing one, and deals what the level then stands at. This is why
it is worth doing early: a level pushed to 3 before nightfall makes the first
nightfall payout deal 4, and every payout after it more.

**Almost nothing answers fatigue.** It is not an attack, so accuracy never
comes into it, no shield rolls against it, and Block does not absorb it — the
same rules poison plays by, and for the same reason: there is no attack there
to answer.

The one thing that does reach it is the share the target carries. "Reduce
damage taken by 25%" and invulnerability answer every kind of damage, fatigue
included, because they are written about damage rather than about attacks.
`_take_damage` takes the share first and Block second, and fatigue asks for
neither `blockable` nor an attacker.

**Nightfall is a moment items can be written against.** "Fatigue starts: gain
10 Heat" fires once, on the way past, and it fires before the first payout
lands.

### 7.2 Critical Hits
- Base 5% chance
- Deals 2x damage
- Can trigger special effects

### 7.2.1 Turning health into Block

"Convert 50 health into 100 Block", "Consume this and convert 15 health to 30
Block". The health is a **price**, not damage: nothing that stands in front of
damage stands in front of it — no Block, no share on damage taken — and
nothing that answers being *hit* answers it, so Spikes send nothing back.

**It is still health falling, and a threshold still notices.** "Health drops
below 50%" is written about health, not about being hit, and Vampiric Armor
paying 50 at the start and 10 every 2.8s is exactly what carries an already
hurt player past the line. Every way a quota goes down goes through one place,
which is what says so.

**All of it or none of it, and never the last point.** A player with less
health than the price keeps what they have and gains nothing, so a conversion
can never be what kills them.

What comes back is Block gained like any other, so a share on Block gained
still applies to it.

### 7.2.2 A share of maximum health

"Gain 10% maximum health + 15% per Star item". A share is read against the
maximum the battle **opened on**, not the one standing now, so two of them
add to 25% rather than compounding to 26.5% — the same rule every other pair
of shares here follows.

Raising the ceiling gives the health with it, rather than leaving a gap to
fill. It is still not healing: a clause that changes healing has nothing to
say about how much bigger somebody just got.

The other side of it is written too — "Your opponent gains 15% less maximum
health from items" — and it is a share on what an item hands over, not on
healing and not on damage.

### 7.3 What stands in front of the quota

Three things, in this order:

1. **A shield's prevention**, if this was an attack. See Section 2.4: one 30%
   roll, and every consequence behind it lands together or not at all.
2. **The share the target carries** — "Reduce damage taken by 25%", and
   invulnerability at -1.0. It answers to every kind of damage, including the
   kinds no shield sees.
3. **Block**, if this is damage Block answers, spent a point at a time.

**Block absorbs what is actually arriving**, which is why it comes after the
share rather than before it. Twenty damage against a quarter off spends
fifteen Block, not twenty — the two orders land the same damage and leave
different amounts of Block, so they differ in how long a shield lasts.

Nothing blocks damage that comes from a player's own stacks: poison has no
attack to block, and effect-damage has no weapon behind it.

**Undecided:** whether a shield's flat prevention comes before or after the
share. It matters — against 20 damage with a 15-point prevention and a quarter
off, preventing first leaves 3 and sharing first leaves nothing. The wiki
gives no order. See BACKLOG.md.

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
