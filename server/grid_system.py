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


# What each character in an item's map means. See docs/item_grid_model.md.
FOOTPRINT = "#"          # a square the item covers
ANCHOR = "^"             # covered, and projects its aura straight up in world
                         # space however the item is turned. The projection is
                         # dropped only where it lands on this item's own
                         # squares; another item in the way does not stop it.
STAR = "*"               # the star aura the item reaches into
DIAMOND = "+"            # the diamond aura, a second and separate zone
EMPTY = "."

# What each aura character is called, for when something reads them. Nothing
# does yet: parse_map returns the covered squares only.
AURA = {STAR: "star", DIAMOND: "diamond"}

COVERED = FOOTPRINT + ANCHOR
LEGAL = COVERED + STAR + DIAMOND + EMPTY


class BadMap(ValueError):
    """A map that does not describe an item. Raised rather than guessed at:
    a map is easy to mistype and a wrong shape is hard to notice in play."""


def _cells(rows, wanted):
    return [(x, y) for y, row in enumerate(rows) for x, c in enumerate(row) if c in wanted]


def _is_connected(cells) -> bool:
    """Every covered square reachable from every other, edge to edge."""
    remaining = set(cells)
    stack = [next(iter(remaining))]
    while stack:
        x, y = stack.pop()
        if (x, y) not in remaining:
            continue
        remaining.discard((x, y))
        stack += [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
    return not remaining


def parse_map(rows: List[str], name: str) -> "ItemShape":
    """The squares an item covers, read from its text map.

    The name is what a refusal is reported against, so it is required: a map
    is easy to mistype and "which one" is the first thing you want to know.

    Aura is not returned yet. Nothing reads it, and returning it would mean
    deciding a shape for it before anything needs one.
    """
    if not rows:
        raise BadMap(f"{name}: a map with no rows describes nothing")

    widths = {len(r) for r in rows}
    if len(widths) != 1:
        raise BadMap(f"{name}: rows are {sorted(widths)} wide, they must match")

    illegal = sorted({c for r in rows for c in r} - set(LEGAL))
    if illegal:
        raise BadMap(f"{name}: {illegal} is not a character a map can hold")

    covered = _cells(rows, COVERED)
    if not covered:
        raise BadMap(f"{name}: no covered squares, so there is no item")

    if not _is_connected(covered):
        raise BadMap(f"{name}: the covered squares are in more than one piece")

    # No blank edge, counting aura as drawn. Two maps of the same item should
    # be the same text, and a stray blank row would make them differ.
    used = set(_cells(rows, COVERED + STAR + DIAMOND))
    if not used:
        raise BadMap(f"{name}: nothing drawn")
    if not any(y == 0 for _, y in used) or not any(y == len(rows) - 1 for _, y in used):
        raise BadMap(f"{name}: blank row at the top or bottom. Trim it.")
    if not any(x == 0 for x, _ in used) or not any(x == len(rows[0]) - 1 for x, _ in used):
        raise BadMap(f"{name}: blank column at the left or right. Trim it.")

    # Offsets from the item's own top left, not the map's. The map is bigger
    # than the item whenever the item reaches into squares it does not cover.
    x0 = min(x for x, _ in covered)
    y0 = min(y for _, y in covered)
    return ItemShape([(x - x0, y - y0) for x, y in covered], name)


