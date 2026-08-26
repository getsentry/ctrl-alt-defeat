"""
Server containers: the squares of the grid where items can be placed.

A container covers the squares of its shape, offset from its position. Shapes
are not always rectangular, so a container has no width and no height.
"""

from typing import List, Optional, Set, Tuple

from grid_system import ItemShape, Rotation
from items import Item, PlacedItem
from utils import Position, Shape

# The grid is 9 squares wide and 7 squares tall.
GRID_SIZE = (9, 7)

# The containers a session starts with, centred horizontally on the grid.
STARTING_CONTAINERS = [
    ("container_a", "standard_vm", (2, 3)),
    ("container_b", "standard_vm", (4, 3)),
    ("container_c", "standard_vm", (6, 3)),
]


class Container(PlacedItem):
    """An item on the grid whose squares are for other items to sit on.

    It adds nothing to a placed item. A container is bought from the same shop,
    built from the same catalogue and stands on the same grid, so it is an item
    that provides squares rather than filling them.

    What separates the two is which list a thing is in, not what it is: a
    session keeps its containers apart from its items, and the placement rules
    read one list for the squares on offer and the other for the squares
    already taken.
    """

    @classmethod
    def of(
        cls,
        container_type: str,
        position: Position,
        container_id: str,
        rotation: Rotation = Rotation.NONE,
    ) -> "Container":
        """Build a container of a type declared in containers.json."""
        item = Item.of(container_type, container_id)
        return cls(**item.item_fields(), position=position, rotation=rotation)


def starting_containers() -> List[Container]:
    """The containers a new session begins with"""
    return [
        Container.of(container_type, position, container_id)
        for container_id, container_type, position in STARTING_CONTAINERS
    ]


class PlacementValidator:
    """Validates item placement considering containers"""

    def __init__(self, main_grid_size: Tuple[int, int] = GRID_SIZE):
        self.main_grid_size = main_grid_size
        self.containers: List[Container] = []
        self.available_squares: Set[Position] = set()  # Squares available for items
        self.container_squares: Set[Position] = set()  # Squares covered by containers
        self.item_squares: Set[Position] = set()  # Squares occupied by items

    def add_container(self, container: Container) -> bool:
        """Add a container and update available squares"""
        covered = set(container.covered_squares())

        # Verify all squares are in bounds and not covered by another container
        for x, y in covered:
            if x < 0 or x >= self.main_grid_size[0]:
                return False
            if y < 0 or y >= self.main_grid_size[1]:
                return False
            if (x, y) in self.container_squares:
                return False  # Already covered by another container

        self.containers.append(container)
        self.container_squares.update(covered)

        # A container's own squares are the space it offers to items
        self.available_squares.update(covered)

        return True

    def _squares_for(self, item_position: Position, item_shape: ItemShape) -> Shape:
        """The grid squares an item of this shape covers at this position"""
        return [
            (item_position[0] + dx, item_position[1] + dy)
            for dx, dy in item_shape.squares
        ]

    def validate_item_placement(
        self, item_position: Position, item_shape: ItemShape
    ) -> bool:
        """Check if an item can be placed at the given position"""
        for x, y in self._squares_for(item_position, item_shape):
            # Must be in an available square (provided by a container)
            if (x, y) not in self.available_squares:
                return False
            # Must not be already occupied by another item
            if (x, y) in self.item_squares:
                return False

        return True

    def place_item(self, item_position: Position, item_shape: ItemShape) -> bool:
        """Place an item if valid"""
        if not self.validate_item_placement(item_position, item_shape):
            return False

        self.item_squares.update(self._squares_for(item_position, item_shape))
        return True

    def get_container_at_position(self, position: Position) -> Optional[Container]:
        """Find which container covers a given square"""
        for container in self.containers:
            if position in container.covered_squares():
                return container
        return None

    def get_containers_for_item(
        self, item_position: Position, item_shape: ItemShape
    ) -> List[Container]:
        """Get all containers that an item overlaps with"""
        containers = []
        seen_ids = set()
        for x, y in self._squares_for(item_position, item_shape):
            container = self.get_container_at_position((x, y))
            if container and container.id not in seen_ids:
                containers.append(container)
                seen_ids.add(container.id)

        return containers
