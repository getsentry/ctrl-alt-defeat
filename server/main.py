"""
Sentry Autobattler Server
- Client manages inventory locally
- Server validates and simulates battles deterministically
- Uses battle_engine for combat simulation
"""

import os
import random
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

from battle_engine import ITEM_CATALOG, BattleSimulator, PlacedItem
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from inventory_manager import InventoryManager
from pydantic import BaseModel

# Test mode allows seeds and special AI configurations for testing
TEST_MODE = os.environ.get("TEST_MODE", "false").lower() == "true"

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


class SimpleBattleRequest(BaseModel):
    """Simplified battle request - uses inventory from session"""

    player_id: str
    round_number: int
    opponent_id: Optional[str] = None  # None = fight AI
    seed: Optional[int] = None  # For deterministic testing (TEST_MODE only)
    test_ai_difficulty: Optional[
        str
    ] = None  # "easy", "medium", "hard" (TEST_MODE only)


class BattleRequest(BaseModel):
    """Legacy battle request with inventory (for backward compatibility)"""

    player_id: str
    inventory: InventorySubmission
    round_number: int
    opponent_id: Optional[str] = None  # None = fight AI
    seed: Optional[int] = None  # For deterministic testing (TEST_MODE only)
    test_ai_difficulty: Optional[
        str
    ] = None  # "easy", "medium", "hard" (TEST_MODE only)


class PurchaseRequest(BaseModel):
    """Request to purchase an item from shop"""

    player_id: str
    item_id: str  # ID of item from shop
    placement: Union[str, List[int]]  # Either "storage" or [x, y] coordinates


