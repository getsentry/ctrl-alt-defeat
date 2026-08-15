"""
Sentry Autobattler Server
- Client manages inventory locally
- Server validates and simulates battles deterministically
- Uses battle_engine for combat simulation
"""

import logging
import os
import random
import uuid
from http import HTTPStatus
from typing import Any, Dict, List, Optional, Tuple, Union

import sentry_sdk
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

import auth_endpoints
from auth import TokenData, get_current_user
from battle_engine import ITEM_CATALOG, BattleItem, BattleSimulator
from containers import Container, starting_containers

# Import session management and schemas
from database import db_manager
from inventory_manager import InvalidPlacementError, InventoryManager, ItemNotFoundError
from items import Item, PlacedItem
from matchmaking import MatchmakingService
from schemas import (
    BattleHistoryEntry,
    BattleHistoryResponse,
    BattleResponse,
    BattleResult,
    GameSession,
    HealthResponse,
    InventoryData,
    LeaderboardEntry,
    LeaderboardResponse,
    MoveItemRequest,
    MoveItemResponse,
    PurchaseRequest,
    PurchaseResponse,
    SellRequest,
    SellResponse,
    SessionUpdate,
    ShopRefreshRequest,
    ShopRefreshResponse,
    SimpleBattleRequest,
    StartSessionRequest,
    StartSessionResponse,
)
from session_manager import SessionManager
from utils import Position, utc_now

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

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if TEST_MODE else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

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
            LoggingIntegration(
                level=logging.INFO,  # Capture info and above as breadcrumbs
                event_level=logging.ERROR,  # Send errors and above as events
            ),
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


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint for monitoring"""
    try:
        # Check database connection
        await db_manager.execute("SELECT 1")
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
        if not TEST_MODE:
            sentry_sdk.capture_exception(e)

    return HealthResponse(
        status="healthy" if db_status == "healthy" else "degraded",
        database=db_status,
        environment=ENVIRONMENT,
        test_mode=TEST_MODE,
        version=os.environ.get("RELEASE", "autobattler-server@1.0.0"),
    )


@app.post("/session/start", response_model=StartSessionResponse)
async def start_session(
    request: StartSessionRequest,
    current_user: TokenData = Depends(get_current_user),
) -> StartSessionResponse:
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

    # Initialize inventory with the starting server containers
    inventory_manager = InventoryManager()
    inventory_state = inventory_manager.get_state()

    # Create session using SessionManager with player name from request
    session = await session_manager.create_session(
        player_id, game_seed, request.player_name
    )

    # Update session with shop and inventory
    session.current_shop = generate_shop_items(1, seed=game_seed)
    session.inventory_grid = inventory_state["grid"]
    session.inventory_storage = inventory_state["storage"]
    session.server_containers = starting_containers()

    # Save the updated session
    await session_manager.update_session(session)

    return StartSessionResponse(
        player_id=player_id,
        player_name=session.player_name,
        session=session,
    )


@app.get("/session/{player_id}")
async def get_session_endpoint(player_id: str) -> GameSession:
    """Get current session state"""
    session = await session_manager.get_session(player_id)
    if not session:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Session not found"
        )
    return session


@app.post("/shop/refresh", response_model=ShopRefreshResponse)
async def refresh_shop(request: ShopRefreshRequest) -> ShopRefreshResponse:
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

    # Shop already contains ShopItem models
    return ShopRefreshResponse(shop=session.current_shop, gold=session.gold)


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
) -> List[Optional[Item]]:
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

            items.append(Item.of(item_type, str(uuid.uuid4())))

    return items


@app.post("/battle/simulate", response_model=BattleResponse)
async def simulate_battle(request: SimpleBattleRequest) -> BattleResponse:
    """
    Simulate a battle using inventory from session
    """
    session = await session_manager.get_session(request.player_id)
    if not session:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Session not found"
        )
    current_round = session.round

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

    # Hand the grid items to the battle engine
    player_items = [
        BattleItem(
            spec=ITEM_CATALOG[item.item_type],
            position=item.position,
            uid=item.id,
            rotation=item.rotation,
        )
        for item in session.inventory_grid
        if item.item_type in ITEM_CATALOG
    ]

    # Try matchmaking first (unless in test mode with specified AI difficulty)
    opponent_data = None
    opponent_type = "ai"
    opponent_name = f"AI Opponent (Round {current_round})"
    match_history_id = None  # Track for updating after battle

    if not TEST_MODE or request.test_ai_difficulty is None:
        # Try to find a real player opponent
        try:
            # Get the database session and user_id
            async with db_manager.get_session() as db:
                # Get the actual database GameSession model
                from sqlalchemy import select

                from models import GameSession as DBGameSession

                db_session_result = await db.execute(
                    select(DBGameSession).where(
                        DBGameSession.player_id == request.player_id
                    )
                )
                db_session = db_session_result.scalar_one_or_none()

                if db_session and db_session.user_id:
                    # Calculate win percentage
                    total_games = session.wins + session.losses
                    win_percent = (
                        (session.wins / total_games * 100) if total_games > 0 else 0
                    )

                    # Try matchmaking
                    matchmaking = MatchmakingService(db)

                    opponent_data = await matchmaking.find_opponent(
                        user_id=db_session.user_id,
                        round_number=current_round,
                        win_percent=win_percent,
                        game_version="1.0.0",  # TODO: Get from config
                        fallback_to_ai=True,
                    )

                    if opponent_data:
                        opponent_type = "player_ghost"
                        opponent_name = opponent_data.get(
                            "player_name", "Unknown Player"
                        )
                        opponent_build_id = opponent_data.get("build_id")
        except Exception:
            # Log error but continue with AI opponent
            logger.exception("Matchmaking failed, falling back to AI opponent")

    # Generate opponent items and containers
    if opponent_data and opponent_type == "player_ghost":
        # Use the matched player's build
        opponent_items = []
        for entry in opponent_data["inventory"]:
            item = PlacedItem.model_validate(entry)
            if item.item_type in ITEM_CATALOG:
                opponent_items.append(
                    BattleItem(
                        spec=ITEM_CATALOG[item.item_type],
                        position=item.position,
                        uid=item.id,
                        rotation=item.rotation,
                    )
                )

        # Create containers from opponent data
        p2_containers = [
            Container.model_validate(container_data)
            for container_data in opponent_data["containers"]
        ]
    else:
        # Fall back to AI opponent
        opponent_items, p2_containers = generate_ai_opponent(
            current_round, request.test_ai_difficulty
        )
        opponent_type = "ai"

        # Give AI a descriptive name based on difficulty
        if TEST_MODE and request.test_ai_difficulty:
            difficulty_names = {
                1: "Rookie Bot",
                2: "Standard AI",
                3: "Expert System",
                4: "Elite AI",
                5: "Nightmare Bot",
            }
            opponent_name = difficulty_names.get(
                request.test_ai_difficulty, f"AI Level {request.test_ai_difficulty}"
            )

    # Simulate battle - use request seed or derive from game seed
    if request.seed is not None:
        battle_seed = request.seed  # Explicit seed for testing
    else:
        # Derive battle seed from game seed + round + battle count
        battle_seed = (
            session.game_seed + current_round * 10000 + (session.wins + session.losses)
        )

    # Get containers from session for player
    p1_containers = session.server_containers

    # Add performance monitoring for battle simulation
    with sentry_sdk.start_span(op="battle.simulation") as span:
        span.set_data("player_items_count", len(player_items))
        span.set_data("opponent_items_count", len(opponent_items))
        span.set_data("round", current_round)

        simulator = BattleSimulator(seed=battle_seed)
        battle_result = simulator.simulate_battle(
            player_items,
            opponent_items,
            round_number=current_round,
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

    session.round += 1  # Advance to next round
    if battle_result["winner"] == 1:  # Player won
        session.wins += 1
        session.shop_refresh_count = 0  # Reset refresh counter for new round
    else:
        session.losses += 1
        session.lives -= 1  # Lose a life on defeat

    gold_reward = get_round_gold(session.round)
    session.gold += gold_reward

    # Store clean battle result for database (before adding non-serializable objects)
    # Convert BattleAction objects to dicts for JSON serialization
    serializable_actions = [action.model_dump() for action in battle_result["actions"]]

    clean_battle_result = {
        "winner": battle_result["winner"],
        "duration": battle_result["duration"],
        "player1_quota": battle_result["player1_quota"],
        "player2_quota": battle_result["player2_quota"],
        "actions": serializable_actions,
        "seed": battle_result["seed"],
    }
    session.last_battle_result = clean_battle_result

    # Save player build for future matchmaking and record match history
    if not TEST_MODE:
        try:
            async with db_manager.get_session() as db:
                from sqlalchemy import select

                from models import GameSession as DBGameSession

                db_session_result = await db.execute(
                    select(DBGameSession).where(
                        DBGameSession.player_id == request.player_id
                    )
                )
                db_session = db_session_result.scalar_one_or_none()

                if db_session and db_session.user_id:
                    matchmaking = MatchmakingService(db)
                    # Save player build
                    player_build = await matchmaking.save_player_build(
                        user_id=db_session.user_id,
                        player_name=session.player_name,
                        game_session_id=request.player_id,
                        round_number=current_round,
                        wins=session.wins,
                        losses=session.losses,
                        lives=session.lives,
                        inventory_grid=session.inventory_grid,
                        server_containers=session.server_containers,
                        battle_won=(battle_result["winner"] == 1),
                        opponent_type=opponent_type,
                        opponent_difficulty=request.test_ai_difficulty,
                    )

                    # Record match history if this was a PvP match (after battle completes)
                    # We always have player_build.id since save_player_build returns the saved build
                    if (
                        opponent_type == "player_ghost"
                        and "opponent_build_id" in locals()
                        and player_build
                    ):
                        await matchmaking.record_match_result(
                            player_user_id=db_session.user_id,
                            player_build_id=player_build.id,
                            opponent_build_id=opponent_build_id,
                            battle_winner=battle_result["winner"],
                        )
        except Exception:
            # Log but don't fail the battle
            logger.exception("Failed to save player build or record match history")

    # Generate new shop for the round (first shop = refresh count 0)
    shop_seed = session.game_seed + session.round * 1000 + session.shop_refresh_count

    session.current_shop = generate_shop_items(session.round, seed=shop_seed)

    # Save updated session
    await session_manager.update_session(session)

    # Store battle in history (use clean result without BattleItem objects)
    await session_manager.save_battle_history(
        player1_id=request.player_id,
        player2_id=None,  # AI opponent for now
        round_number=current_round,
        winner=battle_result["winner"],
        battle_data=clean_battle_result,
    )

    battle_id = str(uuid.uuid4())

    # Check win/loss conditions
    game_over = session.lives <= 0
    victory = session.wins >= 10  # Won round 10

    # Serialize player and enemy inventories for client display
    def to_placed(item: BattleItem) -> PlacedItem:
        """The battle engine's item, as the item the client already knows"""
        return Item.of(item.spec.id, item.uid).placed_at(item.position, item.rotation)

    if "player1_items" in battle_result:
        player_inventory = {
            "items": [to_placed(item) for item in battle_result["player1_items"]],
            "servers": battle_result.get("player1_containers", []),
        }
        battle_result["player_inventory"] = player_inventory

    if "player2_items" in battle_result:
        enemy_inventory = {
            "items": [to_placed(item) for item in battle_result["player2_items"]],
            "servers": battle_result.get("player2_containers", []),
        }
        battle_result["enemy_inventory"] = enemy_inventory

    # Remove the raw objects from the result (they're not JSON serializable)
    battle_result.pop("player1_items", None)
    battle_result.pop("player2_items", None)
    battle_result.pop("player1_containers", None)
    battle_result.pop("player2_containers", None)

    battle_actions = battle_result["actions"]

    # The items are already the client's type, so the inventories pass straight
    # through.
    player_inventory = InventoryData(
        items=battle_result.get("player_inventory", {}).get("items", []),
        servers=battle_result.get("player_inventory", {}).get("servers", []),
    )

    enemy_inventory = InventoryData(
        items=battle_result.get("enemy_inventory", {}).get("items", []),
        servers=battle_result.get("enemy_inventory", {}).get("servers", []),
    )

    # Create BattleResult model
    battle_result_model = BattleResult(
        winner=battle_result["winner"],
        duration=battle_result["duration"],
        player1_quota=battle_result["player1_quota"],
        player2_quota=battle_result["player2_quota"],
        actions=battle_actions,
        seed=battle_result["seed"],
        player_inventory=player_inventory,
        enemy_inventory=enemy_inventory,
        opponent_name=opponent_name,
        opponent_type=opponent_type,
    )

    # Create SessionUpdate model
    session_update = SessionUpdate(
        round=session.round,
        gold=session.gold,
        gold_earned=gold_reward,
        wins=session.wins,
        losses=session.losses,
        lives=session.lives,
        game_over=game_over,
        victory=victory,
    )

    # Shop already contains ShopItem models
    return BattleResponse(
        battle_result=battle_result_model,
        session_update=session_update,
        new_shop=session.current_shop,
        battle_id=battle_id,
    )


