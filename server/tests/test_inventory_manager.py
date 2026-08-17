"""
Tests for the inventory management system
Tests written first, following TDD principles
"""

import json

import pytest

from grid_system import Rotation
from inventory_manager import (
    InvalidPlacementError,
    InventoryGrid,
    InventoryManager,
    InventoryStorage,
    ItemNotFoundError,
)
from items import Item
from tests.test_utils import find_bad_positions
from utils import dump_all


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
        actual_positions = [c.position for c in grid.containers]
        assert actual_positions == expected_positions

        # Check each container covers a 2x2 block
        for container in grid.containers:
            assert sorted(container.shape) == [(0, 0), (0, 1), (1, 0), (1, 1)]

    def test_can_hold(self):
        """Test validation of item placement on servers"""
        grid = InventoryGrid()

        # Valid placements (on servers)
        assert grid.can_hold([(2, 3)]) is True  # Container A top-left
        assert grid.can_hold([(3, 4)]) is True  # Container A bottom-right
        assert grid.can_hold([(4, 3)]) is True  # Container B top-left
        assert grid.can_hold([(5, 4)]) is True  # Container B bottom-right
        assert grid.can_hold([(6, 3)]) is True  # Container C top-left
        assert grid.can_hold([(7, 4)]) is True  # Container C bottom-right

        # Invalid placements (not on servers)
        assert grid.can_hold([(0, 0)]) is False  # Empty space
        assert grid.can_hold([(1, 3)]) is False  # Left of containers
        assert grid.can_hold([(8, 3)]) is False  # Right of containers
        assert grid.can_hold([(4, 2)]) is False  # Above containers
        assert grid.can_hold([(4, 5)]) is False  # Below containers

        # Out of bounds
        assert grid.can_hold([(-1, 0)]) is False
        assert grid.can_hold([(9, 0)]) is False
        assert grid.can_hold([(0, 7)]) is False

    def test_place_item(self):
        """Test placing items on the grid"""
        grid = InventoryGrid()

        # Place an item on container A
        item1 = Item.of("null_blade", "item1")
        grid.place_item(item1, (2, 3))

        assert len(grid.items) == 1
        assert grid.items[0].position == (2, 3)
        assert grid.get_item_at((2, 3)).id == "item1"

        # Place another item on container B
        # firewall is 1x2, so it covers (4, 3) and (4, 4)
        item2 = Item.of("firewall", "item2")
        grid.place_item(item2, (4, 3))

        assert len(grid.items) == 2
        assert grid.get_item_at((4, 4)).id == "item2"

    def test_overlap_detection(self):
        """Test that items cannot overlap"""
        grid = InventoryGrid()

        # Place first item
        item1 = Item.of("null_blade", "item1")
        grid.place_item(item1, (2, 3))

        # Try to place overlapping item
        item2 = Item.of("firewall", "item2")
        with pytest.raises(InvalidPlacementError):
            grid.place_item(item2, (2, 3))

    def test_remove_item(self):
        """Test removing items from the grid"""
        grid = InventoryGrid()

        # Place and remove by position
        item1 = Item.of("null_blade", "item1")
        grid.place_item(item1, (2, 3))
        removed = grid.remove_item_at((2, 3))

        assert removed.id == item1.id
        assert len(grid.items) == 0
        assert grid.get_item_at((2, 3)) is None

        # Try to remove from empty position
        with pytest.raises(ItemNotFoundError):
            grid.remove_item_at((2, 3))

    def test_get_battle_items(self):
        """Test getting items formatted for battle"""
        grid = InventoryGrid()

        # Place several items
        item1 = Item.of("null_blade", "item1")
        item2 = Item.of("firewall", "item2")
        item3 = Item.of("core_dumper", "item3")

        grid.place_item(item1, (2, 3))
        grid.place_item(item2, (4, 3))
        grid.place_item(item3, (6, 4))

        battle_items = grid.get_battle_items()

        assert len(battle_items) == 3
        # Every battle item knows where it is and what it is
        for item in battle_items:
            assert item.position is not None
            assert item.item_type
            assert item.id

    def test_multi_square_items(self):
        """Test placing items that occupy multiple squares"""
        grid = InventoryGrid()

        # null_blade is 1x2, so it covers two squares
        item = Item.of("null_blade", "multi1")
        grid.place_item(item, (2, 3))

        # Both squares should be occupied
        assert grid.get_item_at((2, 3)).id == "multi1"
        assert grid.get_item_at((2, 4)).id == "multi1"

        # Cannot place another item on either square
        item2 = Item.of("firewall", "item2")
        with pytest.raises(InvalidPlacementError):
            grid.place_item(item2, (2, 4))


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

        item1 = Item.of("null_blade", "item1")
        item2 = Item.of("firewall", "item2")

        storage.add_item(item1)
        storage.add_item(item2)

        assert len(storage.items) == 2
        assert item1 in storage.items
        assert item2 in storage.items

    def test_remove_from_storage(self):
        """Test removing items from storage"""
        storage = InventoryStorage()

        item1 = Item.of("null_blade", "item1")
        item2 = Item.of("firewall", "item2")

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

        item1 = Item.of("null_blade", "item1")
        item2 = Item.of("firewall", "item2")

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
            item = Item.of("null_blade", f"item{i}")
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

        item = Item.of("null_blade", "item1")
        success = manager.place_item(item, placement=(2, 3))

        assert success is True
        assert len(manager.grid.items) == 1
        assert manager.grid.get_item_at((2, 3)).id == item.id

    def test_place_item_in_storage(self):
        """Test placing item in storage through manager"""
        manager = InventoryManager()

        item = Item.of("null_blade", "item1")
        success = manager.place_item(item, placement="storage")

        assert success is True
        assert len(manager.storage.items) == 1
        assert manager.storage.find_item("item1") == item

    def test_move_item_from_storage_to_grid(self):
        """Test moving items between storage and grid"""
        manager = InventoryManager()

        # Add item to storage
        item = Item.of("null_blade", "item1")
        manager.place_item(item, placement="storage")

        # Move to grid - should not raise exception
        manager.move_item("item1", from_location="storage", to_location=(2, 3))

        # Verify move succeeded
        assert len(manager.storage.items) == 0
        assert len(manager.grid.items) == 1
        assert manager.grid.get_item_at((2, 3)).id == item.id

    def test_move_item_from_grid_to_storage(self):
        """Test moving items from grid to storage"""
        manager = InventoryManager()

        # Add item to grid
        item = Item.of("null_blade", "item1")
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
        grid_item1 = Item.of("null_blade", "grid1")
        grid_item2 = Item.of("firewall", "grid2")
        storage_item = Item.of("core_dumper", "storage1")

        manager.place_item(grid_item1, placement=(2, 3))
        manager.place_item(grid_item2, placement=(4, 3))
        manager.place_item(storage_item, placement="storage")

        battle_items = manager.get_battle_inventory()

        # Only grid items should be included
        assert len(battle_items) == 2
        item_ids = [item.id for item in battle_items]
        assert "grid1" in item_ids
        assert "grid2" in item_ids
        assert "storage1" not in item_ids

    def test_sell_item_from_grid(self):
        """Test selling items from grid"""
        manager = InventoryManager()

        item = Item.of("null_blade", "item1")
        manager.place_item(item, placement=(2, 3))

        removed = manager.remove_item(location=(2, 3))

        assert removed.id == item.id
        assert len(manager.grid.items) == 0

    def test_sell_item_from_storage(self):
        """Test selling items from storage"""
        manager = InventoryManager()

        item = Item.of("null_blade", "item1")
        manager.place_item(item, placement="storage")

        removed = manager.remove_item(item_id="item1")

        assert removed.id == item.id
        assert len(manager.storage.items) == 0

    def test_get_inventory_state(self):
        """Test getting full inventory state for persistence"""
        manager = InventoryManager()

        # Add various items
        grid_item = Item.of("null_blade", "grid1")
        storage_item = Item.of("firewall", "storage1")

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
        grid_item = Item.of("null_blade", "grid1")
        storage_item = Item.of("firewall", "storage1")
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
        assert manager2.grid.get_item_at((2, 3)).id == "grid1"
        assert manager2.storage.find_item("storage1").id == "storage1"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


