# Bot generation: research notes

> **Status, August 2026.** The trainer now runs the REAL server code in-process
> (`server_harness.py`); the hand-copied `rules.py` this document often refers
> to has been DELETED, after it drifted and broke within two days of a
> refactor. `ladder.py`, `rate.py`, `compare.py`, `export.py` and
> `feature_stats.py` were folded into `measure.py` and `archive.py`.
>
> The reasoning below still holds. The file names and the measured numbers
> predate both that port and a full item-data rewrite, so treat every figure
> as historical unless `README.md` repeats it.

Notes for the automatic opponent generator. The goal: make many builds at many
strengths, so matchmaking always has an opponent for a player at any record.

This document records **why** the design is what it is. The code in this folder
is the first prototype of it. Read this before you change the approach, because
several obvious approaches were considered and rejected for reasons that are
not visible in the code.

Status at the time of writing: infrastructure runs, difficulty ladder does not
calibrate. See section 10.

---

## 1. What the bot actually decides

The first framing was wrong. The battle looked like the hard part, so the first
proposal put a policy on the battle. That is not where the decisions are.

`battle_engine.simulate_battle()` is **fully deterministic** given the two
loadouts and a seed. Neither player acts during a battle. So the battle is a
scoring function, not a game to play.

The real decision sequence is the run:

```
new run -> shop -> buy/sell/reroll/arrange -> battle -> gold -> shop -> ...
```

18 rounds. 10 wins to win the run. 5 lives. Survival mode after 10 wins.

So the bot plays an **economy and packing** game, not a combat game. Every
decision is: what do I buy with limited gold, and where does it go on a grid
where adjacency gives synergy.

## 2. The two-level decomposition

The problem splits cleanly, and the two halves want different tools.

**Inner problem: placement.** Given a set of items and a set of containers,
find the arrangement that maximises synergy. This is deterministic, fully
observable, and combinatorial. It is a packing problem with an objective.

> Do NOT put a neural network here. Local search solves it better, faster, and
> without training. `placement.anneal()` does hill climbing with single-item
> restarts. It is ~10 lines of real logic.

**Outer problem: purchasing.** Given gold, a random shop, and an unknown
future, decide what to buy. This is sequential, stochastic, and partially
observable. This is the part where learning helps.

The split matters because it makes the learned part much smaller. The policy
never outputs coordinates. It outputs "buy shop slot 2", and the packer decides
where the item goes.

## 3. Why annealing for placement

Measured cost:

| Operation | Time |
|---|---|
| `adjacency_score()` | ~3 us |
| One battle | ~575 us |
| One full 18-round run | ~10.4 ms |

The objective is ~190x cheaper than a battle. That is what makes annealing
usable: 200 steps of layout search costs less than one battle. If the objective
needed a battle to evaluate, this approach would be dead.

`adjacency_score()` counts orthogonally adjacent item pairs. It is a **proxy**
for synergy, not the real thing. Game Design Document 4.3 defines adjacency as
orthogonal only, and every square of a multi-square item counts. When the
recipe system lands, this proxy gets worse and must be replaced.

## 4. Survey of approaches for the outer problem

Considered, in increasing cost:

**Hand-written heuristics.** Score each offer, buy the best. This is
`bots.Heuristic`. Cheap, immediate, and gives a baseline. Weakness: the score
function encodes what the author believes wins, which may be wrong. It is wrong
right now (section 10).

**Direct search over heuristic parameters.** Keep the heuristic, but let an
optimiser find the weights. CMA-ES or Optuna, with win rate against a fixed
field as the objective. `HeuristicParams` is a dataclass for exactly this
reason: the search space is already isolated.

> This is the recommended next step. A run costs 10.4 ms, so a 2000-evaluation
> search costs minutes, not hours.

**Reinforcement learning.** PPO over the purchase decision. Two requirements:

