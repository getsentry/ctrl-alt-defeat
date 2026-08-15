"""
Pydantic schemas for API request/response models
"""

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from utils import Position


class ShopItem(BaseModel):
    """Item available in the shop"""

    id: str = Field(description="Unique item instance ID")
    item_type: str = Field(description="Item type identifier")
    name: str = Field(description="Display name")
    category: str = Field(description="Item category")
    slug: str = Field(default="", description="URL-friendly identifier")
    rarity: str = Field(description="Item rarity tier")
    cost: int = Field(description="Gold cost to purchase")
    is_container: bool = Field(
        default=False, description="Whether this is a server container"
    )
    min_damage: int = Field(default=0, description="Minimum damage")
    max_damage: int = Field(default=0, description="Maximum damage")
    cooldown: float = Field(default=0, description="Cooldown in seconds")
    cpu_cost: int = Field(default=0, description="CPU cost")
    special_effect: str = Field(default="", description="Special effect")
    shape: List[List[int]] = Field(description="Item shape as list of [x, y] offsets")


class GameSession(BaseModel):
    """Player's current game session"""

    player_id: str
    player_name: str = "Player"
    round: int = 1
    gold: int = 12  # Start with 12g for round 1
    lives: int = 5  # Player has 5 lives/tries
    wins: int = 0
    losses: int = 0
    last_battle_result: Optional[Dict]
    current_shop: List[
        Optional[ShopItem]
    ] = []  # Shop can have empty slots after purchases
    game_seed: int  # Master seed for all RNG in this game session (always set)
    shop_refresh_count: int = 0  # Track number of shop refreshes for seed variation
    # Inventory fields
    inventory_grid: List[Dict] = []  # Items placed on the grid
    inventory_storage: List[Dict] = []  # Items in storage (not used in battle)
    server_containers: List[Dict] = []  # Server container positions and info


class StartSessionRequest(BaseModel):
    """Request to start a new game session"""

    player_name: Optional[str] = None
    seed: Optional[int] = None


class ShopRefreshRequest(BaseModel):
    """Request to refresh shop items"""

    player_id: str


class SimpleBattleRequest(BaseModel):
    """Simple battle request with just player ID"""

    player_id: str
    seed: Optional[int] = None  # For deterministic testing
    test_ai_difficulty: Optional[
        int
    ] = None  # AI difficulty for testing (test mode only)


class PurchaseRequest(BaseModel):
    """Request to purchase an item"""

    player_id: str
    item_id: str
    target_position: Optional[Position] = None  # [x, y] position on grid
    to_storage: bool = False  # Place in storage instead of grid


class SellRequest(BaseModel):
    """Request to sell an item"""

    player_id: str
    item_uid: str  # Unique ID of the placed item


class MoveItemRequest(BaseModel):
    """Request to move an item to a new position or storage"""

    player_id: str
    item_uid: str  # Unique instance ID of the item to move
    to_location: Union[str, Position]  # "storage" or [x, y] coordinates


# ============ Response Models ============


class StartSessionResponse(BaseModel):
    """Response when starting a new game session"""

    player_id: str = Field(description="Unique player/session identifier")
    player_name: str = Field(description="Player's display name")
    session: GameSession = Field(description="Complete game session state")


class PurchaseResponse(BaseModel):
    """Response after purchasing an item"""

    purchased_item: ShopItem = Field(description="The item that was purchased")
    gold: int = Field(description="Remaining gold after purchase")
    server_containers: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Updated server containers list (when purchasing a container)",
    )


class PlacedItem(BaseModel):
    """Item placed on the grid during battle"""

    id: str = Field(description="Unique item instance ID")
    slug: str = Field(description="Unique item slug")
    item_type: str = Field(description="Item type identifier")
    name: str = Field(description="Display name")
    position: Position = Field(description="[x, y] grid position")
    category: str = Field(description="Item category")
    shape: List[List[int]] = Field(description="Shape as list of [x, y] offsets")
    # Additional fields for tooltips
    rarity: str = Field(default="", description="Item rarity tier")
    cost: int = Field(default=0, description="Item value/cost")
    min_damage: int = Field(default=0, description="Minimum damage dealt")
    max_damage: int = Field(default=0, description="Maximum damage dealt")
    min_heal: int = Field(default=0, description="Minimum healing amount")
    max_heal: int = Field(default=0, description="Maximum healing amount")
    cooldown: float = Field(default=0.0, description="Activation cooldown in seconds")
    cpu_cost: int = Field(default=0, description="CPU cost to activate")
    special_effect: str = Field(default="", description="Special effect description")
    block_amount: int = Field(default=0, description="Damage blocked")
    description: str = Field(default="", description="Item description")


class ServerContainer(BaseModel):
    """Server container information"""

    id: str = Field(description="Container instance ID")
    slug: str = Field(description="Container slug")
    type: str = Field(description="Container type")
    position: Position = Field(description="[x, y] position")
    width: int = Field(description="Container width")
    height: int = Field(description="Container height")


