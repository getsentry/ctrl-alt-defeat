# Client backlog

Things found while working on the client's screens that were not the right
thing to fix at the time. Add as you find them, delete as they land.

The backlog at the repo root is about the server, the items and the game rules,
and several people write to it at once. Anything that is only about what the
player looks at belongs here instead.

## The stamina bar is decoration

`battle_screen.gd:306` and `:314` invent it:

```gdscript
"stamina": 10.0,
"max_stamina": 10.0,
```

Nothing ever writes to it again. The word `stamina` appears **zero times** in
`api_types.gd` and zero times in `battle_event_processor.gd`, so no field on the
battle result carries it and no event changes it. The bar reads 10/10 for the
whole battle because 10/10 is all it has ever been told.

The number is wrong as well as static. Section 1.2 of the Game Design Document
says the CPU pool is **3 cycles**, regenerating 1 per second. The client shows
10, which is over three times the rule.

The server knows about CPU — `BattleActionName` has `CPU_FAIL` and `CPU_DRAIN`
— but a battle action carries no CPU level, so even replaying every event
cannot reconstruct the curve.

**Fix.** Server side first: put the CPU level on the action, or add a
`cpu`/`max_cpu` pair to the battle result the way health has one. Only then can
the client draw it. Until that lands the honest thing may be to hide the bar
rather than show a number that is made up.

## An item's hit should sound like what the item is made of

There is one hit sound, played when an item's attack lands. What it ought to
key off is how the item *looks* — a blade and a brick should not land the same
way — which is a property no item currently carries. The server would need to
say, or the client would need to infer it from the artwork.

`tools/create_sounds.py` builds the one there is; splitting it is a matter of
calling `hit()` a few times with different numbers and picking between them in
`BattleHud.item_fired`.

## The battle speed button calls a method that does not exist

`battle_screen._on_toggle_speed` cycles `battle_speed_multiplier` 1x → 2x → 3x,
updates its own label, and then does this:

```gdscript
if event_processor and event_processor.is_playing:
    event_processor.set_playback_speed(battle_speed_multiplier)
```

**There is no `set_playback_speed`.** `grep -rn "func set_playback_speed"
client/scripts/` returns nothing. The only place `playback_speed` is ever
assigned is `start_playback(speed)`, which runs once when the battle begins. So
the button changes its own caption and nothing else, which is exactly what a
player sees: it clicks, it reads 2x, the battle runs at the same pace.

**Adding the method is not enough.** The playhead is derived from the wall
clock and the multiplier together:

```gdscript
var current_time = (Time.get_ticks_msec() / 1000.0 - start_time) * playback_speed
```

Change `playback_speed` half way through and all the elapsed time is rescaled
retroactively, so the battle jumps: eight seconds in, switching 1x to 2x snaps
the playhead to sixteen and fires every event in between at once. The change
has to bank the seconds already played at the old speed and restart the clock
from there — keep a `played` total, add to it on each speed change, and measure
new elapsed time from that point.

**There is no pause either.** `stop_playback()` sets `is_playing = false` and
stops processing, but nothing resumes from where it stopped, for the same
reason: `start_time` is the only anchor and it is absolute. The same `played`
total that fixes the speed change is what a pause and resume needs. The clock
plate has room for a pause button beside the speed one.

**Test.** Start playback, advance the clock, change speed, and assert the
playhead moved on from where it was rather than jumping. Then pause, advance
the clock, resume, and assert it did not skip the gap.

## The post-battle screen has nothing left to say

The round result overlay now shows the result over the finished battle: which
way the round went, the wins banked, the tries left. `PostBattleScreen` then
shows the same result again as text, plus the gold earned, and asks for a
second click to reach the shop.

Two screens and two clicks for one round, and the first of them is the one
worth keeping.

**Fix.** Route `_go_to_post_battle` straight to `UnifiedGridUI`, keeping the
game-over branch `PostBattleScreen._on_continue_pressed` currently owns
(`GameStateManager.is_game_over()` → `GameOverScreen`). Gold earned needs
somewhere to go — either onto the round result overlay next to the wins, or
into the shop's header, which already shows the gold total.

`PostBattleScreen` also applies the health loss on the way through
(`set_battle_result` does `GameStateManager.player_health -= health_lost`).
Check whether anything still reads `player_health` before deleting the screen
that maintains it — the run is decided by `player_lives`, and this may be a
second, unused counter.

Delete `PostBattleScreen.tscn`, `post_battle_screen.gd` and
`test_post_battle_screen.gd` with it, and the routing assertions in
`test_battle_screen.gd` that name it.

## There are two backlogs at the repo root

`BACKLOG.md` (453 lines, current) and `docs/BACKLOG.md` (53 lines, untouched
since `5a7407a`). The second looks abandoned rather than separate. Someone who
knows which is which should delete one.
