# Backlog

## Bugs

### Container placement is not bounds-checked, and it bricks the run

`/purchase/item` validates a container against **overlap only** (`main.py:1080`
checks `new_squares & existing.covered_squares()`). It never checks that the
container stays on the grid.

`PlacementValidator.add_container` **does** bounds-check
(`containers.py:84-89`), and the battle engine calls it on every battle
(`battle_engine.py:171-178`).

So the two disagree, and the server sells you a placement its own engine will
later refuse.

**What the player sees.** Buy a container whose shape runs off the edge — for
example a 3-wide `memory_cache` anchored at x=8 on a 9-wide grid
(`GRID_SIZE = (9, 7)`, `containers.py:17`), covering x=8,9,10. The purchase
succeeds. Then **every subsequent battle in that run fails**:

```
ValueError: Invalid placement for player 2 items - items overlap or are
            outside containers
```

`ValueError` is not an `HTTPException`, so it escapes as an unhandled 500. The
session cannot recover — the container is already in `server_containers` and
there is no endpoint to remove one. The run is dead and the player cannot tell
why.

It also hits the bots: this was found when a generated build could not fight.

**Fix.** Bounds-check in the container branch of `/purchase/item`, rejecting
with a 400 the way the overlap check does. Reusing `PlacementValidator` there
would be better than a second hand-written check, since a second check is what
caused the disagreement.

**Test.** Buy a multi-square container at the right or bottom edge and assert a
400; then assert a battle still runs.

---

## Found while building the first item effect

*(See `docs/effects.md` for the reasoning behind each. Ordered by how much
they cost.)*

### A seeded shop depends on the order the filesystem lists files in

`load_items` walks `items_dir.glob("*.json")`, and the order it gets back is
whatever the filesystem gives. That order becomes the catalogue's insertion
order, and the shop draws from it, so **the same seed can offer different
items on different machines**.

Found by sorting the glob while fixing something else: five seeded tests
changed their answers immediately, including "seed 0 should produce a buff",
which stopped being true. The sort was reverted because reshuffling every shop
in the game does not belong in an unrelated change.

Section 9.1 promises a deterministic simulation and `test_deterministic_battles`
holds it for battles. The shop has no such guarantee, and this is why.

**Fix.** Sort the catalogue on load and take the one-off shop reshuffle, or
stop the shop depending on insertion order at all — the second is better, and
it means drawing from a sorted list of ids at the point of use rather than
from whatever `dict` iteration hands back.

### Two items sit on a trigger their source does not have

`health_threshold` is right for two of the items using it. Two others were
given a threshold their source never had:

| Ours | Source | What the source actually says |
|---|---|---|
| `healing_nanobots` | Healing Herbs | "**Start of battle**: Gain 2 Regeneration" |
| `backup_system` | Goobert | "**5 Star item activations**: Heal for 9" |

Neither can be fixed yet. Regeneration does not tick, and no trigger counts
activations. They are left healing on a threshold, which is at least
something the engine does, rather than being moved to a trigger that would
silently do nothing.

`auto_rollback` was a third of these and is now right -- Carrot's "Every 2.7s:
Cleanse 1 debuff" -- once the cleanse it was waiting on existed. Its heal,
buff and consume were invented and are gone with the threshold.

### Five catalogue fields still have defaults

Nothing an item supplies should have one. The catalogue is transcribed by hand
from a wiki, and a default cannot be told apart from a transcription that lost
a value -- which is how a shield came to roll 30% for 8 with no CPU drain, how
an on-hit trigger came to have no chance, and how a cleanse came to take
"debuff" without being asked.

Every effect built recently states everything. These older ones do not:

| Field | Unstated on | Silently becomes |
|---|---|---|
| `attack.crit_chance` | 55 effects | 0 |
| `buff.target` | 16 | `self` |
| `heal.min_heal` / `max_heal` | 3 each | 1 |
| `debuff.target` | 1 | `enemy` |

