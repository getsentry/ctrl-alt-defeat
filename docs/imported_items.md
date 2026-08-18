# Imported items

The 129 items whose numbers now come from a Backpack Battles item a Sentaur
can reach: 128 that we did not have, plus Mobius Lash, which was re-pointed
off a Berserker weapon. Each keeps its source's map, rarity, cost, sockets and
combat stats. The category is ours, and so is the name for the 9 that `docs/`
had already thought one up for; the rest still wear the source's name.

`server/data/items/*.json` is the record, not this file. Regenerate it with
`research/item_grids/write_import_doc.py` rather than editing it, so the counts
below cannot drift from the JSON.

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

**The original 96 items carry no `unbuilt`, and that does not mean they are
finished.** They were never surveyed against the wiki's wording. 21 of the
catalogue's 26 `buff` effects do nothing at all, because they name `contained`,
`adjacent` and `all_sentaur` — sets of items — while being written into the
player's buff dictionary, which is not where an item's numbers live.

## Set aside, not imported

Six more were scraped and deliberately kept out of the catalogue. The whole point
of each is to put another class's items in the shop, and those classes are not
being made, so there is nothing to build and no version of the game where they
work. They sit in `server/data/unavailable_items.json`, which nothing loads:

| Item | Why |
|---|---|
| Cog Badge (`cog_badge`) | Offers Engineer items, and there is no Engineer. |
| Flame Badge (`flame_badge`) | Offers Pyromancer items, and there is no Pyromancer. |
| Magic Badge (`magic_badge`) | Offers Mage items, and there is no Mage. |
| Skull Badge (`skull_badge`) | Offers Reaper items, and there is no Reaper. |
| Twine Badge (`twine_badge`) | Offers Adventurer items, and there is no Adventurer. |
| Wolf Badge (`wolf_badge`) | Offers Berserker items, and there is no Berserker. |

That file sits beside `data/items/` rather than in it, because `ConfigLoader`
globs `data/items/*.json` and an item in there would be offered. Keeping them
rather than deleting them does two jobs:
`research/item_grids/import_missing_items.py` reads the file, so a later scrape
does not add them back; and each has effects besides the class unlock -- Wolf
Badge's Battle Rage, Flame Badge's Heat -- so one could return as a different
item without being rebuilt from the wiki.

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

Both are still scraped, under `research/item_grids/`.

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
a second colour close to its first. See `server/item_looks.py`.

## Problems (weapons) (44)

| Item | From | Rarity | Cost | Map | Sockets | Unbuilt |
|---|---|---|---:|---|---:|---:|
| Bloodthorne |  | godly | 15 | 1x3 | 2 | 2 |
| Bloody Dagger |  | legendary | 12 | 3x4 | 1 | 2 |
| Broom |  | common | 4 | 1x4 | 1 | 2 |
| Buffer Overflow | Spear | rare | 6 | 1x9 | 1 | 1 |
| Burning Torch |  | epic | 5 | 1x2 | 1 | 2 |
| Claws of Attack |  | epic | 8 | 2x1 | 1 | 2 |
| Credential Harvester | Blood Harvester | unique | 7 | 3x4 | 3 | 2 |
| Crossblades |  | godly | 30 | 4x4 | 3 | 2 |
| Dancing Dragon |  | unique | 9 | 6x4 | 2 | 3 |
| Darksaber |  | godly | 16 | 1x4 | 2 | 2 |
| Data Miner | Shovel | rare | 8 | 1x4 | 1 | 2 |
| Eggscalibur |  | legendary | 10 | 5x4 | 2 | 2 |
| Falcon Blade |  | legendary | 15 | 5x5 | 2 | 2 |
| Fancy Fencing Rapier |  | godly | 12 | 1x4 | 1 | 2 |
| Frostbite |  | legendary | 11 | 1x3 | 2 | 3 |
| Hammer |  | rare | 8 | 3x3 | 2 | 1 |
| Hero Longsword |  | legendary | 19 | 3x5 | 2 | 1 |
| Hero Sword |  | epic | 7 | 3x4 | 1 | 1 |
| Holy Spear |  | godly | 18 | 3x9 | 2 | 2 |
| Hungry Blade |  | epic | 7 | 1x3 | 1 | 3 |
| Impractically Large Greatsword |  | godly | 14 | 2x4 | 4 | 1 |
| Katana |  | godly | 11 | 1x4 | 3 | 1 |
| Lightsaber |  | godly | 9 | 1x4 | 2 | 2 |
| Magic Staff |  | epic | 10 | 1x4 | 1 | 1 |
| Magic Torch |  | legendary | 11 | 3x2 | 1 | 1 |
| Manathirst |  | legendary | 13 | 1x3 | 1 | 2 |
| Mobius Lash | Thorn Whip | epic | 8 | 3x3 | 2 | 2 |
| Pandamonium |  | legendary | 11 | 5x4 | 2 | 2 |
| Ping Flood | Stone | common | 1 | 1x1 |  | 2 |
| Poison Dagger |  | epic | 11 | 1x2 | 1 | 2 |
| Poison Spear |  | legendary | 13 | 1x9 | 1 | 1 |
| Pop |  | unique | 6 | 2x2 | 4 | 1 |
| Prismatic Sword |  | godly | 17 | 3x5 | 2 | 5 |
| Rage Click | Artifact Stone: Cold | unique | 10 | 1x3 |  | 3 |
| Ripsaw Blade |  | legendary | 7 | 1x4 | 3 | 1 |
| Serpent Staff |  | legendary | 17 | 1x4 | 1 | 2 |
| Shell Totem |  | rare | 5 | 7x2 |  | 2 |
| Snow Stick |  | legendary | 8 | 1x4 | 1 | 1 |
| Spectral Dagger |  | legendary | 10 | 1x2 | 1 | 2 |
| Stack Smasher | Pan | common | 4 | 4x4 | 1 | 1 |
| Stankus' Toothpick |  | legendary | 9 | 5x6 | 1 | 2 |
| Stone Golem |  | godly | 16 | 4x3 | 1 | 3 |
| Thermal Throttle | Artifact Stone: Heat | unique | 9 | 1x3 |  | 3 |
| Thornbloom |  | godly | 14 | 3x3 | 2 | 3 |

