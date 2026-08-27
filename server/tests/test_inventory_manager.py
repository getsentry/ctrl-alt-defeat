"""
Tests for the inventory management system
Tests written first, following TDD principles
"""

import json

import pytest
from containers import Container
from grid_system import Rotation, parse_map
from inventory_manager import (
    InvalidPlacementError,
    InventoryGrid,
    InventoryManager,
    InventoryStorage,
    ItemNotFoundError,
)
from items import Item, PlacedItem
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

        # The starting containers are two rows deep, so everything here has to
        # be a shape that stands in two rows. A Stack Smasher is a three row L
        # and cannot be placed at the start of a game at all.
        item1 = Item.of("null_blade", "item1")
        item2 = Item.of("firewall", "item2")
        item3 = Item.of("api_token", "item3")

        grid.place_item(item1, (2, 3))
        grid.place_item(item2, (3, 3))
        grid.place_item(item3, (6, 3))

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
        storage_item = Item.of("stack_smasher", "storage1")

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


class TestAnAnchorIsNotAlwaysOneOfTheSquares:
    """Twelve items in the catalogue are plus or L shapes whose first square is
    (1, 0). The square such an item's position names is not one it covers.

    Removal used to ask the grid what stood at the item's own anchor, and for
    these the grid answered "nothing" about the very item being removed.
    Selling one returned a 500, moving one a 404, and 428 tests said nothing.
    """

    def _plus_on_the_grid(self, manager: InventoryManager, item_id: str):
        plus = Item.of("nullshot", item_id)
        assert (0, 0) not in plus.shape, "Fixture: this anchor is not covered"
        # Put on the grid directly. Placement is not what is under test, and a
        # plus needs three by three of container to be placed properly.
        placed = plus.placed_at((1, 1), Rotation.NONE)
        manager.grid.items.append(placed)
        return placed

    def test_it_can_still_be_taken_off_the_grid(self):
        manager = InventoryManager()
        self._plus_on_the_grid(manager, "plus1")

        removed = manager.remove_item(item_id="plus1")

        assert removed is not None, "The item should come off the grid"
        assert removed.id == "plus1"
        assert manager.grid.items == []

    def test_it_can_still_be_moved(self):
        manager = InventoryManager()
        self._plus_on_the_grid(manager, "plus2")

        manager.move_item(item_id="plus2", from_location=(1, 1), to_location="storage")

        assert manager.grid.items == []
        assert [held.id for held in manager.storage.items] == ["plus2"]


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
                    dump_all([Container.of("standard_vm", (2, 3), "container_a")])[0]
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

        assert sorted(turned.covered_squares()) == [(7, 3), (8, 3)]
        assert manager.place_item(turned, placement=(7, 3)) is False
        assert manager.grid.items == [], "Nothing should have landed"

    def test_the_same_item_upright_there_is_allowed(self):
        manager = InventoryManager()
        upright = Item.of("null_blade", "item1")

        assert sorted(upright.placed_at((7, 3)).covered_squares()) == [(7, 3), (7, 4)]
        assert manager.place_item(upright, placement=(7, 3)) is True

    def test_a_turned_item_keeps_its_turn_on_the_grid(self):
        manager = InventoryManager()
        turned = Item.of("null_blade", "item1").placed_at((2, 3), Rotation.CLOCKWISE_90)

        manager.place_item(turned, placement=(2, 3))

        placed = manager.grid.get_item_at((3, 3))
        assert placed is not None, "The turned item reaches the square beside it"
        assert placed.rotation is Rotation.CLOCKWISE_90


# The shapes these tests place, built the way the catalogue builds them.
ONE_SQUARE = parse_map(["#"], "one square")
TWO_WIDE = parse_map(["##"], "two wide")


