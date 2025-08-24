"""
Database models and operations for Fantasy Football AI
Handles SQLite database for storing NFL player statistics
"""

import sqlite3
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from contextlib import contextmanager
from pfr_scraper import PlayerInfo, PassingStats, RushingStats, ReceivingStats
import csv

logger = logging.getLogger(__name__)

class FootballDatabase:
    """SQLite database handler for NFL statistics"""
    
    def __init__(self, db_path: str = "football_stats.db"):
        """
        Initialize database connection
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize database with schema"""
        schema_path = Path("database_schema.sql")
        
        if not schema_path.exists():
            logger.error(f"Schema file not found: {schema_path}")
            return
        
        with open(schema_path, 'r') as f:
            schema_sql = f.read()
        
        with self.get_connection() as conn:
            # Split and execute each statement
            statements = [stmt.strip() for stmt in schema_sql.split(';') if stmt.strip()]
            for statement in statements:
                try:
                    conn.execute(statement)
                except sqlite3.Error as e:
                    # Ignore table already exists errors
                    if "already exists" not in str(e).lower():
                        logger.error(f"Error executing SQL: {e}")
            
            conn.commit()
            logger.info("Database initialized successfully")
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        try:
            yield conn
        except sqlite3.Error as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()
    
    def get_team_id(self, team_abbr: str) -> Optional[int]:
        """Get team ID by abbreviation"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT id FROM teams WHERE abbreviation = ? OR abbreviation = ?",
                (team_abbr, team_abbr.upper())
            )
            row = cursor.fetchone()
            return row['id'] if row else None
    
    def insert_player(self, player: PlayerInfo) -> int:
        """
        Insert or update player information
        
        Returns:
            Player ID (database primary key)
        """
        with self.get_connection() as conn:
            # Check if player exists
            cursor = conn.execute(
                "SELECT id FROM players WHERE pfr_id = ?",
                (player.pfr_id,)
            )
            row = cursor.fetchone()
            
            if row:
                # Update existing player
                player_id = row['id']
                conn.execute("""
                    UPDATE players SET 
                        name = ?, position = ?, height = ?, weight = ?,
                        birth_date = ?, college = ?, drafted_year = ?,
                        drafted_round = ?, drafted_pick = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (
                    player.name, player.position, player.height, player.weight,
                    player.birth_date, player.college, player.drafted_year,
                    player.drafted_round, player.drafted_pick, player_id
                ))
                logger.info(f"Updated player: {player.name}")
            else:
                # Insert new player
                cursor = conn.execute("""
                    INSERT INTO players 
                    (pfr_id, name, position, height, weight, birth_date, college, 
                     drafted_year, drafted_round, drafted_pick)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    player.pfr_id, player.name, player.position, player.height,
                    player.weight, player.birth_date, player.college,
                    player.drafted_year, player.drafted_round, player.drafted_pick
                ))
                player_id = cursor.lastrowid
                logger.info(f"Inserted new player: {player.name}")
            
            conn.commit()
            return player_id
    
    def insert_passing_stats(self, stats: List[PassingStats]) -> int:
        """Insert passing statistics"""
        count = 0
        
        with self.get_connection() as conn:
            for stat in stats:
                # Get player ID
                cursor = conn.execute(
                    "SELECT id FROM players WHERE pfr_id = ?",
                    (stat.player_id,)
                )
                row = cursor.fetchone()
                if not row:
                    logger.warning(f"Player not found: {stat.player_id}")
                    continue
                
                player_id = row['id']
                team_id = self.get_team_id(stat.team)
                
                if not team_id:
                    logger.warning(f"Team not found: {stat.team}")
                    continue
                
                # Insert or replace stats
                conn.execute("""
                    INSERT OR REPLACE INTO passing_stats 
                    (player_id, team_id, season, games, games_started, completions,
                     attempts, completion_pct, passing_yards, passing_tds, interceptions,
                     yards_per_attempt, yards_per_completion, quarterback_rating,
                     sacks, sack_yards, yards_per_game, comeback_wins, game_winning_drives)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    player_id, team_id, stat.season, stat.games, stat.games_started,
                    stat.completions, stat.attempts, stat.completion_pct,
                    stat.passing_yards, stat.passing_tds, stat.interceptions,
                    stat.yards_per_attempt, stat.yards_per_completion,
                    stat.quarterback_rating, stat.sacks, stat.sack_yards,
                    None, None, None  # calculated fields
                ))
                count += 1
            
            conn.commit()
        
        logger.info(f"Inserted {count} passing stat records")
        return count
    
    def insert_rushing_stats(self, stats: List[RushingStats]) -> int:
        """Insert rushing statistics"""
        count = 0
        
        with self.get_connection() as conn:
            for stat in stats:
                # Get player ID
                cursor = conn.execute(
                    "SELECT id FROM players WHERE pfr_id = ?",
                    (stat.player_id,)
                )
                row = cursor.fetchone()
                if not row:
                    logger.warning(f"Player not found: {stat.player_id}")
                    continue
                
                player_id = row['id']
                team_id = self.get_team_id(stat.team)
                
                if not team_id:
                    logger.warning(f"Team not found: {stat.team}")
                    continue
                
                # Insert or replace stats
                conn.execute("""
                    INSERT OR REPLACE INTO rushing_stats 
                    (player_id, team_id, season, games, games_started, rushing_attempts,
                     rushing_yards, yards_per_attempt, rushing_tds, longest_rush,
                     yards_per_game, fumbles, fumbles_lost)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    player_id, team_id, stat.season, stat.games, stat.games_started,
                    stat.rushing_attempts, stat.rushing_yards, stat.yards_per_attempt,
                    stat.rushing_tds, stat.longest_rush, None,  # yards_per_game calculated
                    stat.fumbles, stat.fumbles_lost
                ))
                count += 1
            
            conn.commit()
        
        logger.info(f"Inserted {count} rushing stat records")
        return count
    
    def insert_receiving_stats(self, stats: List[ReceivingStats]) -> int:
        """Insert receiving statistics"""
        count = 0
        
        with self.get_connection() as conn:
            for stat in stats:
                # Get player ID
                cursor = conn.execute(
                    "SELECT id FROM players WHERE pfr_id = ?",
                    (stat.player_id,)
                )
                row = cursor.fetchone()
                if not row:
                    logger.warning(f"Player not found: {stat.player_id}")
                    continue
                
                player_id = row['id']
                team_id = self.get_team_id(stat.team)
                
                if not team_id:
                    logger.warning(f"Team not found: {stat.team}")
                    continue
                
                # Insert or replace stats
                conn.execute("""
                    INSERT OR REPLACE INTO receiving_stats 
                    (player_id, team_id, season, games, games_started, targets,
                     receptions, receiving_yards, yards_per_reception, receiving_tds,
                     longest_reception, yards_per_game, catch_pct, yards_per_target,
                     fumbles, fumbles_lost)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    player_id, team_id, stat.season, stat.games, stat.games_started,
                    stat.targets, stat.receptions, stat.receiving_yards,
                    stat.yards_per_reception, stat.receiving_tds, stat.longest_reception,
                    None, stat.catch_pct, stat.yards_per_target,  # yards_per_game calculated
                    stat.fumbles, stat.fumbles_lost
                ))
                count += 1
            
            conn.commit()
        
        logger.info(f"Inserted {count} receiving stat records")
        return count
    
    def get_player_stats(self, player_name: str, seasons: Optional[List[int]] = None) -> Dict[str, Any]:
        """
        Get comprehensive stats for a player
        
        Args:
            player_name: Player name to search for
            seasons: Optional list of seasons to filter by
            
        Returns:
            Dictionary with player info and stats
        """
        with self.get_connection() as conn:
            # Find player
            cursor = conn.execute(
                "SELECT * FROM players WHERE name LIKE ? OR pfr_id = ?",
                (f"%{player_name}%", player_name)
            )
            player = cursor.fetchone()
            
            if not player:
                return {}
            
            player_id = player['id']
            season_filter = ""
            params = [player_id]
            
            if seasons:
                season_filter = f"AND season IN ({','.join(['?'] * len(seasons))})"
                params.extend(seasons)
            
            # Get passing stats
            cursor = conn.execute(f"""
                SELECT ps.*, t.abbreviation as team_abbr, t.name as team_name
                FROM passing_stats ps
                JOIN teams t ON ps.team_id = t.id
                WHERE ps.player_id = ? {season_filter}
                ORDER BY ps.season
            """, params)
            passing_stats = [dict(row) for row in cursor.fetchall()]
            
            # Get rushing stats
            cursor = conn.execute(f"""
                SELECT rs.*, t.abbreviation as team_abbr, t.name as team_name
                FROM rushing_stats rs
                JOIN teams t ON rs.team_id = t.id
                WHERE rs.player_id = ? {season_filter}
                ORDER BY rs.season
            """, params)
            rushing_stats = [dict(row) for row in cursor.fetchall()]
            
            # Get receiving stats
            cursor = conn.execute(f"""
                SELECT recv.*, t.abbreviation as team_abbr, t.name as team_name
                FROM receiving_stats recv
                JOIN teams t ON recv.team_id = t.id
                WHERE recv.player_id = ? {season_filter}
                ORDER BY recv.season
            """, params)
            receiving_stats = [dict(row) for row in cursor.fetchall()]
            
            return {
                'player': dict(player),
                'passing_stats': passing_stats,
                'rushing_stats': rushing_stats,
                'receiving_stats': receiving_stats
            }
    
    def search_players(self, query: str, position: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search for players by name or position"""
        with self.get_connection() as conn:
            sql = "SELECT * FROM players WHERE name LIKE ?"
            params = [f"%{query}%"]
            
            if position:
                sql += " AND position = ?"
                params.append(position.upper())
            
            sql += " ORDER BY name LIMIT 20"
            
            cursor = conn.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_database_stats(self) -> Dict[str, int]:
        """Get database statistics"""
        with self.get_connection() as conn:
            stats = {}
            
            # Count records in each table
            for table in ['players', 'passing_stats', 'rushing_stats', 'receiving_stats']:
                cursor = conn.execute(f"SELECT COUNT(*) as count FROM {table}")
                row = cursor.fetchone()
                stats[table] = row['count']
            
            return stats

    def import_draft_values(self, csv_file_path: str, season: int = 2025) -> int:
        """
        Import draft values from CSV file
        
        Args:
            csv_file_path: Path to CSV file with columns: Position,Rank,Player,Team,Value
            season: Season year for the draft values
            
        Returns:
            Number of records imported
        """
        imported = 0
        
        with self.get_connection() as conn:
            # Clear existing data for the season
            conn.execute("DELETE FROM draft_values WHERE season = ?", (season,))
            
            with open(csv_file_path, 'r') as file:
                reader = csv.DictReader(file)
                position_ranks = {}  # Track position rankings
                
                for row in reader:
                    position = row['Position']
                    rank_overall = int(row['Rank']) if row['Rank'] else None
                    player_name = row['Player']
                    team = row['Team'] if row['Team'] else None
                    value = int(row['Value']) if row['Value'] else 0
                    
                    # Calculate position rank
                    if position not in position_ranks:
                        position_ranks[position] = 0
                    position_ranks[position] += 1
                    rank_position = position_ranks[position]
                    
                    conn.execute("""
                        INSERT INTO draft_values 
                        (position, rank_overall, rank_position, player_name, team, draft_value, season)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (position, rank_overall, rank_position, player_name, team, value, season))
                    
                    imported += 1
            
            conn.commit()
            
        logger.info(f"Imported {imported} draft values for season {season}")
        return imported

    def get_draft_values(self, season: int = 2025, position: Optional[str] = None, 
                        limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get draft values from database
        
        Args:
            season: Season year
            position: Filter by position (e.g., 'QB', 'RB')
            limit: Limit number of results
            
        Returns:
            List of draft value dictionaries
        """
        query = """
            SELECT * FROM draft_values 
            WHERE season = ?
        """
        params = [season]
        
        if position:
            query += " AND position = ?"
            params.append(position)
        
        query += " ORDER BY rank_overall"
        
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def search_draft_values(self, search_term: str, season: int = 2025) -> List[Dict[str, Any]]:
        """
        Search draft values by player name
        
        Args:
            search_term: Player name search term
            season: Season year
            
        Returns:
            List of matching draft value dictionaries
        """
        query = """
            SELECT * FROM draft_values 
            WHERE season = ? AND player_name LIKE ?
            ORDER BY rank_overall
        """
        
        with self.get_connection() as conn:
            cursor = conn.execute(query, (season, f"%{search_term}%"))
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

if __name__ == "__main__":
    # Test the database
    logging.basicConfig(level=logging.INFO)
    
    db = FootballDatabase()
    
    # Import draft values if CSV exists
    csv_path = "draft_values.csv"
    if Path(csv_path).exists():
        imported = db.import_draft_values(csv_path)
        print(f"Imported {imported} draft values")
        
        # Test search
        qbs = db.get_draft_values(position="QB", limit=5)
        print("Top 5 QBs:", [p['player_name'] for p in qbs])
    
    stats = db.get_database_stats()
    print("Database stats:", stats)