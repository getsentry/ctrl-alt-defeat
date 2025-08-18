"""
Server containers - items that provide grid space for other items
Servers are placed in the main grid and provide internal storage space
"""

from dataclasses import dataclass
from typing import Any, List, Optional, Set, Tuple

from grid_system import SHAPES, ItemShape, Rotation
from item_effects import BuffEffect, ItemSpec, PassiveTrigger, StatModEffect


@dataclass
class ServerContainer:
    """
    A server rack/container that provides grid space
    This is an item that can be placed in the main grid
    """

    # Item properties
    spec: Any  # ItemSpec - the item specification with effects
    position: Tuple[int, int]  # Position in main grid
    uid: str

    # Container properties
    internal_grid_size: Tuple[int, int]  # (width, height) of internal storage
    shape: Any = None  # ItemShape - shape it takes in main grid
    rotation: Any = None  # Rotation

    def __post_init__(self):
        """Initialize with defaults"""
        if self.shape is None and SHAPES:
            self.shape = SHAPES["2x2"]  # Default 2x2 container
        if self.rotation is None and Rotation:
            self.rotation = Rotation.NONE

    def get_occupied_squares(self) -> List[Tuple[int, int]]:
        """Get all main grid squares this container occupies"""
        if self.shape and self.rotation is not None:
            rotated_shape = self.shape.rotate(self.rotation)
            return [
                (self.position[0] + dx, self.position[1] + dy)
                for dx, dy in rotated_shape.squares
            ]
        else:
            # Default to single square if grid system not available
            return [self.position]

    def get_internal_squares(self) -> Set[Tuple[int, int]]:
        """Get all internal grid squares this container provides (in global coordinates)"""
        # The container occupies certain squares in the main grid
        # Those same squares become available for items to be placed on
        # So we return the squares the container occupies
        return set(self.get_occupied_squares())


