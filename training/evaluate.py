"""
What a bot can PERCEIVE about a rack. No opinions live here.

The split this module exists to enforce:

    what the bot can SEE        hand-built, here          my job
    what a sight is WORTH       learned by train.py       the search's job

Nothing below assigns value. Every function returns a structural measurement,
and the weights that turn measurements into a decision are learned from real
battle outcomes. That is deliberate: hand-tuned weights encode what the author
believes wins and go stale the moment the game is rebalanced, while a
measurement stays true.

THE PERCEPTION PROBLEM IS NOT SOLVED, AND IT IS THE REAL LIMIT.
An item is invisible here if a rack holding it scores the same as an empty
one. Measured against the current catalogue, a large fraction of items are
invisible, because their effects are BuffEffect and StatModEffect and this
module reads neither. The stat system is still being built, so filling those
in now would mean guessing at numbers that have not settled.

The consequence to remember when reading trained weights: for an invisible
item the ONLY non-zero features are the category one-hots, `cost` and `tiles`.
Training will therefore load weight onto a one-hot, and that looks exactly
like a strong preference for a category when it is really a missing sensor.
Do not read a category weight as a balance finding until this is closed.

Re-run `python audit.py` after the stats land to see how far it has closed.
"""

from __future__ import annotations

BASE_MAX_CPU = 10.0    # battle_engine.py
BASE_CPU_REGEN = 2.0   # battle_engine.py

# ------------------------------------------------------------------ the spec


def spec_of(catalogue, item):
    """The full ItemSpec for a grid or shop item.

    Worth going back to the spec rather than trusting the shop payload: the
    payload flattens an item to min_damage/max_damage/min_heal/max_heal/
    block_amount, which covers only four of the seven effect classes. The
    spec still carries the triggers and effects themselves.
    """
    return catalogue.items.get(item.item_type)


# ------------------------------------------------------------------ CPU model


def cpu_profile(catalogue, grid) -> tuple[float, float, float]:
    """(max_cpu, regen_per_second, drain_per_second) for a rack.

    CPU is the binding constraint in a battle: every timed item pays cpu_cost
    when it fires, and a rack that drains faster than it regenerates throttles
    and does nothing. A rack of pure attackers starves itself, which is why a
    damage-only score is actively misleading.
    """
    max_cpu, regen, drain = BASE_MAX_CPU, BASE_CPU_REGEN, 0.0
    for item in grid:
        spec = spec_of(catalogue, item)
        if spec is None:
            continue
        for trigger in spec.triggers:
            for effect in getattr(trigger, "effects", None) or []:
                if type(effect).__name__ == "StatModEffect":
                    if effect.stat_name == "max_cpu":
                        max_cpu += effect.value
                    elif effect.stat_name == "cpu_regen":
                        regen += effect.value
            cooldown = getattr(trigger, "cooldown", None)
            cost = getattr(trigger, "cpu_cost", 0) or 0
            if cooldown and cost:
                drain += cost / max(cooldown, 0.5)
    return max_cpu, regen, drain


# ----------------------------------------------------------------- adjacency


def adjacent_pairs(grid) -> list[set[int]]:
    """For each item, the indices of the items orthogonally touching it.

    Uses the server's own covered_squares(), so rotation and irregular shapes
    are handled by the same code the battle engine uses.
    """
    owner: dict[tuple[int, int], int] = {}
    for index, item in enumerate(grid):
        for square in item.covered_squares():
            owner[tuple(square)] = index

    neighbours: list[set[int]] = [set() for _ in grid]
    for (x, y), index in owner.items():
        for near in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            other = owner.get(near)
            if other is not None and other != index:
                neighbours[index].add(other)
                neighbours[other].add(index)
    return neighbours


def adjacency_multipliers(catalogue, grid) -> list[float]:
    """Per-item multiplier from the synergies that ACTUALLY FIRE.

    Only the category-matched ones are modelled. The engine also has three
    name-matched synergies, and they compare against item names that no item
    carries, so they can never trigger. Modelling them would reward layouts
    that do nothing.
    """
    neighbours = adjacent_pairs(grid)
    categories = []
    for item in grid:
        spec = spec_of(catalogue, item)
        categories.append(spec.category if spec else "")

    multipliers = []
    for index, _ in enumerate(grid):
        near = neighbours[index]
        problems = sum(1 for j in near if categories[j] == "problem")
        defenses = sum(1 for j in near if categories[j] == "defense")
        infra = sum(1 for j in near if categories[j] == "infrastructure")

        m = 1.0
        if categories[index] == "problem" and problems >= 2:
            m *= 1.2   # Bug Swarm
        if problems >= 1 and defenses >= 1 and infra >= 1:
            m *= 1.3   # Full Stack
        multipliers.append(m)
    return multipliers


# ------------------------------------------------------------ offence/defence


