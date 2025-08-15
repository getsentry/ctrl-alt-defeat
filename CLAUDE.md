# CLAUDE.md - Project Guidelines and Reminders

## CRITICAL: Version Control Rules

### NEVER CREATE VERSION FILES
- **NO v2, v3, v4 files** - We use Git for version control
- **NO backup files** - Git handles all backups  
- **NO copies of files** - Git tracks all history
- Always edit files in place
- Trust Git to handle versioning

### When Making Changes
- Edit the existing file directly
- Commit changes with clear messages
- Never create `filename_v2.py`, `filename_backup.py`, etc.

## Project-Specific Rules

### File Organization
- Test files should be separate from implementation files
- Use descriptive names without version numbers

### Testing
- Always run tests after making changes
- Create comprehensive tests for new features
- Tests should verify the Game Design Document specifications

### Code Quality
- Follow existing patterns in the codebase
- Don't add comments unless specifically requested
- Keep responses concise and to the point

## Common Commands
- Run tests: `python -m pytest test_battle_engine.py -v`
- Start server: `python main.py`
- Commit changes: Use git commit with descriptive messages

## Remember
- Git tracks everything - no need for manual versioning
- When in doubt, edit in place
- Trust the version control system