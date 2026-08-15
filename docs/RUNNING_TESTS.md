# Running the tests

Commands that work, as of 2026-08-14.

## Prerequisites

**Python 3.11** and a virtual environment:

```bash
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -r server/requirements.txt pytest pytest-asyncio
```

**Godot 4.4.1.** The version matters. `client/project.godot` records
`config/features=PackedStringArray("4.4", ...)`. A newer Godot can rewrite that
file and the `.godot` cache. `README.md` says 4.3, which is out of date.

```bash
# macOS: brew gives 4.7.1, which is too new. Use the GitHub build.
curl -fLO https://github.com/godotengine/godot/releases/download/4.4.1-stable/Godot_v4.4.1-stable_macos.universal.zip
unzip Godot_v4.4.1-stable_macos.universal.zip
mv Godot.app /Applications/
xattr -dr com.apple.quarantine /Applications/Godot.app
ln -sf /Applications/Godot.app/Contents/MacOS/Godot /opt/homebrew/bin/godot
godot --version   # must print 4.4.1.stable
```

**PostgreSQL.** Check which ports are free first. On a Sentry dev machine, 5432
and 5433 are usually taken by other containers. Point the tests at your own
database, or they will write to somebody else's.

```bash
docker run -d --name cad-test-pg \
  -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=postgres \
  -p 5434:5432 postgres:16-alpine
```

> `server/tests/conftest.py` defaults `DB_HOST` to `localhost:5432`. Always set
> `DB_HOST` yourself, or the tests can hit a different database.

## Server tests

```bash
cd server
DB_HOST=localhost:5434 \
DB_NAME=ctrl_alt_defeat_server_tests \
DATABASE_URL="postgresql://postgres:postgres@localhost:5434/ctrl_alt_defeat_server_tests" \
TEST_MODE=true \
../.venv/bin/python -m pytest tests/ -q
```

Expected: **216 passed, 0 failed, 2 skipped, in about 20 seconds.**

The suite is deterministic. If you see a failure, it is real.

The API shape work (canonical position format, plus
`tests/test_position_format.py` and `tests/test_position_contract.py`) sits in a
stash, not in the working tree:

```bash
git stash list        # api-shape: position canonicalisation
git stash pop
```

## Client tests

**Do not use `client/run_tests.sh`.** It kills the run after 10 seconds
(`run_tests.sh:131`), so the suite always reports a timeout and a failure. Start
the server yourself and call Godot directly.

```bash
# 1. Start a test server
cd server
TEST_MODE=true ../.venv/bin/python main.py \
  --port 8081 --db-host localhost:5434 --db-name ctrl_alt_defeat_client_test &

# 2. Run one or more test scripts.
#    -gconfig= is needed. Without it, .gutconfig.json adds every directory back
#    and -gtest does not filter.
cd ../client
BATTLE_SERVER_URL="http://localhost:8081" godot --headless \
  --script addons/gut/gut_cmdln.gd \
  -gconfig= \
  -gtest=res://test/unit/test_position_format.gd \
  -gexit -glog=1
```

For the whole suite, add `-ginclude_subdirs` and point at `res://test`:

```bash
BATTLE_SERVER_URL="http://localhost:8081" BATTLE_TEST_SEED=424242 godot --headless \
  --script addons/gut/gut_cmdln.gd \
  -gconfig= -gdir=res://test -ginclude_subdirs -gexit -glog=1
```

Expected: **241 tests, 231 passed, 0 failed, 10 pending, about 8 seconds.**

### Test environment variables

| Variable | Effect |
|---|---|
| `BATTLE_SERVER_URL` | Server the client talks to. Required. |
| `BATTLE_TEST_SEED` | Fixes the game seed, so the shop is the same every run. `424242` gives five non-container items. The server accepts a seed only in `TEST_MODE`. |
| `BATTLE_PLAYBACK_SPEED` | Battle replay speed. Headless already runs at 50x, so set this only to slow a battle down and watch it, for example `BATTLE_PLAYBACK_SPEED=1`. |
| `BATTLE_ANIMATIONS` | Cosmetic tweens, fades and pauses. Headless turns them off. Set to `1` to watch them in a headless run, or `0` to strip them from a normal run. |

Battle replay used to dominate the runtime. The server simulates the whole
battle at once, but the client replays the timeline in real time, so at 1x a
15 second battle costs 15 seconds. Headless detects itself and replays at 50x.

