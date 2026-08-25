# Turning things: what the code does now, and where it should go

A review of every place a rotation is worked out, why rotation keeps coming
back as a bug, and what to change. Written after the fourth rotation fix in as
many weeks.

## The short version

The maths is not the problem. `_turn` is one function on each side, it has
been right since the direction was settled, and the two sides are locked
together by a shared fixture. No file outside `grid_system.py` and
`api_types.gd` works out a rotation of its own.

The problem is that **a turn re-derives the origin**, and everything expressed
relative to that origin has to be re-derived with it — the aura, the square in
your hand, the items riding on a container. Each time that has come up it has
been solved again, locally, by a new function. That is the duct tape.

There is one operation underneath all of them:

> Turn a body, and carry everything expressed relative to that body with it.

The server already implements it *within one item*. The client implements it
twice, in two functions that do not know they are the same. Nothing implements
it *between* items, which is why a container cannot turn.

## What exists today

### Server: two functions, one of them doing the real work

| Where | What it does |
|---|---|
| `grid_system._turn(square, rotation)` | one square, a quarter turn clockwise |
| `grid_system.ItemShape.rotate(rotation)` | the whole body: footprint, star, diamond and anchors, turned together, all settled against the **footprint's** corner, anchors projected upward afterwards |

Everything else goes through those: `items.PlacedItem._turned`,
`covered_squares`, `zone_squares`, and the battle engine's own shape lookups.

`ItemShape.rotate` is the good design in this codebase. It treats the item and
its auras as **one rigid body about one origin**, which is the model this
document argues for everywhere else.

### Client: the same maths, split, with the coupling passed by hand

| Where | What it does |
|---|---|
| `APITypes._spin` | one square, no settling |
| `APITypes._corner` | the top left of a set of squares |
| `APITypes.turn(shape, rotation)` | the footprint |
| `APITypes.turn_zone(shape, zone, anchors, rotation)` | **one** zone — re-deriving the footprint's corner on every call |
| `APITypes.turn_within(shape, rotation, square)` | where one square of a body ends up |
| `InventoryGrid.carried_corner` / `square_for_corner` | where a carried item is drawn, and which square that is — exact inverses of `grid_to_pixel` |
| `APITypes.turned_by(rotation, quarters)` | the facing arithmetic |

The invariant the server enforces by construction — *these lists share one
origin* — the client enforces by **passing the shape into every call**. It
works, and every current caller gets it right, but nothing stops a sixth list
being added and turned against its own corner. That is a failure mode the
server does not have.

### `Item` and `PlacedItem`

`Item` answers `turned_shape()` with the untouched shape and `facing()` with 0;
`PlacedItem` overrides both. That is a good touch: nothing asking has to know
which kind it holds. The cost is that "not on the grid" and "facing 0" are the
same state, which is why `Item.turned()` has to return a `PlacedItem` at the
origin.

## Why it keeps breaking

Eleven commits mention rotation. Sorting them by cause:

**1. The two sides disagreeing.** *Solved, structurally.* `_turn` returned
`(y, -x)` — anticlockwise on a y-down grid — while Godot rotated the artwork
the other way, so a spear pointed one way and its aura reached the other.
`server/tests/fixtures/turned_shapes.json` now pins what the server makes of
five shapes at four rotations, and both languages read it. Keep this.

**2. Representations drifting apart.** *"Turn an item in one place instead of
three." "Turn an item's artwork with the item."* The same fact lives in several
places and they are kept in step by hand.

**3. Origin confusion.** *The recurring one.* A turn settles the body against a
new corner, so anything relative to the body moves too. This is what produced
the aura pointing the wrong way, the mark sitting a spear's length from the
spear, and the reason a container "cannot" turn.

Cause 3 is the model problem. Cause 2 is what makes it expensive to fix.

## The drift, concretely

The same fact is stored in five places on the client:

| Where | Holds |
|---|---|
| `visual.set_meta("item_data")` | the `PlacedItem` — position and facing |
| `visual.item_data` | the visual's own copy, refreshed only by `redraw_as` |
| `visual.set_meta("grid_pos")` | the position, again |
| `inventory_grid.item_grid[y][x]` | occupancy, derived from the turned shape |
| `texture_rect.rotation_degrees` | the artwork's angle |

`inventory_grid._place_item_at` calls `redraw_as` **only when the facing
changed**. Move an item without turning it and `visual.item_data` keeps the old
position while the meta holds the new one.

Today nothing reads a position off the visual's copy — only appearance fields
and `cooldown` — so this is a hazard rather than a live bug. It is exactly the
shape of the bugs that keep landing.

## The model to adopt

