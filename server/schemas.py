"""
Pydantic schemas for API request/response models
"""

from typing import Dict, List, Optional, Union

from pydantic import BaseModel


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
    round_number: int
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
