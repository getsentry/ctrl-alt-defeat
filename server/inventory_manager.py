"""
Inventory management system for the autobattler game
Manages both the 9x7 grid with server containers and unlimited storage
"""

from typing import Dict, List, Optional, Sequence, Set, Union

from containers import Container, starting_containers
from grid_system import Rotation
from items import Item, PlacedItem
from utils import Position


class InvalidPlacementError(Exception):
    """Raised when an item cannot be placed at the specified location"""

    pass


class ItemNotFoundError(Exception):
    """Raised when an item cannot be found"""

    pass


class InventoryGrid:
    """
    Manages the 9x7 grid with server containers
    Items can only be placed on server containers
    """

    def __init__(self):
        """Initialize the grid with the starting server containers"""
        self.width = 9
        self.height = 7
        self.items: List[PlacedItem] = []
        self.containers: List[Container] = starting_containers()

    def _container_squares(self) -> Set[Position]:
        """Every grid square covered by a container"""
        return {
            square
            for container in self.containers
            for square in container.covered_squares()
        }

    def can_hold(self, squares: Sequence[Position]) -> bool:
        """
        Whether the grid can hold something covering these squares.

        This takes the squares rather than a shape and a position, because a
        turned item covers different squares from the ones its shape lists.
        Asking with a shape is how a rotation gets lost.
        """
        covered = self._container_squares()

        for x, y in squares:
            # Check bounds
            if x < 0 or x >= self.width or y < 0 or y >= self.height:
                return False

            # Items sit on containers, never on bare grid
            if (x, y) not in covered:
                return False

        return True

    def get_item_at(self, position: Position) -> Optional[PlacedItem]:
        """Get the item covering a specific square"""
        for item in self.items:
            if position in item.covered_squares():
                return item
        return None

    def place_item(
        self,
        item: Item,
        position: Position,
        rotation: Optional[Rotation] = None,
    ) -> None:
        """Place an item on the grid, facing the way it is asked to.

        Told nothing, it keeps facing the way it already does, so a move that
        is only a move does not quietly straighten an item out.
        """
        if rotation is None:
            rotation = getattr(item, "rotation", Rotation.NONE)
        placed = item.placed_at(position, rotation)

        # The whole item, as it is turned, has to sit on containers
        if not self.can_hold(placed.covered_squares()):
            raise InvalidPlacementError(
                f"Item at position {position} does not fit entirely on server containers"
            )

        # And it cannot land on another item
        for square in placed.covered_squares():
            existing_item = self.get_item_at(square)
            if existing_item is not None:
                raise InvalidPlacementError(
                    f"Position {square} is already occupied by item {existing_item.id}"
                )

        self.items.append(placed)

    def remove_item_at(self, position: Position) -> PlacedItem:
        """Remove and return the item at a position"""
        item = self.get_item_at(position)
        if item is None:
            raise ItemNotFoundError(f"No item at position {position}")

        self.items.remove(item)
        return item

    def get_battle_items(self) -> List[PlacedItem]:
        """Get all items formatted for battle"""
        return self.items.copy()

    def find_container(self, container_id: str) -> Optional[Container]:
        """The container with this id, if the grid holds one"""
        for container in self.containers:
            if container.id == container_id:
                return container
        return None

    def move_container(
        self, container_id: str, position: Position
    ) -> List[PlacedItem]:
        """Move a container, and everything resting on it, to a new anchor.

        Every item with a square on the container travels with it, shifted by
        the same amount. An item that cannot stand where it lands is taken off
        the grid and returned, for the caller to put in storage; see
        docs/moving_containers.md.

        The container itself is all or nothing. If it would leave the grid or
        land on another container, nothing moves at all.
        """
        container = self.find_container(container_id)
        if container is None:
            raise ItemNotFoundError(f"No container with id {container_id}")

        # model_copy rather than placed_at, which would hand back a PlacedItem
        # and quietly take the container out of the list of containers.
        moved = container.model_copy(update={"position": position})
        dx = position[0] - container.position[0]
        dy = position[1] - container.position[1]

        others = [c for c in self.containers if c.id != container_id]
        self._check_container_fits(moved, others)

        # Everything with a square on the container comes with it. Not only
        # what sits wholly inside: half an item cannot stay behind.
        carried_squares = set(container.covered_squares())
        travellers = [
            item
            for item in self.items
            if carried_squares & set(item.covered_squares())
        ]
        stayed = [item for item in self.items if item not in travellers]

        self.containers = others + [moved]

        # Travellers keep their positions relative to each other, so they can
        # only collide with an item that stayed put.
        taken_squares = {
            square for item in stayed for square in item.covered_squares()
        }
        self.items = stayed
        displaced: List[PlacedItem] = []
        for item in travellers:
            shifted = item.placed_at(
                (item.position[0] + dx, item.position[1] + dy), item.rotation
            )
            squares = set(shifted.covered_squares())
            if self.can_hold(shifted.covered_squares()) and not (
                squares & taken_squares
            ):
                self.items.append(shifted)
                taken_squares |= squares
            else:
                displaced.append(shifted)

        return displaced

    def _check_container_fits(
        self, container: Container, others: Sequence[Container]
    ) -> None:
        """Whether a container may stand on these squares, or why it may not"""
        occupied = {
            square for other in others for square in other.covered_squares()
        }
        for x, y in container.covered_squares():
            if x < 0 or x >= self.width or y < 0 or y >= self.height:
                raise InvalidPlacementError(
                    f"A container at {container.position} would leave the grid"
                )
            if (x, y) in occupied:
                raise InvalidPlacementError(
                    f"A container at {container.position} would overlap another"
                )