class TestMovingAContainer:
    """A move carries whatever rests on the thing moved.

    The starting grid is three 2x2 containers at (2,3), (4,3) and (6,3), so
    they cover x 2-7 and y 3-4 with nothing else on the board.
    See docs/moving_containers.md.
    """

    def _grid(self) -> InventoryGrid:
        return InventoryGrid()

    def _item(self, item_id: str, position, shape=None) -> PlacedItem:
        item = Item.of("null_blade", item_id)
        squares = list((shape or ONE_SQUARE).squares)
        return item.model_copy(update={"shape": squares}).placed_at(position)

    def test_a_container_takes_its_items_with_it(self):
        grid = self._grid()
        grid.items.append(self._item("on_a", (2, 3)))

        displaced = grid.move_container("container_a", (0, 0))

        assert displaced == []
        assert grid.find_container("container_a").position == (0, 0)
        assert grid.items[0].position == (0, 0), "The item moved with it"

    def test_an_item_left_with_nothing_under_it_is_displaced(self):
        # A two-wide item straddling containers A and B. Only A moves, so the
        # half that was on B has nothing under it any more.
        grid = self._grid()
        grid.items.append(self._item("straddler", (3, 3), shape=TWO_WIDE))

        displaced = grid.move_container("container_a", (0, 0))

        assert [item.id for item in displaced] == ["straddler"]
        assert grid.items == [], "A displaced item is off the grid"
        assert grid.find_container("container_a").position == (0, 0)

    def test_an_item_that_still_has_ground_under_it_is_not_displaced(self):
        """The half that hangs off the moving container lands on another one.

        A fourth container at (4,5) covers x 4-5, y 5-6. Container A moves down
        to (2,5), so the two-wide item straddling A and B travels to (3,5) and
        covers (3,5) on A and (4,5) on the new container. It has ground under
        all of it, so it stays where it landed.
        """
        grid = self._grid()
        grid.containers.append(Container.of("standard_vm", (4, 5), "container_d"))
        grid.items.append(self._item("straddler", (3, 3), shape=TWO_WIDE))

        displaced = grid.move_container("container_a", (2, 5))

        assert displaced == [], "It landed on ground, so it stays"
        assert grid.items[0].position == (3, 5)

    def test_an_item_landing_on_a_stationary_item_is_displaced(self):
        """The same move as above, but something is already standing there.

        Only a straddling item can collide: an item wholly on the moving
        container lands wholly inside it, and the container cannot land on
        another container, so there is nothing there to hit.
        """
        grid = self._grid()
        grid.containers.append(Container.of("standard_vm", (4, 5), "container_d"))
        grid.items.append(self._item("straddler", (3, 3), shape=TWO_WIDE))
        grid.items.append(self._item("stayed", (4, 5)))

        displaced = grid.move_container("container_a", (2, 5))

        assert [item.id for item in displaced] == [
            "straddler"
        ], "The item being moved gives way, not the one that stayed still"
        assert [item.id for item in grid.items] == ["stayed"]
        assert grid.items[0].position == (4, 5), "The stationary item did not move"

    def test_a_container_that_would_leave_the_grid_is_refused(self):
        grid = self._grid()
        grid.items.append(self._item("on_a", (2, 3)))

        with pytest.raises(InvalidPlacementError, match="leave the grid"):
            grid.move_container("container_a", (8, 3))

        assert grid.find_container("container_a").position == (2, 3)
        assert grid.items[0].position == (2, 3), "Nothing moved"

    def test_a_container_that_would_overlap_another_is_refused(self):
        grid = self._grid()

        with pytest.raises(InvalidPlacementError, match="overlap"):
            grid.move_container("container_a", (4, 3))

        assert grid.find_container("container_a").position == (2, 3)

    def test_a_container_may_move_onto_where_it_already_is(self):
        # Its own squares are not an obstacle to itself.
        grid = self._grid()

        assert grid.move_container("container_a", (2, 3)) == []
        assert grid.find_container("container_a").position == (2, 3)

    def test_an_unknown_container_is_not_found(self):
        with pytest.raises(ItemNotFoundError):
            self._grid().move_container("no_such_container", (0, 0))

    def test_a_displaced_item_goes_to_storage(self):
        manager = InventoryManager()
        manager.grid.items.append(self._item("straddler", (3, 3), shape=TWO_WIDE))

        displaced = manager.move_container("container_a", (0, 0))

        assert [item.id for item in displaced] == ["straddler"]
        assert [item.id for item in manager.storage.items] == ["straddler"]
        assert manager.grid.items == []

    def test_the_square_a_displaced_item_leaves_is_free(self):
        """A displaced item is off the grid, so its old square takes another.

        Nothing on the grid keeps a record of what is occupied: get_item_at
        reads the list of items and can_hold reads the list of containers. So
        this is really asking whether the item was taken out of the list, but
        it is the fact a caller depends on.
        """
        grid = self._grid()
        grid.containers.append(Container.of("standard_vm", (4, 5), "container_d"))
        grid.items.append(self._item("straddler", (3, 3), shape=TWO_WIDE))
        grid.items.append(self._item("stayed", (4, 5)))

        grid.move_container("container_a", (2, 5))

        assert grid.get_item_at((3, 5)) is None, "The displaced item left no trace"
        grid.place_item(Item.of("null_blade", "newcomer"), (3, 5))
        assert grid.get_item_at((3, 5)).id == "newcomer"

    def test_the_ground_a_container_leaves_stops_being_usable(self):
        grid = self._grid()

        grid.move_container("container_a", (0, 0))

        assert (
            grid.can_hold([(2, 3)]) is False
        ), "The squares container A used to cover are bare floor now"
        assert grid.can_hold([(3, 4)]) is False
        with pytest.raises(InvalidPlacementError):
            grid.place_item(Item.of("null_blade", "nowhere"), (2, 3))

    def test_the_ground_a_container_arrives_on_becomes_usable(self):
        grid = self._grid()

        grid.move_container("container_a", (0, 0))

        assert grid.can_hold([(0, 0)]) is True
        assert grid.can_hold([(1, 1)]) is True
        # null_blade is two squares tall, so at (1,0) it covers (1,0) and
        # (1,1), which are the right-hand column of the container's new home.
        grid.place_item(Item.of("null_blade", "newcomer"), (1, 0))
        assert grid.get_item_at((1, 1)).id == "newcomer"

    def test_a_travelling_item_frees_the_square_it_came_from(self):
        grid = self._grid()
        grid.items.append(self._item("passenger", (2, 3)))

        grid.move_container("container_a", (0, 0))

        assert grid.get_item_at((2, 3)) is None, "It is not in two places at once"
        assert grid.get_item_at((0, 0)).id == "passenger"

    def test_an_item_in_storage_has_no_position(self):
        # It is off the grid, so it is an Item and not a PlacedItem.
        manager = InventoryManager()
        manager.grid.items.append(self._item("straddler", (3, 3), shape=TWO_WIDE))

        manager.move_container("container_a", (0, 0))

        assert not hasattr(manager.storage.items[0], "position")


