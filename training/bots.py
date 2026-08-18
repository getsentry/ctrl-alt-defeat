"""
The policies. Two of them, and the difference is the whole design.

  NaiveSpender   hand-written, deliberately bad, never trained. The floor of
                 the ladder, and the cold-start opponent.
  LinearBot      a learned policy. Its genome is a flat vector of floats and
                 it holds no opinion about the game; train.py supplies the
                 values from real battle outcomes.

There is no hand-tuned "good" bot, on purpose. A scoring function written by
hand encodes what its author believes wins, and goes stale the moment the game
is rebalanced -- which, in this repo, happens weekly. Rebalance, re-run
train.py, and LinearBot adapts with no code change.

Both act ONLY through the harness, which calls the real server handlers. A bot
cannot cheat here: if the server rejects a purchase, the bot does not get the
item, exactly as a player would not.

THE LADDER comes from training checkpoints rather than hand-written tiers.
Generation 0 is random and plays badly, the last generation plays as well as
this method can, and the generations between are the ladder -- all the same
code with different weights. Retraining recalibrates it automatically.
"""

from __future__ import annotations

import random

import evaluate
import placement

N_FEATURES = len(evaluate.FEATURE_NAMES)
N_LAYOUT = 4      # weights over layout_features
N_CONTROL = 3     # buy_threshold, reroll_threshold, reserve_frac
N_TAIL = N_LAYOUT + N_CONTROL
GENOME_SIZE = N_FEATURES + N_TAIL

MAX_REROLLS = 4   # a hard cap, so a bad genome cannot spin forever


def random_genome(rng: random.Random) -> list[float]:
    return [rng.gauss(0.0, 1.0) for _ in range(GENOME_SIZE)]


class NaiveSpender:
    """Buys a random affordable item and drops it in the first legal slot.
    Never rerolls, never sells, never rearranges.

    Not trained, and never will be. It exists to produce the messy, over-full
    rack a new player actually builds. Crucially it always SPENDS: an empty
    rack reads as a broken opponent on the post-battle screen, not as an easy
    one.
    """

    def __init__(self, buy_chance: float = 1.0, name: str = "naive"):
        self.buy_chance = buy_chance
        self.name = name

    def take_shop_turn(self, harness, who, session, rng):
        for _ in range(12):
            affordable = [e for e in session.current_shop
                          if e is not None and e.price <= session.gold]
            if not affordable or rng.random() > self.buy_chance:
                break

            entry = rng.choice(affordable)
            position = _any_legal_spot(session, entry)
            if position is None:
                break
            try:
                harness.purchase(who, entry.id, position)
                session = harness.session(who)
            except Exception:
                break
        return session


