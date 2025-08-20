"""
Sentry Autobattler Server
- Client manages inventory locally
- Server validates and simulates battles deterministically
- Uses battle_engine for combat simulation
"""

import os
import random
import uuid
from http import HTTPStatus
from typing import Any, Dict, List, Optional, Tuple

import auth_endpoints
import sentry_sdk
from auth import TokenData, get_current_user
from battle_engine import ITEM_CATALOG, BattleSimulator, PlacedItem

# Import session management and schemas
from database import db_manager
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from inventory_manager import InventoryManager
from schemas import (
    GameSession,
    PurchaseRequest,
    SellRequest,
    ShopRefreshRequest,
    SimpleBattleRequest,
    StartSessionRequest,
)
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration
from server_containers import ServerContainer, create_server_containers
from session_manager import SessionManager
from utils import utc_now

# Test mode allows seeds and special AI configurations for testing
TEST_MODE = os.environ.get("TEST_MODE", "false").lower() == "true"


def filter_sensitive_data(event):
    """Filter out sensitive data from Sentry events"""
    # Remove authentication headers
    if "request" in event and "headers" in event["request"]:
        headers = event["request"]["headers"]
        if "authorization" in headers:
            headers["authorization"] = "[FILTERED]"
        if "cookie" in headers:
            headers["cookie"] = "[FILTERED]"

    # Remove passwords from request data
    if "request" in event and "data" in event["request"]:
        data = event["request"]["data"]
        if isinstance(data, dict):
            if "password" in data:
                data["password"] = "[FILTERED]"
            if "password_hash" in data:
                data["password_hash"] = "[FILTERED]"

    # Remove JWT tokens from error messages
    if "exception" in event and "values" in event["exception"]:
        for exception in event["exception"]["values"]:
            if "value" in exception and "jwt" in exception["value"].lower():
                exception["value"] = "[JWT TOKEN FILTERED]"

    return event


# Initialize Sentry
SENTRY_DSN = os.environ.get(
    "SENTRY_DSN",
    "https://6a4ff9b3cfcb25b639b4ba43d1990e9f@o1.ingest.us.sentry.io/4509874488410112",
)
ENVIRONMENT = "test" if TEST_MODE else os.environ.get("ENVIRONMENT", "production")

if SENTRY_DSN and not TEST_MODE:  # Don't initialize Sentry in test mode
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            FastApiIntegration(
                transaction_style="endpoint",
                failed_request_status_codes=[
                    400,
                    401,
                    403,
                    404,
                    405,
                    500,
                    501,
                    502,
                    503,
                    504,
                ],
            ),
            StarletteIntegration(transaction_style="endpoint"),
            SqlalchemyIntegration(),
        ],
        traces_sample_rate=0.1,  # 10% of transactions for performance monitoring
        profiles_sample_rate=0.1,  # 10% of transactions for profiling
        environment=ENVIRONMENT,
        release=os.environ.get("RELEASE", "autobattler-server@1.0.0"),
        send_default_pii=False,  # Don't send personally identifiable information
        attach_stacktrace=True,
        before_send=lambda event, hint: filter_sensitive_data(event),
    )
    print(f"Sentry initialized for {ENVIRONMENT} environment")

# Create session manager
session_manager = SessionManager()

app = FastAPI(title="Sentry Autobattler Server")

# Include authentication routes
app.include_router(auth_endpoints.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Log HTTP exceptions to Sentry"""
    if exc.status_code >= 500 and not TEST_MODE:
        sentry_sdk.capture_exception(exc)
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Log unhandled exceptions to Sentry"""
    if not TEST_MODE:
        sentry_sdk.capture_exception(exc)
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.on_event("startup")
async def startup_event():
    """Initialize database connection on startup"""
    try:
        await session_manager.initialize()
        print(f"Server started in {'TEST' if TEST_MODE else 'PRODUCTION'} mode")
        print("Using PostgreSQL for session persistence")
        if SENTRY_DSN and not TEST_MODE:
            # Log startup to Sentry
            sentry_sdk.capture_message(f"Server started in {ENVIRONMENT}", level="info")
    except Exception as e:
        if not TEST_MODE:
            sentry_sdk.capture_exception(e)
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up database connections on shutdown"""
    await db_manager.close()
    print("Server shutdown complete")


# Request/Response models have been moved to schemas.py


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    try:
        # Check database connection
        await db_manager.execute("SELECT 1")
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
        if not TEST_MODE:
            sentry_sdk.capture_exception(e)

    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "database": db_status,
        "environment": ENVIRONMENT,
        "test_mode": TEST_MODE,
        "version": os.environ.get("RELEASE", "autobattler-server@1.0.0"),
    }


@app.post("/session/start")
async def start_session(
    request: StartSessionRequest,
    current_user: TokenData = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Start a new game session

    Requires authentication via JWT token.
    Use /auth/guest to create a guest account first if needed.
    """
    # Use authenticated user from token
    player_id = str(current_user.user_id)

    # Set Sentry user context for better error tracking
    if not TEST_MODE:
        sentry_sdk.set_user(
            {
                "id": player_id,
                "username": current_user.username,
            }
        )

    # Only allow custom seeds in TEST_MODE
    if request.seed is not None and not TEST_MODE:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Custom seeds only allowed in test mode",
        )

    # Always have a seed - use provided or generate one
    game_seed = (
        request.seed if request.seed is not None else random.randint(0, 2**31 - 1)
    )

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

    # Create session using SessionManager
    session = await session_manager.create_session(player_id, game_seed)

    # Update session with shop and inventory
    session.current_shop = generate_shop_items(1, seed=game_seed)
    session.inventory_grid = inventory_state["grid"]
    session.inventory_storage = inventory_state["storage"]
    session.server_containers = server_containers

    # Save the updated session
    await session_manager.update_session(session)

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
        "session": session.model_dump(),
        "item_catalog": item_catalog_simple,
    }


