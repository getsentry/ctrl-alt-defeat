# Sentry Autobattler - Full Stack Integration

## Overview

The Sentry Autobattler is now fully integrated with server-authoritative inventory management. The client (Godot) communicates with the server (Python/FastAPI) for all game state management.

## Quick Start

### 1. Start the Server

```bash
cd server
pip install -r requirements.txt
TEST_MODE=true python main.py
```

Server will run at `http://localhost:8000`
- API docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/`

### 2. Run the Client

```bash
cd client
godot project.godot
```

Or run in editor:
1. Open Godot
2. Import the client project
3. Run the main scene

## Testing

### Run All Tests

```bash
# From project root
./run_integration_tests.sh
```

### Server Tests Only

```bash
cd server
python -m pytest tests/ -v
```

### Integration Tests Only

```bash
# Simple E2E test
python test_e2e.py

# Full integration suite
python server_integration_test.py
```

### Client Tests (requires Godot)

```bash
cd client
godot --headless --script run_integration_tests.gd
```

## Architecture

### Server-Authoritative Design

```
Client (Godot)          Server (FastAPI)
    |                         |
    |-- Start Session ------> | Creates GameSession
    |<-- Player ID, Shop ---- | with inventory
    |                         |
    |-- Purchase Item ------> | Validates placement
    |   (with placement)       | Updates inventory
    |<-- Success/Error ------- |
    |                         |
    |-- Simulate Battle ----> | Uses session inventory
    |   (no inventory!)        | Runs simulation
    |<-- Battle Result ------- | Updates session
```

### Key Changes from Original Design

1. **No Client Inventory Submission**: Battles use server-stored inventory
2. **Placement Validation**: Items must be placed on valid server containers
3. **SimpleBattleRequest**: Only needs player_id and round_number
4. **Container System**: 3 server containers at fixed positions

## API Endpoints

### Session Management

```http
POST /session/start?game_seed=42
GET /session/{player_id}
```

### Shop Operations

```http
POST /shop/refresh
{
  "player_id": "uuid",
  "round": 1
}
```

### Item Management

```http
POST /purchase/item
{
  "player_id": "uuid",
  "item_id": "item-uuid",
  "placement": [2, 3]  // or "storage"
}

POST /sell/item
{
  "player_id": "uuid",
  "item_id": "item-uuid",
  "from_storage": false
}
```

### Battle Simulation

```http
POST /battle/simulate
{
  "player_id": "uuid",
  "round_number": 1,
  "seed": 42,  // Optional (TEST_MODE only)
  "test_ai_difficulty": "easy"  // Optional (TEST_MODE only)
}
```

## Container Positions

Items must be placed on valid server containers:

```
Grid (9x7):
+---+---+---+---+---+---+---+---+---+
|   |   | A | A | B | B | C | C |   |  y=3
+---+---+---+---+---+---+---+---+---+
|   |   | A | A | B | B | C | C |   |  y=4
+---+---+---+---+---+---+---+---+---+
  0   1   2   3   4   5   6   7   8    x

Container A: (2,3) - positions [2,3], [3,3], [2,4], [3,4]
Container B: (4,3) - positions [4,3], [5,3], [4,4], [5,4]
Container C: (6,3) - positions [6,3], [7,3], [6,4], [7,4]
```

## Client Integration (Godot)

### Updated ServerAPI.gd

Key methods:
```gdscript
# Start game with optional seed
func start_new_game(game_seed: int = -1)

# Purchase with placement
func purchase_item(item_id: String, placement)

# Battle without inventory!
func simulate_battle(round_number: int, seed: int = -1, test_ai_difficulty: String = "")

# Sell with item ID
func sell_item(item_id: String, from_storage: bool = false)
```

### Signals

```gdscript
signal game_started(player_id: String, game_state: Dictionary)
signal purchase_complete(success: bool, data: Dictionary)
signal sell_complete(success: bool, data: Dictionary)
signal battle_complete(result: Dictionary)
signal error_occurred(message: String)
```

## Development Workflow

1. **Start server in test mode** for deterministic testing:
   ```bash
   TEST_MODE=true python server/main.py
   ```

2. **Make changes** to client or server

3. **Run tests** to verify:
   ```bash
   python test_e2e.py  # Quick test
   ./run_integration_tests.sh  # Full suite
   ```

4. **Check API docs** at `http://localhost:8000/docs`

## Troubleshooting

### "Invalid placement" errors
- Ensure items are placed on container positions (see grid above)
- Use `ServerAPI.get_valid_container_positions()` helper

### "Empty inventory" battle errors
- Must purchase at least one item to grid before battling
- Items in storage don't count for battles

### Connection errors
- Ensure server is running on port 8000
- Check firewall settings
- Verify `BASE_URL` in client matches server

### Test mode not working
- Set `TEST_MODE=true` environment variable
- Restart server after setting

## Test Coverage

- **Server**: 134 unit tests
- **Integration**: 11 E2E scenarios
- **Client**: 12 integration tests
- **Total**: 150+ automated tests

## Next Steps

- [ ] Add WebSocket support for real-time updates
- [ ] Implement multiplayer battles
- [ ] Add replay system
- [ ] Create tournament mode
- [ ] Add more item types and synergies

## Support

For issues or questions:
1. Check the [Integration Guide](INTEGRATION_GUIDE.md)
2. Review API docs at `/docs` endpoint
3. Check test files for usage examples
4. File an issue on GitHub