class TestStoredPositions:
    """Stored state holds (x, y) pairs, and encodes to arrays"""

    def test_default_containers_are_pairs(self):
        grid = InventoryGrid()
        for container in grid.containers:
            assert isinstance(container.position, tuple), (
                f"Container {container.id} stores a "
                f"{type(container.position).__name__}, not a pair"
            )
            assert len(container.position) == 2

    def test_placed_item_position_is_a_pair(self):
        grid = InventoryGrid()
        grid.place_item(Item.of("null_blade", "item_1"), (2, 3))

        placed = grid.get_item_at((2, 3))
        assert placed.position == (2, 3)
        assert isinstance(placed.position, tuple)

    def test_inventory_state_encodes_positions_as_arrays(self):
        """State goes to the database as JSON, where a pair becomes an array."""
        manager = InventoryManager()
        manager.place_item(Item.of("null_blade", "item_1"), (2, 3))

        state = manager.get_state()
        encoded = json.loads(
            json.dumps({key: dump_all(value) for key, value in state.items()})
        )

        assert encoded["grid"][0]["position"] == [2, 3]
        assert not find_bad_positions(
            encoded
        ), "Encoded state should carry [x, y] arrays"

    def test_lookups_take_a_pair(self):
        grid = InventoryGrid()
        grid.place_item(Item.of("null_blade", "item_1"), (2, 3))

        assert grid.get_item_at((2, 3)).id == "item_1"

    def test_restoring_from_the_database_converts_positions(self):
        """
        Saved state has been through JSON, so its positions arrive as lists.
        The models turn them back into pairs on the way in.
        """
        manager = InventoryManager()
        manager.restore_state(
            {
                "grid": dump_all([Item.of("null_blade", "item_1").placed_at((2, 3))]),
                "storage": [],
                "containers": [
                    {
                        "id": "container_a",
                        "slug": "standard_vm",
                        "type": "standard_vm",
                        "position": [2, 3],
                        "shape": [[0, 0], [1, 0], [0, 1], [1, 1]],
                    }
                ],
            }
        )

        assert manager.grid.items[0].position == (2, 3)
        assert isinstance(manager.grid.items[0].position, tuple)
        assert manager.grid.containers[0].position == (2, 3)
        assert manager.grid.containers[0].shape == [(0, 0), (1, 0), (0, 1), (1, 1)]
        assert manager.grid.get_item_at((2, 3)).id == "item_1"


