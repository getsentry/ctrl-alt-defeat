"""Counting a won run on the account, as it ends."""

import pytest
from models import GameSession, User
from payout import WINS_TO_WIN_RUN
from session_manager import SessionManager
from utils import utc_now


async def _a_run_that_ended(db, wins: int, lives: int) -> User:
    user = User(username=f"Guest_{utc_now().timestamp()}_{wins}_{lives}",
                account_type="guest", account_status="active")
    db.add(user)
    await db.flush()
    db.add(GameSession(
        player_id=f"run_{user.id}", player_name="Player", user_id=user.id,
        game_seed=1, round=wins + 1, wins=wins, losses=0, lives=lives))
    await db.flush()
    return user


class TestCountingAWonRun:
    """The session row cannot answer this afterwards -- the next run writes
    over it -- so it is counted as the run ends.
    """

    @pytest.mark.asyncio
    async def test_a_run_that_went_the_distance_is_counted_as_won(
            self, transactional_db):
        async with transactional_db() as db:
            user = await _a_run_that_ended(db, wins=WINS_TO_WIN_RUN, lives=3)
            await SessionManager().finish_run(f"run_{user.id}")
            await db.refresh(user)

        assert user.total_runs_won == 1
        assert user.total_games_played == 1

    @pytest.mark.asyncio
    async def test_a_run_that_ran_out_of_tries_is_played_but_not_won(
            self, transactional_db):
        async with transactional_db() as db:
            user = await _a_run_that_ended(db, wins=2, lives=0)
            await SessionManager().finish_run(f"run_{user.id}")
            await db.refresh(user)

        assert user.total_runs_won == 0
        assert user.total_games_played == 1, "played, and lost"
