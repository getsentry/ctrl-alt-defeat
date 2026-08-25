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
from payout import Payout, for_abandoned_run, for_finished_run, run_is_over, run_was_won
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

        This writes over the row the last run lived in. Anything owed for that
        run has to be settled first -- see `pay_for_abandoned_run`, which
        /session/start calls before this, because it is the answer to
        /session/start that has to carry what was paid.
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
                existing_session.game_seed = game_seed
                existing_session.shop_refresh_count = session.shop_refresh_count
                existing_session.last_activity = utc_now()
                # A fresh run, so it has not finished and has not been paid.
                existing_session.finished_at = None
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

    async def finish_run(self, player_id: str) -> Optional[Payout]:
        """End the player's run, pay it out, and count it. Once.

        Returns what the run paid, whether or not this call is the one that
        paid it. /battle/simulate works out that the run is over on every call,
        so a client whose answer went missing asks again -- and it should see
        the same ending, with the same banners, rather than a payout of
        nothing. The numbers cannot drift: a finished run's wins and tries
        never change again.

        `finished_at` is what makes the second call pay nothing, and the row is
        locked while it is read so that two calls at once cannot both find it
        unset. Without the lock both would read the same balance, add to it,
        and one increment would be lost -- or worse, both would land and the
        run would pay twice.
        """
        async with db_manager.get_session() as db:
            result = await db.execute(
                select(GameSession)
                .where(GameSession.player_id == player_id)
                .with_for_update()
            )
            db_session = result.scalar_one_or_none()
            if db_session is None:
                return None

            # The row is read again here, under the lock. What the caller
            # decided was over came from an earlier transaction that has since
            # committed and let go, and a /session/start landing in that gap
            # settles the old run and resets the row to a fresh one. Paying
            # then would pay 8 coin for a run nobody has played and stamp the
            # new run as finished, so it would pay nothing when it really ends.
            if not run_is_over(db_session.wins, db_session.lives):
                return None

            paid = for_finished_run(db_session.wins, max(0, db_session.lives))
            if db_session.finished_at is not None:
                return paid

            user = await db.get(User, db_session.user_id)
            if user is not None:
                user.snuba_coin += paid.total
                user.total_games_played += 1
                user.total_wins += db_session.wins
                user.total_losses += db_session.losses
                # Whether this run was won has to be counted as it ends: the
                # row that knows is written over by the next run.
                if run_was_won(db_session.wins):
                    user.total_runs_won += 1

            db_session.finished_at = utc_now()
            await db.commit()

        return paid

    async def pay_for_abandoned_run(self, player_id: str) -> Optional[Payout]:
        """Pay for the run the player walked away from, before it is replaced.

        There is no quit signal: the window closes and the session is never
        touched again. So the moment the player asks for a new run is both the
        first time the server can know the last one is over and a moment the
        player is there to see it -- and it is the last moment the old run
        still exists, because starting a new one writes over the same row.

        Wins only, and it does not count as a game played. Section 5.5 has the
        arithmetic that makes paying for anything else worse than playing.

        The row is locked while it is read, for the same reason as
        `finish_run`: two starts at once would otherwise both see an unpaid run
        and pay for it.
        """
        async with db_manager.get_session() as db:
            result = await db.execute(
                select(GameSession)
                .where(GameSession.player_id == player_id)
                .with_for_update()
            )
            db_session = result.scalar_one_or_none()
            if db_session is None or db_session.finished_at is not None:
                return None
            if db_session.wins <= 0:
                return None

            paid = for_abandoned_run(db_session.wins)

            user = await db.get(User, db_session.user_id)
            if user is not None:
                user.snuba_coin += paid.total
                user.total_wins += db_session.wins
                user.total_losses += db_session.losses

            db_session.finished_at = utc_now()
            await db.commit()

        return paid

    async def snuba_coin_for(self, player_id: str) -> int:
        """The account's SnubaCoin balance, for the player of `player_id`."""
        async with db_manager.get_session() as db:
            result = await db.execute(
                select(User.snuba_coin)
                .join(GameSession, GameSession.user_id == User.id)
                .where(GameSession.player_id == player_id)
            )
            return result.scalar_one_or_none() or 0

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