@app.get("/session/{player_id}")
async def get_session_endpoint(player_id: str) -> GameSession:
    """Get current session state"""
    session = await session_manager.get_session(player_id)
    if not session:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Session not found"
        )
    return session


@app.post("/shop/refresh")
async def refresh_shop(request: ShopRefreshRequest) -> Dict[str, Any]:
    """Get new shop items (costs 1 gold if not free refresh)"""
    session = await session_manager.get_session(request.player_id)
    if not session:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Session not found"
        )

    # Check if this is a paid refresh
    if len(session.current_shop) > 0:  # Not the first shop of the round
        if session.gold < 1:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST, detail="Not enough gold"
            )
        session.gold -= 1

    # Increment refresh counter for this round
    session.shop_refresh_count += 1

    # Use game seed + round + refresh count for deterministic but varying shops
    shop_seed = session.game_seed + session.round * 1000 + session.shop_refresh_count

    session.current_shop = generate_shop_items(session.round, seed=shop_seed)

    # Save updated session
    await session_manager.update_session(session)

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
        elif rarity == "unique":
            rarity = "godly"  # Unique items are very rare
        if rarity in items_by_rarity:
            items_by_rarity[rarity].append((item_type, item_spec))

    # Shuffle each rarity list with the seed for better distribution
    if seed is not None:
        for rarity in items_by_rarity:
            rng.shuffle(items_by_rarity[rarity])

    # Get rarity weights for this round
    weights = get_rarity_weights(round_number)

    # Track recently used items to avoid too many duplicates
    used_item_types = []

    for i in range(shop_size):
        # Always generate an item - no empty slots
        # Step 1: Pick rarity
        rarity = pick_rarity(weights, rng)

        # Step 2: Pick item from that rarity
        rarity_items = items_by_rarity.get(rarity, [])
        if not rarity_items:
            # Fallback to common if no items of that rarity
            rarity_items = items_by_rarity.get("common", [])

        if rarity_items:
            # Try to avoid duplicates by filtering out recently used items
            available_items = [
                (it, spec) for it, spec in rarity_items if it not in used_item_types
            ]

            # If all items of this rarity were used, allow duplicates
            if not available_items:
                available_items = rarity_items

            # Use a more distributed selection by adding item index to seed
            item_index = rng.randint(0, len(available_items) - 1)
            item_type, item_spec = available_items[item_index]

            # Track this item type (but allow some duplicates after 3 different items)
            used_item_types.append(item_type)
            if len(used_item_types) > 3:
                used_item_types.pop(0)

            # Check if it's a container (containers have internal_size in their catalog)
            containers_catalog = create_server_containers()
            is_container = item_type in containers_catalog
            if is_container:
                # Get container info for internal size
                container_info = containers_catalog.get(item_type, {})
                internal_size = container_info.get("internal_size", (2, 2))

                item_info = {
                    "id": str(uuid.uuid4()),
                    "item_type": item_type,
                    "name": item_spec.name,
                    "category": "container",  # Mark as container category for UI
                    "rarity": item_spec.rarity,
                    "cost": get_shop_cost(item_spec.rarity, 1),
                    "is_container": True,
                    "internal_width": internal_size[0],
                    "internal_height": internal_size[1],
                    "min_damage": 0,
                    "max_damage": 0,
                    "cooldown": 0,
                    "cpu_cost": 0,
                    "special_effect": "",
                }
            else:
                # Regular item
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
                    "is_container": False,
                    "min_damage": min_dmg,
                    "max_damage": max_dmg,
                    "cooldown": cooldown,
                    "cpu_cost": cpu_cost,
                    "special_effect": special,
                }

            items.append(item_info)

    return items


