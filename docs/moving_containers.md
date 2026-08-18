# Moving a Container

**Status:** in progress. Every part is marked **done** or **to do** below.
When nothing is left to do, delete this file — what it describes will be in
the code and its tests.

| Part | State |
|---|---|
| 1. One endpoint, one rule | done |
| 2. Which items travel | done |
| 3. What makes a move fail | done |
| 4. The hand, instead of the chest | to do, and not soon |
| 5. Showing the chest | done |
| 6. Dragging a container in the client | done |
| 7. Rotation | to do, and not soon |

A container can be placed when it is bought and never moved again. That makes
the grid a layout you commit to on the first purchase of the round, which is
not the game. This describes moving one.

---

## 1. One endpoint, one rule — *done*

**`/move/item` moves a container too.** A container is a `PlacedItem`, so the
client should not have to pick an endpoint based on what kind of item it is
holding. Today that endpoint searches `inventory_storage` and `inventory_grid`
only, so a container's id gets a 404; it has to search `server_containers` as
well, and `MoveItemResponse` has to start returning containers.

The rule that covers both, without branching on `is_container`:

> **A move carries whatever rests on the thing moved.**

Nothing rests on an ordinary item, so for items this is exactly what happens
now. For a container it carries its contents.

**A container cannot be moved to storage.** It is the ground; there is nowhere
for it to go. That request is refused.

---

## 2. Which items travel — *done*

**Every item with at least one square on the container.** Not "every item
wholly inside it" — an item may straddle two containers, which is why
`get_containers_for_item` exists, and half of it cannot stay behind.

Each travelling item shifts by the same delta as the container. Their positions
relative to one another never change, which is why two travelling items can
never collide with each other.

**A stationary item cannot lose its footing.** Any item with a square on the
moving container travels, so an item that stays behind has every square on a
container that did not move. It can still be *landed on*, which section 3
covers.

---

## 3. What makes a move fail — *done*

Two different kinds of failure, with two different answers.

### The container itself — the whole move is refused

- Any square off the grid.
- Any square on another container.

Nothing changes and the request is a 400. There is no partial outcome: a
container half-moved is not a state the player asked for.

### A travelling item — that item is set down

Checked at its new position, against the layout as it will be:

- Every square must be on some container. Not necessarily the one it came
  with: an item hanging off the edge of the moving container lands cleanly if
  the squares it hangs over belong to a container that stayed put. That case
  succeeds and is worth keeping.
- No square may be shared with another item.

An item failing either check **goes to storage**, and the rest of the move
still stands. The traveller is the one that gives way, never the item that
stayed still, because the traveller is the one being moved.

Travelling items are checked in the order they are held, so the outcome is the
same every time.

---

## 4. What Backpack Battles does, and what we do instead — *to do*

Backpack Battles does not put a displaced item in the chest. It puts it in your
hand — attached to the cursor, waiting to be placed. With two displaced items,
one goes to the chest and the other goes to your hand.

**We put every displaced item in storage.** That is this version.

The difference is smaller than it looks, and the simple version does not block
the better one:

- The hand is a **client** idea. The server has nowhere to hold an item that is
  neither on the grid nor in the chest, and it should not grow one. Storage is
  where a displaced item lives.
- So the richer behaviour is the client, on receiving the move, noticing that
  exactly one item was displaced and picking it up off the chest into a drag,
  rather than the server behaving differently.
- The client can already tell which items were set down. The response carries
  the whole chest, every item id is a unique instance, and an item on the grid
  is never also in the chest, so whatever is in storage now and was not before
  is exactly what this move displaced.

**The response says what the world is, not what happened to it.** That is how
the rest of the API works — the grid, the chest and the containers all arrive
whole — and a list naming the displaced items would be the one place that
broke the pattern for something the client can already work out.

---

## 5. The chest has to be visible first — *done*

**Storage is not drawn.** `unified_grid_ui.gd` builds `storage_grid`, styles it
and marks its cells usable, and nothing ever puts an item in it.
`inventory_storage` arrives on every response and is parsed in `api_types.gd`
by both `GameSession` and `MoveItemResponse`; no UI script reads either one.

That makes this a prerequisite of the work above, not a job alongside it. A
displaced item goes to the chest, so until the chest is drawn, moving a
container makes items *disappear* — and the player has no way to tell a
displaced item from a lost one.

Two halves, and only the first is needed here:

- **Show what is in the chest.** Read `inventory_storage` and lay it out in
  `storage_grid`. Required.
- **Drag between the chest and the grid.** The endpoint takes
  `to_location: "storage"` already, so the server side exists. Not required
  for this, but the chest is not much use read-only.

---

## 6. Dragging a container — *done*

A container is dragged the way an item is, with three differences.

**It needs free squares, not usable ones.** An item asks whether a container
has made a square usable; a container asks whether a square is empty. The two
ask opposite questions of the same board, which is why `can_place_container`
exists beside `_can_place_item`.

**Its items travel with it on screen.** `_start_container_drag` collects every
item visual with a square on the container — the same rule the server uses —
and moves them with it.

**The board is redrawn from the answer, not from the drop.** The response
carries the grid, the chest and the containers, because the move can set an
item down in the chest. Assuming the drop succeeded would lose that.

`drop_container_at` takes the pointer rather than reading it, so where a
container lands can be tested without a mouse.

---

## 7. Rotation — *to do*

A container has a rotation and nothing sets it. Whatever eventually turns a
container has to turn its contents with it, and turning is not the same as
shifting: the items' positions rotate about the container's anchor as well.
This document is about position only. `covered_squares()` already applies a
rotation on both a container and an item, so the geometry is in place.

---

## 8. Tests

Done:

- A container moves to free ground and takes its items with it.
- An item that hangs over the edge of a moving container onto another
  container lands cleanly and is not displaced.
- An item with nothing under it after the move goes to storage.
- An item that would land on a stationary item goes to storage, and the
  stationary one does not move.
- A container that would leave the grid is refused, and nothing moves.
- A container that would overlap another container is refused, and nothing
  moves.
- A container cannot be sent to storage.
- Moving an ordinary item still behaves exactly as it did.
- A displaced item arrives in the chest.
- The square a displaced item leaves takes another item.
- The ground a container leaves stops being usable, and the ground it arrives
  on becomes usable.
- A travelling item is not left behind on the square it came from.

- The chest shows what the server says is in it. *(done)*
- A container can be dragged, and its items move with it on screen. *(done)*
- A container needs free squares, not squares another container has made
  usable, and is no obstacle to itself. *(done)*
- A container dropped where it cannot stand goes back, and so does everything
  standing on it. *(done)*

To do:

- Section 4, the displaced item going to the hand rather than the chest.
- Section 7, rotation.
