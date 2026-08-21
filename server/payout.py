"""What the end of a run pays, in SnubaCoin.

Section 5.5 of the Game Design Document. The arithmetic is here rather than in
the endpoint because the breakdown is part of the answer: the client draws a
banner for each line and flies that line's icons into the crate, so "20" on its
own is not enough to show the payout with.

Nothing here touches the database. The rules are worth testing on their own,
and the exploit the abandoned rule closes is arithmetic rather than storage.
"""

from typing import List

from pydantic import BaseModel, Field

#: Wins that win a run.
WINS_TO_WIN_RUN = 10

#: Tries a run starts with.
STARTING_TRIES = 5

#: For finishing a run at all, either way.
FOR_FINISHING = 3

#: For each win banked.
PER_WIN = 1

#: For each try never spent.
PER_TRY_LEFT = 1

#: On top, for winning the run.
FOR_WINNING = 5


class PayoutLine(BaseModel):
    """One thing the run is paid for, and what it is worth."""

    reason: str = Field(
        description=(
            "Which line this is: run_complete, wins, tries_left or run_won. "
            "The client turns it into a banner, so it is a key and not a "
            "sentence."
        )
    )
    count: int = Field(
        description=(
            "How many icons this line flies -- trophies for wins, hearts for "
            "tries. 1 for the lines that are a flat amount, because a banner "
            "with nothing on the bar to fly still pays a coin."
        )
    )
    coin: int = Field(description="SnubaCoin this line pays")


class Payout(BaseModel):
    """What a run paid, and what for."""

    lines: List[PayoutLine] = Field(
        default_factory=list,
        description="Paid in this order, one banner at a time",
    )
    total: int = Field(default=0, description="SnubaCoin the whole run paid")


def _payout(lines: List[PayoutLine]) -> Payout:
    """A payout from its lines, dropping the ones worth nothing.

    A line worth nothing is a banner that says "0 TRIES LEFT" and flies no
    icons, which is slower than not showing it.
    """
    kept = [line for line in lines if line.coin > 0]
    return Payout(lines=kept, total=sum(line.coin for line in kept))


def for_finished_run(wins: int, tries_left: int) -> Payout:
    """What a run that reached its end pays.

    `tries_left` is the lives still on the counter, so a run lost on the last
    try passes 0 and a run won without ever losing passes all of them.
    """
    won = wins >= WINS_TO_WIN_RUN
    return _payout(
        [
            PayoutLine(reason="run_complete", count=1, coin=FOR_FINISHING),
            PayoutLine(reason="wins", count=wins, coin=wins * PER_WIN),
            PayoutLine(
                reason="tries_left",
                count=tries_left,
                coin=tries_left * PER_TRY_LEFT,
            ),
            PayoutLine(
                reason="run_won",
                count=1,
                coin=FOR_WINNING if won else 0,
            ),
        ]
    )


def for_abandoned_run(wins: int) -> Payout:
    """What a run the player walked away from pays.

    Wins and nothing else. Give an abandoned run the whole table and quitting
    at round 1 with five tries unspent pays 3 + 0 + 5 = 8, while genuinely
    losing on two wins pays 3 + 2 + 0 = 5 -- quitting would beat playing. Wins
    are the only line a player cannot collect by giving up early, so wins are
    the only line this pays.
    """
    return _payout([PayoutLine(reason="wins", count=wins, coin=wins * PER_WIN)])


def run_was_won(wins: int) -> bool:
    """Whether the run reached its target."""
    return wins >= WINS_TO_WIN_RUN


def run_was_lost(lives: int) -> bool:
    """Whether the run spent its last try."""
    return lives <= 0


def run_is_over(wins: int, lives: int) -> bool:
    """Whether a run has ended, either way.

    Both endings, in one place, and said once. The two used to be worked out
    separately wherever they were wanted, and the client read only the losing
    one -- so a won run went quietly back to the shop for round 11.
    """
    return run_was_won(wins) or run_was_lost(lives)
