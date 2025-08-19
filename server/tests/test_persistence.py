"""
Test database persistence for game sessions
"""

import os

import pytest
import pytest_asyncio
from database import db_manager
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
        if not manager.use_fallback:
            await db_manager.close()

    @pytest.mark.asyncio
    async def test_create_session(self, session_manager_instance):
        """Test creating a new session"""
        manager = session_manager_instance
        player_id = "test_player_123"
        game_seed = 42

        # Create session
        session = await manager.create_session(player_id, game_seed)

        assert session is not None
        assert session.player_id == player_id
        assert session.game_seed == game_seed
        assert session.round == 1
        assert session.gold == 12
        assert session.lives == 5

        # Cleanup
        await manager.delete_session(player_id)

    @pytest.mark.asyncio
    async def test_get_session(self, session_manager_instance):
        """Test retrieving an existing session"""
        manager = session_manager_instance
        player_id = "test_player_456"
        game_seed = 99

        # Create session
        created = await manager.create_session(player_id, game_seed)

        # Retrieve session
        retrieved = await manager.get_session(player_id)

        assert retrieved is not None
        assert retrieved.player_id == created.player_id
        assert retrieved.game_seed == created.game_seed

        # Cleanup
        await manager.delete_session(player_id)

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
        updated = await manager.get_session(player_id)
        assert updated.gold == 50
        assert updated.round == 5
        assert updated.wins == 3
        assert updated.losses == 1

        # Cleanup
        await manager.delete_session(player_id)

    @pytest.mark.asyncio
    async def test_delete_session(self, session_manager_instance):
        """Test deleting a session"""
        manager = session_manager_instance
        player_id = "test_player_delete"

        # Create session
        await manager.create_session(player_id)

        # Delete
        deleted = await manager.delete_session(player_id)
        assert deleted

        # Try to retrieve - should be None
        session = await manager.get_session(player_id)
        assert session is None

    @pytest.mark.asyncio
    async def test_list_sessions(self, session_manager_instance):
        """Test listing all sessions"""
        manager = session_manager_instance

        # Create multiple sessions
        player_ids = [f"test_list_{i}" for i in range(3)]
        for pid in player_ids:
            await manager.create_session(pid)

        # List sessions
        all_sessions = await manager.list_sessions()

        # Check all test sessions are in the list
        for pid in player_ids:
            assert pid in all_sessions

        # Cleanup
        for pid in player_ids:
            await manager.delete_session(pid)

    @pytest.mark.asyncio
    async def test_session_with_complex_data(self, session_manager_instance):
        """Test session with inventory and shop data"""
        manager = session_manager_instance
        player_id = "test_complex"

        # Create session with complex data
        session = await manager.create_session(player_id)

        # Add inventory items
        session.inventory_grid = [
            {"id": "item1", "item_type": "null_pointer", "position": [0, 0], "cost": 3},
            {"id": "item2", "item_type": "firewall", "position": [1, 0], "cost": 5},
        ]

        session.inventory_storage = [
            {"id": "item3", "item_type": "memory_leak", "cost": 4}
        ]

        session.current_shop = [
            {"id": "shop1", "item_type": "buffer_overflow", "cost": 8},
            {"id": "shop2", "item_type": "race_condition", "cost": 6},
        ]

        # Update
        await manager.update_session(session)

        # Retrieve and verify
        retrieved = await manager.get_session(player_id)
        assert len(retrieved.inventory_grid) == 2
        assert retrieved.inventory_grid[0]["item_type"] == "null_pointer"
        assert len(retrieved.inventory_storage) == 1
        assert len(retrieved.current_shop) == 2

        # Cleanup
        await manager.delete_session(player_id)

    @pytest.mark.asyncio
    async def test_battle_history(self, session_manager_instance):
        """Test saving and retrieving battle history"""
        manager = session_manager_instance
        player_id = "test_battles"

        # Create session
        await manager.create_session(player_id)

        # Save some battles
        for i in range(3):
            await manager.save_battle_history(
                player1_id=player_id,
                player2_id=None,  # AI opponent
                round_number=i + 1,
                winner=1 if i % 2 == 0 else 2,
                battle_data={"duration": 30 + i, "actions": []},
            )

        # Get history
        history = await manager.get_battle_history(player_id, limit=5)

        if not manager.use_fallback:
            assert len(history) == 3
            # Should be sorted by most recent first
            assert history[0]["round_number"] == 3

        # Cleanup
        await manager.delete_session(player_id)

    @pytest.mark.asyncio
    async def test_fallback_mode(self):
        """Test that fallback to in-memory storage works"""
        # Create manager with intentionally bad database URL
        old_url = os.environ.get("DATABASE_URL")
        os.environ["DATABASE_URL"] = "postgresql://bad:bad@nohost:5432/nodb"

        manager = SessionManager()
        await manager.initialize()

        # Should be using fallback
        assert manager.use_fallback

        # Test basic operations still work
        player_id = "test_fallback"
        session = await manager.create_session(player_id)
        assert session is not None

        retrieved = await manager.get_session(player_id)
        assert retrieved is not None

        deleted = await manager.delete_session(player_id)
        assert deleted

        # Restore environment
        if old_url:
            os.environ["DATABASE_URL"] = old_url
        else:
            del os.environ["DATABASE_URL"]


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
