"""
Inventory management system for the autobattler game
Manages both the 9x7 grid with server containers and unlimited storage
"""

import uuid
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Set, Tuple, Union

from config_loader import config_loader
from containers import Container, starting_containers
from grid_system import Rotation
from item_effects import Recipe
from items import Item, PlacedItem
from utils import Position

# ============= COMBINING (GDD 5.3) =============

# What a recipe part says in front of a kind, to mean any item of it.
CLASS = "class:"


@dataclass(frozen=True)
class Pending:
    """A recipe the items in the rack are some or all of the way towards.

    `have` of `need` parts are there and touching. When they are equal this is
    a combination that will happen when the battle starts, and it comes from
    the same plan the combining itself uses, so what the player is shown and
    what happens cannot disagree. When they are not, it is the progress to show
    beside a part the player has just put down -- "Long Poll 2/3".

    Item ids, because the client is looking at those items.
    """

    makes: str
    have: int
    need: int
    ingredients: Tuple[str, ...]  # ids present that would be used up
    catalysts: Tuple[str, ...]  # ids present that are needed and kept
    missing: Tuple[str, ...]  # parts still wanted, a type or a class wildcard

    @property
    def complete(self) -> bool:
        return self.have == self.need


@dataclass(frozen=True)
class Combination:
    """One crafting that happened, for the client to show.

    The consumed items are gone from the grid by the time this is read, so they
    are carried whole rather than named. A name would not be enough to draw one,
    and with two of a kind on the rack it would not say which two were eaten.
    """

    made: str  # item type of the result
    made_id: str  # the new item's own id
    consumed: Tuple[PlacedItem, ...]  # used up, as they stood
    kept: Tuple[PlacedItem, ...]  # catalysts, still on the grid
    freed: Tuple[Position, ...]  # squares the ingredients were standing on
    position: Optional[Position]  # where the result landed, None if in the chest


def _craftable() -> List[tuple]:
    """(item type, spec) for everything with a recipe, containers included.

    Read fresh rather than cached: a test that patches the catalogue expects
    the change to be seen.
    """
    return [
        (item_type, spec)
        for source in (config_loader.items, config_loader.containers)
        for item_type, spec in source.items()
        if spec.recipe
    ]


def any_of(part: str) -> List[str]:
    """Every item type that can be this part of a recipe.

    A named part is the one item. A `class:` part is a wildcard over the kinds
    an item's icon declares (GDD 5.4): `class:fire` is any item that is on
    fire, which is how Hot Cell asks to be lit by whatever fire the player
    happens to have rather than by one named lighter. Nothing at all for a part
    the catalogue cannot answer, which is a recipe nobody could complete.
    """
    if part.startswith(CLASS):
        kind = part[len(CLASS) :]
        return sorted(
            slug for slug, spec in config_loader.items.items() if kind in spec.kinds
        )
    return [part] if part in config_loader.items else []


def _answers(part: str, item_type: str) -> bool:
    """Whether an item of this type can stand for that part of a recipe."""
    if part.startswith(CLASS):
        spec = config_loader.items.get(item_type)
        return spec is not None and part[len(CLASS) :] in spec.kinds
    return part == item_type


def combining_partners() -> Dict[str, List[str]]:
    """For each item type, the types it appears in a recipe with.

    A fact about the catalogue, the same for every player and every rack, so it
    is sent once and answered on the client. That matters: it is wanted on hover
    and while dragging, and asking the server per mouse move would be absurd.

    It needs none of the rules about what actually combines -- no touching, no
    counting, no deciding between two recipes that want the same item. It only
    says these two go together, which is why the client may safely answer it.
    A type pairs with itself where a recipe wants two of it.

    A wildcard part is every item that answers it, so a Lump of Coal draws a
    line to all eight items that are on fire. Two of those eight draw no line
    to each other: they answer the same one part, and one part takes one item.
    A part nothing answers pairs with nobody, rather than promise a combination
    that can never happen.
    """
    partners: Dict[str, Set[str]] = {}
    for spec in list(config_loader.items.values()) + list(
        config_loader.containers.values()
    ):
        for recipe in spec.recipe:
            options = [any_of(part) for part in recipe.parts()]
            for n, mine in enumerate(options):
                for m, theirs in enumerate(options):
                    if n != m and theirs:
                        for one in mine:
                            partners.setdefault(one, set()).update(theirs)
    return {slug: sorted(others) for slug, others in sorted(partners.items())}


