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
    gold: int = 10
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
        player_id=player_id, round=1, gold=10, current_shop=generate_shop_items(1)
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
    """Get new shop items (costs 2 gold if not free refresh)"""
    if request.player_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[request.player_id]

    # Check if this is a paid refresh
    if len(session.current_shop) > 0:  # Not the first shop of the round
        if session.gold < 2:
            raise HTTPException(status_code=400, detail="Not enough gold")
        session.gold -= 2

    session.current_shop = generate_shop_items(session.round)

    return {"shop": session.current_shop, "gold": session.gold}


def get_shop_cost(rarity: str, tier: int) -> int:
    """Get cost based on rarity and tier"""
    base_costs = {"common": 3, "uncommon": 5, "rare": 8, "epic": 12, "legendary": 20}
    return base_costs.get(rarity, 3) * tier


def generate_shop_items(round_number: int) -> List[Optional[Dict]]:
    """Generate random shop items based on round"""
    shop_size = 5  # Always 5 slots
    items = []

    for i in range(shop_size):
        if random.random() < 0.8:  # 80% chance of item
            item_type = random.choice(list(ITEM_CATALOG.keys()))
            item_spec = ITEM_CATALOG[item_type]

            # Tier system removed - all items available at all rounds

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
                "cost": get_shop_cost(item_spec.rarity, 1),  # Tier removed - use base cost
                "min_damage": min_dmg,
                "max_damage": max_dmg,
                "cooldown": cooldown,
                "cpu_cost": cpu_cost,
                "special_effect": special,
            }

            items.append(item_info)
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
        validate_placement=False,  # Skip validation for now
    )

    # Calculate gold reward
    gold_reward = 0
    if battle_result["winner"] == 1:  # Player won
        session.wins += 1
        # Fixed gold per round as per game design doc
        if request.round_number <= 3:
            gold_reward = 12
        elif request.round_number <= 6:
            gold_reward = 14
        elif request.round_number <= 9:
            gold_reward = 16
        elif request.round_number <= 12:
            gold_reward = 18
        else:
            gold_reward = 20
    else:
        session.losses += 1
        # Still get gold even on loss
        gold_reward = gold_reward = (
            12
            if request.round_number <= 3
            else 14
            if request.round_number <= 6
            else 16
            if request.round_number <= 9
            else 18
            if request.round_number <= 12
            else 20
        )

    session.gold += gold_reward
    session.round += 1
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

    return {
        "battle_result": battle_result,
        "session_update": {
            "round": session.round,
            "gold": session.gold,
            "gold_earned": gold_reward,
            "wins": session.wins,
            "losses": session.losses,
        },
        "new_shop": session.current_shop,
        "battle_id": battle_record["id"],
    }


def generate_ai_items(round_number: int) -> List[PlacedItem]:
    """Generate AI opponent items based on round"""
    num_items = min(2 + round_number // 2, 8)
    items = []

    positions_used = set()

    for _ in range(num_items):
        # Find free position in 7x9 grid
        position = None
        for _ in range(20):  # Try up to 20 times
            x, y = random.randint(0, 6), random.randint(0, 8)
            if (x, y) not in positions_used:
                position = (x, y)
                positions_used.add(position)
                break

        if position:
            item_type = random.choice(list(ITEM_CATALOG.keys()))
            item_spec = ITEM_CATALOG[item_type]

            # Tier system removed - all items available at all rounds

            placed_item = PlacedItem(
                spec=item_spec, position=position, uid=str(uuid.uuid4())[:8]
            )

            items.append(placed_item)

    return items


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
