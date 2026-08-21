### A container's clauses now run, and two dormant bugs woke with them

Making containers act was the batch's structural change and it made two
things reachable that had never run:

- **Stamina Sack is the only `max_cpu` in the catalogue.** The pool used to be
  filled before an item could resize it, so it gave +1 maximum and left its
  owner a second of regeneration short. Fixed by filling after the handlers.
- **A container's spec was the catalogue's own object**, shared by both
  players and every battle in the process. Nothing broke because no container
  yet carries a trigger that keeps state — `patch_registry` will be the first.
  Fixed by copying it, the way an item's has always been copied.

Worth remembering as a shape: a feature that was never reachable has never
been tested either, and the code around it has been free to rot.

### Red Orchid Collar wants lifesteal on an attack, which nothing has

"Star items steal 3% life for each Luck (up to 50%) and gain 4% critical
chance for each Vampirism." The second half is a scaled aura and is built; the
first is not. Lifesteal exists on effect damage alone -- `EffectDamageEffect`
carries a `lifesteal` share -- and an attack has nowhere to put one. It wants
a modifier stat that `_process_attack` reads and heals by after the damage
lands, which is a different mechanic from the aura that hands it out.

One clause, one item.

### A container can only be reached, never counted, from outside

`contained` is the container's own footprint, so an item asking about "the
items inside" means the container it is written on. Nothing yet lets an item
ask about a *different* container -- "the Potion above it" already goes by the
star zone, but "4 Potions inside consumed" (Patch Registry) wants a trigger
that fires when an item standing on this container is used up, which is a
moment nothing raises.

Two clauses, one item.

### Motherboard's sale chance is round-conditional

"In rounds 1 and 10, sale chance is increased by 20%." `sale_chance_from`
reads the specs a player holds and knows nothing about which round it is, and
`SaleChanceEffect` has no condition. One clause; it is the last thing between
Motherboard and being whole.

### A shop effect that lasts wants session state, not a payout

Gold is paid and gone. A free reroll, a discount, "For the next shop: ..." are
not: they sit there until something spends them, and a benefit that sits there
is a benefit that can be hoarded or farmed.

The shape for those: set it where the shop-entered effects run -- the battle
ending, once a round -- as a field on the session, spend it where it is used,
and clear it when the next battle starts so an unspent one does not carry.

**Nothing needs it yet.** `free_refresh` and `shop_discount` were names in the
unbuilt list and no item ever declared either; they have been removed with the
rest. The two real "Shop refreshes:" clauses want trade offers and a rarity
bump, and a third trigger for a refresh as against an entry, none of which
exists.

### The client suite was never broken

Thirteen failures were reported against it for several commits and put down to
"pre-existing, from the pull". They were a stale Godot import cache in the old
checkout: `godot --headless --import` and the suite is green at 725 with exit
code 0.

Worth remembering how that went unnoticed. The number was stable, so it looked
like a known quantity, and every check compared *against the same broken
baseline* -- which is exactly what a baseline cannot tell you. A suite that
fails the same way every time is not evidence that the failures are real.

The fresh checkout also needed `devenv sync`, and that needed the bare Python
3.14 venv moved out of the way first: it installs into whatever `.venv` is
there, and the project's pinned pydantic-core and greenlet do not build on
3.14. `devenv/config.ini` says 3.11.

### Wolpertinger wants a per-status modifier on the player

"Increase base stamina regeneration by 0.7% for each buff you have." Every
per-status modifier we have changes a number on an *item*; this changes one on
the player, and `PLAYER_MODIFIERS` has no way to scale by what is held.

One clause, so it waits. Worth doing with the next player-modifier work rather
than alone.

### Two clauses stand in `patch` and `script` for Potion and Food

CI Cauldron counts "Star Potions and Diamond Foods", and the catalogue says
`patch` and `script`. Those were the nearest categories at the time, because
the import had scattered Potions across `consumable` and `patch` and Foods
across `consumable` and `script`, and neither had a tag of its own.

They do now: the wiki's `type` field is imported as a kind, so `potion` and
`food` mean what they say. The two clauses can be corrected, and anything else
reaching for a category because a kind was missing is worth the same look --
"Star Weapons" is currently written as the three ways of attacking, where
`weapon` would say it directly.

### On buy needs more than a trigger, so there is no trigger

Two items say it: "On buy: Gain a random effect" and "On Buy: Split into 2
Snowballs". One needs an effect chosen at random and attached to an item; the
other needs an item to become two different items. Neither is a trigger's job.