def create_server_containers():
    """Create different types of server containers with their item specs"""

    if not ItemSpec:
        return {}

    # Mini Server Rack - 2x2 external, provides 3x4 internal
    mini_rack_spec = ItemSpec(
        id="mini_rack",
        name="Mini Server Rack",
        category="infrastructure",
        shape=SHAPES["2x2"] if SHAPES else None,
        triggers=[
            PassiveTrigger(
                effects=[
                    StatModEffect(stat_name="max_cpu", value=3),
                    BuffEffect(
                        buff_name="rack_cooling",
                        value=0.05,  # Items inside are 5% faster
                        target_type="contained",
                    ),
                ]
            )
        ]
        if PassiveTrigger
        else [],
        rarity="common",
    )

    # Standard Server Rack - 2x3 external, provides 4x5 internal
    standard_rack_spec = ItemSpec(
        id="standard_rack",
        name="Standard Server Rack",
        category="infrastructure",
        shape=SHAPES["2x3"] if SHAPES else None,
        triggers=[
            PassiveTrigger(
                effects=[
                    StatModEffect(stat_name="max_cpu", value=5),
                    StatModEffect(stat_name="cpu_regen", value=1),
                    BuffEffect(
                        buff_name="rack_efficiency",
                        value=0.1,  # Items inside are 10% faster
                        target_type="contained",
                    ),
                ]
            )
        ]
        if PassiveTrigger
        else [],
        rarity="uncommon",
    )

    # Enterprise Server Rack - 3x3 external, provides 5x6 internal
    enterprise_rack_spec = ItemSpec(
        id="enterprise_rack",
        name="Enterprise Server Rack",
        category="infrastructure",
        shape=ItemShape(
            [(0, 0), (1, 0), (2, 0), (0, 1), (1, 1), (2, 1), (0, 2), (1, 2), (2, 2)],
            "3x3",
        )
        if ItemShape
        else None,
        triggers=[
            PassiveTrigger(
                effects=[
                    StatModEffect(stat_name="max_cpu", value=8),
                    StatModEffect(stat_name="cpu_regen", value=2),
                    BuffEffect(
                        buff_name="enterprise_power",
                        value=0.15,  # Items inside are 15% faster
                        target_type="contained",
                    ),
                    BuffEffect(
                        buff_name="enterprise_accuracy",
                        value=0.1,  # Items inside have +10% accuracy
                        target_type="contained",
                    ),
                ]
            )
        ]
        if PassiveTrigger
        else [],
        rarity="rare",
    )

    # Blade Server Chassis - 1x4 external, provides 3x4 internal (vertical orientation)
    blade_chassis_spec = ItemSpec(
        id="blade_chassis",
        name="Blade Server Chassis",
        category="infrastructure",
        shape=ItemShape([(0, 0), (0, 1), (0, 2), (0, 3)], "1x4") if ItemShape else None,
        triggers=[
            PassiveTrigger(
                effects=[
                    StatModEffect(stat_name="max_cpu", value=6),
                    BuffEffect(
                        buff_name="blade_density",
                        value=0.2,  # Items inside attack 20% faster
                        target_type="contained",
                    ),
                ]
            )
        ]
        if PassiveTrigger
        else [],
        rarity="uncommon",
    )

    # Quantum Server - 2x2 external, provides 6x6 internal (space-bending technology!)
    quantum_server_spec = ItemSpec(
        id="quantum_server",
        name="Quantum Server",
        category="infrastructure",
        shape=SHAPES["2x2"] if SHAPES else None,
        triggers=[
            PassiveTrigger(
                effects=[
                    StatModEffect(stat_name="max_cpu", value=15),
                    StatModEffect(stat_name="cpu_regen", value=3),
                    BuffEffect(
                        buff_name="quantum_entanglement",
                        value=0.25,  # Items inside are 25% faster
                        target_type="contained",
                    ),
                    BuffEffect(
                        buff_name="quantum_superposition",
                        value=0.15,  # Items have 15% chance to activate twice
                        target_type="contained",
                    ),
                ]
            )
        ]
        if PassiveTrigger
        else [],
        rarity="legendary",
    )

    return {
        "mini_rack": {
            "spec": mini_rack_spec,
            "internal_size": (3, 4),
            "external_shape": SHAPES["2x2"] if SHAPES else None,
        },
        "standard_rack": {
            "spec": standard_rack_spec,
            "internal_size": (4, 5),
            "external_shape": SHAPES["2x3"] if SHAPES else None,
        },
        "enterprise_rack": {
            "spec": enterprise_rack_spec,
            "internal_size": (5, 6),
            "external_shape": ItemShape(
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
            )
            if ItemShape
            else None,
        },
        "blade_chassis": {
            "spec": blade_chassis_spec,
            "internal_size": (3, 4),
            "external_shape": ItemShape([(0, 0), (0, 1), (0, 2), (0, 3)], "1x4")
            if ItemShape
            else None,
        },
        "quantum_server": {
            "spec": quantum_server_spec,
            "internal_size": (6, 6),
            "external_shape": SHAPES["2x2"] if SHAPES else None,
        },
    }


