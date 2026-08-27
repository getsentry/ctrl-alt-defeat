#!/usr/bin/env python3
"""Write down where a rack's passengers land when the rack turns.

    python tools/dump_carried_round.py

Both sides carry an item round with a turning rack, and they have to give the
same answer. They did not: the client mapped the item's corner square through
the turn, which is right for a single square and wrong for anything longer,
because the corner of a turned body is not the turned corner. A two-square item
on a two-by-two rack came out one square off, and at the edge of the board that
put it outside the rack it was riding.

So the answers are written down once, here, and both sides are held to them:

    server/tests/test_inventory_manager.py  the server still gives these
    client/test/unit/test_carrying.gd       the client gives the same ones

Change the rule on either side and one of those goes red. Regenerate after a
change that is meant, and the other side goes red until it agrees -- which is
the point. This is the same lock that killed the `_turn` direction argument;
see tools/dump_turned_shapes.py.

The cases are chosen for what each can break, not for being real racks:

    a square tray            the rack does not move, so only the rider can
    a tall tray              the rack moves as well as the rider
    a long rider             the case that was wrong: its corner changes
    a rider in every corner  where on the tray it sits decides where it goes
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server"))

from grid_system import ItemShape, Rotation  # noqa: E402

WRITTEN_TO = ROOT / "server" / "tests" / "fixtures" / "carried_round.json"

SQUARE = [(0, 0), (1, 0), (0, 1), (1, 1)]
TALL = [(0, 0), (1, 0), (0, 1), (1, 1), (0, 2), (1, 2)]

# name, the tray's squares, the rider's own shape, the tray square it sits on
CASES = [
    ("one square on a square tray", SQUARE, [(0, 0)], (0, 0)),
    ("one square in each corner", SQUARE, [(0, 0)], (1, 1)),
    ("a tall rider on a square tray", SQUARE, [(0, 0), (0, 1)], (0, 0)),
    ("a tall rider, right hand column", SQUARE, [(0, 0), (0, 1)], (1, 0)),
    ("a wide rider on a square tray", SQUARE, [(0, 0), (1, 0)], (0, 0)),
    ("a tall rider on a tall tray", TALL, [(0, 0), (0, 1)], (0, 1)),
    ("a wide rider on a tall tray", TALL, [(0, 0), (1, 0)], (0, 2)),
    ("an L on a tall tray", TALL, [(1, 0), (0, 1), (1, 1)], (0, 0)),
]


def main() -> None:
    lines = ["["]
    for last, (name, tray, rider, sits_on) in enumerate(CASES):
        body = ItemShape(squares=list(tray))
        lines.append("  {")
        lines.append(f'    "name": {json.dumps(name)},')
        lines.append(f'    "tray": {json.dumps([list(s) for s in tray])},')
        lines.append(f'    "rider": {json.dumps([list(s) for s in rider])},')
        lines.append(f'    "sits_on": {json.dumps(list(sits_on))},')
        lines.append('    "lands_on": {')
        for turn, rotation in enumerate(Rotation):
            covers = [(sits_on[0] + dx, sits_on[1] + dy) for dx, dy in rider]
            corner = body.corner_of(covers, rotation)
            lines.append(
                f'      "{rotation.value}": [{corner[0]}, {corner[1]}]'
                + ("," if turn < len(Rotation) - 1 else "")
            )
        lines.append("    }")
        lines.append("  }" + ("," if last < len(CASES) - 1 else ""))
    lines.append("]")

    WRITTEN_TO.write_text("\n".join(lines) + "\n")
    print(f"{len(CASES)} cases written to {WRITTEN_TO}")


if __name__ == "__main__":
    main()