A trigger for it was written and taken out again. Nothing could call it, and a
trigger nothing fires still appears in the item's description -- it would have
told the player "when you buy this" about something that never happened.

### The shop needs features, not effects

A shop trigger and a gold effect are built, and three items pay out with them.
Most of the rest are not effects at all. Sorted by what they need:

**The shop must be able to make items** (8 clauses). "Dig up a random item",
"Generate a low-quality Gemstone", "Generate items worth 1 Gold", "Consume
Star items. Create different items based on the combined value", "Replace this
with random starting bags and items". Nothing anywhere can put an item into a
player's bag except a purchase.

**The pool must be changeable** (5). "Gemstones are offered in the shop",
"Crafted items are offered", "Ranger items are offered", "Items of all classes
are offered", "Your starting class items are no longer offered". `shop_needs`
gates one item at a time; these open or close whole groups. The gemstone one is
already handled the other way round, by `addshop`, which suggests a shape.

**Trades do not exist** (3). "40% chance for a Trade offer".

**Throwing does not exist** (5). "Can only be thrown once per battle", "Star
Stones above can be thrown repeatedly".

**Rounds are not a thing an item can read** (2). "In rounds 1 and 10, sale
chance is increased by 20%", "Hatches after 2 rounds in your backpack".

**Small and buildable** (4). Treasure-find chance, the rarity of one offer,
gold fees, "Instead of gold, you receive items with a higher value".

Two clauses are not mechanics at all and should come off the lists: "(Rewarded
for starting as a random character.)" and "Value of Star items > 20 Gold",
which is a heading the parser kept.

### Potion spillover is built, and six Potions still owe it

Six of the twelve have it. The other six have no clause that drinks them yet --
their conditions are unbuilt -- so there is nowhere to hang it, and they carry
it on their `unbuilt` lists instead. It was on no list at all before, which is
worse than unbuilt: nothing was owed and nothing was there.

**Whether it chains is still open.** The wiki says "the Potion above it" in the
singular every time, and that is what is built. Its advice on the Potion Belt
page -- "the entire setup should be vertical to make the most of the Potion
spillover" -- reads either way, and a vertical stack of four is exactly the
case the advice is about. Worth settling by playing.

### The wiki's `type` is the tag the catalogue was missing

Food and Potion both looked like they had no equivalent here: the import
scattered Food across `consumable` and `script`, and Potion across `consumable`
and `patch`. Both were solved by the same thing -- the wiki's `type` field,
which was never read.

It is now imported as a kind, so `food`, `potion`, `weapon`, `pet`, `bag`,
`armor`, `shield`, `helmet`, `gloves`, `shoes`, `accessory` and `gemstone` are
all tags an aura can narrow by. No collisions with the kinds already there.

Worth checking what else that field settles. "Star Weapons" is currently
written as the three ways of attacking; `weapon` would say it directly.

# Backlog

## Bugs

### Counting clauses by mechanic does not predict what a mechanic unlocks

Three passes have now been sized this way and all three missed badly:

| Expected | Landed | Why |
|---|---|---|
| chance on an effect: 39 | 8 | the rest also want resist, nullify or a condition |
| five mechanics at once: ~60 | 0 | every one needed a second gap closed too |
| "already buildable": 172 | 22 | counted clauses that mention a built effect, not clauses that can be said |
| seven mechanics at once: ~90 | 14 | the same, and Food has no local tag |

A fourth way of counting missed as well, and it is worth naming because it
looked more careful than the others. Sorting the clauses by *what blocks them*
put 15 under "two sentences in one string", which sounded like a limit of the
translation rather than of the engine. It was neither: every one of the 15 had
a second sentence needing a mechanic, and what the regular expression measured
was punctuation. A blocker you cannot name in words is not a blocker you have
found.

Almost every remaining clause is held up by two or three things at once. A
count per mechanic is an upper bound on what it could ever unlock, never a
forecast of what it will.

**What to do instead.** Pick an item, read its clauses, and build what that
item needs until it is wholly expressible. The counts are still useful for
choosing which item -- `Use N Mana` appears in 22 clauses and 8 of them are
`On attack`, which is already built -- but the unit of work is the item.

Worth knowing when planning: 377 clauses remain, 107 on modules waiting for
sockets, 270 on everything else.

### The corpus is missing the wiki's own "In shop" row

Every item page renders one -- "In shop: Yes", "No", "Box of Riches needed",
"Beastmaster's Subclass item" -- and none of it is in `research/wiki_pages/`.
It is not a parameter anyone types. Template:Item_infobox works it out, so
downloading the wikitext gets everything except the answer.

`parse_wiki.py` now works it out the same way, copied from the template's
source rather than inferred:

