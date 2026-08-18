"""
Where an item can go, and which arrangement is best.

Every square this module computes comes from the SERVER's own geometry:
`PlacedItem.covered_squares()` and `Container.covered_squares()` (items.py:179,
containers.py:53). Nothing here re-derives a shape.

That matters because the old version did re-derive it, from a width/height
bounding box, and was accidentally right only because every container happened
to be rectangular. The real method already handles rotation and irregular
shapes, so building on it means the first L-shaped container to land works
without a change here.

WHAT PLACEMENT IS WORTH TODAY: not much, and it is worth knowing why. An
arrangement only matters if moving an item changes the outcome, and that needs
either adjacency synergies that fire or shapes that are awkward to pack. The
game currently has neither reliably, and the API accepts no rotation at all, so
a packing search has little to discover. This module is built for the game that
is coming, and is cheap enough to carry until then.
"""

from __future__ import annotations

import random
from typing import Iterable, Optional


Square = tuple[int, int]

# Importing server_harness FIRST is not optional. It puts server/ on sys.path
# and builds the item catalogue under the right working directory. Import a
# server module before it and the catalogue loads empty, silently, for the
# whole process -- see the note in server_harness.
import server_harness  # noqa: F401

from containers import GRID_SIZE  # the board, not restated (containers.py:17)


# ------------------------------------------------------------------ the board


def container_squares(session) -> set[Square]:
    """Every square inside a container. Items may only live here.

    Items span containers freely: the server validates against the UNION of
    all container squares, not against each container in turn.
    """
    out: set[Square] = set()
    for container in session.server_containers:
        out |= {tuple(s) for s in container.covered_squares()}
    return out


def occupied_squares(session, skip: str | None = None) -> dict[Square, str]:
    """Square -> id of the item on it. `skip` leaves one item out, which is
    what a move needs: the mover must not collide with its own old squares."""
    out: dict[Square, str] = {}
    for item in session.inventory_grid:
        if skip is not None and item.id == skip:
            continue
        for square in item.covered_squares():
            out[tuple(square)] = item.id
    return out


def free_squares(session) -> set[Square]:
    return container_squares(session) - set(occupied_squares(session))


def shape_of(item) -> list[Square]:
    """The item's own squares, before it has a position."""
    return [tuple(s) for s in (item.shape or [(0, 0)])]


def squares_at(shape: Iterable[Square], position: Square) -> set[Square]:
    x, y = position
    return {(x + dx, y + dy) for dx, dy in shape}


# ---------------------------------------------------------------- placement


def fits(shape, position, board: set[Square], taken: set[Square]) -> bool:
    covered = squares_at(shape, position)
    return covered <= board and not (covered & taken)


def legal_positions(session, item, skip: str | None = None) -> list[Square]:
    """Every square the item could be anchored at, in a stable order.

    Sorted so a bot's choice is reproducible from its seed. An unsorted set
    would make two identical genomes score differently between runs.
    """
    board = container_squares(session)
    taken = set(occupied_squares(session, skip=skip))
    shape = shape_of(item)
    return [p for p in sorted(board) if fits(shape, p, board, taken)]


def first_fit(session, item, skip: str | None = None) -> Optional[Square]:
    board = container_squares(session)
    taken = set(occupied_squares(session, skip=skip))
    shape = shape_of(item)
    for position in sorted(board):
        if fits(shape, position, board, taken):
            return position
    return None


def free_tile_count(session) -> int:
    return len(free_squares(session))


def container_positions(session, entry) -> list[Square]:
    """Where a CONTAINER may be anchored.

    A container does not go inside the board the way an item does -- it IS the
    board. So its legal squares are the whole grid, minus what other
    containers already claim, and it must stay in bounds.

    The bounds test is not optional: /purchase/item checks overlap only
    (main.py:1080), so the server will happily sell a container hanging off
    the edge, and every later battle then fails validation
    (containers.py:84). See BACKLOG.md.
    """
    width, height = GRID_SIZE
    claimed = container_squares(session)
    shape = [tuple(s) for s in (entry.shape or [(0, 0)])]

    out = []
    for y in range(height):
        for x in range(width):
            covered = squares_at(shape, (x, y))
            if covered & claimed:
                continue
            if any(sx < 0 or sx >= width or sy < 0 or sy >= height
                   for sx, sy in covered):
                continue
            out.append((x, y))
    return out


# --------------------------------------------------------------- rearranging


