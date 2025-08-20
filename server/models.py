"""
Database models for game session persistence using SQLAlchemy
"""

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class GameSession(Base):
    """Database model for persisting game sessions"""

    __tablename__ = "game_sessions"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Legacy player_id for backward compatibility
    player_id = Column(String, unique=True, index=True, nullable=False)
    player_name = Column(String, nullable=False, default="Player")

    # User association - one active game session per user
    user_id = Column(
        Integer, ForeignKey("users.id"), unique=True, nullable=False, index=True
    )
    game_version = Column(String(20), default="1.0.0", nullable=False)
    session_token = Column(String(255), nullable=True)

    # Core game state
    round = Column(Integer, default=1, nullable=False)
    gold = Column(Integer, default=12, nullable=False)
    lives = Column(Integer, default=5, nullable=False)
    wins = Column(Integer, default=0, nullable=False)
    losses = Column(Integer, default=0, nullable=False)

    # RNG and shop
    game_seed = Column(Integer, nullable=False)
    shop_refresh_count = Column(Integer, default=0, nullable=False)

    # Complex nested data stored as JSON
    last_battle_result = Column(JSON, nullable=True)
    current_shop = Column(JSON, default=list, nullable=False)

    # Inventory state (stored as JSON for flexibility)
    inventory_grid = Column(JSON, default=list, nullable=False)
    inventory_slots = Column(JSON, default=list, nullable=False)
    inventory_storage = Column(JSON, default=list, nullable=False)
    placed_items = Column(JSON, default=list, nullable=False)
    server_containers = Column(JSON, default=list, nullable=False)

    # Timestamps for session management
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    last_activity = Column(DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self) -> dict:
        """Convert database model to dictionary for API responses"""
        return {
            "player_id": self.player_id,
            "player_name": self.player_name,
            "round": self.round,
            "gold": self.gold,
            "lives": self.lives,
            "wins": self.wins,
            "losses": self.losses,
            "game_seed": self.game_seed,
            "shop_refresh_count": self.shop_refresh_count,
            "last_battle_result": self.last_battle_result,
            "current_shop": self.current_shop or [],
            "inventory_grid": self.inventory_grid or [],
            "inventory_slots": self.inventory_slots or [],
            "inventory_storage": self.inventory_storage or [],
            "placed_items": self.placed_items or [],
            "server_containers": self.server_containers or [],
        }

    def update_from_dict(self, data: dict) -> None:
        """Update model from dictionary (e.g., from Pydantic model)"""
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.last_activity = datetime.utcnow()


class BattleHistory(Base):
    """Database model for storing battle history"""

    __tablename__ = "battle_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    player1_id = Column(String, index=True, nullable=False)
    player2_id = Column(String, nullable=True)  # Null for AI battles
    round_number = Column(Integer, nullable=False)
    winner = Column(Integer, nullable=False)  # 1 or 2
    battle_data = Column(JSON, nullable=False)  # Full battle replay data
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "player1_id": self.player1_id,
            "player2_id": self.player2_id,
            "round_number": self.round_number,
            "winner": self.winner,
            "battle_data": self.battle_data,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class User(Base):
    """Database model for user accounts"""

    __tablename__ = "users"

    # Identity
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(
        String(32), unique=True, nullable=False, index=True
    )  # Generated for guests
    display_name = Column(String(64), nullable=True)

    # Account type and status
    account_type = Column(
        String(20), default="guest", nullable=False
    )  # 'guest', 'registered'
    account_status = Column(String(20), default="active", nullable=False)  # 'active'

    # Authentication (for registered users)
    email = Column(String(255), unique=True, nullable=True, index=True)
    password_hash = Column(String(255), nullable=True)

    # Stats
    total_games_played = Column(Integer, default=0, nullable=False)
    total_wins = Column(Integer, default=0, nullable=False)
    total_losses = Column(Integer, default=0, nullable=False)
    current_rank = Column(Integer, default=1000, nullable=False)  # ELO-style rating

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    last_login_at = Column(DateTime, nullable=True)

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "username": self.username,
            "display_name": self.display_name or self.username,
            "account_type": self.account_type,
            "account_status": self.account_status,
            "email": self.email,
            "total_games_played": self.total_games_played,
            "total_wins": self.total_wins,
            "total_losses": self.total_losses,
            "current_rank": self.current_rank,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login_at": self.last_login_at.isoformat()
            if self.last_login_at
            else None,
        }


class PlayerBuild(Base):
    """Database model for player build snapshots used in matchmaking"""

    __tablename__ = "player_builds"

    # Identity
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    player_name = Column(String(64), nullable=False)

    # Game context
    game_version = Column(String(20), nullable=False, index=True)
    game_session_id = Column(String(255), nullable=True)

    # Match criteria
    round_number = Column(Integer, nullable=False, index=True)
    wins = Column(Integer, nullable=False)
    losses = Column(Integer, nullable=False)
    win_percent = Column(Float, nullable=False, index=True)  # Denormalized for indexing
    current_lives = Column(Integer, nullable=False)

    # Build data
    inventory_snapshot = Column(JSON, nullable=False)  # Full inventory grid
    server_containers = Column(JSON, nullable=False)  # Container configuration
    total_item_value = Column(Integer, nullable=False)
    total_item_count = Column(Integer, nullable=False)

    # Battle outcome
    battle_won = Column(Boolean, nullable=False)  # Did this build win its battle?
    opponent_type = Column(String(20), nullable=False)  # 'ai' or 'player'
    opponent_difficulty = Column(Integer, nullable=True)  # For AI opponents

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Composite index for efficient matchmaking queries
    __table_args__ = (
        Index(
            "idx_matchmaking",
            "game_version",
            "round_number",
            "win_percent",
            "created_at",
        ),
    )

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses"""
        return {
            "build_id": self.build_id,
            "user_id": self.user_id,
            "player_name": self.player_name,
            "game_version": self.game_version,
            "game_session_id": self.game_session_id,
            "round_number": self.round_number,
            "wins": self.wins,
            "losses": self.losses,
            "win_percent": self.win_percent,
            "current_lives": self.current_lives,
            "inventory_snapshot": self.inventory_snapshot,
            "server_containers": self.server_containers,
            "total_item_value": self.total_item_value,
            "total_item_count": self.total_item_count,
            "battle_won": self.battle_won,
            "opponent_type": self.opponent_type,
            "opponent_difficulty": self.opponent_difficulty,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class MatchmakingHistory(Base):
    """Database model for tracking matchmaking history to prevent repeat matches"""

    __tablename__ = "matchmaking_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    player_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    opponent_build_id = Column(Integer, ForeignKey("player_builds.id"), nullable=False)
    matched_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Prevent matching same opponent too frequently
    __table_args__ = (
        UniqueConstraint(
            "player_user_id", "opponent_build_id", name="unique_recent_match"
        ),
        Index("idx_player_history", "player_user_id", "matched_at"),
    )

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "player_user_id": self.player_user_id,
            "opponent_build_id": self.opponent_build_id,
            "matched_at": self.matched_at.isoformat() if self.matched_at else None,
        }
