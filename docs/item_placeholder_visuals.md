# Item Placeholder Visuals

**Status:** agreed design. The catalogue data is in, and so is the drawing of
the fill and the outline. The patterns and the icons are not.

Only 9 of the 86 items have artwork. Every other item draws as the same blue
square, so the grid tells the player nothing. This document specifies what an
item without artwork looks like instead.

**This applies only when an item has no artwork.** `ItemVisual` looks for
`res://assets/items/<slug>.png` first. When it finds one, none of this is drawn.
Every item will get artwork in the end. This is what the player sees until then.

This is presentation only. It changes no mechanic, so the Game Design Document
does not move. It does add two fields to the item catalogue; see
[section 5](#5-where-the-data-lives).

---

## 1. Three channels

A placeholder carries three separate pieces of information. Each one uses its
own channel, so none of them compete:

| Channel | Tells the player | Comes from |
|---|---|---|
| Fill colour | which category this is | the item's `color` field, a `#RRGGBB` value |
| Pattern | which item this is | the item's `pattern` field, a name |
| Icon | which category this is | the item's `category` field |

A fourth mark, the outline, groups the cells of one item together. It carries no
information of its own. See [section 4](#4-the-outline).

Rarity is not one of the channels. The tooltip already shows it, and an outline
that showed rarity would only appear on the items without artwork, which is
worse than not showing it at all.

Note on spelling: the code and the JSON use `color`, to match Godot's own
`Color` and the existing `bg_color` and `item_color`. The prose says colour.

---

## 2. Colour by category

**Every item in a category shares one colour.** The pattern is what separates
one item from another inside that category. This makes colour say something —
red is a problem, blue is a defense — and it reinforces the icon.

| Category | Colour | Hex | Items |
|---|---|---|---|
| `problem` | `red` | `#BE0032` | 19 |
| `module` | `orange` | `#F38400` | 14 |
| `protocol` | `green` | `#008856` | 14 |
| `consumable` | `pink` | `#E68FAC` | 10 |
| `script` | `lime` | `#8DB600` | 7 |
| `defense` | `blue` | `#0067A5` | 6 |
| `infrastructure` | `violet` | `#604E97` | 6 |
| `patch` | `yellow` | `#F3C300` | 6 |
| `monitor` | `sky` | `#A1CAF1` | 4 |

**This fits, but only just.** The largest category holds 19 items and there are
20 patterns. When a category outgrows the patterns, do not repeat a pair. Take
an unused colour from the palette below and give it to the extra items. The
uniqueness test will tell you the moment this happens.

### The palette

Sixteen colours, from Kelly's 22 colours of maximum contrast (1965). White,
black, and the four darkest entries are dropped, because the UI background is
already dark. Nine are in use; the other seven are headroom.

| Name | Hex | Kelly's name | In use |
|---|---|---|---|
| `red` | `#BE0032` | vivid red | yes |
| `orange` | `#F38400` | vivid orange | yes |
| `yellow` | `#F3C300` | vivid yellow | yes |
| `lime` | `#8DB600` | vivid yellowish green | yes |
| `green` | `#008856` | vivid green | yes |
| `sky` | `#A1CAF1` | very light blue | yes |
| `blue` | `#0067A5` | strong blue | yes |
| `violet` | `#604E97` | strong violet | yes |
| `pink` | `#E68FAC` | strong purplish pink | yes |
| `amber` | `#F6A600` | vivid orange yellow | no |
| `ember` | `#E25822` | vivid reddish orange | no |
| `citron` | `#DCD300` | vivid greenish yellow | no |
| `salmon` | `#F99379` | strong yellowish pink | no |
| `magenta` | `#B3446C` | strong purplish red | no |
| `purple` | `#875692` | strong purple | no |
| `sand` | `#C2B280` | grayish yellow | no |

Sixteen is near the limit of what a person can tell apart by hue alone. Do not
add a seventeenth. If you need more combinations, add patterns.

`sand` is the weakest of the sixteen against a dark background, which is one
reason it is not in use. Look at the palette in the real UI before you promote
any of the seven spares.

---

## 3. The patterns

Twenty patterns, built from seven motifs and their variations. Each motif is one
small draw routine; the variations are parameters to it.

**The order matters.** A category with four items uses only the first four
patterns, so the list runs from the most distinct to the least.

| # | Name | Motif |
|---|---|---|
| 1 | `solid` | none |
| 2 | `stripe_d_bold` | diagonal `\` stripes, wide |
| 3 | `dot_large_grid` | large dots, square layout |
| 4 | `stripe_v_bold` | vertical stripes, wide |
| 5 | `check_large` | large chequers |
| 6 | `stripe_h_bold` | horizontal stripes, wide |
| 7 | `hatch_diag` | diagonal cross-hatch |
| 8 | `dot_small_stagger` | small dots, staggered layout |
| 9 | `chevron_up` | chevrons pointing up |
| 10 | `stripe_a_bold` | diagonal `/` stripes, wide |
| 11 | `rings` | concentric rings |
| 12 | `stripe_v_fine` | vertical stripes, narrow |
| 13 | `dot_large_stagger` | large dots, staggered layout |
| 14 | `check_small` | small chequers |
| 15 | `stripe_h_fine` | horizontal stripes, narrow |
| 16 | `hatch_ortho` | orthogonal cross-hatch |
| 17 | `chevron_right` | chevrons pointing right |
| 18 | `stripe_d_fine` | diagonal `\` stripes, narrow |
| 19 | `dot_small_grid` | small dots, square layout |
| 20 | `stripe_a_fine` | diagonal `/` stripes, narrow |

**Draw every pattern in one fixed dark ink at 30% alpha, not in a second
colour.** Then an item is "orange", not "orange and black", and the colour
channel stays clean whatever the fill.

**Every measurement is a fraction of the cell size**, so a 45 px grid cell and a
60 px shop cell show the same pattern at the same relative scale:

| Feature | Size |
|---|---|
| Fine stripe width and gap | cell / 9 |
| Bold stripe width and gap | cell / 4.5 |
| Small dot radius | cell / 12 |
| Large dot radius | cell / 7 |
| Dot spacing | cell / 3 |
| Small chequer | cell / 3 |
| Large chequer | cell / 2 |
| Ring spacing | cell / 6 |

The pattern runs across the whole item, not per cell. It does not restart at a
cell edge. See [section 7](#7-how-the-drawing-works).

---

## 4. The outline

One outline traces the edge of the whole item, not a box around each cell. It is
the mark that says "these cells are one thing".

- **Colour:** the item's own fill colour, darkened. It adds no new information,
  so it must not add a new colour.
- **Width:** 3 px.
- **Position:** wholly inside the shape. `ItemVisual` sets `clip_contents = true`
  and sizes itself to the bounding box, so an outline that straddled the edge
  would lose its outer half.

**Items with artwork get no outline.** The artwork is distinct enough on its own,
and the outline is a stopgap for the placeholders only.

---

## 5. Where the data lives

`color` and `pattern` are **required fields on each item in
`server/data/items/*.json`**. They travel through `ItemSpec`, `items.Item` and
the API to `api_types.gd`, next to `rarity` and `slug`.

`server/item_looks.py` declares which names are legal: the palette, the pattern
list, and which colour belongs to which category. `server/tests/test_item_looks.py`
holds the whole catalogue against it.

The catalogue owns the data, not the client, for one reason: a required field
makes a missing look a load failure. Nobody can add an item without a look, and
the uniqueness test has the whole catalogue in one place to check.

**The catalogue names a colour. The client is sent the value.** `Item.of` calls
`hex_of()`, so `"red"` in the JSON leaves the server as `"#BE0032"`. The client
therefore keeps no palette of its own, and a colour can be retuned by changing
one line in `item_looks.py` — no new client build.

**The pattern stays a name**, because the client draws it and cannot be sent a
motif as a value. So the client does know the twenty pattern names. That half of
the seam cannot be closed, but it matters less: a new pattern needs a new draw
routine, which is a client change anyway.

**The icons need nothing from the server.** The item already carries `category`,
and the client keys the icon file off it.

Containers have no `color` and no `pattern`. See [section 9](#9-containers).

---

## 6. The icons

One icon per category:

| Category | Icon |
|---|---|
| `problem` | bug |
| `protocol` | plug |
| `module` | chip |
| `consumable` | coffee cup |
| `script` | terminal prompt |
| `infrastructure` | server rack |
| `patch` | bandage |
| `defense` | shield |
| `monitor` | gauge |

**The icon is knocked out of the pattern.** The pattern draws across the cell,
then the icon shape is drawn in the plain fill colour with no pattern ink over
it. The icon appears as a clean shape in the texture, and both channels stay at
full strength.

**Draw the icon on every cell of the item.** An item with an irregular shape has
no reliable middle, and a repeated icon still reads correctly when a container
edge or another item hides part of the item.

This makes two demands on the artwork:

1. **Each icon is a single-colour silhouette**, white on transparent. It is used
   as a mask, not as a picture. The existing files in
   `client/assets/sprites/items/` (`bug_icon.svg`, `shield_icon.svg`,
   `coffee.svg`, and the rest) are candidates, but only if their silhouette is
   solid. A multi-colour icon cannot be knocked out.
2. **The silhouette must read at 28 px.** That is the icon box inside a 45 px
   cell. Simple shapes only, no detail.

The dark edge around the knocked-out icon needs no second asset. Draw the same
silhouette in the dark ink at four ±1 px offsets, then draw it once at true
position in the fill colour. The offsets show as a 1 px edge.

An unknown category draws no icon and logs a warning. It must not stop the grid
from drawing.

---

## 7. How the drawing works

`client/scripts/item_placeholder.gd` draws the whole item in one control with a
`_draw()` function. `ItemVisual` adds one of them per item, and no other node.

The input is the set of covered cells. Draw in this order:

1. **Fill and outline.** See below. *(done)*
2. **Pattern.** Across the bounding box, in the dark ink at 30% alpha, clipped
   to the covered cells. Clipping is what makes the pattern continuous across
   the item rather than restarting in each cell.
3. **Icons.** Per cell: the silhouette in dark ink at four ±1 px offsets, then
   the silhouette in the plain fill colour.

**One rule decides the outline.** A side of a cell is on the item's edge when
the square beyond it is not part of the item. That covers a rectangle, an L, a
T, and a shape with a hole, with no special cases — the hole gets an outline for
the same reason the outside does.

**The outline is painted, not stroked.** Fill the whole covered area in the
outline colour, then paint it again in the fill colour, pulled in by 3 px on
every side that is on the edge. What is left showing is a band exactly on the
edge and nowhere else. Tracing the edge as lines gives the same answer but needs
the corners handled; this way they take care of themselves.

**The cells draw flush.** The grid leaves 1 px between its squares. Inside an
item that gap is closed, or the outline would have holes where two cells meet.
Only the gaps *inside* the item are closed, so the item still lines up with the
grid squares underneath it.

---

## 8. Shapes and rotation

The placeholder path already handles shapes that are not rectangles. It walks
the offset list, so an L, a T, or a shape with a hole draws correctly today.
Three related notes:

- **No item uses an irregular shape yet.** All 86 are `1x1` to `3x2`.
  `server/grid_system.py` has `L_shape`, `T_shape`, `banana` and `pizza_slice`
  ready, but no JSON file names them. `docs/item_grid_model.md` proposes to
  replace the `"2x2"` string with a text map. Nothing here blocks that proposal:
  the drawing code needs only a list of covered cells.
- **The client ignores rotation.** `PlacedItem.rotation` is parsed, but
  `covered_squares()` in `api_types.gd` does not turn the shape, and
  `ItemVisual` never reads it. The server does turn it. Nothing sets a rotation
  today, so nothing is broken now. But an outline around a turned L would be
  wrong, so `ItemVisual` must read the turned cells.
- **The artwork path is not shape-general.** It stretches one image into the
  bounding box, which puts artwork in empty cells of an L. That is a problem for
  the artwork pass, not for this work.

---

## 9. Containers

A container is the ground the items sit on. It keeps its quiet translucent fill
and gets its own outline. **No palette colour, no pattern, no icon.** If a
container took part in the palette, the grid would become too busy to read.

---

## 10. Tests

**Server** (`tests/test_item_looks.py` and `tests/test_items.py`, done):
- No two items share the same `color` and `pattern` pair. This is the guard that
  makes the "no collisions" promise hold as items are added.
- Every `color` and every `pattern` name is one the client knows.
- Every item's colour is the colour of its category.
- Every item has both fields, and no container has either.
- The colour reaches the client as a value and the pattern as a name, and both
  survive an item being placed on the grid and put back in the chest.

**Client** (`test/unit/test_item_placeholder.gd` and `test_item_visual.gd`):
- The rectangles are worked out without drawing, so they are checked directly
  rather than by looking at pixels. *(done)*
- The outline is right for a single cell, a wide item, an L with its concave
  corner, and a ring with a hole in the middle. *(done)*
- An item still lines up with the grid squares underneath it. *(done)*
- A container draws in its own see-through colour. *(done)*
- An item that arrives with no colour still draws, in a colour nobody could
  mistake for a real one. *(done)*
- A container draws with no pattern and no icon. *(not done)*
- An unknown category still draws. *(not done)*

---

## 11. Clean-up while in these files

- `_get_color_for_category()` in `client/scripts/unified_grid_ui.gd` is dead.
  Only `test_unified_grid_ui.gd` calls it, and it knows 4 of the 9 categories.
  Delete both. *(not done)*
- `_get_texture_path()` printed on every item drawn. *(done)*