1. `subclassname` set                  -> that subclass's item
2. `skillround` set                    -> a round 3 or 10 skill
3. another page's `addshop` names it   -> gated behind that page's item
4. a recipe makes it                   -> No
5. Star of Courage, Sack of Surprises  -> No, by name
6. a Chess Piece                       -> with the Chess Board
7. a Puzzlebag                         -> with a Puzzlebox or Puzzle Badge
8. a Bag belonging to a class          -> No
9. anything else                       -> Yes

**Two guesses were wrong before this, and both mattered.** Rarity plays no
part -- Tim is Unique and sold -- so filing every Unique as treasure hid
items the shop should offer. And the opening sentence is not evidence: Torch's
page says "available in the shop for all classes", it has a recipe, and its
own row says No. Reading the prose put seven items in the shop that the game
does not sell.

The rule is still a copy of a template rather than the template's output.
Capturing the rendered row for all 240 items would end the question; the
Cargo table behind the wiki has 19 columns and this is not one of them,
because it is computed.

### Big Bowl of Treats is a subclass item, and three pets wait behind it

Hedgehog, Rat and Squirrel are gated behind it, and it is the Beastmaster's
subclass item rather than an ordinary one. It is not in the catalogue, so
those three cannot be offered at all -- which is right for now, since offering
them with no gate would be worse.

Importing it means importing subclass items, which is a different job: seven
of them, one per subclass, none of them bought.

### Every Potion has a clause the import missed: spillover

A Potion that is consumed also applies the effect of the Potion above it,
*without consuming that one*. The wiki says it on every Potion page, in the
same words each time -- "as well as applying the effect of the Potion above
it" -- and names it: "potion spillover".

None of the 10 Potions in the catalogue has it, and it is on none of their
`unbuilt` lists either, so it is missing rather than owed. The import took the
clause out of the `effect` field and this sentence is in the prose beside it.

**"The Potion above it" and "its star" are the same square.** Every Potion's
map is `['*', '^', '#']`: it covers two squares, and its star is the one
square directly above, marked `^` so the projection goes straight up in world
space however the item is turned. So this needs no new idea of "above" -- it
is `on: "consumed"` on the star, which the aura triggers already have.

What it needs is a way to say "do what that item does" without consuming it,
which is the same missing piece as "Trigger the Star Pet", "Trigger all Star
Food" and "Repeat the Start of battle effects of the Star items" -- 4 more
clauses. One mechanic, 14 clauses.

**Open:** whether spillover chains. The wiki always says "the Potion above it",
singular, but also advises that "the entire setup should be vertical to make
the most of the Potion spillover", which reads either way. Worth settling
before building, because a vertical stack of four is the case the advice is
about.

The 10: emergency_hotfix, emergency_patch, health_potion, memory_injection,
performance_boost, security_hardening, strong_heroic_potion,
strong_stone_skin_potion, system_restore, vampiric_potion. Potion Belt is a
container and holds them.

### A chain with no end stops quietly, and should not

Two guards keep a battle from running until the stack gives out: a trigger
cannot answer itself, and effects cannot nest past 32. The second one is the
backstop for a pair taking turns, which the first cannot see.

Reaching it means the catalogue describes something with no end, which is a
mistake worth shouting about. It writes a line to the server log and carries
on, because stopping the battle would be worse. But a log line is not where
anyone looks: the right signal is a battle action the client can show, and
that needs a name added to the action enum and the client's processor, which
is a contract change to make deliberately rather than in passing.

Until then, `logger.warning` in `_apply_effects` is the only evidence.

### `_pay` exists because two places spent buffs

A `cost` effect and a `use` trigger each carried their own copy of the four
lines that spend a price. That is the shape that let Vampirism ignore a
healing share -- one road out of two, and the second one forgotten.

Worth looking for the rest of them. `_grant`, `_inflict`, `_heal`,
`_take_damage` and `_pay` are the roads that exist; anything writing to
`buffs`, `debuffs`, `quota`, `block` or `cpu` outside them is a road nobody
declared.

### `should_activate` is unread on half the triggers

The engine asks it for the four triggers where it does real work -- a chance
roll, a health threshold -- and subscribes the rest by event type, where the
event has already been decided before anything runs. So AuraTrigger,
StatusChangeTrigger, OnStunTrigger, OutOfStaminaTrigger and OnMissTrigger each
carried a method that read like the rule and was never asked.

A mutation found it: rewriting AuraTrigger's to watch the wrong event broke
nothing at all. They return False with a comment now, which is honest but
leaves the abstract method on the base doing two different jobs. Worth
splitting the base in two -- triggers the engine polls, and triggers that
subscribe -- so the shape says which is which.

