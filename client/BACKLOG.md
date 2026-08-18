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

## `player_health` is a counter nothing counts

`GameStateManager.player_health` starts at 100 and is now never changed by
anything. The post-battle screen used to take one off it per loss, and that
screen is gone; the only thing that read it was the game over screen, working
out victory a second way, which now asks the server's flag instead.

A run is decided by `player_lives`. Even when the health was maintained it
could not reach zero, because the run ends after five losses and health only
fell by one each time — so `player_health > 0` was true in every state the game
could reach.

**Fix.** Delete `player_health` and `max_player_health`, and the assertions in
`test/smoke/test_critical_path.gd` that check them. Left in place for now
because that smoke test needs a running server to verify against.

## There are two backlogs at the repo root

`BACKLOG.md` (453 lines, current) and `docs/BACKLOG.md` (53 lines, untouched
since `5a7407a`). The second looks abandoned rather than separate. Someone who
knows which is which should delete one.