class TestFailuresReachTheCaller:
    """
    A placement reports False only when the placement itself is wrong. Any other
    fault travels up, so it is not reported to the player as a full grid.
    """

    def test_an_invalid_placement_reports_false(self):
        manager = InventoryManager()

        placed = manager.place_item(Item.of("null_blade", "item1"), placement=(0, 0))

        assert placed is False, "Bare floor is not a placement"

    def test_a_fault_that_is_not_a_placement_problem_is_raised(self, monkeypatch):
        manager = InventoryManager()

        def explode(*_args, **_kwargs):
            raise RuntimeError("the grid is on fire")

        monkeypatch.setattr(manager.grid, "place_item", explode)

        with pytest.raises(RuntimeError, match="on fire"):
            manager.place_item(Item.of("null_blade", "item1"), placement=(2, 3))

    def test_removing_an_item_that_is_not_there_reports_nothing(self):
        manager = InventoryManager()

        assert manager.remove_item(item_id="no_such_item") is None

    def test_a_fault_while_removing_is_raised(self, monkeypatch):
        manager = InventoryManager()
        manager.place_item(Item.of("null_blade", "item1"), placement=(2, 3))

        def explode(*_args, **_kwargs):
            raise RuntimeError("the grid is on fire")

        monkeypatch.setattr(manager.grid, "remove_item_at", explode)

        with pytest.raises(RuntimeError, match="on fire"):
            manager.remove_item(location=(2, 3))

    def test_a_failed_move_puts_the_item_back(self):
        manager = InventoryManager()
        manager.place_item(Item.of("null_blade", "item1"), placement=(2, 3))

        with pytest.raises(InvalidPlacementError):
            manager.move_item("item1", from_location=(2, 3), to_location=(0, 0))

        assert manager.grid.get_item_at((2, 3)).id == "item1", "The item is back"


class TestATurnedItemIsCheckedAsItIsTurned:
    """
    A turned item covers different squares from the ones its shape lists, so
    every check has to ask for the squares rather than the shape.
    """

    def test_a_turn_that_hangs_off_the_containers_is_refused(self):
        manager = InventoryManager()
        # null_blade is one wide and two tall, so a quarter turn makes it two
        # wide. At (7, 3) that reaches (8, 3), which no container covers.
        upright = Item.of("null_blade", "item1")
        turned = upright.placed_at((7, 3), Rotation.CLOCKWISE_90)

        assert turned.covered_squares() == [(7, 3), (8, 3)]
        assert manager.place_item(turned, placement=(7, 3)) is False
        assert manager.grid.items == [], "Nothing should have landed"

    def test_the_same_item_upright_there_is_allowed(self):
        manager = InventoryManager()
        upright = Item.of("null_blade", "item1")

        assert upright.placed_at((7, 3)).covered_squares() == [(7, 3), (7, 4)]
        assert manager.place_item(upright, placement=(7, 3)) is True

    def test_a_turned_item_keeps_its_turn_on_the_grid(self):
        manager = InventoryManager()
        turned = Item.of("null_blade", "item1").placed_at((2, 3), Rotation.CLOCKWISE_90)

        manager.place_item(turned, placement=(2, 3))

        placed = manager.grid.get_item_at((3, 3))
        assert placed is not None, "The turned item reaches the square beside it"
        assert placed.rotation is Rotation.CLOCKWISE_90
