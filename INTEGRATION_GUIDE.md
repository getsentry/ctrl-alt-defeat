# Sentry Autobattler Integration Guide

## Overview

This guide documents the integration between the Python server (FastAPI) and the Godot client, including the updated API endpoints and testing procedures.

## Architecture Changes

### Server-Authoritative Inventory Management

The game now uses a fully server-authoritative inventory system:

1. **Session-Based Inventory**: All inventory is stored in the server's `GameSession`
2. **No Client Inventory Submission**: Battles use inventory from the server session
3. **Container-Based Placement**: Items must be placed on valid server containers

### Key API Changes

#### 1. Battle Simulation - SimpleBattleRequest

**Old Format (Removed):**
```json
{
  "player_id": "uuid",
  "inventory": {
    "items": [...],
    "grid_size": 7
  },
  "round_number": 1
}
```

**New Format:**
```json
{
  "player_id": "uuid",
  "round_number": 1,
  "seed": 42,  // Optional, TEST_MODE only
  "test_ai_difficulty": "easy"  // Optional, TEST_MODE only
}
```

#### 2. Purchase Item - With Placement

```json
{
  "player_id": "uuid",
  "item_id": "item-uuid",
  "placement": [2, 3]  // Or "storage"
}
```

Valid grid positions (on containers):
- Container A (2,3): `[2,3], [3,3], [2,4], [3,4]`
- Container B (4,3): `[4,3], [5,3], [4,4], [5,4]`
- Container C (6,3): `[6,3], [7,3], [6,4], [7,4]`

#### 3. Sell Item - Updated

```json
{
  "player_id": "uuid",
  "item_id": "item-uuid",
  "from_storage": false
}
```

## Running Integration Tests

### Prerequisites

1. **Python 3.8+** with dependencies:
   ```bash
   cd server
   pip install -r requirements.txt
   ```

2. **Godot 4.x** (optional, for client tests)

3. **Enable Test Mode** (for deterministic testing):
   ```bash
   export TEST_MODE=true
   ```

### Running Tests

#### Option 1: Full Integration Suite
```bash
# From project root
./run_integration_tests.sh
```

This runs:
1. Server unit tests (pytest)
2. Integration tests (Python)
3. Client tests (Godot, if available)

#### Option 2: Server Integration Only
```bash
python server_integration_test.py
```

#### Option 3: Manual Testing

1. Start the server:
   ```bash
   cd server
   TEST_MODE=true python main.py
   ```

2. Run client tests (in another terminal):
   ```bash
   cd client
   godot --script tests/test_server_integration.gd
   ```

## Client Implementation Guide

### ServerAPI.gd Updates

The client's `ServerAPI.gd` has been updated with:

1. **New Signals**:
   - `purchase_complete(success: bool, data: Dictionary)`
   - `sell_complete(success: bool, data: Dictionary)`
   - `session_received(session: Dictionary)`

2. **Updated Methods**:
   ```gdscript
   # Purchase with placement
   func purchase_item(item_id: String, placement)

   # Battle without inventory
   func simulate_battle(round_number: int, seed: int = -1, test_ai_difficulty: String = "")

   # Sell with item ID
   func sell_item(item_id: String, from_storage: bool = false)
   ```

3. **Helper Functions**:
   ```gdscript
   func get_valid_container_positions() -> Array
   func is_valid_placement(position: Array) -> bool
   ```

### Game Flow Integration

1. **Starting a Game**:
   ```gdscript
   server_api.start_new_game(42)  # With seed for testing
   await server_api.game_started
   ```

2. **Purchasing Items**:
   ```gdscript
   # To grid
   server_api.purchase_item(item_id, [2, 3])

   # To storage
   server_api.purchase_item(item_id, "storage")
   ```

3. **Starting Battle**:
   ```gdscript
   # No inventory needed!
   server_api.simulate_battle(round_number, seed, "easy")
   await server_api.battle_complete
   ```

## Test Coverage

### Server Tests (134 tests)
- Unit tests for all components
- Battle engine validation
- Inventory management
- Container placement
- Session management

### Integration Tests (11 scenarios)
1. Server connection
2. Session start/get
3. Purchase to grid/storage
4. Invalid placement rejection
5. Shop refresh
6. Item selling
7. Battle with empty inventory (rejection)
8. Battle with items
9. Full round cycle
10. Victory condition
11. Game over condition

### Client Tests
- Real server connection
- API compatibility
- Error handling
- Full game flow

## Common Issues and Solutions

### Issue: "Invalid placement" errors
**Solution**: Ensure items are placed on valid container positions (see valid positions above)

### Issue: "Empty inventory" battle error
**Solution**: Purchase at least one item to the grid before battling

### Issue: Server not accessible
**Solution**: Ensure server is running on `http://localhost:8000`

### Issue: Test mode features not working
**Solution**: Set `TEST_MODE=true` environment variable before starting server

## Development Workflow

1. **Start server in test mode**:
   ```bash
   TEST_MODE=true python server/main.py
   ```

2. **Run integration tests**:
   ```bash
   ./run_integration_tests.sh
   ```

3. **Test client manually**:
   - Open Godot project
   - Run main scene
   - Server will handle all inventory

## API Reference

Full API documentation available at:
- `http://localhost:8000/docs` (Swagger UI)
- `http://localhost:8000/redoc` (ReDoc)

## Migration Checklist

- [x] Update ServerAPI.gd to new format
- [x] Remove inventory submission from battles
- [x] Add placement parameter to purchases
- [x] Update sell endpoint with item_id
- [x] Create integration test suite
- [x] Document all changes
- [x] Add helper functions for valid positions
- [x] Enable TEST_MODE for deterministic testing
