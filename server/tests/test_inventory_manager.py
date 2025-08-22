"""
Tests for the inventory management system
Tests written first, following TDD principles
"""

import pytest
from inventory_manager import (
    InvalidPlacementError,
    InventoryGrid,
    InventoryManager,
    InventoryStorage,
    ItemNotFoundError,
)


class TestInventoryGrid:
    """Test the 9x7 grid management with server containers"""

    def test_grid_initialization(self):
        """Test that grid initializes with correct dimensions and 3 containers"""
        grid = InventoryGrid()

        # Check dimensions
        assert grid.width == 9
        assert grid.height == 7

        # Check that 3 server containers are placed
        assert len(grid.containers) == 3

        # Check container positions (centered horizontally)
        expected_positions = [(2, 3), (4, 3), (6, 3)]
        actual_positions = [c["position"] for c in grid.containers]
        assert actual_positions == expected_positions

        # Check each container is 2x2
        for container in grid.containers:
            assert container["width"] == 2
            assert container["height"] == 2

    def test_is_valid_placement(self):
        """Test validation of item placement on servers"""
        grid = InventoryGrid()

        # Valid placements (on servers)
        assert grid.is_valid_placement((2, 3)) is True  # Container A top-left
        assert grid.is_valid_placement((3, 4)) is True  # Container A bottom-right
        assert grid.is_valid_placement((4, 3)) is True  # Container B top-left
        assert grid.is_valid_placement((5, 4)) is True  # Container B bottom-right
        assert grid.is_valid_placement((6, 3)) is True  # Container C top-left
        assert grid.is_valid_placement((7, 4)) is True  # Container C bottom-right

        # Invalid placements (not on servers)
        assert grid.is_valid_placement((0, 0)) is False  # Empty space
        assert grid.is_valid_placement((1, 3)) is False  # Left of containers
        assert grid.is_valid_placement((8, 3)) is False  # Right of containers
        assert grid.is_valid_placement((4, 2)) is False  # Above containers
        assert grid.is_valid_placement((4, 5)) is False  # Below containers

        # Out of bounds
        assert grid.is_valid_placement((-1, 0)) is False
        assert grid.is_valid_placement((9, 0)) is False
        assert grid.is_valid_placement((0, 7)) is False

    def test_place_item(self):
        """Test placing items on the grid"""
        grid = InventoryGrid()

        # Place an item on container A
        item1 = {"id": "item1", "item_type": "null_blade", "position": (2, 3)}
        grid.place_item(item1, (2, 3))

        assert len(grid.items) == 1
        assert grid.items[0]["position"] == (2, 3)
        assert grid.get_item_at((2, 3)) == item1

        # Place another item on container B
        item2 = {"id": "item2", "item_type": "firewall", "position": (4, 4)}
        grid.place_item(item2, (4, 4))

        assert len(grid.items) == 2
        assert grid.get_item_at((4, 4)) == item2

    def test_overlap_detection(self):
        """Test that items cannot overlap"""
        grid = InventoryGrid()

        # Place first item
        item1 = {"id": "item1", "item_type": "null_blade"}
        grid.place_item(item1, (2, 3))

        # Try to place overlapping item
        item2 = {"id": "item2", "item_type": "firewall"}
        with pytest.raises(InvalidPlacementError):
            grid.place_item(item2, (2, 3))

    def test_remove_item(self):
        """Test removing items from the grid"""
        grid = InventoryGrid()

        # Place and remove by position
        item1 = {"id": "item1", "item_type": "null_blade"}
        grid.place_item(item1, (2, 3))
        removed = grid.remove_item_at((2, 3))

        assert removed == item1
        assert len(grid.items) == 0
        assert grid.get_item_at((2, 3)) is None

        # Try to remove from empty position
        with pytest.raises(ItemNotFoundError):
            grid.remove_item_at((2, 3))

    def test_get_battle_items(self):
        """Test getting items formatted for battle"""
        grid = InventoryGrid()

        # Place several items
        item1 = {"id": "item1", "item_type": "null_blade"}
        item2 = {"id": "item2", "item_type": "firewall"}
        item3 = {"id": "item3", "item_type": "core_dumper"}

        grid.place_item(item1, (2, 3))
        grid.place_item(item2, (4, 3))
        grid.place_item(item3, (6, 4))

        battle_items = grid.get_battle_items()

        assert len(battle_items) == 3
        # Check items have positions
        for item in battle_items:
            assert "position" in item
            assert "item_type" in item
            assert "id" in item

    def test_multi_square_items(self):
        """Test placing items that occupy multiple squares"""
        grid = InventoryGrid()

        # Place a 2x1 item
        item = {
            "id": "multi1",
            "item_type": "denier_of_service",
            "shape": [(0, 0), (1, 0)],  # 2x1 shape
        }
        grid.place_item(item, (2, 3))

        # Both squares should be occupied
        assert grid.get_item_at((2, 3)) == item
        assert grid.get_item_at((3, 3)) == item

        # Cannot place another item on either square
        item2 = {"id": "item2", "item_type": "firewall"}
        with pytest.raises(InvalidPlacementError):
            grid.place_item(item2, (3, 3))