def raw_dps(catalogue, grid) -> float:
    """Damage per second with unlimited CPU. Throttling is modelled separately
    by the CPU ratio, so this stays a property of the items."""
    multipliers = adjacency_multipliers(catalogue, grid)
    total = 0.0
    for index, item in enumerate(grid):
        spec = spec_of(catalogue, item)
        if spec is None:
            continue
        for trigger in spec.triggers:
            cooldown = getattr(trigger, "cooldown", None)
            if not cooldown:
                continue
            for effect in getattr(trigger, "effects", None) or []:
                low = getattr(effect, "min_damage", None)
                high = getattr(effect, "max_damage", None)
                if low is None and high is None:
                    continue
                average = ((low or 0) + (high or 0)) / 2.0
                accuracy = getattr(effect, "accuracy", 1.0)
                total += (average * (accuracy if accuracy is not None else 1.0)
                          * multipliers[index]) / max(cooldown, 0.5)
    return total


ENEMY_ATTACK_PERIOD = 3.0   # a guess, and one of the weaker assumptions here


def sustain(catalogue, grid) -> float:
    """Healing plus expected blocked damage per second.

    Shields fire on being attacked rather than on a timer, so there is no
    cooldown to divide by and ENEMY_ATTACK_PERIOD stands in. That constant is
    hand-picked, and it inflates or deflates every defensive item together --
    worth replacing with a measured value once battles are being mined.
    """
    total = 0.0
    for item in grid:
        spec = spec_of(catalogue, item)
        if spec is None:
            continue
        for trigger in spec.triggers:
            cooldown = getattr(trigger, "cooldown", None) or ENEMY_ATTACK_PERIOD
            for effect in getattr(trigger, "effects", None) or []:
                low = getattr(effect, "min_heal", None)
                high = getattr(effect, "max_heal", None)
                if low is not None or high is not None:
                    total += (((low or 0) + (high or 0)) / 2.0) / max(cooldown, 0.5)
                block = getattr(effect, "block_amount", None)
                if block:
                    chance = getattr(effect, "block_chance", None)
                    total += (block * (1.0 if chance is None else chance)
                              ) / ENEMY_ATTACK_PERIOD
    return total


def rack_features(catalogue, grid) -> tuple:
    max_cpu, regen, drain = cpu_profile(catalogue, grid)
    ratio = 1.0 if drain <= 0 else min(1.0, regen / drain)
    adjacency = sum(adjacency_multipliers(catalogue, grid)) if grid else 0.0
    return (raw_dps(catalogue, grid), sustain(catalogue, grid), ratio,
            max_cpu, regen, adjacency)


# ------------------------------------------------------------------ features
#
# To give the bot a sense it does not have, append one measurement here and one
# name to FEATURE_NAMES. Training picks up the new dimension with no other
# change, because the genome is sized from this list.

FEATURE_NAMES = [
    "d_dps",         # change in damage per second
    "d_sustain",     # change in heal + block per second
    "d_cpu_ratio",   # change in the share of activations CPU can pay for
    "d_max_cpu",
    "d_regen",
    "d_adjacency",   # change in total adjacency multiplier
    "net_cost",      # price paid, minus anything recovered by selling
    "tiles",         # squares the incoming item consumes
    "gold_frac",     # net price as a share of gold in hand
    "tiles_frac",    # squares as a share of free squares
    "rarity",        # designer-authored power ranking, 0..1
    "is_attack",
    "is_defense",
    "is_infra",
    "round_frac",    # how late in the run we are
    "sold_count",    # how many items this plan gives up for gold
    "sold_tiles",    # how much space giving them up frees
    "moved_count",   # how many items it shuffles to make room
    "stashed_count",  # how many it parks in storage instead of selling
    "stashed_tiles",  # how much space parking them frees
    "from_storage",   # 1.0 if this brings an owned item back onto the grid
    "is_container",   # 1.0 if the purchase is space rather than an item
    "tiles_gained",   # squares the purchase ADDS to the board
    "to_storage",     # 1.0 if the purchase is parked, not placed
]

RARITY_RANK = {"common": 0.0, "uncommon": 0.2, "rare": 0.4,
               "epic": 0.6, "legendary": 0.8, "unique": 0.9, "godly": 1.0}

ATTACK = {"problem", "protocol", "script"}
DEFENCE = {"defense", "patch", "monitor"}
INFRA = {"infrastructure", "module", "container"}