def get_ghost_player_items(round_number: int) -> List[BattleItem]:
    """Get predefined ghost player inventory for each round"""

    containers = generate_ai_containers()

    # Define ghost player inventories for rounds 1-10
    ghost_inventories = {
        1: [  # Very basic
            ("null_blade", (0, 3)),
        ],
        2: [  # Still easy
            ("null_blade", (0, 3)),
            ("firewall", (4, 3)),
        ],
        3: [  # Adding defense
            ("null_blade", (0, 3)),
            ("core_dumper", (2, 3)),
            ("firewall", (4, 3)),
        ],
        4: [  # More items
            ("null_blade", (0, 3)),
            ("core_dumper", (2, 3)),
            ("firewall", (4, 3)),
            ("health_check", (5, 3)),
        ],
        5: [  # Medium difficulty
            ("null_blade", (0, 3)),
            ("core_dumper", (2, 3)),
            ("deadlock_twins", (6, 3)),
            ("firewall", (4, 3)),
            ("error_monitoring", (5, 3)),
        ],
        6: [  # Adding infrastructure
            ("null_blade", (0, 3)),
            ("core_dumper", (2, 3)),
            ("deadlock_twins", (6, 3)),
            ("firewall", (4, 3)),
            ("error_monitoring", (5, 3)),
            ("auto_scaler", (5, 4)),
        ],
        7: [  # Stronger items
            ("null_blade", (1, 3)),
            ("core_dumper", (2, 3)),
            ("buffer_overflow", (1, 4)),
            ("firewall", (4, 3)),
            ("error_monitoring", (5, 3)),
            ("auto_scaler", (5, 4)),  # Moved to avoid overlap
            ("health_check", (6, 3)),  # Moved to empty spot
        ],
        8: [  # Good mix
            ("null_blade", (1, 3)),
            ("core_dumper", (2, 3)),
            ("buffer_overflow", (1, 4)),
            ("deadlock_twins", (2, 4)),
            ("firewall", (4, 3)),
            ("error_monitoring", (5, 3)),
            ("auto_scaler", (5, 4)),  # Moved to avoid overlap with firewall
            ("quantum_processor", (6, 3)),  # Moved to empty spot
        ],
        9: [  # Near endgame
            ("null_blade", (1, 3)),
            ("core_dumper", (2, 3)),
            ("buffer_overflow", (1, 4)),
            ("deadlock_twins", (2, 4)),
            ("firewall", (4, 3)),
            ("error_monitoring", (5, 3)),
            ("auto_scaler", (5, 4)),  # Moved to avoid overlap with firewall
            ("quantum_processor", (6, 3)),  # Moved to empty spot
            ("load_balancer_module", (3, 3)),
        ],
        10: [  # Final boss
            ("null_blade", (1, 3)),
            ("core_dumper", (2, 3)),
            ("buffer_overflow", (1, 4)),
            ("deadlock_twins", (2, 4)),
            ("firewall", (4, 3)),
            ("error_monitoring", (5, 3)),
            ("auto_scaler", (5, 4)),  # Moved to avoid overlap with firewall
            ("quantum_processor", (6, 3)),  # Moved to empty spot
            ("load_balancer_module", (3, 3)),
            ("health_check", (3, 4)),
        ],
    }
    if round_number >= 5:
        containers.append(Container.of("standard_vm", (6, 3), "ai_vm4"))

    # Get inventory for this round (cap at 10)
    round_items = ghost_inventories.get(min(round_number, 10), ghost_inventories[1])

    items = []
    for item_type, position in round_items:
        if item_type in ITEM_CATALOG:
            item_spec = ITEM_CATALOG[item_type]
            placed_item = BattleItem(
                spec=item_spec,
                position=position,
                uid=f"ghost_{item_type}_{position[0]}_{position[1]}",
            )
            items.append(placed_item)

    return items, containers