def a_rack(*placements):
    """A manager holding these (item type, position) pairs, in this order.

    Order is the point in several tests: the grid keeps items in the order they
    were placed, and that is what decides which combination wins.
    """
    manager = InventoryManager()
    for n, (item_type, position) in enumerate(placements):
        manager.grid.place_item(Item.of(item_type, f"item{n}"), position)
    return manager


def a_wide_rack(*placements):
    """The same on one 3x3 rack. The three the game starts with are two rows
    deep, which is not enough room to stand four things around a 2x2 item."""
    manager = InventoryManager()
    manager.grid.containers = [Container.of("mesh_network_hub", (0, 0), "hub")]
    for n, (item_type, position) in enumerate(placements):
        manager.grid.place_item(Item.of(item_type, f"item{n}"), position)
    return manager


class TestCombiningItems:
    """GDD 5.3: items together in the rack combine when the shop phase begins.

    Every fixture below places real catalogue items, because the rules that
    matter -- what touches what, whether the result fits -- depend on the shapes
    those items actually have. A made-up two-square item would pass tests the
    real ones fail.
    """

    def test_two_items_together_become_the_item_they_make(self):
        rack = a_rack(("neural_link_collar", (2, 3)), ("cpu_booster", (3, 3)))
        made = rack.combine()

        assert [c.made for c in made] == ["blue_sage_collar"]
        assert [i.item_type for i in rack.grid.items] == ["blue_sage_collar"]

    def test_items_that_are_not_touching_do_not_combine(self):
        # The same two, one rack apart.
        rack = a_rack(("neural_link_collar", (2, 3)), ("cpu_booster", (6, 3)))
        assert rack.combine() == []
        assert len(rack.grid.items) == 2

    def test_touching_at_a_corner_is_not_touching(self):
        rack = a_rack(("neural_link_collar", (3, 3)), ("cpu_booster", (4, 4)))
        assert rack.combine() == []

    def test_one_item_touches_all_the_others_not_every_pair(self):
        """A Stone Golem is a Heart Container and four Stones.

        The heart is two by two, so the four stones sit around it and none of
        them touches another. Requiring every pair to touch would make this
        recipe impossible rather than merely hard.
        """
        rack = a_wide_rack(
            ("heart_container", (0, 0)),  # covers (0,0) (1,0) (0,1) (1,1)
            ("ping_flood", (2, 0)),
            ("ping_flood", (2, 1)),
            ("ping_flood", (0, 2)),
            ("ping_flood", (1, 2)),
        )
        stones = [i for i in rack.grid.items if i.item_type == "ping_flood"]
        assert len(stones) == 4
        for stone in stones:
            touching = {i.item_type for i in rack.grid.touching(stone)}
            assert "heart_container" in touching, "every stone must reach the heart"
        apart = [
            a.id
            for a in stones
            for b in stones
            if a.id != b.id and b.id not in {t.id for t in rack.grid.touching(a)}
        ]
        assert apart, "the fixture wants stones that do not all touch each other"

        assert [c.made for c in rack.combine()] == ["stone_golem"]

    def test_a_stone_that_only_reaches_another_stone_does_not_count(self):
        rack = a_wide_rack(
            ("heart_container", (0, 0)),
            ("ping_flood", (2, 0)),
            ("ping_flood", (2, 1)),
            ("ping_flood", (0, 2)),
            ("ping_flood", (2, 2)),  # touches (2,1), not the heart
        )
        assert rack.combine() == [], "three stones reach the heart, not four"

    def test_a_catalyst_is_needed_and_is_not_used_up(self):
        rack = a_rack(("crypto_mining_rig", (2, 3)), ("maneki_neko", (4, 3)))
        made = rack.combine()

        assert [c.made for c in made] == ["serverless_function"]
        assert [i.item_type for i in made[0].consumed] == ["crypto_mining_rig"]
        assert [i.item_type for i in made[0].kept] == ["maneki_neko"]
        assert [i.item_type for i in rack.grid.items] == [
            "maneki_neko"
        ], "the catalyst is still there"

    def test_without_the_catalyst_nothing_happens(self):
        rack = a_rack(("crypto_mining_rig", (2, 3)))
        assert rack.combine() == []

    def test_two_of_one_ingredient_means_two(self):
        """Long Poll is a Main Branch and two Edge Caches, not one."""
        one = a_rack(("hero_sword", (2, 3)), ("whetstone", (3, 3)))
        assert one.combine() == [], "one Edge Cache is not enough"

        two = a_rack(
            ("hero_sword", (2, 3)), ("whetstone", (3, 3)), ("whetstone", (3, 4))
        )
        assert [c.made for c in two.combine()] == ["hero_longsword"]

    def test_the_result_stands_where_its_ingredients_stood(self):
        rack = a_rack(("neural_link_collar", (2, 3)), ("cpu_booster", (3, 3)))
        made = rack.combine()

        assert made[0].position == (2, 3)
        assert set(made[0].freed) == {(2, 3), (3, 3)}
        assert rack.grid.items[0].position == (2, 3)
        assert rack.storage.items == []

    def test_a_result_too_big_for_the_gap_goes_in_the_chest(self):
        """Long Poll is three squares tall and its ingredients free a 2x2, so
        it has nowhere to stand. It is not lost."""
        rack = a_rack(
            ("hero_sword", (2, 3)), ("whetstone", (3, 3)), ("whetstone", (3, 4))
        )
        made = rack.combine()

        assert made[0].position is None
        assert rack.grid.items == []
        assert [i.item_type for i in rack.storage.items] == ["hero_longsword"]
        assert (
            rack.storage.items[0].id == made[0].made_id
        ), "the client is told an id, and that is the item it gets"

    def test_the_result_does_not_spread_beyond_the_squares_it_freed(self):
        """A combination should not take space the player was keeping."""
        rack = a_rack(
            ("neural_link_collar", (2, 3)),
            ("cpu_booster", (3, 3)),
            ("null_blade", (4, 3)),
        )
        rack.combine()

        untouched = [i for i in rack.grid.items if i.item_type == "null_blade"]
        assert untouched and untouched[0].position == (4, 3)

    def test_an_ingredient_is_not_used_by_two_combinations(self):
        """One CPU Booster between two collars makes one thing, not two."""
        rack = a_rack(
            ("neural_link_collar", (2, 3)),
            ("cpu_booster", (3, 3)),
            ("white_lily_collar", (4, 3)),
        )
        made = rack.combine()
        assert len(made) == 1, f"used the booster twice: {[c.made for c in made]}"

    def test_the_newest_item_decides_which_combination_happens(self):
        """The booster completes either collar. The one placed last wins."""
        first = a_rack(
            ("cpu_booster", (3, 3)),
            ("white_lily_collar", (4, 3)),
            ("neural_link_collar", (2, 3)),
        )
        second = a_rack(
            ("cpu_booster", (3, 3)),
            ("neural_link_collar", (2, 3)),
            ("white_lily_collar", (4, 3)),
        )

        def eaten(rack):
            return sorted(i.item_type for i in rack.combine()[0].consumed)

        assert eaten(first) != eaten(
            second
        ), "which collar was eaten should follow which was placed last"

    def test_the_same_rack_always_combines_the_same_way(self):
        def once():
            rack = a_rack(
                ("cpu_booster", (3, 3)),
                ("white_lily_collar", (4, 3)),
                ("neural_link_collar", (2, 3)),
            )
            return [
                (c.made, tuple(i.item_type for i in c.consumed)) for c in rack.combine()
            ]

        assert once() == once() == once()

    def test_separate_combinations_all_happen(self):
        rack = a_rack(
            ("neural_link_collar", (2, 3)),
            ("cpu_booster", (3, 3)),
            ("crypto_mining_rig", (6, 3)),
            ("maneki_neko", (5, 3)),
        )
        made = {c.made for c in rack.combine()}
        assert made == {"blue_sage_collar", "serverless_function"}

    def test_a_result_does_not_go_on_to_combine_in_the_same_pass(self):
        """20 items are both a result and another recipe's ingredient.

        Here the rootkit could combine with the collar directly, but the booster
        was placed last so the sage collar is made first. That collar and the
        rootkit then make an orchid collar -- next round, not this one, so the
        player sees the step and can break it up.
        """
        rack = a_wide_rack(
            ("vampire_rootkit", (0, 0)),
            ("neural_link_collar", (1, 0)),
            ("cpu_booster", (2, 0)),
        )

        first = rack.combine()
        assert [c.made for c in first] == ["blue_sage_collar"], "one step only"
        assert {i.item_type for i in rack.grid.items} == {
            "blue_sage_collar",
            "vampire_rootkit",
        }

        second = rack.combine()
        assert [c.made for c in second] == [
            "red_orchid_collar"
        ], "the next shop phase takes the next step"

    def test_an_empty_rack_combines_nothing(self):
        assert InventoryManager().combine() == []


