# Client backlog

Things found while working on the client's screens that were not the right
thing to fix at the time. Add as you find them, delete as they land.

The backlog at the repo root is about the server, the items and the game rules,
and several people write to it at once. Anything that is only about what the
player looks at belongs here instead.

## An item's hit should sound like what the item is made of

There is one hit sound, played when an item's attack lands. What it ought to
key off is how the item *looks* — a blade and a brick should not land the same
way — which is a property no item currently carries. The server would need to
say, or the client would need to infer it from the artwork.

`tools/create_sounds.py` builds the one there is; splitting it is a matter of
calling `hit()` a few times with different numbers and picking between them in
`BattleHud.item_fired`.

## `test_multiple_rounds` fails about one run in five, but only in company

Run on its own it passed eight times out of eight. Run as part of `test/ui/`
it fails roughly one time in five, always the same way:

```
[1] expected to equal [2]:  Round should advance from 1 to 2
```

Passing alone and failing in company means the tests are not isolated from one
another: they share one server and one GameStateManager, and something an
earlier test leaves behind decides this one. The root backlog has the same
complaint about the API tests ("share state and fail about one run in six"), so
it may be one cause with two symptoms.

Worth doing properly rather than by retry. `/test/start-session` exists for
isolation and this suite does not use it between tests.

## There are two backlogs at the repo root

`BACKLOG.md` (453 lines, current) and `docs/BACKLOG.md` (53 lines, untouched
since `5a7407a`). The second looks abandoned rather than separate. Someone who
knows which is which should delete one.

## Selling an item off the grid does nothing

`test/ui/test_ui_driven.gd::test_selling_an_item_pays_the_player` fails, and
has been failing since before the shop was reworked (it fails the same way on
`47da445` with no changes on top). Right-clicking a placed item is meant to
sell it. All three assertions go the wrong way at once:

```
[1] expected to equal [0]:  The sold item leaves the grid
[9] expected to be > than [9]:  Selling should pay the player
[9] expected to equal [11]:  A sale pays half of what the item cost
```

The item stays on the grid and the gold does not move, so the sale is not
reaching the server at all. It is the only failing test in the suite, and it is
about the one way a player gets gold back, so it is worth someone's afternoon.

Start at `InventoryGrid._on_item_input`, which is what the test drives, and
follow the right-click through to `BattleServerAPI.sell_item`.

## The grid marks a square against a preview that has been freed

Every headless run of `test_inventory_grid.gd` prints:

```
SCRIPT ERROR: Invalid assignment of property or key 'visible' with value of
type 'bool' on a base object of type 'previously freed'.
   at: InventoryGrid._end_drag (res://scripts/inventory_grid.gd:562)
```

`_end_drag` sets `hover_preview.visible = false` without asking whether the
preview is still there, and by teardown it is not. `mark_square` guards the
same field with `is_instance_valid` and rebuilds it; `_end_drag` does not.

It is one line, but it is printed on every run, and a run whose output always
has an error in it is a run nobody reads.

## Three of the character stats still have nothing behind them

The panel reads Name, Class, Gold, Health, Stamina, Round, Wins, Tries, in the
order Backpack Battles uses, with a plate for the rank under it. Five of those
rows have a real reading. Three draw a dash, and one of the dashes is only
half a dash:

- **Health.** There is no health figure to show. `player_health` has read 100
  since the post-battle screen was deleted, and the entry above has it down for
  deletion — so the row draws a dash rather than a bar that never moves. It
  becomes a reading if the server ever sends one, and goes if it does not.
- **Stamina usage.** The column beside the Stamina row is held open and draws
  nothing. It needs a reading of how hard a build leans on its pool, which
  nothing computes yet on either side.
- **Rank.** There is no ranking, so the plate says Unranked, which is true of
  everyone. It becomes a real reading the day a ladder exists.

**Stamina is right only until the player buys something.** The pool now reaches
the client, but only stamped on a battle action, so the shop reads the last
battle's `max_cpu` off `GameStateManager.last_battle_events`. That is correct at
the top of every shop phase and wrong the moment a purchase raises the pool —
containers, infrastructure and consumables all have items carrying a `max_cpu`
effect — and it is blank for the whole of round one, before any battle has been
fought.

**Fix.** Put `max_cpu` on what the session and the move responses already send
back. The engine works it out from the placed items at the top of a battle
(`battle_engine.py`, the `max_cpu` effects around line 456); the same sum over
the current inventory is what the shop needs, and it would let the shop say what
the *next* battle will open with rather than what the last one did.

**Class is settled**: there is one kind of player, `Sentaur`, and the panel says
so from a constant. Give it a second class and it needs a session field.

## `test_multiple_rounds` hangs since the post-battle screen was taken out

`test/ui/test_ui_driven.gd::test_multiple_rounds` times out at 45 seconds —
"waiting on something that has not happened" — on `0a6034e` with nothing on top
of it. It passed before that commit.

That commit routes the end of a battle straight to the shop instead of through
`PostBattleScreen`, so the click the test waits for is a click on a screen that
no longer appears. Whatever the test waits on now needs to be whatever the new
route actually reaches.

