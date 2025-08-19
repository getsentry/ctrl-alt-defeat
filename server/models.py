"""
Database models for game session persistence using SQLAlchemy
"""

from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Integer, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class GameSessionDB(Base):
    """Database model for persisting game sessions"""

    __tablename__ = "game_sessions"

    # Primary key
    player_id = Column(String, primary_key=True, index=True)

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


class BattleHistoryDB(Base):
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
