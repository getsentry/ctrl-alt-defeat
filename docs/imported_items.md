# What is left to build

Every item whose numbers come from a Backpack Battles item a Sentaur can reach.
101 of them carry work that is not done, listed here by category.

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
|---|---|
| Cog Badge (`cog_badge`) | Offers Engineer items, and there is no Engineer. |
| Flame Badge (`flame_badge`) | Offers Pyromancer items, and there is no Pyromancer. |
| Heartbeat Node (`health_check`) | Set aside 2026-08-19: Goobling is gated behind the It's Slime Time! skill, which this game does not have, has no recipe and no subclass, so it had no way to be obtained. Bring it back by giving it a path. |
| Magic Badge (`magic_badge`) | Offers Mage items, and there is no Mage. |
| Skull Badge (`skull_badge`) | Offers Reaper items, and there is no Reaper. |
| Twine Badge (`twine_badge`) | Offers Adventurer items, and there is no Adventurer. |
| Wolf Badge (`wolf_badge`) | Offers Berserker items, and there is no Berserker. |

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
a second colour close to its first. See `server/item_looks.py`.

## Problems (weapons) (16)

| Item | From | Rarity | Cost | Map | Sockets | Unbuilt |
|---|---|---|---:|---|---:|---:|
| Blade Server | Impractically Large Greatsword | godly | 14 | 2x4 | 4 | 1 |
| Build Golem | Stone Golem | godly | 16 | 4x3 | 1 | 2 |
| Cert Lance | Holy Spear | godly | 18 | 3x9 | 2 | 2 |
| Data Miner | Shovel | rare | 8 | 1x4 | 1 | 1 |
| Day Zero | Artifact Stone: Death | unique | 8 | 1x3 |  | 2 |
| Loaded Dice Rig | Fortuna's Grace | legendary | 10 | 4x3 | 1 | 1 |
| Pandemic | Pandamonium | legendary | 11 | 5x4 | 2 | 1 |
| Ping of Death | Stone | common | 1 | 1x1 |  | 1 |
| Polyglot Blade | Prismatic Sword | godly | 17 | 3x5 | 2 | 5 |
| Rage Click | Artifact Stone: Cold | unique | 10 | 1x3 |  | 1 |
| Ripsaw | Ripsaw Blade | legendary | 7 | 1x4 | 3 | 1 |
| Snake Case | Serpent Staff | legendary | 17 | 1x4 | 1 | 2 |
| Spam Cannon | Belladonna's Whisper | legendary | 13 | 4x3 | 1 | 1 |
| Thermal Throttle | Artifact Stone: Heat | unique | 9 | 1x3 |  | 1 |
| Venom Lance | Poison Spear | legendary | 13 | 1x9 | 1 | 1 |
| Vim Katana | Katana | godly | 11 | 1x4 | 3 | 1 |

## Protocols (accessories) (30)

