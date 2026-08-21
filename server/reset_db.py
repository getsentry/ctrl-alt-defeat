"""Empty the database, so the migrations can build it again.

Alembic cannot do this on its own where the schema was built by `create_all`
and never stamped: with no `alembic_version` row, `downgrade base` believes
there is nothing to undo and returns without dropping a table, and the
`upgrade head` that follows falls over the tables that are still there --

    asyncpg.exceptions.DuplicateTableError: relation "battle_history"
    already exists

which is a database that can never be migrated again. Emptying it is the way
out: what `alembic upgrade head` then builds is stamped as it goes, because
the upgrade is doing the building.

Every table is dropped rather than the schema itself. A managed Postgres
hands out a user that owns its tables and not always the `public` schema, and
`DROP SCHEMA` from a user who does not own it fails on a permission the
addon will not give us.

    python reset_db.py --yes && alembic upgrade head && alembic current

The flag is not ceremony. This is a file that empties whatever database the
environment points at, and the environment usually points at production.
"""

import argparse
import asyncio
import os
import sys
from urllib.parse import urlparse

import asyncpg
from database import get_database_url, parse_asyncpg_url


def where_it_points(url: str) -> str:
    """The database this would empty, said without its password"""
    parsed = urlparse(url)
    return f"{parsed.hostname}:{parsed.port or 5432}{parsed.path}"


async def empty(url: str) -> list:
    """Drop every table in the database, and say which ones went.

    CASCADE because the tables reference each other, and a drop order that
    respects five foreign keys is a drop order to keep up to date. Sequences
    and indexes go with the tables that own them.
    """
    clean_url, connect_args = parse_asyncpg_url(url)
    connection = await asyncpg.connect(clean_url, **connect_args)
    try:
        rows = await connection.fetch(
            "SELECT tablename FROM pg_tables WHERE schemaname = current_schema()"
        )
        names = sorted(row["tablename"] for row in rows)
        for name in names:
            await connection.execute(f'DROP TABLE IF EXISTS "{name}" CASCADE')
        return names
    finally:
        await connection.close()


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Empty it. Without this the target is named and nothing is done.",
    )
    args = parser.parse_args(argv)

    # DB_HOST and DB_NAME are how every other part of the server is pointed at
    # a database -- `database.py` reads them, `alembic/env.py` reads them, and
    # the test suite sets them. Called with no arguments, `get_database_url`
    # ignores them and returns the default, which is the developer's main
    # database. So the one file whose whole job is to empty a database was the
    # one that could not be aimed at a different one, and
    # `DB_NAME=something_else python reset_db.py --yes` emptied `autobattler`.
    url = get_database_url(
        db_host=os.environ.get("DB_HOST"), db_name=os.environ.get("DB_NAME")
    )
    print(f"Database: {where_it_points(url)}")

    if not args.yes:
        print("Nothing done. Pass --yes to empty it.")
        return 1

    dropped = asyncio.run(empty(url))
    if dropped:
        print(f"Dropped {len(dropped)} tables: {', '.join(dropped)}")
    else:
        print("Nothing to drop; it was already empty.")
    print("Now run: alembic upgrade head")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
