# Test Infrastructure Documentation

## Overview
The client test infrastructure uses a real server with PostgreSQL database for integration testing. Tests use transaction-based isolation for speed (10x faster than table truncation).

## Requirements
- PostgreSQL must be running
- Server must be started with `TEST_MODE=true`
- Test database: `ctrl_alt_defeat_client_test`

## How It Works

### 1. Test Runner (`run_tests.sh`)
- Starts server on port 8081 with TEST_MODE enabled
- Configures test database: `ctrl_alt_defeat_client_test`
- Runs unit tests then integration tests
- Cleans up server on exit

### 2. Transaction-Based Test Isolation
When TEST_MODE is enabled, the server provides special endpoints:
- `POST /test/start-session` - Starts a database transaction
- `POST /test/end-session/{session_id}` - Rolls back all changes

Each test suite:
1. Starts a test session (creates transaction)
2. Runs all tests within that transaction
3. Ends the session (rolls back changes)

This is 10x faster than truncating tables between tests!

### 3. Test Organization
```
/client/test/
├── unit/              # Unit tests for individual components
│   ├── test_battle_screen.gd
│   ├── test_game_state_manager.gd
│   └── test_inventory_persistence.gd
└── integration/       # Integration tests using real server
    ├── test_ui_driven.gd          # UI-driven integration tests
    └── test_session_manager.gd    # Transaction session helper
```

## Running Tests

### Run All Tests
```bash
cd client
./run_tests.sh
```

### Run Only Unit Tests
```bash
godot --headless --script addons/gut/gut_cmdln.gd -gdir=res://test/unit -gexit
```

### Run Only Integration Tests (requires server)
```bash
# Start server first
TEST_MODE=true python ../server/main.py --port 8081 --db-name ctrl_alt_defeat_client_test

# Then run integration tests
BATTLE_SERVER_URL=http://localhost:8081 godot --headless --script addons/gut/gut_cmdln.gd -gdir=res://test/integration -gexit
```

## Current Test Results

### ✅ Working
- Server connection and session creation
- Shop refresh functionality
- Error reporting with detailed messages
- Transaction-based test isolation (when server supports it)

### ❌ Known Issues
1. **UI Purchase Simulation**: Shop items don't have `_gui_input` handlers, so drag-and-drop can't be simulated
2. **Battle Submission**: Fails with "Cannot battle with empty inventory" because purchases don't work in tests
3. **Server Startup**: May show errors about `use_fallback` attribute but continues running

## Error Messages
The improved error reporting shows:
- HTTP status codes
- Server error details (e.g., "Cannot battle with empty inventory")
- Transaction endpoint availability
- Database connection status

## Best Practices
1. Always verify TEST_MODE is enabled before running integration tests
2. Use transaction sessions for speed - avoid `/test/reset-database`
3. Check error messages for debugging - they now include server details
4. Ensure PostgreSQL is running before starting tests
