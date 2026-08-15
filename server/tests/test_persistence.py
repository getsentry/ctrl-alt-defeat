"""
Test database persistence for game sessions
"""

import random

import pytest
import pytest_asyncio

from database import db_manager
from items import Item
from session_manager import SessionManager


class TestSessionPersistence:
    """Test session persistence with PostgreSQL"""

    @pytest_asyncio.fixture
    async def session_manager_instance(self):
        """Create a session manager for testing"""
        manager = SessionManager()
        await manager.initialize()
        yield manager
        # Cleanup after test
        await db_manager.close()

    @pytest.mark.asyncio
    async def test_create_session(self, session_manager_instance):
        """Test creating a new session"""
        manager = session_manager_instance
        player_id = "test_player_123"
        game_seed = 42

        # Create session (creates guest user and returns numeric ID)
        session = await manager.create_session(player_id, game_seed)

        assert session is not None
        # player_id is now a numeric user ID (as string)
        assert session.player_id.isdigit()
        assert session.game_seed == game_seed
        assert session.round == 1
        assert session.gold == 12
        assert session.lives == 5

        # Cleanup - use actual player_id from session
        await manager.delete_session(session.player_id)

    @pytest.mark.asyncio
    async def test_get_session(self, session_manager_instance):
        """Test retrieving an existing session"""
        manager = session_manager_instance
        player_id = "test_player_456"
        game_seed = 99

        # Create session
        created = await manager.create_session(player_id, game_seed)

        # Retrieve session using the actual player_id
        retrieved = await manager.get_session(created.player_id)

        assert retrieved is not None
        assert retrieved.player_id == created.player_id
        assert retrieved.game_seed == created.game_seed

        # Cleanup
        await manager.delete_session(created.player_id)

    @pytest.mark.asyncio
    async def test_update_session(self, session_manager_instance):
        """Test updating a session"""
        manager = session_manager_instance
        player_id = "test_player_789"

        # Create session
        session = await manager.create_session(player_id)

        # Modify session
        session.gold = 50
        session.round = 5
        session.wins = 3
        session.losses = 1

        # Update
        success = await manager.update_session(session)
        assert success

        # Retrieve and verify
        updated = await manager.get_session(session.player_id)
        assert updated.gold == 50
        assert updated.round == 5
        assert updated.wins == 3
        assert updated.losses == 1

        # Cleanup
        await manager.delete_session(session.player_id)

    @pytest.mark.asyncio
    async def test_delete_session(self, session_manager_instance):
        """Test deleting a session"""
        manager = session_manager_instance
        player_id = "test_player_delete"

        # Create session
        session = await manager.create_session(player_id)

        # Delete using actual player_id
        deleted = await manager.delete_session(session.player_id)
        assert deleted

        # Try to retrieve - should be None
        retrieved = await manager.get_session(session.player_id)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_list_sessions(self, session_manager_instance):
        """Test listing all sessions"""
        manager = session_manager_instance

        # Use unique IDs to avoid conflicts from previous runs
        import time

        suffix = str(int(time.time() * 1000))[-6:]

        # Create multiple sessions
        player_ids = [f"test_list_{i}_{suffix}" for i in range(3)]
        created_sessions = []
        for pid in player_ids:
            session = await manager.create_session(pid)
            created_sessions.append(session)

        # List sessions
        all_sessions = await manager.list_active_sessions()

        # Check all test sessions are in the list
        for session in created_sessions:
            assert session.player_id in all_sessions

        # Cleanup
        for session in created_sessions:
            await manager.delete_session(session.player_id)

    @pytest.mark.asyncio
    async def test_session_with_complex_data(self, session_manager_instance):
        """Test session with inventory and shop data"""
        manager = session_manager_instance
        import time

        suffix = str(int(time.time() * 1000))[-6:]
        player_id = f"test_complex_{suffix}"

        # Create session with complex data
        session = await manager.create_session(player_id)

        # Add inventory items
        session.inventory_grid = [
            Item.of("null_blade", "item1").placed_at((0, 0)),
            Item.of("firewall", "item2").placed_at((1, 0)),
        ]

        session.inventory_storage = [Item.of("core_dumper", "item3")]

        session.current_shop = [
            Item.of("deadlock_twins", "shop1"),
            Item.of("core_dumper", "shop2"),
        ]

        # Update
        await manager.update_session(session)

        # Retrieve and verify
        retrieved = await manager.get_session(session.player_id)
        assert len(retrieved.inventory_grid) == 2
        assert retrieved.inventory_grid[0].item_type == "null_blade"
        assert len(retrieved.inventory_storage) == 1
        assert len(retrieved.current_shop) == 2

        # Cleanup
        await manager.delete_session(session.player_id)

    @pytest.mark.asyncio
    async def test_battle_history(self, session_manager_instance):
        """Test saving and retrieving battle history"""
        manager = session_manager_instance
        player_id = "test_battles_" + str(
            random.randint(1000, 9999)
        )  # Unique ID to avoid conflicts

        # Create session
        session = await manager.create_session(player_id)

        # Save some battles
        for i in range(3):
            await manager.save_battle_history(
                player1_id=session.player_id,
                player2_id=None,  # AI opponent
                round_number=i + 1,
                winner=1 if i % 2 == 0 else 2,
                battle_data={"duration": 30 + i, "actions": []},
            )

        # Get history
        history = await manager.get_battle_history(session.player_id, limit=5)

        assert len(history) == 3
        # Should be sorted by most recent first
        assert history[0]["round_number"] == 3

        # Cleanup - delete session and battle history
        await manager.delete_session(session.player_id)
        # Also clean up battle history
        from sqlalchemy import delete

        from database import db_manager
        from models import BattleHistory

        async with db_manager.get_session() as db:
            await db.execute(
                delete(BattleHistory).where(
                    BattleHistory.player1_id == session.player_id
                )
            )
            await db.commit()


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