### A mutation run that is killed leaves the catalogue mutated

Mutation testing works by breaking a file, running the suite, and putting the
file back. A run that is interrupted -- a timeout, a Ctrl-C -- never reaches
the putting back, and what it leaves behind is a catalogue with a clause
quietly missing.

It happened: a run hit a two-minute limit while testing Quantum Firewall and
left "The same 30% roll also gains 1 Spiked" gone from the item and gone from
`unbuilt`, so nothing was owed and nothing was there. The next mutation of the
same item reported MISSED, which is how it was found -- a missing test looks
exactly like this.

The harness restores on SIGTERM and SIGINT now, and runs one file's suite
rather than all of them so it finishes inside the limit. Worth keeping in mind
for any script that edits tracked files and tidies up afterwards: `git status`
after one is not paranoia.

### `_modify` had no catch-all, and two stats did nothing because of it

`damage_flat` and `max_damage_flat` were added to MODIFIERS so a status could
scale them, and `_per_status` reads whatever stat it is asked for. `_modify`
does not: it is a chain of comparisons and fell off the end silently, so an
aura granting either parsed, settled, and changed no number.

`_apply_effects` has raised on an unhandled effect since that guard caught
three bugs. `_modify` now raises on an unhandled stat for the same reason.
Anywhere else a name is matched against a list of branches wants the same
treatment -- `_cleanse`, and the trigger dispatch in `_setup_item_handlers`.

`damage_reduction` came off MODIFIERS at the same time. A reduction belongs to
whoever takes the damage, which is `damage_taken` in PLAYER_MODIFIERS, and no
item ever declared it.

### A shield rolls before the target's share comes off

The order damage is worked through is now: a shield's prevention, then the
share the target carries, then Block. The share moved in front of Block
because Block absorbs damage and so should absorb the damage that is actually
arriving -- twenty against a quarter off spends fifteen Block, not twenty.

The shield is the part still open. "30% chance to prevent 15 damage" is a flat
subtraction, so it matters a great deal whether it comes before or after a
quarter is taken off: against 20 damage, preventing first leaves 5 and then 3;
sharing first leaves 15 and then nothing. The wiki's Block page says only
"Absorbs 1 damage per stack" and gives no order at all, so this is a choice
and not a reading. Worth settling by testing the game, since several items
carry a shield and a share together -- Stone Helm is one.

### `spawn_companion` is an effect nothing in the source game has

Still in `UNBUILT_EFFECTS`, still invented. Nothing declares it and nothing
ever will. It should go the way the invented debuffs went, along with the
other names on that list that no item uses.

### "(once)" on a health threshold changes nothing today

Every threshold clause in the source game that says "(once)" is written here
with a `limit` of 1 wrapped round it, and that wrapper is currently doing no
work: `HealthThresholdTrigger` already fires on the crossing and never again,
so removing the limit breaks no test. A mutation found it by changing the
allowance to 99 and watching nothing fail.

It is kept rather than dropped because it is what the item says, and because
Section 2.1 records the open question it belongs to: whether a threshold
should re-arm after the player heals back above the line. "(once)" appears on
13 threshold clauses in the source game and on no other kind of trigger, which
suggests the default re-arms. If it ever does, this wrapper is what makes
those 13 behave.

Until then it is a fact recorded, not a mechanic running. Deciding the
re-arming question is what settles it either way.

### A resist chance is rolled per stack, and the wiki does not say so

Reflect is explicitly per stack: "only 1 stack will be reflected per reflect."
Resist's charges are counted the same way, so they are spent per stack here.
Its *chance* is the guess: "You have a 2% chance to resist debuffs for each
Luck" could be one roll for the whole inflict or one per stack, and against a
5-stack Blind those are very different.

Per stack was chosen for consistency with the charges beside it. Nothing in
the wiki settles it.

### Resist cannot yet be a chance that grows with a status

"You have a 2% chance to resist debuffs for each Luck" (Dancing Dragon) and
"15% chance to resist critical hits" / "40% chance to resist stuns" (Cap of
Resilience, Stone Helm) are all resist, and none of them fits what is built.
The first wants a chance sized by a status; the other two want resisting
something that is not a debuff at all.

Six clauses across four items.

### Backpack Battles "Food" has no tag of its own here

10 clauses say "Star Food", "for each Star Pet or Food", "Trigger all Star
Food". Nothing in the catalogue answers to it. The wiki's Food type landed on
two different local categories when the items were imported -- Carrot became a
`consumable` and Banana, Blueberries and Pumpkin became `script`s -- so there
is no filter that means the same thing.

