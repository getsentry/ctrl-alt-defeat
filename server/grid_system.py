from dataclasses import dataclass
from enum import Enum
from typing import List, Tuple


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
