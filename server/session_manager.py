"""
Session management layer for game sessions
Handles database operations and provides a clean interface for the API
"""

import logging
import random
from datetime import timedelta
from typing import List, Optional

from containers import starting_containers
from database import db_manager  # noqa: F401
from models import BattleHistory, GameSession, User
from schemas import GameSession as GameSessionPydantic
from sqlalchemy import delete, select, text
from utils import dump_all, utc_now

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages game sessions with database persistence"""

    def __init__(self):
        self._initialized = False

    async def initialize(self):
        """Initialize the session manager and database"""
        if self._initialized:
            return

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
        self,
        player_id: str,
        game_seed: Optional[int] = None,
    ) -> GameSessionPydantic:
        """Create a new game session

        Args:
            player_id: The user ID (as string) for this session, or a temporary ID for guest users
            game_seed: Optional seed for deterministic gameplay

        The player's name is not an argument. It belongs to the account, and
        the session reads it from there.
        """
        # Generate seed if not provided
        if game_seed is None:
            game_seed = random.randint(0, 1000000)

        # Try to get the user by ID first
        user = await self._get_user(player_id)

        # If no user found, create a guest user. This is the path a token that
        # outlived its account takes.
        if not user:
            from auth_endpoints import insert_generated_guest

            async with db_manager.get_session() as db:
                user = await insert_generated_guest(db)

            # Update player_id to be the actual user ID
            player_id = str(user.id)

        # Create session with starting values
        from main import ROUND_GOLD, generate_shop_items

        session = GameSessionPydantic(
            player_id=player_id,  # This is now the actual user.id
            player_name=user.username,
            round=1,
            gold=ROUND_GOLD[0],  # Round one's gold, per Backpack Battles
            lives=5,
            wins=0,
            losses=0,
            inventory_grid=[],
            current_shop=generate_shop_items(1, game_seed),
            last_battle_result=None,
            game_seed=game_seed,
            shop_refresh_count=0,
            inventory_storage=[],
            server_containers=starting_containers(),
        )

        # Save to database
        async with db_manager.get_session() as db:
            # Check if session already exists for this player
            from sqlalchemy import select

            result = await db.execute(
                select(GameSession).where(GameSession.player_id == player_id)
            )
            existing_session = result.scalar_one_or_none()

            if existing_session:
                # Update existing session with new values
                existing_session.player_name = session.player_name
                existing_session.user_id = user.id
                existing_session.round = session.round
                existing_session.gold = session.gold
                existing_session.lives = session.lives
                existing_session.wins = session.wins
                existing_session.losses = session.losses
                existing_session.inventory_grid = dump_all(session.inventory_grid)
                existing_session.inventory_storage = dump_all(session.inventory_storage)
                existing_session.server_containers = dump_all(session.server_containers)
                existing_session.current_shop = dump_all(session.current_shop)
                existing_session.last_battle_result = session.last_battle_result
                existing_session.game_seed = game_seed
                existing_session.shop_refresh_count = session.shop_refresh_count
                existing_session.last_activity = utc_now()
                print(f"Updated existing session for player {player_id}")
            else:
                # Create new session
                db_session = GameSession(
                    player_id=player_id,
                    player_name=session.player_name,
                    user_id=user.id,  # Link to the guest user
                    round=session.round,
                    gold=session.gold,
                    lives=session.lives,
                    wins=session.wins,
                    losses=session.losses,
                    inventory_grid=dump_all(session.inventory_grid),
                    inventory_storage=dump_all(session.inventory_storage),
                    server_containers=dump_all(session.server_containers),
                    current_shop=dump_all(session.current_shop),
                    last_battle_result=session.last_battle_result,
                    game_seed=game_seed,
                    shop_refresh_count=session.shop_refresh_count,
                )
                db.add(db_session)
                print(f"Created new session for player {player_id}")

            await db.commit()

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
                db_session.last_activity = utc_now()
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
                db_session.inventory_grid = dump_all(session.inventory_grid)
                db_session.inventory_storage = dump_all(session.inventory_storage)
                db_session.server_containers = dump_all(session.server_containers)
                db_session.current_shop = dump_all(session.current_shop)
                db_session.last_battle_result = session.last_battle_result
                db_session.shop_refresh_count = session.shop_refresh_count
                db_session.last_activity = utc_now()

                await db.commit()
                return True

            return False

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
        cutoff = utc_now() - timedelta(hours=hours)

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
                logger.info("Database reset using TRUNCATE")
            except Exception:
                logger.warning(
                    "Failed to reset database with TRUNCATE, trying DELETE",
                    exc_info=True,
                )
                # Try DELETE as fallback (works with more databases)
                try:
                    await db.execute(delete(BattleHistory))
                    await db.execute(delete(GameSession))
                    await db.commit()
                    logger.info("Database reset using DELETE")
                except Exception:
                    logger.exception("Failed to reset database with DELETE")
                    raise


# Global session manager instance
session_manager = SessionManager()
