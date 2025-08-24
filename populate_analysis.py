"""
Populate player analysis data using the existing LLM analysis system
Integrates with main.py functionality to generate analysis for draft players
"""

import dspy
from dotenv import load_dotenv
import os
from database import FootballDatabase
import logging
from typing import List, Dict, Any
from pathlib import Path

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure DSPy
lm = dspy.LM('openai/gpt-4o-2024-08-06', api_key=os.environ.get("OPENAI_API_KEY"))
dspy.configure(lm=lm)

class FantasyFootballAnalysis(dspy.Signature):
    """Analyze a fantasy football player for the 2025 season using data-driven sources."""
    
    player_name: str = dspy.InputField(desc="The name of the NFL player to analyze")
    
    playing_time: int = dspy.OutputField(desc="Expected change in snap count/playing time vs previous season. Scale: -5 (major decrease) to +5 (major increase), 0 = similar to last year")
    injury_risk: int = dspy.OutputField(desc="Risk of injury impacting fantasy performance. Scale: 0 (very low risk) to 5 (very high risk)")  
    breakout_risk: int = dspy.OutputField(desc="Potential for significant fantasy improvement. Scale: 0 (no upside) to 5 (massive breakout potential)")
    bust_risk: int = dspy.OutputField(desc="Risk of underperforming relative to draft position. Scale: 0 (very safe) to 5 (high bust risk)")
    key_changes: str = dspy.OutputField(desc="Major team changes affecting the player (coaching staff, personnel, scheme changes, etc.) in 2-3 sentences")
    outlook: str = dspy.OutputField(desc="Overall 2025 fantasy outlook for the player in 2-3 sentences focusing on projection and key factors")

