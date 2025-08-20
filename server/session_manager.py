"""
Session management layer for game sessions
Handles database operations and provides a clean interface for the API
"""

import random
from datetime import datetime, timedelta
from typing import List, Optional

from database import db_manager  # noqa: F401
from models import BattleHistory, GameSession, User
from schemas import GameSession as GameSessionPydantic
from sqlalchemy import delete, select, text


class SessionManager:
    """Manages game sessions with database persistence"""

    def __init__(self, db_host: Optional[str] = None, db_name: Optional[str] = None):
        self.db_host = db_host
        self.db_name = db_name
        self._initialized = False

    async def initialize(self):
        """Initialize the session manager and database"""
        if self._initialized:
            return

        # Re-initialize db_manager with custom config if provided
        if self.db_host or self.db_name:
            from database import DatabaseManager

            global db_manager
            db_manager = DatabaseManager(self.db_host, self.db_name)

        await db_manager.initialize()

        # Verify database is working
        if not await db_manager.health_check():
            raise RuntimeError("Database health check failed - PostgreSQL is required")

        self._initialized = True

    async def _get_user(self, user_id: str) -> Optional[User]:
        """Get a user by ID"""
        async with db_manager.get_session() as db:
            # user_id is the actual user.id from the database
            try:
                user_id_int = int(user_id)
                result = await db.execute(select(User).where(User.id == user_id_int))
                return result.scalar_one_or_none()
            except (ValueError, TypeError):
                # Invalid user_id format
                return None

    async def create_session(
        self, player_id: str, game_seed: Optional[int] = None
    ) -> GameSessionPydantic:
        """Create a new game session

        Args:
            player_id: The user ID (as string) for this session, or a temporary ID for guest users
            game_seed: Optional seed for deterministic gameplay
        """
        # Generate seed if not provided
        if game_seed is None:
            game_seed = random.randint(0, 1000000)

        # Try to get the user by ID first
        user = await self._get_user(player_id)

        # If no user found, create a guest user
        if not user:
            async with db_manager.get_session() as db:
                import uuid

                username = f"Guest_{uuid.uuid4().hex[:8]}_{random.randint(1000, 9999)}"
                user = User(
                    username=username,
                    display_name=f"Player_{player_id[:8]}",
                    account_type="guest",
                    account_status="active",
                    total_games_played=0,
                    total_wins=0,
                    total_losses=0,
                    current_rank=1000,
                )
                db.add(user)
                await db.commit()
                await db.refresh(user)

            # Update player_id to be the actual user ID
            player_id = str(user.id)

        # Create session with starting values
        from shop_generation import generate_shop_items

        # Initialize server containers (3 standard VMs)
        server_containers = [
            {
                "id": "container_a",
                "type": "standard_vm",
                "position": [2, 3],
                "width": 2,
                "height": 2,
            },
            {
                "id": "container_b",
                "type": "standard_vm",
                "position": [4, 3],
                "width": 2,
                "height": 2,
            },
            {
                "id": "container_c",
                "type": "standard_vm",
                "position": [6, 3],
                "width": 2,
                "height": 2,
            },
        ]

        session = GameSessionPydantic(
            player_id=player_id,  # This is now the actual user.id
            player_name=user.display_name or user.username,
            round=1,
            gold=12,  # Starting gold from game design
            lives=5,
            wins=0,
            losses=0,
            inventory_grid=[],
            inventory_slots=[],
            current_shop=generate_shop_items(1, game_seed),
            last_battle_result=None,
            game_seed=game_seed,
            shop_refresh_count=0,
            inventory_storage=[],
            placed_items=[],
            server_containers=server_containers,
        )

        # Save to database
        async with db_manager.get_session() as db:
            # Create database model
            db_session = GameSession(
                player_id=player_id,
                player_name=session.player_name,
                user_id=user.id,  # Link to the guest user
                round=session.round,
                gold=session.gold,
                lives=session.lives,
                wins=session.wins,
                losses=session.losses,
                inventory_grid=session.inventory_grid,
                inventory_slots=session.inventory_slots,
                inventory_storage=session.inventory_storage,
                placed_items=session.placed_items,
                server_containers=session.server_containers,
                current_shop=session.current_shop,
                last_battle_result=session.last_battle_result,
                game_seed=game_seed,
                shop_refresh_count=session.shop_refresh_count,
            )
            db.add(db_session)
            await db.commit()
            print(f"Session saved to database for player {player_id}")

        return session

    async def get_session(self, player_id: str) -> Optional[GameSessionPydantic]:
        """Get a session by player ID"""
        async with db_manager.get_session() as db:
            result = await db.execute(
                select(GameSession).where(GameSession.player_id == player_id)
            )
            db_session = result.scalar_one_or_none()

            if db_session:
                # Update last activity
                db_session.last_activity = datetime.utcnow()
                await db.commit()
                return GameSessionPydantic.model_validate(db_session.to_dict())

            return None

    async def update_session(self, session: GameSessionPydantic) -> bool:
        """Update an existing session"""
        async with db_manager.get_session() as db:
            result = await db.execute(
                select(GameSession).where(GameSession.player_id == session.player_id)
            )
            db_session = result.scalar_one_or_none()

            if db_session:
                # Update fields
                db_session.round = session.round
                db_session.gold = session.gold
                db_session.lives = session.lives
                db_session.wins = session.wins
                db_session.losses = session.losses
                db_session.inventory_grid = session.inventory_grid
                db_session.inventory_slots = session.inventory_slots
                db_session.inventory_storage = session.inventory_storage
                db_session.placed_items = session.placed_items
                db_session.server_containers = session.server_containers
                db_session.current_shop = session.current_shop
                db_session.last_battle_result = session.last_battle_result
                db_session.shop_refresh_count = session.shop_refresh_count
                db_session.last_activity = datetime.utcnow()

                await db.commit()
                return True

            return False

    async def save_or_update_session(self, session: GameSessionPydantic) -> None:
        """Save or update a session"""
        player_id = session.player_id

        async with db_manager.get_session() as db:
            # Check if session exists
            result = await db.execute(
                select(GameSession).where(GameSession.player_id == player_id)
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Update existing session
                existing.update_from_dict(session.model_dump())
                db_session = existing
            else:
                # Create new session
                db_session = GameSession(**session.model_dump())
                db.add(db_session)

            await db.commit()

    async def delete_session(self, player_id: str) -> bool:
        """Delete a session"""
        async with db_manager.get_session() as db:
            result = await db.execute(
                delete(GameSession).where(GameSession.player_id == player_id)
            )
            await db.commit()
            return result.rowcount > 0

    async def list_active_sessions(self) -> List[str]:
        """List all active session IDs"""
        async with db_manager.get_session() as db:
            result = await db.execute(select(GameSession.player_id))
            return [row[0] for row in result.fetchall()]

    async def cleanup_old_sessions(self, hours: int = 24):
        """Remove sessions that haven't been active for X hours"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        async with db_manager.get_session() as db:
            result = await db.execute(
                delete(GameSession).where(GameSession.last_activity < cutoff)
            )
            await db.commit()
            return result.rowcount

    async def save_battle_history(
        self,
        player1_id: str,
        player2_id: Optional[str],
        round_number: int,
        winner: int,
        battle_data: dict,
    ):
        """Save battle history to database"""
        async with db_manager.get_session() as db:
            battle = BattleHistory(
                player1_id=player1_id,
                player2_id=player2_id,
                round_number=round_number,
                winner=winner,
                battle_data=battle_data,
            )
            db.add(battle)
            await db.commit()

    async def get_battle_history(self, player_id: str, limit: int = 10) -> List[dict]:
        """Get recent battle history for a player"""
        async with db_manager.get_session() as db:
            result = await db.execute(
                select(BattleHistory)
                .where(BattleHistory.player1_id == player_id)
                .order_by(BattleHistory.created_at.desc())
                .limit(limit)
            )
            battles = result.scalars().all()
            return [battle.to_dict() for battle in battles]

    async def reset_database(self):
        """Reset database to clean state - TEST MODE ONLY

        WARNING: This will delete ALL data in the database!
        """
        import os

        if os.environ.get("TEST_MODE") != "true":
            raise RuntimeError("Database reset only allowed in TEST_MODE")

        async with db_manager.get_session() as db:
            # Try TRUNCATE first (faster)
            try:
                await db.execute(text("TRUNCATE TABLE game_sessions CASCADE"))
                await db.execute(text("TRUNCATE TABLE battle_history CASCADE"))
                await db.commit()
                print("Database reset using TRUNCATE")
            except Exception as e:
                print(f"Failed to reset database with TRUNCATE: {e}")
                # Try DELETE as fallback (works with more databases)
                try:
                    await db.execute(delete(BattleHistory))
                    await db.execute(delete(GameSession))
                    await db.commit()
                    print("Database reset using DELETE")
                except Exception as e2:
                    print(f"Failed to reset database with DELETE: {e2}")
                    raise


# Global session manager instance
session_manager = SessionManager()
