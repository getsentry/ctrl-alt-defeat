"""One unique name per account

Drops `users.display_name`. The account has one name now, `username`, and a
leaderboard shows it, so it has to be unique. The new index ignores letter
case, because `Dan` and `dan` on the same board would read as one player.

Revision ID: b7c41d9e2af3
Revises: f2ec8e8b3a48
Create Date: 2026-08-20 16:44:39

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7c41d9e2af3"
down_revision: Union[str, None] = "f2ec8e8b3a48"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Names that differ only by letter case were legal until now. The index
    # below would refuse to build over them, so settle them first: the oldest
    # account keeps the name, and every later one gains its own id.
    op.execute(
        """
        UPDATE users AS u
        SET username = left(u.username, 26) || '_' || u.id
        WHERE EXISTS (
            SELECT 1 FROM users AS other
            WHERE lower(other.username) = lower(u.username)
              AND other.id < u.id
        )
        """
    )

    op.execute("CREATE UNIQUE INDEX ix_users_username_lower ON users (lower(username))")

    op.drop_column("users", "display_name")


def downgrade() -> None:
    op.add_column(
        "users", sa.Column("display_name", sa.String(length=64), nullable=True)
    )
    op.execute("DROP INDEX ix_users_username_lower")
