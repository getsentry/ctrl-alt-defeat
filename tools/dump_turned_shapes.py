#!/usr/bin/env python3
"""Write down what the server makes of a turned shape, for the client to check.

    python tools/dump_turned_shapes.py

Both sides turn shapes. The server is the authority, but the client has to draw
a turn before the server has heard of the move, so it keeps its own copy of the
rule in APITypes. Two copies of one rule drift: the client turned shapes
anticlockwise for as long as anyone can tell, which put a spear's reach behind
its own tip.

So the answers are written down once, here, and both sides are held to them:

    server/tests/test_grid_system.py    the server still gives these answers
    client/test/unit/test_api_types.gd  the client gives the same ones

Change the turn on either side and one of those goes red. Regenerate the file
after a change that is meant, and the other side goes red until it agrees --
which is the point.

The maps are chosen for what each one can break, not for being real items:

    reaching right    which way a quarter turn goes at all
    spear             a long reach, so a turn the wrong way is unmissable
    anchored potion   the square that points up whichever way the item faces
    two zones         both zones at once, off an irregular footprint
    an L              a footprint whose corner moves when it turns
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))

from grid_system import Rotation, parse_map  # noqa: E402

WRITTEN_TO = Path("server/tests/fixtures/turned_shapes.json")

MAPS = [
    ("reaching right", ["#*"]),
    ("spear", ["*"] * 5 + ["#"] * 4),
    ("anchored potion", ["*", "^", "#"]),
    ("two zones", [".+..*", "++##*", "++##*", ".+..*"]),
    ("an L", ["##", "#."]),
]


def squares(offsets) -> str:
    """A list of squares on one line, so a diff reads as a change of shape."""
    return "[" + ", ".join(f"[{x}, {y}]" for x, y in sorted(offsets)) + "]"


def main() -> None:
    lines = ["["]
    for last, (name, item_map) in enumerate(MAPS):
        shape = parse_map(item_map, name)
        lines.append("  {")
        lines.append(f'    "name": {json.dumps(name)},')
        lines.append(f'    "map": {json.dumps(item_map)},')
        lines.append(f'    "anchors": {squares(shape.anchors)},')
        lines.append('    "turns": {')
        for turn, rotation in enumerate(Rotation):
            turned = shape.rotate(rotation)
            lines.append(f'      "{rotation.value}": {{')
            lines.append(f'        "squares": {squares(turned.squares)},')
            lines.append(f'        "star": {squares(turned.star)},')
            lines.append(f'        "diamond": {squares(turned.diamond)}')
            lines.append("      }" + ("," if turn < len(Rotation) - 1 else ""))
        lines.append("    }")
        lines.append("  }" + ("," if last < len(MAPS) - 1 else ""))
    lines.append("]")

    WRITTEN_TO.write_text("\n".join(lines) + "\n")
    print(f"{len(MAPS)} shapes written to {WRITTEN_TO}")


if __name__ == "__main__":
    main()
