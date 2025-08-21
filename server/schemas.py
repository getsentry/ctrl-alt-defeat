"""
Pydantic schemas for API request/response models
"""

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class GameSession(BaseModel):
    """Player's current game session"""

    player_id: str
    player_name: str = "Player"
    round: int = 1
    gold: int = 12  # Start with 12g for round 1
    lives: int = 5  # Player has 5 lives/tries
    wins: int = 0
    losses: int = 0
    last_battle_result: Optional[Dict] = None
    current_shop: List[Optional[Dict]] = []  # Shop can have empty slots
    game_seed: int  # Master seed for all RNG in this game session (always set)
    shop_refresh_count: int = 0  # Track number of shop refreshes for seed variation
    # Inventory fields
    inventory_grid: List[Dict] = []  # Items placed on the grid
    inventory_slots: List[Dict] = []  # Inventory slots (legacy compatibility)
    inventory_storage: List[Dict] = []  # Items in storage (not used in battle)
    placed_items: List[Dict] = []  # Quick reference to items on grid
    server_containers: List[Dict] = []  # Server container positions and info


class StartSessionRequest(BaseModel):
    """Request to start a new game session"""

    player_name: str
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
    target_position: Optional[List[int]] = None  # [x, y] position on grid
    target_container_id: Optional[str] = None  # Container to place item in
    to_storage: bool = False  # Place in storage instead of grid


class SellRequest(BaseModel):
    """Request to sell an item"""

    player_id: str
    item_uid: str  # Unique ID of the placed item


class MoveItemRequest(BaseModel):
    """Request to move an item to a new position or storage"""

    player_id: str
    item_uid: str  # Unique instance ID of the item to move
    to_location: Union[str, List[int]]  # "storage" or [x, y] coordinates


# ============ Response Models ============


class ItemCatalogEntry(BaseModel):
    """Simplified item info for client catalog"""

    name: str
    category: str
    rarity: str
    min_damage: int = Field(default=0, description="Minimum damage dealt")
    max_damage: int = Field(default=0, description="Maximum damage dealt")
    cooldown: float = Field(default=0, description="Cooldown in seconds")
    cpu_cost: int = Field(default=0, description="CPU cost to trigger")
    special_effect: str = Field(default="", description="Special effect description")


class StartSessionResponse(BaseModel):
    """Response when starting a new game session"""

    player_id: str = Field(description="Unique player/session identifier")
    session: GameSession = Field(description="Complete game session state")
    item_catalog: Dict[str, ItemCatalogEntry] = Field(
        description="Catalog of all available items with their stats"
    )


class ShopItem(BaseModel):
    """Item available in the shop"""

    id: str = Field(description="Unique item instance ID")
    item_type: str = Field(description="Item type identifier")
    name: str = Field(description="Display name")
    category: str = Field(description="Item category")
    rarity: str = Field(description="Item rarity tier")
    cost: int = Field(description="Gold cost to purchase")
    is_container: bool = Field(
        default=False, description="Whether this is a server container"
    )
    internal_width: Optional[int] = Field(
        default=None, description="Container internal width"
    )
    internal_height: Optional[int] = Field(
        default=None, description="Container internal height"
    )
    min_damage: int = Field(default=0, description="Minimum damage")
    max_damage: int = Field(default=0, description="Maximum damage")
    cooldown: float = Field(default=0, description="Cooldown in seconds")
    cpu_cost: int = Field(default=0, description="CPU cost")
    special_effect: str = Field(default="", description="Special effect")


class PurchaseResponse(BaseModel):
    """Response after purchasing an item"""

    success: bool = Field(description="Whether purchase was successful")
    purchased_item: ShopItem = Field(description="The item that was purchased")
    gold: int = Field(description="Remaining gold after purchase")


class PlacedItem(BaseModel):
    """Item placed on the grid during battle"""

    id: str = Field(description="Unique item instance ID")
    item_type: str = Field(description="Item type identifier")
    name: str = Field(description="Display name")
    position: List[int] = Field(description="[x, y] grid position")
    category: str = Field(description="Item category")
    shape: List[List[int]] = Field(description="Shape as list of [x, y] offsets")


class ServerContainer(BaseModel):
    """Server container information"""

    id: str = Field(description="Container instance ID")
    type: str = Field(description="Container type")
    position: List[int] = Field(description="[x, y] position")
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
    target: Optional[str] = Field(default=None, description="Target item")
    damage: Optional[int] = Field(default=None, description="Damage dealt")
    player: int = Field(description="Player 1 or 2")
    details: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional details"
    )


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