def get_test_ai_items(difficulty: int, round_number: int) -> List[BattleItem]:
    """Get test AI items based on difficulty for testing"""
    if difficulty == 1:
        # Very weak - just one defensive item
        # Place on P2 container at (1,3)
        return [
            BattleItem(
                spec=ITEM_CATALOG["firewall"],
                position=(1, 3),
                uid="test_firewall",
            )
        ]
    elif difficulty == 2:
        # Moderate - a few basic items
        # Place on P2 containers which cover (1-2,3-4), (3-4,3-4), (5-6,3-4)
        items = []
        item_types = ["null_blade", "firewall"]
        positions = [(1, 3), (3, 3)]  # Use first two container positions
        for i, item_type in enumerate(item_types):
            if item_type in ITEM_CATALOG:
                items.append(
                    BattleItem(
                        spec=ITEM_CATALOG[item_type],
                        position=positions[i],
                        uid=f"test_{item_type}_{i}",
                    )
                )
        return items


def generate_ai_opponent(
    round_number: int, test_difficulty: Optional[int] = None
) -> Tuple[List[BattleItem], List[Container]]:
    """
    Generate AI opponent items and containers based on round
    Returns: (items, containers) tuple
    """
    if TEST_MODE and test_difficulty:
        items = get_test_ai_items(test_difficulty, round_number)
        containers = generate_ai_containers()
    else:
        items, containers = get_ghost_player_items(round_number)

    # Generate containers for AI based on item positions

    return items, containers