Deciding what Food is here unblocks all 10 at once. It wants either a `food`
kind on the items that are one, or a category the imports agree on.

### `special` on an attack is a hack with no items behind it

`AttackEffect.special` carries "stacking", "crash" and "bypass_block", which
`_process_attack` reads with a chain of string comparisons. No item in the
catalogue sets "stacking"; one test does. "crash" and "bypass_block" are set
by items and do things no effect describes.

Each is a mechanic wearing a string. "stacking" is now `gain_damage` said
badly, and the other two want effects of their own.

### AuraTrigger defaults its catalogue values and repeats a filter

`AuraTrigger` gives `zone`, `counting` and `after` defaults, which is the thing
no other trigger does: a default cannot be told from a transcription that lost
a value. It also carries its own copy of `matches`, which is now the `Counting`
mixin's job -- `ModifyEffect`, `ModifyPerEffect`, `PerCountEffect` and
`GainDamageEffect` all take it from there.

### A limit on a buff is not a limit on a modifier

"Gain 1 Vampirism (up to 5 per battle)" and "Star items trigger 5% faster (up
to 50%)" read alike and are not the same thing. The second is built: a
modifier knows what it has given and stops. The first limits how much of a
buff one item may grant over a battle, which nothing counts.

### Healing has no modifier

"Increase your healing by 4%", "heal 7% more". `MODIFIERS` has five stats and
none of them is healing. Two clauses want it.

### Sockets go last, not first

107 clauses sit on 30 modules and none of them can be built until a module can
be slotted. It is the biggest single number in the backlog and it is the wrong
thing to work on next, because of what those 107 buy: 30 items, none of which
is a core item, and no clause anywhere else is waiting on them. Every other
mechanic gets weapons, armour and pets going.

Do not drop it -- a module with no effect is an item that lies about itself --
but it goes to the bottom of the list, under the effects that finish items
people actually fight with.

### A module does nothing until it is socketed

A module -- Backpack Battles calls them gemstones -- has no effect on its own.
What it does depends on where it is slotted, and the catalogue says so
directly: 75 clauses are headed "Weapon sockets:", "Armor & other sockets:" or
"Backpack:", one item behaving three ways.

So a module's clause must not be translated as an unconditional trigger.
"Start of battle: Gain 12 Block" on Burning Coal would fire wherever the item
sat, including in storage, which is more wrong than not firing at all. Two
were translated that way and put back.

**Leave every `module` clause unbuilt until sockets exist.** 30 items are in
that category and none of them can be right before then.

It is also why Wisp has no aura zone of its own: it lends its effect to an
item that already projects one.

### Names on the unbuilt list that are not mechanics

Four entries are real mechanics under a wrong name, and one is not real at
all. Each wants correcting in the data rather than building:

| Name | What it really is |
|---|---|
| `damage_reduction` | already a valid `modify` stat |
| `enemy_debuff` | `debuff` with `target: enemy` |
| `adjacent_buff` | a `modify` with an aura target, now adjacency is gone |
| `battle_start` as an *effect* | a trigger name written in the effect slot |
| `spawn_companion` | not a mechanic this game has |

Taking a name off the list is part of implementing the feature, in the same
branch. `adjacent_buff` sat there for two commits after `modify` was built,
which is the drift the list exists to prevent.

The module-level list does not record aura-as-trigger, which was missing
until it was built. A mechanic can be absent from both the list and the
engine, so the per-item `unbuilt` clauses are the more reliable queue.

### What the player is told an item does

Two things are called a description and neither is right on its own.

`describe()` in `items.py` generates the item-level one from damage, heal and
block. It knows nothing else, so Virus Injector reads "Deals 4-11 damage every
1.7s" and never mentions the poison that is the reason to buy it, and Legacy
Code gets an empty string because its whole effect is an aura. Every effect
added recently is invisible to it, and so will the next be.

The per-effect descriptions in the catalogue are the better raw material: one
per clause, taken from the item's own text. 56 of 133 effects carry one.

**Fix.** Compose the item description from its effects rather than generating
it from a fixed set of stats, so a new effect type shows up in the shop
without teaching `describe()` about it. Three things to settle first: whether
the server joins them or the client renders a list (a list suits the grid work
better, since it can highlight the aura clause on hover); what to do about the
77 effects with no description; and player-facing names, since "Cleanse 4
memory_leaked" should read "Memory Leaked".

Worth folding into the frontend instructions rather than deciding alone.

### Two guards that cannot be reached