class PlacementValidator:
    """Validates item placement considering containers"""

    def __init__(self, main_grid_size: Tuple[int, int] = (7, 9)):
        self.main_grid_size = main_grid_size
        self.containers: List[ServerContainer] = []
        self.available_squares: Set[Tuple[int, int]] = set()
        self.occupied_squares: Set[Tuple[int, int]] = set()

    def add_container(self, container: ServerContainer) -> bool:
        """Add a container and update available squares"""
        # Check if container can be placed in main grid
        container_squares = set(container.get_occupied_squares())

        # Verify all squares are in bounds and not occupied
        for x, y in container_squares:
            if x < 0 or x >= self.main_grid_size[0]:
                return False
            if y < 0 or y >= self.main_grid_size[1]:
                return False
            if (x, y) in self.occupied_squares:
                return False  # Already occupied by another container

        # Place container
        self.containers.append(container)
        self.occupied_squares.update(container_squares)

        # Add internal squares as available
        internal_squares = container.get_internal_squares()
        self.available_squares.update(internal_squares)

        return True

    def validate_item_placement(
        self, item_position: Tuple[int, int], item_shape: Any, item_rotation: Any = None
    ) -> bool:
        """Check if an item can be placed at the given position"""
        # Get squares the item would occupy
        if item_shape and item_rotation is not None:
            rotated_shape = item_shape.rotate(item_rotation)
            item_squares = [
                (item_position[0] + dx, item_position[1] + dy)
                for dx, dy in rotated_shape.squares
            ]
        else:
            item_squares = [item_position]

        # Check each square
        for x, y in item_squares:
            # Must be in an available square (provided by a container)
            if (x, y) not in self.available_squares:
                return False
            # Must not be already occupied by another item
            if (x, y) in self.occupied_squares:
                return False

        return True

    def place_item(
        self, item_position: Tuple[int, int], item_shape: Any, item_rotation: Any = None
    ) -> bool:
        """Place an item if valid"""
        if not self.validate_item_placement(item_position, item_shape, item_rotation):
            return False

        # Mark squares as occupied
        if item_shape and item_rotation is not None:
            rotated_shape = item_shape.rotate(item_rotation)
            item_squares = [
                (item_position[0] + dx, item_position[1] + dy)
                for dx, dy in rotated_shape.squares
            ]
        else:
            item_squares = [item_position]

        self.occupied_squares.update(item_squares)
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
        self, item_position: Tuple[int, int], item_shape: Any, item_rotation: Any = None
    ) -> List[ServerContainer]:
        """Get all containers that an item overlaps with"""
        # Get squares the item occupies
        if item_shape and item_rotation is not None:
            rotated_shape = item_shape.rotate(item_rotation)
            item_squares = [
                (item_position[0] + dx, item_position[1] + dy)
                for dx, dy in rotated_shape.squares
            ]
        else:
            item_squares = [item_position]

        # Find all containers that provide any of these squares
        containers = set()
        for x, y in item_squares:
            container = self.get_container_at_position((x, y))
            if container:
                containers.add(container)

        return list(containers)


if __name__ == "__main__":
    # Demo the container system
    print("Server Container System Demo\n")

    # Create containers
    containers = create_server_containers()

    # Create a validator
    validator = PlacementValidator()

    # Add a mini rack at position (1, 1)
    mini_rack = ServerContainer(
        spec=containers["mini_rack"]["spec"],
        position=(1, 1),
        uid="rack1",
        internal_grid_size=containers["mini_rack"]["internal_size"],
        shape=containers["mini_rack"]["external_shape"],
    )

    if validator.add_container(mini_rack):
        print(f"Added mini rack at {mini_rack.position}")
        print(f"  Occupies main grid squares: {mini_rack.get_occupied_squares()}")
        print(f"  Provides internal squares: {mini_rack.get_internal_squares()}")

    # Try to place an item
    if validator.validate_item_placement((1, 1), SHAPES["1x1"] if SHAPES else None):
        print("\nCan place 1x1 item at (1, 1) - inside the rack!")

    if not validator.validate_item_placement((0, 0), SHAPES["1x1"] if SHAPES else None):
        print("Cannot place 1x1 item at (0, 0) - no container there!")

    # Add a standard rack
    standard_rack = ServerContainer(
        spec=containers["standard_rack"]["spec"],
        position=(4, 2),
        uid="rack2",
        internal_grid_size=containers["standard_rack"]["internal_size"],
        shape=containers["standard_rack"]["external_shape"],
    )

    if validator.add_container(standard_rack):
        print(f"\nAdded standard rack at {standard_rack.position}")
        print(
            f"  Provides {len(standard_rack.get_internal_squares())} internal squares"
        )
