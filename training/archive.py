"""
The build archive: every rack a bot ever fought with, filed by the record it
earned.

This is the PRODUCT. Training is only the machine that fills it. What
matchmaking needs is a large, varied pool of believable racks with honest
labels, so a player sitting at (round 7, 4 wins, 2 losses) can always be given
an opponent that genuinely reached the same place.

DELIBERATELY A SEPARATE SQLITE FILE. The server uses Postgres through
SQLAlchemy and this touches none of it. The archive is throwaway training
state: delete it and re-run. It is on disk rather than in memory because it
must outlive a training process -- unlike the harness database, which exists
only to keep the server code happy for the length of one run.

WHY THE RECORD IS THE LABEL. Nothing here rates a build by inspection. A build
is filed at the (round, wins, losses) it actually reached, which is a fact
rather than an estimate, and it stays true when the game is rebalanced.
`measure.py` adds a rating on top for finer ordering, but the cell is the
label that matchmaking reads.
"""

from __future__ import annotations

import json
import random
import sqlite3
from pathlib import Path

from run import Build

DEFAULT_PATH = Path(__file__).resolve().parent / "archive.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS builds (
    id            INTEGER PRIMARY KEY,
    round_number  INTEGER NOT NULL,
    wins          INTEGER NOT NULL,
    losses        INTEGER NOT NULL,
    generator     TEXT    NOT NULL,
    generation    INTEGER NOT NULL DEFAULT -1,
    run_id        TEXT    NOT NULL DEFAULT 'legacy',
    item_count    INTEGER NOT NULL,
    gold_unspent  INTEGER NOT NULL,
    grid          TEXT    NOT NULL,
    containers    TEXT    NOT NULL,
    plays         INTEGER NOT NULL DEFAULT 0,
    opp_wins      INTEGER NOT NULL DEFAULT 0,
    rating        REAL    NOT NULL DEFAULT 1200.0
);
-- Sampling is always "a build at this round", so the index has to lead with
-- round_number or every draw becomes a table scan. The archive reaches six
-- figures quickly and ORDER BY RANDOM() over that is ruinous.
CREATE INDEX IF NOT EXISTS builds_cell ON builds (round_number, wins, losses);
CREATE INDEX IF NOT EXISTS builds_round_id ON builds (round_number, id);
"""

# `generation` alone cannot identify where a build came from: every training
# run counts from zero, so run 1's generation 10 and run 3's generation 10 are
# stored identically. Grouping by generation then blends runs together and the
# comparison "is this run better than the last" becomes unanswerable. run_id
# separates them.


class Archive:
    def __init__(self, path=DEFAULT_PATH):
        self.path = str(path)
        self.db = sqlite3.connect(self.path)
        # BY NAME, NEVER BY POSITION. Adding a column moves every index after
        # it, and worse, ALTER TABLE appends while a fresh CREATE puts it in
        # declared order -- so an upgraded database and a new one disagree
        # about what r[6] means. Nothing would raise; the builds would just
        # come back with the wrong fields.
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        self._migrate()

    def _migrate(self) -> None:
        have = {r["name"] for r in self.db.execute("PRAGMA table_info(builds)")}
        if "run_id" not in have:
            self.db.execute("ALTER TABLE builds ADD COLUMN run_id TEXT"
                            " NOT NULL DEFAULT 'legacy'")
            self.db.commit()

    # ------------------------------------------------------------- writing

    def add_many(self, builds: list[Build], generation: int = -1,
                 run_id: str = "unknown") -> int:
        rows = [
            (b.round_number, b.wins, b.losses, b.generator, generation, run_id,
             b.item_count, b.gold_unspent,
             json.dumps(b.grid), json.dumps(b.containers))
            for b in builds if b.item_count > 0   # an empty rack is not an opponent
        ]
        if not rows:
            return 0
        self.db.executemany(
            "INSERT INTO builds (round_number, wins, losses, generator, generation,"
            " run_id, item_count, gold_unspent, grid, containers)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
        return len(rows)

    def record_result(self, build_id: int, opponent_won: bool) -> None:
        """Log how a stored build fared when it was used as an opponent.

        Without this every build weighs the same and PFSP sampling degenerates
        to uniform -- the "fight someone competitive" mechanism goes inert
        while still looking like it works.
        """
        self.db.execute(
            "UPDATE builds SET plays = plays + 1, opp_wins = opp_wins + ?"
            " WHERE id = ?", (1 if opponent_won else 0, build_id))

    def set_rating(self, build_id: int, rating: float) -> None:
        self.db.execute("UPDATE builds SET rating = ? WHERE id = ?",
                        (rating, build_id))

    def commit(self):
        self.db.commit()

    def close(self):
        self.db.commit()
        self.db.close()

    # ------------------------------------------------------------- reading

    def count(self) -> int:
        return self.db.execute("SELECT COUNT(*) FROM builds").fetchone()[0]

    def _rows_to_builds(self, rows) -> list[Build]:
        return [
            Build(round_number=r["round_number"], wins=r["wins"],
                  losses=r["losses"], generator=r["generator"],
                  item_count=r["item_count"], gold_unspent=r["gold_unspent"],
                  grid=json.loads(r["grid"]),
                  containers=json.loads(r["containers"]), id=r["id"])
            for r in rows
        ]

    def sample(self, n: int, rng: random.Random,
               round_number: int | None = None) -> list[Build]:
        """Random builds, optionally at one round.

        Picks by random id within the round rather than ORDER BY RANDOM(),
        which sorts the whole matching set on every single draw.
        """
        if round_number is None:
            rows = self.db.execute(
                "SELECT * FROM builds ORDER BY RANDOM() LIMIT ?", (n,)).fetchall()
            return self._rows_to_builds(rows)

        span = self.db.execute(
            "SELECT MIN(id), MAX(id) FROM builds WHERE round_number = ?",
            (round_number,)).fetchone()
        if span is None or span[0] is None:
            return []

        out = []
        for _ in range(n * 3):
            if len(out) >= n:
                break
            pivot = rng.randint(span[0], span[1])
            row = self.db.execute(
                "SELECT * FROM builds WHERE round_number = ? AND id >= ?"
                " ORDER BY id LIMIT 1", (round_number, pivot)).fetchone()
            if row:
                out.append(row)
        return self._rows_to_builds(out[:n])

    def sample_cell(self, n: int, rng: random.Random, round_number: int,
                    wins: int, losses: int) -> list[Build]:
        """Random builds from ONE (round, wins, losses) cell.

        Rating compares builds within a cell, so it needs this rather than
        sample(round_number=...). Sampling a whole round and discarding the
        rows from other cells throws away four fifths of every draw, which is
        how a 122,000-build archive ended up with 696 rated builds.

        Served by the builds_cell index, and by id pivot rather than
        ORDER BY RANDOM(), which sorts the entire cell on every draw.
        """
        span = self.db.execute(
            "SELECT MIN(id), MAX(id), COUNT(*) FROM builds"
            " WHERE round_number = ? AND wins = ? AND losses = ?",
            (round_number, wins, losses)).fetchone()
        if not span or span[0] is None:
            return []
        low, high, total = span
        if total <= n:
            rows = self.db.execute(
                "SELECT * FROM builds WHERE round_number = ? AND wins = ?"
                " AND losses = ?", (round_number, wins, losses)).fetchall()
            return self._rows_to_builds(rows)

        picked: dict[int, tuple] = {}
        for _ in range(n * 4):
            if len(picked) >= n:
                break
            row = self.db.execute(
                "SELECT * FROM builds WHERE round_number = ? AND wins = ?"
                " AND losses = ? AND id >= ? ORDER BY id LIMIT 1",
                (round_number, wins, losses, rng.randint(low, high))).fetchone()
            if row:
                picked[row[0]] = row
        return self._rows_to_builds(list(picked.values()))

    def sample_pfsp(self, n: int, rng: random.Random,
                    round_number: int | None = None) -> list[Build]:
        """Prioritised sampling: prefer opponents this bot does NOT reliably
        beat, which is where the learning is.

        Uniform sampling wastes most battles on opponents already mastered.
        Weighting by the opponent's win rate concentrates effort on the ones
        that still teach something -- the AlphaStar idea, simplified.
        """
        pool = self.sample(n * 4, rng, round_number)
        if len(pool) <= n:
            return pool
        weights = []
        for b in pool:
            row = self.db.execute(
                "SELECT plays, opp_wins FROM builds WHERE id = ?", (b.id,)).fetchone()
            plays, wins = (row or (0, 0))
            rate = (wins / plays) if plays else 0.5
            weights.append(rate ** 2 + 0.05)   # floor, so nothing is unreachable
        return rng.choices(pool, weights=weights, k=n)

    def cells(self) -> list[tuple]:
        """(round, wins, losses, count) -- how well the table is covered.

        The gaps matter more than the totals: an empty cell is a record a
        player can reach and be given nothing to fight.
        """
        return self.db.execute(
            "SELECT round_number, wins, losses, COUNT(*) FROM builds"
            " GROUP BY round_number, wins, losses ORDER BY 1,2,3").fetchall()

    # ------------------------------------------------------------ exporting

    def export(self, path, per_cell: int = 100) -> int:
        """Write a capped number of builds per (round, wins, losses) cell.

        Capped because the archive is wildly uneven -- early rounds have
        orders of magnitude more builds than late ones -- and shipping it raw
        would give players the same handful of round-14 opponents forever.
        """
        out, seen = [], {}
        for row in self.db.execute(
                "SELECT * FROM builds ORDER BY rating DESC"):
            key = (row["round_number"], row["wins"], row["losses"])
            if seen.get(key, 0) >= per_cell:
                continue
            seen[key] = seen.get(key, 0) + 1
            out.append({
                "round_number": row["round_number"], "wins": row["wins"],
                "losses": row["losses"], "generator": row["generator"],
                "rating": row["rating"], "run_id": row["run_id"],
                "inventory": json.loads(row["grid"]),
                "containers": json.loads(row["containers"]),
            })
        Path(path).write_text(json.dumps(out))
        return len(out)
