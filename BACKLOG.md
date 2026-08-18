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

### The loader swallows a bad item, and takes the rest of the file with it

`load_items` wraps each category file in `except Exception`, logs, and carries
on (`config_loader.py:92`). It aborts **partway** through the file, so items
before the bad one survive and items after it vanish. Half a category going
missing is harder to notice than all of it.

This now matters more than it did. `_parse_trigger` and `_parse_effect` raise
on a missing `chance`, a missing shield number and an unknown debuff name —
good messages that nobody ever sees, while items disappear.

**Fix.** Fail startup. A catalogue the server cannot read is not a state it
should serve from: it sells items that do not exist and runs battles that
cannot be simulated. The alternative is to drop the guards, and then the bad
data ships silently instead.

### `damage_taken` is a health threshold wearing the wrong name

All five items using it set a threshold — `health_potion` 0.5,
`emergency_patch` 0.2, `healing_nanobots` 0.4, `system_restore` 0.3,
`backup_system` 0.3. None uses the bare form, and Backpack Battles has no
on-damage trigger at all. Two bugs follow:

- **It fires while below the line, not on crossing it.** A threshold item with
  no `ConsumeEffect` heals over and over. All five consume themselves, which
  hides it.
- **It depends on every damage source emitting an event.** Poison did not, so
  a Health Potion watched its owner die of poison. Fixed by making poison
  emit, but the next damage source will have the same hole.

**Fix.** Check the threshold in `_take_damage`, comparing the health before
and after, and fire what the fall crossed. Then `damage_taken` can go.

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

`crash` and `bypass_block` both come from the design document — Null blade's
"On Crit: 20% chance to crash for 15 damage" and SQL Injector's "Bypasses 50%
of shields" — and neither item's JSON sets anything. For Null blade someone
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

### Every activation is floored at 1 CPU

`cpu_cost = max(1, trigger.get_cpu_cost() - item.cpu_discount)`
(`battle_engine.py:637`) throws away every fractional cost:

| Item | Declares | Charged |
|---|---|---|
| `deadlock_twins` | 0.0 | 1.0 |
| `sql_injector` | 0.3 | 1.0 |
| `virus_injector` | 0.7 | 1.0 |
| `quantum_sniper` | 0.7 | 1.0 |

Sections 1.2 and 2.3 both insist costs are fractional, and 1.2 describes the
pressure this destroys: "a typical weapon of ours drains 0.5 a second, so two
run level with regeneration and a third has to wait." It also makes Load
Balancer's `cpu_discount` nearly inert, since no discount can take a cost
below 1.

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

### `TestMoveItemAPI` is order-dependent

Two failures in eight runs on a clean tree, a different test each time, always
in `test_main.py`. Never fails in isolation or in a fixed order. Predates this
work.

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

- **`config_loader` swallows a bad data file** (`config_loader.py:92` catches
  `Exception`, logs, and continues). A JSON typo silently removes an entire
  category — `consumables.json` was missing one `[` and the game ran with zero
  consumables, with no error surfaced. Consider failing startup instead.

- **`config_loader` builds its catalogue from a cwd-relative path**
  (`config_loader.py:32`, plus the `load_all()` at module import). Importing it
  from anywhere but `server/` yields an empty catalogue and only a printed
  warning. This makes the server hard to drive from tools and tests.