class TestAPartThatIsAKindNotAnItem:
    """GDD 5.4: `class:fire` is any item whose icon says it is on fire.

    Hot Cell and Thermal Torch are lit by one, and eight items qualify. The
    player uses whichever they happen to hold, so the recipe names none of
    them.
    """

    def test_any_item_of_the_kind_answers_the_part(self):
        for lighter in ("thermal_throttle", "oil_lamp", "magic_torch"):
            rack = a_rack(("lump_of_coal", (2, 3)), (lighter, (3, 3)))
            made = rack.combine()

            assert [c.made for c in made] == ["burning_coal"], f"{lighter} lights it"
            assert [i.item_type for i in made[0].consumed] == ["lump_of_coal"]
            assert [i.item_type for i in made[0].kept] == [
                lighter
            ], "the fire is a catalyst, so it is still there"

    def test_an_item_of_another_kind_does_not(self):
        # An Edge Cache is of no kind at all, and a Null Blade is melee. Both
        # touch a Dead Cell happily and neither lights it.
        rack = a_rack(("lump_of_coal", (2, 3)), ("whetstone", (3, 3)))
        assert rack.combine() == []

    def test_the_item_the_recipe_makes_can_be_the_fire_it_needs(self):
        """A Hot Cell is on fire, so it lights the next one."""
        rack = a_rack(("lump_of_coal", (2, 3)), ("burning_coal", (3, 3)))
        made = rack.combine()

        assert [c.made for c in made] == ["burning_coal"]
        assert [i.id for i in made[0].consumed] == ["item0"], "the coal, not the cell"
        assert sorted(i.item_type for i in rack.grid.items) == [
            "burning_coal",
            "burning_coal",
        ]

    def test_the_fire_has_to_be_touching_like_any_part(self):
        rack = a_rack(("lump_of_coal", (2, 3)), ("thermal_throttle", (6, 3)))
        assert rack.combine() == []

    def test_it_is_promised_before_it_happens(self):
        rack = a_rack(("lump_of_coal", (2, 3)), ("thermal_throttle", (3, 3)))
        pending = rack.pending()

        assert len(pending) == 1
        assert pending[0].makes == "burning_coal"
        assert pending[0].complete
        assert pending[0].ingredients == ("item0",)
        assert pending[0].catalysts == ("item1",), "the fire is kept"


