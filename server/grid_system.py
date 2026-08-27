from dataclasses import dataclass
from enum import Enum
from typing import Dict, Iterable, List, Sequence, Set, Tuple

Position = Tuple[int, int]


class Rotation(Enum):
    """Rotation states for items"""

    NONE = 0
    CLOCKWISE_90 = 90
    CLOCKWISE_180 = 180
    CLOCKWISE_270 = 270


def _clear_of(covered: Set[Position], square: Position) -> Position:
    """Straight up from this square to the first one the item does not cover.

    An anchor's aura is above the ITEM, not above the anchor. Turned half
    round, a potion's anchor is the lower of its two cells, and an aura that
    stopped at the cell above it would stop inside the potion -- leaving it
    with no star at all, where the game gives it one directly above. See
    docs/item_grid_model.md section 5.

    Two anchors that clear the item into the same square make one aura, which
    is what keeps Bag of Stones at one star on end and two laid flat.
    """
    x, y = square
    while (x, y) in covered:
        y -= 1
    return (x, y)


def _turn(square: Position, rotation: Rotation) -> Position:
    """One square, a quarter turn clockwise at a time.

    Rows count downwards, so y points down and clockwise sends (x, y) to
    (-y, x): the square to the right of an item ends up below it. The other
    formula, (y, -x), is the one for a graph with y pointing up, and on a grid
    it turns the squares anticlockwise -- which is how a spear came to be drawn
    pointing one way with its aura reaching the other. The client turns shapes
    in APITypes._spin() and the two have to agree.
    """
    x, y = square
    if rotation == Rotation.CLOCKWISE_90:
        return (-y, x)
    if rotation == Rotation.CLOCKWISE_180:
        return (-x, -y)
    if rotation == Rotation.CLOCKWISE_270:
        return (y, -x)
    return (x, y)


@dataclass
class ItemShape:
    """The squares an item covers, and the squares it reaches into.

    Every list is offset from the item's own top left corner, so a square the
    item reaches above or to the left of itself is negative. They have to share
    one origin: an aura is only meaningful next to the footprint it belongs to.
    """

    # Offsets from the item's own corner. A 2x2 is [(0,0), (1,0), (0,1), (1,1)].
    squares: List[Position]
    name: str = ""

    # The two aura zones, drawn on the map as * and +. Separate zones: an item
    # may project either, both or neither, and an effect names which it means.
    star: Tuple[Position, ...] = ()
    diamond: Tuple[Position, ...] = ()

    # Covered squares whose zone points straight up in world space however the
    # item is turned. Always a subset of `squares`, because `parse_map` reads a
    # `^` as covered, and every shape comes from there.
    anchors: Tuple[Position, ...] = ()

    def where(self, square: Position, rotation: Rotation) -> Position:
        """Where one square of this shape ends up when the whole shape turns.

        The client has the same thing in APITypes.Turned.where(), and the two
        have to agree: it is what carries an item round when the rack under it
        turns, on both sides.
        """
        if rotation == Rotation.NONE or not self.squares:
            return square
        spun = [_turn(covered, rotation) for covered in self.squares]
        min_x = min(x for x, _ in spun)
        min_y = min(y for _, y in spun)
        x, y = _turn(square, rotation)
        return (x - min_x, y - min_y)

    def corner_of(
        self, squares_on_it: Iterable[Position], rotation: Rotation
    ) -> Position:
        """Where a thing sitting on this shape ends up: the corner of the
        squares it lands on.

        The client has the same thing in APITypes.Turned.corner_of(), and
        `server/tests/fixtures/carried_round.json` holds both to the same
        answers.
        """
        landed = [self.where(square, rotation) for square in squares_on_it]
        return (min(x for x, _ in landed), min(y for _, y in landed))

    def rotate(self, rotation: Rotation) -> "ItemShape":
        """Return a rotated version of the shape"""
        if rotation == Rotation.NONE:
            return self

        # An anchor's square is already in `star` for the way the item faces
        # now. Take it out before turning, or it turns with the item and the
        # anchor projects a second one, leaving the item with two.
        #
        # By the same rule that put it there: the aura clears the item, so the
        # square to take out is the one it cleared to, not the one above the
        # anchor. Those are the same square only while the anchor is on top.
        mine = set(self.squares)
        was_projected = {_clear_of(mine, square) for square in self.anchors}

        squares = [_turn(square, rotation) for square in self.squares]
        star = [_turn(square, rotation) for square in set(self.star) - was_projected]
        diamond = [_turn(square, rotation) for square in self.diamond]
        anchors = [_turn(square, rotation) for square in self.anchors]

        # Settle everything against the FOOTPRINT's corner, not its own. Each
        # list is a position relative to the item, so they have to move together
        # -- an aura settled against its own corner lands on top of the item.
        if squares:
            min_x = min(x for x, _ in squares)
            min_y = min(y for _, y in squares)

            def shift(cells: Iterable[Position]) -> List[Position]:
                return [(x - min_x, y - min_y) for x, y in cells]

            squares = shift(squares)
            star = shift(star)
            diamond = shift(diamond)
            anchors = shift(anchors)

        # An anchor points up in world space, so its square is worked out after
        # the turn rather than turned with the rest. It goes past the item's
        # own cells to the first square clear of them; another item in the way
        # does not stop it.
        covered = set(squares)
        projected = {_clear_of(covered, square) for square in anchors}
        star = sorted(set(star) - covered | projected)

        return ItemShape(
            squares,
            self.name,
            tuple(star),
            tuple(sorted(set(diamond) - covered)),
            tuple(anchors),
        )