`scripts/Presentation.gd` holds the switch for everything cosmetic: the four
battle effect tweens, the 0.5s pause before playback, the 2s pause before the
post-battle screen, the main menu music fade and the error toast fades. None of
it changes game state, and in a test it only adds time and leaves work running
against nodes about to be freed. `BattleScreen._exit_tree()` also kills its
tracked tweens and stops playback, so leaving the screen mid-battle is safe.

| Script | Result |
|---|---|
| `test_unified_grid_ui.gd` | 21/21 |
| `test_item_tooltip.gd` | 18/18 |
| `test_item_visual.gd` | 16/16 |
| `test_error_manager.gd` | 13/13 |
| `test_game_state_manager.gd` | 12/12 |
| `test_game_over_screen.gd` | 11/11 |
| `test_presentation.gd` | 9/9 |
| `test_ui_driven.gd` | 9/9 |
| `test_post_battle_screen.gd` | 9/10 (1 pending) |
| `test_critical_path.gd` | 7/8 (1 pending) |
| `test_battle_screen.gd` | 24/29 (5 pending) |
| `test_main_menu.gd` | 12/15 (3 pending) |
| `test_inventory_persistence.gd` | 4/4 |
| `test_server_containers.gd` | 4/4 |

The pending tests are not failures. Each one records a feature the tests expect
but the game does not have: no Continue or Settings button on the main menu, no
round number, play, pause or skip control on the battle screen, and no clamping
of `player_health` or `player_lives`.

## The segfault, and the GUT patch

The suite used to segfault at the end of `test_battle_screen.gd`, about half the
time when that file ran on its own. It is fixed, but the fix is a local patch to
a vendored third-party addon, so it needs to be re-applied if GUT is updated.

The cause is in GUT itself, `addons/gut/test.gd`:

```gdscript
func _notification(what):
    if(what == NOTIFICATION_EXIT_TREE):
        _awaiter.queue_free()      # _awaiter starts as null
```

`_awaiter` is declared `var _awaiter = null` and is only assigned once the test
is set up. When GUT removes a test script from the tree, `_propagate_exit_tree`
fires this handler, and calling `queue_free()` on a null or already-freed
reference kills the engine. It shows up as `EXC_BAD_ACCESS,
KERN_INVALID_ADDRESS at 0x68`.

The local patch adds a guard:

```gdscript
        if(is_instance_valid(_awaiter)):
            _awaiter.queue_free()
```

Ten runs of `test_battle_screen.gd` and eight full-suite runs after the patch:
zero crashes. Before it: five crashes in eight.

**Upstream still has the bug.** GUT `main` carries the same unguarded line, and
this project pins 9.4.0 while the latest release is 9.6.1. Upgrading GUT will
overwrite the patch and bring the crash back, so either re-apply it or send it
upstream.

### How the cause was found

Godot's own backtrace was useless: the official macOS build is stripped, with no
DWARF sections and no dSYM, and Godot publishes no debug-symbol build. Its crash
handler falls back to the nearest exported symbol, which produced names like
`EditorSettingsDialog + 9188270` — nine megabytes past a symbol that has nothing
to do with the code.

The macOS crash reports in `~/Library/Logs/DiagnosticReports/Godot-*.ips` are
symbolicated by the OS and were readable. They gave the real stack:

```
Node::remove_child  ->  Node::_propagate_exit_tree  ->  Object::notification
  ->  GDScriptInstance::notification  ->  GDScriptFunction::call  ->  abort
```

That named the mechanism directly: a GDScript notification handler running
during exit-tree propagation. Read those first next time.

## Notes on writing UI tests here

- **Wait for a condition, not a duration.** `_wait_until()`, `_wait_for_scene()`
  and `_wait_for_shop_ready()` in `test_ui_driven.gd` return as soon as the
  state is right. The fixed sleeps they replaced added up to 87 seconds and
  still failed on a busy machine.
- **The shop is random.** Slot 0 is a container whenever the roll produces one,
  and a container cannot be dropped onto another container. Use
  `_first_non_container_shop_item()`. The server also accepts a `seed` on
  `/session/start` in test mode, which would make the shop deterministic.
- **Never free every child of `root`.** It holds the `GameStateManager` and
  `BattleServerAPI` autoloads and the GUT runner. Snapshot the children in
  `before_each` and free only what the test added.
- **Stop battle playback before freeing a BattleScreen.** Its timers and tweens
  otherwise resume on a freed node and take the engine down.

## Stopping a run

A finished run exits on its own, so no kill is needed. If one hangs, use
`pkill -9 -f gut_cmdln`. SIGINT does not stop a hung Godot, and SIGKILL does not
raise the macOS crash reporter.
