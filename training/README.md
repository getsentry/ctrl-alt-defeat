# Bot generation

Generates opponent builds for matchmaking: many varied racks, each labelled
with the record it actually earned, so a player at any point in a run can be
given a believable opponent.

**The product is the archive, not the bot.** Training is only the machine that
fills it. Variety and honest labels matter more than peak strength.

## It runs the real game

There is no copy of the rules here. `server_harness.py` calls the server's own
FastAPI handlers as plain Python functions:

- **no HTTP** — a handler is an async function, and `Depends(...)` is only a
  default argument, so passing `current_user=` yourself skips the dependency
  injection entirely
- **no auth** — same reason
- **no Postgres, no disk** — every storage call funnels through one seam,
  `db_manager.get_session()` (`database.py:245`), pointed at
  `sqlite+aiosqlite:///:memory:`
- **nothing in `server/` is modified**

This replaced a hand-copied `rules.py`, which drifted and broke within two days
of a refactor. A copy can only detect divergence; importing the real thing
prevents it.

## Running it

```sh
cd /Users/danfuller/code/ctrlaltdefeat_training

./.venv/bin/python training/train.py --generations 20 --population 24 --runs 8
./.venv/bin/python training/measure.py
```

Training writes `training/archive.db` (the builds) and `training/checkpoints/`
(the ladder). Both are throwaway — delete and re-run.

**After any rebalance, delete `archive.db`, `benchmark.json` and
`checkpoints/`.** They hold racks built from item stats that no longer exist,
so the frozen bar silently moves and old builds become unplayable.

## The files

| File | What it does |
|---|---|
| `server_harness.py` | Runs the real server code in-process. Import this first — it builds the item catalogue under the right working directory |
| `placement.py` | Where an item fits, using the server's own `covered_squares()` |
| `evaluate.py` | What a bot can perceive. Measurements only, never value |
| `bots.py` | `NaiveSpender` (the floor) and `LinearBot` (learned) |
| `run.py` | Plays a run, snapshots each rack as a `Build` |
| `archive.py` | Stores builds by (round, wins, losses); samples opponents; exports |
| `train.py` | Evolution strategy over `LinearBot` genomes |
| `measure.py` | Bot strength against a frozen benchmark; Elo ratings for builds |

## Two traps that cost real time

**Always close the harness.** Use `with Harness() as h:`. aiosqlite runs on a
non-daemon thread, so an undisposed engine means the process finishes all its
work, prints everything, and then hangs at interpreter shutdown forever. It
looks exactly like slow code. `atexit` cannot save you — CPython joins
non-daemon threads before running `atexit` handlers.

**Import `server_harness` before any server module.** `config_loader` is a
singleton built once from a cwd-relative path, so whoever imports it first
decides whether the catalogue is full or empty for the whole process. A
spawned multiprocessing worker inherits `sys.path`, which made this fail in
workers while working in the parent.

## When auras land, do this

Item shapes became irregular at `68e041a` ("Read an item's shape from its map").
Packing is now a real combinatorial problem: 11 of 95 items are
non-rectangular, and items average 2.59 squares instead of ~1.5.

Auras are NOT live yet, so position still barely affects a battle. Measured
right after the shape change:

```
adjacency spread over 127 random arrangements   0.0940   (was 0.0000)
annealing vs not, head to head                   45.8%   tie
```

Arrangement varies now, but only from the two category-matched synergies that
already worked, which is too weak to win battles. **The annealer is correctly
switched off** (`LinearBot.anneal_steps = 0`).

To decide when to switch it on, re-run the flatness check after auras fire:

```sh
python - <<'EOF'
# spread over random arrangements of one rack; see scratchpad t_wake.py
EOF
```

If the adjacency spread rises well above 0.1, set `anneal_steps` to ~60 and
compare with `measure.compare_bots`. Turn it on only if that comparison wins —
each annealing step costs a real `/move` call, so it must earn the round trip.

The same event should wake `placement.repack_via_storage`, which is written and
tested but has never fired: racks still end with zero free squares (9 runs in
10), so there is nowhere to shuffle. It uses storage as scratch space and
becomes useful once wrong-shaped gaps appear.

## Current state, honestly

Training improves against its own pool — mean fitness roughly doubled over 12
generations — but the trained bots do **not** yet beat the naive floor against
the frozen benchmark. That is expected, and the reason is perception, not
search:

**A large share of items are invisible to `evaluate.py`**, because their
effects are `BuffEffect` and `StatModEffect` and it reads neither. The stat
system is still being built, so those sensors are deliberately not written
yet. Until they are, the bot cannot value most of the catalogue, and no amount
of training fixes a sensor that reads zero.

Consequence when reading trained weights: for an invisible item the only
non-zero features are the category one-hots, `cost` and `tiles`, so training
loads weight onto a one-hot. That looks exactly like a strong preference for a
category when it is really a missing measurement. Do not read a category
weight as a balance finding until the sensors are closed.

## Notes for the game, found while building this

- `/purchase/item` does not bounds-check container placement (`main.py:1080`
  checks only overlap), but the battle engine does
  (`containers.py:84`). So the server will sell you a container hanging off
  the grid, and every later battle then fails.
- Rotation is modelled (`Item.placed_at(position, rotation)`) and read by the
  battle engine, but no endpoint accepts one, so every item sits at
  `Rotation.NONE` for bots and players alike.
- `shop_refresh_count` resets only on a win (`main.py:641`), so the shop seed
  shifts after a loss.
- `find_opponent` requires `battle_won == True` (`matchmaking.py:125`), so new
  players never meet a losing build.
- `config_loader` logs and continues when a data file fails to parse
  (`config_loader.py:92`), so a JSON typo silently removes a whole category.
