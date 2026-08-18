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
Run one file at a time. `-gtest` does not restrict GUT, and the whole suite
pulls in `test/ui/` and `test/integration/`, which need a server running in
TEST_MODE and will otherwise hang or fail:

```
godot --headless --path client -s addons/gut/gut_cmdln.gd \
  -gdir=res://test/unit -ginclude_subdirs=false -gselect=test_api_types.gd -gexit
```

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