class TestInventoryStorage:
    """Test the unlimited storage area"""

    def test_storage_initialization(self):
        """Test storage starts empty"""
        storage = InventoryStorage()
        assert len(storage.items) == 0
        assert storage.get_all() == []

    def test_add_to_storage(self):
        """Test adding items to storage"""
        storage = InventoryStorage()

        item1 = {"id": "item1", "item_type": "null_blade"}
        item2 = {"id": "item2", "item_type": "firewall"}

        storage.add_item(item1)
        storage.add_item(item2)

        assert len(storage.items) == 2
        assert item1 in storage.items
        assert item2 in storage.items

    def test_remove_from_storage(self):
        """Test removing items from storage"""
        storage = InventoryStorage()

        item1 = {"id": "item1", "item_type": "null_blade"}
        item2 = {"id": "item2", "item_type": "firewall"}

        storage.add_item(item1)
        storage.add_item(item2)

        # Remove by item ID
        removed = storage.remove_item("item1")
        assert removed == item1
        assert len(storage.items) == 1
        assert item1 not in storage.items

        # Try to remove non-existent item
        with pytest.raises(ItemNotFoundError):
            storage.remove_item("item999")

    def test_find_item_in_storage(self):
        """Test finding items in storage"""
        storage = InventoryStorage()

        item1 = {"id": "item1", "item_type": "null_blade"}
        item2 = {"id": "item2", "item_type": "firewall"}

        storage.add_item(item1)
        storage.add_item(item2)

        found = storage.find_item("item2")
        assert found == item2

        not_found = storage.find_item("item999")
        assert not_found is None

    def test_storage_unlimited_capacity(self):
        """Test that storage has no capacity limit"""
        storage = InventoryStorage()

        # Add many items
        for i in range(100):
            item = {"id": f"item{i}", "item_type": "null_blade"}
            storage.add_item(item)

        assert len(storage.items) == 100