def plan_features(catalogue, session, item, position, sold=(), free_tiles: int = 0,
                  moved: dict | None = None, stashed=(), from_storage: bool = False,
                  is_container: bool = False, to_storage: bool = False
                  ) -> list[float]:
    """Features for a whole PLAN: shuffle, stash or sell to make room, then
    put an item on the grid -- bought from the shop, or reclaimed from storage.

    SELLING AND STASHING ARE DIFFERENT TRADES, and both must be available or
    the bot is forced into a false choice. Selling frees squares AND returns
    half the price, but the item is gone. Stashing frees the same squares and
    keeps the item, but returns nothing. Storage is unlimited
    (inventory_manager.py:111), so parking is always possible. Which is right
    depends on whether the item will be wanted later, which is exactly the
    kind of judgement that should be trained rather than written down.

    Buying, placing and selling are ONE decision, not three. "Is this item
    worth having" cannot be answered without knowing where it would go and
    what would have to leave to make room -- a strong item is worthless if
    fitting it costs two items that were carrying the rack. Scoring the plan
    lets a single learned weight vector price the whole trade, so training
    discovers how much a sale has to buy before it is worth making.

    Every offence and defence term is MARGINAL: the delta between the rack now
    and the rack the plan would produce. The same attacker is excellent with
    spare CPU and worthless in a starved rack, so an isolated score sees
    neither.

    THE SQUARE IS REQUIRED. Adjacency is a property of WHERE an item sits, so
    a value computed without one is meaningless. This is the seam that makes
    adjacency usable the moment the synergies actually fire: the bot already
    scores each candidate square separately, so a square that earns a bonus
    simply scores higher, with no code change.
    """
    # BUYING SPACE IS A REAL STRATEGY and must be comparable with buying an
    # item, or the bot silently caps itself at its starting rack. A container
    # adds no damage and no healing, so every rack delta below is zero for it;
    # its whole value is `tiles_gained`. Leaving it out of the candidate list
    # -- which an earlier version did with one line -- meant no trained bot
    # ever owned more than its three starting containers, across 263,000
    # builds, while the random bot grew to four and carried 40% more items.
    spec = spec_of(catalogue, item)
    # Sold and stashed items both LEAVE THE RACK, so both change the rack
    # features identically. Only the gold and the permanence differ, and those
    # are separate features below.
    dropped = {s.id for s in sold} | {s.id for s in stashed}
    moved = moved or {}

    # The resulting rack, with everything the plan does applied at once. Moves
    # matter to the SCORE and not only to whether the item fits: shifting an
    # item changes what it sits beside, so a rearrangement can gain or lose
    # adjacency for the mover as well as the newcomer.
    kept = [
        (i.placed_at(list(moved[i.id])) if i.id in moved else i)
        for i in session.inventory_grid if i.id not in dropped
    ]

    before = rack_features(catalogue, session.inventory_grid)
    # NEITHER a container NOR a parked item joins the rack, so for both the
    # resulting rack is just whatever survived the plan.
    #
    # Getting this wrong made buy-to-storage the bot's favourite move: scoring
    # it with the item placed at (0, 0) handed it the item's full damage and
    # healing while paying no square, so parking looked like a free placement.
    # A parked item contributes NOTHING until it is brought back out. Its only
    # value is optionality, and `to_storage` is the feature that prices that.
    off_grid = is_container or to_storage
    after = rack_features(
        catalogue, kept if off_grid else kept + [item.placed_at(list(position))])

    category = spec.category if spec else ""
    tiles = max(1, len(item.shape or [(0, 0)]))
    tiles_gained = tiles if is_container else 0
    consumes_grid = not (is_container or to_storage)
    recovered = sum(getattr(s, "sell_value", 0) for s in sold)
    # An item already owned costs nothing to put back on the grid.
    # `price`, not `cost`: one shop item in ten is on sale at half price
    # (items.py:119, sale_price). Scoring on `cost` over-prices every sale
    # item and makes the bot refuse bargains it can afford.
    price = 0 if from_storage else item.price
    net_cost = price - recovered

    # Only items that were ON THE GRID free squares by leaving. Selling out of
    # storage raises gold and nothing else, and counting its tiles as space
    # gained would tell the bot it had made room it has not made.
    on_grid = {i.id for i in session.inventory_grid}
    sold_tiles = sum(max(1, len(s.shape or [(0, 0)]))
                     for s in sold if s.id in on_grid)
    stashed_tiles = sum(max(1, len(s.shape or [(0, 0)])) for s in stashed)

    return [
        after[0] - before[0],
        after[1] - before[1],
        after[2] - before[2],
        after[3] - before[3],
        after[4] - before[4],
        after[5] - before[5],
        float(net_cost),
        float(tiles) if consumes_grid else 0.0,
        net_cost / max(1.0, session.gold),
        (tiles / max(1.0, free_tiles + sold_tiles + stashed_tiles))
        if consumes_grid else 0.0,
        RARITY_RANK.get(getattr(spec, "rarity", "common"), 0.0) if spec else 0.0,
        1.0 if category in ATTACK else 0.0,
        1.0 if category in DEFENCE else 0.0,
        1.0 if category in INFRA else 0.0,
        session.round / float(18),
        float(len(sold)),
        float(sold_tiles),
        float(len(moved)),
        float(len(stashed)),
        float(stashed_tiles),
        1.0 if from_storage else 0.0,
        1.0 if is_container else 0.0,
        float(tiles_gained),
        1.0 if to_storage else 0.0,
    ]


def layout_features(catalogue, grid) -> list[float]:
    """Features for judging one ARRANGEMENT against another. The annealing
    objective, so it must stay cheap."""
    dps, sus, ratio, _max_cpu, _regen, adjacency = rack_features(catalogue, grid)
    return [dps, sus, ratio, adjacency]