## Protocols (accessories) (38)

| Item | From | Rarity | Cost | Map | Sockets | Unbuilt |
|---|---|---|---:|---|---:|---:|
| Amulet of Fortune |  | rare | 6 | 3x3 |  | 2 |
| Amulet of Light |  | rare | 6 | 7x7 |  | 2 |
| Angel Crystal |  | unique | 6 | 7x4 |  | 3 |
| Bag of Stones |  | rare | 3 | 1x3 |  | 1 |
| Blue Sage Collar |  | legendary | 8 | 3x3 |  | 1 |
| Boiling Pot |  | rare | 8 | 5x4 | 1 | 3 |
| Djinn Lamp |  | godly | 11 | 3x1 |  | 2 |
| Fanfare |  | godly | 7 | 6x5 |  | 2 |
| Flute |  | epic | 6 | 6x5 |  | 2 |
| Furcifer Prime Subscription |  | unique | 5 | 1x1 |  | 2 |
| Happy Bomb |  | unique | 7 | 2x2 |  | 1 |
| Heart Container |  | godly | 11 | 2x2 | 1 | 2 |
| Heart of Darkness |  | godly | 19 | 4x4 | 1 | 3 |
| Leaf Badge |  | unique | 5 | 3x3 |  | 3 |
| Lucky Piggy |  | epic | 7 | 3x2 |  | 3 |
| Maneki-neko |  | legendary | 10 | 3x4 |  | 5 |
| Oil Lamp |  | epic | 7 | 2x2 |  | 2 |
| Platinum Customer Card |  | epic | 8 | 3x3 |  | 4 |
| Present |  | unique | 10 | 2x2 |  | 2 |
| Puzzle Badge |  | unique | 5 | 4x4 |  | 3 |
| Rainbow Badge |  | unique | 5 | 1x1 |  | 2 |
| Red Orchid Collar |  | legendary | 8 | 3x3 |  | 1 |
| Repeater |  | unique | 8 | 5x3 |  | 1 |
| Rope |  | rare | 4 | 3x2 |  | 1 |
| Shepherds Crook |  | rare | 8 | 2x5 |  | 3 |
| Shiny Shell |  | common | 2 | 3x1 |  | 1 |
| Sir Sand |  | epic | 5 | 1x2 |  | 1 |
| Snowball |  | epic | 4 | 1x1 |  | 2 |
| Stable Recombobulator |  | unique | 6 | 5x5 |  | 2 |
| Star of Courage |  | unique | 1 | 1x1 |  | 3 |
| Stone Badge |  | unique | 5 | 1x1 |  | 3 |
| Time Dilator |  | unique | 8 | 1x1 |  | 2 |
| Unidentified Amulet |  | rare | 6 | 1x1 |  | 1 |
| Unstable Recombobulator |  | epic | 6 | 5x5 |  | 2 |
| Walrus Tusk |  | common | 4 | 1x2 |  | 1 |
| Whetstone |  | common | 4 | 1x3 |  | 1 |
| White Lily Collar |  | legendary | 8 | 3x3 |  | 2 |
| Wonky Snowman |  | epic | 8 | 1x2 |  | 1 |

## Pets (19)

