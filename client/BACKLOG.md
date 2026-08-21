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
