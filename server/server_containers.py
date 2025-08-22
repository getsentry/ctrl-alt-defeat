"""
Server containers - items that provide grid space for other items
Servers are placed in the main grid and provide internal storage space
"""

from dataclasses import dataclass, field
from typing import List, Optional, Set, Tuple

from grid_system import SHAPES, ItemShape, Rotation
from item_effects import ItemSpec


@dataclass
class ServerContainer:
    """
    A server rack/container that provides grid space
    This is an item that can be placed in the main grid
    """

    # Item properties
    spec: ItemSpec
    position: Tuple[int, int]  # Position in main grid
    uid: str
    shape: ItemShape
    rotation: Rotation = field(default=Rotation.NONE)

    def get_occupied_squares(self) -> List[Tuple[int, int]]:
        """Get all main grid squares this container occupies"""
        rotated_shape = self.shape.rotate(self.rotation)
        return [
            (self.position[0] + dx, self.position[1] + dy)
            for dx, dy in rotated_shape.squares
        ]

    def get_internal_squares(self) -> Set[Tuple[int, int]]:
        """Get all internal grid squares this container provides (in global coordinates)"""
        # The container's shape IS its internal space
        # If it's T-shaped, you get T-shaped internal space
        return set(self.get_occupied_squares())


def create_server_containers():
    """Create server containers from JSON configuration"""
    from config_loader import create_server_containers_from_config

    return create_server_containers_from_config()


class PlacementValidator:
    """Validates item placement considering containers"""

    def __init__(self, main_grid_size: Tuple[int, int] = (7, 9)):
        self.main_grid_size = main_grid_size
        self.containers: List[ServerContainer] = []
        self.available_squares: Set[
            Tuple[int, int]
        ] = set()  # Squares available for items
        self.container_squares: Set[
            Tuple[int, int]
        ] = set()  # Squares occupied by containers
        self.item_squares: Set[Tuple[int, int]] = set()  # Squares occupied by items

    def add_container(self, container: ServerContainer) -> bool:
        """Add a container and update available squares"""
        # Check if container can be placed in main grid
        container_occupied = set(container.get_occupied_squares())

        # Verify all squares are in bounds and not occupied by another container
        for x, y in container_occupied:
            if x < 0 or x >= self.main_grid_size[0]:
                return False
            if y < 0 or y >= self.main_grid_size[1]:
                return False
            if (x, y) in self.container_squares:
                return False  # Already occupied by another container

        # Place container
        self.containers.append(container)
        self.container_squares.update(container_occupied)

        # Add internal squares as available
        internal_squares = container.get_internal_squares()
        self.available_squares.update(internal_squares)

        return True

    def validate_item_placement(
        self,
        item_position: Tuple[int, int],
        item_shape: ItemShape,
        item_rotation: Rotation = Rotation.NONE,
    ) -> bool:
        """Check if an item can be placed at the given position"""
        # Get squares the item would occupy
        rotated_shape = item_shape.rotate(item_rotation)
        item_squares = [
            (item_position[0] + dx, item_position[1] + dy)
            for dx, dy in rotated_shape.squares
        ]

        # Check each square
        for x, y in item_squares:
            # Must be in an available square (provided by a container)
            if (x, y) not in self.available_squares:
                return False
            # Must not be already occupied by another item
            if (x, y) in self.item_squares:
                return False

        return True

    def place_item(
        self,
        item_position: Tuple[int, int],
        item_shape: ItemShape,
        item_rotation: Rotation = Rotation.NONE,
    ) -> bool:
        """Place an item if valid"""
        if not self.validate_item_placement(item_position, item_shape, item_rotation):
            return False

        rotated_shape = item_shape.rotate(item_rotation)
        item_squares = [
            (item_position[0] + dx, item_position[1] + dy)
            for dx, dy in rotated_shape.squares
        ]

        self.item_squares.update(item_squares)
        return True

    def get_container_at_position(
        self, position: Tuple[int, int]
    ) -> Optional[ServerContainer]:
        """Find which container provides a given square"""
        for container in self.containers:
            if position in container.get_internal_squares():
                return container
        return None

    def get_containers_for_item(
        self,
        item_position: Tuple[int, int],
        item_shape: ItemShape,
        item_rotation: Rotation = Rotation.NONE,
    ) -> List[ServerContainer]:
        """Get all containers that an item overlaps with"""
        # Get squares the item occupies
        rotated_shape = item_shape.rotate(item_rotation)
        item_squares = [
            (item_position[0] + dx, item_position[1] + dy)
            for dx, dy in rotated_shape.squares
        ]

        # Find all containers that provide any of these squares
        containers = []
        seen_uids = set()
        for x, y in item_squares:
            container = self.get_container_at_position((x, y))
            if container and container.uid not in seen_uids:
                containers.append(container)
                seen_uids.add(container.uid)

        return containers


if __name__ == "__main__":
    # Demo the container system
    print("Server Container System Demo\n")

    # Create containers
    containers = create_server_containers()

    # Create a validator
    validator = PlacementValidator()

    # Add a standard VM at position (1, 1)
    standard_vm = ServerContainer(
        spec=containers["standard_vm"]["spec"],
        position=(1, 1),
        uid="vm1",
        shape=containers["standard_vm"]["spec"].shape,
    )

    if validator.add_container(standard_vm):
        print(f"Added standard VM at {standard_vm.position}")
        print(f"  Occupies main grid squares: {standard_vm.get_occupied_squares()}")
        print(f"  Provides internal squares: {standard_vm.get_internal_squares()}")

    # Try to place an item
    if validator.validate_item_placement((1, 1), SHAPES["1x1"] if SHAPES else None):
        print("\nCan place 1x1 item at (1, 1) - inside the VM!")

    if not validator.validate_item_placement((0, 0), SHAPES["1x1"] if SHAPES else None):
        print("Cannot place 1x1 item at (0, 0) - no container there!")

    # Add an edge node
    edge_node = ServerContainer(
        spec=containers["edge_node"]["spec"],
        position=(4, 2),
        uid="edge1",
        shape=containers["edge_node"]["spec"].shape,
    )

    if validator.add_container(edge_node):
        print(f"\nAdded edge node at {edge_node.position}")
        print(
            f"  Provides {len(edge_node.get_internal_squares())} internal squares (horizontal 2x1)"
        )