class TestWhatTheRackIsOnTheWayTo:
    """`pending` warns the player before they commit to a combination.

    It has to agree with what combining actually does, so it reads the same
    plan. A warning that promised something else would be worse than none.
    """

    def test_a_complete_set_says_it_will_combine(self):
        rack = a_rack(("neural_link_collar", (2, 3)), ("cpu_booster", (3, 3)))
        pending = rack.pending()

        assert len(pending) == 1
        assert pending[0].makes == "blue_sage_collar"
        assert pending[0].complete
        assert pending[0].have == pending[0].need == 2

    def test_asking_changes_nothing(self):
        rack = a_rack(("neural_link_collar", (2, 3)), ("cpu_booster", (3, 3)))
        rack.pending()
        rack.pending()
        assert [i.item_type for i in rack.grid.items] == [
            "neural_link_collar",
            "cpu_booster",
        ], "the rack is untouched by being asked about"

    def test_it_promises_exactly_what_combining_does(self):
        """The two read one plan, so they cannot disagree."""

        def rack():
            return a_rack(
                ("cpu_booster", (3, 3)),
                ("white_lily_collar", (4, 3)),
                ("neural_link_collar", (2, 3)),
            )

        promised = [(p.makes, sorted(p.ingredients)) for p in rack().pending()]
        happened = [
            (c.made, sorted(i.id for i in c.consumed)) for c in rack().combine()
        ]
        assert promised == happened

    def test_a_part_finished_set_counts_up(self):
        """What an item is labelled with when it is put down: 2 of 3."""
        rack = a_rack(("hero_sword", (2, 3)), ("whetstone", (3, 3)))
        pending = rack.pending()

        assert len(pending) == 1
        assert pending[0].makes == "hero_longsword"
        assert (pending[0].have, pending[0].need) == (2, 3)
        assert pending[0].missing == ("whetstone",), "and what is still wanted"
        assert not pending[0].complete

    def test_one_item_on_its_own_is_not_progress(self):
        rack = a_rack(("hero_sword", (2, 3)))
        assert rack.pending() == []

    def test_parts_that_are_not_touching_are_not_progress(self):
        rack = a_rack(("hero_sword", (2, 3)), ("whetstone", (6, 3)))
        assert rack.pending() == []

    def test_an_item_already_combining_is_not_offered_elsewhere(self):
        """It is going to combine. Telling the player what else it might have
        been would only muddle the label."""
        rack = a_wide_rack(
            ("vampire_rootkit", (0, 0)),
            ("neural_link_collar", (1, 0)),
            ("cpu_booster", (2, 0)),
        )
        pending = rack.pending()
        combining = {i for p in pending if p.complete for i in p.ingredients}
        for entry in pending:
            if entry.complete:
                continue
            assert not (
                set(entry.ingredients) & combining
            ), f"{entry.makes} offers an item that is already spoken for"