class InventoryData(BaseModel):
    """Player or enemy inventory during battle"""

    items: List[PlacedItem] = Field(description="Items on the grid")
    servers: List[ServerContainer] = Field(description="Server containers")


class BattleAction(BaseModel):
    """Single action in battle timeline"""

    timestamp: int = Field(description="Time in milliseconds")
    source: str = Field(description="Item that triggered the action")
    action: str = Field(description="Action type")
    target: Optional[str] = Field(description="Target item")
    damage: Optional[int] = Field(description="Damage dealt")
    player: int = Field(description="Player 1 or 2")
    details: Optional[Dict[str, Any]] = Field(description="Additional details")


class BattleResult(BaseModel):
    """Detailed battle outcome"""

    winner: int = Field(description="Winner (1=player, 2=opponent)")
    duration: float = Field(description="Battle duration in seconds")
    player1_quota: int = Field(description="Player 1 remaining quota")
    player2_quota: int = Field(description="Player 2 remaining quota")
    actions: List[BattleAction] = Field(description="Battle timeline")
    seed: int = Field(description="Battle RNG seed")
    player_inventory: InventoryData = Field(description="Player's battle inventory")
    enemy_inventory: InventoryData = Field(description="Enemy's battle inventory")
    opponent_name: str = Field(default="AI Opponent", description="Opponent's name")
    opponent_type: str = Field(default="ai", description="Type: ai or player_ghost")


class SessionUpdate(BaseModel):
    """Session changes after battle"""

    round: int = Field(description="Current round number")
    gold: int = Field(description="Current gold amount")
    gold_earned: int = Field(description="Gold earned this round")
    wins: int = Field(description="Total wins")
    losses: int = Field(description="Total losses")
    lives: int = Field(description="Remaining lives")
    game_over: bool = Field(description="Whether game has ended")
    victory: bool = Field(description="Whether player achieved victory")


class BattleResponse(BaseModel):
    """Response after simulating a battle"""

    battle_result: BattleResult = Field(description="Complete battle details")
    session_update: SessionUpdate = Field(description="Session state changes")
    new_shop: List[Optional[ShopItem]] = Field(
        description="New shop items for next round"
    )
    battle_id: str = Field(description="Unique battle identifier")


class HealthResponse(BaseModel):
    """Health check response"""

    status: str = Field(description="Service health status")
    database: str = Field(description="Database connection status")
    environment: str = Field(description="Current environment")
    test_mode: bool = Field(description="Whether in test mode")
    version: str = Field(description="Server version")


class ShopRefreshResponse(BaseModel):
    """Response after refreshing shop"""

    shop: List[Optional[ShopItem]] = Field(description="New shop items")
    gold: int = Field(description="Remaining gold after refresh cost")


class SellResponse(BaseModel):
    """Response after selling an item"""

    gold_gained: int = Field(description="Gold gained from sale")
    gold: int = Field(description="Total gold after sale")
    sold_item: Dict[str, Any] = Field(description="The item that was sold")


class ItemInfo(BaseModel):
    """Basic item information for move responses"""

    id: str = Field(description="Item unique ID")
    item_type: str = Field(description="Item type identifier")
    position: Optional[Position] = Field(
        description="Current position or None if in storage"
    )
    name: Optional[str] = Field(description="Item name")


class MoveItemResponse(BaseModel):
    """Response after moving an item"""

    inventory_grid: List[Dict[str, Any]] = Field(description="Updated grid inventory")
    inventory_storage: List[Dict[str, Any]] = Field(description="Updated storage")
    item: ItemInfo = Field(description="Moved item information")


class LeaderboardEntry(BaseModel):
    """Single leaderboard entry"""

    player_id: str = Field(description="Player identifier")
    round: int = Field(description="Current round")
    wins: int = Field(description="Total wins")
    losses: int = Field(description="Total losses")
    win_rate: float = Field(description="Win percentage")
    score: int = Field(description="Calculated score")


class LeaderboardResponse(BaseModel):
    """Leaderboard response"""

    entries: List[LeaderboardEntry] = Field(description="Top players")


class BattleHistoryEntry(BaseModel):
    """Single battle history record"""

    id: int = Field(description="Battle ID")
    player1_id: str = Field(description="Player 1 ID")
    player2_id: Optional[str] = Field(description="Player 2 ID or None for AI")
    round_number: int = Field(description="Round when battle occurred")
    winner: int = Field(description="Winner (1 or 2)")
    battle_data: Dict[str, Any] = Field(description="Battle replay data")
    created_at: Optional[str] = Field(description="Timestamp")


class BattleHistoryResponse(BaseModel):
    """Battle history response"""

    battles: List[BattleHistoryEntry] = Field(description="Recent battles")
