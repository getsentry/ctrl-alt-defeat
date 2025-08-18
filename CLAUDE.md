# CLAUDE.md - Project Rules

## Critical Rules
- **NO version files (v2, v3, etc)** - Use Git
- **NO backup files** - Git handles backups
- **Update Game Design Document FIRST** when changing mechanics
- Edit files in place, never create copies
- Tests should verify the Game Design Document
- **ALWAYS run ALL tests before committing server changes**: `cd server && python -m pytest tests/`

## Commands
- Run ALL tests: `cd server && python -m pytest tests/`
- Run specific test: `cd server && python -m pytest tests/test_battle_engine.py -v`
- Start server: `cd server && python main.py`

## Test Status
- ✅ 54 tests passing
- ❌ 26 tests failing (need container updates after making placement validation mandatory)
