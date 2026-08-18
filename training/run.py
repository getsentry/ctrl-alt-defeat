"""
Play a run, and keep what it produces.

A run is the unit of everything here: the bot starts a session, and each round
it shops and then fights, until it runs out of lives or hits the round cap.
Every rack it fought with is snapshotted, tagged with the record it held at
that moment, and handed to the archive.

WHAT A BUILD IS FOR. The product of this project is not a strong bot -- it is
a large, varied set of racks with honest records, so matchmaking can always
find a believable opponent for a player at any point in a run. A build filed
at (round 7, 4 wins, 2 losses) is exactly what a player sitting at that record
should meet. Strength is a means; variety and honest labels are the product.

SURVIVAL MODE. Training plays past the tenth win, to the round cap or until
lives run out. Stopping at 10 caps the objective: once most genomes reach it
they all score exactly 10 and the search cannot rank them. It is also a real
game mode, so the builds stay honest opponents.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

import placement

MAX_ROUNDS = 18
WINS_TO_VICTORY = 10


@dataclass
class Build:
    """One rack, frozen at the moment it fought, with the record it held.

    The record is the LABEL, and it is earned rather than assigned. Nothing
    here rates a build; it simply records where it actually got to.
    """

    round_number: int
    wins: int
    losses: int
    grid: list[dict]
    containers: list[dict]
    generator: str = "unknown"
    item_count: int = 0
    gold_unspent: int = 0
    id: Optional[int] = None

    @classmethod
    def of(cls, session, generator: str) -> "Build":
        return cls(
            round_number=session.round,
            wins=session.wins,
            losses=session.losses,
            grid=[item.model_dump(mode="json") for item in session.inventory_grid],
            containers=[c.model_dump(mode="json") for c in session.server_containers],
            generator=generator,
            item_count=len(session.inventory_grid),
            gold_unspent=session.gold,
        )

    def as_opponent(self) -> dict:
        """The shape MatchmakingService.find_opponent returns (main.py:557-590):
        the handler reads `inventory`, `containers`, `player_name`, `build_id`."""
        return {
            "build_id": self.id,
            "player_name": f"{self.generator}-r{self.round_number}",
            "inventory": self.grid,
            "containers": self.containers,
        }


@dataclass
class RunResult:
    builds: list[Build] = field(default_factory=list)
    wins: int = 0
    losses: int = 0
    final_round: int = 1
    gold_unspent: int = 0
    battles: int = 0
    # (archive build id, did that opponent win) for every fight against a
    # stored build. Without this the archive never learns which of its builds
    # are hard, every PFSP weight stays at the 0.5 default, and prioritised
    # sampling silently becomes uniform -- the mechanism looks present and
    # does nothing.
    opponent_results: list[tuple] = field(default_factory=list)


def play_run(harness, bot, seed: int, user: str = "bot",
             rng: Optional[random.Random] = None,
             opponents=None, survival: bool = True) -> RunResult:
    """One full run through the real server handlers.

    `opponents` is a callable (round_number) -> Build or None. Supply it and
    the bot fights builds you choose -- that is the self-play loop. Leave it
    out and the server picks its own AI opponent, which is what a cold start
    needs before any archive exists.
    """
    rng = rng or random.Random(seed)
    who = harness.user(user)
    result = RunResult()

    served: list = [None]   # the build the handler was last given

    def source(round_number):
        build = opponents(round_number) if opponents else None
        served[0] = build
        return build.as_opponent() if build else None

    harness.opponent_source = source if opponents else None

    session = harness.start_run(who, seed)

    while True:
        if session.lives <= 0 or session.round > MAX_ROUNDS:
            break
        if not survival and session.wins >= WINS_TO_VICTORY:
            break

        try:
            session = bot.take_shop_turn(harness, who, session, rng)
        except Exception:
            session = harness.session(who)   # a broken genome must not kill the run

        if not session.inventory_grid:
            # The server refuses an empty rack (main.py:504). Nothing to do but
            # take the loss, which the handler will not do for us.
            break

        result.builds.append(Build.of(session, bot.name))
        wins_before = session.wins
        served[0] = None
        try:
            harness.battle(who, rng.randrange(2**31))
            result.battles += 1
        except Exception:
            break
        session = harness.session(who)

        # Whether OUR side won is read from the session, not from the battle
        # response, so it agrees with whatever the handler actually recorded.
        opponent = served[0]
        if opponent is not None and opponent.id is not None:
            result.opponent_results.append(
                (opponent.id, session.wins == wins_before))

    result.wins = session.wins
    result.losses = session.losses
    result.final_round = session.round
    result.gold_unspent = session.gold
    harness.opponent_source = None
    return result