Seventy items in all. `attack.crit_chance` is the one that matters most: 55
weapons are silently non-critting, and the design document gives a 5% base
crit chance in Section 7.2, so the default disagrees with the spec as well as
hiding the omission.

**Fix.** Require them in `_parse_effect`, and write the value into every item.
Mechanical, but it touches most of the catalogue, so it wants to be its own
change with nothing else in it.

Runtime state keeps its defaults. `fired` and `current_cooldown` are the
engine's bookkeeping, not something an item can say.

### `player.buffs` is four different things in one dictionary

Calling a player's core attributes "buffs" is the root of it. `Player.buffs`
currently holds:

| What | Examples | Should be |
|---|---|---|
| Real buffs | `regeneration` | A stacking status, like debuffs |
| A resource | `block` | Its own field. Block absorbs damage a point at a time; it is not a status |
| Core attributes | `accuracy`, `speed`, `cpu_cost`, `attack_speed`, `damage_reduction`, `max_memory`, `compute` | Attributes of the player or its items, modified, not stacked |
| Engine bookkeeping | `reflect` | Not player state at all |

**Only `block` is ever read.** Every other name in that table is written into
the dictionary and consulted by nothing, while logging a `buff` action that
makes it look as though it worked. An item that says "adjacent items act 10%
faster" writes `speed` and changes nothing.

It is also not type-safe: `reflect` is stored as a fraction beside integer
stack counts, so summing the dictionary is meaningless and a cleanse could
remove `0.3` of something.

**Three consequences, all live:**

- **`cleanse: buff` is unsafe.** It picks a kind at random and could strip
  somebody's Block, which is not a buff. Nothing does it today because no item
  removes buffs yet, but the effect allows it.
- **No buff can be named or checked.** `buff_name` is unvalidated, unlike
  `debuff_name`, so a typo is silent. There is no `BUFFS` allowlist to check
  against because nobody has decided what our buffs are.
- **Named buff removal cannot be written.** Six items in the source game want
  it: "Remove 2 Luck", "Remove 1 Spikes and 2 Empower", "Remove 1 Vampirism".

**Fix.** Separate the four. Real buffs become a stacking status set with an
allowlist, the way `DEBUFFS` already works -- Backpack Battles has seven:
Empower, Heat, Luck, Mana, Regeneration, Spikes, Vampirism. Block becomes a
field on the player. Attribute modifiers stop pretending to be statuses and
act on the attribute they name. `reflect` moves out of player state.

Do this with the Section 3.1 entry below, which is the same job seen from the
design document's side: that list has four invented buffs and is missing four
real ones.

### Fifteen more items want a cleanse they do not have

`cleanse` is built, and five items use it. Twenty items in the catalogue have
a source that cleanses, so fifteen are still short one. Each is blocked on
something other than the cleanse itself:

- **A trigger we do not have.** `system_restore` is Divine Potion, "You
  reached 10 debuff: Consume this and cleanse 10 debuffs" -- a count of
  debuffs held, which is a resource threshold. It cleanses at the start of
  battle instead, where there is nothing to remove.
- **A condition we cannot express.** `holy_spear` cleanses "1 debuff for each
  Star free slot"; `shelly` gives cleanses "a 25% chance to cleanse an
  additional debuff", which modifies other items' cleanses.
- **Items not otherwise imported yet**, where the cleanse is one clause of
  several: `burning_coal`, `gold_armor`, `winged_boots`, `snowmaster`,
  `ai_companion_core`, `corrupted_kernel`, `glowing_crown`, the
  recombobulators, the Amethyst modules.

Covered by the per-item audit entry below, and listed here because the effect
they were waiting on now exists.

Two smaller ones, both real:

- **`emergency_patch` still gains Block it should not.** Strong Health Potion
  is "heal for 24, gain 3 **Regeneration** and cleanse 4 Poison". The heal and
  the cleanse are right now; the Block is invented and Regeneration does not
  tick.