- **Action masking is mandatory.** Most actions are illegal most of the time
  (cannot afford it, no room, slot empty). Without masking, the policy spends
  almost all its samples learning what it may not do. Use `MaskablePPO` from
  `sb3-contrib`.
- The observation must include gold, round, record, the shop, and the current
  rack. Free tiles matter as much as gold.

RL is only worth it for the top tiers (8-10), and only after direct search
stops improving.

**MCTS.** Attractive because the model is perfect: we can simulate forward
exactly. Expensive because each rollout needs battles. Worth revisiting if the
purchase policy plateaus.

**Quality-Diversity (MAP-Elites, `pyribs`).** Not an alternative to the above,
it is a complement. Instead of one best build, keep an archive of builds that
are good AND different, filed by behaviour descriptors (item count, damage
share, tile usage, rarity mix).

> This directly serves the product need. Matchmaking wants VARIETY, not one
> optimal build. A player who meets the same rack every round notices at once.
> Pure optimisation produces a monoculture; QD does not.

## 5. Bootstrapping: where do the first opponents come from

The chicken-and-egg problem: to play a run you need opponents, and at the start
there are none.

Solution used in `run.py`: run a **cohort** of bots through the rounds
together and pair them against each other by record. This needs no pre-existing
pool. It also mirrors what the real game does, because Backpack Battles pairs
you against ghosts of players at a similar record, not against a live opponent.

Once a pool exists, the standard progression is:

| Scheme | What it does | Failure mode |
|---|---|---|
| Naive self-play | Always fight the current best | Strategy cycling. A beats B, B beats C, C beats A, forever |
| **FSP** (Fictitious Self-Play) | Fight a uniform sample of ALL past versions | Slow; wastes time on opponents already beaten |
| **PFSP** (AlphaStar) | Sample past versions weighted by how hard they are | The practical choice |
| League with exploiters | Add agents whose only job is to beat the main agent | Most expensive; overkill here |

**Catastrophic forgetting is the real risk, not weak play.** An agent that only
fights the current best forgets how to beat older strategies. The archive is
the defence: never delete an old build, keep sampling from the whole history.

## 6. Difficulty levels: separate generators, not one noise dial

The tempting design is one good policy plus a temperature dial: turn up the
noise for a weak bot. **This does not work**, and it is worth stating why.

A high-temperature policy produces **incoherent non-play**: an empty rack,
hoarded gold, items bought and never placed. A real weak player does something
different. They spend all their gold, on the wrong things, and pack badly.

Those two look nothing alike to a player reading the post-battle screen. An
empty rack reads as a bug, not as an easy opponent.

> The user said it directly: "the bots shouldn't actively not use items, they
> should at least spend some money."

So the ladder comes from **different generators**:

| Tier | Generator | Behaviour |
|---|---|---|
| 1-3 | `NaiveSpender` | Buy a random affordable item, first-fit, never reroll |
| 4-7 | `Heuristic` | Score offers, anneal the layout, reroll a weak shop |
| 8-10 | not built | Tuned parameters, then a trained policy |

## 7. MMR: do not rate the bots, let them earn a record

The question was how to give a bot an MMR so matchmaking can pair it with a
player of similar skill. The answer is to not assign one.

Distinguish two things that are easy to confuse:

- A **build** is a frozen loadout that plays one battle. It has no history.
- A **player** accumulates a record across many runs.

A build cannot have an MMR, because MMR is a property of a history.

**Honest-run labelling.** Let the bot play a real run. At each round, file the
build at the `(round, wins, losses)` cell it actually reached. The record IS
the label. A bot that reached round 7 with 2 wins and 4 losses produces exactly
the opponent a struggling player at round 7 should meet.

This needs no rating system, no Elo, and no calibration step. It cannot drift,
because the label is a fact about what happened.

**Coverage.** There are ~80 reachable `(round, W, L)` cells. At 100 builds per
cell that is ~8000 builds, which is ~450 full runs. At 10.4 ms per run that is
under a minute of compute.

## 8. Off-the-shelf tools

