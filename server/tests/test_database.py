"""Building the database URL. Everything that connects goes through this."""

from database import get_database_url


def url_with(monkeypatch, base, **overrides):
    """`get_database_url` as it behaves for a given DATABASE_URL.

    No module reload. `get_database_url` reads the environment when it is
    called, so setting the variable is enough -- and reloading `database`
    rebuilds its module-level `DATABASE_URL` and engine from whatever this
    test set, which every test that runs afterwards then connects with.
    """
    monkeypatch.setenv("DATABASE_URL", base)
    return get_database_url(**overrides)


class TestPointingItSomewhereElse:
    def test_a_host_override_keeps_the_password(self, monkeypatch):
        assert (
            url_with(monkeypatch, "postgresql://u:p@h:5432/d", db_host="other:5432")
            == "postgresql://u:p@other:5432/d"
        )

    def test_a_name_override_keeps_the_host(self, monkeypatch):
        assert (
            url_with(monkeypatch, "postgresql://u:p@h:5432/d", db_name="other")
            == "postgresql://u:p@h:5432/other"
        )

    def test_a_url_with_no_password_does_not_grow_one(self, monkeypatch):
        """`urlparse` gives password None, and an f-string writes "None".

        A URL like this would then try to log in with a four-letter password
        and be refused, while every message about it named a host and a
        database that looked exactly right.
        """
        built = url_with(
            monkeypatch,
            "postgresql://appuser@db.internal:5432/app",
            db_host="other:5432",
        )
        assert "None" not in built
        assert built.startswith("postgresql://appuser:@other:5432/")

    def test_nothing_to_override_is_left_alone(self, monkeypatch):
        base = "postgresql://u:p@h:5432/d"
        assert url_with(monkeypatch, base) == base