- **`emergency_hotfix` is a second Health Potion** on a battle_start trigger,
  where the real one is a health threshold. Two items, one source, one of them
  wrong.

### A health threshold cannot say whether it re-arms

`HealthThresholdTrigger` fires once a battle and never re-arms. Fall to 20%
of a 30% threshold, heal to 40%, fall to 20% again, and it stays quiet.

That is right for some items and wrong for others, and the trigger has no way
to say which it is.

**The evidence that both exist.** `(once)` appears on 13 threshold clauses in
the source game and on **zero** other triggers -- not one timer, on-hit or
start-of-battle effect uses it. So it is a threshold-specific modifier rather
than emphasis, and a modifier has to be modifying something. If thresholds
already fired once a battle, writing `(once)` on 13 items would say nothing.

The reading that makes it meaningful: **crossing the line is the trigger, and
`(once)` pins it to one crossing per battle.**

Tim is the case that needs re-arming. "Opponent drops below 30%: Heal for 50
and gain 5 Empower", with no `(once)` and no consume. It is written as
something that happens when the opponent's health drops past the line, and it
should happen again if they climb back over it and fall a second time.

**Fix.** A field on the trigger -- `once: bool` -- and re-arm when health goes
back above the line unless it is set. The catalogue writes `once: true` for
the items whose text says `(once)`.

**Not urgent.** Every one of our five threshold items carries a
`ConsumeEffect`, so it removes itself the first time and the distinction
cannot be observed. It matters as soon as a non-consuming threshold item is
imported, and Tim would be the first.

Nothing in the wiki states the rule outright; the Discord or Steam forum would
settle it before this is built.

### There is nowhere for "can this item act at all?" to live

Every event handler opens with the same line, because a consumed item has to
stop acting and nothing stops it centrally:

```python
if item.uid in self.consumed_items:
    return
```

Seven of them, across four handlers. Adding a trigger means remembering to
write it again, and forgetting means a potion that drank itself keeps healing.
It is a correctness risk that reads as boilerplate, which is the worst kind.

**Fix: one gate that every trigger passes through**, holding whatever is true
of items in general rather than of any one trigger. A handler would then say
only what makes *it* different.

Consumption is the case that exists today, but it is not the only one coming.
Stun in the source game "pauses all cooldowns for a certain amount of time",
which is the same shape: a condition on the item or its owner that suppresses
everything, checked in one place. `StunEffect` is already defined in
`item_effects.py`, used by no item and handled by nothing.

Unsubscribing on consume would also work and is worth considering —
`_consume_item` already cancels the item's timers, and `EventManager.unsubscribe`
exists with no callers, so the halves are inconsistent today. But it only
answers "consumed". A gate answers the class, and stun would otherwise need
its own seven lines.

Worth doing before the next trigger. Each one added is another copy of the
line, and the gate is where they all go away at once.

### `Effect.apply` does not apply anything

`Effect` is an ABC with an `apply` method, so it looks polymorphic. It is not.
Every `apply` builds a dict of the effect's own fields and returns it, and
`_apply_effects` then runs a nine-branch `isinstance` chain to do the actual
work. Eleven effects build a dict; the engine reads back out of those dicts in
thirty places.

```python
# item_effects.py -- copies its own fields into a dict
def apply(self, source, target, battle_state):
    return {"type": "heal", "min_heal": self.min_heal,
            "max_heal": self.max_heal, "target_type": self.target_type}

# battle_engine.py -- unpacks the dict and does the work
elif isinstance(effect, HealEffect):
    heal = self.rng.randint(result["min_heal"], result["max_heal"])
    owner.quota = min(owner.max_quota, owner.quota + heal)
```

The dict carries nothing the dataclass did not already have. Adding an effect
therefore means editing two files, and the two can disagree.

