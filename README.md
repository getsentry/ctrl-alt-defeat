# Sentry Autobattler

A Backpack Battles-inspired autobattler with Sentry error monitoring theme.

## Project Structure

```
autobattler/
├── client/           # Godot client (UI and game logic)
│   ├── project.godot
│   ├── scenes/       # Game scenes
│   └── scripts/      # GDScript files
├── server/           # Python FastAPI server
│   ├── main.py       # API endpoints
│   ├── battle_engine.py  # Battle simulation
│   └── item_effects.py   # Item definitions
└── docs/             # Game design documentation
```

## Setup

### Prerequisites
- Python 3.10+
- Godot 4.3
- pip

### Server Setup
1. Install Python dependencies:
```bash
cd server
pip install fastapi uvicorn pydantic
```

2. Start the server:
```bash
python main.py
```
The server will run on http://localhost:8000

### Client Setup
1. Open Godot 4.3
2. Import the project from the `client/` directory
3. Open the project

## How to Play

### Game Flow
1. **Start Game**: Click "Start New Game" from the main menu
2. **Shop Phase**:
   - Buy items from the shop (costs gold)
   - Drag items from shop to your inventory grid
   - Arrange items in your 7x9 server rack
   - Items can be dragged to reposition
   - Right-click or Shift+click to sell items (50% value)
3. **Battle Phase**:
   - Click "Start Battle" when ready
   - Watch the automated battle unfold
   - Items activate on timers using CPU cycles
4. **Results**:
   - Win: Continue to next round with more gold
   - Lose: Lose health, continue if health > 0
   - Game Over: When health reaches 0
   - Victory: Win 10 matches

### Controls
- **Left Click**: Select/place items
- **Drag**: Move items in inventory
- **Right Click**: Remove item from grid
- **Shift+Click**: Sell item for gold

### Item Types
- **Problems/Bugs** (Weapons): Deal damage on timers
- **Monitoring** (Shields): Block incoming attacks
- **Infrastructure** (Support): Provide buffs and resources
- **Food**: Healing and regeneration
- **Pets**: Automated helpers
- **Consumables**: One-time use items

## Development

### Running Tests
```bash
cd server
python -m pytest test_battle_engine.py -v
```

### Key Systems
- **InventorySystem**: Drag-and-drop grid inventory management
- **ShopSystem**: Item shop with rarity-based pricing
- **BattleVisualization**: Animated battle playback
- **ServerAPI**: Communication with Python backend

### API Endpoints
- `POST /session/start` - Start new game session
- `POST /shop/refresh` - Get new shop items
- `POST /battle/simulate` - Run battle simulation
- `POST /purchase/item` - Buy item from shop
- `POST /sell/item` - Sell item for gold

## Features

### Implemented
✅ Game session management
✅ Shop system with item generation
✅ Drag-and-drop inventory
✅ Battle simulation
✅ Item rarity system
✅ Health/gold management
✅ Win/loss conditions
✅ Battle visualization

### Planned
- [ ] Multi-square items
- [ ] Item combining/recipes
- [ ] Container items (server racks)
- [ ] Adjacency bonuses
- [ ] Multiplayer matchmaking
- [ ] Leaderboards
- [ ] Save/load games
- [ ] Sound effects
- [ ] Particle effects

## Notes
- Items are managed client-side for responsiveness
- Server validates and simulates battles deterministically
- Battle results include full event timeline for replay