Nothing packages this end to end. The useful pieces:

| Tool | Use |
|---|---|
| `sb3-contrib` (`MaskablePPO`) | The RL part, if it is needed. Action masking built in |
| `optuna` / `cma` | Parameter search over `HeuristicParams`. Start here |
| `pyribs` | MAP-Elites archive for build variety |
| `PettingZoo` / `Gymnasium` | Environment interfaces, if RL happens |
| `OpenSpiel` | Has FSP/PFSP reference implementations worth reading |

All are free and open source. None of them know anything about this game, so
the environment wrapper is work regardless.

## 9. What blocks a clean version

The rules currently live inside FastAPI request handlers, so they cannot be
imported without an HTTP request and a PostgreSQL connection. `rules.py` in
this folder is a **copy** of that logic, and it can drift.

`docs/rules_layer_refactor.md` (in the main repo) describes the fix: pull the
rules into a pure layer, and inject storage at a service layer above it. Then
this file is deleted and the trainer imports the same code the server runs.
That refactor waits for the API-shape work.

Known determinism holes that must close before training is reproducible:

- `generate_shop_items` falls back to the global `random` (main.py:513-516)
- `BattleSimulator` falls back to `time.time()` (battle_engine.py:148-151)

## 9b. The design rule that came out of building it

**No hand-tuned weights anywhere.**

The first version scored shop offers with a formula written by hand: damage per
second, minus a tile penalty, minus a cost penalty. It failed, and it failed in
a way that was not obvious. It was blind to shields, to healing, and to CPU, so
it bought attackers that could not fire. The simplest possible bot beat it.

The deeper problem is that a hand-written score is a claim about what wins. It
is stale as soon as the game is rebalanced, and it is wrong in ways nobody can
see until a measurement contradicts it.

So the split is now strict:

| Layer | Contains | Changes when the game is rebalanced |
|---|---|---|
| `evaluate.py` | Structural MEASUREMENTS: damage per second, CPU supply against CPU demand, heal and block per second, tiles, cost | No |
| The genome | The WEIGHTS that turn those into a decision | Yes, by retraining |

`evaluate.py` never says an item is good. It says what an item does to the
rack. Training decides what that is worth, from real battle outcomes.

Practical result: rebalance the game, re-run `train.py`, get a new ladder. No
code change. That is the property the whole system is built around.

To give the bot a signal it cannot currently see, add a feature to
`FEATURE_NAMES` and to `buy_features()`. Training picks up the new dimension
with no other change.

## 9c. Two measurement traps

**Fitness is not progress.** During training each genome is scored against the
archive as it stands at that moment, and the archive gets stronger every
generation. A flat fitness curve can mean "stopped improving" or "improving
exactly as fast as the opposition", and the training log cannot tell them
apart. `ladder.py` measures against a FROZEN benchmark of naive racks, which
can. The benchmark is built only from `NaiveSpender` on purpose: it must be
reproducible from a seed, or ladders from two different training runs are not
comparable.

**A capped objective kills the search.** Scoring "wins per run" stops at 10,
because that wins the run. Once most genomes reach 10 they all score exactly
10 and cannot be ranked, so the search has no gradient to follow. Training
therefore plays in SURVIVAL mode, to the 18 round cap or until lives run out.
That is a real game mode, so the builds are still honest opponents.

## 10. Findings from the FIRST prototype (historical)

> Kept because the reframe at the end of this section is why the current design
> exists. The code it describes -- `Heuristic`, `for_level()`, the naive tiers
> as a ladder -- was deleted. For current results see sections 13 and 14.

**The infrastructure works.** 792 builds from 6 cohorts, in seconds. Every
build carries a record it earned.

**The ladder does not calibrate.** Measured win rate against the field:

```
naive_L3            62.2%     <- the SIMPLEST bot is the strongest
heuristic_L5        58.3%
heuristic_L6        55.5%
heuristic_L7        53.6%
heuristic_L4        50.1%
naive_L2            41.7%
naive_L1            13.6%     <- clean bottom rung, this one is correct
```