An aura is stopped from reaching or answering the item that projects it. No
shape in the catalogue draws a zone onto its own squares -- the geometry
places them beside the footprint -- so neither guard can fire, and a mutation
removing either passes the whole suite.

Cheap and correct, but untested, and the tests that look like they cover them
do not. Either find a shape that reaches itself, or drop the guards and say in
the comment why they are unnecessary.

### Running the tests from the repo root gives different answers

`cd server && python -m pytest tests/` passes. `python -m pytest server/tests/`
from the root reports failures, because the rootdir resolves differently.
CLAUDE.md documents the working form, so this is a trap rather than a
breakage, but it costs whoever falls into it an hour.

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

### An item sits on a trigger its source does not have

*(Resolved by the item data audit.)* Both now carry their source's data:
`healing_nanobots` gains 2 Regenerating at battle start — correct, though the
buff does not tick yet (see "Five of the seven are still not read" below) —
and `backup_system` is a pet with its activation-counting effect in `unbuilt`.

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

### The buff work that is still open

`player.buffs` now holds only the seven real buffs. Block is an attribute,
`reflect` is gone, and a number that changes an item is a `modify` rather than
a buff. What remains:

**Aura-as-trigger is the half still missing.** Two of the three directions
an aura works are built: what the zone falls on ("Star items trigger 20%
faster", 22 items) and what the zone counts ("Triggers 15% faster for each
Star Food", 37 items). The third is the zone as a cause.

 A zone reaches items two ways.
As a target -- "Start of battle: Star items trigger 20% faster" -- it works
now. As a trigger -- "Star item activates:", "6 Star item activations:" -- it
does not, and 43 items in the source game use that form.

**`contained` reaches nothing.** A container does not know which items sit
inside it, so a modifier scoped to it is dropped rather than applied. Three
items are affected. The pieces exist: `Container.covered_squares()` and the
item's own squares, intersected.

**Superseded, kept for the record:**

**A modifier is declared and never applied.** Ten items carry one, saying
things like "items trigger 10% faster". The effect parses, its stat and scope
are both checked, and a star or diamond scope is checked against the zones the
item actually draws -- but nothing acts on it, because the battle cannot yet
see an aura. `grid_system` reads the zones off the map; `battle_engine` has no
reference to them. Wiring the two together is the job.

**An aura can be a trigger, and that half does not exist.** A zone reaches
items two different ways in the source game, and only one of them is a target:

| | Items | Example |
|---|---|---|
| **Aura as target** | 22 | "Start of battle: Star items trigger 20% faster" |
| **Aura as trigger** | 43 | "Star item activates: ...", "6 Star item activations: ..." |

The first is built: an ordinary trigger fires and the effect names the zone it
lands on, the same way `cleanse` names `self` or `enemy`. Crow's "Every 3s:
Star items trigger 6% faster" is a timer whose effect targets `star`, so no
trigger needs composing with another.

The second cannot be written at all. Something happening *to* an item in the
zone is the cause, which needs an `aura` trigger -- and a counted form, since
several say "6 Star item activations". No item using one is imported yet, so
nothing is broken today, but 43 of them wait on it.

**Checking a name against its source matters more than renaming it.** Three
entries were converted from a wrong effect type to a right one, and two of the
three were legitimising something the source item never had:

| Ours | Source | What the source actually says |
|---|---|---|
| `network_cache` | Ranger Bag | "Items inside gain 10% critical hit chance +3% for each Luck" -- not CPU regen |
| `encryption_layer` | Frozen Buckler | "...prevent 12 damage, remove 0.9 stamina and inflict 1 Cold" -- no damage reduction |

Both invented effects are gone. Frozen Buckler's Cold is now wired, which
gives Throttled its first source in the game. Ranger Bag's real effect needs
`crit_chance` as a modifier stat, which does not exist, and a value that
scales with Luck, which nothing supports.

The lesson for the rest of the list: a name the loader drops is not
necessarily a mechanic to build. It may be an effect the item never had.

**Four modifiers are invented.** *(Resolved by the item data audit.)* All four
now hold their source's wording in `unbuilt` instead of an invented modifier:
`security_hardening` and `performance_boost` wait on their consume triggers,
`ai_companion_core` is a pet, and `querystorm` keeps its swing with its three
effect lines unbuilt. The triggers they wait on -- a Block threshold, running
out of stamina, counting activations -- are still to build.

**One of the seven is still not read.** Credits is spent by items that need
it, and no imported item spends Mana. Nothing structural blocks it.

**`api_token` attacks and declares no weapon kind**, so it counts as neither
melee nor ranged. Spiked and Draining ignore it, and the shields will too once
they answer only to melee. Its `icontype` needs one.

**Superseded:** Optimized and Throttled decide how
fast an item triggers, Calibrated decides accuracy, and Regenerating heals on
poison's clock. What is left:

- **Monitored** (Empower) is "+1 **weapon** damage per stack", so it needs a
  weapon to be distinguishable from anything else.
- **Spiked** and **Draining** fire "when hit with a **Melee** weapon" and
  "when hitting with a Melee weapon", so they need the same thing plus
  melee against ranged.
- **Credits** (Mana) is spent by items that need it, and no such item is
  imported.

The first three all wait on one concept: an item's weapon type. That is the
same concept the shield entry below needs, since every shield in the source
game only rolls against melee.

**Optimized and Throttled have sources now** *(updated by the item data
audit)*. Throttled comes from `encryption_layer`'s proc, `cryogenic_shield`'s
battle start and `cryogenic_cooling_system`'s timer; Optimized only from
`quantum_processor`'s every-8s timer, which is out of the shop until its
start-of-battle effect is built. `ddos_protection_module` carries Pumpkin's
real weapon swing and its "Fatigue starts: gain 10 Heat", now that a
`fatigue_start` trigger exists.

**Spiked and Draining have items now** (`spike_launcher`, `spike_generator`,
`load_balancer_script`; `vampire_rootkit`), though the buffs themselves are
still unread. Monitored is granted only by `quantum_processor`'s timer.

`cache_optimizer` is Credits from Blueberries' "Every 3.5s: Gain 1 Mana",
with the "at least 10 Mana" branch recorded in its `unbuilt`.

### Rotten Die inflicts fatigue only from the backpack

`inflict_fatigue` is built and two items use it: `day_zero` on hit, and
nightfall itself. Rotten Die's "Every 3.9s: Inflict Fatigue damage" is still
in its `unbuilt`, and not for want of the effect — the clause is a *backpack*
effect, one of three the item has depending on where it sits, and the engine
has no idea where an item sits. Its socket clauses are shelved for the same
reason.

That is the blocker worth naming: a socketable item's text is three items'
worth of behaviour under one name, and nothing reads which of the three
applies. Rotten Die is out of the shop until it does.

### A modifier that counts a status cannot be handed to a zone

`modify_per_status` is worth so much per stack of a status and reads the count
when it matters, which is exactly the shape Day Zero's "Star items have +8%
critical hit chance per Fatigue level of your opponent" wants — the level
climbs all battle, so the bonus cannot be settled with the rest of the aura.

It does not fit yet for two reasons. It lands on the item carrying it
(`item.per_status.append`) rather than on the items a zone reaches, so there
is no way to say *Star items*; and `_held` counts stacks out of `buffs` and
`debuffs`, where fatigue does not live — it is a level of its own on `Player`,
because nothing applies or cleanses it.

Both are small. A `target_type` on `ModifyPerStatusEffect`, run through
`_reached_by` the way `ModifyEffect` already is, and one place that answers
"how many of this does the player hold" for statuses and fatigue alike —
`_held` and `_stacks` both want that answer and each work it out themselves
today. The clause stays in Day Zero's `unbuilt` until then.

### Fifteen more items want a cleanse they do not have

`cleanse` is built, and five items use it. Twenty items in the catalogue have
a source that cleanses, so fifteen are still short one. Each is blocked on
something other than the cleanse itself:

- **A trigger we do not have.** `system_restore` is Divine Potion, "You
  reached 10 debuff: Consume this and cleanse 10 debuffs" -- a count of
  debuffs held, which is a resource threshold. The audit moved the whole
  effect to `unbuilt`; it no longer cleanses at battle start.
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

- ~~`emergency_patch` gains Block it should not~~ *(fixed by the audit:
  it now gains 3 Regenerating, and Regenerating ticks)*.
- ~~`emergency_hotfix` is a second Health Potion on a battle_start trigger~~
  *(fixed by the audit: it consumes on the 50% health threshold like its
  source)*.

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

### Two owners for the same client state, and no rule saying which

`GameStateManager.pending` is written from two layers. `battle_server_api.gd`
writes it as it parses a purchase, a sale and a move; `game_state_manager.gd`
writes it itself for a battle. Nothing in either file says which is the rule,
so the next endpoint that answers with `pending` gets whichever its author
happens to read first.

It is also an undeclared side effect. `move_item()` says it returns a
`MoveItemResponse`; it also changes a global, and that is visible neither in
the signature nor in the five signals at the top of the file, which is where
that file otherwise announces what it does.

Neither cheap fix works. A `pending_changed` signal would make the effect
declared -- a real gain -- but the author of the next endpoint still has to
remember to emit it. Moving the writes out to the callers is worse: there are
ten call sites across `unified_grid_ui.gd` and `inventory_grid.gd`, and the
responses are consumed inconsistently -- `_on_inventory_returned` covers two
of the five move and sell paths. That turns one forgettable place into ten.

**What would work** is `GameStateManager` becoming the front door: the screen
asks it to buy, sell or move, it calls the server and records what came back.
One place, and forgetting becomes impossible, because the state is written by
the thing that owns it. That is a refactor of ten call sites in two files and
it is not a combining change, so it wants its own commit.

### Nothing remembers a recipe once it has been discovered

**108 of the 222 items can only be crafted.** They carry a recipe and are
`in_shop: false`, so a shelf never offers one: Build Step, Onion Router, Power
Brick, Cipher Core, Lucky Bitflip and a hundred more. Until combining was built
none of them was reachable at all.

Showing a player what a pair would make before they make it is not wanted --
finding out is the game. But nothing records what they *have* found out either,
so a recipe discovered in round three is gone by the next run, and by the round
after it. A discovered-recipes screen is the missing half of the loop: the arcs
say two items go together, the merge says what they became, and nothing keeps
that anywhere.

Needs a place to keep it (per player, not per session, or it is worth nothing),
and a screen to read it on. The catalogue already carries every recipe, so what
is missing is only which of them this player has seen happen.

### Auras are drawn in the shop but not in a battle

Hovering an item shows the zone it reaches into and which items it is acting on
(GDD 4.3). That is the shop only. During a battle the racks are drawn by
`battle_screen.gd` out of its own `InventoryGrid` instances rather than through
`unified_grid_ui.gd`, so none of the wiring is shared: it would want an aura
overlay per rack and hover detection of its own.

Worth having -- a battle is where a player asks why a build works, and nothing
there can be changed anyway so there is no risk in showing it. It is not a
small change, which is why it is here rather than done.

### The grid frees every child it has whenever it redraws

`InventoryGrid._setup_visual()` frees every child of the grid and rebuilds the
background and the cells. Anything else parented to the grid is destroyed with
them, on every move, purchase and merge. The aura overlay stands beside the
grid rather than inside it for exactly this reason, which is the wrong shape
for something that draws only grid squares.

It should free what it owns rather than everything it can see.

### A full-screen flash with no way to turn it off

Items combining takes the whole screen to white for a third of a second, once
per shop phase. That is well short of a strobe and nothing else in the game
flashes, so it is not urgent -- but there is no setting for it, and there is no
settings screen to put one on. When there is one, `WHITEOUT_PEAK` in
`combining_overlay.gd` is the single number it would drive. Low priority.

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

## From the item data audit (all 222 items surveyed against their Backpack Battles sources)

- **Weapon-pets need engine support.** Five weapons are typed "Weapon, Pet" on
  the wiki (`querystorm`, `denier_of_service`, `data_leech_swarm`, `pop`,
  `stone_golem`). They now carry `"pet": true` in their JSON, but nothing reads
  it yet. Effects like "Triggers 15% faster for each Star Pet or Food" must
  count them as pets when those effects are built.

- ~~11 gem-module tiers are missing~~ *(added, with combining recipes: two of
  a tier make the next, per the wiki's Gemstone page)*. The 11 new modules
  still need drawing briefs and artwork; their placeholder looks are set.

- **Recipes are not imported.** The item JSON holds no recipe data, and the
  Game Design Document's example recipes (5.4) name ingredients that do not
  exist. The wiki pages carry a Recipe infobox (ingredients + cost) for every
  craftable item; an import would map ingredient names to our slugs via each
  item's `source` field.

- **Melee/ranged lives only in `icontype`.** The wiki marks 61 items melee or
  ranged in their `icontype`, which the catalogue carries as a string. Nothing
  parses it into the engine; ranged/melee distinctions ("On attacked (Melee)",
  Spikes' return-damage limits) will need it typed when those effects are
  built.

- **Sentaur idle animation**: a subtle breathing-bob loop for the character
  sprites. Input image and motion prompt are staged in `art_draft/`
  (`sentaur_idle_input.png`, `sentaur_idle_prompt.txt`); free options tried and
  ranked in the session notes (Ludo.ai's idle preset looked most fit). Fallback:
  gpt-image keyframes + Godot tweens. The CRT face is a screen, so expression
  swaps (blink, damage, victory) are cheap stills whenever wanted.
