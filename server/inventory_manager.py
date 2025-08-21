"""
Inventory management system for the autobattler game
Manages both the 9x7 grid with server containers and unlimited storage
"""

from typing import Dict, List, Optional, Tuple, Union


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
        """Initialize the grid with 3 adjacent 2x2 server containers"""
        self.width = 9
        self.height = 7
        self.items = []  # List of placed items

        # Initialize with 3 server containers centered horizontally
        self.containers = [
            {
                "id": "container_a",
                "position": (2, 3),
                "width": 2,
                "height": 2,
                "type": "standard_vm",
            },
            {
                "id": "container_b",
                "position": (4, 3),
                "width": 2,
                "height": 2,
                "type": "standard_vm",
            },
            {
                "id": "container_c",
                "position": (6, 3),
                "width": 2,
                "height": 2,
                "type": "standard_vm",
            },
        ]

    def is_valid_placement(
        self, position: Tuple[int, int], shape: List[Tuple[int, int]] = None
    ) -> bool:
        """Check if a position is valid for item placement, considering its shape"""
        # If no shape provided, assume single square
        if shape is None:
            shape = [(0, 0)]

        # Check all squares the item would occupy
        base_x, base_y = position
        for dx, dy in shape:
            x = base_x + dx
            y = base_y + dy

            # Check bounds
            if x < 0 or x >= self.width or y < 0 or y >= self.height:
                return False

            # Check if position is on a server container
            on_container = False
            for container in self.containers:
                cx, cy = container["position"]
                cw, ch = container["width"], container["height"]

                if cx <= x < cx + cw and cy <= y < cy + ch:
                    on_container = True
                    break

            if not on_container:
                return False

        return True

    def get_item_at(self, position: Tuple[int, int]) -> Optional[Dict]:
        """Get the item at a specific position"""
        for item in self.items:
            # Convert position to tuple if it's a list (from database)
            item_pos = item.get("position")
            if item_pos is None:
                continue
            if isinstance(item_pos, list):
                item_pos = tuple(item_pos)

            # Check if this is a multi-square item
            if "shape" in item:
                # Multi-square item
                base_x, base_y = item_pos
                for dx, dy in item["shape"]:
                    if (base_x + dx, base_y + dy) == position:
                        return item
            else:
                # Single square item
                if item_pos == position:
                    return item
        return None

    def _get_occupied_squares(
        self, item: Dict, position: Tuple[int, int]
    ) -> List[Tuple[int, int]]:
        """Get all squares that would be occupied by an item at a position"""
        if "shape" in item:
            # Multi-square item
            base_x, base_y = position
            return [(base_x + dx, base_y + dy) for dx, dy in item["shape"]]
        else:
            # Single square item
            return [position]

    def place_item(self, item: Dict, position: Tuple[int, int]) -> None:
        """Place an item on the grid"""
        # Check all squares the item would occupy
        occupied_squares = self._get_occupied_squares(item, position)

        # First check if the entire shape fits on containers
        shape = item.get("shape", [(0, 0)])  # Default to single square
        if not self.is_valid_placement(position, shape):
            raise InvalidPlacementError(
                f"Item at position {position} does not fit entirely on server containers"
            )

        # Then check for overlaps with existing items
        for square in occupied_squares:
            existing_item = self.get_item_at(square)
            if existing_item is not None:
                item_id = existing_item.get("id", "unknown")
                raise InvalidPlacementError(
                    f"Position {square} is already occupied by item {item_id}"
                )

        # Place the item
        item["position"] = position
        self.items.append(item)

    def remove_item_at(self, position: Tuple[int, int]) -> Dict:
        """Remove and return the item at a position"""
        item = self.get_item_at(position)
        if item is None:
            raise ItemNotFoundError(f"No item at position {position}")

        self.items.remove(item)
        return item

    def get_battle_items(self) -> List[Dict]:
        """Get all items formatted for battle"""
        return self.items.copy()


class InventoryStorage:
    """
    Manages the unlimited storage area for unused items
    """

    def __init__(self):
        """Initialize empty storage"""
        self.items = []

    def add_item(self, item: Dict) -> None:
        """Add an item to storage"""
        self.items.append(item)

    def remove_item(self, item_id: str) -> Dict:
        """Remove and return an item by ID"""
        for item in self.items:
            if item["id"] == item_id:
                self.items.remove(item)
                return item
        raise ItemNotFoundError(f"Item with ID {item_id} not found in storage")

    def find_item(self, item_id: str) -> Optional[Dict]:
        """Find an item by ID"""
        for item in self.items:
            if item["id"] == item_id:
                return item
        return None

    def get_all(self) -> List[Dict]:
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

    def place_item(self, item: Dict, placement: Union[str, Tuple[int, int]]) -> bool:
        """
        Place an item either in storage or on the grid

        Args:
            item: The item to place
            placement: Either "storage" or (x, y) coordinates

        Returns:
            True if successful
        """
        try:
            if placement == "storage":
                self.storage.add_item(item)
            else:
                # Placement is grid coordinates
                self.grid.place_item(item, placement)
            return True
        except (InvalidPlacementError, Exception):
            return False

    def move_item(
        self,
        item_id: str,
        from_location: Union[str, Tuple[int, int]],
        to_location: Union[str, Tuple[int, int]],
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
            if item["id"] != item_id:
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
                self.grid.place_item(item, to_location)
        except (InvalidPlacementError, Exception):
            # Restore item to original location on failure
            if from_location == "storage":
                self.storage.add_item(item)
            else:
                self.grid.place_item(item, from_location)
            raise

    def get_battle_inventory(self) -> List[Dict]:
        """Get only grid items for battle (storage items not used)"""
        return self.grid.get_battle_items()

    def remove_item(
        self, location: Optional[Tuple[int, int]] = None, item_id: Optional[str] = None
    ) -> Optional[Dict]:
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
                    if grid_item["id"] == item_id:
                        return self.grid.remove_item_at(grid_item["position"])

            return None
        except (ItemNotFoundError, Exception):
            return None

    def get_state(self) -> Dict:
        """Get the full inventory state for persistence"""
        return {
            "grid": self.grid.items.copy(),
            "storage": self.storage.items.copy(),
            "containers": self.grid.containers.copy(),
        }

    def restore_state(self, state: Dict) -> None:
        """Restore inventory from saved state"""
        # Clear current state
        self.grid.items = []
        self.storage.items = []

        # Restore grid items
        if "grid" in state:
            self.grid.items = state["grid"].copy()

        # Restore storage items
        if "storage" in state:
            self.storage.items = state["storage"].copy()

        # Restore containers if provided
        if "containers" in state:
            self.grid.containers = state["containers"].copy()
