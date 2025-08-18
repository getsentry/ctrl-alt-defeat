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
    """Create server containers from JSON configuration"""
    try:
        from config_loader import create_server_containers_from_config

        containers = create_server_containers_from_config()
        if containers:
            return containers
    except (ImportError, FileNotFoundError):
        pass

    # Fallback to hardcoded version
    return create_server_containers_hardcoded()


def create_server_containers_hardcoded():
    """Create different types of server containers with their item specs (hardcoded fallback)"""

    if not ItemSpec:
        return {}

    # Standard VM - 2x2 (4 slots)
    standard_vm_spec = ItemSpec(
        id="standard_vm",
        name="Standard VM",
        category="infrastructure",
        shape=SHAPES["2x2"] if SHAPES else None,
        triggers=[],  # No special effects
        rarity="common",
    )

    # Edge Node - 2x1 (2 slots horizontal)
    edge_node_spec = ItemSpec(
        id="edge_node",
        name="Edge Node",
        category="infrastructure",
        shape=ItemShape([(0, 0), (1, 0)], "2x1") if ItemShape else None,
        triggers=[
            PassiveTrigger(
                effects=[
                    BuffEffect(
                        buff_name="edge_speed",
                        value=0.1,  # Modules inside execute 10% faster
                        target_type="contained",
                    ),
                ]
            )
        ]
        if PassiveTrigger
        else [],
        rarity="rare",
    )

    # Memory Cache - 3x1 (3 slots horizontal)
    memory_cache_spec = ItemSpec(
        id="memory_cache",
        name="Memory Cache",
        category="infrastructure",
        shape=ItemShape([(0, 0), (1, 0), (2, 0)], "3x1") if ItemShape else None,
        triggers=[
            PassiveTrigger(
                effects=[
                    StatModEffect(stat_name="max_cpu", value=1),  # Gain 1 maximum CPU
                ]
            )
        ]
        if PassiveTrigger
        else [],
        rarity="epic",
    )

    # Load Balancer - 1x1 (1 slot)
    load_balancer_spec = ItemSpec(
        id="load_balancer",
        name="Load Balancer",
        category="infrastructure",
        shape=ItemShape([(0, 0)], "1x1") if ItemShape else None,
        triggers=[
            # BattleStartTrigger would be needed for "Start of battle: Gain 15 Block"
            # For now using PassiveTrigger as placeholder
            PassiveTrigger(
                effects=[
                    StatModEffect(stat_name="block", value=15),  # Start with 15 Block
                ]
            )
        ]
        if PassiveTrigger
        else [],
        rarity="godly",
    )

    # Patch Registry - 2x2 (4 slots)
    patch_registry_spec = ItemSpec(
        id="patch_registry",
        name="Patch Registry",
        category="infrastructure",
        shape=SHAPES["2x2"] if SHAPES else None,
        triggers=[
            # Complex trigger for "First Patch deployed: Random buff / 4 Patches deployed: Clear 8 errors"
            # Placeholder for now
            PassiveTrigger(
                effects=[
                    BuffEffect(
                        buff_name="patch_efficiency",
                        value=0.1,  # Placeholder effect
                        target_type="contained",
                    ),
                ]
            )
        ]
        if PassiveTrigger
        else [],
        rarity="legendary",
    )

    # Container Orchestrator - 3x2 (6 slots)
    container_orchestrator_spec = ItemSpec(
        id="container_orchestrator",
        name="Container Orchestrator",
        category="infrastructure",
        shape=ItemShape(
            [(0, 0), (1, 0), (2, 0), (0, 1), (1, 1), (2, 1)],
            "3x2",
        )
        if ItemShape
        else None,
        triggers=[
            # "Start of battle: gain 7 Block for each Basic module inside"
            # Placeholder for now
            PassiveTrigger(
                effects=[
                    StatModEffect(stat_name="block", value=7),  # Placeholder
                ]
            )
        ]
        if PassiveTrigger
        else [],
        rarity="epic",
    )

    # Serverless Function - 2x2 (4 slots)
    serverless_function_spec = ItemSpec(
        id="serverless_function",
        name="Serverless Function",
        category="infrastructure",
        shape=SHAPES["2x2"] if SHAPES else None,
        triggers=[
            # "Deploy phase: If has 2+ Legendary modules, generate free API credits"
            # Placeholder for now
            PassiveTrigger(
                effects=[
                    BuffEffect(
                        buff_name="api_efficiency",
                        value=0.15,  # Placeholder
                        target_type="contained",
                    ),
                ]
            )
        ]
        if PassiveTrigger
        else [],
        rarity="epic",
    )

    # Chaos Experiment - Variable shape (for now using 2x2)
    chaos_experiment_spec = ItemSpec(
        id="chaos_experiment",
        name="Chaos Experiment",
        category="infrastructure",
        shape=SHAPES["2x2"]
        if SHAPES
        else None,  # Variable shape - using 2x2 as placeholder
        triggers=[
            # "Game started: Replace with random infrastructure and modules"
            # This would require special handling
            PassiveTrigger(
                effects=[
                    BuffEffect(
                        buff_name="chaos",
                        value=0.2,  # Placeholder
                        target_type="contained",
                    ),
                ]
            )
        ]
        if PassiveTrigger
        else [],
        rarity="unique",
    )

    return {
        "standard_vm": {
            "spec": standard_vm_spec,
            "internal_size": (2, 2),  # Same as external
            "external_shape": SHAPES["2x2"] if SHAPES else None,
        },
        "edge_node": {
            "spec": edge_node_spec,
            "internal_size": (2, 1),  # Same as external
            "external_shape": ItemShape([(0, 0), (1, 0)], "2x1") if ItemShape else None,
        },
        "memory_cache": {
            "spec": memory_cache_spec,
            "internal_size": (3, 1),  # Same as external
            "external_shape": ItemShape([(0, 0), (1, 0), (2, 0)], "3x1")
            if ItemShape
            else None,
        },
        "load_balancer": {
            "spec": load_balancer_spec,
            "internal_size": (1, 1),  # Same as external
            "external_shape": ItemShape([(0, 0)], "1x1") if ItemShape else None,
        },
        "patch_registry": {
            "spec": patch_registry_spec,
            "internal_size": (2, 2),  # Same as external
            "external_shape": SHAPES["2x2"] if SHAPES else None,
        },
        "container_orchestrator": {
            "spec": container_orchestrator_spec,
            "internal_size": (3, 2),  # Same as external
            "external_shape": ItemShape(
                [(0, 0), (1, 0), (2, 0), (0, 1), (1, 1), (2, 1)],
                "3x2",
            )
            if ItemShape
            else None,
        },
        "serverless_function": {
            "spec": serverless_function_spec,
            "internal_size": (2, 2),  # Same as external
            "external_shape": SHAPES["2x2"] if SHAPES else None,
        },
        "chaos_experiment": {
            "spec": chaos_experiment_spec,
            "internal_size": (2, 2),  # Variable - using 2x2 as placeholder
            "external_shape": SHAPES["2x2"] if SHAPES else None,
        },
    }


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
        self, item_position: Tuple[int, int], item_shape: Any, item_rotation: Any = None
    ) -> bool:
        """Check if an item can be placed at the given position"""
        # Get squares the item would occupy
        if item_shape:
            if item_rotation is None and Rotation:
                item_rotation = Rotation.NONE
            if item_rotation is not None:
                rotated_shape = item_shape.rotate(item_rotation)
                item_squares = [
                    (item_position[0] + dx, item_position[1] + dy)
                    for dx, dy in rotated_shape.squares
                ]
            else:
                # Fallback if rotation not available
                item_squares = [
                    (item_position[0] + dx, item_position[1] + dy)
                    for dx, dy in item_shape.squares
                ]
        else:
            item_squares = [item_position]

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
        self, item_position: Tuple[int, int], item_shape: Any, item_rotation: Any = None
    ) -> bool:
        """Place an item if valid"""
        if not self.validate_item_placement(item_position, item_shape, item_rotation):
            return False

        # Mark squares as occupied
        if item_shape:
            if item_rotation is None and Rotation:
                item_rotation = Rotation.NONE
            if item_rotation is not None:
                rotated_shape = item_shape.rotate(item_rotation)
                item_squares = [
                    (item_position[0] + dx, item_position[1] + dy)
                    for dx, dy in rotated_shape.squares
                ]
            else:
                # Fallback if rotation not available
                item_squares = [
                    (item_position[0] + dx, item_position[1] + dy)
                    for dx, dy in item_shape.squares
                ]
        else:
            item_squares = [item_position]

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
        self, item_position: Tuple[int, int], item_shape: Any, item_rotation: Any = None
    ) -> List[ServerContainer]:
        """Get all containers that an item overlaps with"""
        # Get squares the item occupies
        if item_shape:
            if item_rotation is None and Rotation:
                item_rotation = Rotation.NONE
            if item_rotation is not None:
                rotated_shape = item_shape.rotate(item_rotation)
                item_squares = [
                    (item_position[0] + dx, item_position[1] + dy)
                    for dx, dy in rotated_shape.squares
                ]
            else:
                # Fallback if rotation not available
                item_squares = [
                    (item_position[0] + dx, item_position[1] + dy)
                    for dx, dy in item_shape.squares
                ]
        else:
            item_squares = [item_position]

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
        internal_grid_size=containers["standard_vm"]["internal_size"],
        shape=containers["standard_vm"]["external_shape"],
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
        internal_grid_size=containers["edge_node"]["internal_size"],
        shape=containers["edge_node"]["external_shape"],
    )

    if validator.add_container(edge_node):
        print(f"\nAdded edge node at {edge_node.position}")
        print(
            f"  Provides {len(edge_node.get_internal_squares())} internal squares (horizontal 2x1)"
        )