The cause is visible in the item counts. Heuristic tiers 5/6/7 average
9.2/8.8/7.5 items; `naive_L3` averages 10.3. The heuristic burns gold on
rerolls and buys less. Two specific errors:

1. `Heuristic.score()` uses only `min_damage`/`max_damage`. It is blind to
   shields, healing and infrastructure, so it never buys them.
2. `reroll_below=0.35` rerolls too often. Gold spent on rerolls is gold not
   spent on items.

**At this power level, filling the rack beats selecting for it.** That is a
result about the game, not only about the code.

**The reframe this points to:** the ladder does not need the generators to be
ordered. It needs SPREAD, which exists (13.6% to 62.2%), and then builds get
labelled by **measured** win rate rather than by which generator made them.
The generators become sources of variety; the tier becomes a measured property.

What is genuinely missing is the top of the ladder. Nothing here plays well, so
there is no level 9 or 10 yet.

## 11. Open questions

- Does adjacency stay a good proxy after the recipe system lands? Probably not.
- Should a build's label be its measured win rate, or the cell it reached, or
  both? They answer different questions.
- `find_opponent()` requires `battle_won == True` (matchmaking.py:123), which
  starves new players of weak opponents. Losing builds are the ones a beginner
  needs to meet.
- How many builds per cell before a player notices repetition?

## 12. Dead adjacency synergies (a bug in the game, not the trainer)

`BattleSimulator._calculate_adjacency()` has six synergies. Three match on
`spec.name` against strings that no item carries, so they can never fire.

| The engine looks for | Matches on | Actual item | Fires? |
|---|---|---|---|
| `"Error Monitoring"` | name | `"Error Monitoring Shield"` | **never** |
| `"Performance Monitoring"` | name | no such item | **never** |
| `"CDN"` | name | no such item | **never** |
| `"Load Balancer"` | name | `"Load Balancer"` | yes |
| Bug Swarm | category | `problem` x >=2 | yes |
| Full Stack | category | `problem`+`defense`+`infrastructure` | yes |

`evaluate.py` models only the three that work. This is deliberate: the
estimator must agree with the engine that RUNS, not with the engine as
intended, or the layout objective rewards arrangements that do nothing.

**The consequence for training.** With only category synergies live and half
the items 1x1, the layout objective is *perfectly flat* -- measured spread
0.0000 across 300 random arrangements of the same rack. The placement
annealer is optimising a constant, which is why it measures as inert. Fixing
the name matching turns placement into a real lever, and `anneal_scored`
starts earning its cost that day.

## 13. The perception problem: 50 of 95 items score zero

Section 9b split the design into what the bot can PERCEIVE (hand-built, my
job) and what perceptions are WORTH (trained, self-correcting). The valuation
half works. The perception half was measured, and it is much weaker than the
docstrings implied.

An item is "invisible" if a rack holding one copy of it scores identically to
an empty rack: no DPS, no sustain, no CPU change. **50 of the 95 items are
invisible.**

| Blind spot | Uses | Detail |
|---|---|---|
| `BuffEffect` | 26 | The most common effect class in the game. Read by nothing. 19 of them are `speed` |
| `StatModEffect`, 8 of 10 stats | 17 | Only `max_cpu` and `cpu_regen` are read. Ignored: `crit_chance` (5), `damage_reduction` (3), `max_memory` (3), `attack_speed`, `damage`, `cpu_cost`, `accuracy`, `cooldown_reduction` |
| `ConsumeEffect` | 6 | Ignored |
| `PassiveTrigger` | 33 | The most common trigger. `raw_dps` skips any trigger with no cooldown |

Whole categories are invisible: all 14 `module` items, most `protocol`s, all
`consumable`s. `Cryogenic Cooling System` costs 25 gold and scores 0.0.

