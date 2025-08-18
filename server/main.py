"""
Sentry Autobattler Server
- Client manages inventory locally
- Server validates and simulates battles deterministically
- Uses battle_engine for combat simulation
"""

import random
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from battle_engine import ITEM_CATALOG, BattleSimulator, PlacedItem
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Sentry Autobattler Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ItemDefinition(BaseModel):
    """Item as sent from client"""

    id: str
    item_type: str  # Key from ITEM_CATALOG
    position: Tuple[int, int]
    container_id: Optional[str] = None  # Which server rack it's in
    tier: int = 1


class InventorySubmission(BaseModel):
    """Full inventory state from client"""

    items: List[ItemDefinition]
    grid_size: int = 7  # 7x9 main server room


class BattleRequest(BaseModel):
    """Request to start a battle"""

    player_id: str
    inventory: InventorySubmission
    round_number: int
    opponent_id: Optional[str] = None  # None = fight AI


class ShopRefreshRequest(BaseModel):
    """Request for new shop items"""

    player_id: str
    round: int


class GameSession(BaseModel):
    """Player's current game session"""

    player_id: str
    round: int = 1
    gold: int = 12  # Start with 12g for round 1
    lives: int = 5  # Player has 5 lives/tries
    wins: int = 0
    losses: int = 0
    last_battle_result: Optional[Dict] = None
    current_shop: List[Optional[Dict]] = []  # Shop can have empty slots


# In-memory storage (replace with Redis/DB for production)
sessions: Dict[str, GameSession] = {}
battle_history: List[Dict] = []


def create_placed_item(item_def: ItemDefinition) -> PlacedItem:
    """Convert client item definition to PlacedItem for battle"""
    if item_def.item_type not in ITEM_CATALOG:
        raise ValueError(f"Unknown item type: {item_def.item_type}")

    item_spec = ITEM_CATALOG[item_def.item_type]

    return PlacedItem(spec=item_spec, position=item_def.position, uid=item_def.id)


@app.post("/session/start")
async def start_session() -> Dict[str, Any]:
    """Start a new game session"""
    player_id = str(uuid.uuid4())

    session = GameSession(
        player_id=player_id,
        round=1,
        gold=12,
        lives=5,
        current_shop=generate_shop_items(1),
    )

    sessions[player_id] = session

    # Create simplified item catalog for client
    item_catalog_simple = {}
    for k, v in ITEM_CATALOG.items():
        min_dmg = 0
        max_dmg = 0
        cooldown = 0
        cpu_cost = 0
        special = ""

        if hasattr(v, "triggers") and v.triggers:
            for trigger in v.triggers:
                if hasattr(trigger, "cooldown"):
                    cooldown = trigger.cooldown
                    cpu_cost = getattr(trigger, "cpu_cost", 0)
                    if hasattr(trigger, "effects"):
                        for effect in trigger.effects:
                            if hasattr(effect, "min_damage"):
                                min_dmg = effect.min_damage
                                max_dmg = effect.max_damage
                            if hasattr(effect, "special"):
                                special = effect.special

        item_catalog_simple[k] = {
            "name": v.name,
            "category": v.category,
            "rarity": v.rarity,
            "min_damage": min_dmg,
            "max_damage": max_dmg,
            "cooldown": cooldown,
            "cpu_cost": cpu_cost,
            "special_effect": special,
        }

    return {
        "player_id": player_id,
        "session": session.dict(),
        "item_catalog": item_catalog_simple,
    }


@app.get("/session/{player_id}")
async def get_session(player_id: str) -> GameSession:
    """Get current session state"""
    if player_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    return sessions[player_id]


@app.post("/shop/refresh")
async def refresh_shop(request: ShopRefreshRequest) -> Dict[str, Any]:
    """Get new shop items (costs 1 gold if not free refresh)"""
    if request.player_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[request.player_id]

    # Check if this is a paid refresh
    if len(session.current_shop) > 0:  # Not the first shop of the round
        if session.gold < 1:
            raise HTTPException(status_code=400, detail="Not enough gold")
        session.gold -= 1

    session.current_shop = generate_shop_items(session.round)

    return {"shop": session.current_shop, "gold": session.gold}


def get_shop_cost(rarity: str, tier: int) -> int:
    """Get cost based on rarity and tier"""
    base_costs = {"common": 3, "uncommon": 5, "rare": 8, "epic": 12, "legendary": 20}
    return base_costs.get(rarity, 3) * tier


