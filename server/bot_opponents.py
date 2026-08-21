"""
The opponents a player fights when no real one is available.

These are racks a bot actually built and actually fought with, exported from
the training archive. Before them, every opponent in the game came from ten
hand-written item lists in main.py -- the same nine items in the same order
for every player on every run, and rounds past ten reused round ten.

WHAT IS IN THE FILE
-------------------
Only what cannot be derived: which item, where it stands, which way it faces.
Everything else -- damage, cooldown, shape, rarity -- comes from ITEM_CATALOG
at load, so a build is about 300 bytes rather than 7,000 and the whole set is
a megabyte of plain JSON. Nothing is compressed, so nothing is decompressed.

WHY IT LOADS ONCE
-----------------
Parsed and indexed by round at import, so choosing an opponent is a list index
rather than a search: measured at 0.27 microseconds against roughly 600 for
the battle it sets up. Each round's list is kept sorted by rating, so picking
a difficulty band is a slice rather than a scan.

THE VERSION IS CHECKED, LOUDLY
------------------------------
A build names its items. Rename or remove one and the rack quietly loses it,
because the battle path skips item types it does not recognise -- so a stale
file does not fail, it just serves weaker opponents than intended and nobody
notices. The file records the catalogue version it was built against and this
module refuses to serve a mismatch.
"""

from __future__ import annotations

import json
import logging
import random
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

OPPONENTS_PATH = Path(__file__).resolve().parent / "data" / "bot_opponents.json"

#: What this build of the server expects the export to have been made against.
EXPECTED_VERSION = "1.0.0"

#: round -> builds at that round, sorted weakest to strongest.
_BY_ROUND: Dict[int, List[dict]] = {}
_LOADED = False


def load(path: Optional[Path] = None) -> int:
    """Read and index the opponents. Returns how many were loaded.

    Missing file is not fatal: the caller falls back to the built-in lists, so
    a developer without the export can still run the game. A file that IS
    there and does not match the catalogue is fatal, because serving it would
    be silently wrong.
    """
    global _LOADED
    _BY_ROUND.clear()
    _LOADED = True

    path = Path(path or OPPONENTS_PATH)
    if not path.exists():
        logger.warning("no bot opponents at %s; falling back to the built-in "
                       "opponents, which are the same nine items every game", path)
        return 0

    data = json.loads(path.read_text())
    version = data.get("version")
    if version != EXPECTED_VERSION:
        raise ValueError(
            f"{path.name} was built for game version {version!r} but this "
            f"server expects {EXPECTED_VERSION!r}. Its builds name items by "
            "type, so a stale file loses any item that has been renamed or "
            "removed -- and loses it quietly. Re-export it."
        )

    for build in data["builds"]:
        _BY_ROUND.setdefault(build["r"], []).append(build)
    for builds in _BY_ROUND.values():
        builds.sort(key=lambda b: b["e"])
    return sum(len(v) for v in _BY_ROUND.values())


def available() -> bool:
    if not _LOADED:
        load()
    return bool(_BY_ROUND)


def pick(round_number: int, rng: Optional[random.Random] = None,
         easiest: float = 0.0, hardest: float = 1.0) -> Optional[dict]:
    """An opponent for this round, or None if there are none to give.

    `easiest` and `hardest` are fractions of the round's difficulty range, so
    a caller can hand a struggling player the weaker end without filtering:
    the list is already sorted, so this is a slice.

    Rounds beyond the deepest exported one reuse the deepest, which is the
    same thing the built-in opponents did and is unreachable anyway -- ten
    wins ends a run, five losses ends it, so round fourteen is the last.
    """
    if not _LOADED:
        load()
    if not _BY_ROUND:
        return None

    rng = rng or random
    pool = _BY_ROUND.get(round_number)
    if pool is None:
        pool = _BY_ROUND[max(_BY_ROUND)]

    low = int(len(pool) * max(0.0, easiest))
    high = int(len(pool) * min(1.0, hardest))
    if high <= low:
        low, high = 0, len(pool)
    return pool[rng.randrange(low, high)]


def as_battle_items(build: dict, catalogue) -> Tuple[list, list]:
    """Turn a stored build into (items, containers) the battle engine takes.

    Raises on an item the catalogue does not know, rather than dropping it.
    A rack silently missing a piece is a weaker opponent than intended, in a
    way nobody would notice from the outside -- the same reasoning the
    built-in opponents already use when they place their items.
    """
    from battle_engine import BattleItem
    from containers import Container

    items = []
    for index, (item_type, position, rotation) in enumerate(build["i"]):
        spec = catalogue.get(item_type)
        if spec is None:
            raise ValueError(
                f"a stored opponent wants {item_type!r}, which is not an item. "
                "The export is older than the catalogue; re-export it."
            )
        items.append(BattleItem(spec=spec, position=tuple(position),
                                uid=f"bot_{index}_{item_type}", rotation=rotation))

    containers = [Container.of(container_type, tuple(position),
                               container_id=f"bot_container_{i}")
                  for i, (container_type, position) in enumerate(build["c"])]
    return items, containers
