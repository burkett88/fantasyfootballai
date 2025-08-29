"""
Fantasy Football Draft Assistant
A comprehensive single-page application for draft day management
"""

from flask import Flask, render_template_string, request, jsonify, redirect, url_for
from database import FootballDatabase
import logging
from typing import Dict, List, Any, Optional
import os
from pathlib import Path
import dspy
from dotenv import load_dotenv
import traceback
import re
from pfr_scraper import PFRScraper

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-here')

# Initialize database
db = FootballDatabase()

# Auction value inflation factor (11% increase)
AUCTION_INFLATION_FACTOR = 1.11

# Configure DSPy for LLM analysis
api_key = os.getenv("OPENAI_API_KEY")
if api_key:
    lm = dspy.LM("openai/gpt-4o-search-preview-2025-03-11", api_key=api_key, temperature=None)
    dspy.configure(lm=lm)
else:
    logger.warning("No OpenAI API key found - LLM analysis will be disabled")

# Define the DSPy signature for player analysis
class FantasyFootballPlayerResearcher(dspy.Signature):
    """This is a very detailed report for football players in the 2025 fantasy football season. This summarizes data from data-driven sources of fantasy football knowledge and not just mainstream sources like cbs."""
    playerName: str = dspy.InputField(desc="Fantasy Football Player Name")
    playing_time: str = dspy.OutputField(desc="Indications about how this players snap count may compare vs the previous season.")
    injury_risk: str = dspy.OutputField(desc="Research on the injury risk for this player in 2025. Consider their injury history and usage.")
    breakout_risk: str = dspy.OutputField(desc="Research on whether people expect this player to potentially breakout, which we define as a significant improvement to their per game points. Include direct quotes where appropriate.")
    bust_risk: str = dspy.OutputField(desc="Research on whether this player could be a bust, particularly relative to where they are being drafted")
    key_changes: str = dspy.OutputField(desc="Personnel changes or coaching changes on the team that may affect their playing time or effectiveness")
    outlook: str = dspy.OutputField(desc="An overall assessment of their outlook")

# Create the predictor if API key is available
player_researcher = dspy.Predict(FantasyFootballPlayerResearcher) if api_key else None