| Item | From | Rarity | Cost | Map | Sockets | Unbuilt |
|---|---|---|---:|---|---:|---:|
| Build Step | Amulet of Alchemy | rare | 6 | 3x9 |  | 1 |
| Cold Wallet | Piggybank | common | 3 | 2x3 |  | 1 |
| Crimson Collar | Red Orchid Collar | legendary | 8 | 3x3 |  | 1 |
| Crypto Mining Rig | Box of Riches | rare | 5 | 2x1 |  | 1 |
| Daemon Lamp | Djinn Lamp | godly | 11 | 3x1 |  | 1 |
| Elastic Waistband | Amulet of Feasting | rare | 6 | 5x9 |  | 1 |
| Entropy Piggy | Lucky Piggy | epic | 7 | 3x2 |  | 1 |
| Fork Bomb | Wonky Snowman | epic | 8 | 1x2 |  | 1 |
| Fortune Bot | Maneki-neko | legendary | 10 | 3x4 |  | 3 |
| Founder's Star | Star of Courage | unique | 1 | 1x1 |  | 3 |
| Free Trial | Customer Card | rare | 4 | 1x1 |  | 1 |
| Logic Bomb | Happy Bomb | unique | 7 | 2x2 |  | 1 |
| Lucky Bitflip | Amulet of Fortune | rare | 6 | 3x3 |  | 2 |
| Null Heart | Heart of Darkness | godly | 19 | 4x4 | 1 | 1 |
| Obfuscator | Sir Sand | epic | 5 | 1x2 |  | 1 |
| Packet Bag | Bag of Stones | rare | 3 | 1x3 |  | 1 |
| Patch Cable | Rope | rare | 4 | 3x2 |  | 1 |
| Platinum Tier | Platinum Customer Card | epic | 8 | 3x3 |  | 4 |
| Power Brick | Amulet of Energy | rare | 6 | 1x2 |  | 1 |
| Prime Subscription | Furcifer Prime Subscription | unique | 5 | 1x1 |  | 2 |
| Puzzle Badge | Puzzle Badge | unique | 5 | 4x4 |  | 3 |
| Rainbow Badge | Rainbow Badge | unique | 5 | 1x1 |  | 1 |
| Ranger Badge | Leaf Badge | unique | 5 | 3x3 |  | 2 |
| Repeater | Repeater | unique | 8 | 5x3 |  | 1 |
| Stable Refactor | Stable Recombobulator | unique | 6 | 5x5 |  | 1 |
| Stone Badge | Stone Badge | unique | 5 | 1x1 |  | 2 |
| Time Dilator | Time Dilator | unique | 8 | 1x1 |  | 2 |
| Undocumented Feature | Unidentified Amulet | rare | 6 | 1x1 |  | 1 |
| Unmarked Package | Present | unique | 10 | 2x2 |  | 1 |
| Unstable Refactor | Unstable Recombobulator | epic | 6 | 5x5 |  | 1 |

## Pets (8)

| Item | From | Rarity | Cost | Map | Sockets | Unbuilt |
|---|---|---|---:|---|---:|---:|
| Bird of Paradigm | Paradise Birb | godly | 20 | 6x7 |  | 1 |
| Legacy Code | Cthulhu | unique | 8 | 5x4 |  | 1 |
| Lil Broker | Lil Chestnut | unique | 6 | 8x2 |  | 2 |
| Random Seed | Ruby Egg | legendary | 10 | 2x2 |  | 1 |
| Root Garbo | King Goobert | godly | 23 | 4x3 | 2 | 2 |
| Shell Script | Shelly | rare | 6 | 4x2 |  | 1 |
| The Kludge | Wolpertinger | godly | 12 | 4x4 |  | 1 |
| Zombie Process | Unsettling Presence | unique | 10 | 1x2 |  | 1 |

## Defenses (armour, shields, helmets, shoes, gloves) (5)

| Item | From | Rarity | Cost | Map | Sockets | Unbuilt |
|---|---|---|---:|---|---:|---:|
| Bare Metal Boots | Stone Shoes | legendary | 12 | 1x2 | 1 | 1 |
| Hot Swap Boots | Winged Boots | godly | 13 | 2x2 | 1 | 1 |
| Itchy Firmware | Cap of Discomfort | legendary | 14 | 1x2 | 1 | 1 |
| Root Certificate | King Crown | godly | 17 | 2x2 | 2 | 1 |
| Splinter Guard | Pine Protector | godly | 14 | 6x6 | 1 | 2 |

## Modules (gemstones) (30)

