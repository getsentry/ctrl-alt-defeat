# Triggers, Effects and Events

What an item can say, and whether the server does anything about it.

The item catalogue is imported by hand from the Backpack Battles wiki, so an
item can name a trigger or an effect that nothing implements. When that
happens the loader returns `None` and the line is dropped without a word. The
item still loads, still appears in the shop and still fights — it just does
less than it says. **26 of the 95 items in the catalogue lose something this
way.**

This page is the list. Regenerate the tables against the code before trusting
them; the loader is the authority, in `_parse_trigger` and `_parse_effect`.

## Events

`EventType` in `server/event_system.py`. Only five of the fourteen are wired
at both ends.

| Event | Emitted | Listened to | Notes |
|---|---|---|---|
| `battle_start` | yes | yes | |
| `health_fell` | yes | yes | A player's health went down, from any source. Was `damage_taken`. |
| `on_attacked` | yes | yes | Shields roll here, only against a hit |
| `on_hit` | yes | yes | The attacking item's own on-hit effects |
| `item_consumed` | yes | **no** | Emitted so adjacency could be recalculated. Nothing recalculates it. |
| `battle_end` | no | no | Declared, never used |
| `damage_dealt` | no | no | `DamageDealtTrigger` exists and waits for it |
| `player_death` | no | no | The loop checks the quota directly instead |
| `timer_tick` | no | no | Timers go through the heap, not an event |
| `item_activated` | no | no | Declared, never used |
| `buff_applied` | no | no | Declared, never used |
| `debuff_applied` | no | no | Declared, never used |
| `cpu_exhausted` | no | no | A throttle is logged, not emitted |
| `cpu_regenerated` | no | no | Declared, never used |

## Triggers

| Trigger | Built | Items | What it means |
|---|---|---|---|
| `timer` | yes | 27 | Every cooldown in the game |
| `passive` | yes | 28 | Always on |
| `battle_start` | yes | 20 | Once, at the start |
| `on_attacked` | yes | 6 | Owner was attacked, and the attack hit |
| `health_threshold` | yes | 5 | Owner's health fell past a line, once a battle |
| `on_hit` | yes | 1 | This item's own attack landed |
| `on_attack` | **no** | 2 | Fires whether the attack hit or missed |
| `on_crit` | **no** | 1 | `neural_interface_blade` |
| `on_damage` | **no** | 1 | `redundancy_protocol` |
| `on_damage_dealt` | **no** | 1 | `vampire_rootkit` |
| `on_big_damage` | **no** | 1 | `ddos_protection_module` |
| `round_start` | **no** | 1 | Outside the battle. `premium_subscription` |

`on_hit`, `on_attacked` and `on_attack` are the three timings from Section 1.3.
Two of the three are built.

## Effects

| Effect | Built | Items |
|---|---|---|
| `attack` | yes | 23 |
| `stat_mod` | yes | 23 |
| `buff` | yes | 9 |
| `modify` | yes | 10 |
| `heal` | yes | 10 |
| `consume` | yes | 7 |
| `prevent_damage` | yes | 6 |
| `cpu_drain` | yes | 6 |
| `cleanse` | yes | 5 |
| `debuff` | yes | 2 |
| `block` | yes | 1 |
| `spawn_companion` | **no** | 4 |
| `gold_gain` | **no** | 2 |
| `scaling_buff` | **no** | 2 |
| `adaptive_buff` | **no** | 1 |
| `adjacent_buff` | **no** | 1 |
| `damage_bonus` | **no** | 1 |
| `damage_immunity` | **no** | 1 |
| `damage_reduction` | **no** | 1 |
| `enemy_debuff` | **no** | 1 |
| `free_refresh` | **no** | 1 |
| `lifesteal` | **no** | 1 |
| `multicast` | **no** | 1 |
| `shop_discount` | **no** | 1 |

`enemy_debuff` is `debuff` under another name, and `adjacent_buff`,
`adaptive_buff` and `scaling_buff` are all `buff` with a condition. Four of
the twenty-three are spellings rather than mechanics.

## What Backpack Battles actually has

**They do not publish a list.** The wiki's Game Mechanics page documents
buffs, debuffs and status effects, but under "Topics to explain more about" it
names "Item activation rules" as one of the things nobody has written up.

So this is derived instead, from the effect text of all 498 items. Each one
writes its trigger in bold at the head of the clause, which makes them
countable. 185 distinct phrases collapse to these families:

