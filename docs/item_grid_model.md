# Item Grid Model

**Status:** proposal, not implemented. No game code or item definition uses this yet.

This document specifies how an item's shape should be stored. It replaces the
`"shape": "2x2"` string used today in `server/data/items/*.json`.

Supporting data lives in `research/item_grids/`. See [Data files](#data-files).

> Per `CLAUDE.md`, update `docs/GAME_DESIGN_DOCUMENT.md` before you change
> mechanics. GDD section 4 already describes L-shapes, T-shapes and irregular
> patterns, so the design is ahead of the data. But GDD section 4.3 defines
> adjacency as "orthogonal only", and that rule cannot express aura zones.
> See [Aura is not adjacency](#aura-is-not-adjacency) before you edit it.

---

## 1. Why the current format fails

`"shape": "2x2"` can only describe a rectangle. Three things break:

1. **Irregular items.** 61 of 497 wiki items are not rectangles. 21 of those are
   reachable by the Ranger.
2. **Aura cells.** Many items act on cells they do not occupy. A Spear is 1x4 but
   reaches 5 cells above it. There is nowhere to record this.
3. **Bags with holes.** Utility Pouch is 3x3 with the bottom-middle cell missing.
   The engine now handles this — `Container.shape` in `server/containers.py` is
   a `Shape` (a list of covered offsets), not a width and a height. The JSON is
   what still cannot express it.

All 96 of our items now map to a wiki source, and **55 have the wrong size**.
See [Migration](#migration).

---

## 2. The text map

An item's shape is a list of equal-length strings, one per row. This is the same
format the wiki uses, so a scrape is a copy and a re-scrape diffs row by row.

```json
"piercing_arrow": {
  "map": [".*+.",
          "+##*",
          ".*+."],
  "provides_slots": false
}
```

### Legend

| Char | Meaning |
|:---:|---|
| `#` | footprint cell — the item occupies this square |
| `^` | footprint cell that is a world-up aura anchor (see [section 5](#5-world-up-aura)) |
| `*` | star aura cell |
| `+` | diamond aura cell |
| `%` | a square a charge travels through (see [section 12](#12-lightning-path--cells-only)) |
| `.` | empty |

`*` and `+` are two **independent** zones. They are not decoration and not
interchangeable — each drives its own effect clause:

```
Piercing Arrow                       .*+.
  * ☆ Weapons deal +50% crit damage. +##*
  * ◇ Item activates: +1 luck.       .*+.
```

10 Ranger-accessible items use both zones at once. Store aura as a map keyed by
zone, never as a single list.

### Record the source

Add a `source` field naming the Backpack Battles item each of ours came from:

```json
"null_blade": {
  "name": "Null blade",
  "map": ["##", "##"],
  "source": "Wooden Sword"
}
```

Today that link lives only in prose, as `**Backpack Battles Equivalent:**` lines
in `docs/*.md`, matched by heading. That is fragile — renaming an item in the
JSON silently breaks it, which is exactly how 37 of our 96 items lost their
mapping. Holding the link in the item itself survives renames, and lets the
scraper join on a field instead of a heading.

Once `source` exists, the scraper should prefer it and fall back to the docs, so
the two can co-exist while the field is filled in.

### Derived values

Everything else comes from `map`. Do not store it:

- `width`, `height` — bounding box of the whole map
- `footprint` — coordinates of `#` and `^`
- `aura.star`, `aura.diamond` — coordinates of `*` and `+`
- the four rotations

### Examples

```
Ranger Bag      Vineweave Basket   Health Potion    Utility Pouch    Boiling Pot
["##",          ["###",            ["*",            ["###",          [".+..*",
 "##",           "###",             "^",             "###",           "++##*",
 "##"]           "###"]             "#"]             "#.#"]           "++##*",
                                                                      ".+..*"]
6 slots         9 slots            anchored aura    bag with a hole   two zones
```

---

## 3. Bags need no second grid

A bag's own cells **are** the slots it provides. I checked all 27 bags on the
wiki: for 26 of them the footprint cell count equals the "Add N backpack slots"
in the effect text. No bag carries any aura glyph.

```json
"ranger_bag": {
  "map": ["##", "##", "##"],
  "provides_slots": true,
  "slots": 6
}
```

The only exception is Sack of Surprises, which the game replaces at start.

`slots` is redundant — it always equals the `#` count. Keep it anyway as a
checksum, and let the parser reject a mismatch. That check is what found the
wrong sizes listed in [Migration](#migration).

**Bags can be irregular.** Both Ranger bags are plain rectangles, but Box of
Cogs, Puzzlebox, Sewing Case and Utility Pouch are not, and Utility Pouch has a
hole. A container is a cell set, not a `(width, height)` pair.

---

## 4. Aura is not adjacency

GDD section 4.3 says adjacency is orthogonal contact. Aura does **not** follow
that rule, so you cannot compute it.

Of the 152 Ranger-accessible items that have aura:

- 78 have aura inside the orthogonal neighbourhood
- **74 reach further out**

A Spear is 1x4 and reaches 5 cells straight up. Amulet of Feasting has 24 aura
cells, 23 of them beyond its neighbours.

So aura must be authored per item. It is a separate concept from the adjacency
rule the GDD already defines, and both need to exist.

---

## 5. World-up aura

For most items the aura turns with the item. For 17 items it does not — the
wiki draws them in two or three rotations for exactly this reason. It is
Bag of Stones plus the 16 potions. 11 of the 17 are in our scope; the rest are
Reaper potions.

One rule covers all 17:

> A footprint cell marked `^` is an **anchor**. Anchors turn with the item. Each
> anchor projects its aura **straight up in world space**, past the item's own
> cells to the first square clear of it.

Mark the anchors in the map. Do not add a per-item flag — Bag of Stones needs
this per cell, not per item.

**Past the item's own cells, not dropped at them.** The wiki is explicit on
both pages: a potion's star "will always be placed above the Potion, rather
than rotating along with the item", and Bag of Stones "only has star slots
vertically above it, regardless of the orientation". Turned half round, a
potion's anchor is the lower of its two cells, and an aura stopped at the cell
above it would stop inside the item — leaving a potion upside down with no star
at all, where the game gives it one directly above.

Two anchors that clear the item into the same square make one aura, not two.
That is what keeps Bag of Stones at one star on end and two laid flat.

```
Health Potion         Bag of Stones
["*",                 ["*",
 "^",   <- neck only   "^",   <- both cells anchor
 "#"]                  "^"]
```

Checked against every rotation the wiki draws:

| Item | Rotation | Stars | Rule gives |
|---|---|---|---|
| Health Potion | vertical | 1 | 1 ✔ |
| Health Potion | 90° CW | 1 | 1 ✔ |
| Health Potion | 90° CCW | 1 | 1 ✔ |
| Health Potion | 180° | 1 | 1 ✔ (anchor is the lower cell; the aura clears the upper one) |
| Bag of Stones | vertical | 1 | 1 ✔ (both anchors clear into the same square) |
| Bag of Stones | horizontal | 2 | 2 ✔ |
| Bag of Stones | 180° | 1 | 1 ✔ |
| Bag of Stones | 270° | 2 | 2 ✔ |

The 180° rows were missing, and 180° is the only rotation the first version of
this rule got wrong. Bag of Stones hid it: both its cells anchor, so it never
depended on which end the anchor had travelled to. A potion has one, so it did.

The simpler rule "every cell projects up" gets Bag of Stones right but gives
potions 2 stars instead of 1. Use the anchor version.

Author the map in the **unrotated** orientation. For these items that is the
tall one.

---

## 6. Rotation

`ItemShape.rotate()` at `server/grid_system.py:24` turns the cells, then
normalises so the top-left sits at `(0, 0)`.

**Trap:** if you rotate the footprint and the aura separately, each normalises
against its own bounding box and the two drift apart. Rotate the combined cell
set, normalise once, then split back by role.

Anchors are the exception. Turn the anchor cells with the footprint, then
re-project their aura upward **after** the rotation, never before.

---

## 7. Parser validation

Text maps are easy to mistype, so reject rather than guess:

1. every row the same length
2. only legal characters
3. at least one footprint cell
4. footprint is 4-connected — this holds for all 497 wiki items, so it is safe
   to enforce
5. no fully blank leading or trailing row or column, so equal shapes compare
   equal
6. if `provides_slots`, the `#` count equals `slots`

---

## 8. Known one-off

**Cog Badge** (Neutral) uses a lightning **path**: "Emit a charge, travelling
1 ⚡ every 2s". The cells are an ordered walk, not a zone. It is the only such
item in scope. The data marks it `"unsupported": "lightning_path"`. Drop it or
hard-code it.

The wiki also has a fourth glyph (`tertiary`). It is used by 2 Mage items only
and never appears in our scope.

---

## 9. Sockets — scraped, not implemented

**Stretch goal. The game has no socket concept today, and this model does not
add one.** The data is scraped so the numbers are on hand when someone picks it
up.

The infobox carries a `sockets` field. 144 items across the wiki use it, **85 of
them in our scope**:

| Sockets | Ranger-scope items |
|:---:|---|
| 1 | 50 |
| 2 | 25 |
| 3 | 8 |
| 4 | 2 |

Mostly weapons (51), then armour (8), shields (7) and helmets (5). The largest
is Impractically Large Greatsword with 4.

**A socket is a count, not a grid position.** This matters for the model: it is
the wiki's own proof that positional data and attachment data are separate
concerns. It also confirms the decision in [section 3](#3-bags-need-no-second-grid) —
if slot-granting had needed its own symbol, sockets would have needed one too,
and they clearly do not.

The relation is one way. All 14 gemstones have `sockets: 0` — a gemstone is what
*fills* a socket, so only the host item carries a count.

This is the gap behind our Module family. `modules.json` items are the gemstone
analogues, and right now there is nothing for them to attach to.

The field appears in a record only when it is non-zero. Absent means 0.

```json
"bloodthorne": {
  "map": ["#", "#", "#"],
  "sockets": 2
}
```

---

## 10. Field inventory

Every field the wiki infobox carries. All of them are now scraped. The last
column says whether the game uses the value today — most do not, and that is
expected; the data is there so nobody has to re-scrape when they build it.

| Wiki field | Pages | Stored as | Used by the game |
|---|---:|---|---|
| `name` | 498 | `wiki` (record key) | yes |
| `image` | 498 | `image` | no — art is not wired up |
| `rarity` | 498 | `rarity` | yes |
| `type` | 498 | `type` | partly — we call it `category` |
| `cost` | 497 | `cost` | yes |
| `grid` | 497 | `map` | **no — this is what this document proposes** |
| `effect` | 496 | `effect` | hand-written as `triggers` |
| `icontype` | 333 | `icontype` | no |
| `class` | 316 | `class` | yes, renamed |
| `sockets` | 145 | `sockets` | no — [section 9](#9-sockets--scraped-not-implemented) |
| `stamina` | 110 | `stats.stamina` | yes, as `cpu_cost` |
| `cooldown` | 110 | `stats.cooldown` | yes |
| `mindamage` | 108 | `stats.min_damage` | yes |
| `maxdamage` | 108 | `stats.max_damage` | yes |
| `accuracy` | 108 | `stats.accuracy` | yes |
| `skillround` | 64 | `skillround` | no |
| `subclassname` | 35 | `subclass` | no |
| `addshop` | 10 | `addshop` | no |
| `inshop` | 5 | `inshop` | no |
| `transformcatalyst` | 1 | `transform_catalyst` | no |
| `tags` | — | not stored | the template derives it from `effect` |

Three notes on the values:

- **`accuracy` scale differs.** The wiki writes a percent (`90`), our items a
  fraction (`0.9`). The scraper converts to our form, so `stats` compares
  directly against a trigger effect.
- **`effect` stays raw.** It is kept as wikitext, one entry per bullet.
  `{{icon/luck}}` and `[[links]]` carry meaning that stripping would lose.
- **`subclassname` is real for us.** The Ranger has two specialisations, Hunter
  and Pathfinder. We have no equivalent concept.

---

## 11. Mismatches against our items

`mismatches.md` is generated on every scrape. It lists every field where an item
in `server/data/items/` disagrees with its Backpack Battles source.

Shape differences are reported as **maps, not as `WxH` strings** — the current
`"shape"` value is drawn out so it compares like for like, next to the map to
author. The right-hand side is the value to paste, so the report doubles as the
migration worklist:

```
Spike Launcher  <-  Tusk Piercer
    ours 2x2      expected (footprint 3x3, irregular)
    ##            .#..
    ##            ###*
                  .#..
```

The size label is the **footprint**. The map beside it also draws the aura, so
it is often wider — here a 3x3 plus-shape with one star slot on its right arm.
Every other field stays in a plain table.

**76 of the 96 matched items disagree, across 208 fields:**

| Field | Items affected |
|---|---:|
| `cost` | 62 |
| `shape` | 55 |
| `rarity` | 25 |
| `stamina` | 18 |
| `min_damage` | 12 |
| `max_damage` | 12 |
| `cooldown` | 10 |
| `accuracy` | 8 |
| `class` | 6 |

Only **`class`** is by design: we renamed Ranger to `sentaur`, so the comparison
normalises the pair. The 3 rows that remain are real — items we made
class-specific that have no class restriction on the wiki. Leave them.

**`rarity` is decided: adopt the wiki value.** Backpack Battles has exactly six
rarities — `common`, `rare`, `epic`, `legendary`, `godly`, `unique`. Our
`uncommon` is not one of them. 25 items differ on rarity, and two groups need
attention that the mapped tables cannot reach:

- **All 12 `uncommon` items now have a wiki rarity to adopt**, except the two
  Flawed Modules, which take the gemstone ladder below. `mismatches.md` lists
  every non-wiki rarity under "Invalid rarity values".
- **The 14 Modules mirror the wiki's gemstone tiers.** Those pages read
  `rarity=Varies`, because one page covers all five tiers and the tier name
  carries the rarity. Our cost ladder already matches the wiki exactly
  (1/2/4/8/16), which confirms the tiers align — only rarity slipped, because
  `uncommon` was inserted at step two and pushed the rest down one:

  | Tier | Cost | Ours | Should be |
  |---|---:|---|---|
  | Chipped | 1 | common | common ✔ |
  | Flawed | 2 | uncommon | **rare** |
  | Regular | 4 | rare | **epic** |
  | Flawless | 8 | epic | **legendary** |
  | Perfect | 16 | legendary | **godly** |

`cost` is the biggest group, and it is **decided: costs should match the wiki.**
All 62 differences get reset to the wiki value.

Our current values cluster on round tiers — across all our items, `8` appears 19
times and `4` fifteen times, with `20` and `25` reserved for high rarity — so
this replaces a simplified price ladder with the real one. 33 of the 46 go down
and 13 go up, which will shift the economy. Treat rebalancing as a separate job.

82 of the 96 items have a plain numeric wiki cost; 20 of those already agree and
need no change. The other 14 are the Modules, whose gemstone pages carry a tier
ladder (`1/2/4/8/16`) instead of one number — our module costs already match
that ladder exactly.
Unmapped items have no wiki cost and keep what they have, which is one more
reason to close the mapping gaps in [Migration](#migration).

`accuracy` never disagrees, because almost none of our weapons are mapped yet.
Only 2 items have damage values on both sides. Closing the 17 unmapped weapons
in [Migration](#migration) will expand this report, not shrink it.

---

## Data files

`research/item_grids/` holds the scraped data. Nothing in the game imports it.

| File | Contents |
|---|---|
| `ranger_item_grids.json` | 258 Ranger-accessible items in the format above |
| `all_item_grids.json` | all 497 wiki items, for later classes |
| `mismatches.md` | generated report, [section 11](#11-mismatches-against-our-items) |
| `scrape_item_grids.py` | regenerates all three from the wiki |

`ranger_item_grids.json` omits a field when it does not apply, so `sockets`,
`provides_slots` and `aura_anchored` are absent rather than zero or false.
`all_item_grids.json` is a flat dump and always writes every key.

Refresh with:

```
python research/item_grids/scrape_item_grids.py
```

Each record keeps `wiki_grid`, the untouched wiki rows. A later re-scrape can
then compare strings instead of re-deriving geometry. It also keeps `image`, the
wiki sprite filename, so you can fetch the original art and confirm its true
pixel aspect. Because a cell is square, a 2x3 item needs art with a 2:3 ratio.

Source of the data: the wiki stores a grid in the raw wikitext of every item
page. `Template:Grid` defines the characters.

```
https://backpackbattles.wiki.gg/wiki/Ranger_Bag?action=raw

{{Item infobox
|name=Ranger Bag
|grid=
11
11
11
}}
```

Wiki digits map to our characters as `1`→`#`, `2`→`*`, `3`→`+`, `5`→`%`, and
anything else is empty. The wiki writes blanks as both `0` and `-`; `0` is only
a separator between rotations drawn side by side, and we author one rotation per
item, so we use a single blank character.

---

## Migration

`docs/*.md` already record the original item as
`**Backpack Battles Equivalent:** Leather Bag`. The scraper reads those lines,
resolves them against the wiki, and writes the result into the `repo` field of
each item. All 96 of our items resolve today.

**55 of the 96 have the wrong size**, and 76 disagree with the wiki on
something. `mismatches.md` has the full list; the shape rows are these:

| File | Item | Now | Correct |
|---|---|---|---|
| `containers.json` | Network Cache | 2x2 | 2x3 |
| `containers.json` | Mesh Network Hub | 3x1 | 3x3 |
| `containers.json` | Patch Registry | 2x2 | 1x4 |
| `monitors.json` | Sanctified Firewall | 2x2 | 2x3 |
| `protocols.json` | Vampire Rootkit | 2x2 | 1x1 |
| `problems.json` | Spike Launcher | 2x2 | 3x3 plus-shape |
| `scripts.json` | Health Check Script | 1x1 | 3-cell L |

### Why 20 items have no mapping

The mapping exists **only** as `**Backpack Battles Equivalent:**` lines in
`docs/*.md`, matched by heading. An item is mapped if and only if a heading
carries its name.

It was 37. Three matching bugs accounted for 16 of those, all now fixed in the
scraper:

- **Headings collide across files.** `Load Balancer`, `Cryogenic Shield` and
  `System Restore` each appear in two docs and mean different items. The lookup
  now keys on the doc file as well, so `containers.json`'s Load Balancer reads
  `containers.md`. That alone recovered Load Balancer → Protective Purse and
  Cryogenic Shield → Ice Armor, both of which had been picking up the other
  file's stale value.
- **Headings can name the wiki item in parentheses.** The Modules are documented
  as `Performance Module (Ruby)`, `Memory Module (Sapphire)` and so on. The
  lookup strips a trailing parenthetical.
- **Gemstone tiers share one wiki page.** `Chipped Performance Module` and
  `Perfect Performance Module` both resolve to Ruby, so the lookup also strips a
  leading `Chipped`/`Flawed`/`Flawless`/`Perfect`.

Some of the rest are a **renaming drift**: the JSON was renamed and the docs
were not, so the heading no longer matches. Git settles those. The scraper reads
the history of each item JSON and treats one name leaving and another arriving
in the same commit, with identical cost, rarity and attack stats, as a rename.
Nine turned up in `problems.json` alone:

| Old name | Current name |
|---|---|
| Null Pointer Exception | Null blade |
| Memory Leak | Stack Smasher |
| Race Condition | Deadlock Twins |
| Infinite Loop | Mobius Lash |
| SQL Injection | SQL Injector |
| DDoS Attack | Denier of Service |
| Zero Day Exploit | Day Zero |
| Network Scanner | Nullshot |
| Distributed Scanner Array | Querystorm |

Two of those had a heading under the old name, so renaming the heading recovered
them: **Null blade → Wooden Sword** and **Stack Smasher → Axe**. Both headings are
now updated in `docs/problems.md`.

The other seven never had an equivalent recorded, even under the old name.
Neither did the items that were authored new and never documented. Those need a
decision, not a lookup.

**A warning for whoever makes those decisions.** The doc blocks carry
`Shape`/`Damage`/`Cost` lines, but those are the *wiki* item's numbers, not
ours — `Null Pointer` reads 1-3 damage at cost 3, which is Wooden Sword's stats,
not what our Null blade ever had. Scoring our values against them produces
confident nonsense. `unmapped.md` states the reason for each item and quotes the
git evidence instead.

Once a pairing is settled, rename the heading in `docs/*.md` to match the item
and re-run the scraper. No code change. Better still, record it as a `source`
field on the item, per [section 2](#record-the-source).

This gates the cost, rarity and shape passes: an unmapped item has no wiki value
to adopt, so it keeps whatever it has today.

---

## 12. Lightning path — cells only

One item, Cog Badge, emits a charge that travels a fixed route around it. The
wiki draws that route with `5`, which we read as `%`.

```
...%...
..%%...
.%.%.%.
%..#..%
.%...%.
..%.%..
...%...
```

A map is a set of squares, so it records where the charge goes but not the order
it visits them in, and the effect needs the order:

> **After 4s:** Emit a charge, traveling 1 lightning every 2s.
> Items under the charge trigger 10% faster + 3% for each lightning traveled.

The cells are held anyway, because the alternative is an item whose map disagrees
with the item it came from. Whatever builds this effect has to work the route out
from the picture, or store it beside the map.

`parse_map` treats `%` like aura: legal, counted when checking for a blank edge,
and not part of the footprint.