| Item | From | Rarity | Cost | Map | Sockets | Unbuilt |
|---|---|---|---:|---|---:|---:|
| Dead Cell | Lump of Coal | common | 2 | 1x1 |  | 7 |
| Golden Sample Efficiency Module | Emerald | godly | 16 | 1x1 |  | 3 |
| Golden Sample Memory Module | Sapphire | godly | 16 | 1x1 |  | 3 |
| Golden Sample Performance Module | Ruby | godly | 16 | 1x1 |  | 3 |
| Golden Sample Processing Module | Topaz | godly | 16 | 1x1 |  | 3 |
| Golden Sample Security Module | Amethyst | godly | 16 | 1x1 |  | 3 |
| Gremlin | Tim | unique | 10 | 1x1 |  | 6 |
| Hot Cell | Burning Coal | rare | 2 | 1x1 |  | 7 |
| Overclocked Efficiency Module | Emerald | legendary | 8 | 1x1 |  | 3 |
| Overclocked Memory Module | Sapphire | legendary | 8 | 1x1 |  | 3 |
| Overclocked Performance Module | Ruby | legendary | 8 | 1x1 |  | 3 |
| Overclocked Processing Module | Topaz | legendary | 8 | 1x1 |  | 3 |
| Overclocked Security Module | Amethyst | legendary | 8 | 1x1 |  | 3 |
| Refurb Efficiency Module | Emerald | rare | 2 | 1x1 |  | 3 |
| Refurb Memory Module | Sapphire | rare | 2 | 1x1 |  | 3 |
| Refurb Performance Module | Ruby | rare | 2 | 1x1 |  | 3 |
| Refurb Processing Module | Topaz | rare | 2 | 1x1 |  | 3 |
| Refurb Security Module | Amethyst | rare | 2 | 1x1 |  | 3 |
| Rotten Die | Corrupted Crystal | epic | 7 | 1x1 |  | 6 |
| Salvaged Efficiency Module | Emerald | common | 1 | 1x1 |  | 3 |
| Salvaged Memory Module | Sapphire | common | 1 | 1x1 |  | 3 |
| Salvaged Performance Module | Ruby | common | 1 | 1x1 |  | 3 |
| Salvaged Processing Module | Topaz | common | 1 | 1x1 |  | 3 |
| Salvaged Security Module | Amethyst | common | 1 | 1x1 |  | 3 |
| Stock Efficiency Module | Emerald | epic | 4 | 1x1 |  | 3 |
| Stock Memory Module | Sapphire | epic | 4 | 1x1 |  | 3 |
| Stock Performance Module | Ruby | epic | 4 | 1x1 |  | 3 |
| Stock Processing Module | Topaz | epic | 4 | 1x1 |  | 3 |
| Stock Security Module | Amethyst | epic | 4 | 1x1 |  | 3 |
| Stray Voltage | Wisp | godly | 8 | 1x1 |  | 6 |

## Patches (potions) (6)

| Item | From | Rarity | Cost | Map | Sockets | Unbuilt |
|---|---|---|---:|---|---:|---:|
| Capacitor Flask | Lightning in a Bottle | unique | 7 | 3x6 | 1 | 2 |
| Drain Vial | Vampiric Potion | legendary | 8 | 1x3 |  | 2 |
| Hardening Serum | Stone Skin Potion | epic | 6 | 1x3 |  | 2 |
| Payload Vial | Pestilence Flask | epic | 7 | 1x3 |  | 2 |
| Read-Only Mode | Strong Stone Skin Potion | legendary | 9 | 1x3 |  | 2 |
| Swap Shot | Mana Potion | epic | 6 | 1x3 |  | 2 |

## Containers (bags) (4)

| Item | From | Rarity | Cost | Map | Sockets | Unbuilt |
|---|---|---|---:|---|---:|---:|
| Bandolier | Potion Belt | legendary | 5 | 1x4 |  | 2 |
| Loot Box | Sack of Surprises | unique | 10 | 2x2 |  | 1 |
| Motherboard | Vineweave Basket | unique | 20 | 3x3 |  | 1 |
| The Cloud | Box of Prosperity | epic | 5 | 2x2 |  | 1 |

**From** is the Backpack Battles item each one's numbers come from.

## What is left

211 effect lines to build, each held in its item's `unbuilt`. A weapon's timer
is already built, so its line is the extra on top; every other item does nothing
at all until its line is built.

Every item in the table has a map that says exactly what its source's says. The
one that could not -- Cog Badge, whose charge travels an ordered route a map
cannot record -- is one of the six set aside.