**It has already caused three bugs in this change.**

- `PreventDamageEffect` had no branch, so it fell out of the chain and did
  nothing. Now guarded twice, at load and at runtime, which is two guards
  standing in for a design that would not have allowed it.
- `CpuDrainEffect` was special-cased inside the shield handler because it was
  easier than adding a tenth branch. It then only worked in a shield, and
  Fanfare's "Every 3s: remove 1 stamina from opponent" would have needed a
  second special case.
- Every effect the loader does not know is dropped silently, which is a
  different symptom of the same thing: no one place owns what an effect is.

**Fix.** Let the effect do the work, exactly as `OverTimeEffect.pay` does in
the same file:

```python
class HealEffect(Effect):
    def apply(self, item, owner, enemy, battle) -> None:
        heal = battle.rng.randint(self.min_heal, self.max_heal)
        battle.heal(owner, heal, source=item.uid)
```

Then `_apply_effects` is a loop, the dicts go, and the runtime guard added
here becomes unnecessary because there is nothing left to forget.

**The one exception is `PreventDamageEffect`**, which cannot apply itself: it
has to hand a number back so a pending attack can be reduced by it. Either
give it its own small protocol, or let `apply` return an optional value that
only the `on_attacked` handler reads.

**Do it with the melee/ranged work below**, since that also needs the shield
path opened up.

### No item has been audited for effects it is simply missing

Two different questions, and only the first has been asked:

1. **Do the effect names in our data have implementations?** Asked. Seven
   trigger types and fourteen effect types do not, costing 26 items something
   — see "26 of 95 items silently do less than they say".
2. **Does each item have all the effects its source item has?** **Never
   asked.** An item can be entirely made of implemented effect types and still
   be missing three of the four things it should do.

Corrupted Kernel, from Corrupted Armor, is the worked example:

| Corrupted Armor | `corrupted_kernel` |
|---|---|
| Star Holy-Items gain Dark | — |
| 10% chance per Dark-item to protect debuffs from cleansing | — |
| Start of battle: Gain **85** Block | Gain **20** Block |
| Every 2.4s: Cleanse 2 debuffs and inflict them on your opponent | — |

Three effects absent and the one we have is wrong by a factor of four. It
passes every check we run, because everything present is well-formed.

`basic_firewall` is the same story: Leather Armor is "Start of battle: Gain 45
Block. Resist 3 debuffs" and ours gains 5 Block and resists nothing.

**Counting will not do it.** A rough comparison of effect counts against the
wiki flagged 10 items — and missed Corrupted Kernel entirely, because that
page uses `*` bullets rather than sentences. So 10 is a floor and not a
number. Nor do the source's clauses map one-to-one onto our effect objects:
"prevent 9 damage, remove 0.3 stamina, and gain 1 Spikes" is one sentence and
three effects.

**Method.** Item by item against the source text, recording for each one
whether every clause is present, absent, or present with the wrong numbers.
96 of our 95 items name a Backpack Battles source, so the list is known. The
output belongs next to `docs/effects.md`, and the parts that are absent
because the effect type does not exist should point at the entry above rather
than being repeated.

Worth doing before any balance work. Right now we do not know what the game
is supposed to do, item by item, so nothing measured against it means much.

### `special` is a stringly-typed side channel, and most of it is dead

`AttackEffect` carries a `special` string that the loader hangs on as a bare
attribute (`effect.special = ...`, the same trick as `effect.hits`). Nothing
validates it and nothing owns it, so it fails silently in both directions:

| `special` | In the catalogue | In the engine |
|---|---|---|
| `stacking` | `core_dumper` | works, but see below |
| `neural_pulse` | `neural_interface_blade` | **no branch** — parses, never read |
| `bypass_block` | **no item** | branch at `battle_engine.py:865`, unreachable |
| `crash` | **no item** | branch at `battle_engine.py:845`, unreachable |