class AnalysisPopulator:
    """Populates player analysis data for the draft application"""
    
    def __init__(self):
        self.db = FootballDatabase()
        self.analyzer = dspy.Predict(FantasyFootballAnalysis)
        
    def get_players_needing_analysis(self, season: int = 2025, limit: int = None) -> List[Dict[str, Any]]:
        """Get players from draft_values who don't have analysis yet"""
        
        query = """
            SELECT dv.player_name, dv.position, dv.team, dv.rank_overall
            FROM draft_values dv
            LEFT JOIN player_analysis pa ON dv.player_name = pa.player_name AND dv.season = pa.season
            WHERE dv.season = ? AND pa.player_name IS NULL
            ORDER BY dv.rank_overall
        """
        
        params = [season]
        if limit:
            query += f" LIMIT {limit}"
            
        with self.db.get_connection() as conn:
            cursor = conn.execute(query, params)
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def analyze_player(self, player_name: str) -> Dict[str, Any]:
        """Generate LLM analysis for a single player"""
        
        logger.info(f"Analyzing {player_name}...")
        
        try:
            result = self.analyzer(player_name=player_name)
            
            analysis_data = {
                'player_name': player_name,
                'analysis_text': f"Playing Time: {result.playing_time}/5 | Injury Risk: {result.injury_risk}/5 | Breakout: {result.breakout_risk}/5 | Bust Risk: {result.bust_risk}/5",
                'playing_time_score': result.playing_time,
                'injury_risk_score': result.injury_risk,
                'breakout_risk_score': result.breakout_risk,
                'bust_risk_score': result.bust_risk,
                'key_changes': result.key_changes,
                'outlook': result.outlook
            }
            
            return analysis_data
            
        except Exception as e:
            logger.error(f"Error analyzing {player_name}: {e}")
            return None
    
    def save_analysis(self, analysis_data: Dict[str, Any], season: int = 2025):
        """Save analysis data to database"""
        
        query = """
            INSERT OR REPLACE INTO player_analysis 
            (player_name, season, analysis_text, playing_time_score, injury_risk_score, 
             breakout_risk_score, bust_risk_score, key_changes, outlook)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        with self.db.get_connection() as conn:
            conn.execute(query, (
                analysis_data['player_name'],
                season,
                analysis_data['analysis_text'], 
                analysis_data['playing_time_score'],
                analysis_data['injury_risk_score'],
                analysis_data['breakout_risk_score'],
                analysis_data['bust_risk_score'],
                analysis_data['key_changes'],
                analysis_data['outlook']
            ))
            conn.commit()
    
    def populate_top_players(self, limit: int = 50):
        """Populate analysis for top N players"""
        
        players = self.get_players_needing_analysis(limit=limit)
        
        if not players:
            logger.info("No players need analysis")
            return
            
        logger.info(f"Found {len(players)} players needing analysis")
        
        success_count = 0
        
        for player in players:
            try:
                analysis = self.analyze_player(player['player_name'])
                if analysis:
                    self.save_analysis(analysis)
                    success_count += 1
                    logger.info(f"✅ Completed analysis for {player['player_name']} ({success_count}/{len(players)})")
                else:
                    logger.warning(f"❌ Failed to analyze {player['player_name']}")
                    
            except Exception as e:
                logger.error(f"❌ Error processing {player['player_name']}: {e}")
                
        logger.info(f"Completed: {success_count}/{len(players)} players analyzed successfully")
    
    def populate_specific_players(self, player_names: List[str]):
        """Populate analysis for specific players"""
        
        success_count = 0
        
        for player_name in player_names:
            try:
                analysis = self.analyze_player(player_name)
                if analysis:
                    self.save_analysis(analysis)
                    success_count += 1
                    logger.info(f"✅ Completed analysis for {player_name}")
                else:
                    logger.warning(f"❌ Failed to analyze {player_name}")
                    
            except Exception as e:
                logger.error(f"❌ Error processing {player_name}: {e}")
                
        logger.info(f"Completed: {success_count}/{len(player_names)} players analyzed successfully")

def populate_sample_teammates():
    """Add some sample teammate data for demonstration"""
    
    db = FootballDatabase()
    
    # Sample teammate relationships
    teammates = [
        # Chiefs offense
        ("Patrick Mahomes II", "Travis Kelce", "TE"),
        ("Patrick Mahomes II", "Isiah Pacheco", "RB"),
        ("Patrick Mahomes II", "DeAndre Hopkins", "WR"),
        ("Travis Kelce", "Patrick Mahomes II", "QB"),
        ("Isiah Pacheco", "Patrick Mahomes II", "QB"),
        
        # Bills offense  
        ("Josh Allen", "Stefon Diggs", "WR"),
        ("Josh Allen", "James Cook", "RB"),
        ("Josh Allen", "Dawson Knox", "TE"),
        ("Stefon Diggs", "Josh Allen", "QB"),
        ("James Cook", "Josh Allen", "QB"),
        
        # Eagles offense
        ("Jalen Hurts", "A.J. Brown", "WR"),
        ("Jalen Hurts", "DeVonta Smith", "WR"), 
        ("Jalen Hurts", "Saquon Barkley", "RB"),
        ("A.J. Brown", "Jalen Hurts", "QB"),
        ("Saquon Barkley", "Jalen Hurts", "QB"),
    ]
    
    with db.get_connection() as conn:
        for player, teammate, position in teammates:
            conn.execute("""
                INSERT OR IGNORE INTO player_teammates 
                (player_name, teammate_name, teammate_position, season)
                VALUES (?, ?, ?, ?)
            """, (player, teammate, position, 2025))
        
        conn.commit()
    
    logger.info(f"Added {len(teammates)} teammate relationships")

if __name__ == "__main__":
    
    # Check for OpenAI API key
    if not os.environ.get("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY environment variable not set")
        exit(1)
    
    populator = AnalysisPopulator()
    
    # Add sample teammate data
    populate_sample_teammates()
    
    # Populate analysis for top 25 players
    populator.populate_top_players(limit=25)
    
    # Example: populate specific high-value players
    # high_value_players = [
    #     "Christian McCaffrey", "Tyreek Hill", "CeeDee Lamb", 
    #     "Ja'Marr Chase", "Amon-Ra St. Brown"
    # ]
    # populator.populate_specific_players(high_value_players)