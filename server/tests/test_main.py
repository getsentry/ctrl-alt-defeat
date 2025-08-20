"""
Tests for AI opponent generation with containers
"""

from battle_engine import BattleSimulator
from main import generate_ai_opponent
from server_containers import ServerContainer


class TestAIOpponentGeneration:
    """Test AI opponent generation returns valid items and containers"""

    def test_generate_ai_opponent_returns_items_and_containers(self):
        """Test that generate_ai_opponent returns both items and containers"""
        # Generate AI opponent for round 3
        items, containers = generate_ai_opponent(round_number=3)

        # Should return items
        assert items is not None
        assert len(items) > 0

        # Should return containers
        assert containers is not None
        assert len(containers) > 0

        # Containers should be ServerContainer instances
        for container in containers:
            assert isinstance(container, ServerContainer)

    def test_ai_opponent_passes_validation(self):
        """Test that AI opponent items and containers pass battle validation"""
        # Generate AI opponent for various rounds
        for round_num in [1, 3, 5, 7, 10]:
            items, containers = generate_ai_opponent(round_number=round_num)

            # Create a battle simulator
            simulator = BattleSimulator(seed=42)

            # Should be able to validate placement
            # This would raise ValueError if validation fails
            assert simulator._validate_placement_with_containers(items, containers)

    def test_ai_containers_cover_item_positions(self):
        """Test that generated containers cover all AI item positions"""
        # Generate AI opponent
        items, containers = generate_ai_opponent(round_number=5)

        # Get all container squares
        container_squares = set()
        for container in containers:
            for square in container.get_occupied_squares():
                container_squares.add(square)

        # Check that all item positions are on container squares
        for item in items:
            item_squares = item.get_occupied_squares()
            for square in item_squares:
                assert (
                    square in container_squares
                ), f"Item square {square} not on any container"

    def test_test_ai_difficulty_none_by_default(self):
        """Test that test_ai_difficulty is None by default in SimpleBattleRequest"""
        from schemas import SimpleBattleRequest

        # Create request without test_ai_difficulty
        request = SimpleBattleRequest(player_id="test_player", round_number=1)

        # Should default to None, not 1
        assert request.test_ai_difficulty is None
        assert request.seed is None

    def test_no_opponent_id_in_battle_request(self):
        """Test that opponent_id is no longer in SimpleBattleRequest"""
        from schemas import SimpleBattleRequest

        # Should not have opponent_id field
        assert not hasattr(SimpleBattleRequest, "opponent_id")

        # Create request - should work without opponent_id
        request = SimpleBattleRequest(player_id="test_player", round_number=1)

        # Should not have opponent_id attribute
        assert not hasattr(request, "opponent_id")
