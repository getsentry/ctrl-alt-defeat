"""How much the game is being played, counted from what it already writes."""

from datetime import timedelta

import pytest
import stats
from models import BattleHistory, GameSession, User
from utils import utc_now


async def _a_player(db, made_at=None) -> User:
    """Somebody who pressed New Game, at some point"""
    user = User(
        username=f"Guest_{utc_now().timestamp()}_{id(db) % 10000}",
        account_type="guest",
        account_status="active",
        created_at=made_at or utc_now(),
    )
    db.add(user)
    await db.flush()
    return user


async def _a_run(db, user, started=None, active=None, round_reached=1,
                 wins=0, finished=False) -> GameSession:
    when = started or utc_now()
    run = GameSession(
        player_id=f"run_{user.id}_{when.timestamp()}",
        player_name="Player",
        user_id=user.id,
        game_seed=1,
        round=round_reached,
        wins=wins,
        created_at=when,
        last_activity=active or when,
        finished_at=utc_now() if finished else None,
    )
    db.add(run)
    await db.flush()
    return run


class TestWhatTheCountsSay:
    """The counts are read as differences.

    The run has a database of its own, but the tests in it still share one,
    so what a test can say for certain is what its own rows changed.
    """

    @pytest.mark.asyncio
    async def test_a_player_who_did_nothing_is_a_player_and_no_runs(
            self, transactional_db):
        async with transactional_db() as db:
            before = await stats.gather(db)
            await _a_player(db)
            after = await stats.gather(db)

        assert after.players["total"] == before.players["total"] + 1
        assert after.runs["in_hand"] == before.runs["in_hand"], "and no run yet"

    @pytest.mark.asyncio
    async def test_somebody_who_played_an_hour_ago_is_not_playing_now(
            self, transactional_db):
        long_ago = utc_now() - timedelta(hours=3)
        async with transactional_db() as db:
            before = await stats.gather(db)
            player = await _a_player(db, made_at=long_ago)
            await _a_run(db, player, started=long_ago, active=long_ago)
            after = await stats.gather(db)

        assert after.players["playing_this_hour"] == before.players[
            "playing_this_hour"], "Three hours ago is not now"
        assert after.players["playing_this_day"] == before.players[
            "playing_this_day"] + 1, "but it is today"

    @pytest.mark.asyncio
    async def test_two_people_playing_are_two_people(self, transactional_db):
        # A player cannot have two runs at once -- `game_sessions.user_id` is
        # unique, and starting again resets the row they have.
        async with transactional_db() as db:
            before = await stats.gather(db)
            await _a_run(db, await _a_player(db))
            await _a_run(db, await _a_player(db))
            after = await stats.gather(db)

        assert after.players["playing_this_day"] == before.players[
            "playing_this_day"] + 2
        assert after.runs["begun_this_day"] == before.runs["begun_this_day"] + 2

    @pytest.mark.asyncio
    async def test_coming_back_is_counted_apart_from_arriving(
            self, transactional_db):
        # The number that says whether the game is worth returning to.
        days_ago = utc_now() - timedelta(days=3)
        async with transactional_db() as db:
            before = await stats.gather(db)
            returning = await _a_player(db, made_at=days_ago)
            await _a_run(db, returning)
            await _a_player(db)  # here for the first time today
            after = await stats.gather(db)

        assert after.players["returned_this_day"] == before.players[
            "returned_this_day"] + 1
        assert after.players["new_this_day"] == before.players["new_this_day"] + 1

    @pytest.mark.asyncio
    async def test_a_finished_run_is_counted_on_the_player(self, transactional_db):
        # Not on the session row, which is reset when they start again and
        # would forget every run but the last.
        async with transactional_db() as db:
            before = await stats.gather(db)
            player = await _a_player(db)
            player.total_games_played = 3
            await _a_run(db, player, round_reached=11, wins=stats.ROUNDS,
                         finished=True)
            after = await stats.gather(db)

        assert after.runs["played_to_the_end"] == before.runs[
            "played_to_the_end"] + 3, "Three runs banked, one row"
        assert after.runs["won"] == before.runs["won"] + 1, "and this one won"
        assert after.runs["in_hand"] == before.runs["in_hand"], \
            "a paid-out run is not in hand"

    @pytest.mark.asyncio
    async def test_where_the_runs_stand_is_counted_a_round_at_a_time(
            self, transactional_db):
        async with transactional_db() as db:
            before = {row["round"]: row["runs"] for row in
                      (await stats.gather(db)).reached}
            for reached in (1, 1, 5):
                await _a_run(db, await _a_player(db), round_reached=reached)
            after = {row["round"]: row["runs"] for row in
                     (await stats.gather(db)).reached}

        assert after[1] == before.get(1, 0) + 2
        assert after[5] == before.get(5, 0) + 1

    @pytest.mark.asyncio
    async def test_battles_are_counted_by_when_they_were_fought(
            self, transactional_db):
        async with transactional_db() as db:
            before = await stats.gather(db)
            db.add(BattleHistory(player1_id="a", round_number=1, winner=1,
                                 battle_data={}, created_at=utc_now()))
            db.add(BattleHistory(player1_id="a", round_number=2, winner=2,
                                 battle_data={},
                                 created_at=utc_now() - timedelta(days=9)))
            await db.flush()
            after = await stats.gather(db)

        assert after.battles["total"] == before.battles["total"] + 2
        assert after.battles["fought_this_day"] == before.battles[
            "fought_this_day"] + 1, "Nine days ago is not today"
        assert after.battles["fought_this_week"] == before.battles[
            "fought_this_week"] + 1, "nor this week"


class TestThePage:
    @pytest.mark.asyncio
    async def test_it_says_the_numbers_it_was_given(self, transactional_db):
        import stats_page

        async with transactional_db() as db:
            player = await _a_player(db)
            await _a_run(db, player, round_reached=3)
            page = stats_page.render(await stats.gather(db))

        assert "Who is playing" in page
        assert "<html" in page and "</html>" in page

    def test_a_round_nobody_reached_is_still_drawn(self):
        import stats_page

        # The gaps are the point: a chart that skips them reads as though
        # nobody stopped there.
        drawn = stats_page._bars([{"round": 1, "runs": 4}])

        assert drawn.count('class="bar"') == stats.ROUNDS

    def test_it_says_nothing_rather_than_dividing_by_zero(self):
        import stats_page

        assert "No runs yet" in stats_page._bars([])


class TestWhoMayRead:
    """The counts are nobody else's business unless the server says so.

    Unset, which is how a developer's own server runs, and they are open. Set
    in the deployment, and a page that answers "is this game being played"
    stops answering it for everyone.
    """

    def test_open_when_no_token_is_configured(self, monkeypatch):
        import main

        monkeypatch.setattr(main, "STATS_TOKEN", "")

        assert main._may_read_stats("")
        assert main._may_read_stats("anything")

    def test_shut_when_one_is(self, monkeypatch):
        import main

        monkeypatch.setattr(main, "STATS_TOKEN", "letmein")

        assert main._may_read_stats("letmein")
        assert not main._may_read_stats("")
        assert not main._may_read_stats("letmeout")