class TestInventoryManager:
    """Test the high-level inventory management"""

    def test_manager_initialization(self):
        """Test manager initializes with grid and storage"""
        manager = InventoryManager()

        assert manager.grid is not None
        assert manager.storage is not None
        assert len(manager.grid.containers) == 3
        assert len(manager.storage.items) == 0

    def test_place_item_on_grid(self):
        """Test placing item on grid through manager"""
        manager = InventoryManager()

        item = {"id": "item1", "item_type": "null_blade"}
        success = manager.place_item(item, placement=(2, 3))

        assert success is True
        assert len(manager.grid.items) == 1
        assert manager.grid.get_item_at((2, 3)) == item

    def test_place_item_in_storage(self):
        """Test placing item in storage through manager"""
        manager = InventoryManager()

        item = {"id": "item1", "item_type": "null_blade"}
        success = manager.place_item(item, placement="storage")

        assert success is True
        assert len(manager.storage.items) == 1
        assert manager.storage.find_item("item1") == item

    def test_move_item_from_storage_to_grid(self):
        """Test moving items between storage and grid"""
        manager = InventoryManager()

        # Add item to storage
        item = {"id": "item1", "item_type": "null_blade"}
        manager.place_item(item, placement="storage")

        # Move to grid - should not raise exception
        manager.move_item("item1", from_location="storage", to_location=(2, 3))

        # Verify move succeeded
        assert len(manager.storage.items) == 0
        assert len(manager.grid.items) == 1
        assert manager.grid.get_item_at((2, 3)) == item

    def test_move_item_from_grid_to_storage(self):
        """Test moving items from grid to storage"""
        manager = InventoryManager()

        # Add item to grid
        item = {"id": "item1", "item_type": "null_blade"}
        manager.place_item(item, placement=(2, 3))

        # Move to storage - should not raise exception
        manager.move_item("item1", from_location=(2, 3), to_location="storage")

        # Verify move succeeded
        assert len(manager.grid.items) == 0
        assert len(manager.storage.items) == 1
        assert manager.storage.find_item("item1") == item

    def test_get_battle_inventory(self):
        """Test getting only grid items for battle"""
        manager = InventoryManager()

        # Add items to both grid and storage
        grid_item1 = {"id": "grid1", "item_type": "null_blade"}
        grid_item2 = {"id": "grid2", "item_type": "firewall"}
        storage_item = {"id": "storage1", "item_type": "core_dumper"}

        manager.place_item(grid_item1, placement=(2, 3))
        manager.place_item(grid_item2, placement=(4, 4))
        manager.place_item(storage_item, placement="storage")

        battle_items = manager.get_battle_inventory()

        # Only grid items should be included
        assert len(battle_items) == 2
        item_ids = [item["id"] for item in battle_items]
        assert "grid1" in item_ids
        assert "grid2" in item_ids
        assert "storage1" not in item_ids

    def test_sell_item_from_grid(self):
        """Test selling items from grid"""
        manager = InventoryManager()

        item = {"id": "item1", "item_type": "null_blade", "cost": 10}
        manager.place_item(item, placement=(2, 3))

        removed = manager.remove_item(location=(2, 3))

        assert removed == item
        assert len(manager.grid.items) == 0

    def test_sell_item_from_storage(self):
        """Test selling items from storage"""
        manager = InventoryManager()

        item = {"id": "item1", "item_type": "null_blade", "cost": 10}
        manager.place_item(item, placement="storage")

        removed = manager.remove_item(item_id="item1")

        assert removed == item
        assert len(manager.storage.items) == 0

    def test_get_inventory_state(self):
        """Test getting full inventory state for persistence"""
        manager = InventoryManager()

        # Add various items
        grid_item = {"id": "grid1", "item_type": "null_blade"}
        storage_item = {"id": "storage1", "item_type": "firewall"}

        manager.place_item(grid_item, placement=(2, 3))
        manager.place_item(storage_item, placement="storage")

        state = manager.get_state()

        assert "grid" in state
        assert "storage" in state
        assert "containers" in state
        assert len(state["grid"]) == 1
        assert len(state["storage"]) == 1
        assert len(state["containers"]) == 3

    def test_restore_inventory_state(self):
        """Test restoring inventory from saved state"""
        manager1 = InventoryManager()

        # Set up some state
        grid_item = {"id": "grid1", "item_type": "null_blade"}
        storage_item = {"id": "storage1", "item_type": "firewall"}
        manager1.place_item(grid_item, placement=(2, 3))
        manager1.place_item(storage_item, placement="storage")

        # Save state
        state = manager1.get_state()

        # Create new manager and restore
        manager2 = InventoryManager()
        manager2.restore_state(state)

        # Verify restoration
        assert len(manager2.grid.items) == 1
        assert len(manager2.storage.items) == 1
        assert manager2.grid.get_item_at((2, 3))["id"] == "grid1"
        assert manager2.storage.find_item("storage1")["id"] == "storage1"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