# What each character in an item's map means. See docs/item_grid_model.md.
FOOTPRINT = "#"  # a square the item covers
ANCHOR = "^"  # covered, and projects its aura straight up in world
# space however the item is turned, past the item's own
# squares to the first one clear of them; another item
# in the way does not stop it.
STAR = "*"  # the star aura the item reaches into
DIAMOND = "+"  # the diamond aura, a second and separate zone
EMPTY = "."

# What each aura character is called, for when something reads them. Nothing
# does yet: parse_map returns the covered squares only.
AURA = {STAR: "star", DIAMOND: "diamond"}

COVERED = FOOTPRINT + ANCHOR
# Squares an item reaches without covering. Held apart from COVERED because the
# blank-edge check counts them and the footprint does not.
REACHED = STAR + DIAMOND
LEGAL = COVERED + REACHED + EMPTY


class BadMap(ValueError):
    """A map that does not describe an item. Raised rather than guessed at:
    a map is easy to mistype and a wrong shape is hard to notice in play."""


def _cells(rows: Sequence[str], wanted: str) -> List[Position]:
    return [
        (x, y) for y, row in enumerate(rows) for x, c in enumerate(row) if c in wanted
    ]


def _is_connected(cells: Iterable[Position]) -> bool:
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

    The aura zones come back too, in the same frame as the covered squares, so
    a zone above or left of the item is negative.
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
    used = set(_cells(rows, COVERED + REACHED))
    if not used:
        raise BadMap(f"{name}: nothing drawn")
    if not any(y == 0 for _, y in used) or not any(y == len(rows) - 1 for _, y in used):
        raise BadMap(f"{name}: blank row at the top or bottom. Trim it.")
    if not any(x == 0 for x, _ in used) or not any(
        x == len(rows[0]) - 1 for x, _ in used
    ):
        raise BadMap(f"{name}: blank column at the left or right. Trim it.")

    # Offsets from the item's own top left, not the map's. The map is bigger
    # than the item whenever the item reaches into squares it does not cover,
    # and every list below is measured from the same corner.
    x0 = min(x for x, _ in covered)
    y0 = min(y for _, y in covered)

    def relative(cells: Iterable[Position]) -> Tuple[Position, ...]:
        return tuple(sorted((x - x0, y - y0) for x, y in cells))

    return ItemShape(
        [(x - x0, y - y0) for x, y in covered],
        name,
        relative(_cells(rows, STAR)),
        relative(_cells(rows, DIAMOND)),
        relative(_cells(rows, ANCHOR)),
    )


def zones_of(
    shape: ItemShape, position: Position, rotation: Rotation = Rotation.NONE
) -> Dict[str, Set[Position]]:
    """The grid squares an item's zones cover, once turned and put down."""
    turned = shape.rotate(rotation)
    x, y = position
    return {
        "star": {(x + dx, y + dy) for dx, dy in turned.star},
        "diamond": {(x + dx, y + dy) for dx, dy in turned.diamond},
    }


def covered_by(
    shape: ItemShape, position: Position, rotation: Rotation = Rotation.NONE
) -> Set[Position]:
    """The grid squares an item stands on, once turned and put down."""
    x, y = position
    return {(x + dx, y + dy) for dx, dy in shape.rotate(rotation).squares}


def reach(
    placements: Sequence[Tuple[str, ItemShape, Position, Rotation]],
) -> Dict[str, Dict[str, List[str]]]:
    """Which items each item's zones reach, as {uid: {zone: [uid, ...]}}.

    A zone reaches an item when any square of the zone lands on any square that
    item stands on. Touching is not required and distance is not a rule: the map
    said which squares, and this only asks who is standing on them.

    Every item gets an entry, so a caller never has to guess whether a missing
    key means no reach or an item it forgot about.
    """
    standing = {
        uid: covered_by(shape, at, facing) for uid, shape, at, facing in placements
    }

    reached: Dict[str, Dict[str, List[str]]] = {}
    for uid, shape, at, facing in placements:
        zones = zones_of(shape, at, facing)
        reached[uid] = {
            zone: sorted(
                other
                for other, squares in standing.items()
                # An item is never in its own reach. The zone already excludes
                # the squares it stands on, but a zone reaching around a hole in
                # another item could otherwise come back to it.
                if other != uid and squares & cells
            )
            for zone, cells in zones.items()
        }
    return reached