def generate_ai_containers() -> List[Container]:
    """Generate server containers that cover all AI item positions"""
    # Standard VMs are 2x2, so adjust positions to avoid gaps
    return [
        Container.of("standard_vm", (0, 3), "ai_vm1"),  # Covers (0,3)-(1,4)
        Container.of("standard_vm", (2, 3), "ai_vm2"),  # Covers (2,3)-(3,4)
        Container.of("standard_vm", (4, 3), "ai_vm3"),  # Covers (4,3)-(5,4)
    ]


def place_item_in_inventory(
    manager: InventoryManager,
    item: Item,
    to_location: Union[str, Position],
) -> None:
    """
    Shared logic for placing an item in inventory (grid or chest)

    Args:
        manager: InventoryManager instance
        item: The item to place
        to_location: Either "storage" or an (x, y) position

    Raises:
        HTTPException: If placement fails with appropriate error message
    """
    if to_location == "storage":
        success = manager.place_item(item, placement="storage")
        if not success:
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                detail="Failed to add item to storage",
            )
    else:
        # Place on grid
        success = manager.place_item(item, placement=to_location)
        if not success:
            # Determine specific error - need to check with shape
            if not manager.grid.is_valid_placement(to_location, item.shape):
                raise HTTPException(
                    status_code=HTTPStatus.BAD_REQUEST,
                    detail=(
                        f"Position {to_location} with shape does not fit "
                        "entirely on server containers"
                    ),
                )
            else:
                existing = manager.grid.get_item_at(to_location)
                if existing:
                    raise HTTPException(
                        status_code=HTTPStatus.BAD_REQUEST,
                        detail=f"Position {to_location} is already occupied",
                    )
                else:
                    raise HTTPException(
                        status_code=HTTPStatus.BAD_REQUEST,
                        detail="Invalid placement for this item",
                    )