It is the second of the two red UI tests, alongside the sale above, and both
are about what happens after a battle rather than during one.

## A fighter with many buffs is a wall of chips

The chips beside each fighter are laid out in one run, one per status, and a
build that stacks several at once fills the middle of the battle screen with
them. Nothing is wrong with any one chip; there are simply too many, and the
row they make is the busiest thing on a screen whose subject is two fighters
hitting each other.

The card that explains one of them (`status_tooltip.gd`) came out of the same
question and answers it for a single chip. What is left is the row itself:
what a player sees before they hover anything.

Worth trying, in the order they get cheaper:

- **One chip per status, not per stack** is already how it works -- the count
  is on the chip. So the row grows with the *variety* of a build, and a build
  with eight kinds of buff is rare enough that the row could simply be allowed
  to wrap into two lines rather than run on.
- **Sort them** so the same status is in the same place every battle, and a
  player reads position rather than text.
- **Fold the small ones away**: show the largest few and a "+3" chip that
  explains the rest on hover, the way the card already explains one.
- **Shrink the chips while there are many of them**, so the row keeps its
  width and the cost of a busy build is legibility rather than layout.

`battle_hud.gd` builds the rows in `_build_effects`/`add_effect`, at the two
offsets the block plate left them (196 and 280).

## A battle's history is saved as an untyped dict

`main.py` builds `clean_battle_result` by hand -- six keys picked out of the
engine's result -- and hands it to `save_battle_history(battle_data=...)`,
where `BattleHistoryEntry.battle_data` is `Dict[str, Any]`.

So the one record of what happened in a battle has no shape anyone can check.
A key renamed at one end is a key silently missing at the other, and nothing
fails until something reads it back.

It is six of `BattleResult`'s eleven fields, which is a real thing worth
naming: the racks that fought, the opponent and what kind of opponent they
were are not kept. Give it a model and the hand-built dict goes with it.

## Hovering a merged item shows one of its ingredients' auras

Put an item down where it combines with another, hover the result, and the
aura drawn is one of the items that went into it rather than the item that is
there now.

The rack redraws from what the server answers with, and the combining is
played out on the shop screen -- the rack that fought, then each combining,
then the rack as it is now (GDD 5.3). Somewhere in that the zone is being
drawn from an item that no longer exists, and the ids are the likely culprit:
`_aura_square()` looks a visual up by id, and a combined item has an id of its
own that neither ingredient had.

## A click on an aura should reach whatever is underneath it

An aura is drawn in squares the item does not cover -- the empty corner of an
L, the reach of a spear -- and a click there does nothing at all today.

That is deliberate, and it was the fix for a worse bug: `covers_point()` used
to answer `_has_point()` with false, which let the click fall through to the
container under the item, so aiming at an aura picked up the whole rack. The
note in `item_visual.gd` says "a gap inside an item's box belongs to nothing
and does nothing."

What it should do is reach **what is actually under the pointer** -- an item
standing on that square, or the rack if there is none -- rather than either
picking up the item projecting the aura or doing nothing. The board already
knows: `item_grid[y][x]` says which item holds a square and `active_grid`
says which rack made it usable. So this is a matter of asking the board what
is there rather than letting Godot's own hit-testing decide, which is what
gets it wrong.

The aura markers themselves are already `MOUSE_FILTER_IGNORE`, so they are not
what swallows the click.

## Switching one item for another feels clunky

Measured against the running server: a placement round trip is **10-14ms**.
The server is not what anyone is waiting for.

Swapping is the case that feels worst, and it is not one round trip. Putting an
item down where another stands runs `make_way_for()`, which:

1. sends **one `move_item` per displaced item**, awaited one after another,
2. sends **another call** for the item being placed,
3. calls `load_inventory_state()`, which is `clear_all()` -- every item visual
   on the board freed and built again from nothing,
4. then throws the displaced into the chest and puts the biggest in hand.

So the cheapest swap is two sequential round trips and a full rebuild of the
board. Each trip is ~11ms of server plus Godot's own HTTP overhead and up to a
frame of waiting for the answer to land, and the rebuild is on top.

Three fixes, and the first two carry no risk of the client and the server
disagreeing:

**Redraw the difference, not the board.** `load_inventory_state` frees and
rebuilds every visual, however little changed. It could keep the ones whose
item is unchanged, move the ones that moved, and only create or free the
difference. Pure client work, no protocol change, and it is the part that is
actually slow.

**Ask once.** "Put this here, and put whatever is in the way in the chest" is
one thing the player did and N+1 calls to the server. One endpoint would make
it one round trip, and would also make the whole swap atomic -- today a refusal
half way through leaves some items already moved, which `make_way_for` has to
undo by redrawing whatever the last answer held.

**Then be optimistic, if it is still worth it.** The client already has every
rule needed to predict the answer -- `_can_place_item` mirrors the server's
`can_hold`, and the two are held together by fixtures. So it could place at
once and correct when the answer comes.