class TestWhichItemsGoTogether:
    """The static relation the client answers hover lines from."""

    def test_it_names_both_sides(self):
        from inventory_manager import combining_partners

        partners = combining_partners()
        assert "whetstone" in partners["hero_sword"]
        assert "hero_sword" in partners["whetstone"], "the relation goes both ways"

    def test_an_item_that_needs_two_of_itself_pairs_with_itself(self):
        from inventory_manager import combining_partners

        # Platinum Customer Card is two Premium Subscriptions.
        assert "premium_subscription" in combining_partners()["premium_subscription"]

    def test_an_item_in_no_recipe_is_absent(self):
        from config_loader import config_loader
        from inventory_manager import combining_partners

        partners = combining_partners()
        loose = [
            slug
            for slug, spec in config_loader.items.items()
            if not spec.recipe and slug not in partners
        ]
        assert loose, "some item should be in no recipe at all"

    def test_it_covers_every_part_of_every_recipe_that_has_two(self):
        """A recipe with one part has nobody to draw a line to.

        Nine of them turn an Unidentified Amulet into a particular amulet, which
        happens when it is bought rather than by putting it next to anything, so
        no line is the right answer.
        """
        from config_loader import config_loader
        from inventory_manager import any_of, combining_partners

        partners = combining_partners()
        alone = set()
        for spec in list(config_loader.items.values()) + list(
            config_loader.containers.values()
        ):
            for recipe in spec.recipe:
                parts = recipe.parts()
                for part in parts:
                    for slug in any_of(part):
                        if len(parts) < 2:
                            alone.add(slug)
                        else:
                            assert (
                                slug in partners
                            ), f"{slug} can be part of a recipe and has no partners"
        assert alone, "no single-part recipes at all makes the exception dead"

    def test_a_wildcard_part_is_every_item_that_answers_it(self):
        """`class:fire` draws a line to each of the eight items on fire.

        The wildcard itself is not an item, so it is never a name in the map:
        the client would have nothing to draw a line to.
        """
        from inventory_manager import any_of, combining_partners

        partners = combining_partners()
        fire = any_of("class:fire")

        assert len(fire) == 8, "setup: eight items are on fire"
        # Hot Cell is a Dead Cell lit by any of them.
        assert set(fire) <= set(partners["lump_of_coal"])
        for slug in fire:
            assert "lump_of_coal" in partners[slug], "the relation goes both ways"

        assert "class:fire" not in partners
        assert not any("class:fire" in others for others in partners.values())

    def test_two_items_answering_the_same_part_are_not_partners(self):
        """One part takes one item, so a second fire adds nothing.

        Thermal Throttle goes with the Dead Cell and the Plasma Edge it lights,
        and with no other fire.
        """
        from inventory_manager import combining_partners

        assert combining_partners()["thermal_throttle"] == [
            "lump_of_coal",
            "plasma_edge",
        ]