class LinearBot:
    """Scores every legal purchase with w . features and takes the best.

    Deliberately linear. It trains in minutes on one core and its weights are
    readable -- you can look at them and learn something about your own game,
    which a weight matrix will not give you. A network was measured against
    this and played no better, so the capacity is not the limit today.
    """

    name = "linear"

    def __init__(self, genome: list[float] | None = None, name: str = "linear",
                 anneal_steps: int = 0):
        self.genome = list(genome) if genome else [0.0] * GENOME_SIZE
        self.name = name
        # Compute budget, never trained. Zero by default, and that is a
        # MEASURED choice rather than an assumption: with auras not yet firing,
        # rearranging a rack changes its adjacency by ~0.09 and wins no extra
        # battles (45.8% head to head, inside the noise), while every annealing
        # step costs a real /move round trip. Re-measure when auras land -- see
        # README -- and raise this only if the comparison actually wins.
        self.anneal_steps = anneal_steps

    @property
    def buy_weights(self) -> list[float]:
        return self.genome[:N_FEATURES]

    @property
    def layout_weights(self) -> list[float]:
        return self.genome[-N_TAIL:-N_CONTROL]

    @property
    def buy_threshold(self) -> float:
        return self.genome[-3]

    @property
    def reroll_threshold(self) -> float:
        return self.genome[-2]

    @property
    def reserve_fraction(self) -> float:
        # Squashed to [0, 0.5] so the search can never discover "save
        # everything", which scores well early (the gold survives) and loses
        # every battle.
        raw = self.genome[-1]
        if raw >= 50:
            return 0.5
        if raw <= -50:
            return 0.0
        return 0.5 / (1.0 + pow(2.718281828, -raw))

    # ------------------------------------------------------------- scoring

    def score_layout(self, catalogue, session) -> float:
        features = evaluate.layout_features(catalogue, session.inventory_grid)
        return sum(w * f for w, f in zip(self.layout_weights, features))

    # ----------------------------------------------------------- the turn

    def take_shop_turn(self, harness, who, session, rng):
        catalogue = harness.catalogue
        rerolls = 0

        for _ in range(16):
            best = self.best_plan(catalogue, session)

            if best is None:
                # Nothing affordable can be made to fit. A reroll is the only
                # move left, and only if it leaves gold to buy what it turns up.
                if rerolls < MAX_REROLLS and session.gold >= 2:
                    session = _reroll(harness, who, session)
                    rerolls += 1
                    continue
                break

            score, entry, position, source, plan = best

            if score < self.reroll_threshold and rerolls < MAX_REROLLS \
                    and session.gold >= 2:
                session = _reroll(harness, who, session)
                rerolls += 1
                continue

            if score < self.buy_threshold:
                break

            try:
                # Order matters: clear the space before asking for it. Every
                # step goes through the server, so a rejected step aborts the
                # plan rather than letting the bot assume it worked.
                for victim in plan.get("sold", ()):
                    harness.sell(who, victim.id)
                for victim in plan.get("stashed", ()):
                    harness.move(who, victim.id, "storage")

                # Lift into storage FIRST, then place, then bring back. The
                # order is the whole trick: the grid has to be empty of these
                # items before the newcomer can take the space they were in.
                buffered = plan.get("buffered") or ()
                for item_id in buffered:
                    harness.move(who, item_id, "storage")

                if not buffered:
                    for item_id, target in (plan.get("moved") or {}).items():
                        harness.move(who, item_id, target)

                if plan.get("to_storage"):
                    harness.purchase(who, entry.id, to_storage=True)
                elif source == "storage":
                    harness.move(who, entry.id, position)
                else:
                    # Containers go through the same endpoint; the server
                    # routes on is_container itself (main.py:1057).
                    harness.purchase(who, entry.id, position)

                for item_id, target in (
                        (plan.get("moved") or {}).items() if buffered else ()):
                    harness.move(who, item_id, target)
                session = harness.session(who)
            except Exception:
                session = harness.session(who)
                break

        if self.anneal_steps:
            session = _anneal_through_server(
                harness, who, session, self, rng, self.anneal_steps)
        return session

    def _score(self, catalogue, session, entry, position, free, *,
               sold=(), moved=None, stashed=(), from_storage=False,
               is_container=False, to_storage=False):
        features = evaluate.plan_features(
            catalogue, session, entry, position, sold, free, moved,
            stashed, from_storage, is_container, to_storage)
        return sum(w * f for w, f in zip(self.buy_weights, features))

    def best_plan(self, catalogue, session):
        """The highest-scoring (buy, square, sell-set) available right now.

        Considers EVERY legal square, not the first that fits. That is what
        makes adjacency usable: two squares differ only in what they sit next
        to, so a bot that takes the first free square can never exploit a
        synergy even when one exists.

        When nothing fits, it considers selling one item to make room. Capped
        at a single sale, and at the cheapest few candidates, because the plan
        space is otherwise combinatorial and this runs inside every shop turn.
        """
        reserve = int(session.gold * self.reserve_fraction)
        budget = session.gold - reserve
        free = placement.free_tile_count(session)
        best = None

        def offer(score, entry, position, source, **plan):
            nonlocal best
            if best is None or score > best[0]:
                best = (score, entry, position, source, plan)

        # Two sources of items, weighed against each other. An item already in
        # storage is free, so "put back what I own" competes directly with
        # "buy something new" -- and it should, because after a sale or a
        # rebalance the parked item may now be the better rack.
        # BUYING SPACE competes with buying an item, scored by the same
        # weights. An earlier version skipped containers entirely, so no
        # trained bot ever grew past its three starting containers -- a whole
        # strategy removed by one line, which the bot could never rediscover.
        for entry in session.current_shop:
            if entry is None or not entry.is_container or entry.price > budget:
                continue
            for position in placement.container_positions(session, entry)[:MAX_POSITIONS]:
                offer(self._score(catalogue, session, entry, position, free,
                                  is_container=True),
                      entry, position, "container", is_container=True)

        candidates = [("shop", e) for e in session.current_shop
                      if e is not None and not e.is_container]
        # Storage is unlimited, so it can grow without bound over a run. Cap
        # what is reconsidered each turn or the plan space -- candidates x
        # squares x sale options -- grows until a single shop turn takes half a
        # second. Most valuable first, since a cheap parked item is parked for
        # a reason.
        candidates += [("storage", i) for i in
                       sorted(session.inventory_storage,
                              key=lambda i: -getattr(i, "cost", 0))[:STORAGE_CANDIDATES]]

        # Anything owned can be sold for gold alone -- ON THE GRID as well as
        # in storage.
        #
        # Restricting this to storage was a real hole. Selling a placed item
        # was then only ever considered when the bot needed its SPACE, never
        # when it needed its MONEY, so "this weak item is worth less than what
        # its gold would buy" was not a thought the bot could have. The
        # measured symptom was a trained bot that sold literally zero times per
        # run -- which looks like a strategy and is actually a missing option.
        cash_sales = sorted(
            list(session.inventory_storage) + list(session.inventory_grid),
            key=lambda i: getattr(i, "sell_value", 0))[:SALE_CANDIDATES]

        for source, entry in candidates:
            from_storage = source == "storage"
            price = 0 if from_storage else entry.price
            spots = placement.legal_positions(session, entry)[:MAX_POSITIONS]

            # Buy it and park it, without placing it at all. The one purchase
            # that needs no square, so it is available when the rack is full
            # and nothing is worth selling -- take the good item now, find room
            # for it later. Storage is unlimited, so this is never blocked.
            if not from_storage and price <= budget and session.inventory_grid:
                offer(self._score(catalogue, session, entry, (0, 0), free,
                                  to_storage=True),
                      entry, None, "shop", to_storage=True)

            if spots:
                if price <= budget:
                    for position in spots:
                        offer(self._score(catalogue, session, entry, position,
                                          free, from_storage=from_storage),
                              entry, position, source, from_storage=from_storage)
                else:
                    # It fits but is unaffordable. Raising the gold from a
                    # stored item costs no grid space at all.
                    for victim in cash_sales:
                        if victim.id == entry.id or price > budget + victim.sell_value:
                            continue
                        for position in spots:
                            offer(self._score(catalogue, session, entry, position,
                                              free, sold=(victim,),
                                              from_storage=from_storage),
                                  entry, position, source, sold=(victim,),
                                  from_storage=from_storage)
                continue

            # No room. THREE ways to make some, and the bot must weigh all of
            # them. Give it only selling and it destroys items it will want
            # back; give it only the gaps and it buys nothing but small items.

            # 1. Shuffle something aside. Costs nothing at all, but needs slack
            #    somewhere -- impossible on a rack with zero free squares.
            if price <= budget:
                repack = placement.repack_for(session, entry)
                if repack:
                    (mover_id, mover_spot), (_, target) = repack
                    offer(self._score(catalogue, session, entry, target, free,
                                      moved={mover_id: mover_spot},
                                      from_storage=from_storage),
                          entry, target, source,
                          moved={mover_id: mover_spot}, from_storage=from_storage)

                # 1b. Lift items into storage, place the newcomer, put them
                #     back. This is the one that works on a FULL rack, where
                #     plain shuffling cannot move anything at all. Everything
                #     lifted returns to the grid, so nothing is given up --
                #     the rack simply ends up packed differently.
                via = placement.repack_via_storage(session, entry)
                if via:
                    lifted_ids, replacements, target = via
                    shuffle = {item_id: spot for item_id, spot in replacements}
                    offer(self._score(catalogue, session, entry, target, free,
                                      moved=shuffle, from_storage=from_storage),
                          entry, target, source,
                          buffered=lifted_ids, moved=shuffle,
                          from_storage=from_storage)

            for victim in _sale_candidates(session):
                openings = placement.legal_positions(
                    session, entry, skip=victim.id)[:MAX_POSITIONS]
                if not openings:
                    continue

                # 2. Park it in storage. Frees the squares, keeps the item,
                #    returns no gold. Storage is unlimited, so this is always
                #    available -- it is the option that was missing.
                if price <= budget:
                    for position in openings:
                        offer(self._score(catalogue, session, entry, position,
                                          free, stashed=(victim,),
                                          from_storage=from_storage),
                              entry, position, source,
                              stashed=(victim,), from_storage=from_storage)

                # 3. Sell it. Same squares, plus gold, but the item is gone.
                if price <= budget + victim.sell_value:
                    for position in openings:
                        offer(self._score(catalogue, session, entry, position,
                                          free, sold=(victim,),
                                          from_storage=from_storage),
                              entry, position, source,
                              sold=(victim,), from_storage=from_storage)
        return best


