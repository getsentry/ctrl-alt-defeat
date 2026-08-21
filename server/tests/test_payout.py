"""What the end of a run pays. Section 5.5 of the Game Design Document."""

from payout import (
    FOR_FINISHING,
    FOR_WINNING,
    STARTING_TRIES,
    WINS_TO_WIN_RUN,
    for_abandoned_run,
    for_finished_run,
    run_is_over,
)


def coin_for(payout, reason):
    """What one line of `payout` paid, or 0 if it is not there."""
    for line in payout.lines:
        if line.reason == reason:
            return line.coin
    return 0


class TestAFinishedRun:
    def test_the_two_worked_examples_from_the_document(self):
        # A lost run on two wins and no tries pays 5.
        assert for_finished_run(wins=2, tries_left=0).total == 5
        # A won run with two tries left pays 20.
        assert for_finished_run(wins=10, tries_left=2).total == 20

    def test_finishing_pays_even_with_nothing_to_show(self):
        paid = for_finished_run(wins=0, tries_left=0)
        assert paid.total == FOR_FINISHING

    def test_every_win_is_worth_one(self):
        assert for_finished_run(wins=4, tries_left=0).total - FOR_FINISHING == 4

    def test_every_try_left_is_worth_one(self):
        assert for_finished_run(wins=0, tries_left=3).total - FOR_FINISHING == 3

    def test_winning_the_run_pays_its_own_bonus(self):
        won = for_finished_run(wins=WINS_TO_WIN_RUN, tries_left=0)
        assert coin_for(won, "run_won") == FOR_WINNING

    def test_a_run_short_of_the_target_gets_no_bonus(self):
        nearly = for_finished_run(wins=WINS_TO_WIN_RUN - 1, tries_left=0)
        assert coin_for(nearly, "run_won") == 0

    def test_the_lines_add_up_to_the_total(self):
        paid = for_finished_run(wins=10, tries_left=2)
        assert sum(line.coin for line in paid.lines) == paid.total

    def test_a_line_worth_nothing_is_not_shown(self):
        """A banner saying "0 TRIES LEFT" with nothing to fly is just a wait."""
        paid = for_finished_run(wins=3, tries_left=0)
        assert [line.reason for line in paid.lines] == ["run_complete", "wins"]

    def test_the_lines_come_in_the_order_they_are_paid(self):
        paid = for_finished_run(wins=10, tries_left=2)
        assert [line.reason for line in paid.lines] == [
            "run_complete",
            "wins",
            "tries_left",
            "run_won",
        ]

    def test_a_line_counts_the_icons_that_fly(self):
        paid = for_finished_run(wins=7, tries_left=2)
        assert coin_for(paid, "wins") == 7
        assert [line.count for line in paid.lines if line.reason == "wins"] == [7]
        assert [line.count for line in paid.lines if line.reason == "tries_left"] == [2]


class TestAnAbandonedRun:
    def test_it_pays_for_its_wins(self):
        assert for_abandoned_run(wins=3).total == 3

    def test_it_pays_nothing_else(self):
        paid = for_abandoned_run(wins=3)
        assert [line.reason for line in paid.lines] == ["wins"]

    def test_walking_away_early_pays_nothing(self):
        assert for_abandoned_run(wins=0).total == 0

    def test_quitting_never_beats_playing(self):
        """The reason abandoning pays for wins alone.

        Give an abandoned run the whole table and the worst way to play -- quit
        at round one, having done nothing -- would out-earn actually losing a
        run, because the tries are all still there to be counted.
        """
        quit_at_once = for_abandoned_run(wins=0).total
        played_badly = for_finished_run(wins=2, tries_left=0).total
        assert quit_at_once < played_badly

        whole_table_if_it_applied = for_finished_run(
            wins=0, tries_left=STARTING_TRIES
        ).total
        assert whole_table_if_it_applied > played_badly


class TestWhenARunIsOver:
    def test_the_last_try_spent_ends_it(self):
        assert run_is_over(wins=3, lives=0)

    def test_the_target_reached_ends_it(self):
        assert run_is_over(wins=WINS_TO_WIN_RUN, lives=4)

    def test_a_run_in_progress_is_not_over(self):
        assert not run_is_over(wins=WINS_TO_WIN_RUN - 1, lives=1)

    def test_winning_counts_as_over(self):
        """The bug this function exists to stop.

        `game_over` and `victory` were two flags and the client read only the
        first, so a won run went quietly back to the shop for round 11.
        """
        assert run_is_over(wins=WINS_TO_WIN_RUN, lives=STARTING_TRIES)