@app.post("/purchase/item", response_model=PurchaseResponse)
async def purchase_item(request: PurchaseRequest) -> PurchaseResponse:
    """Purchase an item from shop and place in inventory or storage"""
    session = await session_manager.get_session(request.player_id)
    if not session:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Session not found"
        )

    # Find item in shop
    item = None
    for shop_item in session.current_shop:
        if shop_item and shop_item.id == request.item_id:
            item = shop_item
            break

    if not item:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Item not in shop")

    # Check gold
    cost = item.cost
    if session.gold < cost:
        raise HTTPException(status_code=400, detail="Not enough gold")

    # Check if it's a container
    is_container = item.is_container

    if is_container:
        # Containers can't be placed in storage, only on the main grid
        if request.to_storage:
            raise HTTPException(
                status_code=400, detail="Containers cannot be placed in storage"
            )

        # Containers need special handling - they become part of the server infrastructure
        if not request.target_position or len(request.target_position) != 2:
            raise HTTPException(
                status_code=400, detail="Container placement requires target_position"
            )

        # Add the container to the session's server_containers
        new_container = Container.of(
            item.item_type, request.target_position, container_id=item.id
        )

        # Check if the container overlaps any the player already owns
        new_squares = set(new_container.covered_squares())
        for existing in session.server_containers:
            if new_squares & set(existing.covered_squares()):
                raise HTTPException(
                    status_code=400, detail="Container overlaps with existing container"
                )

        # Add the container
        session.server_containers.append(new_container)

        # Deduct gold and remove from shop
        session.gold -= cost
        session.current_shop = [
            si if si and si.id != request.item_id else None
            for si in session.current_shop
        ]

        # Save updated session
        await session_manager.update_session(session)

        # Return response with updated server_containers
        return PurchaseResponse(
            purchased_item=item,
            gold=session.gold,
            server_containers=session.server_containers,
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

    # Determine placement location
    if request.to_storage:
        to_location = "storage"
    elif request.target_position and len(request.target_position) == 2:
        to_location = request.target_position
    else:
        raise HTTPException(
            status_code=400,
            detail="Must specify either to_storage=True or target_position",
        )

    # Use shared placement logic
    place_item_in_inventory(manager, item, to_location)

    # Update session with new inventory state
    new_state = manager.get_state()
    session.inventory_grid = new_state["grid"]
    session.inventory_storage = new_state["storage"]

    # Deduct gold and remove from shop
    session.gold -= cost
    session.current_shop = [
        si if si and si.id != request.item_id else None for si in session.current_shop
    ]

    # Save updated session
    await session_manager.update_session(session)

    # Item is already a ShopItem model
    return PurchaseResponse(
        purchased_item=item,
        gold=session.gold,
        server_containers=session.server_containers,
    )


@app.post("/sell/item", response_model=SellResponse)
async def sell_item(request: SellRequest) -> SellResponse:
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
        if item.id == request.item_uid:
            item_found = item
            item_cost = item.cost
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
            if item.id == request.item_uid:
                item_found = item
                item_cost = item.cost
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

    # Calculate gold (50% of cost, rounded down)
    gold_gained = item_cost // 2
    session.gold += gold_gained

    # Save updated session
    await session_manager.update_session(session)

    return SellResponse(
        gold_gained=gold_gained,
        gold=session.gold,
        sold_item=item_found,
    )


@app.post("/move/item", response_model=MoveItemResponse)
async def move_item(request: MoveItemRequest) -> MoveItemResponse:
    """Move an item to a new position or storage"""
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

    # Find the item and its current location
    item_found = None
    current_location = None

    for item in session.inventory_storage:
        if item.id == request.item_uid:
            item_found = item
            current_location = "storage"
            break

    if not item_found:
        for item in session.inventory_grid:
            if item.id == request.item_uid:
                item_found = item
                current_location = item.position
                break

    if not item_found:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Item not found in inventory"
        )

    to_loc = request.to_location

    # Check for same position move (no-op)
    if current_location == to_loc:
        return MoveItemResponse(
            inventory_grid=session.inventory_grid,
            inventory_storage=session.inventory_storage,
        )

    # Attempt the move using InventoryManager
    try:
        manager.move_item(
            item_id=request.item_uid, from_location=current_location, to_location=to_loc
        )
    except ItemNotFoundError as e:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(e))
    except InvalidPlacementError as e:
        # Parse the error message to provide cleaner output
        error_msg = str(e)
        if "not on a server container" in error_msg:
            detail = f"Position {to_loc} is not on a server container"
        elif "already occupied" in error_msg:
            detail = f"Position {to_loc} is already occupied"
        else:
            detail = error_msg
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=detail)

    # Update session with new inventory state
    new_state = manager.get_state()
    session.inventory_grid = new_state["grid"]
    session.inventory_storage = new_state["storage"]

    # Save updated session
    await session_manager.update_session(session)

    return MoveItemResponse(
        inventory_grid=session.inventory_grid,
        inventory_storage=session.inventory_storage,
    )


