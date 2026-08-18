# Backlog

Things to fix that were not the right thing to fix when found. Add as you
review, tick off as they land. Keep entries to a few lines.

## Open

**Four ways to be holding something, five ways to put it down.** An item picked
up off the grid, out of the chest, off the shop shelf, or handed over after a
container move is four separate states with four sets of code, and they land
through five paths. Anything true of "a held item" has to be written that many
times. Rotation was the first property added since they multiplied and it found
three of them: the shop drag could not be turned, the purchase dropped the
facing, and a turn in place counted as no change. One `Carried` -- the item, its
facing, the visual following the pointer, and where it came from -- would make
each of those one place. Three of the five drops already make the same call.
`client/scripts/unified_grid_ui.gd`, `client/scripts/inventory_grid.gd`

**`move_item` and `purchase_item` take a place that is either a square or the
word "storage".** GDScript cannot say "one of these two", so the parameter is
`Variant` and neither the caller nor the reader is told anything. Two calls
each -- one for a square, one for the chest -- would type it.
`client/scripts/battle_server_api.gd`

**A container cannot be turned, deliberately.** An item can, and the move
carries its facing. Turning a container would have to turn everything standing
on it about its anchor, which is a different problem from the shift that moving
one needs, and only six of the eleven containers would change shape. Written
down so nobody rediscovers it as a missing feature. `client/scripts/inventory_grid.gd`
`turn_dragged`

**The view owns the model in `inventory_grid.gd`.** `items` is a list of
visuals, and the item itself lives in each visual's metadata. So "where is this
item" has five answers — `item_data`, the `grid_pos` meta, the visual's pixel
position, `item_grid`, `active_grid` — and every move has to update all of
them. A container carried an item that had moved off it because one of the five
went stale, and `get_inventory_state` had been quietly compensating for years.
The grid should hold a model and derive the drawing from it, the way the server
does with one list of `PlacedItem`. `client/scripts/inventory_grid.gd`

**Nothing can fake `BattleServerAPI`, so the riskiest handlers have no tests.**
`put_on_grid`, `_on_item_stored`, `_on_container_dropped` and
`_on_chest_item_sold` each have a network call in the middle, so a unit test
cannot run them. These are the paths that put an item back when the server says
no — the ones where a bug costs the player an item. A settable reference
defaulting to the autoload would bring all four under test, and would let
several extractions made only to get a foothold be retired.
`client/scripts/unified_grid_ui.gd`

**The shop refresh price is hardcoded in the client.** The server charges 1
gold for the first four refreshes of a round and 2 from the fifth
(`FREE_PRICE_REFRESHES`), while the button says `Refresh (1g)` in both
`UnifiedGridUI.tscn` and the fallback that builds it in code. `_on_refresh_shop`
also makes no gold check, so it calls the server and takes a 400. The price
should come from the server, as the item colours now do.
`client/scenes/UnifiedGridUI.tscn`, `client/scripts/unified_grid_ui.gd`

**Patches and monitors almost never appear in the shop.** Over 400 rolls at
round one they took 10 and 9 of 1979 slots, against 501 for modules. Containers
are fine at 122. Looks like rarity weighting rather than anything about the
categories. `server/main.py` `generate_shop_items`

**The client ignores `PlacedItem.rotation`.** It is parsed, and
`covered_squares()` in `api_types.gd` does not apply it, so a turned item would
draw and hit-test unturned. Nothing sets a rotation yet, so nothing is broken
today. `client/scripts/api_types.gd`

**`item_looks.py` says there are 20 patterns.** There are 36 since `a2ccd1c`,
which also added `CATEGORY_EXTRA_COLOR` that nothing reads. The module
docstring and `docs/item_placeholder_visuals.md` both still describe the old
list and one colour per category. `server/item_looks.py`,
`docs/item_placeholder_visuals.md`
