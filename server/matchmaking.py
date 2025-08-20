"""
Matchmaking system for finding suitable opponents from historical player builds
"""

import random
from datetime import timedelta
from typing import Dict, List, Optional

from models import MatchmakingHistory, PlayerBuild
from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from utils import utc_now


class MatchmakingService:
    """Service for finding suitable opponents for players"""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def save_player_build(
        self,
        user_id: int,
        player_name: str,
        game_session_id: str,
        round_number: int,
        wins: int,
        losses: int,
        lives: int,
        inventory_grid: List[Dict],
        server_containers: List[Dict],
        battle_won: bool,
        opponent_type: str = "ai",
        opponent_difficulty: Optional[int] = None,
    ) -> PlayerBuild:
        """
        Save a snapshot of a player's build for future matchmaking

        Args:
            user_id: User's database ID
            player_name: Player's display name
            game_session_id: Current game session ID
            round_number: Current round number
            wins: Number of wins
            losses: Number of losses
            lives: Current lives
            inventory_grid: Items placed on grid
            server_containers: Container configuration
            battle_won: Whether this build won its battle
            opponent_type: 'ai' or 'player'
            opponent_difficulty: AI difficulty level if applicable

        Returns:
            The saved PlayerBuild instance
        """
        # Calculate statistics
        total_games = wins + losses
        win_percent = (wins / total_games * 100) if total_games > 0 else 0

        # Calculate item statistics
        total_item_count = len(inventory_grid)
        total_item_value = sum(item.get("cost", 0) for item in inventory_grid)

        # Create build snapshot
        build = PlayerBuild(
            user_id=user_id,
            player_name=player_name,
            game_version="1.0.0",  # TODO: Get from config
            game_session_id=game_session_id,
            round_number=round_number,
            wins=wins,
            losses=losses,
            win_percent=win_percent,
            current_lives=lives,
            inventory_snapshot=inventory_grid,
            server_containers=server_containers,
            total_item_value=total_item_value,
            total_item_count=total_item_count,
            battle_won=battle_won,
            opponent_type=opponent_type,
            opponent_difficulty=opponent_difficulty,
        )

        self.db.add(build)
        await self.db.commit()
        await self.db.refresh(build)
        return build

    async def find_opponent(
        self,
        user_id: int,
        round_number: int,
        win_percent: float,
        game_version: str = "1.0.0",
        max_skill_difference: float = 20.0,
        fallback_to_ai: bool = True,
    ) -> Optional[Dict]:
        """
        Find a suitable opponent from historical player builds

        Args:
            user_id: Current player's user ID
            round_number: Current round number
            win_percent: Player's current win percentage
            game_version: Game version for compatibility
            max_skill_difference: Maximum difference in win percentage for matching
            fallback_to_ai: Whether to return None (for AI fallback) if no match found

        Returns:
            Dictionary with opponent data or None if no suitable match found
        """
        # Build the base query

        # Find suitable opponent builds
        query = select(PlayerBuild).where(
            and_(
                # Same round number and game version
                PlayerBuild.round_number == round_number,
                PlayerBuild.game_version == game_version,
                # Not the same player
                PlayerBuild.user_id != user_id,
                # Build that won its battle (validated as good)
                PlayerBuild.battle_won.is_(True),
                # Recent builds (last 7 days)
                PlayerBuild.created_at > utc_now() - timedelta(days=7),
                # Similar skill level
                PlayerBuild.win_percent.between(
                    win_percent - max_skill_difference,
                    win_percent + max_skill_difference,
                ),
            )
        )

        # Fetch random sample of candidates for variety
        # No ordering needed - just get a random selection
        query = query.limit(30)

        # Get candidates
        candidates = await self.db.execute(query)
        candidates = candidates.scalars().all()

        if not candidates:
            return None if fallback_to_ai else None

        # Just pick randomly from all candidates for maximum variety
        opponent_build = random.choice(candidates)

        # Return opponent data in format expected by battle system
        return {
            "type": "player_ghost",  # Ghost of a real player
            "build_id": opponent_build.id,
            "player_name": opponent_build.player_name,
            "round_number": opponent_build.round_number,
            "wins": opponent_build.wins,
            "losses": opponent_build.losses,
            "win_percent": opponent_build.win_percent,
            "inventory": opponent_build.inventory_snapshot,
            "containers": opponent_build.server_containers,
        }

    async def record_match_result(
        self,
        player_user_id: int,
        player_build_id: int,
        opponent_build_id: int,
        battle_winner: int,
    ) -> None:
        """
        Record match history after battle completes

        Args:
            player_user_id: User ID of the player
            player_build_id: ID of the player's build
            opponent_build_id: ID of the opponent's build
            battle_winner: 1 if player won, 2 if opponent won
        """
        match_history = MatchmakingHistory(
            player_user_id=player_user_id,
            player_build_id=player_build_id,
            opponent_build_id=opponent_build_id,
            battle_winner=battle_winner,
        )
        self.db.add(match_history)
        await self.db.commit()

    async def get_build_leaderboard(
        self, round_number: int, limit: int = 10
    ) -> List[Dict]:
        """
        Get leaderboard of best performing builds for a round

        Args:
            round_number: Round to get leaderboard for
            limit: Number of top builds to return

        Returns:
            List of build stats ordered by performance
        """
        # Query to get builds with their win rates against real players
        query = """
            SELECT
                pb.id,
                pb.player_name,
                pb.user_id,
                pb.win_percent as build_win_percent,
                COUNT(mh.id) as times_used,
                SUM(CASE WHEN mh.battle_winner = 2 THEN 1 ELSE 0 END) as times_won,
                CAST(SUM(CASE WHEN mh.battle_winner = 2 THEN 1 ELSE 0 END) AS FLOAT) /
                    NULLIF(COUNT(CASE WHEN mh.battle_winner IS NOT NULL THEN 1 END), 0)
                    * 100 as opponent_win_rate
            FROM player_builds pb
            LEFT JOIN matchmaking_history mh ON mh.opponent_build_id = pb.id
            WHERE pb.round_number = :round_number
                AND pb.battle_won = TRUE
                AND mh.battle_winner IS NOT NULL
            GROUP BY pb.id, pb.player_name, pb.user_id, pb.win_percent
            HAVING COUNT(mh.id) > 0
            ORDER BY opponent_win_rate DESC, times_used DESC
            LIMIT :limit
        """

        from sqlalchemy import text

        result = await self.db.execute(
            text(query), {"round_number": round_number, "limit": limit}
        )

        builds = []
        for row in result:
            builds.append(
                {
                    "build_id": row[0],
                    "player_name": row[1],
                    "user_id": row[2],
                    "build_win_percent": row[3],
                    "times_used": row[4],
                    "times_won": row[5],
                    "opponent_win_rate": row[6],
                }
            )

        return builds

    async def cleanup_old_builds(self, days_to_keep: int = 30) -> int:
        """
        Clean up old player builds to manage database size

        Args:
            days_to_keep: Keep builds from last N days

        Returns:
            Number of builds deleted
        """
        cutoff_date = utc_now() - timedelta(days=days_to_keep)

        # Delete old builds
        result = await self.db.execute(
            delete(PlayerBuild).where(PlayerBuild.created_at < cutoff_date)
        )

        await self.db.commit()
        return result.rowcount