class DraftManager:
    """Handles all draft-related operations"""
    
    def __init__(self, database: FootballDatabase):
        self.db = database
        
    def get_all_players(self, season: int = 2025, status_filter: str = "all", position_filter: str = "all") -> List[Dict[str, Any]]:
        """Get all players with their draft values and status"""
        
        # Base query joining draft values with status
        query = """
            SELECT 
                dv.*,
                ROUND(dv.draft_value * ?) as draft_value,
                COALESCE(dps.is_target, 0) as is_target,
                COALESCE(dps.is_avoid, 0) as is_avoid,
                COALESCE(dps.is_drafted, 0) as is_drafted,
                COALESCE(dps.drafted_by, '') as drafted_by,
                COALESCE(dps.drafted_price, 0) as drafted_price,
                COALESCE(dps.has_injury_risk, 0) as has_injury_risk,
                COALESCE(dps.has_breakout_potential, 0) as has_breakout_potential,
                COALESCE(dps.custom_tags, '') as custom_tags,
                COALESCE(dps.draft_notes, '') as draft_notes,
                COALESCE(pa.analysis_text, '') as analysis_text,
                COALESCE(pa.playing_time_score, 0) as playing_time_score,
                COALESCE(pa.injury_risk_score, 0) as injury_risk_score,
                COALESCE(pa.breakout_risk_score, 0) as breakout_risk_score,
                COALESCE(pa.bust_risk_score, 0) as bust_risk_score
            FROM draft_values dv
            LEFT JOIN draft_player_status dps ON dv.player_name = dps.player_name AND dv.season = dps.season
            LEFT JOIN player_analysis pa ON dv.player_name = pa.player_name AND dv.season = pa.season
            WHERE dv.season = ? AND dv.position NOT IN ('K', 'DST')
        """
        
        params = [AUCTION_INFLATION_FACTOR, season]
        
        # Apply status filter
        if status_filter == "available":
            query += " AND COALESCE(dps.is_drafted, 0) = 0"
        elif status_filter == "drafted":
            query += " AND COALESCE(dps.is_drafted, 0) = 1"
        elif status_filter == "targets":
            query += " AND COALESCE(dps.is_target, 0) = 1"
        elif status_filter == "avoid":
            query += " AND COALESCE(dps.is_avoid, 0) = 1"
            
        # Apply position filter
        if position_filter != "all":
            query += " AND dv.position = ?"
            params.append(position_filter)
            
        query += " ORDER BY dv.rank_overall"
        
        with self.db.get_connection() as conn:
            cursor = conn.execute(query, params)
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def search_players(self, search_term: str, season: int = 2025, status_filter: str = "all", position_filter: str = "all") -> List[Dict[str, Any]]:
        """Search players by name"""
        players = self.get_all_players(season, status_filter, position_filter)
        search_lower = search_term.lower()
        return [p for p in players if search_lower in p['player_name'].lower()]
    
    def update_player_status(self, player_name: str, status_updates: Dict[str, Any], season: int = 2025):
        """Update player status flags"""
        
        with self.db.get_connection() as conn:
            # Insert or update player status
            conn.execute("""
                INSERT OR REPLACE INTO draft_player_status 
                (player_name, season, is_target, is_avoid, is_drafted, drafted_by, 
                 drafted_price, has_injury_risk, has_breakout_potential, custom_tags, draft_notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                player_name, season,
                status_updates.get('is_target', 0),
                status_updates.get('is_avoid', 0), 
                status_updates.get('is_drafted', 0),
                status_updates.get('drafted_by', ''),
                status_updates.get('drafted_price', 0),
                status_updates.get('has_injury_risk', 0),
                status_updates.get('has_breakout_potential', 0),
                status_updates.get('custom_tags', ''),
                status_updates.get('draft_notes', '')
            ))
            conn.commit()
    
    def get_teammates(self, player_name: str, season: int = 2025) -> List[Dict[str, Any]]:
        """Get offensive teammates for a player"""
        query = """
            SELECT teammate_name, teammate_position 
            FROM player_teammates 
            WHERE player_name = ? AND season = ?
            ORDER BY 
                CASE teammate_position 
                    WHEN 'QB' THEN 1
                    WHEN 'RB' THEN 2  
                    WHEN 'WR' THEN 3
                    WHEN 'TE' THEN 4
                    ELSE 5
                END,
                teammate_name
        """
        
        with self.db.get_connection() as conn:
            cursor = conn.execute(query, (player_name, season))
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def analyze_player_with_llm(self, player_name: str, season: int = 2025) -> Optional[Dict[str, Any]]:
        """Generate LLM analysis for a player and store in database"""
        if not player_researcher:
            logger.warning("LLM analysis not available - no API key configured")
            return None
            
        try:
            # Check if analysis already exists
            with self.db.get_connection() as conn:
                cursor = conn.execute(
                    "SELECT * FROM player_analysis WHERE player_name = ? AND season = ?",
                    (player_name, season)
                )
                existing = cursor.fetchone()
                
                if existing:
                    logger.info(f"Analysis already exists for {player_name}")
                    return dict(existing)
            
            logger.info(f"Generating LLM analysis for {player_name}")
            result = player_researcher(playerName=player_name)
            
            # Convert markdown links to HTML
            def convert_markdown_links(text: str) -> str:
                pattern = r'\[([^\]]+)\]\((https?://[^\)]+)\)'
                replacement = r'<a href="\2" target="_blank" class="text-blue-600 hover:text-blue-800 underline">\1</a>'
                return re.sub(pattern, replacement, text)
            
            # Combine all analysis into a single text field
            analysis_parts = [
                f"**Playing Time**: {result.playing_time}",
                f"**Injury Risk**: {result.injury_risk}", 
                f"**Breakout Risk**: {result.breakout_risk}",
                f"**Bust Risk**: {result.bust_risk}",
                f"**Key Changes**: {result.key_changes}",
                f"**Outlook**: {result.outlook}"
            ]
            
            analysis_text = convert_markdown_links("\n\n".join(analysis_parts))
            
            # Store in database
            with self.db.get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO player_analysis 
                    (player_name, season, analysis_text, key_changes, outlook)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    player_name, season, analysis_text,
                    convert_markdown_links(result.key_changes),
                    convert_markdown_links(result.outlook)
                ))
                conn.commit()
            
            logger.info(f"Stored LLM analysis for {player_name}")
            
            return {
                'player_name': player_name,
                'season': season,
                'analysis_text': analysis_text,
                'key_changes': convert_markdown_links(result.key_changes),
                'outlook': convert_markdown_links(result.outlook)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing player {player_name}: {str(e)}")
            traceback.print_exc()
            return None
    
    def get_player_stats(self, player_name: str, seasons: Optional[List[int]] = None) -> Dict[str, Any]:
        """Get player stats from the database using the existing method"""
        if not seasons:
            # Get last 3 seasons by default
            current_year = 2024  # 2024 is the most recent complete season
            seasons = [current_year - i for i in range(3)]
        
        return self.db.get_player_stats(player_name, seasons)
    
    def scrape_and_store_player_stats(self, player_name: str) -> bool:
        """Scrape stats for a player from Pro Football Reference and store in database"""
        try:
            scraper = PFRScraper(delay=1.0)  # Be respectful with requests
            
            logger.info(f"Searching for {player_name} on Pro Football Reference...")
            
            # Search for player
            pfr_ids = scraper.search_player(player_name)
            if not pfr_ids:
                logger.warning(f"No Pro Football Reference results found for {player_name}")
                return False
            
            # Try each ID to find the one with the most relevant stats (for active players)
            best_pfr_id = None
            best_stats_count = 0
            best_latest_season = 0
            
            for pfr_id in pfr_ids:
                try:
                    test_passing, test_rushing, test_receiving = scraper.get_player_stats(pfr_id)
                    total_stats = len(test_passing) + len(test_rushing) + len(test_receiving)
                    
                    # Find the most recent season
                    latest_season = 0
                    for stats_list in [test_passing, test_rushing, test_receiving]:
                        if stats_list:
                            latest_season = max(latest_season, max(stat.season for stat in stats_list))
                    
                    # Prefer players with more recent stats and more total stats
                    if (latest_season > best_latest_season or 
                        (latest_season == best_latest_season and total_stats > best_stats_count)):
                        best_pfr_id = pfr_id
                        best_stats_count = total_stats
                        best_latest_season = latest_season
                        
                        logger.info(f"Found better match: {pfr_id} with {total_stats} stats, latest season {latest_season}")
                        
                except Exception as e:
                    logger.warning(f"Error checking stats for {pfr_id}: {str(e)}")
                    continue
            
            if not best_pfr_id:
                logger.warning(f"No valid stats found for any {player_name} variants")
                return False
                
            pfr_id = best_pfr_id
            logger.info(f"Using PFR ID: {pfr_id} for {player_name} (latest season: {best_latest_season})")
            
            # Get player info and stats for the best match
            player_info = scraper.get_player_info(pfr_id)
            passing_stats, rushing_stats, receiving_stats = scraper.get_player_stats(pfr_id)
            
            if not (passing_stats or rushing_stats or receiving_stats):
                logger.warning(f"No stats retrieved for {player_name} with ID {pfr_id}")
                return False
            
            # Store player info if we got any
            if player_info:
                with self.db.get_connection() as conn:
                    conn.execute("""
                        INSERT OR REPLACE INTO players 
                        (pfr_id, name, position, height, weight, birth_date, college, drafted_year, drafted_round, drafted_pick)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        player_info.pfr_id, player_info.name or player_name, player_info.position,
                        player_info.height, player_info.weight, player_info.birth_date,
                        player_info.college, player_info.drafted_year, player_info.drafted_round, player_info.drafted_pick
                    ))
                    conn.commit()
            
            # Store stats
            stats_stored = 0
            
            with self.db.get_connection() as conn:
                # Get or create player record to get the database player_id
                cursor = conn.execute("SELECT id FROM players WHERE pfr_id = ?", (pfr_id,))
                player_row = cursor.fetchone()
                if player_row:
                    db_player_id = player_row[0]
                else:
                    # Insert minimal player record if not exists
                    cursor = conn.execute("""
                        INSERT INTO players (pfr_id, name, position) 
                        VALUES (?, ?, ?)
                    """, (pfr_id, player_name, player_info.position if player_info else ''))
                    db_player_id = cursor.lastrowid
                    conn.commit()
                
                # Clear existing stats for this player
                conn.execute("DELETE FROM passing_stats WHERE player_id = ?", (db_player_id,))
                conn.execute("DELETE FROM rushing_stats WHERE player_id = ?", (db_player_id,))
                conn.execute("DELETE FROM receiving_stats WHERE player_id = ?", (db_player_id,))
                
                # Helper function to get or create team_id
                def get_team_id(team_abbr):
                    if not team_abbr:
                        return 1  # Default team ID
                    cursor = conn.execute("SELECT id FROM teams WHERE abbreviation = ?", (team_abbr,))
                    result = cursor.fetchone()
                    if result:
                        return result[0]
                    else:
                        # Create new team if not exists
                        cursor = conn.execute("""
                            INSERT INTO teams (abbreviation, name, city) 
                            VALUES (?, ?, ?)
                        """, (team_abbr, team_abbr, ''))
                        conn.commit()
                        return cursor.lastrowid
                
                # Insert passing stats
                for stat in passing_stats:
                    team_id = get_team_id(stat.team)
                    conn.execute("""
                        INSERT INTO passing_stats 
                        (player_id, team_id, season, games, games_started, completions, attempts, 
                         completion_pct, passing_yards, passing_tds, interceptions, yards_per_attempt, 
                         yards_per_completion, quarterback_rating, sacks, sack_yards)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        db_player_id, team_id, stat.season, stat.games, stat.games_started,
                        stat.completions, stat.attempts, stat.completion_pct, stat.passing_yards,
                        stat.passing_tds, stat.interceptions, stat.yards_per_attempt,
                        stat.yards_per_completion, stat.quarterback_rating, stat.sacks, stat.sack_yards
                    ))
                    stats_stored += 1
                
                # Insert rushing stats
                for stat in rushing_stats:
                    team_id = get_team_id(stat.team)
                    conn.execute("""
                        INSERT INTO rushing_stats 
                        (player_id, team_id, season, games, games_started, rushing_attempts, 
                         rushing_yards, yards_per_attempt, rushing_tds, longest_rush, fumbles, fumbles_lost)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        db_player_id, team_id, stat.season, stat.games, stat.games_started,
                        stat.rushing_attempts, stat.rushing_yards, stat.yards_per_attempt,
                        stat.rushing_tds, stat.longest_rush, stat.fumbles, stat.fumbles_lost
                    ))
                    stats_stored += 1
                
                # Insert receiving stats
                for stat in receiving_stats:
                    team_id = get_team_id(stat.team)
                    conn.execute("""
                        INSERT INTO receiving_stats 
                        (player_id, team_id, season, games, games_started, targets, receptions,
                         receiving_yards, yards_per_reception, receiving_tds, longest_reception,
                         catch_pct, yards_per_target, fumbles, fumbles_lost)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        db_player_id, team_id, stat.season, stat.games, stat.games_started,
                        stat.targets, stat.receptions, stat.receiving_yards, stat.yards_per_reception,
                        stat.receiving_tds, stat.longest_reception, stat.catch_pct, stat.yards_per_target,
                        stat.fumbles, stat.fumbles_lost
                    ))
                    stats_stored += 1
                
                conn.commit()
            
            logger.info(f"Successfully stored {stats_stored} stat records for {player_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error scraping stats for {player_name}: {str(e)}")
            return False

# Initialize draft manager
draft_manager = DraftManager(db)

@app.route('/')
def index():
    """Main draft application page"""
    return render_template_string(DRAFT_APP_HTML)

@app.route('/api/players')
def api_players():
    """API endpoint for player data"""
    status_filter = request.args.get('filter', 'all')
    position_filter = request.args.get('position', 'all')
    search_term = request.args.get('search', '')
    
    if search_term:
        players = draft_manager.search_players(search_term, status_filter=status_filter, position_filter=position_filter)
    else:
        players = draft_manager.get_all_players(status_filter=status_filter, position_filter=position_filter)
    
    return jsonify(players)

@app.route('/api/players/<player_name>/status', methods=['POST'])
def update_player_status(player_name):
    """Update player status"""
    status_updates = request.get_json()
    draft_manager.update_player_status(player_name, status_updates)
    return jsonify({'success': True})

@app.route('/api/players/<player_name>/teammates')
def get_player_teammates(player_name):
    """Get player teammates"""
    teammates = draft_manager.get_teammates(player_name)
    return jsonify(teammates)

@app.route('/api/players/<player_name>')
def get_player_detail(player_name):
    """Get detailed player information including stats"""
    players = draft_manager.search_players(player_name)
    if players:
        player = players[0]  # Get exact match or first result
        teammates = draft_manager.get_teammates(player_name)
        player['teammates'] = teammates
        
        # Get player stats from Pro Football Reference data
        try:
            stats_data = draft_manager.get_player_stats(player_name)
            player['stats'] = stats_data
            logger.info(f"Retrieved stats for {player_name}: {len(stats_data.get('passing_stats', []))} passing, {len(stats_data.get('rushing_stats', []))} rushing, {len(stats_data.get('receiving_stats', []))} receiving")
        except Exception as e:
            logger.warning(f"Could not retrieve stats for {player_name}: {str(e)}")
            player['stats'] = {}
        
        return jsonify(player)
    return jsonify({'error': 'Player not found'}), 404

@app.route('/api/players/<player_name>/analyze', methods=['POST'])
def analyze_player(player_name):
    """Generate LLM analysis for a player"""
    try:
        analysis = draft_manager.analyze_player_with_llm(player_name)
        if analysis:
            return jsonify({'success': True, 'analysis': analysis})
        else:
            return jsonify({'success': False, 'error': 'Analysis failed or not available'}), 500
    except Exception as e:
        logger.error(f"Error in analyze_player endpoint: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/players/<player_name>/refresh-stats', methods=['POST'])
def refresh_player_stats(player_name):
    """Refresh stats for a specific player from Pro Football Reference"""
    try:
        success = draft_manager.scrape_and_store_player_stats(player_name)
        if success:
            return jsonify({'success': True, 'message': 'Stats refreshed successfully'})
        else:
            return jsonify({'success': False, 'error': 'Failed to refresh stats'}), 500
    except Exception as e:
        logger.error(f"Error refreshing stats for {player_name}: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/refresh-all-stats', methods=['POST'])
def refresh_all_stats():
    """Refresh stats for all players (this could take a while)"""
    try:
        # Get all unique player names from draft values
        with db.get_connection() as conn:
            cursor = conn.execute("SELECT DISTINCT player_name FROM draft_values ORDER BY rank_overall LIMIT 100")
            player_names = [row[0] for row in cursor.fetchall()]
        
        success_count = 0
        for player_name in player_names:
            try:
                if draft_manager.scrape_and_store_player_stats(player_name):
                    success_count += 1
            except Exception as e:
                logger.warning(f"Failed to refresh stats for {player_name}: {str(e)}")
                continue
        
        return jsonify({
            'success': True, 
            'message': f'Refreshed stats for {success_count} out of {len(player_names)} players'
        })
    except Exception as e:
        logger.error(f"Error in refresh_all_stats: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# HTML Template with embedded CSS and JavaScript
DRAFT_APP_HTML = r'''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Fantasy Football Draft Assistant</title>
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f5f7;
            color: #1d1d1f;
            font-size: 14px;
        }
        
        .header {
            background: #1d1d1f;
            color: white;
            padding: 1rem;
            position: sticky;
            top: 0;
            z-index: 100;
        }
        
        .header h1 {
            text-align: center;
            font-size: 1.25rem;
            font-weight: 600;
        }
        
        .controls {
            background: white;
            padding: 0.75rem;
            border-bottom: 1px solid #d2d2d7;
            display: flex;
            gap: 0.75rem;
            align-items: center;
            flex-wrap: wrap;
        }
        
        .search-box {
            flex: 1;
            min-width: 250px;
            padding: 0.4rem;
            border: 1px solid #d2d2d7;
            border-radius: 6px;
            font-size: 0.875rem;
        }
        
        .filter-buttons {
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
        }
        
        .filter-section {
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        
        .filter-label {
            font-size: 0.75rem;
            font-weight: 500;
            color: #6B7280;
        }
        
        .filter-btn {
            padding: 0.4rem 0.75rem;
            border: 1px solid #d2d2d7;
            background: white;
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.2s;
            font-size: 0.75rem;
        }
        
        .filter-btn.active {
            background: #007AFF;
            color: white;
            border-color: #007AFF;
        }
        
        .main-container {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr 1fr;
            gap: 0.5rem;
            padding: 0.5rem;
            height: calc(100vh - 100px);
        }
        
        @media (max-width: 1200px) {
            .main-container {
                grid-template-columns: 1fr 1fr;
                grid-template-rows: 1fr 1fr;
            }
        }
        
        @media (max-width: 768px) {
            .main-container {
                grid-template-columns: 1fr;
                grid-template-rows: 1fr 1fr 1fr 1fr;
            }
        }
        
        .player-list {
            background: white;
            border-radius: 12px;
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }
        
        .player-list-header {
            padding: 0.5rem;
            border-bottom: 1px solid #d2d2d7;
            font-weight: 600;
            background: #f8f8f8;
            font-size: 0.75rem;
        }
        
        .player-grid {
            flex: 1;
            overflow-y: auto;
        }
        
        .player-row {
            display: grid;
            grid-template-columns: 20px 25px 100px 35px 25px 60px;
            gap: 0.1rem;
            padding: 0.2rem 0.25rem;
            border-bottom: 1px solid #f0f0f0;
            cursor: pointer;
            transition: background-color 0.2s;
            align-items: center;
            font-size: 0.65rem;
            min-height: 22px;
        }
        
        .player-row:hover {
            background: #f8f8f8;
        }
        
        .player-row.selected {
            background: #007AFF1A;
            border-left: 4px solid #007AFF;
        }
        
        .player-row.drafted {
            opacity: 0.5;
            text-decoration: line-through;
        }
        
        .player-row.target {
            border-left: 4px solid #34C759;
        }
        
        .player-row.avoid {
            border-left: 4px solid #FF3B30;
        }
        
        .rank {
            font-weight: 600;
            color: #8E8E93;
        }
        
        .position {
            font-size: 0.5rem;
            background: #007AFF;
            color: white;
            padding: 0.05rem 0.15rem;
            border-radius: 2px;
            text-align: center;
            font-weight: 600;
            line-height: 1;
        }
        
        .position.QB { background: #FF9500; }
        .position.RB { background: #34C759; }
        .position.WR { background: #007AFF; }
        .position.TE { background: #5856D6; }
        .position.DST { background: #8E8E93; }
        .position.K { background: #FF2D92; }
        
        .player-name {
            font-weight: 500;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        
        .player-row > div:nth-child(3) {
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            font-size: 0.6rem;
        }
        
        .player-team {
            font-size: 0.5rem;
            color: #8E8E93;
            margin-left: 0.2rem;
            font-weight: 500;
        }
        
        .value {
            font-weight: 600;
            color: #34C759;
        }
        
        .indicators {
            display: flex;
            gap: 0.25rem;
        }
        
        .actions {
            display: flex;
            gap: 0.05rem;
            justify-content: flex-start;
        }
        
        .action-btn {
            padding: 0.05rem 0.15rem;
            border: none;
            border-radius: 1px;
            cursor: pointer;
            font-size: 0.45rem;
            font-weight: 600;
            transition: all 0.2s;
            line-height: 1;
            min-width: 14px;
            text-align: center;
        }
        
        .btn-target {
            background: #34C759;
            color: white;
        }
        
        .btn-avoid {
            background: #FF3B30;
            color: white;
        }
        
        .btn-drafted {
            background: #8E8E93;
            color: white;
        }
        
        .btn-analyze {
            background: #007AFF;
            color: white;
            padding: 0.5rem 1rem;
            margin-bottom: 1rem;
            width: 100%;
            font-size: 0.875rem;
        }
        
        .btn-analyze:hover {
            background: #0056CC;
        }
        
        .btn-analyze:disabled {
            background: #8E8E93;
            cursor: not-allowed;
        }
        
        .btn-refresh {
            background: #FF9500;
            color: white;
            padding: 0.5rem 1rem;
            margin-bottom: 1rem;
            font-size: 0.875rem;
        }
        
        .btn-refresh:hover {
            background: #E6850E;
        }
        
        .btn-refresh:disabled {
            background: #8E8E93;
            cursor: not-allowed;
        }
        
        .player-detail {
            background: white;
            border-radius: 12px;
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }
        
        .detail-header {
            padding: 0.75rem;
            border-bottom: 1px solid #d2d2d7;
            background: #f8f8f8;
            font-size: 0.875rem;
        }
        
        .detail-content {
            flex: 1;
            overflow-y: auto;
            padding: 0.75rem;
            font-size: 0.8rem;
        }
        
        .empty-state {
            display: flex;
            align-items: center;
            justify-content: center;
            height: 100%;
            color: #8E8E93;
            font-style: italic;
        }
        
        .teammates {
            display: flex;
            gap: 0.5rem;
            margin-top: 0.5rem;
        }
        
        .teammate {
            background: #f0f0f0;
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
            font-size: 0.75rem;
        }
        
        .analysis-section {
            margin-top: 1rem;
            padding-top: 1rem;
            border-top: 1px solid #d2d2d7;
        }
        
        .section-title {
            font-weight: 600;
            margin-bottom: 0.4rem;
            color: #1d1d1f;
            font-size: 0.875rem;
        }
        
        .loading {
            text-align: center;
            padding: 2rem;
            color: #8E8E93;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 0.4rem;
            margin: 0.4rem 0;
        }
        
        .stat-item {
            background: #f8f8f8;
            padding: 0.4rem;
            border-radius: 4px;
            text-align: center;
        }
        
        .stat-value {
            font-weight: 600;
            font-size: 0.9em;
        }
        
        .stat-label {
            font-size: 0.65rem;
            color: #8E8E93;
            margin-top: 0.2rem;
        }
        
        .stats-table {
            width: 100%;
            border-collapse: collapse;
            margin: 0.75rem 0;
            font-size: 0.75rem;
        }
        
        .stats-table th,
        .stats-table td {
            padding: 0.3rem 0.2rem;
            text-align: center;
            border-bottom: 1px solid #f0f0f0;
        }
        
        .stats-table th {
            background: #f8f8f8;
            font-weight: 600;
            color: #1d1d1f;
            border-bottom: 2px solid #d2d2d7;
        }
        
        .stats-table tr:hover {
            background: #f8f8f8;
        }
        
        .stats-table .season-col {
            font-weight: 600;
            color: #007AFF;
        }
        
        .no-stats {
            text-align: center;
            color: #8E8E93;
            font-style: italic;
            padding: 2rem;
        }
        
        .stats-table strong {
            color: #007AFF;
            font-weight: 700;
        }
        
        .fantasy-points-header {
            background: linear-gradient(135deg, #007AFF, #34C759);
            color: white !important;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🏈 Fantasy Football Draft Assistant</h1>
    </div>
    
    <div class="controls">
        <input type="text" class="search-box" placeholder="Search players..." 
               oninput="searchPlayers(this.value)">
        
        <div class="filter-section">
            <span class="filter-label">Status:</span>
            <div class="filter-buttons" id="status-filters">
                <button class="filter-btn active" onclick="filterPlayers('all')">All</button>
                <button class="filter-btn" onclick="filterPlayers('available')">Available</button>
                <button class="filter-btn" onclick="filterPlayers('targets')">Targets</button>
                <button class="filter-btn" onclick="filterPlayers('avoid')">Avoid</button>
                <button class="filter-btn" onclick="filterPlayers('drafted')">Drafted</button>
            </div>
        </div>
        
        
        <div class="filter-section">
            <button class="filter-btn" onclick="refreshAllStats()" id="refresh-all-btn" style="background: #FF9500; color: white; border-color: #FF9500;">
                🔄 Refresh All Stats
            </button>
        </div>
    </div>
    
    <div class="main-container">
        <div class="player-list">
            <div class="player-list-header">
                Quarterbacks
            </div>
            <div class="player-grid" id="qb-grid">
                <div class="loading">Loading QBs...</div>
            </div>
        </div>
        
        <div class="player-list">
            <div class="player-list-header">
                Running Backs
            </div>
            <div class="player-grid" id="rb-grid">
                <div class="loading">Loading RBs...</div>
            </div>
        </div>
        
        <div class="player-list">
            <div class="player-list-header">
                Wide Receivers
            </div>
            <div class="player-grid" id="wr-grid">
                <div class="loading">Loading WRs...</div>
            </div>
        </div>
        
        <div class="player-list">
            <div class="player-list-header">
                Tight Ends
            </div>
            <div class="player-grid" id="te-grid">
                <div class="loading">Loading TEs...</div>
            </div>
        </div>
    </div>
    
    <!-- Player Profile Modal -->
    <div id="player-profile-modal" style="display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 1000;">
        <div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); background: white; border-radius: 12px; width: 90%; max-width: 800px; max-height: 90%; overflow-y: auto;">
            <div style="padding: 1rem; border-bottom: 1px solid #d2d2d7; display: flex; justify-content: between; align-items: center;">
                <h2 id="modal-player-title" style="margin: 0; flex: 1;">Player Profile</h2>
                <button onclick="closePlayerProfile()" style="background: none; border: none; font-size: 1.5rem; cursor: pointer; padding: 0.25rem;">&times;</button>
            </div>
            <div id="modal-player-content" style="padding: 1rem;">
                Loading...
            </div>
        </div>
    </div>

    <script>
        let currentFilter = 'all';
        let currentPosition = 'all';
        let currentSearch = '';
        let selectedPlayer = null;
        let players = [];
        
        // Load players on page load
        document.addEventListener('DOMContentLoaded', function() {
            loadAllPositions();
        });
        
        async function loadAllPositions(filter = 'all', search = '') {
            const positions = ['QB', 'RB', 'WR', 'TE'];
            
            for (const position of positions) {
                try {
                    const url = new URL('/api/players', window.location.origin);
                    if (filter !== 'all') url.searchParams.append('filter', filter);
                    url.searchParams.append('position', position);
                    if (search) url.searchParams.append('search', search);
                    
                    const response = await fetch(url);
                    const positionPlayers = await response.json();
                    renderPositionList(position, positionPlayers);
                } catch (error) {
                    console.error(`Error loading ${position} players:`, error);
                    document.getElementById(`${position.toLowerCase()}-grid`).innerHTML = 
                        '<div class="loading">Error loading players</div>';
                }
            }
        }
        
        function renderPositionList(position, playerList) {
            const grid = document.getElementById(`${position.toLowerCase()}-grid`);
            
            if (playerList.length === 0) {
                grid.innerHTML = '<div class="loading">No players found</div>';
                return;
            }
            
            grid.innerHTML = playerList.map(player => `
                <div class="player-row ${getPlayerClasses(player)}" 
                     onclick="openPlayerProfile('${player.player_name.replace(/'/g, "\\'")}')">
                    <div class="rank">${player.rank_overall}</div>
                    <div class="position ${player.position}">${player.position}</div>
                    <div>
                        <span class="player-name">${player.player_name}</span><span class="player-team">${player.team ? ' (' + player.team + ')' : ''}</span>
                    </div>
                    <div class="value">$${player.draft_value}</div>
                    <div class="indicators">
                        ${player.has_injury_risk ? '🚑' : ''}
                        ${player.has_breakout_potential ? '💥' : ''}
                    </div>
                    <div class="actions" onclick="event.stopPropagation()">
                        <button class="action-btn btn-target" 
                                onclick="toggleStatus('${player.player_name.replace(/'/g, "\\'")}', 'target')">
                            ${player.is_target ? '✓' : 'T'}
                        </button>
                        <button class="action-btn btn-avoid" 
                                onclick="toggleStatus('${player.player_name.replace(/'/g, "\\'")}', 'avoid')">
                            ${player.is_avoid ? '✓' : 'A'}
                        </button>
                        <button class="action-btn btn-drafted" 
                                onclick="toggleStatus('${player.player_name.replace(/'/g, "\\'")}', 'drafted')">
                            ${player.is_drafted ? '✓' : 'D'}
                        </button>
                    </div>
                </div>
            `).join('');
        }
        
        function getPlayerClasses(player) {
            let classes = [];
            if (selectedPlayer === player.player_name) classes.push('selected');
            if (player.is_drafted) classes.push('drafted');
            else if (player.is_target) classes.push('target');
            else if (player.is_avoid) classes.push('avoid');
            return classes.join(' ');
        }
        
        async function openPlayerProfile(playerName) {
            selectedPlayer = playerName;
            
            // Show modal
            const modal = document.getElementById('player-profile-modal');
            modal.style.display = 'block';
            
            // Set loading state
            document.getElementById('modal-player-title').textContent = `${playerName} - Loading...`;
            document.getElementById('modal-player-content').innerHTML = '<div class="loading">Loading player details...</div>';
            
            // Load player details
            try {
                const response = await fetch(`/api/players/${encodeURIComponent(playerName)}`);
                const player = await response.json();
                console.log('Player details loaded:', player);
                
                if (player.error) {
                    document.getElementById('modal-player-content').innerHTML = 
                        `<div class="empty-state">${player.error}</div>`;
                    return;
                }
                
                document.getElementById('modal-player-title').textContent = `${player.player_name} (${player.position} - ${player.team || 'FA'})`;
                renderPlayerDetailInModal(player);
            } catch (error) {
                console.error('Error loading player details:', error);
                document.getElementById('modal-player-content').innerHTML = 
                    `<div class="empty-state">Error loading player details</div>`;
            }
        }
        
        function closePlayerProfile() {
            document.getElementById('player-profile-modal').style.display = 'none';
            selectedPlayer = null;
        }
        
        function renderPlayerDetailInModal(player) {
            const content = `
                <div style="display: flex; gap: 0.5rem; margin-bottom: 1rem;">
                    <button class="action-btn btn-analyze" onclick="analyzePlayer('${player.player_name.replace(/'/g, "\\'")}')" id="analyze-btn" style="flex: 1;">
                        🤖 Generate AI Analysis
                    </button>
                    <button class="action-btn btn-refresh" onclick="refreshPlayerStats('${player.player_name.replace(/'/g, "\\'")}')" id="refresh-btn" style="flex: 1; background: #FF9500;">
                        🔄 Refresh Stats
                    </button>
                </div>
                
                <div class="stats-grid">
                    <div class="stat-item">
                        <div class="stat-value">${player.rank_overall}</div>
                        <div class="stat-label">Overall Rank</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">$${player.draft_value}</div>
                        <div class="stat-label">Draft Value</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">${player.rank_position}</div>
                        <div class="stat-label">${player.position} Rank</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">
                            ${player.has_injury_risk ? '🚑' : '✅'} 
                            ${player.has_breakout_potential ? '💥' : ''}
                        </div>
                        <div class="stat-label">Risk Indicators</div>
                    </div>
                </div>
                
                ${player.teammates && player.teammates.length > 0 ? `
                    <div class="analysis-section">
                        <div class="section-title">Offensive Teammates</div>
                        <div class="teammates">
                            ${player.teammates.map(t => 
                                `<span class="teammate">${t.teammate_name} (${t.teammate_position})</span>`
                            ).join('')}
                        </div>
                    </div>
                ` : ''}
                
                ${player.stats ? renderPlayerStats(player.stats) : ''}
                
                ${player.analysis_text ? `
                    <div class="analysis-section">
                        <div class="section-title">🤖 AI Player Analysis</div>
                        <div class="analysis-text" style="white-space: pre-wrap; line-height: 1.6;">${player.analysis_text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')}</div>
                        
                        ${player.playing_time_score || player.injury_risk_score || player.breakout_risk_score || player.bust_risk_score ? `
                            <div class="stats-grid" style="margin-top: 1rem;">
                                ${player.playing_time_score ? `
                                    <div class="stat-item">
                                        <div class="stat-value">${player.playing_time_score}</div>
                                        <div class="stat-label">Playing Time</div>
                                    </div>
                                ` : ''}
                                ${player.injury_risk_score ? `
                                    <div class="stat-item">
                                        <div class="stat-value">${player.injury_risk_score}</div>
                                        <div class="stat-label">Injury Risk</div>
                                    </div>
                                ` : ''}
                                ${player.breakout_risk_score ? `
                                    <div class="stat-item">
                                        <div class="stat-value">${player.breakout_risk_score}</div>
                                        <div class="stat-label">Breakout Risk</div>
                                    </div>
                                ` : ''}
                                ${player.bust_risk_score ? `
                                    <div class="stat-item">
                                        <div class="stat-value">${player.bust_risk_score}</div>
                                        <div class="stat-label">Bust Risk</div>
                                    </div>
                                ` : ''}
                            </div>
                        ` : ''}
                    </div>
                ` : `
                    <div class="analysis-section">
                        <div class="section-title">🤖 AI Player Analysis</div>
                        <div style="color: #8E8E93; font-style: italic; text-align: center; padding: 2rem;">
                            Click "Generate AI Analysis" to get detailed insights about this player's 2025 fantasy outlook.
                        </div>
                    </div>
                `}
                
                ${player.draft_notes ? `
                    <div class="analysis-section">
                        <div class="section-title">Draft Notes</div>
                        <div>${player.draft_notes}</div>
                    </div>
                ` : ''}
            `;
            
            document.getElementById('modal-player-content').innerHTML = content;
        }
        
        async function toggleStatus(playerName, statusType) {
            // Find player across all positions
            let player = null;
            const positions = ['QB', 'RB', 'WR', 'TE'];
            
            // Get fresh player data
            for (const position of positions) {
                try {
                    const url = new URL('/api/players', window.location.origin);
                    url.searchParams.append('position', position);
                    url.searchParams.append('search', playerName);
                    
                    const response = await fetch(url);
                    const searchResults = await response.json();
                    const foundPlayer = searchResults.find(p => p.player_name === playerName);
                    if (foundPlayer) {
                        player = foundPlayer;
                        break;
                    }
                } catch (error) {
                    console.error(`Error searching for player in ${position}:`, error);
                }
            }
            
            if (!player) return;
            
            const updates = {
                is_target: statusType === 'target' ? !player.is_target : player.is_target,
                is_avoid: statusType === 'avoid' ? !player.is_avoid : player.is_avoid,
                is_drafted: statusType === 'drafted' ? !player.is_drafted : player.is_drafted,
                has_injury_risk: player.has_injury_risk,
                has_breakout_potential: player.has_breakout_potential
            };
            
            // Set default values for drafted fields
            if (statusType === 'drafted') {
                updates.drafted_by = '';
                updates.drafted_price = 0;
                
                // If marking as drafted, remove target status
                if (!player.is_drafted) {
                    updates.is_target = false;
                }
            }
            
            // If marking as target, remove drafted status
            if (statusType === 'target' && !player.is_target && player.is_drafted) {
                updates.is_drafted = false;
                updates.drafted_by = '';
                updates.drafted_price = 0;
            }
            
            try {
                const response = await fetch(`/api/players/${encodeURIComponent(playerName)}/status`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(updates)
                });
                
                if (response.ok) {
                    // Update local data
                    Object.assign(player, updates);
                    
                    // Refresh all position lists
                    loadAllPositions(currentFilter, currentSearch);
                    
                    // Update modal if this player is selected
                    if (selectedPlayer === playerName) {
                        renderPlayerDetailInModal(player);
                    }
                }
            } catch (error) {
                console.error('Error updating player status:', error);
            }
        }
        
        function filterPlayers(filter) {
            currentFilter = filter;
            
            // Update button states for status filters only
            document.querySelectorAll('#status-filters .filter-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            event.target.classList.add('active');
            
            loadAllPositions(filter, currentSearch);
        }
        
        function searchPlayers(searchTerm) {
            currentSearch = searchTerm;
            loadAllPositions(currentFilter, searchTerm);
        }
        
        function calculateFantasyPoints(passingStats, rushingStats, receivingStats) {
            // Half-PPR Scoring System:
            // Passing: 1 pt per 25 yards, 4 pts per TD, -2 pts per INT
            // Rushing: 1 pt per 10 yards, 6 pts per TD, -2 pts per fumble lost
            // Receiving: 1 pt per 10 yards, 6 pts per TD, 0.5 pts per reception, -2 pts per fumble lost
            
            let points = 0;
            
            // Passing points
            if (passingStats) {
                points += (passingStats.passing_yards || 0) / 25; // 1 pt per 25 yards
                points += (passingStats.passing_tds || 0) * 4; // 4 pts per TD
                points -= (passingStats.interceptions || 0) * 2; // -2 pts per INT
            }
            
            // Rushing points  
            if (rushingStats) {
                points += (rushingStats.rushing_yards || 0) / 10; // 1 pt per 10 yards
                points += (rushingStats.rushing_tds || 0) * 6; // 6 pts per TD
                points -= (rushingStats.fumbles_lost || 0) * 2; // -2 pts per fumble lost
            }
            
            // Receiving points
            if (receivingStats) {
                points += (receivingStats.receiving_yards || 0) / 10; // 1 pt per 10 yards
                points += (receivingStats.receiving_tds || 0) * 6; // 6 pts per TD
                points += (receivingStats.receptions || 0) * 0.5; // 0.5 pts per reception (half-PPR)
                points -= (receivingStats.fumbles_lost || 0) * 2; // -2 pts per fumble lost
            }
            
            return points;
        }
        
        function renderPlayerStats(stats) {
            if (!stats || (!stats.passing_stats?.length && !stats.rushing_stats?.length && !stats.receiving_stats?.length)) {
                return `
                    <div class="analysis-section">
                        <div class="section-title">📊 Player Statistics</div>
                        <div class="no-stats">No historical statistics available in database</div>
                    </div>
                `;
            }
            
            let statsHtml = '<div class="analysis-section"><div class="section-title">📊 Player Statistics</div>';
            
            // Passing Stats
            if (stats.passing_stats && stats.passing_stats.length > 0) {
                statsHtml += `
                    <div style="margin-bottom: 2rem;">
                        <h4 style="margin: 0.75rem 0 0.4rem 0; color: #1d1d1f; font-size: 0.8rem;">Passing Statistics</h4>
                        <table class="stats-table">
                            <thead>
                                <tr>
                                    <th>Season</th>
                                    <th>Team</th>
                                    <th>G</th>
                                    <th>Comp</th>
                                    <th>Att</th>
                                    <th>Comp%</th>
                                    <th>Yds</th>
                                    <th>TD</th>
                                    <th>INT</th>
                                    <th>QBR</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${stats.passing_stats.map(stat => `
                                    <tr>
                                        <td class="season-col">${stat.season}</td>
                                        <td>${stat.team_abbr || ''}</td>
                                        <td>${stat.games || 0}</td>
                                        <td>${stat.completions || 0}</td>
                                        <td>${stat.attempts || 0}</td>
                                        <td>${stat.completion_pct ? stat.completion_pct.toFixed(1) + '%' : '-'}</td>
                                        <td>${stat.passing_yards || 0}</td>
                                        <td>${stat.passing_tds || 0}</td>
                                        <td>${stat.interceptions || 0}</td>
                                        <td>${stat.quarterback_rating ? stat.quarterback_rating.toFixed(1) : '-'}</td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                `;
            }
            
            // Rushing Stats
            if (stats.rushing_stats && stats.rushing_stats.length > 0) {
                statsHtml += `
                    <div style="margin-bottom: 2rem;">
                        <h4 style="margin: 0.75rem 0 0.4rem 0; color: #1d1d1f; font-size: 0.8rem;">Rushing Statistics</h4>
                        <table class="stats-table">
                            <thead>
                                <tr>
                                    <th>Season</th>
                                    <th>Team</th>
                                    <th>G</th>
                                    <th>Att</th>
                                    <th>Yds</th>
                                    <th>Y/A</th>
                                    <th>TD</th>
                                    <th>Long</th>
                                    <th>Fum</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${stats.rushing_stats.map(stat => `
                                    <tr>
                                        <td class="season-col">${stat.season}</td>
                                        <td>${stat.team_abbr || ''}</td>
                                        <td>${stat.games || 0}</td>
                                        <td>${stat.rushing_attempts || 0}</td>
                                        <td>${stat.rushing_yards || 0}</td>
                                        <td>${stat.yards_per_attempt ? stat.yards_per_attempt.toFixed(1) : '-'}</td>
                                        <td>${stat.rushing_tds || 0}</td>
                                        <td>${stat.longest_rush || '-'}</td>
                                        <td>${stat.fumbles || 0}</td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                `;
            }
            
            // Receiving Stats
            if (stats.receiving_stats && stats.receiving_stats.length > 0) {
                statsHtml += `
                    <div style="margin-bottom: 2rem;">
                        <h4 style="margin: 0.75rem 0 0.4rem 0; color: #1d1d1f; font-size: 0.8rem;">Receiving Statistics</h4>
                        <table class="stats-table">
                            <thead>
                                <tr>
                                    <th>Season</th>
                                    <th>Team</th>
                                    <th>G</th>
                                    <th>Tgt</th>
                                    <th>Rec</th>
                                    <th>Yds</th>
                                    <th>Y/R</th>
                                    <th>TD</th>
                                    <th>Long</th>
                                    <th>Catch%</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${stats.receiving_stats.map(stat => `
                                    <tr>
                                        <td class="season-col">${stat.season}</td>
                                        <td>${stat.team_abbr || ''}</td>
                                        <td>${stat.games || 0}</td>
                                        <td>${stat.targets || 0}</td>
                                        <td>${stat.receptions || 0}</td>
                                        <td>${stat.receiving_yards || 0}</td>
                                        <td>${stat.yards_per_reception ? stat.yards_per_reception.toFixed(1) : '-'}</td>
                                        <td>${stat.receiving_tds || 0}</td>
                                        <td>${stat.longest_reception || '-'}</td>
                                        <td>${stat.catch_pct ? stat.catch_pct.toFixed(1) + '%' : '-'}</td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                `;
            }
            
            // Fantasy Points Summary
            const fantasyPointsByYear = {};
            
            // Combine all stats by season to calculate fantasy points
            const allSeasons = new Set();
            
            if (stats.passing_stats) stats.passing_stats.forEach(stat => allSeasons.add(stat.season));
            if (stats.rushing_stats) stats.rushing_stats.forEach(stat => allSeasons.add(stat.season));
            if (stats.receiving_stats) stats.receiving_stats.forEach(stat => allSeasons.add(stat.season));
            
            [...allSeasons].sort((a, b) => b - a).forEach(season => {
                const passingData = stats.passing_stats?.find(s => s.season === season);
                const rushingData = stats.rushing_stats?.find(s => s.season === season);
                const receivingData = stats.receiving_stats?.find(s => s.season === season);
                
                const fantasyPoints = calculateFantasyPoints(passingData, rushingData, receivingData);
                const games = passingData?.games || rushingData?.games || receivingData?.games || 0;
                const ppg = games > 0 ? fantasyPoints / games : 0;
                
                fantasyPointsByYear[season] = {
                    total: fantasyPoints,
                    games: games,
                    ppg: ppg,
                    team: passingData?.team_abbr || rushingData?.team_abbr || receivingData?.team_abbr || ''
                };
            });
            
            if (Object.keys(fantasyPointsByYear).length > 0) {
                statsHtml += `
                    <div style="margin-bottom: 2rem;">
                        <h4 style="margin: 0.75rem 0 0.4rem 0; color: #1d1d1f; font-size: 0.8rem;">🏆 Fantasy Points (Half-PPR)</h4>
                        <table class="stats-table">
                            <thead>
                                <tr>
                                    <th>Season</th>
                                    <th>Team</th>
                                    <th>Games</th>
                                    <th>Total Pts</th>
                                    <th>PPG</th>
                                    <th>16-Game Pace</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${Object.entries(fantasyPointsByYear)
                                    .sort(([a], [b]) => b - a)
                                    .map(([season, data]) => `
                                    <tr>
                                        <td class="season-col">${season}</td>
                                        <td>${data.team}</td>
                                        <td>${data.games}</td>
                                        <td><strong>${data.total.toFixed(1)}</strong></td>
                                        <td><strong>${data.ppg.toFixed(1)}</strong></td>
                                        <td>${(data.ppg * 16).toFixed(1)}</td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                        <div style="font-size: 0.65rem; color: #8E8E93; margin-top: 0.4rem;">
                            * Half-PPR: Pass TD=4, Rush/Rec TD=6, 25 pass yds=1, 10 rush/rec yds=1, Reception=0.5, INT/Fumble=-2
                        </div>
                    </div>
                `;
            }
            
            statsHtml += '</div>';
            return statsHtml;
        }
        
        async function analyzePlayer(playerName) {
            const analyzeBtn = document.getElementById('analyze-btn');
            if (!analyzeBtn) return;
            
            // Disable button and show loading state
            analyzeBtn.disabled = true;
            analyzeBtn.textContent = '🔄 Generating Analysis...';
            
            try {
                const response = await fetch(`/api/players/${encodeURIComponent(playerName)}/analyze`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                
                const result = await response.json();
                console.log('Analysis result:', result);
                
                if (result.success) {
                    // Refresh player profile to show new analysis
                    await openPlayerProfile(playerName);
                    
                    // Show success message briefly
                    analyzeBtn.textContent = '✅ Analysis Complete';
                    setTimeout(() => {
                        analyzeBtn.textContent = '🤖 Generate AI Analysis';
                        analyzeBtn.disabled = false;
                    }, 2000);
                } else {
                    analyzeBtn.textContent = '❌ Analysis Failed';
                    setTimeout(() => {
                        analyzeBtn.textContent = '🤖 Generate AI Analysis';
                        analyzeBtn.disabled = false;
                    }, 3000);
                    console.error('Analysis failed:', result.error);
                }
            } catch (error) {
                analyzeBtn.textContent = '❌ Error';
                setTimeout(() => {
                    analyzeBtn.textContent = '🤖 Generate AI Analysis';
                    analyzeBtn.disabled = false;
                }, 3000);
                console.error('Error analyzing player:', error);
            }
        }
        
        async function refreshPlayerStats(playerName) {
            const refreshBtn = document.getElementById('refresh-btn');
            if (!refreshBtn) return;
            
            // Disable button and show loading state
            refreshBtn.disabled = true;
            refreshBtn.textContent = '🔄 Refreshing...';
            
            try {
                const response = await fetch(`/api/players/${encodeURIComponent(playerName)}/refresh-stats`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                
                const result = await response.json();
                console.log('Refresh result:', result);
                
                if (result.success) {
                    // Refresh player profile to show updated stats
                    await openPlayerProfile(playerName);
                    
                    // Show success message briefly
                    refreshBtn.textContent = '✅ Stats Refreshed';
                    setTimeout(() => {
                        refreshBtn.textContent = '🔄 Refresh Stats';
                        refreshBtn.disabled = false;
                    }, 2000);
                } else {
                    refreshBtn.textContent = '❌ Refresh Failed';
                    setTimeout(() => {
                        refreshBtn.textContent = '🔄 Refresh Stats';
                        refreshBtn.disabled = false;
                    }, 3000);
                    console.error('Refresh failed:', result.error);
                }
            } catch (error) {
                refreshBtn.textContent = '❌ Error';
                setTimeout(() => {
                    refreshBtn.textContent = '🔄 Refresh Stats';
                    refreshBtn.disabled = false;
                }, 3000);
                console.error('Error refreshing stats:', error);
            }
        }
        
        async function refreshAllStats() {
            const refreshAllBtn = document.getElementById('refresh-all-btn');
            if (!refreshAllBtn) return;
            
            // Confirm with user since this takes a long time
            if (!confirm('This will refresh stats for the top 100 players and may take several minutes. Continue?')) {
                return;
            }
            
            // Disable button and show loading state
            refreshAllBtn.disabled = true;
            refreshAllBtn.textContent = '🔄 Refreshing All... (This may take a while)';
            
            try {
                const response = await fetch('/api/refresh-all-stats', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                
                const result = await response.json();
                console.log('Bulk refresh result:', result);
                
                if (result.success) {
                    // Refresh all position lists
                    await loadAllPositions(currentFilter, currentSearch);
                    
                    // Show success message with count
                    refreshAllBtn.textContent = `✅ ${result.message}`;
                    setTimeout(() => {
                        refreshAllBtn.textContent = '🔄 Refresh All Stats';
                        refreshAllBtn.disabled = false;
                    }, 5000);
                } else {
                    refreshAllBtn.textContent = '❌ Bulk Refresh Failed';
                    setTimeout(() => {
                        refreshAllBtn.textContent = '🔄 Refresh All Stats';
                        refreshAllBtn.disabled = false;
                    }, 3000);
                    console.error('Bulk refresh failed:', result.error);
                }
            } catch (error) {
                refreshAllBtn.textContent = '❌ Error';
                setTimeout(() => {
                    refreshAllBtn.textContent = '🔄 Refresh All Stats';
                    refreshAllBtn.disabled = false;
                }, 3000);
                console.error('Error with bulk refresh:', error);
            }
        }
    </script>
</body>
</html>
'''

if __name__ == '__main__':
    # Ensure database is initialized with draft values
    csv_path = Path('draft_values.csv')
    if csv_path.exists():
        logger.info("Importing draft values...")
        imported = db.import_draft_values(str(csv_path))
        logger.info(f"Imported {imported} draft values")
    
    app.run(debug=True, host='0.0.0.0', port=5001)