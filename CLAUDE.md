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
- Run ALL tests: `cd server && python -m pytest tests/`
- Run specific test: `cd server && python -m pytest tests/test_battle_engine.py -v`
- Start server: `cd server && python main.py`
