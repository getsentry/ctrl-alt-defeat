"""How much the game is being played, counted from what it already writes.

Nothing here is instrumentation added for the purpose. A run leaves a
`game_sessions` row with the time of its last move on it, a finished run
stamps `finished_at`, a battle leaves a `battle_history` row, and an account
is only made when somebody presses New Game -- so the counts below come from
asking those three tables the right questions.

That last point is what makes any of it worth reading. The client signs in
from `start_session`, not on page load, so an account means somebody started
a run rather than merely opened the page. And it keeps its token in browser
storage, so the same person coming back tomorrow is the same account: new
accounts are new people, near enough.

One thing the tables do not hold: a history of runs. `game_sessions.user_id`
is unique, so a player has one row and starting again resets it in place --
the row is where their run is now, not a record of the runs they have had.
So a run is counted where a finished one is actually banked, on the player:
`users.total_games_played`, which `session_manager` raises when it pays out.
`game_sessions.round` is still worth reading, as where everybody's latest run
stands, and `battle_history` is the one table that really does keep a row per
thing that happened.

Mostly counts: what is being asked is whether anybody is out there. `recent()`
is the one thing here that reads a name, and a name is the handle somebody
typed on a menu -- no account id, no token, no address.
"""

from dataclasses import asdict, dataclass, field
from datetime import timedelta
from typing import Dict, List

from sqlalchemy import func, select

from models import BattleHistory, GameSession, User
from utils import utc_now

#: How far back "lately" reaches, and what each window is called on the page.
WINDOWS = {"hour": timedelta(hours=1), "day": timedelta(days=1),
           "week": timedelta(days=7)}

#: A run is ten rounds. Anything past that is a run that won.
ROUNDS = 10


@dataclass
class Player:
    """One person's latest run, as a page would list it.

    A name is whatever they typed on the menu -- most of them are "Player" --
    and it is the only thing here that is theirs. No account id, no token, no
    address: enough to see that somebody was here and how they got on.
    """

    name: str
    round: int
    wins: int
    losses: int
    started: str
    last_seen: str
    finished: bool


@dataclass
class Stats:
    """What the tables say, as a page would read it out"""

    #: When this was asked, so a page can say how fresh it is.
    taken_at: str = ""

    players: Dict[str, int] = field(default_factory=dict)
    runs: Dict[str, int] = field(default_factory=dict)
    battles: Dict[str, int] = field(default_factory=dict)

    #: Where each player's latest run stands, a round at a time. The shape of
    #: this is the question "does anybody get to the end", answered.
    reached: List[Dict[str, int]] = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)


async def _count(db, table, column, since=None) -> int:
    """How many rows, optionally only the recent ones"""
    query = select(func.count()).select_from(table)
    if since is not None:
        query = query.where(column >= since)
    return int((await db.execute(query)).scalar() or 0)


async def recent(db, limit: int = 50) -> List[Player]:
    """The people who played most recently, latest first.

    One row each, because that is all the schema keeps: a player has one
    session, reset when they start again, so this is where each of them got
    to rather than everything they have ever done.
    """
    rows = await db.execute(
        select(GameSession.player_name, GameSession.round, GameSession.wins,
               GameSession.losses, GameSession.created_at,
               GameSession.last_activity, GameSession.finished_at)
        .order_by(GameSession.last_activity.desc())
        .limit(max(1, min(limit, 200)))
    )
    return [
        Player(
            name=row[0] or "Player",
            round=int(row[1]),
            wins=int(row[2]),
            losses=int(row[3]),
            started=row[4].isoformat(),
            last_seen=row[5].isoformat(),
            finished=row[6] is not None,
        )
        for row in rows.all()
    ]


async def gather(db) -> Stats:
    """Ask the three tables how the game is going"""
    now = utc_now()
    stats = Stats(taken_at=now.isoformat())

    # Everyone who has ever started a run, and how many of those are recent.
    stats.players["total"] = await _count(db, User, User.created_at)
    for name, window in WINDOWS.items():
        stats.players[f"new_this_{name}"] = await _count(
            db, User, User.created_at, now - window)

    # Somebody is playing if their run has moved lately. `last_activity` is
    # stamped by the moves themselves, so this is people, not open tabs.
    for name, window in WINDOWS.items():
        playing = select(func.count(func.distinct(GameSession.user_id))).where(
            GameSession.last_activity >= now - window)
        stats.players[f"playing_this_{name}"] = int(
            (await db.execute(playing)).scalar() or 0)

    # Somebody who started a run today, having made their account before
    # today: the number that says whether anybody came back.
    returned = select(func.count(func.distinct(GameSession.user_id))).select_from(
        GameSession).join(User, User.id == GameSession.user_id).where(
            GameSession.last_activity >= now - WINDOWS["day"],
            User.created_at < now - WINDOWS["day"])
    stats.players["returned_this_day"] = int(
        (await db.execute(returned)).scalar() or 0)

    # A run in hand: a row that has not been paid out yet.
    going = select(func.count()).select_from(GameSession).where(
        GameSession.finished_at.is_(None))
    stats.runs["in_hand"] = int((await db.execute(going)).scalar() or 0)

    for name, window in WINDOWS.items():
        stats.runs[f"begun_this_{name}"] = await _count(
            db, GameSession, GameSession.created_at, now - window)

    # Finished runs are counted on the player, because the session row is
    # reset in place when they start again and would forget every run but the
    # last. This is the number `session_manager` raises when it pays one out.
    played = select(func.coalesce(func.sum(User.total_games_played), 0))
    stats.runs["played_to_the_end"] = int((await db.execute(played)).scalar() or 0)

    # And of the runs standing now, the ones that went the distance.
    won = select(func.count()).select_from(GameSession).where(
        GameSession.wins >= ROUNDS)
    stats.runs["won"] = int((await db.execute(won)).scalar() or 0)

    stats.battles["total"] = await _count(
        db, BattleHistory, BattleHistory.created_at)
    for name, window in WINDOWS.items():
        stats.battles[f"fought_this_{name}"] = await _count(
            db, BattleHistory, BattleHistory.created_at, now - window)

    # And where those runs stand, which is the answer with the most in it: a
    # column of ones at round 1 is a game nobody is finishing.
    rounds = select(GameSession.round, func.count()).group_by(
        GameSession.round).order_by(GameSession.round)
    stats.reached = [
        {"round": int(row[0]), "runs": int(row[1])}
        for row in (await db.execute(rounds)).all()
    ]

    return stats
