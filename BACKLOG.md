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
