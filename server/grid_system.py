"""
Grid System for Inventory Management
Handles multi-square items, rotation, and container/backpack system
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


class Rotation(Enum):
    """Rotation states for items"""

    NONE = 0
    CLOCKWISE_90 = 90
    CLOCKWISE_180 = 180
    CLOCKWISE_270 = 270


@dataclass
class ItemShape:
    """Define the shape of a multi-square item"""

    # List of (x, y) offsets from the anchor point (0, 0)
    # For example, a 2x2 square would be [(0,0), (1,0), (0,1), (1,1)]
    squares: List[Tuple[int, int]]
    name: str = ""

    def rotate(self, rotation: Rotation) -> "ItemShape":
        """Return a rotated version of the shape"""
        if rotation == Rotation.NONE:
            return self

        rotated_squares = []
        for x, y in self.squares:
            if rotation == Rotation.CLOCKWISE_90:
                # (x, y) -> (y, -x)
                rotated_squares.append((y, -x))
            elif rotation == Rotation.CLOCKWISE_180:
                # (x, y) -> (-x, -y)
                rotated_squares.append((-x, -y))
            elif rotation == Rotation.CLOCKWISE_270:
                # (x, y) -> (-y, x)
                rotated_squares.append((-y, x))

        # Normalize to ensure top-left is at (0, 0)
        if rotated_squares:
            min_x = min(x for x, y in rotated_squares)
            min_y = min(y for x, y in rotated_squares)
            rotated_squares = [(x - min_x, y - min_y) for x, y in rotated_squares]

        return ItemShape(rotated_squares, self.name)

    def get_bounds(self) -> Tuple[int, int]:
        """Get width and height of the shape"""
        if not self.squares:
            return 0, 0
        max_x = max(x for x, y in self.squares)
        max_y = max(y for x, y in self.squares)
        return max_x + 1, max_y + 1


# Common item shapes
SHAPES = {
    "1x1": ItemShape([(0, 0)], "1x1"),
    "1x2": ItemShape([(0, 0), (0, 1)], "1x2"),
    "2x1": ItemShape([(0, 0), (1, 0)], "2x1"),
    "2x2": ItemShape([(0, 0), (1, 0), (0, 1), (1, 1)], "2x2"),
    "1x3": ItemShape([(0, 0), (0, 1), (0, 2)], "1x3"),
    "3x1": ItemShape([(0, 0), (1, 0), (2, 0)], "3x1"),
    "L_shape": ItemShape([(0, 0), (0, 1), (1, 1)], "L_shape"),
    "T_shape": ItemShape([(1, 0), (0, 1), (1, 1), (2, 1)], "T_shape"),
    "2x3": ItemShape([(0, 0), (1, 0), (0, 1), (1, 1), (0, 2), (1, 2)], "2x3"),
    "3x2": ItemShape([(0, 0), (1, 0), (2, 0), (0, 1), (1, 1), (2, 1)], "3x2"),
    # Food shapes (like Banana in Backpack Battles)
    "banana": ItemShape([(0, 0), (1, 0), (1, 1), (2, 1)], "banana"),
    "pizza_slice": ItemShape([(0, 0), (1, 0), (0, 1)], "pizza_slice"),
}


@dataclass
class GridItem:
    """An item placed on a grid"""

    item_id: str
    shape: ItemShape
    position: Tuple[int, int]  # Top-left position on grid
    rotation: Rotation = Rotation.NONE

    def get_occupied_squares(self) -> List[Tuple[int, int]]:
        """Get all grid squares this item occupies"""
        rotated_shape = self.shape.rotate(self.rotation)
        return [
            (self.position[0] + dx, self.position[1] + dy)
            for dx, dy in rotated_shape.squares
        ]


@dataclass
class Container:
    """A container (backpack/server rack) that provides grid space"""

    container_id: str
    name: str
    grid_size: Tuple[int, int]  # (width, height) of internal grid
    position: Optional[Tuple[int, int]] = None  # Position in main grid if placed
    shape: ItemShape = field(
        default_factory=lambda: SHAPES["2x2"]
    )  # Shape it takes in main grid

    def __post_init__(self):
        # Initialize internal grid as 2D list of booleans
        width, height = self.grid_size
        self.grid = [[False for _ in range(width)] for _ in range(height)]
        self.items: Dict[str, GridItem] = {}

    def can_place_item(self, item: GridItem, position: Tuple[int, int]) -> bool:
        """Check if item can be placed at position in this container"""
        item.position = position
        occupied = item.get_occupied_squares()

        # Check bounds
        for x, y in occupied:
            if x < 0 or x >= self.grid_size[0] or y < 0 or y >= self.grid_size[1]:
                return False
            if self.grid[y][x]:  # Already occupied (grid is [row][col])
                return False
        return True

    def place_item(self, item: GridItem, position: Tuple[int, int]) -> bool:
        """Place item in container"""
        if not self.can_place_item(item, position):
            return False

        item.position = position
        item.container_id = self.container_id
        occupied = item.get_occupied_squares()

        for x, y in occupied:
            self.grid[y][x] = True

        self.items[item.item_id] = item
        return True

    def remove_item(self, item_id: str) -> Optional[GridItem]:
        """Remove item from container"""
        if item_id not in self.items:
            return None

        item = self.items[item_id]
        occupied = item.get_occupied_squares()

        for x, y in occupied:
            self.grid[y][x] = False

        del self.items[item_id]
        return item


@dataclass
class InventoryGrid:
    """Main inventory grid system"""

    main_grid_size: Tuple[int, int] = (7, 9)  # Main "server room" size

    def __init__(self, main_grid_size: Tuple[int, int] = (7, 9)):
        self.main_grid_size = main_grid_size
        width, height = main_grid_size
        self.main_grid = [[False for _ in range(width)] for _ in range(height)]
        self.containers: Dict[str, Container] = {}
        self.items: Dict[str, GridItem] = {}  # Items in main grid
        self.container_positions: Dict[
            str, Tuple[int, int]
        ] = {}  # Container positions in main grid

    def add_container(self, container: Container, position: Tuple[int, int]) -> bool:
        """Add a container to the main grid"""
        # Check if container can be placed
        container_item = GridItem(
            item_id=container.container_id, shape=container.shape, position=position
        )

        if not self.can_place_in_main(container_item):
            return False

        # Place container
        occupied = container_item.get_occupied_squares()
        for x, y in occupied:
            self.main_grid[y][x] = True

        container.position = position
        self.containers[container.container_id] = container
        self.container_positions[container.container_id] = position
        return True

    def can_place_in_main(self, item: GridItem) -> bool:
        """Check if item can be placed in main grid"""
        occupied = item.get_occupied_squares()

        for x, y in occupied:
            if (
                x < 0
                or x >= self.main_grid_size[0]
                or y < 0
                or y >= self.main_grid_size[1]
            ):
                return False
            if self.main_grid[y][x]:
                return False
        return True

    def place_item_in_main(self, item: GridItem, position: Tuple[int, int]) -> bool:
        """Place item directly in main grid"""
        item.position = position
        if not self.can_place_in_main(item):
            return False

        occupied = item.get_occupied_squares()
        for x, y in occupied:
            self.main_grid[y][x] = True

        item.container_id = None
        self.items[item.item_id] = item
        return True

    def get_all_items(self) -> List[GridItem]:
        """Get all items (in main grid and containers)"""
        all_items = list(self.items.values())
        for container in self.containers.values():
            all_items.extend(container.items.values())
        return all_items

    def get_adjacent_items(self, item: GridItem) -> List[GridItem]:
        """Get all items adjacent to the given item"""
        adjacent = []
        item_squares = set(item.get_occupied_squares())

        # Get adjacent squares (orthogonal only)
        adjacent_squares = set()
        for x, y in item_squares:
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                adj_square = (x + dx, y + dy)
                if adj_square not in item_squares:
                    adjacent_squares.add(adj_square)

        # Check which items occupy these squares
        if item.container_id:
            # Item is in a container, only check items in same container
            container = self.containers[item.container_id]
            for other_item in container.items.values():
                if other_item.item_id != item.item_id:
                    other_squares = set(other_item.get_occupied_squares())
                    if adjacent_squares & other_squares:
                        adjacent.append(other_item)
        else:
            # Item is in main grid
            for other_item in self.items.values():
                if other_item.item_id != item.item_id:
                    other_squares = set(other_item.get_occupied_squares())
                    if adjacent_squares & other_squares:
                        adjacent.append(other_item)

        return adjacent

    def render_ascii(self) -> str:
        """Render the grid as ASCII art"""
        output = []

        # Main grid
        output.append("=== MAIN SERVER ROOM ===")
        output.append("  " + "".join(str(i) for i in range(self.main_grid_size[0])))

        # Create display grid
        display = [
            [" " for _ in range(self.main_grid_size[0])]
            for _ in range(self.main_grid_size[1])
        ]

        # Mark containers
        for container_id, pos in self.container_positions.items():
            container = self.containers[container_id]
            container_item = GridItem(container_id, container.shape, pos)
            for x, y in container_item.get_occupied_squares():
                if 0 <= x < self.main_grid_size[0] and 0 <= y < self.main_grid_size[1]:
                    display[y][x] = "█"

        # Mark items
        for item in self.items.values():
            for x, y in item.get_occupied_squares():
                if 0 <= x < self.main_grid_size[0] and 0 <= y < self.main_grid_size[1]:
                    display[y][x] = item.item_id[0].upper()

        # Print grid
        for i, row in enumerate(display):
            output.append(f"{i} " + "".join(row))

        # Show containers
        for container_id, container in self.containers.items():
            output.append(f"\n=== {container.name} ({container_id}) ===")
            output.append("  " + "".join(str(i) for i in range(container.grid_size[0])))

            # Create container display
            c_display = [
                [" " for _ in range(container.grid_size[0])]
                for _ in range(container.grid_size[1])
            ]

            for item in container.items.values():
                for x, y in item.get_occupied_squares():
                    if (
                        0 <= x < container.grid_size[0]
                        and 0 <= y < container.grid_size[1]
                    ):
                        c_display[y][x] = item.item_id[0].upper()

            for i, row in enumerate(c_display):
                output.append(f"{i} " + "".join(row))

        return "\n".join(output)


# Container types (Server Racks)
def create_standard_containers():
    """Create standard container types"""
    return {
        "mini_rack": Container(
            container_id="mini_rack",
            name="Mini Server Rack",
            grid_size=(3, 4),
            shape=SHAPES["2x2"],
        ),
        "standard_rack": Container(
            container_id="standard_rack",
            name="Standard Server Rack",
            grid_size=(4, 5),
            shape=ItemShape([(0, 0), (1, 0), (0, 1), (1, 1), (0, 2), (1, 2)], "2x3"),
        ),
        "enterprise_rack": Container(
            container_id="enterprise_rack",
            name="Enterprise Server Rack",
            grid_size=(5, 6),
            shape=ItemShape(
                [
                    (0, 0),
                    (1, 0),
                    (2, 0),
                    (0, 1),
                    (1, 1),
                    (2, 1),
                    (0, 2),
                    (1, 2),
                    (2, 2),
                ],
                "3x3",
            ),
        ),
    }


if __name__ == "__main__":
    # Demo the grid system
    print("Grid System Demo\n")

    # Create inventory
    inventory = InventoryGrid()

    # Add a mini server rack
    mini_rack = Container("rack1", "Mini Rack", (3, 4), shape=SHAPES["2x2"])
    inventory.add_container(mini_rack, (1, 1))

    # Add items to the rack
    item1 = GridItem("bug1", SHAPES["1x2"], (0, 0))
    mini_rack.place_item(item1, (0, 0))

    item2 = GridItem("shield1", SHAPES["L_shape"], (0, 0))
    mini_rack.place_item(item2, (1, 1))

    # Add items to main grid
    item3 = GridItem("infra1", SHAPES["2x2"], (0, 0))
    inventory.place_item_in_main(item3, (4, 2))

    # Demonstrate rotation
    item4 = GridItem("weapon1", SHAPES["1x3"], (0, 0), rotation=Rotation.CLOCKWISE_90)
    inventory.place_item_in_main(item4, (5, 5))

    # Print the grid
    print(inventory.render_ascii())

    # Test adjacency
    print("\nAdjacency test:")
    print(
        f"Items adjacent to bug1: {[i.item_id for i in inventory.get_adjacent_items(item1)]}"
    )
    print(
        f"Items adjacent to shield1: {[i.item_id for i in inventory.get_adjacent_items(item2)]}"
    )
