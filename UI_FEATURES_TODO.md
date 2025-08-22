# UI Features TODO

## 1. Player Name Input & Opponent Display [COMPLETED]

### Current State
- Client hardcodes "Player" as name when starting session (BattleServerAPI.gd line 79)
- Server stores player_name in GameSession model
- Matchmaking system tracks opponent names when using ghost players
- BattleResult doesn't include opponent name/type currently
- GameStateManager has player_name field but defaults to "Player"

### Implementation Steps

#### Client - Add Name Input to Main Menu
**MainMenu.gd & MainMenu.tscn**
- [x] Add LineEdit control for player name input (with placeholder "Enter your name")
- [x] Default to "Player" if empty
- [x] Pass player name to GameStateManager when starting game
- [x] Store in GameStateManager.player_name

#### Client - Use Player Name in Session Start
**BattleServerAPI.gd**
- [x] Modify `start_session()` to accept optional player_name parameter
- [x] Use GameStateManager.player_name or passed parameter

#### Server - Include Opponent Info in Battle Response
**schemas.py**
- [x] Add to BattleResult:
  - opponent_name: str = Field(default="AI Opponent", description="Opponent's name")
  - opponent_type: str = Field(default="ai", description="Type: ai or player_ghost")

**main.py - simulate_battle endpoint**
- [x] Track opponent_name during matchmaking/AI generation
- [x] Include in BattleResult response:
  - For AI: "AI Opponent (Round X)" or difficulty-based names
  - For ghost players: actual player name from matchmaking

#### Client - Display Names in Battle Screen
**BattleScreen.gd**
- [x] Add labels for player and opponent names above inventories
- [x] Get player name from GameStateManager
- [x] Get opponent name from battle result
- [x] Style differently for AI vs ghost players (maybe different colors)

**api_types.gd**
- [x] Add opponent_name and opponent_type to BattleResult class

---

## 2. Comprehensive Hover Tooltips [PENDING]

### Current State
- **ItemVisual.gd** already has tooltip code with `enable_tooltip` flag
- **ShopItem** (from shop endpoints) includes: rarity, cost, min_damage, max_damage, cooldown, cpu_cost, special_effect
- **PlacedItem** (from battle/inventory) only has: id, slug, item_type, name, position, category, shape
- **No standard format** between endpoints - need to enhance all endpoints

### Implementation Steps

#### Backend - Standardize item serialization across ALL endpoints

**Create unified item serialization function (server/main.py)**
- [ ] Create `serialize_item_full()` function that extracts all item details
- [ ] Include: rarity, cost, min_damage, max_damage, cooldown, cpu_cost, special_effect, description

**Update all endpoints to use full serialization:**
- [ ] `serialize_placed_item()` - used in battle responses
- [ ] Inventory grid items in session responses
- [ ] Storage items in session responses
- [ ] Move item responses
- [ ] Purchase responses

#### Update Backend Response Models (server/schemas.py)
- [ ] Enhance `PlacedItem` model to include all fields
- [ ] Ensure consistency across all item representations

#### Client - Update API Types (client/scripts/api_types.gd)
- [ ] Add fields to `InventoryItem`:
  - rarity: String
  - cost: int
  - min_damage: int
  - max_damage: int
  - cooldown: float
  - cpu_cost: int
  - special_effect: String
  - description: String

#### Client - Enhance ItemVisual tooltip (client/scripts/ItemVisual.gd)
- [ ] Update `_show_tooltip()` to display:
  - Name with rarity color
  - Category and Rarity text
  - Shape (mini grid visualization)
  - Cost: "Value: 🪙 X gold"
  - Effects: Build from damage/heal/cooldown/cpu data
    - "⚔️ Damage: X-Y every Zs (📊 CPU: N)"
    - "❤️ Heals: X-Y HP"
    - "🛡️ Blocks: X damage"
  - Description if available

#### Enable tooltips everywhere
- [ ] Set `enable_tooltip = true` in:
  - InventoryGrid items (inventory and battle screens)
  - Shop preview items
  - Storage items

### Affected Endpoints
All these need to return full item data:
- `/session/start` - initial inventory
- `/battle/simulate` - battle inventories
- `/shop/purchase` - purchased item
- `/inventory/move` - moved item
- `/inventory/sell` - sold item (for confirmation)
- `/shop/refresh` - shop items (already complete)

### Benefits
- Consistent data format across all endpoints
- Players can hover any item anywhere to see full details
- No need for separate item info requests
- Better understanding of item mechanics