@app.post("/battle/simulate")
async def simulate_battle(request: SimpleBattleRequest) -> Dict[str, Any]:
    """
    Simulate a battle using inventory from session
    """
    session = await session_manager.get_session(request.player_id)
    if not session:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Session not found"
        )

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

    # Generate AI opponent (matchmaking will be implemented later)
    opponent_items, p2_containers = generate_ai_opponent(
        request.round_number, request.test_ai_difficulty
    )

    # Simulate battle - use request seed or derive from game seed
    if request.seed is not None:
        battle_seed = request.seed  # Explicit seed for testing
    else:
        # Derive battle seed from game seed + round + battle count
        battle_seed = (
            session.game_seed
            + request.round_number * 10000
            + (session.wins + session.losses)
        )

    # Get containers from session for player
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

    # Add performance monitoring for battle simulation
    with sentry_sdk.start_span(op="battle.simulation") as span:
        span.set_data("player_items_count", len(player_items))
        span.set_data("opponent_items_count", len(opponent_items))
        span.set_data("round", request.round_number)

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
        session.shop_refresh_count = 0  # Reset refresh counter for new round
        gold_reward = get_round_gold(session.round)  # Gold for new round
    else:
        session.losses += 1
        session.lives -= 1  # Lose a life on defeat
        gold_reward = get_round_gold(session.round)  # Same round gold (no advance)

    session.gold += gold_reward

    # Store clean battle result for database (before adding non-serializable objects)
    clean_battle_result = {
        "winner": battle_result["winner"],
        "duration": battle_result["duration"],
        "player1_quota": battle_result["player1_quota"],
        "player2_quota": battle_result["player2_quota"],
        "actions": battle_result["actions"],
        "seed": battle_result["seed"],
    }
    session.last_battle_result = clean_battle_result

    # Generate new shop for the round (first shop = refresh count 0)
    shop_seed = session.game_seed + session.round * 1000 + session.shop_refresh_count

    session.current_shop = generate_shop_items(session.round, seed=shop_seed)

    # Save updated session
    await session_manager.update_session(session)

    # Store battle in history (use clean result without PlacedItem objects)
    await session_manager.save_battle_history(
        player1_id=request.player_id,
        player2_id=None,  # AI opponent for now
        round_number=request.round_number,
        winner=battle_result["winner"],
        battle_data=clean_battle_result,
    )

    battle_id = str(uuid.uuid4())

    # Check win/loss conditions
    game_over = session.lives <= 0
    victory = session.round > 10 and battle_result["winner"] == 1  # Won round 10

    # Serialize player and enemy inventories for client display
    def serialize_placed_item(item: PlacedItem) -> Dict:
        """Convert PlacedItem to client-compatible format"""
        shape_data = [[0, 0]]  # Default 1x1 shape
        if item.spec.shape:
            # ItemShape has 'squares' attribute, not 'occupied_squares'
            if hasattr(item.spec.shape, "squares"):
                shape_data = [list(s) for s in item.spec.shape.squares]
            elif hasattr(item.spec.shape, "get_occupied_squares"):
                shape_data = [list(s) for s in item.spec.shape.get_occupied_squares()]

        return {
            "id": item.uid,
            "item_type": item.spec.id,
            "name": item.spec.name,
            "position": list(item.position),
            "category": item.spec.category,
            "shape": shape_data,
        }

    def serialize_container(container: ServerContainer) -> Dict:
        """Convert ServerContainer to client-compatible format"""
        width = 2  # Default width
        height = 2  # Default height

        if hasattr(container, "shape"):
            if hasattr(container.shape, "width"):
                width = container.shape.width
            elif hasattr(container.shape, "squares"):
                # Calculate from squares
                max_x = max(s[0] for s in container.shape.squares) + 1
                width = max_x

            if hasattr(container.shape, "height"):
                height = container.shape.height
            elif hasattr(container.shape, "squares"):
                # Calculate from squares
                max_y = max(s[1] for s in container.shape.squares) + 1
                height = max_y

        return {
            "id": container.uid,
            "type": container.spec.id
            if hasattr(container.spec, "id")
            else "standard_vm",
            "position": list(container.position),
            "width": width,
            "height": height,
        }

    # Add serialized inventories to battle result for client display
    if "player1_items" in battle_result:
        player_inventory = {
            "items": [
                serialize_placed_item(item) for item in battle_result["player1_items"]
            ],
            "servers": [
                serialize_container(c)
                for c in battle_result.get("player1_containers", [])
            ],
        }
        battle_result["player_inventory"] = player_inventory

    if "player2_items" in battle_result:
        enemy_inventory = {
            "items": [
                serialize_placed_item(item) for item in battle_result["player2_items"]
            ],
            "servers": [
                serialize_container(c)
                for c in battle_result.get("player2_containers", [])
            ],
        }
        battle_result["enemy_inventory"] = enemy_inventory

    # Remove the raw objects from the result (they're not JSON serializable)
    battle_result.pop("player1_items", None)
    battle_result.pop("player2_items", None)
    battle_result.pop("player1_containers", None)
    battle_result.pop("player2_containers", None)

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
        "battle_id": battle_id,
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


