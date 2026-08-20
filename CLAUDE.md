# CLAUDE.md - Project Rules

## Critical Rules
- **NO version files (v2, v3, etc)** - Use Git
- **NO backup files** - Git handles backups
- **Update Game Design Document FIRST** when changing mechanics
- Edit files in place, never create copies
- Tests should verify the Game Design Document
- **ALWAYS run ALL tests before committing server changes**: `cd server && python -m pytest tests/`

## Test Organization
- **Tests go in files matching the source file name**: Tests for functions in `main.py` go in `test_main.py`, tests for `inventory_manager.py` go in `test_inventory_manager.py`, etc.
- Keep test files focused on testing their corresponding source file

## Commands

### Server Tests
- Run ALL tests: `cd server && python -m pytest tests/`
- Run specific test: `cd server && python -m pytest tests/test_battle_engine.py -v`
- Start server: `cd server && python main.py`

### Client Tests
Everything runs, and the whole lot takes about 17 seconds.

The unit tests need nothing running, and are the ones to use while working:

```
cd client && godot --headless --path . -s addons/gut/gut_cmdln.gd \
  -gdir=res://test/unit -ginclude_subdirs=false -gexit
```

`-ginclude_subdirs=false` is what keeps it to `test/unit/`. Add
`-gselect=test_api_types.gd` for a single file.

`test/ui/` and `test/smoke/` drive the real UI against a real server, so run
them through `client/run_tests.sh`, which starts one in TEST_MODE first. Run
them before anything that touches a screen: they are the only tests that would
notice a scene that no longer loads.

| Suite | Tests | Needs a server | Time |
|-------|-------|----------------|------|
| `test/unit/` | 625 | no | 17s |
| `test/ui/` | 14 | yes | 100s |
| `test/smoke/` | 8 | yes | <1s |
| `test/integration/` | 0 | - | - |

`test/integration/` holds no tests. Both files in it are helper classes that
extend RefCounted, and GUT skips them with a warning because they are named
`test_*`. Either rename them or make them tests.

### Test Timeouts
**No test may hang the run.** GUT on its own awaits each test method with no
limit, so one test waiting on something that never arrives stops everything,
and the output does not even say which test it was.

`-gtest_timeout=<seconds>` fails a test that takes longer and moves on to the
next one, naming it. 0 waits forever.

It defaults to **10 seconds**, which is generous: the slowest unit test takes a
tenth of a second and the slowest UI test three. `run_tests.sh` raises it to 45,
not because anything there is slow, but so that a test's own wait — which gives
up after 25 and says what it was waiting for — reports before GUT cuts in with
a generic timeout.

This is a **local change to the vendored addon** (`_call_test_bounded` in
`addons/gut/gut.gd`, plus `gut_config.gd` and `cli/gut_cli.gd`, each marked
LOCAL CHANGE) — keep it when upgrading GUT.

GDScript cannot cancel a coroutine, so a test abandoned this way is still
suspended somewhere. Treat a timeout as something to fix, not to live with.

The one hang this cannot catch is a test that never awaits at all — an endless
loop starves the process, timeout included. That one you notice and interrupt.

## Git

**Do not commit or push until you are asked to.** Do the work, stop at a point
that can be reviewed, and say what changed and what is still open. Being asked
to *do* something is not being asked to commit it.

An approval covers the change it was given for and nothing else. If a message
approves a commit and asks for more work, the new work is not covered by it —
that work waits for its own review, even though a commit was just approved.

When you are asked to commit, pull first. Several agents commit to `main` at
once, so pulls collide often. Run this once
per clone — `git config` writes to `.git/config`, so it is not shared and a new
clone will not have it:

```
git config pull.rebase true       # replay local commits, no merge bubble
git config rebase.autostash true  # stash and restore a dirty tree
git config rerere.enabled true    # remember a conflict resolution and reuse it
git config merge.conflictstyle zdiff3
```

`rerere` earns its place here: a rebase replays each commit separately, and the
item JSON files get touched by nearly every commit, so the same conflict can
come up several times in one rebase.

Before pulling, commit or move aside anything untracked. An untracked file
sitting where an incoming commit wants to write blocks the merge outright, and
no pull strategy fixes that.