`bypass_block` is also the wrong shape now: it halves `enemy.buffs["block"]`,
the Block resource, while shields are `PreventDamageEffect`. Even if an item
set it, it would not bypass a shield.

`crash` and `bypass_block` both come from the design document — Null Blade's
"On Crit: 20% chance to crash for 15 damage" and SQL Injector's "Bypasses 50%
of shields" — and neither item's JSON sets anything. For Null Blade someone
read the 20% crit chance as the crash chance.

### `stacking` is an on-hit effect, and the commonest one in the game

`special: "stacking"` on `core_dumper` is Axe's "On hit: Gain 1 damage",
written as a magic string because there was no `on_hit` trigger at the time.
There is one now.

It is not a special case. **Twelve** items in the source game gain damage on
hit: Axe (+1), Double Axe (+2), Halberd (+1), Crossblades (+1 and 4% faster),
Torch (25% chance), Burning Torch (30% chance), and six more that spend a buff
to do it.

**Fix.** An ordinary effect behind the trigger we already have:

```json
{ "type": "on_hit", "chance": 1.0,
  "effects": [ {"type": "gain_damage", "value": 1} ] }
```

Three things follow that the magic string gets wrong:

- **The chance is free.** Torch is 25%, Burning Torch 30%. `ChanceTrigger`
  already holds it, so `plasma_edge` — our Torch, currently missing its effect
  altogether — needs no new machinery.
- **The amount stops being fixed at 1.** Double Axe gains 2; the string
  hardcodes `+= 1`.
- **It fixes a live ordering bug.** In `_process_attack` the stack bonus is
  added *after* the crit doubling, so a crit doubles the base damage but not
  the accumulated bonus. Core Dumper at +5 stacks critting on 3-6 deals
  `2*6 + 5 = 17` where it should be `2*11 = 22`. As an on-hit effect the gain
  lands on the weapon before the next swing rolls and the ordering question
  goes away.

**One constraint on the data model.** Katana is "On hit: Remove 1 damage
gained in battle from all opponent Weapons", so the accumulated gain has to
stay a readable quantity of its own rather than being folded into `min_damage`
and `max_damage`. Keep it a field on the item, as `memory_leak_stacks` already
is — just reached through an effect instead of a string.

### Shields block ranged attacks they should not

Every shield in Backpack Battles names the attack types it answers to, and
ours answer to all of them. So a shield rolls against attacks it should
ignore, which makes every shield we have stronger than its source.

It is a property of each shield, not a blanket rule:

| Answers to | Shields |
|---|---|
| `(Melee)` | Wooden Buckler, Hero Shield, Frozen Buckler, Spiked Shield, Heart Shield, Pine Protector, Shield of Valor |
| `(Melee/Ranged)` | Moon Shield, Spiked Wall, Sun Shield |

Both wiki pages agree. The Accuracy page gives the rule, and Wooden Buckler's
prose gives it from the item's side: "When the character is hit by a Melee
attack, it prevents 7 damage and removes 0.3 stamina from the opponent."

**What it costs us now.** All five of our shield sources are in the melee-only
group, so every shield we have should ignore ranged attacks entirely. Eight
weapons in the catalogue are ranged and are being blocked anyway:
`quantum_sniper`, `virus_injector`, `malware_propagator`,
`probability_manipulator`, `quantum_flux_rifle`, `data_leech_swarm`,
`spike_launcher`, `spike_generator`.

**Fix.** `ranged: true` already sits on the attack effect but nothing reads it.
Carry the attack type on the `ON_ATTACKED` event, and give `on_attacked` the
list of types it answers to — a list rather than a flag, so the three
Melee/Ranged shields can be imported without a second mechanism later.

Worth doing with the melee-only buffs, which have the same shape: Spikes
"deals 1 damage per stack when hit with a Melee weapon" and Vampirism "heals
1 health per stack when hitting with a Melee weapon".

### 26 of 95 items silently do less than they say