class TestARackTurnsWithEverythingOnIt:
    """A rack is an item that other items stand on, and that is the only
    difference. Turned, it and its passengers go round as one rigid body: the
    square of the rack each item sits on turns with the rack, and the item
    turns by the same amount so it lies the same way on the tray.

    Nothing sitting wholly on a rack can fall off it that way -- a turn maps
    the rack's squares onto themselves -- so what gets displaced is what
    straddled two racks, or what collides with something that stayed put.
    """

    def _a_rack_holding(self, manager, rack_type="network_cache"):
        """A rack two wide and three tall at the origin, with a 1x1 on it."""
        manager.grid.containers = [Container.of(rack_type, (0, 0), "rack")]
        manager.grid.items = []
        return manager

    def test_a_rack_turned_covers_the_squares_it_turned_onto(self):
        manager = InventoryManager()
        self._a_rack_holding(manager)

        manager.move_container("rack", (0, 0), Rotation.CLOCKWISE_90)

        rack = manager.grid.find_container("rack")
        assert rack.rotation == Rotation.CLOCKWISE_90
        covered = set(rack.covered_squares())
        assert (2, 0) in covered, "three squares across, turned"
        assert (0, 2) not in covered, "and not three down"

    def test_an_item_on_a_turned_rack_goes_round_with_it(self):
        manager = InventoryManager()
        self._a_rack_holding(manager)
        # A 1x1 in the far corner of a 2x3 rack.
        manager.grid.items = [Item.of("api_token", "riding").placed_at((1, 2))]

        displaced = manager.move_container("rack", (0, 0), Rotation.CLOCKWISE_90)

        assert displaced == [], "It was wholly on the rack, so it cannot fall off"
        riding = manager.grid.items[0]
        rack = manager.grid.find_container("rack")
        assert set(riding.covered_squares()) <= set(
            rack.covered_squares()
        ), "and it is still on the rack"

    def test_an_item_on_a_turned_rack_faces_the_way_the_rack_turned(self):
        manager = InventoryManager()
        self._a_rack_holding(manager)
        upright = Item.of("null_blade", "blade").placed_at((0, 0))
        manager.grid.items = [upright]

        manager.move_container("rack", (0, 0), Rotation.CLOCKWISE_90)

        blade = manager.grid.items[0]
        assert blade.rotation == Rotation.CLOCKWISE_90, "It turned with the tray"

    def test_everything_on_a_rack_stays_on_it_however_it_turns(self):
        """The property worth having. Fill a rack and turn it every way; what
        was on it is still on it, and nothing is displaced."""
        for turn in (
            Rotation.CLOCKWISE_90,
            Rotation.CLOCKWISE_180,
            Rotation.CLOCKWISE_270,
        ):
            manager = InventoryManager()
            self._a_rack_holding(manager)
            manager.grid.items = [
                Item.of("api_token", f"chip{x}{y}").placed_at((x, y))
                for x in range(2)
                for y in range(3)
            ]

            displaced = manager.move_container("rack", (0, 0), turn)

            assert displaced == [], f"nothing falls off, turned {turn.value}"
            rack = set(manager.grid.find_container("rack").covered_squares())
            assert len(manager.grid.items) == 6, f"all six still there, {turn.value}"
            for item in manager.grid.items:
                assert set(item.covered_squares()) <= rack, (
                    f"{item.id} is off the rack, turned {turn.value}"
                )

    def test_a_rack_moved_and_not_turned_is_unchanged_in_facing(self):
        manager = InventoryManager()
        self._a_rack_holding(manager)
        manager.grid.items = [Item.of("api_token", "riding").placed_at((0, 0))]

        manager.move_container("rack", (3, 0))

        assert manager.grid.find_container("rack").rotation == Rotation.NONE
        assert manager.grid.items[0].position == (3, 0), "carried, not turned"