def repack_for(session, item) -> Optional[list[tuple[str, Square]]]:
    """A set of moves that would make room for `item`, or None.

    Returns the PLAN rather than performing it, because performing it means
    calling the server's /move endpoint once per step, and the caller should
    decide whether the item is worth that many calls.

    Deliberately shallow: it tries relocating ONE existing item at a time.
    A full repack is a bin-packing search, and with the current catalogue --
    mostly 1x1, no rotation available -- the deep version finds almost
    nothing the shallow one misses.
    """
    board = container_squares(session)
    shape = shape_of(item)
    taken_all = occupied_squares(session)

    for mover in session.inventory_grid:
        taken_without = {sq for sq, owner in taken_all.items() if owner != mover.id}
        # Where could the item go, if this one moved out of the way?
        target = next((p for p in sorted(board)
                       if fits(shape, p, board, taken_without)), None)
        if target is None:
            continue

        # And where could the mover go, without landing back on the item?
        blocked = taken_without | squares_at(shape, target)
        mover_shape = [tuple(s) for s in mover.shape or [(0, 0)]]
        spot = next((p for p in sorted(board)
                     if fits(mover_shape, p, board, blocked)), None)
        if spot is not None and tuple(spot) != tuple(mover.position):
            return [(mover.id, spot), (None, target)]
    return None


def repack_via_storage(session, item, buffer_limit: int = 4
                       ) -> Optional[tuple[list, list, Square]]:
    """Use storage as scratch space to make an arrangement that has no gaps.

    THIS IS WHY A FULL RACK IS NOT A DEAD END. `repack_for` needs a free
    square to shuffle into, so it can do nothing once the rack is packed --
    which is nearly always. But storage is unlimited
    (inventory_manager.py:111), so items can be lifted OFF the grid, the new
    item placed, and the lifted ones put back wherever they now fit. Any
    arrangement is reachable that way; the only cost is server calls.

    Returns (stashed_ids, replacements, target) where `replacements` is a list
    of (item_id, square) to restore afterwards, or None if even this cannot
    fit the item.

    Lifts the FEWEST items it can, smallest first, and gives up after
    `buffer_limit`. Lifting everything would always succeed and would cost two
    server calls per item for a rack of twenty.
    """
    board = container_squares(session)
    shape = shape_of(item)
    grid = list(session.inventory_grid)

    # Smallest first: lifting a 1x1 is the cheapest way to open a square, and
    # a small item is the easiest to put back afterwards.
    order = sorted(grid, key=lambda i: len(i.shape or [(0, 0)]))

    for count in range(1, min(buffer_limit, len(order)) + 1):
        lifted = order[:count]
        lifted_ids = {i.id for i in lifted}
        staying = {sq for i in grid if i.id not in lifted_ids
                   for sq in (tuple(s) for s in i.covered_squares())}

        target = next((p for p in sorted(board)
                       if fits(shape, p, board, staying)), None)
        if target is None:
            continue

        # Now put the lifted items back, largest first -- the awkward ones
        # need the choice while the board is still open.
        taken = staying | squares_at(shape, target)
        replacements, ok = [], True
        for back in sorted(lifted, key=lambda i: -len(i.shape or [(0, 0)])):
            back_shape = [tuple(s) for s in (back.shape or [(0, 0)])]
            spot = next((p for p in sorted(board)
                         if fits(back_shape, p, board, taken)), None)
            if spot is None:
                ok = False   # it does not go back; that is a net loss of a rack slot
                break
            taken |= squares_at(back_shape, spot)
            replacements.append((back.id, spot))

        if ok:
            return [i.id for i in lifted], replacements, target
    return None


# ---------------------------------------------------------------- annealing


def anneal(session, score, steps: int, rng: random.Random, apply_move) -> float:
    """Hill-climb the arrangement, keeping only moves that score better.

    `score` takes the session and returns a number; `apply_move` performs one
    move through the server and returns True on success. Both are injected so
    this stays pure geometry and never imports the harness.

    Returns the final score. If the objective is flat -- which it currently is,
    because adjacency almost never fires -- this does nothing and says so by
    returning the same number it started with.
    """
    best = score(session)
    if steps <= 0 or not session.inventory_grid:
        return best

    for _ in range(steps):
        mover = rng.choice(session.inventory_grid)
        options = legal_positions(session, mover, skip=mover.id)
        if not options:
            continue
        target = rng.choice(options)
        if tuple(target) == tuple(mover.position):
            continue

        before = tuple(mover.position)
        if not apply_move(mover.id, target):
            continue
        now = score(session)
        if now > best:
            best = now
        else:
            apply_move(mover.id, before)   # undo
    return best
