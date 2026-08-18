"""
How strong is a bot, and how strong is a build?

Two different questions, answered separately, because conflating them is the
mistake that wasted a day of this project.

A BOT is a policy. Measure it against a FROZEN benchmark, or the number means
nothing: during training every genome is scored against an archive that grows
stronger each generation, so a flat fitness curve can mean "stopped improving"
OR "improving exactly as fast as the opposition". Training output cannot tell
those apart. A benchmark that never changes can.

A BUILD is one frozen rack. Its label is the (round, wins, losses) cell it
reached, and its rating orders builds within a cell. The ladder players
actually meet comes from BUILDS, not from bots: every trained checkpoint plays
competently and they cluster at the top, whereas builds vary enormously
because shop luck decides whether a run comes together. That spread is the
product.

BATTLES HERE GO STRAIGHT TO BattleSimulator. That is the same engine the
server calls, with the same BattleItem wiring main.py uses, so no rule is
duplicated -- but it skips sessions and economy, which a rack-versus-rack
comparison does not need.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import bots
import run as run_mod
import server_harness

BENCHMARK_PATH = Path(__file__).resolve().parent / "benchmark.json"


# --------------------------------------------------------------- one battle


def head_to_head(harness, a: run_mod.Build, b: run_mod.Build, seed: int,
                 round_number: int | None = None) -> bool:
    """True if `a` wins. Mirrors the wiring at main.py:509 and :571."""
    from battle_engine import BattleItem, BattleSimulator
    from containers import Container
    from items import PlacedItem

    catalogue = harness.catalogue.items

    def side(build):
        items = []
        for entry in build.grid:
            item = PlacedItem.model_validate(entry)
            if item.item_type in catalogue:
                items.append(BattleItem(spec=catalogue[item.item_type],
                                        position=item.position, uid=item.id,
                                        rotation=item.rotation))
        containers = [Container.model_validate(c) for c in build.containers]
        return items, containers

    a_items, a_containers = side(a)
    b_items, b_containers = side(b)
    if not a_items or not b_items:
        return bool(a_items)

    result = BattleSimulator(seed=seed).simulate_battle(
        a_items, b_items, round_number or a.round_number,
        p1_containers=a_containers, p2_containers=b_containers)
    return result["winner"] == 1


# ---------------------------------------------------------------- benchmark


def build_benchmark(harness, size: int = 300, seed: int = 12345
                    ) -> list[run_mod.Build]:
    """A FROZEN opponent set, generated once and reused.

    Built only from NaiveSpender, deliberately. A benchmark made of trained
    bots would drift every time training re-runs, and ladders from two runs
    would not be comparable. Naive racks are reproducible from a seed alone.

    DELETE benchmark.json after an item rebalance. The racks inside it hold
    items whose stats have changed, so the frozen bar silently moves.
    """
    if BENCHMARK_PATH.exists():
        data = json.loads(BENCHMARK_PATH.read_text())
        return [run_mod.Build(**d) for d in data]

    builds = []
    for i in range(24):
        naive = bots.NaiveSpender(buy_chance=(0.55, 0.75, 0.9, 1.0)[i % 4])
        result = run_mod.play_run(harness, naive, seed=seed + i * 7919,
                                  user=f"bench{i}", rng=random.Random(seed + i))
        builds.extend(b for b in result.builds if b.item_count > 0)
    builds = builds[:size]

    BENCHMARK_PATH.write_text(json.dumps([
        {"round_number": b.round_number, "wins": b.wins, "losses": b.losses,
         "grid": b.grid, "containers": b.containers, "generator": "benchmark",
         "item_count": b.item_count, "gold_unspent": b.gold_unspent}
        for b in builds]))
    return builds


def ladder_elo(harness, checkpoints: list, runs_each: int = 6,
               battles: int = 400, seed: int = 23) -> dict[int, float]:
    """Elo for each checkpoint, from checkpoints fighting EACH OTHER.

    THIS IS THE HONEST PROGRESS MEASURE, and the naive benchmark is not.

    A benchmark built from NaiveSpender racks is a floor, not a yardstick.
    Once a bot is winning 70% against it, further improvement barely moves the
    number, and a 5-point gain there could mean anything. Worse, it saturates:
    two genuinely different bots both sitting at 97% are indistinguishable, and
    a tie reads as "equally good" when it means "the ruler is too short".

    Checkpoints fighting each other has no ceiling. The measurement gets harder
    at exactly the rate the players get better, so a rating gain always means
    the same thing: it beat opposition that was itself improving.

    It also produces the difficulty ladder directly. A checkpoint's rating IS
    its tier, earned rather than assigned by which generation it happens to be.
    """
    rng = random.Random(seed)

    # Each checkpoint plays real runs, so its racks reflect its economy and not
    # just its taste in items.
    racks: dict[int, dict[int, list]] = {}
    for gen, bot in checkpoints:
        by_round: dict[int, list] = {}
        for i in range(runs_each):
            result = run_mod.play_run(harness, bot, seed=seed + i * 104729,
                                      user=f"elo{gen}_{i}", rng=rng)
            for build in result.builds:
                if build.item_count:
                    by_round.setdefault(build.round_number, []).append(build)
        racks[gen] = by_round

    ratings = {gen: 1200.0 for gen, _ in checkpoints}
    gens = [g for g, _ in checkpoints]
    k = 32.0

    for _ in range(battles):
        a, b = rng.sample(gens, 2) if len(gens) > 1 else (gens[0], gens[0])
        shared = set(racks[a]) & set(racks[b])
        if not shared:
            continue
        rnd = rng.choice(sorted(shared))
        a_build = rng.choice(racks[a][rnd])
        b_build = rng.choice(racks[b][rnd])
        a_won = head_to_head(harness, a_build, b_build, rng.randrange(2**31), rnd)

        expected = 1.0 / (1.0 + 10 ** ((ratings[b] - ratings[a]) / 400))
        delta = k * ((1.0 if a_won else 0.0) - expected)
        ratings[a] += delta
        ratings[b] -= delta
    return ratings


def compare_bots(harness, bot_a, bot_b, seeds=(7, 1009, 5077), runs_each: int = 12,
                 battles_per_seed: int = 400) -> tuple[float, float]:
    """A's win rate against B, head to head. Returns (mean, spread over seeds).

    THE ONLY MEASURE THAT ANSWERS "is this training run better than the last
    one". Everything else in this file compares against a fixed bar, and a
    fixed bar has two failings: a beginner bar flatters a competent bot by
    about 20 points, and any frozen bar saturates once both sides clear it.

    Here the opposition is the other bot, so there is no ceiling and no
    benchmark to maintain.

    BOTH BOTS PLAY THE SAME RUN SEEDS. Shop luck is the dominant source of
    variance in this game, so pairing the seeds removes it as a confound: any
    difference is how they played the same shops, not who got the better ones.

    Racks only fight at an EQUAL round, or the comparison measures whose
    economy got further rather than whose rack is stronger.

    Read the result against the spread. With three seeds, anything inside
    50% +- 2*spread is a tie, not a win.
    """
    rates = []
    for seed in seeds:
        racks = {}
        for label, bot in (("a", bot_a), ("b", bot_b)):
            by_round: dict[int, list] = {}
            rng = random.Random(seed)
            for i in range(runs_each):
                result = run_mod.play_run(harness, bot, seed=seed + i * 104729,
                                          user=f"cmp{label}{seed}_{i}", rng=rng)
                for build in result.builds:
                    if build.item_count:
                        by_round.setdefault(build.round_number, []).append(build)
            racks[label] = by_round

        rng = random.Random(seed)
        shared = sorted(set(racks["a"]) & set(racks["b"]))
        if not shared:
            continue
        wins = played = 0
        for _ in range(battles_per_seed):
            rnd = rng.choice(shared)
            if head_to_head(harness, rng.choice(racks["a"][rnd]),
                            rng.choice(racks["b"][rnd]), rng.randrange(2**31), rnd):
                wins += 1
            played += 1
        if played:
            rates.append(wins / played)

    if not rates:
        return 0.0, 0.0
    mean = sum(rates) / len(rates)
    spread = (max(rates) - min(rates)) / 2 if len(rates) > 1 else 0.0
    return mean, spread


def measure_bot(harness, bot, benchmark, battles: int = 300, seed: int = 7,
                runs: int = 40) -> float:
    """A bot's win rate against the frozen benchmark.

    The bot plays real runs to produce racks, and those fight benchmark racks
    from a similar round. Playing runs rather than scoring one hand-made rack
    is the point: a bot's strength includes its economy, not just its final
    loadout.
    """
    rng = random.Random(seed)
    by_round: dict[int, list] = {}
    for b in benchmark:
        by_round.setdefault(b.round_number, []).append(b)

    # COUNT RUNS, NOT BUILDS. The earlier version stopped once it had 40
    # builds, which one good run can supply on its own -- so all 400 battles
    # were then drawn from a handful of runs, and the whole measurement rode
    # on whether those few runs got lucky shops. That produced 23-point swings
    # between adjacent generations, which is not a skill difference.
    #
    # The battle count never was the limit. The RUN count is, because shop RNG
    # is the dominant source of variance in this game.
    own = []
    for attempt in range(runs):
        result = run_mod.play_run(harness, bot, seed=seed + attempt * 104729,
                                  user=f"meas{attempt}", rng=rng)
        own.extend(b for b in result.builds if b.item_count > 0)
    if not own:
        return 0.0

    wins = played = 0
    for _ in range(battles):
        mine = rng.choice(own)
        pool = [b for r in range(mine.round_number - 1, mine.round_number + 2)
                for b in by_round.get(r, [])]
        if not pool:
            continue
        if head_to_head(harness, mine, rng.choice(pool), rng.randrange(2**31),
                        mine.round_number):
            wins += 1
        played += 1
    return wins / played if played else 0.0


# ------------------------------------------------------------ build ratings


def rate_builds(harness, archive, rounds: int = 12, per_cell: int = 200,
                k: float = 24.0, seed: int = 11) -> tuple[int, int]:
    """Elo over builds, by Swiss pairing within a (round, wins, losses) cell.

    Only builds at the SAME cell fight. Comparing a round-3 rack with a
    round-14 one measures the economy that produced them, not the racks, and
    every late build would outrank every early one for no useful reason.

    TWO KNOBS DECIDE WHETHER THIS MEANS ANYTHING.

    `per_cell` is how many builds get to fight at all. Anything not sampled
    keeps the default 1200 and is not "average", it is UNMEASURED -- a silent
    tie with every other unmeasured build. The first version sampled by round
    and discarded the other cells, so 122,000 builds yielded 696 ratings.

    `rounds` is how far a rating can travel: Elo moves at most k per game, so
    12 Swiss rounds cap movement at +-288. Too few and everything piles up
    near the start, which reads as "all builds are equal" when it means "the
    measurement has not converged".

    Returns (battles, builds_rated).
    """
    rng = random.Random(seed)
    ratings: dict[int, float] = {}
    battles = 0

    for round_number, wins, losses, count in archive.cells():
        if count < 2:
            continue
        builds = archive.sample_cell(min(count, per_cell), rng,
                                     round_number, wins, losses)
        if len(builds) < 2:
            continue
        for b in builds:
            ratings.setdefault(b.id, 1200.0)

        for _ in range(rounds):
            # Swiss: sort by current rating and pair neighbours, so each game
            # is against someone of similar strength and therefore informative.
            order = sorted(builds, key=lambda b: -ratings[b.id])
            for i in range(0, len(order) - 1, 2):
                a, b = order[i], order[i + 1]
                a_won = head_to_head(harness, a, b, rng.randrange(2**31),
                                     round_number)
                battles += 1
                expected = 1.0 / (1.0 + 10 ** ((ratings[b.id] - ratings[a.id]) / 400))
                delta = k * ((1.0 if a_won else 0.0) - expected)
                ratings[a.id] += delta
                ratings[b.id] -= delta

    for build_id, rating in ratings.items():
        archive.set_rating(build_id, rating)
    archive.commit()
    return battles, len(ratings)


def report(archive_path=None, checkpoint_step: int = 4, battles: int = 200):
    import archive as archive_mod
    import train

    with server_harness.Harness() as harness:
        benchmark = build_benchmark(harness)
        print(f"benchmark: {len(benchmark)} frozen naive racks\n")

        gens = train.available_checkpoints()[::checkpoint_step]
        if not gens:
            print("no checkpoints; run train.py first")
            return

        # The naive benchmark answers only "does it beat a beginner", which is
        # a floor check. Progress is measured by checkpoints fighting each
        # other, where the bar rises with the players.
        print(f"{'gen':>5} {'elo vs other checkpoints':>26} {'vs naive (floor)':>18}")
        loaded = [(g, train.load_checkpoint(g)) for g in gens]
        elo = ladder_elo(harness, loaded)
        for gen, bot in loaded:
            floor_rate = measure_bot(harness, bot, benchmark, battles)
            print(f"{gen:>5} {elo[gen]:>26.0f} {floor_rate:>17.1%}")

        floor = measure_bot(harness, bots.NaiveSpender(0.9), benchmark, battles)
        print(f"\nnaive floor against itself: {floor:.1%}")
        span = max(elo.values()) - min(elo.values())
        print(f"elo span across the ladder: {span:.0f} points "
              f"({'a real ladder' if span > 150 else 'TOO NARROW to tier'})")

        arc = archive_mod.Archive(archive_path or archive_mod.DEFAULT_PATH)
        cells = arc.cells()
        print(f"\narchive: {arc.count()} builds across {len(cells)} "
              f"(round, wins, losses) cells")
        fought, rated = rate_builds(harness, arc)
        print(f"rated {rated} builds via {fought} battles")
        arc.close()


if __name__ == "__main__":
    report()