class TestWhereAPassengerLands:
    """`server/tests/fixtures/carried_round.json` is what this side makes of a
    rack turning under an item, and the client is held to the same answers.

    They disagreed once. The client mapped the item's corner square through the
    turn, which is right for a single square and wrong for anything longer:
    the corner of a turned body is not the turned corner. A two-square item on
    a two-by-two rack came out one square off, and at the edge of the board
    that put it outside the rack it was riding.

    Regenerate with `python tools/dump_carried_round.py` after a change that is
    meant, and the client goes red until it agrees -- which is the point.
    """

    @staticmethod
    def _written_down():
        import json
        from pathlib import Path

        path = Path(__file__).parent / "fixtures" / "carried_round.json"
        return json.loads(path.read_text())

    def test_the_server_still_gives_these_answers(self):
        from grid_system import ItemShape, Rotation

        for case in self._written_down():
            tray = ItemShape(squares=[tuple(s) for s in case["tray"]])
            sits_on = tuple(case["sits_on"])
            covers = [
                (sits_on[0] + dx, sits_on[1] + dy) for dx, dy in case["rider"]
            ]
            for facing, expected in case["lands_on"].items():
                landed = tray.corner_of(covers, Rotation(int(facing)))
                assert list(landed) == expected, (
                    f"{case['name']} turned {facing}: "
                    f"{landed} where the file says {expected}. "
                    "Run `python tools/dump_carried_round.py` if that is meant."
                )

    def test_a_passenger_never_leaves_the_tray_it_rides(self):
        """The property the numbers are there to keep. A turn maps a tray's
        squares onto themselves, so nothing sitting wholly on one can fall off
        it -- and an answer that puts a rider off the tray is wrong however
        plausible it looks."""
        from grid_system import ItemShape, Rotation

        for case in self._written_down():
            squares = [tuple(s) for s in case["tray"]]
            tray = ItemShape(squares=squares)
            sits_on = tuple(case["sits_on"])
            rider = [tuple(s) for s in case["rider"]]
            covers = [(sits_on[0] + dx, sits_on[1] + dy) for dx, dy in rider]
            assert set(covers) <= set(squares), f"{case['name']} starts off the tray"

            for facing in case["lands_on"]:
                turn = Rotation(int(facing))
                corner = tray.corner_of(covers, turn)
                turned_tray = set(tray.rotate(turn).squares)
                turned_rider = ItemShape(squares=rider).rotate(turn).squares
                landed = {
                    (corner[0] + dx, corner[1] + dy) for dx, dy in turned_rider
                }
                assert landed <= turned_tray, (
                    f"{case['name']} turned {facing} lands on {sorted(landed)}, "
                    f"and the tray is {sorted(turned_tray)}"
                )


class TestAnAnchorUnderATurningRack:
    """An anchor points straight up in world space however its item is turned
    (`^` in a map, grid_system.ANCHOR). A rack turning underneath is a turn
    like any other, so the rule has to survive it.

    Emergency Hotfix is the shape for it: a star, an anchor and a footprint in
    one column, so where the star lands says which way the item is really
    facing.
    """

    def _a_potion_on_a_rack(self, turn):
        from containers import Container
        from grid_system import Rotation
        from items import Item

        manager = InventoryManager()
        manager.grid.containers = [Container.of("network_cache", (2, 2), "rack")]
        manager.grid.items = [
            Item.of("emergency_hotfix", "potion").placed_at((2, 3))
        ]
        manager.move_container("rack", (2, 2), turn)
        return manager.grid.items[0]

    def test_the_anchor_still_points_up_when_the_rack_turns(self):
        from grid_system import Rotation

        for turn in Rotation:
            potion = self._a_potion_on_a_rack(turn)
            covered = set(potion.covered_squares())
            star = set(potion.zone_squares()["star"])
            above = {(x, y - 1) for x, y in covered} - covered

            assert star, f"the rack turned {turn.value} and the star vanished"
            assert star & above, (
                f"rack turned {turn.value}: the star is at {sorted(star)} and "
                f"the squares above the item are {sorted(above)}"
            )

    def test_a_potion_upside_down_still_has_its_star_above_it(self):
        """The case the rule was never checked against, and the one it got
        wrong. Turned half round the anchor is the lower of the potion's two
        squares, so an aura that stopped at the square above it would stop
        inside the potion -- leaving it with no star at all. The wiki: the star
        "will always be placed above the Potion, rather than rotating along
        with the item"."""
        from grid_system import Rotation

        potion = self._a_potion_on_a_rack(Rotation.CLOCKWISE_180)
        covered = set(potion.covered_squares())
        star = potion.zone_squares()["star"]

        assert len(star) == 1, "one star, as at every other rotation"
        assert star[0] not in covered, "and it is clear of the potion"
        assert star[0][1] == min(y for _, y in covered) - 1, (
            "directly above it"
        )

    def test_the_item_faces_the_way_the_rack_turned_it(self):
        from grid_system import Rotation

        for turn in (
            Rotation.NONE,
            Rotation.CLOCKWISE_90,
            Rotation.CLOCKWISE_180,
            Rotation.CLOCKWISE_270,
        ):
            assert self._a_potion_on_a_rack(turn).rotation == turn
