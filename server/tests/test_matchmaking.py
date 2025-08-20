"""
Tests for the matchmaking system
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from matchmaking import MatchmakingService
from models import PlayerBuild


class TestMatchmakingService:
    """Test matchmaking service functionality"""

    @pytest.mark.asyncio
    async def test_save_player_build(self):
        """Test saving a player build for matchmaking"""
        # Create mock database session
        mock_db = MagicMock()
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        # Create service
        service = MatchmakingService(mock_db)

        # Test data
        test_inventory = [
            {"id": "item1", "item_type": "null_pointer", "position": [2, 3]}
        ]
        test_containers = [
            {"id": "container_a", "type": "standard_vm", "position": [2, 3]}
        ]

        # Save build
        build = await service.save_player_build(
            user_id=1,
            player_name="TestPlayer",
            game_session_id="session123",
            round_number=5,
            wins=3,
            losses=2,
            lives=3,
            inventory_grid=test_inventory,
            server_containers=test_containers,
            battle_won=True,
            opponent_type="ai",
            opponent_difficulty=2,
        )

        # Verify build was created correctly
        assert build.user_id == 1
        assert build.player_name == "TestPlayer"
        assert build.round_number == 5
        assert build.wins == 3
        assert build.losses == 2
        assert build.win_percent == 60.0  # 3/5 * 100
        assert build.battle_won is True
        assert build.inventory_snapshot == test_inventory
        assert build.server_containers == test_containers

        # Verify database operations were called
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_find_opponent_no_matches(self):
        """Test finding opponent when no matches exist"""
        # Create mock database session
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        # Create service
        service = MatchmakingService(mock_db)

        # Find opponent
        opponent = await service.find_opponent(
            user_id=1,
            round_number=5,
            win_percent=50.0,
            game_version="1.0.0",
            fallback_to_ai=True,
        )

        # Should return None when no matches found
        assert opponent is None

    @pytest.mark.asyncio
    async def test_find_opponent_with_match(self):
        """Test finding opponent when suitable match exists"""
        # Create mock player build
        mock_build = MagicMock(spec=PlayerBuild)
        mock_build.id = 100
        mock_build.player_name = "OpponentPlayer"
        mock_build.round_number = 5
        mock_build.wins = 4
        mock_build.losses = 3
        mock_build.win_percent = 57.14
        mock_build.inventory_snapshot = [{"id": "item1", "item_type": "firewall"}]
        mock_build.server_containers = [{"id": "container_a"}]

        # Create mock database session
        mock_db = MagicMock()

        # Mock candidates query
        candidates_result = MagicMock()
        candidates_result.scalars.return_value.all.return_value = [mock_build]

        # Set up execute to return candidates
        mock_db.execute = AsyncMock(return_value=candidates_result)
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        # Create service
        service = MatchmakingService(mock_db)

        # Find opponent
        opponent = await service.find_opponent(
            user_id=1,
            round_number=5,
            win_percent=50.0,
            game_version="1.0.0",
            fallback_to_ai=True,
        )

        # Verify opponent data
        assert opponent is not None
        assert opponent["type"] == "player_ghost"
        assert opponent["build_id"] == 100
        assert opponent["player_name"] == "OpponentPlayer"
        assert opponent["round_number"] == 5
        assert opponent["wins"] == 4
        assert opponent["losses"] == 3

        # No match history recorded during find_opponent anymore
        mock_db.add.assert_not_called()
        mock_db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_find_opponent_no_candidates(self):
        """Test finding opponent when no suitable candidates exist"""
        # Create mock database session
        mock_db = MagicMock()

        # Mock candidates query with no results
        candidates_result = MagicMock()
        candidates_result.scalars.return_value.all.return_value = (
            []
        )  # No valid candidates

        mock_db.execute = AsyncMock(return_value=candidates_result)

        # Create service
        service = MatchmakingService(mock_db)

        # Find opponent
        opponent = await service.find_opponent(
            user_id=1,
            round_number=5,
            win_percent=50.0,
            game_version="1.0.0",
            fallback_to_ai=True,
        )

        # Should return None since no valid candidates
        assert opponent is None

    @pytest.mark.asyncio
    async def test_record_match_result(self):
        """Test recording match result after battle completes"""
        # Create mock database session
        mock_db = MagicMock()
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()

        # Create service
        service = MatchmakingService(mock_db)

        # Record match result
        await service.record_match_result(
            player_user_id=1, player_build_id=50, opponent_build_id=100, battle_winner=1
        )

        # Verify match history was created
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

        # Check the created match history object
        match_history = mock_db.add.call_args[0][0]
        assert match_history.player_user_id == 1
        assert match_history.player_build_id == 50
        assert match_history.opponent_build_id == 100
        assert match_history.battle_winner == 1

    @pytest.mark.asyncio
    async def test_cleanup_old_builds(self):
        """Test cleaning up old player builds"""
        # Create mock database session
        mock_db = MagicMock()

        # Mock delete result
        delete_result = MagicMock()
        delete_result.rowcount = 15  # 15 builds deleted

        mock_db.execute = AsyncMock(return_value=delete_result)
        mock_db.commit = AsyncMock()

        # Create service
        service = MatchmakingService(mock_db)

        # Cleanup old builds
        deleted_count = await service.cleanup_old_builds(days_to_keep=30)

        # Verify deletion
        assert deleted_count == 15
        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()
