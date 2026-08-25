#!/usr/bin/env python3
"""Write down every footprint the catalogue actually contains.

    python tools/dump_footprints.py

The client's drag tests sweep this file: every shape, every rotation, every way
of carrying something. Written down rather than listed in the test, so that an
item with a shape nobody had thought of is covered the day it is added rather
than the day someone remembers to add a case for it.

`server/tests/test_items.py` fails when this file and the catalogue disagree,
so forgetting to regenerate is loud rather than silent.

The shapes are deduplicated: 24 distinct footprints across 232 items and
containers, and a test that ran all 232 would be running the same nine squares
over and over.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))

from grid_system import parse_map  # noqa: E402

# Anchored to this file rather than to the working directory: the guard in
# server/tests/test_items.py imports footprints() and pytest runs from server/.
ROOT = Path(__file__).resolve().parent.parent
CATALOGUE = ROOT / "server" / "data" / "items"
WRITTEN_TO = ROOT / "server" / "tests" / "fixtures" / "footprints.json"


def footprints() -> list[dict]:
    """Every distinct footprint, with one item that has it and how many do."""
    found: dict[tuple, list[str]] = defaultdict(list)
    for path in sorted(CATALOGUE.glob("*.json")):
        data = json.loads(path.read_text())
        entries = {**(data.get("items") or {}), **(data.get("containers") or {})}
        for slug, entry in sorted(entries.items()):
            if not entry.get("map"):
                continue
            shape = tuple(sorted(parse_map(entry["map"], slug).squares))
            found[shape].append(slug)

    return [
        {
            "squares": [list(square) for square in shape],
            "example": names[0],
            "items": len(names),
        }
        # Smallest first, so a diff reads in a sensible order.
        for shape, names in sorted(found.items(), key=lambda kv: (len(kv[0]), kv[0]))
    ]


def main() -> None:
    shapes = footprints()
    lines = ["["]
    for last, entry in enumerate(shapes):
        squares = ", ".join(f"[{x}, {y}]" for x, y in entry["squares"])
        lines.append("  {")
        lines.append(f'    "squares": [{squares}],')
        lines.append(f'    "example": {json.dumps(entry["example"])},')
        lines.append(f'    "items": {entry["items"]}')
        lines.append("  }" + ("," if last < len(shapes) - 1 else ""))
    lines.append("]")

    WRITTEN_TO.write_text("\n".join(lines) + "\n")
    print(f"{len(shapes)} footprints written to {WRITTEN_TO}")


if __name__ == "__main__":
    main()
