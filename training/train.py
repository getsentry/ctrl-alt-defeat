"""
The training loop: an evolution strategy over LinearBot genomes.

No gradients and no framework, for practical reasons rather than ideological
ones:

  - The objective is "wins per run", which is noisy, discrete and not
    differentiable. Gradients do not exist here without a lot of machinery.
  - A run costs ~20 ms through the real server code, so a population of 24
    over 12 runs each is a few seconds spread across cores.
  - The genome is small. An ES searches that space comfortably.

A hidden-layer policy was measured against this and played no better -- see
RESEARCH.md. Revisit when adjacency fires, item shapes get awkward, or recipes
land, because all three add interactions a linear score cannot express.

WHERE THE DIFFICULTY LADDER COMES FROM
--------------------------------------
Every generation is checkpointed. Generation 0 is a random genome and plays
badly; the last plays as well as this method can; the ones between ARE the
ladder, all the same code with different weights. That beats hand-writing a
"level 4 bot", because the ladder is produced by the process that produces
strength, so it stays calibrated across a rebalance. Retrain, get a new ladder.

SELF-PLAY. Each generation's builds go into the archive, so the next
generation fights the previous one. The pool only grows and old strategies are
never forgotten, which turns naive self-play into fictitious self-play.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import random
import time
from pathlib import Path

import archive as archive_mod
import bots
import evaluate
import run as run_mod
import server_harness

CHECKPOINT_DIR = Path(__file__).resolve().parent / "checkpoints"

# One harness per worker PROCESS, not per task. Booting costs ~0.4 s and holds
# an event loop and a database, so building one per genome would dominate the
# run time and leak threads.
_HARNESS = None


def _worker_init():
    global _HARNESS
    _HARNESS = server_harness.Harness()


def evaluate_genome(job: tuple) -> tuple:
    """Play `runs` full runs with this genome. Returns (fitness, builds, wins)."""
    genome, seed, runs, db_path, generation = job
    bot = bots.LinearBot(genome=genome, name=f"gen{generation:03d}")
    rng = random.Random(seed)

    arc = archive_mod.Archive(db_path) if db_path else None

    def opponent_for(round_number):
        if arc is None:
            return None
        pool = arc.sample_pfsp(1, rng, round_number=round_number)
        return pool[0] if pool else None

    total_wins = total_rounds = 0
    builds = []
    faced = []
    for i in range(runs):
        result = run_mod.play_run(
            _HARNESS, bot, seed=seed + i * 7919, user=f"w{os.getpid()}",
            rng=rng, opponents=opponent_for if arc else None, survival=True)
        total_wins += result.wins
        total_rounds += result.final_round
        builds.extend(result.builds)
        faced.extend(result.opponent_results)

    if arc is not None:
        arc.close()

    # Wins per run in survival mode, with rounds survived as a small tiebreak
    # so two genomes that never win are still ordered by how long they lasted.
    fitness = total_wins / runs + 0.01 * (total_rounds / runs)
    return fitness, builds, total_wins, faced


def mutate(genome, sigma, rng):
    return [g + rng.gauss(0.0, sigma) for g in genome]


def train(generations=20, population=24, runs_per_genome=8, elite_frac=0.25,
          sigma=0.35, sigma_decay=0.97, seed=0, db_path=None, workers=None,
          checkpoint_dir=None, run_id=None) -> dict:
    rng = random.Random(seed)
    workers = workers or max(1, (os.cpu_count() or 4) - 2)
    db_path = db_path or str(archive_mod.DEFAULT_PATH)
    ckpt = Path(checkpoint_dir) if checkpoint_dir else CHECKPOINT_DIR
    ckpt.mkdir(parents=True, exist_ok=True)

    arc = archive_mod.Archive(db_path)
    # Stamp every build with WHICH RUN made it. Generation numbers restart at
    # zero each run, so without this the archive blends runs together and
    # "is this run better than the last" cannot be asked of it.
    run_id = run_id or f"s{seed}-p{population}-r{runs_per_genome}-g{generations}"
    print(f"archive: {db_path} ({arc.count()} builds)   run_id: {run_id}")

    # Cold start. Without a pool, generation 0 fights the server's stock AI and
    # every battle is a walkover, so fitness carries no signal.
    if arc.count() < 200:
        print("seeding archive with naive racks...")
        with server_harness.Harness() as h:
            seeded = 0
            for i in range(12):
                naive = bots.NaiveSpender(buy_chance=(0.55, 0.75, 0.9, 1.0)[i % 4])
                r = run_mod.play_run(h, naive, seed=1000 + i * 7919,
                                     user=f"seed{i}", rng=random.Random(i))
                seeded += arc.add_many(r.builds, generation=-1, run_id='seed')
            arc.commit()
        print(f"  seeded {seeded} builds")

    pop = [bots.random_genome(rng) for _ in range(population)]
    n_elite = max(2, int(population * elite_frac))
    history, best_ever = [], (-1.0, None)

    pool = mp.Pool(workers, initializer=_worker_init)
    try:
        for gen in range(generations):
            t0 = time.time()
            jobs = [(g, seed + gen * 100_000 + i * 991, runs_per_genome, db_path, gen)
                    for i, g in enumerate(pop)]
            results = pool.map(evaluate_genome, jobs)

            scored = sorted(zip((r[0] for r in results), range(len(pop))),
                            reverse=True)
            elites = [pop[i] for _, i in scored[:n_elite]]

            added = 0
            for _fitness, builds, _wins, faced in results:
                added += arc.add_many(builds, generation=gen, run_id=run_id)
                # Written in the PARENT: workers open the archive read-only
                # and only one process may write. This is what gives PFSP its
                # weights; without it every build looks equally hard.
                for build_id, opponent_won in faced:
                    arc.record_result(build_id, opponent_won)
            arc.commit()

            best_fit = scored[0][0]
            mean_fit = sum(r[0] for r in results) / len(results)
            mean_wins = sum(r[2] for r in results) / (len(results) * runs_per_genome)
            if best_fit > best_ever[0]:
                best_ever = (best_fit, list(elites[0]))

            _save_checkpoint(ckpt, gen, elites[0], best_fit, mean_fit, mean_wins)
            history.append({"generation": gen, "best": best_fit, "mean": mean_fit,
                            "mean_wins": mean_wins, "archive": arc.count()})
            print(f"gen {gen:3d}  best {best_fit:5.2f}  mean {mean_fit:5.2f}  "
                  f"wins/run {mean_wins:4.2f}  archive {arc.count():6d} (+{added})"
                  f"  sigma {sigma:.3f}  {time.time()-t0:5.1f}s")

            # Carry the best genome EVER seen, not just this generation's
            # elites. Fitness is a noisy estimate over a handful of runs, so a
            # mediocre genome can get lucky, win selection, and take the
            # population with it -- which is how a measured ladder ends up
            # peaking in the middle and declining afterwards. Re-injecting the
            # all-time best means quality can stall but cannot be lost.
            pop = list(elites)
            if best_ever[1] is not None and best_ever[1] not in pop:
                pop.append(list(best_ever[1]))
            while len(pop) < population:
                pop.append(mutate(rng.choice(elites), sigma, rng))
            sigma *= sigma_decay
    finally:
        # terminate(), NOT close()+join(). Each worker holds a Harness, whose
        # aiosqlite connection runs on a non-daemon thread, so a worker asked
        # to shut down politely never exits and join() waits forever. The
        # worker state is disposable, so killing them is correct as well as
        # necessary.
        pool.terminate()
        pool.join()
        arc.close()

    (ckpt / "history.json").write_text(json.dumps(history, indent=2))
    return {"history": history, "best": best_ever}


def _save_checkpoint(ckpt, gen, genome, best, mean, mean_wins):
    (ckpt / f"gen_{gen:03d}.json").write_text(json.dumps({
        "generation": gen, "genome": genome, "fitness": best,
        "mean_fitness": mean, "mean_wins": mean_wins,
        "feature_names": __import__("evaluate").FEATURE_NAMES,
    }, indent=2))


def load_checkpoint(gen: int, checkpoint_dir=None) -> bots.LinearBot:
    d = Path(checkpoint_dir) if checkpoint_dir else CHECKPOINT_DIR
    data = json.loads((d / f"gen_{gen:03d}.json").read_text())
    genome = data["genome"]

    # REFUSE a genome of the wrong length. LinearBot slices its weights by
    # position -- buy weights from the front, layout and controls from the
    # back -- so a genome that is one gene short does not fail, it OVERLAPS:
    # the last buy weight and the first layout weight become the same number.
    # The bot still runs and still scores, and every measurement taken from it
    # is quietly meaningless. Adding one feature is enough to cause this.
    if len(genome) != bots.GENOME_SIZE:
        raise ValueError(
            f"checkpoint gen_{gen:03d} has {len(genome)} genes but this build "
            f"expects {bots.GENOME_SIZE} ({len(evaluate.FEATURE_NAMES)} features "
            f"+ {bots.N_TAIL} tail). The feature set changed since it was "
            f"trained, so these weights mean nothing here. Retrain."
        )
    return bots.LinearBot(genome=genome, name=f"gen{gen:03d}")


def available_checkpoints(checkpoint_dir=None) -> list[int]:
    d = Path(checkpoint_dir) if checkpoint_dir else CHECKPOINT_DIR
    if not d.exists():
        return []
    return sorted(int(p.stem.split("_")[1]) for p in d.glob("gen_*.json"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--generations", type=int, default=20)
    ap.add_argument("--population", type=int, default=24)
    ap.add_argument("--runs", type=int, default=8)
    ap.add_argument("--sigma", type=float, default=0.35)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--db", default=None)
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--checkpoints", default=None)
    ap.add_argument("--run-id", default=None)
    args = ap.parse_args()

    t = time.time()
    out = train(generations=args.generations, population=args.population,
                runs_per_genome=args.runs, sigma=args.sigma, seed=args.seed,
                db_path=args.db, workers=args.workers,
                checkpoint_dir=args.checkpoints, run_id=args.run_id)
    print(f"\ntrained in {time.time()-t:.0f}s; best fitness {out['best'][0]:.2f}")