def get_rarity_weights(round_number: int) -> Dict[str, float]:
    """Get rarity weights based on round number"""
    # Rarity table: Common, Rare, Epic, Legendary, Godly
    rarity_table = {
        1: {"common": 90, "rare": 10, "epic": 0, "legendary": 0, "godly": 0},
        2: {"common": 84, "rare": 15, "epic": 1, "legendary": 0, "godly": 0},
        3: {"common": 75, "rare": 20, "epic": 5, "legendary": 0, "godly": 0},
        4: {"common": 64, "rare": 25, "epic": 10, "legendary": 1, "godly": 0},
        5: {"common": 45, "rare": 35, "epic": 15, "legendary": 5, "godly": 0},
        6: {"common": 29, "rare": 40, "epic": 20, "legendary": 10, "godly": 1},
        7: {"common": 20, "rare": 35, "epic": 25, "legendary": 15, "godly": 5},
        8: {"common": 20, "rare": 30, "epic": 25, "legendary": 15, "godly": 10},
        9: {"common": 20, "rare": 28, "epic": 25, "legendary": 15, "godly": 12},
        10: {"common": 20, "rare": 25, "epic": 25, "legendary": 15, "godly": 15},
        11: {"common": 20, "rare": 23, "epic": 23, "legendary": 17, "godly": 17},
    }

    # Round 12-18 use same weights
    if round_number >= 12:
        return {"common": 20, "rare": 20, "epic": 20, "legendary": 20, "godly": 20}

    return rarity_table.get(round_number, rarity_table[1])


def pick_rarity(weights: Dict[str, float]) -> str:
    """Pick a rarity based on weights"""
    total = sum(weights.values())
    if total == 0:
        return "common"

    roll = random.uniform(0, total)
    cumulative = 0

    for rarity, weight in weights.items():
        cumulative += weight
        if roll <= cumulative:
            return rarity

    return "common"  # Fallback


def generate_shop_items(round_number: int) -> List[Optional[Dict]]:
    """Generate random shop items based on round and rarity"""
    shop_size = 5  # Always 5 slots
    items = []

    # Group items by rarity
    items_by_rarity = {
        "common": [],
        "uncommon": [],
        "rare": [],
        "epic": [],
        "legendary": [],
        "godly": [],
    }
    for item_type, item_spec in ITEM_CATALOG.items():
        rarity = item_spec.rarity.lower()
        # Map uncommon to rare for our table
        if rarity == "uncommon":
            rarity = "rare"
        if rarity in items_by_rarity:
            items_by_rarity[rarity].append((item_type, item_spec))

    # Get rarity weights for this round
    weights = get_rarity_weights(round_number)

    for i in range(shop_size):
        if random.random() < 0.85:  # 85% chance of item (15% empty)
            # Step 1: Pick rarity
            rarity = pick_rarity(weights)

            # Step 2: Pick item from that rarity
            rarity_items = items_by_rarity.get(rarity, [])
            if not rarity_items:
                # Fallback to common if no items of that rarity
                rarity_items = items_by_rarity.get("common", [])

            if rarity_items:
                item_type, item_spec = random.choice(rarity_items)

                # Extract damage values from attack effects if present
                min_dmg = 0
                max_dmg = 0
                cooldown = 0
                cpu_cost = 0
                special = ""

                # Look for timer trigger with attack effect
                if hasattr(item_spec, "triggers") and item_spec.triggers:
                    for trigger in item_spec.triggers:
                        if hasattr(trigger, "cooldown"):
                            cooldown = trigger.cooldown
                            cpu_cost = getattr(trigger, "cpu_cost", 0)
                            if hasattr(trigger, "effects"):
                                for effect in trigger.effects:
                                    if hasattr(effect, "min_damage"):
                                        min_dmg = effect.min_damage
                                        max_dmg = effect.max_damage
                                    if hasattr(effect, "special"):
                                        special = effect.special

                item_info = {
                    "id": str(uuid.uuid4()),
                    "item_type": item_type,
                    "name": item_spec.name,
                    "category": item_spec.category,
                    "rarity": item_spec.rarity,
                    "cost": get_shop_cost(item_spec.rarity, 1),
                    "min_damage": min_dmg,
                    "max_damage": max_dmg,
                    "cooldown": cooldown,
                    "cpu_cost": cpu_cost,
                    "special_effect": special,
                }

                items.append(item_info)
            else:
                items.append(None)
        else:
            items.append(None)

    return items