# ---------------------------------------------------------------- internals


def _any_legal_spot(session, entry):
    """A legal square for a shop entry, containers included.

    A container is not placed inside the grid the way an item is: it CREATES
    grid squares. So its legal spots are the board at large, minus the squares
    other containers already claim -- and it must stay INSIDE the board.

    The bounds test is not redundant, even though the server validates
    purchases. /purchase/item checks only container overlap (main.py:1080) and
    never bounds, so it will happily sell you a container hanging off the edge
    of the grid. The battle engine then refuses the whole rack
    (PlacementValidator.add_container, containers.py:84) and the run is dead.
    Until the server closes that gap, the bot must not ask for it.
    """
    if not entry.is_container:
        return placement.first_fit(session, entry)

    width, height = placement.GRID_SIZE
    claimed = placement.container_squares(session)
    shape = [tuple(s) for s in (entry.shape or [(0, 0)])]
    for y in range(height):
        for x in range(width):
            covered = placement.squares_at(shape, (x, y))
            if covered & claimed:
                continue
            if any(sx < 0 or sx >= width or sy < 0 or sy >= height
                   for sx, sy in covered):
                continue
            return (x, y)
    return None


SALE_CANDIDATES = 6        # grid or storage items considered for sale
STORAGE_CANDIDATES = 6     # parked items reconsidered for the grid each turn
MAX_POSITIONS = 12         # squares scored per item

