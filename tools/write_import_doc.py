#!/usr/bin/env python3
"""Regenerate docs/imported_items.md from the catalogue.

Run after anything that changes the imported items, so the counts in the doc are
never a second, drifting copy of the JSON.
"""

import collections
import glob
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SET_ASIDE = ROOT / "server" / "data" / "unavailable_items.json"

ORDER = ["problem", "protocol", "pet", "defense", "module", "patch", "script", "container"]
TITLE = {
    "problem": "Problems (weapons)",
    "protocol": "Protocols (accessories)",
    "pet": "Pets",
    "defense": "Defenses (armour, shields, helmets, shoes, gloves)",
    "module": "Modules (gemstones)",
    "patch": "Patches (potions)",
    "script": "Scripts (food)",
    "container": "Containers (bags)",
}


def unfinished() -> list:
    """Every item in the catalogue that still carries work, by slug.

    Pulled out of main() so a test can count the same thing the doc says,
    rather than parsing the doc back or keeping a second copy of the rule.
    """
    found = []
    for path in sorted(glob.glob(str(ROOT / "server/data/items/*.json"))):
        data = json.loads(Path(path).read_text())
        for slug, item in (data.get("items") or data["containers"]).items():
            if "unbuilt" in item:
                found.append(slug)
    return found


def main() -> None:
    never = [
        (item["name"], slug, item["why"])
        for slug, item in json.loads(SET_ASIDE.read_text())["items"].items()
    ]

    rows = collections.defaultdict(list)
    for path in sorted(glob.glob(str(ROOT / "server/data/items/*.json"))):
        data = json.loads(Path(path).read_text())
        for slug, item in (data.get("items") or data["containers"]).items():
            if "unbuilt" not in item:
                continue
            rows[item.get("category", "container")].append(
                (
                    item["name"],
                    item["source"],
                    item["rarity"],
                    item["cost"],
                    len(item["map"][0]),
                    len(item["map"]),
                    len(item["unbuilt"]),
                    item.get("sockets", 0),
                )
            )

    total = sum(len(v) for v in rows.values())
    todo = sum(r[6] for items in rows.values() for r in items)

    out = [f"""# What is left to build

Every item whose numbers come from a Backpack Battles item a Sentaur can reach.
{total} of them carry work that is not done, listed here by category.

This file is generated. Run `tools/write_import_doc.py` rather
than editing it, so the counts cannot drift from
`server/data/items/*.json`, which is the record.

## How an unfinished item says so

The wiki's wording for every effect **not built yet** is held on the item as
`unbuilt`. It drains as the work lands: drop the line you implement, drop the key
when the list empties. A missing key is the only thing that says "finished", so
there is nothing to keep in step with it, and the counts here are just
`len(unbuilt)`.

A weapon does swing, because the wiki gives the cooldown, the damage range, the
accuracy and the stamina it costs, and nothing else is needed to run a timer. Its
**extra** effect is in `unbuilt`, and so is every effect of every item that is not
a weapon. All of these are `"in_shop": false` on top of that, because offering a
half-built item would change the balance of each shop roll while looking
finished. Turn one on by deleting its `in_shop` line.

## Set aside, not imported

Six more were scraped and deliberately kept out of the catalogue. The whole point
of each is to put another class's items in the shop, and those classes are not
being made, so there is nothing to build and no version of the game where they
work. They sit in `server/data/unavailable_items.json`, which nothing loads:

| Item | Why |
|---|---|"""]
    for name, slug, why in sorted(never):
        out.append(f"| {name} (`{slug}`) | {why} |")

    out.append("""
That file sits beside `data/items/` rather than in it, because `ConfigLoader`
globs `data/items/*.json` and an item in there would be offered. Keeping them
rather than deleting them says what was set aside and why, and each has effects
besides the class unlock -- Wolf Badge's Battle Rage, Flame Badge's Heat -- so
one could return as a different item without being rebuilt from the wiki.

Because none of them is loaded, no map in the catalogue holds a `%`, and
`grid_system.py` needs no character for the charge route Cog Badge sends around
itself.

Three badges are **not** in that list and do work:

- **Leaf Badge** offers Sentaur items, which is a class we have.
- **Stone Badge** stops your own class's items being offered, whatever the class.
- **Puzzle Badge** never mentions a class.

**Rainbow Badge** is the awkward one. "Items of all classes are offered in the
shop" is not impossible for us, it is merely empty — all our classes are already
offered — which leaves it a weaker Leaf Badge that also grants a buff. It is held
back as unbuilt rather than marked unavailable.

## Left out on purpose

- **Skills** (39). Handed out at a level rather than bought.
- **Subclass items** (4: Beastmaster, Grovekeeper, Pathfinder, Lifebinder).
  Subclasses do not exist yet. **Data Packets**, already in the catalogue, is a
  fifth: its source Piercing Arrow is a Hunter item, so it is held back with a
  `needs` line rather than deleted, because subclasses are meant to arrive.

Both are in the committed wiki corpus, under `research/wiki_pages/`.

## Categories

Category is flavour. It picks the file, the colour the client draws and the name
a player reads; it never changes how an item plays.

| Wiki type | Ours |
|---|---|
| Weapon, Weapon+Pet, Weapon+Food | `problem` |
| Accessory | `protocol` |
| Pet | `pet` — new, and the reason `sand` left the spare colours |
| Gemstone | `module` |
| Helmet, Armor, Shield, Shoes, Gloves | `defense` |
| Potion | `patch` |
| Food | `script` |
| Bag | a container |

`problem` and `protocol` hold 61 and 58 items against 36 patterns, so each borrows
a second colour close to its first. See `server/item_looks.py`.""")

    for category in ORDER:
        items = sorted(rows[category])
        if not items:
            continue
        out.append(f"\n## {TITLE[category]} ({len(items)})\n")
        out.append("| Item | From | Rarity | Cost | Map | Sockets | Unbuilt |")
        out.append("|---|---|---|---:|---|---:|---:|")
        for name, source, rarity, cost, w, h, lines, sockets in items:
            frm = source
            out.append(
                f"| {name} | {frm} | {rarity} | {cost} | {w}x{h} | "
                f"{sockets or ''} | {lines} |"
            )

    out.append(f"""
**From** is the Backpack Battles item each one's numbers come from.

## What is left

{todo} effect lines to build, each held in its item's `unbuilt`. A weapon's timer
is already built, so its line is the extra on top; every other item does nothing
at all until its line is built.

Every item in the table has a map that says exactly what its source's says. The
one that could not -- Cog Badge, whose charge travels an ordered route a map
cannot record -- is one of the six set aside.
""")
    (ROOT / "docs/imported_items.md").write_text("\n".join(out) + "\n")
    print(f"wrote docs/imported_items.md: {total} items, {todo} lines to build")


if __name__ == "__main__":
    main()