@app.post("/battle/simulate")
async def simulate_battle(request: BattleRequest) -> Dict[str, Any]:
    """
    Simulate a battle with submitted inventory
    Client sends full inventory state, server simulates and returns replay
    """
    if request.player_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[request.player_id]

    # Validate inventory
    if len(request.inventory.items) == 0:
        raise HTTPException(
            status_code=400, detail="Cannot battle with empty inventory"
        )

    # Convert client items to PlacedItems
    player_items = []
    for item_def in request.inventory.items:
        try:
            placed_item = create_placed_item(item_def)
            # Note: tier is already part of the spec
            player_items.append(placed_item)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    # Generate or fetch opponent
    if request.opponent_id and request.opponent_id in sessions:
        # In real implementation, load opponent's last submitted inventory
        opponent_items = generate_ai_items(request.round_number)
    else:
        opponent_items = generate_ai_items(request.round_number)

    # Simulate battle
    simulator = BattleSimulator()
    battle_result = simulator.simulate_battle(
        player_items,
        opponent_items,
        round_number=request.round_number,
    )

    # Calculate gold reward based on round (same win or lose)
    def get_round_gold(round_num: int) -> int:
        """Get gold per round based on the specification"""
        if round_num == 1:
            return 12  # Starting gold
        elif 2 <= round_num <= 4:
            return 9
        elif 5 <= round_num <= 6:
            return 10
        elif round_num == 7:
            return 11
        elif round_num == 8:
            return 21  # Big boost!
        elif 9 <= round_num <= 10:
            return 12
        elif 11 <= round_num <= 12:
            return 13
        elif 13 <= round_num <= 14:
            return 14
        else:  # Round 15+
            return 15

    if battle_result["winner"] == 1:  # Player won
        session.wins += 1
        session.round += 1  # Advance to next round
        gold_reward = get_round_gold(session.round)  # Gold for new round
    else:
        session.losses += 1
        session.lives -= 1  # Lose a life on defeat
        gold_reward = get_round_gold(session.round)  # Same round gold (no advance)

    session.gold += gold_reward
    session.last_battle_result = battle_result
    session.current_shop = generate_shop_items(session.round)

    # Store battle in history
    battle_record = {
        "id": str(uuid.uuid4()),
        "player_id": request.player_id,
        "opponent_id": request.opponent_id,
        "timestamp": datetime.utcnow().isoformat(),
        "round": request.round_number,
        "result": battle_result,
    }
    battle_history.append(battle_record)

    # Check win/loss conditions
    game_over = session.lives <= 0
    victory = session.round > 10 and battle_result["winner"] == 1  # Won round 10

    return {
        "battle_result": battle_result,
        "session_update": {
            "round": session.round,
            "gold": session.gold,
            "gold_earned": gold_reward,
            "wins": session.wins,
            "losses": session.losses,
            "lives": session.lives,
            "game_over": game_over,
            "victory": victory,
        },
        "new_shop": session.current_shop,
        "battle_id": battle_record["id"],
    }


