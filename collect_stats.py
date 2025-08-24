"""
Main data collection pipeline for NFL player statistics.
Orchestrates scraping from Pro Football Reference and storing in local database.
"""

import argparse
import logging
import time
from typing import List, Optional
from pathlib import Path

from pfr_scraper import PFRScraper
from database import FootballDatabase

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class StatsCollector:
    """Main class for collecting and storing NFL statistics"""
    
    def __init__(self, db_path: str = "football_stats.db", scraper_delay: float = 2.0):
        """
        Initialize the stats collector
        
        Args:
            db_path: Path to SQLite database
            scraper_delay: Delay between scraper requests (seconds)
        """
        self.db = FootballDatabase(db_path)
        self.scraper = PFRScraper(delay=scraper_delay)
        
    def collect_player_stats(self, pfr_id: str) -> bool:
        """
        Collect all stats for a single player
        
        Args:
            pfr_id: Pro Football Reference player ID (e.g., 'MahoPa00')
            
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Collecting stats for player: {pfr_id}")
        
        try:
            # Get player info
            player_info = self.scraper.get_player_info(pfr_id)
            if not player_info:
                logger.error(f"Could not get player info for {pfr_id}")
                return False
            
            # Insert player into database
            player_db_id = self.db.insert_player(player_info)
            logger.info(f"Player {player_info.name} stored with ID: {player_db_id}")
            
            # Get all stats
            passing_stats, rushing_stats, receiving_stats = self.scraper.get_player_stats(pfr_id)
            
            # Store stats in database
            if passing_stats:
                self.db.insert_passing_stats(passing_stats)
                logger.info(f"Stored {len(passing_stats)} passing seasons for {player_info.name}")
            
            if rushing_stats:
                self.db.insert_rushing_stats(rushing_stats)
                logger.info(f"Stored {len(rushing_stats)} rushing seasons for {player_info.name}")
            
            if receiving_stats:
                self.db.insert_receiving_stats(receiving_stats)
                logger.info(f"Stored {len(receiving_stats)} receiving seasons for {player_info.name}")
            
            logger.info(f"Successfully collected stats for {player_info.name}")
            return True
            
        except Exception as e:
            logger.error(f"Error collecting stats for {pfr_id}: {e}")
            return False
    
    def collect_multiple_players(self, pfr_ids: List[str]) -> dict:
        """
        Collect stats for multiple players
        
        Args:
            pfr_ids: List of PFR player IDs
            
        Returns:
            Dictionary with success/failure counts
        """
        results = {'successful': 0, 'failed': 0, 'errors': []}
        
        for i, pfr_id in enumerate(pfr_ids):
            logger.info(f"Processing player {i+1}/{len(pfr_ids)}: {pfr_id}")
            
            try:
                success = self.collect_player_stats(pfr_id)
                if success:
                    results['successful'] += 1
                else:
                    results['failed'] += 1
                    results['errors'].append(f"{pfr_id}: Failed to collect stats")
                
                # Add delay between players to be respectful
                if i < len(pfr_ids) - 1:
                    time.sleep(1.0)
                    
            except Exception as e:
                results['failed'] += 1
                results['errors'].append(f"{pfr_id}: {str(e)}")
                logger.error(f"Unexpected error processing {pfr_id}: {e}")
        
        return results
    
    def get_top_fantasy_players(self) -> List[str]:
        """
        Get a list of top fantasy football player PFR IDs
        This is a curated list of top players for fantasy football analysis
        """
        top_players = [
            # Top QBs
            "MahoPa00",  # Patrick Mahomes
            "AlleJo02",  # Josh Allen  
            "HurbJa00",  # Jalen Hurts
            "LamJa01",   # Lamar Jackson
            "BurrJo01",  # Joe Burrow
            "AlleDa00",  # Dak Prescott
            "TuaTa00",   # Tua Tagovailoa
            "RogeAa00",  # Aaron Rodgers
            
            # Top RBs
            "McCaCh01",  # Christian McCaffrey
            "HallBr00",  # Breece Hall
            "BarkSa00",  # Saquon Barkley
            "CookDa01",  # Dalvin Cook
            "JackJo02",  # Josh Jacobs
            "ChubNi00",  # Nick Chubb
            "KamaAl00",  # Alvin Kamara
            "MixoJo00",  # Joe Mixon
            "TaylJo02",  # Jonathan Taylor
            
            # Top WRs
            "JeffJu00",  # Justin Jefferson
            "ChasCo00",  # Cooper Kupp
            "HillTy00",  # Tyreek Hill
            "AdamDa01",  # Davante Adams
            "DigsSt01",  # Stefon Diggs
            "EvanMi00",  # Mike Evans
            "BrowAJ00",  # AJ Brown
            "KirkCh01",  # Christian Kirk
            "LambCe00",  # CeeDee Lamb
            "MetcDK00",  # DK Metcalf
            
            # Top TEs
            "KelcTr00",  # Travis Kelce
            "AndrMa01",  # Mark Andrews
            "KittGe00",  # George Kittle
            "WallDa03",  # Darren Waller
            "PittKy00",  # Kyle Pitts
        ]
        
        return top_players
    
    def collect_top_players(self) -> dict:
        """Collect stats for top fantasy football players"""
        top_players = self.get_top_fantasy_players()
        logger.info(f"Collecting stats for {len(top_players)} top fantasy players")
        return self.collect_multiple_players(top_players)
    
    def update_player(self, name_or_id: str) -> bool:
        """
        Update stats for a specific player by name or PFR ID
        
        Args:
            name_or_id: Player name or PFR ID
            
        Returns:
            True if successful
        """
        # If it looks like a PFR ID, use it directly
        if len(name_or_id) <= 10 and any(c.isdigit() for c in name_or_id):
            pfr_id = name_or_id
        else:
            # Search for the player
            pfr_ids = self.scraper.search_player(name_or_id)
            if not pfr_ids:
                logger.error(f"Could not find PFR ID for: {name_or_id}")
                return False
            pfr_id = pfr_ids[0]
        
        return self.collect_player_stats(pfr_id)
    
    def show_database_stats(self):
        """Show current database statistics"""
        stats = self.db.get_database_stats()
        print("\n=== Database Statistics ===")
        for table, count in stats.items():
            print(f"{table}: {count:,} records")
        print()
    
    def search_and_show_player(self, query: str):
        """Search for a player and show their stats"""
        stats = self.db.get_player_stats(query)
        
        if not stats:
            print(f"No player found matching: {query}")
            return
        
        player = stats['player']
        print(f"\n=== {player['name']} ({player['position']}) ===")
        print(f"PFR ID: {player['pfr_id']}")
        if player['height']: print(f"Height: {player['height']}")
        if player['weight']: print(f"Weight: {player['weight']} lbs")
        
        # Show recent stats
        if stats['passing_stats']:
            latest_passing = stats['passing_stats'][-1]
            print(f"\nLatest Passing ({latest_passing['season']}): "
                  f"{latest_passing['passing_yards']} yards, "
                  f"{latest_passing['passing_tds']} TDs")
        
        if stats['rushing_stats']:
            latest_rushing = stats['rushing_stats'][-1]
            print(f"Latest Rushing ({latest_rushing['season']}): "
                  f"{latest_rushing['rushing_yards']} yards, "
                  f"{latest_rushing['rushing_tds']} TDs")
        
        if stats['receiving_stats']:
            latest_receiving = stats['receiving_stats'][-1]
            print(f"Latest Receiving ({latest_receiving['season']}): "
                  f"{latest_receiving['receiving_yards']} yards, "
                  f"{latest_receiving['receiving_tds']} TDs")

def main():
    """Main CLI interface"""
    parser = argparse.ArgumentParser(description='NFL Stats Collector')
    parser.add_argument('--collect-top', action='store_true', 
                       help='Collect stats for top fantasy players')
    parser.add_argument('--player', type=str,
                       help='Collect stats for specific player (name or PFR ID)')
    parser.add_argument('--search', type=str,
                       help='Search for player and show stats')
    parser.add_argument('--stats', action='store_true',
                       help='Show database statistics')
    parser.add_argument('--db-path', default='football_stats.db',
                       help='Path to SQLite database')
    parser.add_argument('--delay', type=float, default=2.0,
                       help='Delay between scraper requests (seconds)')
    
    args = parser.parse_args()
    
    collector = StatsCollector(db_path=args.db_path, scraper_delay=args.delay)
    
    if args.stats:
        collector.show_database_stats()
    
    if args.search:
        collector.search_and_show_player(args.search)
    
    if args.player:
        success = collector.update_player(args.player)
        if success:
            print(f"Successfully updated stats for: {args.player}")
        else:
            print(f"Failed to update stats for: {args.player}")
    
    if args.collect_top:
        print("Collecting stats for top fantasy football players...")
        print("This may take several minutes due to rate limiting...")
        results = collector.collect_top_players()
        
        print(f"\n=== Collection Results ===")
        print(f"Successful: {results['successful']}")
        print(f"Failed: {results['failed']}")
        
        if results['errors']:
            print("\nErrors:")
            for error in results['errors']:
                print(f"  - {error}")
        
        collector.show_database_stats()

if __name__ == "__main__":
    main()