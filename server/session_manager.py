"""
Session management layer for game sessions
Handles database operations and provides a clean interface for the API
"""

import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# Import will be replaced in initialize() if custom config is provided
from database import db_manager  # noqa: F401
from models import BattleHistoryDB, GameSessionDB
from schemas import GameSession as GameSessionPydantic
from sqlalchemy import delete, select


class SessionManager:
    """Manages game sessions with database persistence"""

    def __init__(self, db_host: Optional[str] = None, db_name: Optional[str] = None):
        self.fallback_sessions: Dict[str, GameSessionPydantic] = {}
        self.use_fallback = False
        self.db_host = db_host
        self.db_name = db_name

    async def initialize(self):
        """Initialize the session manager and database"""
        try:
            # Re-initialize db_manager with custom config if provided
            if self.db_host or self.db_name:
                from database import DatabaseManager

                global db_manager
                db_manager = DatabaseManager(self.db_host, self.db_name)

            await db_manager.initialize()
            # Check if database is working
            if not await db_manager.health_check():
                print("Database health check failed, using in-memory fallback")
                self.use_fallback = True
        except Exception as e:
            print(f"Failed to initialize database, using in-memory fallback: {e}")
            self.use_fallback = True

    async def create_session(
        self, player_id: str, game_seed: Optional[int] = None
    ) -> GameSessionPydantic:
        """Create a new game session"""
        # Generate seed if not provided
        if game_seed is None:
            game_seed = random.randint(0, 2**31 - 1)

        # Create Pydantic model
        session = GameSessionPydantic(
            player_id=player_id,
            round=1,
            gold=12,
            lives=5,
            wins=0,
            losses=0,
            game_seed=game_seed,
            shop_refresh_count=0,
            current_shop=[],
            inventory_grid=[],
            inventory_storage=[],
            placed_items=[],
            server_containers=[],
        )

        # Save to database or fallback
        if self.use_fallback:
            self.fallback_sessions[player_id] = session
        else:
            try:
                async with db_manager.get_session() as db:
                    # Check if session already exists
                    existing = await db.get(GameSessionDB, player_id)
                    if existing:
                        # Update existing session
                        existing.update_from_dict(session.model_dump())
                        db_session = existing
                    else:
                        # Create new session
                        db_session = GameSessionDB(**session.model_dump())
                        db.add(db_session)
                    await db.commit()
            except Exception as e:
                print(f"Failed to save session to database: {e}")
                # Fallback to in-memory
                self.fallback_sessions[player_id] = session

        return session

    async def get_session(self, player_id: str) -> Optional[GameSessionPydantic]:
        """Get an existing game session"""
        if self.use_fallback:
            return self.fallback_sessions.get(player_id)

        try:
            async with db_manager.get_session() as db:
                db_session = await db.get(GameSessionDB, player_id)
                if db_session:
                    # Update last activity
                    db_session.last_activity = datetime.utcnow()
                    await db.commit()
                    # Convert to Pydantic model
                    return GameSessionPydantic(**db_session.to_dict())
                return None
        except Exception as e:
            print(f"Failed to get session from database: {e}")
            # Try fallback
            return self.fallback_sessions.get(player_id)

    async def update_session(self, session: GameSessionPydantic) -> bool:
        """Update an existing session"""
        if self.use_fallback:
            self.fallback_sessions[session.player_id] = session
            return True

        try:
            async with db_manager.get_session() as db:
                db_session = await db.get(GameSessionDB, session.player_id)
                if db_session:
                    db_session.update_from_dict(session.model_dump())
                    await db.commit()
                    return True
                else:
                    # Session doesn't exist, create it
                    db_session = GameSessionDB(**session.model_dump())
                    db.add(db_session)
                    await db.commit()
                    return True
        except Exception as e:
            print(f"Failed to update session in database: {e}")
            # Fallback to in-memory
            self.fallback_sessions[session.player_id] = session
            return True

    async def delete_session(self, player_id: str) -> bool:
        """Delete a session"""
        if self.use_fallback:
            if player_id in self.fallback_sessions:
                del self.fallback_sessions[player_id]
                return True
            return False

        try:
            async with db_manager.get_session() as db:
                db_session = await db.get(GameSessionDB, player_id)
                if db_session:
                    await db.delete(db_session)
                    await db.commit()
                    return True
                return False
        except Exception as e:
            print(f"Failed to delete session from database: {e}")
            # Try fallback
            if player_id in self.fallback_sessions:
                del self.fallback_sessions[player_id]
                return True
            return False

    async def list_sessions(self) -> List[str]:
        """List all active session player IDs"""
        if self.use_fallback:
            return list(self.fallback_sessions.keys())

        try:
            async with db_manager.get_session() as db:
                result = await db.execute(select(GameSessionDB.player_id))
                return [row[0] for row in result]
        except Exception as e:
            print(f"Failed to list sessions from database: {e}")
            return list(self.fallback_sessions.keys())

    async def cleanup_old_sessions(self, hours: int = 24):
        """Remove sessions that haven't been active for X hours"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        if self.use_fallback:
            # Can't track activity time in memory-only mode
            return 0

        try:
            async with db_manager.get_session() as db:
                result = await db.execute(
                    delete(GameSessionDB).where(
                        GameSessionDB.last_activity < cutoff_time
                    )
                )
                await db.commit()
                return result.rowcount
        except Exception as e:
            print(f"Failed to cleanup old sessions: {e}")
            return 0

    async def save_battle_history(
        self,
        player1_id: str,
        player2_id: Optional[str],
        round_number: int,
        winner: int,
        battle_data: dict,
    ):
        """Save battle result to history"""
        if self.use_fallback:
            # Don't save history in fallback mode
            return

        try:
            async with db_manager.get_session() as db:
                battle = BattleHistoryDB(
                    player1_id=player1_id,
                    player2_id=player2_id,
                    round_number=round_number,
                    winner=winner,
                    battle_data=battle_data,
                )
                db.add(battle)
                await db.commit()
        except Exception as e:
            print(f"Failed to save battle history: {e}")

    async def get_battle_history(self, player_id: str, limit: int = 10) -> List[dict]:
        """Get recent battle history for a player"""
        if self.use_fallback:
            return []

        try:
            async with db_manager.get_session() as db:
                result = await db.execute(
                    select(BattleHistoryDB)
                    .where(
                        (BattleHistoryDB.player1_id == player_id)
                        | (BattleHistoryDB.player2_id == player_id)
                    )
                    .order_by(BattleHistoryDB.created_at.desc())
                    .limit(limit)
                )
                battles = result.scalars().all()
                return [battle.to_dict() for battle in battles]
        except Exception as e:
            print(f"Failed to get battle history: {e}")
            return []

    async def reset_database(self):
        """Reset database to clean state - TEST MODE ONLY

        Truncates all tables while keeping the schema intact.
        This is used for testing to ensure a clean state between test runs.
        """
        if self.use_fallback:
            # Clear in-memory sessions
            self.fallback_sessions.clear()
            print("Cleared all in-memory sessions")
        else:
            try:
                from sqlalchemy import text

                async with db_manager.get_session() as db:
                    # Use TRUNCATE for PostgreSQL (faster and resets sequences)
                    # CASCADE handles foreign key constraints if any exist
                    await db.execute(text("TRUNCATE TABLE game_sessions CASCADE"))
                    await db.execute(text("TRUNCATE TABLE battle_history CASCADE"))
                    await db.commit()
                    print("Database tables truncated successfully")
            except Exception as e:
                print(f"Failed to reset database with TRUNCATE: {e}")
                # Try DELETE as fallback (works with more databases)
                try:
                    async with db_manager.get_session() as db:
                        await db.execute(delete(BattleHistoryDB))
                        await db.execute(delete(GameSessionDB))
                        await db.commit()
                        print("Database tables cleared using DELETE")
                except Exception as e2:
                    print(f"Failed to reset database with DELETE: {e2}")
                    raise


# Global session manager instance
session_manager = SessionManager()
