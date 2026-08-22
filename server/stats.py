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
from typing import Dict, List, Optional

from sqlalchemy import case, func, or_, select

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

    #: The run they are in: where it has got to, and its record so far.
    round: int
    wins: int
    losses: int

    #: And the account behind it. `runs` counts runs played to the end -- a
    #: run walked away from pays out but is not counted as one played -- and
    #: `runs_won` how many of those went the distance.
    #:
    #: The battle record is counted from `battle_history`, a row per battle,
    #: so it is every battle this player has ever fought and the run above is
    #: in it. Not from the totals on the account: those are added up as a run
    #: is paid out, so a run still being played counts for nothing until it
    #: ends, and somebody at 4-4 in round nine reads 0-0.
    runs: int
    runs_won: int
    battles_won: int
    battles_lost: int

    started: str
    last_seen: str
    finished: bool

    @property
    def win_rate(self) -> int:
        fought = self.battles_won + self.battles_lost
        return 0 if fought == 0 else int(self.battles_won / fought * 100)


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

    #: And how far runs get in general, over every run that is over: the share
    #: that reached each round, and the share that won that many battles.
    how_far: Dict[str, object] = field(default_factory=dict)

    #: The same shape asked of people rather than runs: the furthest each
    #: player has ever got, so a run that went badly is not held against
    #: somebody who has had a good one.
    best: Dict[str, object] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return asdict(self)


async def _count(db, table, column, since=None) -> int:
    """How many rows, optionally only the recent ones"""
    query = select(func.count()).select_from(table)
    if since is not None:
        query = query.where(column >= since)
    return int((await db.execute(query)).scalar() or 0)


async def _battles_fought(db, players: List[str]) -> Dict[str, Dict[str, int]]:
    """How many battles each of these players has fought, and won.

    One question for the whole page rather than one per row. `player1_id` is
    the account id and the player is always player one, so a player's battles
    are all under the one key however many runs they span.
    """
    if not players:
        return {}

    won = func.count().filter(BattleHistory.winner == 1)
    lost = func.count().filter(BattleHistory.winner != 1)
    rows = await db.execute(
        select(BattleHistory.player1_id, won, lost)
        .where(BattleHistory.player1_id.in_(players))
        .group_by(BattleHistory.player1_id)
    )
    return {row[0]: {"won": int(row[1]), "lost": int(row[2])}
            for row in rows.all()}


def _run_by_run(players: Optional[List[str]] = None):
    """One row per run, worked out from the order of the battles.

    Nothing keeps a run. `game_sessions` is written over when somebody starts
    again, and `battle_history` has no run of its own to point at -- but it
    has the round each battle was fought in, and rounds climb through a run
    and start again at one. So a battle whose round is no higher than the one
    before it is the first battle of a new run.

    What comes back is the player, which of their runs it was, how many
    battles it fought and how many it won, and when it last did anything.
    Worked out rather than recorded, so it says what it can: a run nobody
    fought a battle in is not here, and neither is anything from before the
    database was last emptied.
    """
    within = {"partition_by": BattleHistory.player1_id,
              "order_by": (BattleHistory.created_at, BattleHistory.id)}
    battles = select(
        BattleHistory.player1_id.label("player"),
        BattleHistory.created_at.label("at"),
        BattleHistory.id.label("row"),
        BattleHistory.winner.label("winner"),
        BattleHistory.round_number.label("round"),
        func.lag(BattleHistory.round_number).over(**within).label("before"),
    )
    if players is not None:
        battles = battles.where(BattleHistory.player1_id.in_(players))
    battles = battles.subquery()

    starts_a_run = case(
        (or_(battles.c.before.is_(None), battles.c.round <= battles.c.before), 1),
        else_=0)
    numbered = select(
        battles.c.player,
        battles.c.winner,
        battles.c.at,
        func.sum(starts_a_run).over(
            partition_by=battles.c.player,
            order_by=(battles.c.at, battles.c.row)).label("run"),
    ).subquery()

    return select(
        numbered.c.player,
        numbered.c.run,
        func.count().label("rounds"),
        func.count().filter(numbered.c.winner == 1).label("wins"),
    ).group_by(numbered.c.player, numbered.c.run).subquery()


async def _runs_fought(db, players: List[str]) -> Dict[str, Dict[str, int]]:
    """How many runs each of these players has had, and how many they won.

    A run with ten wins in it is a run that went the distance.
    """
    if not players:
        return {}

    each_run = _run_by_run(players)
    rows = await db.execute(
        select(each_run.c.player, func.count(),
               func.count().filter(each_run.c.wins >= ROUNDS))
        .group_by(each_run.c.player))
    return {row[0]: {"runs": int(row[1]), "won": int(row[2])}
            for row in rows.all()}