@app.get("/leaderboard", response_model=LeaderboardResponse)
async def get_leaderboard(limit: int = 10) -> LeaderboardResponse:
    """Get top players"""
    entries = []

    # Get all active sessions
    player_ids = await session_manager.list_active_sessions()
    for player_id in player_ids:
        session = await session_manager.get_session(player_id)
        if not session:
            continue
        entries.append(
            LeaderboardEntry(
                player_id=player_id,
                round=session.round,
                wins=session.wins,
                losses=session.losses,
                win_rate=round(
                    session.wins / max(1, session.wins + session.losses) * 100, 1
                ),
                score=session.wins * 100 + session.round * 10,
            )
        )

    entries.sort(key=lambda x: x.score, reverse=True)
    return LeaderboardResponse(entries=entries[:limit])


@app.get("/battle/history/{player_id}", response_model=BattleHistoryResponse)
async def get_battle_history(player_id: str, limit: int = 10) -> BattleHistoryResponse:
    """Get player's recent battles"""
    # Get battle history from session manager
    battles_data = await session_manager.get_battle_history(player_id, limit)

    # Convert to BattleHistoryEntry models
    battles = []
    for battle in battles_data:
        battles.append(
            BattleHistoryEntry(
                id=battle["id"],
                player1_id=battle["player1_id"],
                player2_id=battle.get("player2_id"),
                round_number=battle["round_number"],
                winner=battle["winner"],
                battle_data=battle["battle_data"],
                created_at=battle.get("created_at"),
            )
        )

    return BattleHistoryResponse(battles=battles)


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
