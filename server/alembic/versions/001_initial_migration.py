"""Initial migration with game sessions and battle history

Revision ID: 001
Revises:
Create Date: 2024-08-19 14:30:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create game_sessions table
    op.create_table(
        "game_sessions",
        sa.Column("player_id", sa.String(), nullable=False),
        sa.Column("round", sa.Integer(), nullable=False),
        sa.Column("gold", sa.Integer(), nullable=False),
        sa.Column("lives", sa.Integer(), nullable=False),
        sa.Column("wins", sa.Integer(), nullable=False),
        sa.Column("losses", sa.Integer(), nullable=False),
        sa.Column("game_seed", sa.Integer(), nullable=False),
        sa.Column("shop_refresh_count", sa.Integer(), nullable=False),
        sa.Column("last_battle_result", sa.JSON(), nullable=True),
        sa.Column("current_shop", sa.JSON(), nullable=False),
        sa.Column("inventory_grid", sa.JSON(), nullable=False),
        sa.Column("inventory_storage", sa.JSON(), nullable=False),
        sa.Column("placed_items", sa.JSON(), nullable=False),
        sa.Column("server_containers", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("last_activity", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("player_id"),
    )
    op.create_index(
        op.f("ix_game_sessions_player_id"), "game_sessions", ["player_id"], unique=False
    )

    # Create battle_history table
    op.create_table(
        "battle_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("player1_id", sa.String(), nullable=False),
        sa.Column("player2_id", sa.String(), nullable=True),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("winner", sa.Integer(), nullable=False),
        sa.Column("battle_data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_battle_history_player1_id"),
        "battle_history",
        ["player1_id"],
        unique=False,
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index(op.f("ix_battle_history_player1_id"), table_name="battle_history")
    op.drop_index(op.f("ix_game_sessions_player_id"), table_name="game_sessions")

    # Drop tables
    op.drop_table("battle_history")
    op.drop_table("game_sessions")