# These three caps bound the plan space, which is otherwise
# candidates x squares x sale options and grew a shop turn to half a second
# once storage started filling up. They limit what is LOOKED AT, never what is
# preferred -- the learned weights still decide among whatever is offered.


def _sale_candidates(session):
    """Items worth considering giving up, cheapest first.

    Capped because every extra candidate multiplies the plans to score, and
    this runs inside the shop loop. Cheapest-first is a heuristic about SEARCH
    ORDER, not about value -- the learned weights still decide whether any
    given sale is worth making. It only decides which sales get looked at.
    """
    return sorted(session.inventory_grid,
                  key=lambda i: getattr(i, "sell_value", 0))[:SALE_CANDIDATES]



def _reroll(harness, who, session):
    try:
        harness.refresh_shop(who)
        return harness.session(who)
    except Exception:
        return session


def _anneal_through_server(harness, who, session, bot, rng, steps):
    """Hill-climb the layout, moving items through the real /move endpoint.

    Expensive by nature: every trial move and every undo is a server call. It
    is off by default for that reason -- see LinearBot.anneal_steps.
    """
    state = {"session": session}

    def apply_move(item_id, target) -> bool:
        try:
            harness.move(who, item_id, target)
            state["session"] = harness.session(who)
            return True
        except Exception:
            return False

    def score(_session) -> float:
        return bot.score_layout(harness.catalogue, state["session"])

    placement.anneal(state["session"], score, steps, rng, apply_move)
    return state["session"]