def generate_ai_opponent(
    round_number: int, test_difficulty: Optional[str] = None
) -> Tuple[List[PlacedItem], List[ServerContainer]]:
    """
    Generate AI opponent items and containers based on round
    Returns: (items, containers) tuple
    """
    if TEST_MODE and test_difficulty:
        items = get_test_ai_items(test_difficulty, round_number)
    else:
        items = get_ghost_player_items(round_number)

    # Generate containers for AI based on item positions
    containers = generate_ai_containers(items)
    return items, containers


def generate_ai_containers(items: List[PlacedItem]) -> List[ServerContainer]:
    """Generate server containers that cover all AI item positions"""
    containers_catalog = create_server_containers()
    vm_info = containers_catalog["standard_vm"]

    # Create a minimal set of containers that cover all item positions
    # For simplicity, create 3 standard VMs at fixed positions
    containers = [
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
    return containers


@app.post("/purchase/item")
async def purchase_item(request: PurchaseRequest) -> Dict[str, Any]:
    """Purchase an item from shop and place in inventory or storage"""
    session = await session_manager.get_session(request.player_id)
    if not session:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Session not found"
        )

    # Find item in shop
    item = None
    for shop_item in session.current_shop:
        if shop_item and shop_item.get("id") == request.item_id:
            item = shop_item
            break

    if not item:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Item not in shop")

    # Check gold
    cost = item["cost"]
    if session.gold < cost:
        raise HTTPException(status_code=400, detail="Not enough gold")

    # Check if it's a container
    is_container = item.get("is_container", False)

    if is_container:
        # Containers can't be placed in storage, only on the main grid
        if request.to_storage:
            raise HTTPException(
                status_code=400, detail="Containers cannot be placed in storage"
            )

        # Containers need special handling - they become part of the server infrastructure
        # For now, return an error since container placement needs more work
        raise HTTPException(
            status_code=501, detail="Container placement not yet implemented"
        )

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
    if request.to_storage:
        # Add to storage
        success = manager.place_item(inventory_item, placement="storage")
        if not success:
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                detail="Failed to add item to storage",
            )
    else:
        # Place on grid
        if request.target_position and len(request.target_position) == 2:
            position = tuple(request.target_position)
            success = manager.place_item(inventory_item, placement=position)
            if not success:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid placement - position may be occupied or not on a server",
                )
        else:
            raise HTTPException(
                status_code=400,
                detail="Invalid placement format - need target_position",
            )

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

    # Save updated session
    await session_manager.update_session(session)

    return {"success": True, "purchased_item": item, "gold": session.gold}


@app.post("/sell/item")
async def sell_item(request: SellRequest) -> Dict[str, Any]:
    """Sell an item for 50% value"""
    session = await session_manager.get_session(request.player_id)
    if not session:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Session not found"
        )

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

    # Search in both storage and grid for the item
    # First try storage
    for item in session.inventory_storage:
        if item["id"] == request.item_uid:
            item_found = item
            item_cost = item.get("cost", 3)
            # Remove from storage using item_id
            removed = manager.remove_item(item_id=request.item_uid)
            if not removed:
                raise HTTPException(
                    status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                    detail="Failed to remove item",
                )
            break

    # If not found in storage, try grid
    if not item_found:
        for item in session.inventory_grid:
            if item["id"] == request.item_uid:
                item_found = item
                item_cost = item.get("cost", 3)
                # Remove from grid using item_id (remove_item handles both storage and grid)
                removed = manager.remove_item(item_id=request.item_uid)
                if not removed:
                    raise HTTPException(
                        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                        detail="Failed to remove item",
                    )
                break

    if not item_found:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Item not found in inventory"
        )

    # Update session with new inventory state
    new_state = manager.get_state()
    session.inventory_grid = new_state["grid"]
    session.inventory_storage = new_state["storage"]
    session.placed_items = new_state["grid"].copy()

    # Calculate gold (50% of cost, rounded down)
    gold_gained = item_cost // 2
    session.gold += gold_gained

    # Save updated session
    await session_manager.update_session(session)

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

    # Get all active sessions
    player_ids = await session_manager.list_sessions()
    for player_id in player_ids:
        session = await session_manager.get_session(player_id)
        if not session:
            continue
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
    # Get battle history from session manager
    battles = await session_manager.get_battle_history(player_id, limit)
    return battles


