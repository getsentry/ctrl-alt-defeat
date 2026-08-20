"""
Pydantic schemas for API request/response models
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from containers import Container
from grid_system import Rotation
from items import Item, PlacedItem
from utils import Position


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
    current_shop: List[Optional[Item]] = []  # Shop can have empty slots after purchases
    game_seed: int  # Master seed for all RNG in this game session (always set)
    shop_refresh_count: int = 0  # Track number of shop refreshes for seed variation
    # Inventory fields
    # What the rack is part or all of the way towards combining. Worked out
    # from the grid rather than stored: it is a view of the items, not a fact
    # about the session, and it is left empty by anything that does not need it.
    pending: List["Pending"] = []
    inventory_grid: List[PlacedItem] = []  # Items on the grid, each with a position
    inventory_storage: List[Item] = []  # Items in the chest, not used in battle
    server_containers: List[Container] = []  # Containers the player owns


class StartSessionRequest(BaseModel):
    """Request to start a new game session"""

    player_name: Optional[str] = None
    seed: Optional[int] = None


class ShopRefreshRequest(BaseModel):
    """Request to refresh shop items"""


class SimpleBattleRequest(BaseModel):
    """Request to simulate a battle"""

    seed: Optional[int] = None  # For deterministic testing
    test_ai_difficulty: Optional[
        int
    ] = None  # AI difficulty for testing (test mode only)


class PurchaseRequest(BaseModel):
    """Request to purchase an item"""

    item_id: str
    target_position: Optional[Position] = None  # [x, y] position on grid
    to_storage: bool = False  # Place in storage instead of grid
    rotation: Rotation = Field(
        default=Rotation.NONE,
        description="Which way the item faces when it lands. An item can be "
        "turned while it is being carried out of the shop.",
    )

class SellRequest(BaseModel):
    """Request to sell an item"""

    item_id: str  # Unique ID of the placed item


class MoveItemRequest(BaseModel):
    """Request to move an item to a new position or storage"""

    item_id: str  # Unique instance ID of the item to move
    to_location: Union[str, Position]  # "storage" or [x, y] coordinates
    rotation: Rotation = Field(
        default=Rotation.NONE,
        description="Which way the item faces when it lands. An item may be "
        "turned while it is held, and a move is when that is settled.",
    )


class RackRequest(BaseModel):
    """What to stand on the player's rack. TEST MODE ONLY.

    A test that wants two particular items together cannot buy them: the shop
    offers what the seed says it offers. So it says what it wants instead, and
    the server puts it there as if it had been bought.
    """

    player_id: str = Field(description="Whose rack to stand them on")
    items: List["RackItem"]


class RackItem(BaseModel):
    item_type: str = Field(description="Catalogue slug of the item to stand")
    position: Position = Field(description="The square it stands on")
    rotation: Rotation = Field(default=Rotation.NONE)


# ============ Response Models ============


class StartSessionResponse(BaseModel):
    """Response when starting a new game session"""

    player_id: str = Field(description="Unique player/session identifier")
    player_name: str = Field(description="Player's display name")
    session: GameSession = Field(description="Complete game session state")


class PurchaseResponse(BaseModel):
    """Response after purchasing an item"""

    purchased_item: Item = Field(description="The item that was purchased")
    gold: int = Field(description="Remaining gold after purchase")
    pending: List["Pending"] = Field(
        default_factory=list, description="What the rack is on the way to combining"
    )
    server_containers: List[Container] = Field(
        description="The containers the player owns after the purchase"
    )


class InventoryData(BaseModel):
    """Player or enemy inventory during battle"""

    items: List[PlacedItem] = Field(description="Items on the grid")
    servers: List[Container] = Field(description="Server containers")


class BattleActionName(str, Enum):
    """
    Everything that can happen in a battle.

    The client matches these names, so the set is the contract between the two.
    A name added here has to be added to the client's processor as well, or the
    client will not act on it.
    """

    BATTLE_START = "battle_start"
    DAMAGE = "damage"
    CRITICAL_HIT = "critical_hit"
    MISS = "miss"
    HEAL = "heal"
    BLOCK = "block"
    BUFF = "buff"
    DEBUFF = "debuff"
    DOT = "dot"
    CONSUME = "consume"
    CPU_FAIL = "cpu_fail"
    CPU_DRAIN = "cpu_drain"
    CLEANSE = "cleanse"
    GAIN_DAMAGE = "gain_damage"
    SPEND = "spend"
    STUN = "stun"
    RESIST = "resist"
    REFLECT = "reflect"
    PLAYER_MODIFY = "player_modify"
    PLAYER_DEFEATED = "player_defeated"


class BattleAction(BaseModel):
    """Single action in battle timeline"""

    timestamp: int = Field(description="Time in milliseconds")
    source: str = Field(description="Item that triggered the action")
    action: BattleActionName = Field(description="What happened")
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


class Combination(BaseModel):
    """One crafting that happened when the shop phase began (GDD 5.3).

    A record of something already done. The inventory in this response is what
    the rack holds now; this says how it got that way, so the client can show
    it happening. A client that ignores every one of these still draws the right
    rack -- it simply cuts to the result.

    The consumed items no longer exist by the time this is read, so they travel
    whole. Naming their types would not be enough: the client has no catalogue
    to look a name up in, and with two of a kind on the rack it could not tell
    which two were eaten.
    """

    made: str = Field(description="Item type the combination produced")
    made_id: str = Field(description="Id of the item that was made")
    consumed: List[PlacedItem] = Field(
        description="The items used up, as they stood before combining"
    )
    kept: List[PlacedItem] = Field(
        description="Catalysts, needed but not used up. Still on the grid."
    )
    freed: List[Position] = Field(
        description="Squares the ingredients stood on, to play the merge over"
    )
    position: Optional[Position] = Field(
        default=None,
        description="Where the result landed, null if it went to the chest",
    )


class CombiningPartners(BaseModel):
    """Which item types go together in a recipe, for the whole catalogue.

    Sent once. It says nothing about any particular rack: whether a combination
    will actually happen depends on rules that stay on the server, and is
    answered by `pending`.
    """

    partners: Dict[str, List[str]] = Field(
        description="Item type to the types it appears in a recipe with"
    )
    names: Dict[str, str] = Field(
        description=(
            "Item type to the name to show for it. The client holds no "
            "catalogue, so a slug it has never been sent an item of -- what a "
            "recipe makes, or a part it is still missing -- has no name "
            "without this."
        )
    )


class Pending(BaseModel):
    """A recipe the rack is part or all of the way towards (GDD 5.3).

    `have` of `need` parts are there and touching each other. Equal means it
    will combine when the battle starts, which is the glow to draw. Fewer means
    it is the progress to label a part with -- "Long Poll 2/3" -- so the player
    can see what they are collecting towards.

    Ids, because the client is looking at those items. The complete ones are
    read from the same plan the combining uses, so the warning and the event
    cannot say different things.
    """

    makes: str = Field(description="Item type it would produce")
    have: int = Field(description="Parts present and touching")
    need: int = Field(description="Parts the recipe wants")
    ingredients: List[str] = Field(description="Ids present that would be used up")
    catalysts: List[str] = Field(description="Ids present that are needed and kept")
    missing: List[str] = Field(
        default_factory=list, description="Item types still wanted"
    )


class InventoryAfterBattle(BaseModel):
    """What the player holds once the battle is over and things have combined.

    The same three names the session uses, so whatever reads a session can read
    this. It is here because combining changes the rack and nothing else in the
    response says so: `battle_result.player_inventory` is the rack that fought.
    """

    inventory_grid: List[PlacedItem] = Field(description="Items on the grid")
    inventory_storage: List[Item] = Field(description="Items in the chest")
    server_containers: List[Container] = Field(description="Containers on the grid")


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
    combinations: List[Combination] = Field(
        default_factory=list,
        description="Items that combined as the next shop phase began",
    )
    pending: List[Pending] = Field(
        default_factory=list,
        description=(
            "What the rack is on the way to combining now, after this round's "
            "combining. A chain takes a round for each step, so a rack that "
            "just combined is often already about to combine again."
        ),
    )


class BattleResponse(BaseModel):
    """Response after simulating a battle"""

    battle_result: BattleResult = Field(description="Complete battle details")
    session_update: SessionUpdate = Field(description="Session state changes")
    inventory: InventoryAfterBattle = Field(
        description=(
            "What the player holds now, after any combining. Not the same as "
            "battle_result.player_inventory, which is the rack that fought, and "
            "so is the rack as it was before combining."
        )
    )
    new_shop: List[Optional[Item]] = Field(description="New shop items for next round")
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

    shop: List[Optional[Item]] = Field(description="New shop items")
    gold: int = Field(description="Remaining gold after refresh cost")


class SellResponse(BaseModel):
    """Response after selling an item"""

    gold_gained: int = Field(description="Gold gained from sale")
    gold: int = Field(description="Total gold after sale")
    pending: List["Pending"] = Field(
        default_factory=list, description="What the rack is on the way to combining"
    )
    sold_item: Item = Field(description="The item that was sold")


class MoveItemResponse(BaseModel):
    """Response after moving an item"""

    inventory_grid: List[PlacedItem] = Field(description="Updated grid inventory")
    inventory_storage: List[Item] = Field(description="Updated chest contents")
    pending: List[Pending] = Field(
        default_factory=list, description="What the rack is on the way to combining"
    )
    server_containers: List[Container] = Field(
        default_factory=list, description="Updated containers"
    )


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
