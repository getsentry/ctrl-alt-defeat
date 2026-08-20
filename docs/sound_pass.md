# A sound pass

What the game has, what it wants, and what each one has to do. Written to be
worked through: pick a row, make the sound, hook it where the last column says.

Everything the game plays today was synthesised by `tools/create_sounds.py` —
no samples, no library, pure stdlib arithmetic. That file already holds the
parts a new sound is built from: `voice()` for a stack of sine harmonics,
`noise()` for a knock, `sweep_filter()` for the resonant low-pass that makes a
sound read as a synthesiser rather than an orchestra, `tail()` and `echo()` for
a room, and `write()` to lay it down at a common peak. Adding a sound means
adding a function beside them and a line in `__main__`.

## The rule these are written to

**A sound that plays every few seconds has to be quieter, shorter and duller
than one that plays once a round.** The hit is the model: a busy build lands
several a second, so it is a twentieth of a second of knock at a fifth of the
level of a sting. A cue you notice individually is a cue that will drive
somebody mad by round six. The rows below are ordered by how often they fire,
loudest and longest at the bottom.

Everything cosmetic goes through `Presentation.request()`, which records what
was asked for and answers whether to actually play it. A sound hung off one of
those is automatically silent in a test, where there is no audio driver.

## What exists

| File | Plays when | Where |
|---|---|---|
| `hit.wav` | an item's attack lands | `battle_hud.gd:item_fired` |
| `round_won.wav` / `round_lost.wav` | the round result arrives | `round_result_overlay.gd` |
| `round_won_chime.wav` / `_lost_chime.wav` | — | kept as a plainer fallback |
| `merge_charge.wav` | items rattle and fly together | `unified_grid_ui.gd:_merge_sound` |
| `merge_flash.wav` | they go out in the whiteout | as above |
| `merge_done.wav` | what they became stands up | as above |
| `menu_music.ogg`, `shop_music.ogg`, `battle_music.ogg` | per screen | scene scripts |

## Wanted: the shop, in order of how often it fires

These fire while the player is arranging things, so they are the ones that most
need to be short and quiet. Several already have a visible effect recorded
through `Presentation` that a sound can hang on.

| Sound | Plays when | What it has to do | Hook |
|---|---|---|---|
| `pick_up` | an item is lifted off the rack, the shelf or the chest | 40ms, dry, low. The sound of something leaving a surface, not a click | `inventory_grid.gd:_start_drag`, `unified_grid_ui.gd:hold`, `storage_bin.gd:pick_up` |
| `put_down` | it lands on a square | 60ms, a touch lower than `pick_up` and slightly softer. The pair has to feel like one gesture | `inventory_grid.gd:place_shop_item` |
| `refused` | a drop lands where it cannot go | 80ms, dull, no pitch. It must read as nothing happening rather than as an alarm — the mark under the item is already red | `inventory_grid.gd:mark_square` when `allowed` is false |
| `turn` | an item is turned a quarter | 50ms, a ratchet. It fires on every wheel notch, so it is the quietest thing in the game | `unified_grid_ui.gd:turn` |
| `into_the_chest` | an item lands in the tray | 120ms clatter, and it wants variation: the chest is a physics body, so two items landing together must not be one doubled sound. Pitch it off the impact speed | `storage_bin.gd:_drop_in` |
| `buy` | a purchase goes through | 200ms, coins and a confirmation. It has to feel like spending, and it is the reward for the shop's whole loop | `unified_grid_ui.gd:_on_purchase_completed` |
| `sell` | an item is sold | 200ms, the same family as `buy` played backwards in feel — gold arriving rather than leaving | `unified_grid_ui.gd:_on_item_sold` |
| `reroll` | the shelf is rolled again | 300ms, a shuffle that resolves. Fires at most a few times a round | `unified_grid_ui.gd:_on_refresh_shop` |
| `battle_start` | the player commits | 600ms, a rising machine. This is the door closing on the shop phase | `unified_grid_ui.gd:_on_ready_for_battle` |

## Wanted: the battle

The battle already has `hit.wav` and the two stings. Everything here fires
inside a simulation the player is watching rather than driving, so it is about
reading what happened, not about feedback.

| Sound | Plays when | What it has to do | Hook |
|---|---|---|---|
| `miss` | an attack rolls a miss | 60ms, a whiff with no impact in it. Pitched clear of `hit` so the two are told apart without looking | `battle_hud.gd`, beside `item_fired` |
| `block` | block absorbs damage | 70ms, dead and wooden. Absorbed damage is the absence of an event | `Presentation.request("block_effect")` |
| `heal` | health goes up | 250ms, a soft rise. Rare enough to be pleasant | `Presentation.request("heal_effect")` |
| `critical` | a hit crits | 120ms over the top of `hit`, not instead of it. Layering keeps the rhythm of the fight intact | `battle_hud.gd`, `action == "critical_hit"` |
| `item_fires` | an item comes off cooldown | 30ms tick, almost inaudible on its own. This is the busiest sound in the game by a long way — it may be better as a filter on `hit` than a sound of its own | `Presentation.request("item_activation")` |
| `nightfall` | a battle runs long and the light goes | 1.5s, a drone falling. Once a battle at most | `Presentation.request("nightfall")` |

## Wanted: the frame around it

| Sound | Plays when | What it has to do | Hook |
|---|---|---|---|
| `button` | any button is pressed | 40ms. One sound for every button; a game where each control has its own voice sounds like a toy | `_dress_button` in `unified_grid_ui.gd` |
| `screen_change` | a scene is swapped | 300ms sweep, under the music | the `change_scene_to_file` call sites |
| `game_over` | the run ends | 2s, and it should quote `round_lost.wav` — the last thing a run says ought to rhyme with what it has been saying all along | `game_over_screen.gd` |
| `victory` | the run is won | 2.5s, the same relationship to `round_won.wav` | `game_over_screen.gd` |

## Worth doing before any of it

**Give the sounds a bus and a volume.** Every player today is created ad hoc
with a `volume_db` written into the script that makes it. That is fine for
four sounds and unworkable for twenty-five: there is no way to turn effects
down without editing five files, and no way to duck them under a sting. One
`SFX` bus, one `Music` bus, and the per-sound level becomes a relative trim.

**Decide about repeats.** `battle_hud.gd` already solves this for the hit: four
voices in rotation and a 55ms gate, so several items landing together read as
one blow rather than a burst of identical ticks. Anything that can fire more
than once in a frame — `item_fires`, `into_the_chest`, `block` — needs the same
treatment, and it should be one helper rather than four copies of that logic.
