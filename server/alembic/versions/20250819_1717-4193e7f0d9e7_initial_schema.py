"""Initial schema

Revision ID: 4193e7f0d9e7
Revises:
Create Date: 2025-08-19 17:17:20.571280

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4193e7f0d9e7"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=32), nullable=False),
        sa.Column("display_name", sa.String(length=64), nullable=True),
        sa.Column(
            "account_type", sa.String(length=20), nullable=False, server_default="guest"
        ),
        sa.Column(
            "account_status",
            sa.String(length=20),
            nullable=False,
            server_default="active",
        ),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column(
            "total_games_played", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("total_wins", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_losses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_rank", sa.Integer(), nullable=False, server_default="1000"),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")
        ),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)

    # Create game_sessions table
    op.create_table(
        "game_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("player_id", sa.String(), nullable=False),
        sa.Column("player_name", sa.String(), nullable=False, server_default="Player"),
        sa.Column(
            "user_id", sa.Integer(), nullable=True
        ),  # Nullable for backward compatibility
        sa.Column(
            "game_version", sa.String(length=20), nullable=False, server_default="1.0.0"
        ),
        sa.Column("session_token", sa.String(length=255), nullable=True),
        sa.Column("round", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("gold", sa.Integer(), nullable=False, server_default="12"),
        sa.Column("lives", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("wins", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("losses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("game_seed", sa.Integer(), nullable=False),
        sa.Column(
            "shop_refresh_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("last_battle_result", sa.JSON(), nullable=True),
        sa.Column("current_shop", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("inventory_grid", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("inventory_slots", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("inventory_storage", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("placed_items", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("server_containers", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")
        ),
        sa.Column(
            "last_activity",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("player_id"),
        sa.UniqueConstraint("user_id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index(
        op.f("ix_game_sessions_player_id"), "game_sessions", ["player_id"], unique=True
    )
    op.create_index(
        op.f("ix_game_sessions_user_id"), "game_sessions", ["user_id"], unique=True
    )

    # Create player_builds table
    op.create_table(
        "player_builds",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("player_name", sa.String(length=64), nullable=False),
        sa.Column("game_version", sa.String(length=20), nullable=False),
        sa.Column("game_session_id", sa.String(length=255), nullable=True),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("wins", sa.Integer(), nullable=False),
        sa.Column("losses", sa.Integer(), nullable=False),
        sa.Column("win_percent", sa.Float(), nullable=False),
        sa.Column("current_lives", sa.Integer(), nullable=False),
        sa.Column("inventory_snapshot", sa.JSON(), nullable=False),
        sa.Column("server_containers", sa.JSON(), nullable=False),
        sa.Column("total_item_value", sa.Integer(), nullable=False),
        sa.Column("total_item_count", sa.Integer(), nullable=False),
        sa.Column("battle_won", sa.Boolean(), nullable=False),
        sa.Column("opponent_type", sa.String(length=20), nullable=False),
        sa.Column("opponent_difficulty", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_matchmaking",
        "player_builds",
        ["game_version", "round_number", "win_percent", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_player_builds_created_at"), "player_builds", ["created_at"]
    )
    op.create_index(
        op.f("ix_player_builds_game_version"), "player_builds", ["game_version"]
    )
    op.create_index(
        op.f("ix_player_builds_round_number"), "player_builds", ["round_number"]
    )
    op.create_index(op.f("ix_player_builds_user_id"), "player_builds", ["user_id"])
    op.create_index(
        op.f("ix_player_builds_win_percent"), "player_builds", ["win_percent"]
    )

    # Create matchmaking_history table
    op.create_table(
        "matchmaking_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("player_user_id", sa.Integer(), nullable=False),
        sa.Column("opponent_build_id", sa.Integer(), nullable=False),
        sa.Column(
            "matched_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")
        ),
        sa.ForeignKeyConstraint(["opponent_build_id"], ["player_builds.id"]),
        sa.ForeignKeyConstraint(["player_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "player_user_id", "opponent_build_id", name="unique_recent_match"
        ),
    )
    op.create_index(
        "idx_player_history", "matchmaking_history", ["player_user_id", "matched_at"]
    )
    op.create_index(
        op.f("ix_matchmaking_history_matched_at"), "matchmaking_history", ["matched_at"]
    )
    op.create_index(
        op.f("ix_matchmaking_history_player_user_id"),
        "matchmaking_history",
        ["player_user_id"],
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
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_battle_history_player1_id"), "battle_history", ["player1_id"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_battle_history_player1_id"), table_name="battle_history")
    op.drop_table("battle_history")
    op.drop_index(
        op.f("ix_matchmaking_history_player_user_id"), table_name="matchmaking_history"
    )
    op.drop_index(
        op.f("ix_matchmaking_history_matched_at"), table_name="matchmaking_history"
    )
    op.drop_index("idx_player_history", table_name="matchmaking_history")
    op.drop_table("matchmaking_history")
    op.drop_index(op.f("ix_player_builds_win_percent"), table_name="player_builds")
    op.drop_index(op.f("ix_player_builds_user_id"), table_name="player_builds")
    op.drop_index(op.f("ix_player_builds_round_number"), table_name="player_builds")
    op.drop_index(op.f("ix_player_builds_game_version"), table_name="player_builds")
    op.drop_index(op.f("ix_player_builds_created_at"), table_name="player_builds")
    op.drop_index("idx_matchmaking", table_name="player_builds")
    op.drop_table("player_builds")
    op.drop_index(op.f("ix_game_sessions_user_id"), table_name="game_sessions")
    op.drop_index(op.f("ix_game_sessions_player_id"), table_name="game_sessions")
    op.drop_table("game_sessions")
    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