**This invalidates the "defence beats damage" reading.** Training produced
`is_defense +2.62` against `d_dps +0.63`, and that was presented as a fact
about game balance. It is more likely an artefact: for half the catalogue the
only non-zero features are the category one-hots and `cost`/`tiles`, so the
search loaded weight onto the one sensor still reporting. **A one-hot standing
in for a missing measurement looks exactly like a strong preference.** Do not
act on that weight until the sensors are closed.

### Three routes past hand-built features

1. **Finish the sensors.** `crit_chance`, `attack_speed`, `damage` buffs and
   `damage_reduction` fold into the existing `raw_dps`/`sustain`. No ML. About
   an hour, and it converts most of the 50. Do this first.
2. **Measure instead of model.** Stop deriving an item's value from its spec.
   Mine it from battles already played: per item type, observed damage dealt,
   throttle rate, and the win-rate difference between racks that held it and
   racks that did not. This captures random procs and unmodelled status
   effects automatically, because it measures outcomes rather than intent, and
   it re-measures itself after every rebalance. Best value of the three.
3. **Learn the item representation.** A learned vector per item type, trained
   from outcomes, with no hand-built sensors at all. 95 items x 8 dims = 760
   parameters, far past what this ES searches, so this is the point where
   gradients start to pay for themselves. Worth it when recipes make
   hand-features hopeless -- not before.

Route 2 gives the linear model good sensors. Route 3 removes the need for
sensors. Note that route 3 is a much stronger argument for a neural network
than the one tested in section 14.

## 14. Does a neural network play better? Measured: no

`train.py --arch mlp` swaps the dot product for one hidden tanh layer. Same
evolution strategy, same features, same turn logic, same budget. Only the
scoring function differs, so the comparison isolates policy capacity.

Gradients are not what makes a network a network -- an ES trains one perfectly
well. So the real cost of the network is SEARCH DIMENSION, not machinery.

```
arm         params     start     final      gain
linear          21    70.6%    96.7%   +26.1%
mlp            135    74.7%    97.5%   +22.8%
```

Both improve enormously against the frozen benchmark. But **that benchmark is
saturated** at 97%, with 3% of headroom left, so a tie there means the ruler
is too short, not that the arms are equal. The discriminating test is the arms
fighting each other, which has no ceiling:

```
linear wins 52.1% of battles against mlp   (per-seed spread 5.4%)
per seed: 55.1%, 47.1%, 46.5%, 52.4%, 59.3%
```

**Verdict: they play equally well.** The extra capacity does not pay for
itself on the game as it stands today.

### Why, and when to revisit

- **The features are already marginal.** `d_cpu_ratio` is the change THIS item
  causes in THIS rack at THIS square, not a property of the item. Context is
  computed into the feature before any weight sees it, so good marginal
  features do much of the work a hidden layer would do.
- **There is little interaction structure to learn yet.** Adjacency never
  fires (section 12) and half the items are 1x1, so packing is near-trivial.
- **A network costs readability.** `is_defense +2.62` is a statement you can
  act on; a weight matrix is not. That readout is a product, not a nicety.
- **A network adds silent failure modes.** The first `MLPBot` bought NOTHING
  and died at round 6: `tanh` output is bounded to +-1 while `buy_threshold`
  is drawn from `gauss(0, 1)`, so the threshold rejected every offer. The fix
  is `bots._LINEAR_SCORE_STD`, a measured calibration of the network's output
  scale to the baseline's. A linear policy cannot fail this way, because its
  weights absorb any scale.

**Revisit when**: adjacency is fixed, item shapes become irregular, or recipes
land -- all three add interaction structure. The cheaper step before a network
is explicit interaction FEATURES in the linear model (`d_dps x cpu_ratio`,
`cost x round_frac`): two lines each, and the weights stay readable.

Escalation order: finish the sensors -> interaction features -> hidden layer
-> MaskablePPO. Do not skip a rung; each one is cheaper than the next and may
end the question.