The risk is worth naming: optimism makes a client/server disagreement
invisible. Today a divergence shows up immediately as a refused move. Drawn
optimistically it would show up as a flicker, or not at all. Four such
disagreements were found and fixed in one week, so if this is done, the
reconciliation must compare what was predicted against what came back and say
so loudly when they differ, rather than quietly taking the server's answer.

## A potion that has been drunk still looks like a potion

Potions are one shot: drunk once and done for the battle. Nothing on the
battle screen says so, so a player watching cannot tell which of their potions
are spent and which are still to come.

Grey it out for now -- `ItemVisual` already tints with `modulate`, which is how
a container is drawn at CONTAINER_ALPHA. Different artwork for a spent one
would be better and can come later.

What says it happened: the battle log carries the action, and the item is named
by its uid, so the screen already knows which one went. There are 12 potion-
shaped items (11 potions and Packet Bag); `icontype: potion` is what marks
them, and the one-shot rule is theirs rather than every consumable's.

## A new run starts with an empty rack

A player's first shop phase begins with three racks and nothing on them. In
the source game each class starts with a loadout, so the first battle is
something to arrange rather than something to survive.

The wiki calls these **starting class presets** and says every one of them has
at least one Leather Bag in it (`research/wiki_pages/Leather_Bag.wikitext`).
The presets themselves are not on the pages we scraped, so they need looking
up before this can be written down.

There is one class here, `Sentaur`, and the panel says so from a constant --
so a preset is one list, not a table, until a second class exists. It belongs
next to `starting_containers()` in `server/containers.py`, which is where the
three racks a run begins with are already decided.

Document the preset in the Game Design Document before building it: what it
holds is a balance decision, and section 6.3 is where the shape of a run is
set out.

## An item says it grants Regeneration and never says what that is

The item card names a status and stops there. "Start of battle: Gain 2
Regeneration" tells a player who already knows what Regeneration is nothing
they did not know, and tells everyone else nothing at all. The source game
answers the question on the card itself: under the item's own lines it puts one
block per status the item can grant -- icon, name in the status's colour, and
what a single stack does. Garlic carries three of them and is a long card, and
still reads better than a short card that withholds the answer.

**The words are already written and already fetched.** `/catalogue/statuses`
returns ten rules from `describe.every_rule()`, each with `status`, `shown`,
`kind`, `each`, `one`, `many` and `detail`, and `game_state_manager.gd` asks
for them once a run. The line the screenshots show is `each` -- what one stack
is worth. `one`, `many` and `detail` describe a stack that exists on a fighter,
so they belong to the chip, not to an item in a shop.

**The card is already drawn, too, in the wrong place.** `status_tooltip.gd`
with `scenes/StatusTooltip.tscn` says exactly this, and only `battle_hud.gd`
raises it, for the chips beside a fighter. So this is not new drawing; it is
the same block, without the count row and without the total row, hanging off
`item_tooltip.gd`.

**What is missing is knowing which statuses an item can grant.** Nothing walks
the effects. It is a walk worth doing rather than a new field to add, because
the names are already in the tree: every `buff_name` and `debuff_name` inside
`triggers`. Counted across the whole catalogue, the statuses items name and the
statuses the server describes are the same ten, with no spare on either side --
so the walk cannot turn up a name that has no words to show, and no described
status is unreachable.

An unbuilt item is the exception and should show nothing rather than a guess.
Drain Vial's "gain 3 Vampirism" sits in an `unbuilt` line as prose, with no
`buff_name` anywhere, and prose is not something to pattern match against ten
names -- it would find Vampirism in an item that only mentions it.

Pull `ICON_PATH` out while doing this. `res://assets/icons/statuses/%s.png` is
written in `battle_hud.gd` and again in `how_to_play.gd`, and this would be the
third copy.

## Items and racks: what is still kept apart

The grid now keeps one record of what covers each square, lowest first, and a
rack is simply the thing at the bottom of the stack. One press picks up
whatever is on top, so a rack you can see is a rack you can pick up, and the
`PlacedContainer` wrapper is gone -- a rack and an item are both an
`ItemVisual` holding a `PlacedItem`.

What is still doubled, in the order it should go:

**The drag machinery.** `_start_container_drag`, `_end_container_drag`,
`drop_container_at`, `_return_container`, `update_container_preview`,
`can_place_container` and `dragging_container` each mirror an item version.
The real difference is one thing: a rack carries what stands on it, which is
`container_riders`. Fold the pair together and let the riders be empty for an
item -- an item carries nothing, which is the same rule with nothing in it.

**Two lists on the wire.** `InventoryState` sends `inventory_grid` and
`server_containers` separately, and that is the root the rest grows from. The
two models are already identical: `Container` subclasses `PlacedItem` and adds
no field, and the client has no Container class at all. Its own docstring says
it -- "what separates the two is which list a thing is in, not what it is."
One list, with `is_container` saying which offer squares, and the client cannot
drift back into two paths because there is only one list to walk.

**Two move endpoints.** `move_item` and `move_container` on the server, for the
same act. They join once the lists do.