class SellRequest(BaseModel):
    """Request to sell an item from inventory"""

    player_id: str
    item_id: str  # ID of item to sell
    from_storage: bool = False  # Whether item is in storage (vs grid)


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
    game_seed: Optional[int] = None  # Master seed for all RNG in this game session

    # Inventory fields
    inventory_grid: List[Dict] = []  # Items placed on the grid
    inventory_storage: List[Dict] = []  # Items in storage (not used in battle)
    placed_items: List[Dict] = []  # Quick reference to items on grid
    server_containers: List[Dict] = []  # Server container positions and info


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
async def start_session(game_seed: Optional[int] = None) -> Dict[str, Any]:
    """Start a new game session"""
    player_id = str(uuid.uuid4())

    # Only allow custom seeds in TEST_MODE
    if game_seed is not None and not TEST_MODE:
        raise HTTPException(
            status_code=403, detail="Custom seeds only allowed in test mode"
        )

    # Use provided seed or generate one
    if game_seed is None:
        game_seed = random.randint(0, 2**31 - 1)

    # Initialize inventory with 3 server containers
    inventory_manager = InventoryManager()
    inventory_state = inventory_manager.get_state()

    # Convert container positions to list format for consistency
    server_containers = []
    for container in inventory_state["containers"]:
        server_containers.append(
            {
                "id": container["id"],
                "type": container["type"],
                "position": list(container["position"]),  # Convert tuple to list
                "width": container["width"],
                "height": container["height"],
            }
        )

    session = GameSession(
        player_id=player_id,
        round=1,
        gold=12,
        lives=5,
        current_shop=generate_shop_items(1, seed=game_seed),
        game_seed=game_seed,
        inventory_grid=inventory_state["grid"],
        inventory_storage=inventory_state["storage"],
        placed_items=[],
        server_containers=server_containers,
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

    # Use game seed + round + some offset for deterministic shops
    shop_seed = (
        (session.game_seed + session.round * 1000) if session.game_seed else None
    )
    session.current_shop = generate_shop_items(session.round, seed=shop_seed)

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


def pick_rarity(weights: Dict[str, float], rng=random) -> str:
    """Pick a rarity based on weights"""
    total = sum(weights.values())
    if total == 0:
        return "common"

    roll = rng.uniform(0, total)
    cumulative = 0

    for rarity, weight in weights.items():
        cumulative += weight
        if roll <= cumulative:
            return rarity

    return "common"  # Fallback


def generate_shop_items(
    round_number: int, seed: Optional[int] = None
) -> List[Optional[Dict]]:
    """Generate random shop items based on round and rarity"""
    # Use deterministic RNG if seed provided
    if seed is not None:
        rng = random.Random(seed)
    else:
        rng = random

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
        if rng.random() < 0.85:  # 85% chance of item (15% empty)
            # Step 1: Pick rarity
            rarity = pick_rarity(weights, rng)

            # Step 2: Pick item from that rarity
            rarity_items = items_by_rarity.get(rarity, [])
            if not rarity_items:
                # Fallback to common if no items of that rarity
                rarity_items = items_by_rarity.get("common", [])

            if rarity_items:
                item_type, item_spec = rng.choice(rarity_items)

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
async def simulate_battle(
    request: Union[BattleRequest, SimpleBattleRequest]
) -> Dict[str, Any]:
    """
    Simulate a battle - supports both legacy BattleRequest and new SimpleBattleRequest
    SimpleBattleRequest uses inventory from session (preferred)
    BattleRequest includes inventory for backward compatibility
    """
    if request.player_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[request.player_id]

    # Validate test-only parameters
    if not TEST_MODE:
        if request.seed is not None:
            raise HTTPException(
                status_code=403, detail="Custom seeds only allowed in test mode"
            )
        if request.test_ai_difficulty is not None:
            raise HTTPException(
                status_code=403,
                detail="AI difficulty override only allowed in test mode",
            )

    # Get inventory from request or session
    if isinstance(request, SimpleBattleRequest):
        # Use inventory from session
        if len(session.inventory_grid) == 0:
            raise HTTPException(
                status_code=400, detail="Cannot battle with empty inventory"
            )

        # Convert session inventory to PlacedItems
        player_items = []
        for item_data in session.inventory_grid:
            if item_data["item_type"] in ITEM_CATALOG:
                item_spec = ITEM_CATALOG[item_data["item_type"]]
                placed_item = PlacedItem(
                    spec=item_spec,
                    position=tuple(item_data["position"]),
                    uid=item_data["id"],
                )
                player_items.append(placed_item)
    else:
        # Legacy: use inventory from request
        if len(request.inventory.items) == 0:
            raise HTTPException(
                status_code=400, detail="Cannot battle with empty inventory"
            )

        # Convert client items to PlacedItems
        player_items = []
        for item_def in request.inventory.items:
            try:
                placed_item = create_placed_item(item_def)
                player_items.append(placed_item)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

    # Generate or fetch opponent
    if request.opponent_id and request.opponent_id in sessions:
        # In real implementation, load opponent's last submitted inventory
        opponent_items = generate_ai_items(
            request.round_number, request.test_ai_difficulty
        )
    else:
        opponent_items = generate_ai_items(
            request.round_number, request.test_ai_difficulty
        )

    # Simulate battle - use request seed or derive from game seed
    if request.seed is not None:
        battle_seed = request.seed  # Explicit seed for testing
    elif session.game_seed is not None:
        # Derive battle seed from game seed + round + battle count
        battle_seed = (
            session.game_seed
            + request.round_number * 10000
            + (session.wins + session.losses)
        )
    else:
        battle_seed = None

    # Get containers from session for player
    from server_containers import ServerContainer, create_server_containers

    p1_containers = []
    for container_data in session.server_containers:
        # Create ServerContainer from session data
        containers_catalog = create_server_containers()
        container_type = container_data.get("type", "standard_vm")
        if container_type in containers_catalog:
            container_info = containers_catalog[container_type]
            p1_containers.append(
                ServerContainer(
                    spec=container_info["spec"],
                    position=tuple(container_data["position"]),
                    uid=container_data["id"],
                    internal_grid_size=container_info["internal_size"],
                    shape=container_info["external_shape"],
                )
            )

    # For P2 (AI), create appropriate containers for the AI items
    # AI places items at specific positions based on round
    p2_containers = []
    containers_catalog = create_server_containers()

    # Create containers that cover AI positions
    # Positions used: (1,3), (2,3), (4,3), (5,3), (1,4), (2,4), (4,4), (5,4)
    vm_info = containers_catalog["standard_vm"]
    p2_containers = [
        ServerContainer(
            spec=vm_info["spec"],
            position=(1, 3),
            uid="ai_vm1",
            internal_grid_size=vm_info["internal_size"],
            shape=vm_info["external_shape"],
        ),
        ServerContainer(
            spec=vm_info["spec"],
            position=(3, 3),
            uid="ai_vm2",
            internal_grid_size=vm_info["internal_size"],
            shape=vm_info["external_shape"],
        ),
        ServerContainer(
            spec=vm_info["spec"],
            position=(5, 3),
            uid="ai_vm3",
            internal_grid_size=vm_info["internal_size"],
            shape=vm_info["external_shape"],
        ),
    ]

    simulator = BattleSimulator(seed=battle_seed)
    battle_result = simulator.simulate_battle(
        player_items,
        opponent_items,
        round_number=request.round_number,
        p1_containers=p1_containers,
        p2_containers=p2_containers,
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
    # Use game seed + round + some offset for deterministic shops
    shop_seed = (
        (session.game_seed + session.round * 1000) if session.game_seed else None
    )
    session.current_shop = generate_shop_items(session.round, seed=shop_seed)

    # Store battle in history
    battle_record = {
        "id": str(uuid.uuid4()),
        "player_id": request.player_id,
        "opponent_id": request.opponent_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
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


def get_test_ai_items(difficulty: str, round_number: int) -> List[PlacedItem]:
    """Get test AI items based on difficulty for testing"""
    if difficulty == "easy":
        # Very weak - just one defensive item
        # Place on P2 container at (1,3)
        return [
            PlacedItem(
                spec=ITEM_CATALOG["firewall"],
                position=(1, 3),
                uid="test_firewall",
            )
        ]
    elif difficulty == "medium":
        # Moderate - a few basic items
        # Place on P2 containers which cover (1-2,3-4), (3-4,3-4), (5-6,3-4)
        items = []
        item_types = ["null_pointer", "firewall"]
        positions = [(1, 3), (3, 3)]  # Use first two container positions
        for i, item_type in enumerate(item_types):
            if item_type in ITEM_CATALOG:
                items.append(
                    PlacedItem(
                        spec=ITEM_CATALOG[item_type],
                        position=positions[i],
                        uid=f"test_{item_type}_{i}",
                    )
                )
        return items
    elif difficulty == "hard":
        # Use normal ghost player difficulty
        return get_ghost_player_items(round_number)
    else:
        # Default to normal difficulty
        return get_ghost_player_items(round_number)


def generate_ai_items(
    round_number: int, test_difficulty: Optional[str] = None
) -> List[PlacedItem]:
    """Generate AI opponent items based on round - uses ghost players or test difficulty"""
    if TEST_MODE and test_difficulty:
        return get_test_ai_items(test_difficulty, round_number)
    return get_ghost_player_items(round_number)


@app.post("/purchase/item")
async def purchase_item(request: PurchaseRequest) -> Dict[str, Any]:
    """Purchase an item from shop and place in inventory or storage"""
    if request.player_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[request.player_id]

    # Find item in shop
    item = None
    for shop_item in session.current_shop:
        if shop_item and shop_item.get("id") == request.item_id:
            item = shop_item
            break

    if not item:
        raise HTTPException(status_code=404, detail="Item not in shop")

    # Check gold
    cost = item["cost"]
    if session.gold < cost:
        raise HTTPException(status_code=400, detail="Not enough gold")

    # Create inventory manager from session state
    manager = InventoryManager()
    manager.restore_state(
        {
            "grid": session.inventory_grid,
            "storage": session.inventory_storage,
            "containers": session.server_containers,
        }
    )

    # Prepare item for placement
    inventory_item = {
        "id": item["id"],
        "item_type": item["item_type"],
        "name": item.get("name", ""),
        "cost": item.get("cost", 0),
        "rarity": item.get("rarity", "common"),
    }

    # Place item based on placement type
    if request.placement == "storage":
        # Add to storage
        success = manager.place_item(inventory_item, placement="storage")
        if not success:
            raise HTTPException(status_code=500, detail="Failed to add item to storage")
    else:
        # Place on grid
        if isinstance(request.placement, list) and len(request.placement) == 2:
            position = tuple(request.placement)
            success = manager.place_item(inventory_item, placement=position)
            if not success:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid placement - position may be occupied or not on a server",
                )
        else:
            raise HTTPException(status_code=400, detail="Invalid placement format")

    # Update session with new inventory state
    new_state = manager.get_state()
    session.inventory_grid = new_state["grid"]
    session.inventory_storage = new_state["storage"]

    # Update placed_items for quick reference
    session.placed_items = new_state["grid"].copy()

    # Deduct gold and remove from shop
    session.gold -= cost
    session.current_shop = [
        si if si and si.get("id") != request.item_id else None
        for si in session.current_shop
    ]

    return {"success": True, "purchased_item": item, "gold": session.gold}


@app.post("/sell/item")
async def sell_item(request: SellRequest) -> Dict[str, Any]:
    """Sell an item for 50% value"""
    if request.player_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[request.player_id]

    # Create inventory manager from session state
    manager = InventoryManager()
    manager.restore_state(
        {
            "grid": session.inventory_grid,
            "storage": session.inventory_storage,
            "containers": session.server_containers,
        }
    )

    # Find and remove item
    item_found = None
    item_cost = 3  # Default cost for gold calculation

    if request.from_storage:
        # Search in storage
        for item in session.inventory_storage:
            if item["id"] == request.item_id:
                item_found = item
                item_cost = item.get("cost", 3)
                # Remove from storage using item_id
                removed = manager.remove_item(item_id=request.item_id)
                if not removed:
                    raise HTTPException(status_code=500, detail="Failed to remove item")
                break
    else:
        # Search in grid
        for item in session.inventory_grid:
            if item["id"] == request.item_id:
                item_found = item
                item_cost = item.get("cost", 3)
                # Remove from grid using item_id (remove_item handles both storage and grid)
                removed = manager.remove_item(item_id=request.item_id)
                if not removed:
                    raise HTTPException(status_code=500, detail="Failed to remove item")
                break

    if not item_found:
        raise HTTPException(status_code=404, detail="Item not found in inventory")

    # Update session with new inventory state
    new_state = manager.get_state()
    session.inventory_grid = new_state["grid"]
    session.inventory_storage = new_state["storage"]
    session.placed_items = new_state["grid"].copy()

    # Calculate gold (50% of cost, rounded down)
    gold_gained = item_cost // 2
    session.gold += gold_gained

    return {
        "success": True,
        "gold_gained": gold_gained,
        "gold": session.gold,
        "sold_item": item_found,
    }


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