| Family | Uses | Phrasings | Ours |
|---|---|---|---|
| `Every Xs` | 129 | 43 | `timer` |
| `Start of battle` | 104 | 2 | `battle_start` |
| `On hit` | 75 | 1 | `on_hit` |
| Shop / out of battle | 49 | 12 | — |
| `After Xs`, once | 37 | 13 | — |
| Resource threshold | 31 | 27 | — |
| State (Battle Rage, charged) | 26 | 8 | — |
| Health threshold | 25 | 7 | `damage_taken` with a threshold |
| Kill / capture | 23 | 3 | — |
| `On attack` | 14 | 1 | — |
| `On attacked` | 10 | 1 | `on_attacked` |
| `On miss` | 2 | 1 | — |
| `Before miss` | 2 | 1 | — |
| one-offs | 82 | 66 | — |

Three things this says.

**The accuracy family is 93 uses over four phrasings** — `On hit`, `On
attack`, `On miss`, `Before miss` — and `On hit` alone is the most common
combat trigger in the game. Section 1.3 covers the first three.

**There is no closed vocabulary.** 66 of the 185 phrases belong to one item
each: "4 Potions inside consumed", "7 debuffs inflicted", "Card revealed".
A third of the phrasings are bespoke. Any trigger system is therefore a small
core plus a long tail, and generalising the tail is not worth it.

**A period is data, never a set.** `Every Xs` has 43 distinct values — 2.1s,
2.4s, 2.6s, 2.7s. Our `timer` already reads it off the item.

## Where a trigger belongs

Read this before adding one. Every rule below was paid for by a bug.

### A trigger belongs where the knowledge it needs lives

This is the whole rule. Work out what the trigger has to know, and put it
where that is already known. Three we have settled:

| Trigger | Has to know | So it lives in |
|---|---|---|
| `on_hit`, `on_attack`, `on_miss` | Did the accuracy roll pass? | the attack path |
| `on_attacked` | Was there an attack, and did it land? | the attack path |
| health thresholds | Where is my health now? | wherever health changes |

`on_attacked` and a health threshold look alike — both are an item reacting to
its owner getting hurt — and they are not the same thing at all. A shield
needs an *attack*: something to roll against, with a damage figure to prevent.
A potion needs a *level*: it does not care what lowered the health or whether
anything attacked at all.

Getting that backwards has a cost we already paid. `on_attacked` used to be
emitted from the damage-applying function rather than the attack, which made
that function mean two things at once — "resolve an attack" and "apply damage
to a player". Poison then could not reuse it, because poison must not make
shields roll, so its damage got a hand-copied second path. The copy is how
poison came to write straight to the quota and be invisible to everything.

The lasting shape: `_mitigate_attack` handles what stands between an attack
and the quota, and `_take_damage` is the one place a quota goes down. A new
damage source calls the second and skips the first.

### Emit from a choke point, not from every source

A trigger that listens for an announcement only works if every source
remembers to announce. Poison bypassed `DAMAGE_TAKEN`, so a Health Potion sat
in the rack and watched its owner die of poison.

The fix is not "make poison emit too" — that lasts until the next damage
source. Nor is it to abandon events: the first attempt at the health threshold
hand-rolled a registry on the simulator and filtered it by owner, which was a
second mechanism doing the first one's job.

**The two are not in tension.** Route every source through one function, and
emit from there. `_take_damage` is the only place a quota goes down, so
`HEALTH_FELL` is emitted once, from it, and anything watching a player's
health subscribes like any other trigger. A new kind of damage gets it right
by calling the same function.

The rule is about *where the emit lives*, not about whether to use events. If
you find yourself keeping a list of things to check by hand, look for the
choke point instead — it is usually the function you are already in.

**A health threshold is not an over-time effect**, though both are driven by
the player's own state. A threshold fires once, when a number is crossed; an
over-time effect fires on a clock forever. Section 2.1 has the rules.

### One roll in front of a list, never one roll per effect

Backpack Battles writes a chance once and hangs the consequences off it:

> "On hit: **70% chance** to inflict 2 Poison and a random debuff."
> "On attacked: **30% chance** to prevent 9 damage, remove 0.3 stamina from
> opponent, and gain 1 Spikes."

So the chance belongs to the trigger and the consequences are a plain list of
effects behind it. `ChanceTrigger` is that shape, and `on_hit` and
`on_attacked` both use it. Rolling per effect would let a shield prevent the
damage and forget the stamina, which no item in the game can do.

Anything a trigger's handler does not recognise should fall through to
`_apply_effects` rather than be skipped. A handler that reads only the effects
it expects is the second way an effect goes missing, below.

### State the numbers, never default them

The catalogue is transcribed by hand from a wiki. A default cannot be told
apart from a transcription that lost a value, and a wrong item that still
loads is worse than one that fails.

This has caught real errors: a shield taking a silent 30% / 8 / 0.0, an
`on_hit` with no chance, a debuff named `virus` that nothing ticks. Every one
of those looked like a working item.

