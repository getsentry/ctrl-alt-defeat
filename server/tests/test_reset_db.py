"""Emptying the database, so the migrations can build it again."""

import reset_db


class TestWhatItTakesToEmptyIt:
    def test_it_does_nothing_without_being_told_twice(self, capsys):
        # The environment usually points at production, and this is a file
        # somebody can run by typing its name.
        assert reset_db.main([]) == 1
        assert "Nothing done" in capsys.readouterr().out

    def test_it_says_which_database_it_is_about_to_empty(self, capsys, monkeypatch):
        # DB_HOST and DB_NAME are overrides laid on top of DATABASE_URL, and
        # the test suite sets both. Cleared here so the URL is what decides.
        monkeypatch.delenv("DB_HOST", raising=False)
        monkeypatch.delenv("DB_NAME", raising=False)
        monkeypatch.setenv(
            "DATABASE_URL", "postgresql://someone:hunter2@db.example.com:5433/live"
        )

        reset_db.main([])

        said = capsys.readouterr().out
        assert "db.example.com:5433/live" in said
        assert "hunter2" not in said, "A password must not be printed"

    def test_db_name_steers_it_like_it_steers_the_server(self, capsys, monkeypatch):
        """The one file whose job is destructive has to be aimable.

        `get_database_url()` called bare ignores DB_HOST and DB_NAME and hands
        back the default, which is the developer's own database. Everything
        else -- `database.py`, `alembic/env.py`, the test suite -- is pointed
        with those two, so this was the only place that could not be pointed
        away, and `DB_NAME=somewhere_else reset_db.py --yes` emptied the
        default instead.
        """
        monkeypatch.setenv(
            "DATABASE_URL", "postgresql://someone:hunter2@db.example.com:5433/live"
        )
        monkeypatch.setenv("DB_NAME", "somewhere_else")

        reset_db.main([])

        assert "/somewhere_else" in capsys.readouterr().out