def get_ghost_player_items(round_number: int) -> List[PlacedItem]:
    """Get predefined ghost player inventory for each round"""

    # Define ghost player inventories for rounds 1-10
    ghost_inventories = {
        1: [  # Very basic
            ("null_pointer", (1, 3)),
        ],
        2: [  # Still easy
            ("null_pointer", (1, 3)),
            ("firewall", (4, 3)),
        ],
        3: [  # Adding defense
            ("null_pointer", (1, 3)),
            ("memory_leak", (2, 3)),
            ("firewall", (4, 3)),
        ],
        4: [  # More items
            ("null_pointer", (1, 3)),
            ("memory_leak", (2, 3)),
            ("firewall", (4, 3)),
            ("health_check", (5, 3)),
        ],
        5: [  # Medium difficulty
            ("null_pointer", (1, 3)),
            ("memory_leak", (2, 3)),
            ("race_condition", (1, 4)),
            ("firewall", (4, 3)),
            ("error_monitoring", (5, 3)),
        ],
        6: [  # Adding infrastructure
            ("null_pointer", (1, 3)),
            ("memory_leak", (2, 3)),
            ("race_condition", (1, 4)),
            ("firewall", (4, 3)),
            ("error_monitoring", (5, 3)),
            ("auto_scaler", (4, 4)),
        ],
        7: [  # Stronger items
            ("null_pointer", (1, 3)),
            ("memory_leak", (2, 3)),
            ("buffer_overflow", (1, 4)),
            ("firewall", (4, 3)),
            ("error_monitoring", (5, 3)),
            ("auto_scaler", (4, 4)),
            ("health_check", (5, 4)),
        ],
        8: [  # Good mix
            ("null_pointer", (1, 3)),
            ("memory_leak", (2, 3)),
            ("buffer_overflow", (1, 4)),
            ("race_condition", (2, 4)),
            ("firewall", (4, 3)),
            ("error_monitoring", (5, 3)),
            ("auto_scaler", (4, 4)),
            ("quantum_processor", (5, 4)),
        ],
        9: [  # Near endgame
            ("null_pointer", (1, 3)),
            ("memory_leak", (2, 3)),
            ("buffer_overflow", (1, 4)),
            ("race_condition", (2, 4)),
            ("firewall", (4, 3)),
            ("error_monitoring", (5, 3)),
            ("auto_scaler", (4, 4)),
            ("quantum_processor", (5, 4)),
            ("load_balancer_module", (3, 3)),
        ],
        10: [  # Final boss
            ("null_pointer", (1, 3)),
            ("memory_leak", (2, 3)),
            ("buffer_overflow", (1, 4)),
            ("race_condition", (2, 4)),
            ("firewall", (4, 3)),
            ("error_monitoring", (5, 3)),
            ("auto_scaler", (4, 4)),
            ("quantum_processor", (5, 4)),
            ("load_balancer_module", (3, 3)),
            ("health_check", (3, 4)),
        ],
    }

    # Get inventory for this round (cap at 10)
    round_items = ghost_inventories.get(min(round_number, 10), ghost_inventories[1])

    items = []
    for item_type, position in round_items:
        if item_type in ITEM_CATALOG:
            item_spec = ITEM_CATALOG[item_type]
            placed_item = PlacedItem(
                spec=item_spec,
                position=position,
                uid=f"ghost_{item_type}_{position[0]}_{position[1]}",
            )
            items.append(placed_item)

    return items


def generate_ai_items(round_number: int) -> List[PlacedItem]:
    """Generate AI opponent items based on round - uses ghost players"""
    return get_ghost_player_items(round_number)


@app.post("/purchase/item")
async def purchase_item(player_id: str, item_id: str) -> Dict[str, Any]:
    """Purchase an item from shop (deduct gold, don't place in inventory)"""
    if player_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[player_id]

    # Find item in shop
    item = None
    for shop_item in session.current_shop:
        if shop_item and shop_item.get("id") == item_id:
            item = shop_item
            break

    if not item:
        raise HTTPException(status_code=404, detail="Item not in shop")

    # Check gold
    cost = item["cost"]
    if session.gold < cost:
        raise HTTPException(status_code=400, detail="Not enough gold")

    # Deduct gold and remove from shop
    session.gold -= cost
    session.current_shop = [
        si if si and si.get("id") != item_id else None for si in session.current_shop
    ]

    return {"success": True, "purchased_item": item, "gold": session.gold}


@app.post("/sell/item")
async def sell_item(player_id: str, value: int) -> Dict[str, Any]:
    """Sell an item for 50% value"""
    if player_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[player_id]

    # Get 50% value rounded down
    gold_gained = value // 2
    session.gold += gold_gained

    return {"success": True, "gold_gained": gold_gained, "gold": session.gold}


@app.get("/leaderboard")
async def get_leaderboard(limit: int = 10) -> List[Dict]:
    """Get top players"""
    leaderboard = []

    for player_id, session in sessions.items():
        leaderboard.append(
            {
                "player_id": player_id,
                "round": session.round,
                "wins": session.wins,
                "losses": session.losses,
                "win_rate": round(
                    session.wins / max(1, session.wins + session.losses) * 100, 1
                ),
                "score": session.wins * 100 + session.round * 10,
            }
        )

    leaderboard.sort(key=lambda x: x["score"], reverse=True)
    return leaderboard[:limit]


@app.get("/battle/history/{player_id}")
async def get_battle_history(player_id: str, limit: int = 10) -> List[Dict]:
    """Get player's recent battles"""
    player_battles = [b for b in battle_history if b["player_id"] == player_id]

    # Sort by timestamp desc and return latest
    player_battles.sort(key=lambda x: x["timestamp"], reverse=True)
    return player_battles[:limit]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