| Item | From | Rarity | Cost | Map | Sockets | Unbuilt |
|---|---|---|---:|---|---:|---:|
| Blood Goobert |  | legendary | 14 | 4x2 |  | 2 |
| Cthulhu |  | unique | 8 | 5x4 |  | 3 |
| Cubert |  | unique | 8 | 4x4 |  | 2 |
| Hyper Hedgehog |  | godly | 12 | 2x4 |  | 3 |
| Jynx torquilla |  | legendary | 6 | 6x7 |  | 1 |
| King Goobert |  | godly | 23 | 4x3 | 2 | 2 |
| Light Goobert |  | godly | 15 | 4x2 |  | 1 |
| Lil Chestnut |  | unique | 6 | 8x2 |  | 3 |
| Paradise Birb |  | godly | 20 | 6x7 |  | 1 |
| Rainbow Goobert Megasludge Alphapuddle |  | godly | 54 | 4x4 |  | 1 |
| Rat Chef |  | rare | 8 | 3x4 |  | 3 |
| Ruby Egg |  | legendary | 10 | 2x2 |  | 2 |
| Shelly |  | rare | 6 | 4x2 |  | 3 |
| Sloth |  | unique | 5 | 4x3 |  | 3 |
| Snowmaster |  | legendary | 9 | 3x3 |  | 2 |
| Steel Goobert |  | legendary | 17 | 4x4 |  | 1 |
| Thorn Elemental |  | unique | 6 | 4x3 | 2 | 3 |
| Unsettling Presence |  | unique | 10 | 1x2 |  | 2 |
| Wolpertinger |  | godly | 12 | 4x4 |  | 3 |

## Defenses (armour, shields, helmets, shoes, gloves) (17)

| Item | From | Rarity | Cost | Map | Sockets | Unbuilt |
|---|---|---|---:|---|---:|---:|
| Cap of Discomfort |  | legendary | 14 | 1x2 | 1 | 3 |
| Cap of Resilience |  | epic | 7 | 1x2 | 1 | 3 |
| Gloves of Power |  | legendary | 10 | 4x1 |  | 2 |
| Glowing Crown |  | godly | 12 | 2x1 | 1 | 2 |
| Gold Armor |  | godly | 22 | 4x5 | 3 | 4 |
| King Crown |  | godly | 17 | 2x2 | 2 | 3 |
| Leather Boots |  | epic | 6 | 1x2 | 1 | 1 |
| Moon Armor |  | godly | 19 | 4x5 | 3 | 2 |
| Moon Shield |  | godly | 18 | 4x5 | 2 | 3 |
| Pine Protector |  | godly | 14 | 6x6 | 1 | 2 |
| Shield of Valor |  | legendary | 11 | 4x5 | 2 | 2 |
| Stone Armor |  | legendary | 13 | 2x3 | 2 | 4 |
| Stone Helm |  | legendary | 13 | 1x2 | 1 | 3 |
| Stone Shoes |  | legendary | 12 | 1x2 | 1 | 1 |
| Vampiric Armor |  | legendary | 15 | 2x3 | 2 | 2 |
| Vampiric Gloves |  | godly | 12 | 4x1 |  | 1 |
| Winged Boots |  | godly | 13 | 2x2 | 1 | 1 |

## Modules (gemstones) (5)

| Item | From | Rarity | Cost | Map | Sockets | Unbuilt |
|---|---|---|---:|---|---:|---:|
| Burning Coal |  | rare | 2 | 1x1 |  | 7 |
| Corrupted Crystal |  | epic | 7 | 1x1 |  | 6 |
| Lump of Coal |  | common | 2 | 1x1 |  | 7 |
| Tim |  | unique | 10 | 1x1 |  | 6 |
| Wisp |  | godly | 8 | 1x1 |  | 6 |

## Patches (potions) (4)

| Item | From | Rarity | Cost | Map | Sockets | Unbuilt |
|---|---|---|---:|---|---:|---:|
| Lightning in a Bottle |  | unique | 7 | 3x6 | 1 | 1 |
| Strong Heroic Potion |  | legendary | 9 | 1x3 |  | 1 |
| Strong Stone Skin Potion |  | legendary | 9 | 1x3 |  | 1 |
| Vampiric Potion |  | legendary | 8 | 1x3 |  | 1 |

## Scripts (food) (1)

| Item | From | Rarity | Cost | Map | Sockets | Unbuilt |
|---|---|---|---:|---|---:|---:|
| Cupcake |  | legendary | 5 | 3x3 |  | 1 |

## Containers (bags) (1)

| Item | From | Rarity | Cost | Map | Sockets | Unbuilt |
|---|---|---|---:|---|---:|---:|
| Chaos Experiment | Sack of Surprises | unique | 10 | 2x2 |  | 1 |

**From** is filled in only where our name differs from the source's.

## What is left

281 effect lines to build, each held in its item's `unbuilt`. A weapon's timer
is already built, so its line is the extra on top; every other item does nothing
at all until its line is built.

Every item in the table has a map that says exactly what its source's says. The
one that could not -- Cog Badge, whose charge travels an ordered route a map
cannot record -- is one of the six set aside.