def _pair_up(parts: Sequence[str], pool: Sequence[PlacedItem]) -> Dict[int, PlacedItem]:
    """One item for each part, as many parts as the items can answer.

    Handing each part the first item that fits it would go wrong, because one
    item can answer two parts: a Hot Cell is a Hot Cell and it is also on fire.
    So a part that finds every item it could use already taken asks those parts
    to move over, and they move if anything else fits them.
    """
    taken: Dict[int, int] = {}  # index in pool -> index in parts

    def seat(part: int, tried: Set[int]) -> bool:
        for n, item in enumerate(pool):
            if n in tried or not _answers(parts[part], item.item_type):
                continue
            tried.add(n)
            if n not in taken or seat(taken[n], tried):
                taken[n] = part
                return True
        return False

    for part in range(len(parts)):
        seat(part, set())
    return {part: pool[n] for n, part in taken.items()}


class InvalidPlacementError(Exception):
    """Raised when an item cannot be placed at the specified location"""

    pass


class ItemNotFoundError(Exception):
    """Raised when an item cannot be found"""

    pass


class InventoryGrid:
    """
    Manages the 9x7 grid with server containers
    Items can only be placed on server containers
    """

    def __init__(self):
        """Initialize the grid with the starting server containers"""
        self.width = 9
        self.height = 7
        self.items: List[PlacedItem] = []
        self.containers: List[Container] = starting_containers()

    def _container_squares(self) -> Set[Position]:
        """Every grid square covered by a container"""
        return {
            square
            for container in self.containers
            for square in container.covered_squares()
        }

    def can_hold(self, squares: Sequence[Position]) -> bool:
        """
        Whether the grid can hold something covering these squares.

        This takes the squares rather than a shape and a position, because a
        turned item covers different squares from the ones its shape lists.
        Asking with a shape is how a rotation gets lost.
        """
        covered = self._container_squares()

        for x, y in squares:
            # Check bounds
            if x < 0 or x >= self.width or y < 0 or y >= self.height:
                return False

            # Items sit on containers, never on bare grid
            if (x, y) not in covered:
                return False

        return True

    def get_item_at(self, position: Position) -> Optional[PlacedItem]:
        """Get the item covering a specific square"""
        for item in self.items:
            if position in item.covered_squares():
                return item
        return None

    def place_item(
        self,
        item: Item,
        position: Position,
        rotation: Optional[Rotation] = None,
    ) -> None:
        """Place an item on the grid, facing the way it is asked to.

        Told nothing, it keeps facing the way it already does, so a move that
        is only a move does not quietly straighten an item out.
        """
        if rotation is None:
            rotation = getattr(item, "rotation", Rotation.NONE)
        placed = item.placed_at(position, rotation)

        # The whole item, as it is turned, has to sit on containers
        if not self.can_hold(placed.covered_squares()):
            raise InvalidPlacementError(
                f"Item at position {position} does not fit entirely on server containers"
            )

        # And it cannot land on another item
        for square in placed.covered_squares():
            existing_item = self.get_item_at(square)
            if existing_item is not None:
                raise InvalidPlacementError(
                    f"Position {square} is already occupied by item {existing_item.id}"
                )

        self.items.append(placed)

    def remove_item_at(self, position: Position) -> PlacedItem:
        """Remove and return the item at a position"""
        item = self.get_item_at(position)
        if item is None:
            raise ItemNotFoundError(f"No item at position {position}")

        self.items.remove(item)
        return item

    def touching(self, item: PlacedItem) -> List[PlacedItem]:
        """The items whose squares touch this one's, edge to edge.

        Corners do not count, and an item never touches itself. GDD 4.3 used to
        make adjacency a battle mechanic; it is not one, and this is only about
        which items are together in the rack.
        """
        mine = set(item.covered_squares())
        around = {
            (x + dx, y + dy)
            for x, y in mine
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
        } - mine
        return [
            other
            for other in self.items
            if other.id != item.id and around & set(other.covered_squares())
        ]

    def _fill(
        self, recipe: Recipe, hub: PlacedItem, available: Sequence[PlacedItem]
    ) -> Dict[int, PlacedItem]:
        """Which part of `recipe` each item around `hub` answers.

        Keyed by where the part sits in `recipe.parts()`, so an item's place
        says whether it is an ingredient or a catalyst. Every part is answered
        by an item touching `hub` -- but the items need not touch each other,
        or a Stone Golem could never be made: four stones cannot all touch one
        another, though all four can touch the heart between them.

        As many parts as the items can answer: all of them when the rack is
        about to combine, fewer while the player is still collecting. Nothing
        at all when the hub answers no part of the recipe.
        """
        here = {item.id for item in available}
        around = [item for item in self.touching(hub) if item.id in here]
        parts = recipe.parts()

        best: Dict[int, PlacedItem] = {}
        for n, part in enumerate(parts):
            if not _answers(part, hub.item_type):
                continue
            # The hub is put on this part first, so a recipe wanting two of its
            # type does not fill both from the neighbours and leave the hub out
            # of its own match.
            rest = _pair_up([p for m, p in enumerate(parts) if m != n], around)
            got = {n: hub}
            got.update({m if m < n else m + 1: item for m, item in rest.items()})
            if len(got) > len(best):
                best = got
        return best

    def _candidates(self, available: Sequence[PlacedItem]) -> List[tuple]:
        """Every combination the rack could make right now.

        Each is (newest, made, recipe, items). `newest` is how far down
        self.items the newest of its items sits, and that list is in the order
        things were placed, so a bigger number means placed later. The items
        come in the order of the recipe's parts, which is what says which of
        them are eaten.
        """
        order = {item.id: n for n, item in enumerate(self.items)}
        found = []
        for made, spec in _craftable():
            for recipe in spec.recipe:
                for hub in available:
                    got = self._fill(recipe, hub, available)
                    if len(got) < len(recipe.parts()):
                        continue
                    items = [got[n] for n in sorted(got)]
                    newest = max(order[item.id] for item in items)
                    found.append((newest, made, recipe, items))
        return found

    def plan(self) -> List[tuple]:
        """What the rack would combine, as (made, recipe, items). Changes nothing.

        Ingredients are used up and catalysts are not, so a catalyst can serve
        more than one combination in the same pass. The result of a combination
        never goes on to make something else here: 20 items are both a recipe's
        result and another's ingredient, and a chain takes a round for each of
        its steps so the player sees them and can break it up.

        Telling the player what is about to happen and doing it read the same
        plan, so the two cannot promise different things.
        """
        available = list(self.items)
        planned = []

        while True:
            candidates = self._candidates(available)
            if not candidates:
                return planned

            # The newest item decides, because it is the one the player just
            # put there. Ties go to the earlier result name, so the same rack
            # always combines the same way.
            _, made, recipe, items = max(
                candidates, key=lambda c: (c[0], [-ord(ch) for ch in c[1]])
            )
            planned.append((made, recipe, items))

            eaten = {item.id for item in self._consumed(recipe, items)}
            available = [item for item in available if item.id not in eaten]

    def pending(self) -> List[Pending]:
        """Every recipe the rack is part or all of the way towards.

        The complete ones come from the plan, so they are exactly what will
        happen. The partial ones are what to label an item with when the player
        puts it down next to something it goes with.
        """
        complete = []
        spoken_for = set()
        for made, recipe, items in self.plan():
            eaten = {item.id for item in self._consumed(recipe, items)}
            spoken_for |= {item.id for item in items}
            complete.append(
                Pending(
                    makes=made,
                    have=len(items),
                    need=len(recipe.parts()),
                    ingredients=tuple(i.id for i in items if i.id in eaten),
                    catalysts=tuple(i.id for i in items if i.id not in eaten),
                    missing=(),
                )
            )
        return complete + self._partly_there(spoken_for)

    def _partly_there(self, spoken_for: Set[str]) -> List[Pending]:
        """Recipes some of the way there, for the progress an item is labelled
        with. Two or more parts have to be together: one item on its own is not
        progress towards anything, it is just an item.

        An item already in a complete combination is left out. It is going to
        combine, and offering the player a second thing it could have been
        instead would only be confusing.
        """
        best: Dict[tuple, Pending] = {}
        loose = [item for item in self.items if item.id not in spoken_for]
        for made, spec in _craftable():
            for recipe in spec.recipe:
                for hub in loose:
                    got = self._fill(recipe, hub, loose)
                    if len(got) < 2:
                        continue
                    parts = recipe.parts()
                    eaten = len(recipe.ingredients)
                    here = Pending(
                        makes=made,
                        have=len(got),
                        need=len(parts),
                        ingredients=tuple(
                            item.id for n, item in sorted(got.items()) if n < eaten
                        ),
                        catalysts=tuple(
                            item.id for n, item in sorted(got.items()) if n >= eaten
                        ),
                        missing=tuple(
                            sorted(part for n, part in enumerate(parts) if n not in got)
                        ),
                    )
                    key = (made, frozenset(item.id for item in got.values()))
                    if key not in best or best[key].have < here.have:
                        best[key] = here
        return sorted(best.values(), key=lambda p: (-p.have, p.makes))

    def combine(self) -> List[Combination]:
        """Carry out the plan. GDD 5.3."""
        return [self._apply(made, recipe, items) for made, recipe, items in self.plan()]

    @staticmethod
    def _consumed(recipe: Recipe, items: Sequence[PlacedItem]) -> List[PlacedItem]:
        """The items an ingredient claims. A catalyst is not one.

        `recipe.parts()` is the ingredients and then the catalysts, and a match
        comes back in that order, so where an item stands says which it is.
        """
        return list(items[: len(recipe.ingredients)])

    def _apply(
        self, made: str, recipe: Recipe, items: Sequence[PlacedItem]
    ) -> Combination:
        """Take the ingredients off the grid and put the result down."""
        eaten = self._consumed(recipe, items)
        freed = sorted({square for item in eaten for square in item.covered_squares()})
        eaten_ids = {item.id for item in eaten}
        kept = tuple(item for item in items if item.id not in eaten_ids)
        for item in eaten:
            self.items.remove(item)

        result = Item.of(made, str(uuid.uuid4())[:8])
        position = self._room_for(result, freed)
        if position is not None:
            self.place_item(result, position)
        return Combination(
            made=made,
            made_id=result.id,
            consumed=tuple(eaten),
            kept=kept,
            freed=tuple(freed),
            position=position,
        )

    def _room_for(self, item: Item, freed: Sequence[Position]) -> Optional[Position]:
        """Where the result can stand among the squares its ingredients left.

        Only those squares: a combination should not push into space the player
        was keeping for something else. Nowhere to stand means the chest, which
        the caller does.
        """
        room = set(freed)
        for position in sorted(room, key=lambda square: (square[1], square[0])):
            squares = item.placed_at(position).covered_squares()
            if set(squares) <= room and self.can_hold(squares):
                return position
        return None

    def get_battle_items(self) -> List[PlacedItem]:
        """Get all items formatted for battle"""
        return self.items.copy()

    def find_container(self, container_id: str) -> Optional[Container]:
        """The container with this id, if the grid holds one"""
        for container in self.containers:
            if container.id == container_id:
                return container
        return None

    @staticmethod
    def _carried_by(
        item: PlacedItem, was: Container, now: Container, quarters: int
    ) -> PlacedItem:
        """Where an item ends up when the rack under it moves and turns."""
        moved_by = (now.position[0] - was.position[0], now.position[1] - was.position[1])
        if quarters % 4 == 0:
            return item.placed_at(
                (item.position[0] + moved_by[0], item.position[1] + moved_by[1]),
                item.rotation,
            )

        # The rack as it stands now, which is the body the squares are
        # expressed against.
        turn = Rotation((quarters * 90) % 360)
        tray = was._turned()
        on_the_tray = [
            (x - was.position[0], y - was.position[1])
            for x, y in item.covered_squares()
        ]
        corner = tray.corner_of(on_the_tray, turn)
        anchor = (corner[0] + now.position[0], corner[1] + now.position[1])
        facing = Rotation((item.rotation.value + quarters * 90) % 360)
        return item.placed_at(anchor, facing)

    def move_container(
        self,
        container_id: str,
        position: Position,
        rotation: Optional[Rotation] = None,
    ) -> List[PlacedItem]:
        """Move a container, and everything resting on it, to a new anchor.

        Every item with a square on the container travels with it. An item that
        cannot stand where it lands is taken off the grid and returned, for the
        caller to put in storage; see docs/moving_containers.md.

        The container itself is all or nothing. If it would leave the grid or
        land on another container, nothing moves at all.
        """
        container = self.find_container(container_id)
        if container is None:
            raise ItemNotFoundError(f"No container with id {container_id}")

        facing = container.rotation if rotation is None else rotation
        quarters = (facing.value - container.rotation.value) // 90

        # model_copy rather than placed_at, which would hand back a PlacedItem
        # and quietly take the container out of the list of containers.
        moved = container.model_copy(
            update={"position": position, "rotation": facing}
        )

        others = [c for c in self.containers if c.id != container_id]
        self._check_container_fits(moved, others)

        # Everything with a square on the container comes with it. Not only
        # what sits wholly inside: half an item cannot stay behind.
        carried_squares = set(container.covered_squares())
        travellers = [
            item for item in self.items if carried_squares & set(item.covered_squares())
        ]
        stayed = [item for item in self.items if item not in travellers]

        self.containers = others + [moved]

        # Travellers keep their positions relative to each other, so they can
        # only collide with an item that stayed put.
        taken_squares = {square for item in stayed for square in item.covered_squares()}
        self.items = stayed
        displaced: List[PlacedItem] = []
        for item in travellers:
            shifted = self._carried_by(item, container, moved, quarters)
            squares = set(shifted.covered_squares())
            if self.can_hold(shifted.covered_squares()) and not (
                squares & taken_squares
            ):
                self.items.append(shifted)
                taken_squares |= squares
            else:
                displaced.append(shifted)

        return displaced

    def _check_container_fits(
        self, container: Container, others: Sequence[Container]
    ) -> None:
        """Whether a container may stand on these squares, or why it may not"""
        occupied = {square for other in others for square in other.covered_squares()}
        for x, y in container.covered_squares():
            if x < 0 or x >= self.width or y < 0 or y >= self.height:
                raise InvalidPlacementError(
                    f"A container at {container.position} would leave the grid"
                )
            if (x, y) in occupied:
                raise InvalidPlacementError(
                    f"A container at {container.position} would overlap another"
                )