async def _every_run(db) -> List[Dict[str, int]]:
    """Every run the history remembers, as how far it got.

    The run somebody is in the middle of is in here too, counted where it
    stands. It drags the lines down while it is being played, which is the
    point: most runs that stop being played are never finished, they are
    walked away from, and a chart that waited for a payout would never show
    those at all.
    """
    each_run = _run_by_run()
    rows = (await db.execute(
        select(each_run.c.rounds, each_run.c.wins))).all()
    return [{"rounds": int(row[0]), "wins": int(row[1])} for row in rows]


async def _the_best_each_player_managed(db) -> List[Dict[str, int]]:
    """The furthest each player has ever got, one row each.

    A different question from how far runs get, and the answer to a kinder
    one: not what happens to a run, but what a person has managed. The run
    they are in the middle of counts, as it does everywhere on this page --
    somebody standing at round nine right now has got to round nine.

    The furthest round and the most wins are asked separately, because they
    are separate questions and need not have happened in the same run.
    """
    each_run = _run_by_run()
    rows = (await db.execute(
        select(each_run.c.player,
               func.max(each_run.c.rounds), func.max(each_run.c.wins))
        .group_by(each_run.c.player))).all()
    return [{"rounds": int(row[1]), "wins": int(row[2])} for row in rows]


def how_far(runs: List[Dict[str, int]]) -> Dict[str, object]:
    """How far runs get, as a page would draw it.

    Two questions of the same runs, so they are answered on one scale: of the
    runs that are over, the share that fought at least N rounds, and the share
    that won at least N battles. Read across, the gap between the two lines is
    how much of a run is spent losing.

    A share of runs that got at least this far, rather than a count that
    stopped exactly here, because that is the question somebody asks of a
    chart like this -- how far do runs get -- and because it is the one shape
    that cannot be read as a spike where a round happens to be popular.
    """
    if not runs:
        return {"runs": 0, "rounds": [], "wins": [], "middle": {}}

    rounds = sorted(run["rounds"] for run in runs)
    wins = sorted(run["wins"] for run in runs)
    total = len(runs)
    furthest = max(max(rounds), ROUNDS)

    def share(counted: List[int], step: int) -> int:
        return round(sum(1 for one in counted if one >= step) / total * 100)

    def middle(counted: List[int], part: float) -> int:
        """The value the run this far along the order got to"""
        return counted[min(len(counted) - 1, int(len(counted) * part))]

    return {
        "runs": total,
        "rounds": [{"step": step, "share": share(rounds, step)}
                   for step in range(1, furthest + 1)],
        "wins": [{"step": step, "share": share(wins, step)}
                 for step in range(1, ROUNDS + 1)],
        "middle": {
            "rounds": middle(rounds, 0.5), "wins": middle(wins, 0.5),
            "rounds_top": middle(rounds, 0.9), "wins_top": middle(wins, 0.9),
        },
    }


async def recent(db, limit: int = 50) -> List[Player]:
    """The people who played most recently, latest first.

    One row each, because that is all the schema keeps: a player has one
    session, reset when they start again, so the run on the row is where they
    are now, not where they have been. Everything behind it -- how many runs,
    how many battles -- is asked of `battle_history`, the one table that keeps
    a row per thing that happened. The account carries totals of its own, but
    they are only added to as a run is paid out, so a run being played counts
    for nothing until it ends.
    """
    rows = (await db.execute(
        select(GameSession.player_name, GameSession.round, GameSession.wins,
               GameSession.losses, GameSession.created_at,
               GameSession.last_activity, GameSession.finished_at,
               GameSession.player_id)
        .join(User, User.id == GameSession.user_id)
        .order_by(GameSession.last_activity.desc())
        .limit(max(1, min(limit, 200)))
    )).all()

    played = [row[7] for row in rows]
    fought = await _battles_fought(db, played)
    had = await _runs_fought(db, played)
    no_battles = {"won": 0, "lost": 0}
    no_runs = {"runs": 0, "won": 0}
    return [
        Player(
            name=row[0] or "Player",
            round=int(row[1]),
            wins=int(row[2]),
            losses=int(row[3]),
            runs=had.get(row[7], no_runs)["runs"],
            runs_won=had.get(row[7], no_runs)["won"],
            battles_won=fought.get(row[7], no_battles)["won"],
            battles_lost=fought.get(row[7], no_battles)["lost"],
            started=row[4].isoformat(),
            last_seen=row[5].isoformat(),
            finished=row[6] is not None,
        )
        for row in rows
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

    # And the same question of every run there has been, rather than of the
    # one each player is in now.
    stats.how_far = how_far(await _every_run(db))
    stats.best = how_far(await _the_best_each_player_managed(db))

    return stats
