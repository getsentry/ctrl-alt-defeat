"""Emptying the database, so the migrations can build it again."""

import reset_db


class TestWhatItTakesToEmptyIt:
    def test_it_does_nothing_without_being_told_twice(self, capsys):
        # The environment usually points at production, and this is a file
        # somebody can run by typing its name.
        assert reset_db.main([]) == 1
        assert "Nothing done" in capsys.readouterr().out

    def test_it_says_which_database_it_is_about_to_empty(self, capsys, monkeypatch):
        monkeypatch.setenv(
            "DATABASE_URL", "postgresql://someone:hunter2@db.example.com:5433/live")

        reset_db.main([])

        said = capsys.readouterr().out
        assert "db.example.com:5433/live" in said
        assert "hunter2" not in said, "A password must not be printed"