Seven trigger types and fourteen effect types in the catalogue have no
implementation. The loader returns `None` and the line is dropped without a
word. Full tables in `docs/effects.md`.

The cheapest wins are `on_attack` (2 items) and `on_miss`, which the attack
path already has everything for.

### Items whose import does not match their source

- **`adaptive_mesh_armor`** is modelled as a shield. Leather Armor is not one:
  "Start of battle: Gain 45 Block. Resist 3 debuffs", with no roll at all. It
  also duplicates `basic_firewall`, which has the same source and the right
  shape.
- **`error_monitoring` and `firewall`** are now identical, both being faithful
  imports of Wooden Buckler. One of them has the wrong source recorded.
- **`mobius_lash`** has Chain Whip's numbers and an invented effect. Chain
  Whip is "On hit: Remove 2 random buffs from your opponent", and the 2 was
  read as a stamina drain. Needs a buff economy before it can be right.
- **Effects behind an `on_attacked` roll we cannot express**: Frozen Buckler's
  "inflict 1 Cold (up to 10)", Spiked Shield's "gain 1 Spikes (up to 5)", Hero
  Shield's start-of-battle weapon buff. The structure holds them now; the
  effects do not exist.

### Section 3.1's buff list has invented entries

Section 3.2 was cut to the three debuffs the game actually has. The buffs need
the same pass. Backpack Battles has seven — Empower, Heat, Luck, Mana,
Regeneration, Spikes, Vampirism. We name three correctly (Optimized,
Monitored, Regenerating) and then four with no counterpart. Luck, Mana, Spikes
and Vampirism are missing from the document but already used in the data:
`spike_generator` grants `energy_spikes`, `vampire_rootkit` does lifesteal,
`quantum_probability_core` comes from Lucky Clover.

### The shop does not mention an item's debuffs

`describe()` in `items.py` reads damage, heal, block and `special_effect` only.
Virus Injector's tooltip says "Deals 4-11 damage every 1.7s (costs 0.7 CPU)"
and never mentions the poison, which is the reason to buy it.

### The API tests share state and fail about one run in six

Not one test but a family. Across many runs the failure lands in a different
place each time, always in one of these four:

- `test_main.py`
- `test_api_slug_responses.py`
- `test_purchase_validation.py`
- `test_game_lifecycle.py`

They pass in isolation and fail in company, so it is shared state rather than
a bad assertion — most likely a session or client that outlives the test that
made it. The other 317 tests pass every run.

Predates the effects work: confirmed by running the four on a clean tree,
where they fail at the same rate.

---

## Also found, lower priority

*(Found while building the bot trainer. Each is real and reproducible; none is
as severe as the one above.)*

- **Rotation is modelled but unreachable.** `Item.placed_at(position, rotation)`
  exists and `BattleSimulator` reads `item.rotation` (`main.py:493`), but no
  endpoint accepts one — `PurchaseRequest` takes `item_id`/`target_position`/
  `to_storage`, `MoveItemRequest` takes `item_id`/`to_location`. So every item
  in the game sits at `Rotation.NONE`. Backpack Battles treats rotation as core,
  and without it packing is close to trivial.

- **`shop_refresh_count` resets only on a win** (`main.py:641`, inside the
  `winner == 1` branch). After a loss the counter carries over, so the shop
  seed for the next round is shifted — the shop a player sees depends on
  whether they won, in a way nothing documents.

- **`find_opponent` requires `battle_won == True`** (`matchmaking.py:125` and
  the raw SQL at `:216`). Losing builds are never offered as opponents, so a
  new player who needs a weak opponent is matched only against builds that won.



- **Sentaur Badge**: `leaf_badge` is currently named "Ranger Badge" with a leaf
  design, but its effect gates Sentaur-class items. Rename it to Sentaur Badge and
  draw it as the (reworked) Sentaur character's emblem once that character exists.