An effect that genuinely has no value for a field writes it anyway — `0` for a
shield that takes no CPU, `1.0` for an effect that always happens.

### Over-time effects are a closed set of three

Something that happens on a clock, driven by the player's own state rather
than by an item. There are three in the source game and there will not be a
fourth:

| Effect | Period | Amount | Driven by |
|---|---|---|---|
| Poison | 2s | 1 damage per stack | a stack count |
| Regeneration | 2s | 1 health per stack | a stack count |
| Fatigue | 1s, from nightfall (17s) | escalating | its own last value |

Only Poison is built. `OverTimeEffect` in `battle_engine.py` is the base
class, each subclass works out its own payout, and `OVER_TIME` is the registry
the battle loop walks.

**Fatigue is why it is a class and not a record.** Its amount is
`previous + previous // 10 + 1`, computed from what it dealt last tick — after
60 seconds the divisor becomes 5. No arrangement of "damage per stack" and
"heal per stack" fields can hold that, so the first version of this, which had
exactly those two fields, was already wrong for a third of the set.

**Do not put stat buffs here, and be careful about why.** Heat, Cold, Blind,
Luck and Empower never tick. They are read at the moment they matter — when an
activation is scheduled, when accuracy is rolled, when damage is totted up.
Spikes and Vampirism are reactive rather than periodic. Of the ten buffs and
debuffs in the game, exactly two tick: Poison and Regeneration.

This is easy to get wrong, because **plenty of items do grant a stat buff on a
timer** — 74 clauses of them. "Burning Coal: After 5s: Gain 2 Heat."
"Broccoli: Every 6s: Gain 2 Luck." "Blood Manipulation: Every 4s: Gain 1
Vampirism." Those are real and common, and not one of them belongs here.

The question that separates the two is **whose clock schedules the tick**:

- `Every 6s: Gain 2 Luck` runs on Broccoli's clock. It sits in the timer heap
  under Broccoli's uid, and `_consume_item` cancels it. That is a `timer`
  trigger holding a `buff` effect, and it is already built.
- Poison runs on the player's clock, off a stack count. Nothing is scheduled
  per item and no item is named in it. Two weapons can both add stacks and the
  total is simply the player's.

The in-battle test is a consumable, because that is the only way an item
leaves the grid once a battle starts — the roster is fixed in the shop phase.
A potion that inflicts poison and then consumes itself takes its timers with
it, and the poison carries on, because it was never the potion's to begin
with.

Nothing here survives the battle either way: `reset_for_battle` clears the
stacks and the clocks, so no over-time effect ever reaches a shop phase.

**The clock belongs to the player, the behaviour to the effect.** `Player`
holds `paid_at` and answers `period_due`, so nothing survives a round that
`reset_for_battle` does not clear. The effect's `pay` routes through
`_take_damage` rather than writing to the quota, so its damage is seen by
everything watching a player's health.

### Do not generalise the tail

A third of Backpack Battles' trigger phrasings belong to one item each. There
is no closed vocabulary to model. Build the core, and let a one-off be a
one-off.

### What is still to place

| Trigger | Uses | Has to know | So it would live in |
|---|---|---|---|
| health threshold | 25 | the health before and after a fall | `_take_damage` |
| shop / out of battle | 49 | the round and the shop | outside the battle loop |
| `After Xs`, once | 37 | the battle clock | the timer heap, not rescheduled |
| resource threshold | 31 | a buff or CPU count crossing a line | wherever that count changes |
| kill / capture | 23 | that a player or unit died | the defeat check |
| `on_attack` | 14 | that an attack was attempted | the attack path, before accuracy |
| `on_miss` | 2 | that the accuracy roll failed | the attack path, on the miss branch |

`on_attack` and `on_miss` are the cheapest: the attack path already knows both,
and it already emits `on_hit` from the branch next door.

## Two ways an effect goes missing

**The loader drops it.** `_parse_effect` returns `None` for a name it does not
know, and `_parse_trigger` does the same. This is the 26 items above. Note the
difference from a *malformed* item: a name the loader has never heard of is
dropped quietly, while an item that uses a known name wrongly now raises
`CatalogueError` and stops the server. Closing this gap means the loader
refusing an unknown name too, which it cannot do until every name in the
catalogue has an implementation.

**A handler ignores it.** An effect can parse and still be skipped by whatever
handles its trigger. The `on_attacked` handler reads `prevent_damage` and
`cpu_drain` and passes anything else to `_apply_effects`, so that one is
covered — but it did not used to be, and `adaptive_mesh_armor` lost its
`adaptive_buff` that way for as long as the code existed.

Neither says anything at startup or in a battle log.