# Test-only endpoints
if TEST_MODE:
    # Store active test transactions
    test_transactions = {}

    @app.post("/test/start-session")
    async def start_test_session() -> Dict[str, str]:
        """Start a test session with transaction isolation (TEST MODE ONLY)

        This creates a database transaction that will be rolled back when
        the test session ends, providing fast test isolation.
        """
        if not TEST_MODE:
            raise HTTPException(
                status_code=403, detail="This endpoint is only available in TEST_MODE"
            )

        import uuid

        from database import db_manager

        try:
            # Generate a unique session ID
            session_id = str(uuid.uuid4())

            # Create a new connection and start a transaction
            connection = await db_manager.engine.connect()
            transaction = await connection.begin()

            # Store the connection and transaction
            test_transactions[session_id] = {
                "connection": connection,
                "transaction": transaction,
                "started_at": utc_now(),
            }

            return {
                "status": "success",
                "session_id": session_id,
                "message": "Test session started with transaction isolation",
            }
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to start test session: {str(e)}"
            )

    @app.post("/test/end-session/{session_id}")
    async def end_test_session(session_id: str) -> Dict[str, str]:
        """End a test session and rollback all changes (TEST MODE ONLY)

        This rolls back the transaction, undoing all database changes made
        during the test session. Much faster than truncating tables.
        """
        if not TEST_MODE:
            raise HTTPException(
                status_code=403, detail="This endpoint is only available in TEST_MODE"
            )

        if session_id not in test_transactions:
            raise HTTPException(
                status_code=404, detail=f"Test session {session_id} not found"
            )

        try:
            session = test_transactions[session_id]

            # Rollback the transaction
            await session["transaction"].rollback()

            # Close the connection
            await session["connection"].close()

            # Remove from active sessions
            del test_transactions[session_id]

            return {
                "status": "success",
                "message": "Test session ended, all changes rolled back",
            }
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to end test session: {str(e)}"
            )

    @app.post("/test/reset-database")
    async def reset_database() -> Dict[str, str]:
        """Reset database to clean state (TEST MODE ONLY)

        This endpoint truncates all tables. It's slower than using
        test sessions but ensures complete cleanup.

        Prefer /test/start-session and /test/end-session for faster isolation.
        """
        if not TEST_MODE:
            raise HTTPException(
                status_code=403, detail="This endpoint is only available in TEST_MODE"
            )

        try:
            # Reset the database tables
            await session_manager.reset_database()
            return {
                "status": "success",
                "message": "Database reset successfully (slow)",
            }
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to reset database: {str(e)}"
            )

    @app.get("/test/status")
    async def test_status() -> Dict[str, Any]:
        """Get test environment status (TEST MODE ONLY)"""
        if not TEST_MODE:
            raise HTTPException(
                status_code=403, detail="This endpoint is only available in TEST_MODE"
            )

        return {
            "test_mode": TEST_MODE,
            "db_host": os.environ.get("DB_HOST", "default"),
            "db_name": os.environ.get("DB_NAME", "default"),
        }


if __name__ == "__main__":
    import argparse

    import uvicorn

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Battle Server")
    parser.add_argument(
        "--port", type=int, default=8000, help="Port to run server on (default: 8000)"
    )
    parser.add_argument(
        "--db-host",
        type=str,
        default=None,
        help="Database host (e.g. localhost:5432 or db.example.com:5432)",
    )
    parser.add_argument(
        "--db-name",
        type=str,
        default=None,
        help="Database name (e.g. autobattler_test)",
    )
    args = parser.parse_args()

    # Set environment variables for database configuration
    if args.db_host:
        os.environ["DB_HOST"] = args.db_host
    if args.db_name:
        os.environ["DB_NAME"] = args.db_name

    print(f"Starting server on port {args.port}...")
    if args.db_host or args.db_name:
        print(
            f"Database config: host={args.db_host or 'default'}, name={args.db_name or 'default'}"
        )
    uvicorn.run(app, host="0.0.0.0", port=args.port)