class InventoryStorage:
    """
    Manages the unlimited storage area for unused items
    """

    def __init__(self):
        """Initialize empty storage"""
        self.items: List[Item] = []

    def add_item(self, item: Item) -> None:
        """Add an item to storage, taking it off the grid if it was on it"""
        self.items.append(item.stored() if isinstance(item, PlacedItem) else item)

    def remove_item(self, item_id: str) -> Item:
        """Remove and return an item by ID"""
        for item in self.items:
            if item.id == item_id:
                self.items.remove(item)
                return item
        raise ItemNotFoundError(f"Item with ID {item_id} not found in storage")

    def find_item(self, item_id: str) -> Optional[Item]:
        """Find an item by ID"""
        for item in self.items:
            if item.id == item_id:
                return item
        return None

    def get_all(self) -> List[Item]:
        """Get all items in storage"""
        return self.items.copy()


class InventoryManager:
    """
    High-level inventory management coordinating grid and storage
    """

    def __init__(self):
        """Initialize with grid and storage"""
        self.grid = InventoryGrid()
        self.storage = InventoryStorage()

    def place_item(
        self,
        item: Item,
        placement: Union[str, Position],
        rotation: Optional[Rotation] = None,
    ) -> bool:
        """
        Place an item either in storage or on the grid

        Args:
            item: The item to place
            placement: Either "storage" or (x, y) coordinates
            rotation: Which way it faces on the grid. Told nothing, it keeps
                facing the way it already does.

        Returns:
            True if successful
        """
        try:
            if placement == "storage":
                self.storage.add_item(item)
            else:
                # Placement is grid coordinates
                self.grid.place_item(item, placement, rotation)
            return True
        except InvalidPlacementError:
            return False

    def move_item(
        self,
        item_id: str,
        from_location: Union[str, Position],
        to_location: Union[str, Position],
        rotation: Optional[Rotation] = None,
    ) -> None:
        """
        Move an item between storage and grid

        Args:
            item_id: ID of the item to move
            from_location: Either "storage" or (x, y) coordinates
            to_location: Either "storage" or (x, y) coordinates

        Raises:
            ItemNotFoundError: If item not found at source location
            InvalidPlacementError: If destination is invalid
        """
        # Find and remove from source
        if from_location == "storage":
            item = self.storage.remove_item(item_id)
        else:
            # Remove from grid position
            item = self.grid.remove_item_at(from_location)
            if item.id != item_id:
                # Wrong item, put it back
                self.grid.place_item(item, from_location)
                raise ItemNotFoundError(
                    f"Item {item_id} not found at position {from_location}"
                )

        # Place at destination
        try:
            if to_location == "storage":
                self.storage.add_item(item)
            else:
                self.grid.place_item(item, to_location, rotation)
        except Exception:
            # Whatever went wrong, the item goes back where it came from, and
            # the caller still hears about it.
            if from_location == "storage":
                self.storage.add_item(item)
            else:
                self.grid.place_item(item, from_location)
            raise

    def move_container(self, container_id: str, position: Position) -> List[Item]:
        """Move a container and everything resting on it.

        Returns the items that could not stand where they landed, which have
        been put in storage. The caller passes them on so that the client knows
        which items moved without it, rather than having to work that out by
        comparing two lists of storage.
        """
        displaced = self.grid.move_container(container_id, position)
        stored = [item.stored() for item in displaced]
        for item in stored:
            self.storage.add_item(item)
        return stored

    def get_battle_inventory(self) -> List[PlacedItem]:
        """Get only grid items for battle (storage items not used)"""
        return self.grid.get_battle_items()

    def remove_item(
        self, location: Optional[Position] = None, item_id: Optional[str] = None
    ) -> Optional[Item]:
        """
        Remove an item from either grid or storage

        Args:
            location: Grid position (if removing from grid)
            item_id: Item ID (if removing from storage)

        Returns:
            The removed item or None
        """
        try:
            if location is not None:
                # Remove from grid
                return self.grid.remove_item_at(location)
            elif item_id is not None:
                # Try storage first
                item = self.storage.find_item(item_id)
                if item:
                    return self.storage.remove_item(item_id)

                # Try grid
                for grid_item in self.grid.items:
                    if grid_item.id == item_id:
                        return self.grid.remove_item_at(grid_item.position)

            return None
        except ItemNotFoundError:
            return None

    def get_state(self) -> Dict:
        """The full inventory state, as typed items and containers"""
        return {
            "grid": self.grid.items.copy(),
            "storage": self.storage.items.copy(),
            "containers": self.grid.containers.copy(),
        }

    def restore_state(self, state: Dict) -> None:
        """Restore inventory from saved state

        Saved state has been through JSON, so the items arrive as plain data and
        the models turn them back into items here.
        """
        self.grid.items = [PlacedItem.model_validate(i) for i in state.get("grid", [])]
        self.storage.items = [Item.model_validate(i) for i in state.get("storage", [])]
        if "containers" in state:
            self.grid.containers = [
                Container.model_validate(c) for c in state["containers"]
            ]