One body, one origin, one operation:

> **Turn a body. Everything expressed relative to it turns with it, and is
> re-derived against the new origin — never carried.**

Three things are "expressed relative to a body" and all three already exist:

- **the aura** — `star` and `diamond`, turned with the footprint
- **the square in your hand** — `grab_cell`, turned by `turn_within`. Only a
  drag off the grid has one; everything else hangs from the middle of its
  picture, see 2b below
- **the passengers** — items on a container, not yet built

The one exception is the `^` anchor, which points **up in world space** however
the body is turned. Both sides already handle it the same way: leave it out of
the turn, then project it afterwards. That rule is correct and should survive
unchanged.

### On "containers all the way down"

The instinct is right: a tray and its passengers are one rigid body, exactly as
an item and its aura are. Rotating a container is not a new kind of problem.

Checked exhaustively — 10 containers × 222 item shapes × every placement ×
every turn, **59,982 cases**:

- carrying an item round rigidly and turning the item **always agree** (0
  disagreements)
- an item wholly on a tray **can never fall off it** when the tray turns (0
  cases), because rotation maps the tray's squares onto themselves

So the hard case people expect — items falling off — does not exist. What
remains is items **straddling two containers**, which `can_hold` permits today,
and collisions with items outside the tray. Both go to the chest, which is what
a container *move* already does.

What I would **not** do is make this a runtime tree of container nodes. The
nesting is only ever two deep — grid, container, item — and there is no third
level in the design. Adopt the model, not the object graph.

## Path forward

Ordered so each step is worth doing on its own.

### 1. One turned body, not several turned lists — client

Give the client what `ItemShape.rotate` already is: a value that turns
footprint, star, diamond and anchors **in one call against one corner**.
`turn_zone` stops taking the shape as an argument, because it can no longer be
called without the body it belongs to.

Removes the "sixth list turned against its own corner" failure mode by
construction, and makes the two sides mirror each other.

*About a day, including tests. No behaviour change — the fixture lock proves
it.*

### 2. One place a visual's facts live — client

Drop `grid_pos` and the visual's private `item_data`; read both off the single
`PlacedItem`. Redraw on every change rather than only on a facing change.

This is the one that kills the drift class, and it is the prerequisite for
anything harder.

*Half a day.*

### 2b. Carried things hang from their own picture — *done*

There were two rules for where a carried item sits, and they disagreed.

An item dragged off the grid is held by **the square the pointer went down
on**. That is right, and `turn_within` carries it correctly through a turn —
checked against every irregular shape in the catalogue, every square, every
turn.

An item off the shelf, out of the chest, or in hand had nobody choose a square,
so it was held by its **middle square**. That was a bandage for a real bug (the
mark sat a spear's length from the spear) and it introduced a smaller one: the
artwork is centred on its bounding box, and for any shape whose box is an even
number of squares across, the box centre is not a square centre. The picture
therefore sat off the pointer — by half a cell for most, a **whole cell** for
Credential Harvester — and turning one swung the picture about a point that was
not under the hand.

**129 of the 222 items were affected**, not only the irregular ones.

The rule now is the simpler one, and there is only one of it:

> A carried item hangs from **the middle of its own artwork**, and the mark is
> worked out from **where that artwork is** — `square_for_corner(carried_corner(...))`,
> the exact inverse of `grid_to_pixel`.

The mark cannot disagree with the picture, because it is derived from it.
`middle_square` and `held_by_offset` are gone, and with them the idea that a
carried item is "held by a square" when nobody picked one.

### 3. Name the rigid-body operation once

`turn_within` is already this function, but it is currently documented as
"where a grab square goes". Reframe it as *where something expressed relative
to this body ends up when the body turns*, and use it for all three cases: the
grab square, the aura, and the passengers.

*An afternoon. Mostly naming, tests and documentation.*

### 4. Containers rotate, in three steps

- **Off the shelf.** The client already turns a carried container, previews it
  turned and sends the facing. The server's purchase branch drops it. **One
  line.** This is where the pinch is: five of the ten containers are
  non-square, and a 1×4 Patch Registry can only be bought upright today.
- **On the board, empty.** Turn the tray and the mark. Refuse it while it has
  passengers.
- **With passengers.** Map each rider through step 3's operation, displace what
  no longer fits down the path a move already uses.

*Step one is trivial. Steps two and three are about a day together, and only
worth doing after step 2 above.*

## What to keep

- `turned_shapes.json` and the two-sided lock. It is the reason cause 1 is dead.
- `ItemShape.rotate` as the reference design.
- The anchor rule: turn with the body, project upward afterwards.
- The displacement path in `inventory_manager.move_container`.