class InventoryStorage:
    """
    Manages the unlimited storage area for unused items
    """

    def __init__(self):
        """Initialize empty storage"""
        self.items: List[Item] = []

    def add_item(self, item: Item) -> None:
        """Add an item to storage, taking it off the grid if it was on it"""
        self.items.append(item.stored() if isinstance(item, PlacedItem) else item)

    def remove_item(self, item_id: str) -> Item:
        """Remove and return an item by ID"""
        for item in self.items:
            if item.id == item_id:
                self.items.remove(item)
                return item
        raise ItemNotFoundError(f"Item with ID {item_id} not found in storage")

    def find_item(self, item_id: str) -> Optional[Item]:
        """Find an item by ID"""
        for item in self.items:
            if item.id == item_id:
                return item
        return None

    def get_all(self) -> List[Item]:
        """Get all items in storage"""
        return self.items.copy()


class InventoryManager:
    """
    High-level inventory management coordinating grid and storage
    """

    def __init__(self):
        """Initialize with grid and storage"""
        self.grid = InventoryGrid()
        self.storage = InventoryStorage()

    def place_item(
        self,
        item: Item,
        placement: Union[str, Position],
        rotation: Optional[Rotation] = None,
    ) -> bool:
        """
        Place an item either in storage or on the grid

        Args:
            item: The item to place
            placement: Either "storage" or (x, y) coordinates
            rotation: Which way it faces on the grid. Told nothing, it keeps
                facing the way it already does.

        Returns:
            True if successful
        """
        try:
            if placement == "storage":
                self.storage.add_item(item)
            else:
                # Placement is grid coordinates
                self.grid.place_item(item, placement, rotation)
            return True
        except InvalidPlacementError:
            return False

    def move_item(
        self,
        item_id: str,
        from_location: Union[str, Position],
        to_location: Union[str, Position],
        rotation: Optional[Rotation] = None,
    ) -> None:
        """
        Move an item between storage and grid

        Args:
            item_id: ID of the item to move
            from_location: Either "storage" or (x, y) coordinates
            to_location: Either "storage" or (x, y) coordinates

        Raises:
            ItemNotFoundError: If item not found at source location
            InvalidPlacementError: If destination is invalid
        """
        # Find and remove from source. By id rather than by asking the grid
        # what stands at from_location: callers pass the item's own anchor, and
        # an anchor is not necessarily one of the item's squares. Twelve items
        # in the catalogue are plus or L shapes whose first square is (1, 0),
        # so the grid answered "nothing there" about the very item being moved.
        if from_location == "storage":
            item = self.storage.remove_item(item_id)
        else:
            item = next((held for held in self.grid.items if held.id == item_id), None)
            if item is None:
                raise ItemNotFoundError(
                    f"Item {item_id} not found at position {from_location}"
                )
            self.grid.items.remove(item)

        # Place at destination
        try:
            if to_location == "storage":
                self.storage.add_item(item)
            else:
                self.grid.place_item(item, to_location, rotation)
        except Exception:
            # Whatever went wrong, the item goes back where it came from, and
            # the caller still hears about it.
            if from_location == "storage":
                self.storage.add_item(item)
            else:
                self.grid.place_item(item, from_location)
            raise

    def move_container(
        self,
        container_id: str,
        position: Position,
        rotation: Optional[Rotation] = None,
    ) -> List[Item]:
        """Move a container and everything resting on it.

        Returns the items that could not stand where they landed, which have
        been put in storage. The caller passes them on so that the client knows
        which items moved without it, rather than having to work that out by
        comparing two lists of storage.
        """
        displaced = self.grid.move_container(container_id, position, rotation)
        stored = [item.stored() for item in displaced]
        for item in stored:
            self.storage.add_item(item)
        return stored

    def get_battle_inventory(self) -> List[PlacedItem]:
        """Get only grid items for battle (storage items not used)"""
        return self.grid.get_battle_items()

    def remove_item(
        self, location: Optional[Position] = None, item_id: Optional[str] = None
    ) -> Optional[Item]:
        """
        Remove an item from either grid or storage

        Args:
            location: Grid position (if removing from grid)
            item_id: Item ID (if removing from storage)

        Returns:
            The removed item or None
        """
        try:
            if location is not None:
                # Remove from grid
                return self.grid.remove_item_at(location)
            elif item_id is not None:
                # Try storage first
                item = self.storage.find_item(item_id)
                if item:
                    return self.storage.remove_item(item_id)

                # Try grid. Removed by identity, not by asking the grid what
                # is at the item's own anchor: an item's anchor is not
                # necessarily one of its own squares. Twelve items in the
                # catalogue are plus or L shapes whose first square is (1, 0),
                # so looking them up at (x, y) found nothing and selling one
                # answered 500.
                for grid_item in self.grid.items:
                    if grid_item.id == item_id:
                        self.grid.items.remove(grid_item)
                        return grid_item

            return None
        except ItemNotFoundError:
            return None

    def pending(self) -> List[Pending]:
        """What the rack would combine if the battle started now."""
        return self.grid.pending()

    def combine(self) -> List[Combination]:
        """Combine what the rack can, and catch anything with nowhere to stand.

        The grid does the combining, because it owns the squares and the order
        things were placed in. It cannot own where a result goes when it does
        not fit, though: that is the chest, which is here.
        """
        done = self.grid.combine()
        for combination in done:
            if combination.position is None:
                # Rebuilt with the id already reported, so the client can match
                # the item it is told about to the one that turns up.
                self.storage.add_item(Item.of(combination.made, combination.made_id))
        return done

    def get_state(self) -> Dict:
        """The full inventory state, as typed items and containers"""
        return {
            "grid": self.grid.items.copy(),
            "storage": self.storage.items.copy(),
            "containers": self.grid.containers.copy(),
        }

    def restore_state(self, state: Dict) -> None:
        """Restore inventory from saved state

        Saved state has been through JSON, so the items arrive as plain data and
        the models turn them back into items here.
        """
        self.grid.items = [PlacedItem.model_validate(i) for i in state.get("grid", [])]
        self.storage.items = [Item.model_validate(i) for i in state.get("storage", [])]
        if "containers" in state:
            self.grid.containers = [
                Container.model_validate(c) for c in state["containers"]
            ]
