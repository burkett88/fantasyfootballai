"""
Pro Football Reference scraper for collecting NFL player statistics.
Scrapes passing, rushing, and receiving stats for fantasy football analysis.
"""

import requests
from bs4 import BeautifulSoup
import time
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from urllib.parse import urljoin
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class PlayerInfo:
    """Basic player information"""
    pfr_id: str
    name: str
    position: str
    height: Optional[str] = None
    weight: Optional[int] = None
    birth_date: Optional[str] = None
    college: Optional[str] = None
    drafted_year: Optional[int] = None
    drafted_round: Optional[int] = None
    drafted_pick: Optional[int] = None

@dataclass
class PassingStats:
    """Season passing statistics"""
    player_id: str
    season: int
    team: str
    games: Optional[int] = None
    games_started: Optional[int] = None
    completions: Optional[int] = None
    attempts: Optional[int] = None
    completion_pct: Optional[float] = None
    passing_yards: Optional[int] = None
    passing_tds: Optional[int] = None
    interceptions: Optional[int] = None
    yards_per_attempt: Optional[float] = None
    yards_per_completion: Optional[float] = None
    quarterback_rating: Optional[float] = None
    sacks: Optional[int] = None
    sack_yards: Optional[int] = None

@dataclass
class RushingStats:
    """Season rushing statistics"""
    player_id: str
    season: int
    team: str
    games: Optional[int] = None
    games_started: Optional[int] = None
    rushing_attempts: Optional[int] = None
    rushing_yards: Optional[int] = None
    yards_per_attempt: Optional[float] = None
    rushing_tds: Optional[int] = None
    longest_rush: Optional[int] = None
    fumbles: Optional[int] = None
    fumbles_lost: Optional[int] = None

@dataclass
class ReceivingStats:
    """Season receiving statistics"""
    player_id: str
    season: int
    team: str
    games: Optional[int] = None
    games_started: Optional[int] = None
    targets: Optional[int] = None
    receptions: Optional[int] = None
    receiving_yards: Optional[int] = None
    yards_per_reception: Optional[float] = None
    receiving_tds: Optional[int] = None
    longest_reception: Optional[int] = None
    catch_pct: Optional[float] = None
    yards_per_target: Optional[float] = None
    fumbles: Optional[int] = None
    fumbles_lost: Optional[int] = None

class PFRScraper:
    """Pro Football Reference web scraper"""
    
    BASE_URL = "https://www.pro-football-reference.com"
    
    def __init__(self, delay: float = 1.0):
        """
        Initialize scraper with rate limiting
        
        Args:
            delay: Seconds to wait between requests (respect robots.txt)
        """
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
    
    def _get_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch and parse a webpage with rate limiting"""
        try:
            logger.info(f"Fetching: {url}")
            response = self.session.get(url)
            response.raise_for_status()
            time.sleep(self.delay)  # Rate limiting
            return BeautifulSoup(response.content, 'html.parser')
        except requests.RequestException as e:
            logger.error(f"Error fetching {url}: {e}")
            return None
    
    def _safe_int(self, value: str) -> Optional[int]:
        """Safely convert string to int"""
        if not value or value == '' or value == '--':
            return None
        try:
            return int(value.replace(',', ''))
        except (ValueError, AttributeError):
            return None
    
    def _safe_float(self, value: str) -> Optional[float]:
        """Safely convert string to float"""
        if not value or value == '' or value == '--':
            return None
        try:
            return float(value.replace('%', ''))
        except (ValueError, AttributeError):
            return None
    
    def get_player_info(self, pfr_id: str) -> Optional[PlayerInfo]:
        """Get basic player information from their PFR page"""
        url = f"{self.BASE_URL}/players/{pfr_id[0]}/{pfr_id}.htm"
        soup = self._get_page(url)
        
        if not soup:
            return None
        
        try:
            # Extract basic info from the player header - try multiple selectors
            name_elem = soup.find('h1', {'itemprop': 'name'}) or soup.find('h1')
            if name_elem:
                name_text = name_elem.get_text().strip()
                # Clean up name - remove nicknames in parentheses
                name = name_text.split('(')[0].strip()
            else:
                name = ""
            
            # Position from the meta info
            pos_elem = soup.find('p', string=re.compile(r'Position:'))
            position = ""
            if pos_elem:
                pos_text = pos_elem.get_text()
                pos_match = re.search(r'Position:\s*(\w+)', pos_text)
                position = pos_match.group(1) if pos_match else ""
            
            # Height and weight
            height = weight = None
            hw_elem = soup.find('span', {'itemprop': 'height'})
            if hw_elem:
                height = hw_elem.get_text().strip()
            
            wt_elem = soup.find('span', {'itemprop': 'weight'})
            if wt_elem:
                weight_text = wt_elem.get_text().strip()
                weight = self._safe_int(weight_text.replace('lb', ''))
            
            return PlayerInfo(
                pfr_id=pfr_id,
                name=name,
                position=position,
                height=height,
                weight=weight
            )
            
        except Exception as e:
            logger.error(f"Error parsing player info for {pfr_id}: {e}")
            return None
    
    def get_player_stats(self, pfr_id: str) -> Tuple[List[PassingStats], List[RushingStats], List[ReceivingStats]]:
        """Get all stats for a player"""
        url = f"{self.BASE_URL}/players/{pfr_id[0]}/{pfr_id}.htm"
        soup = self._get_page(url)
        
        if not soup:
            return [], [], []
        
        passing_stats = self._parse_passing_stats(soup, pfr_id)
        rushing_stats = self._parse_rushing_stats(soup, pfr_id)
        receiving_stats = self._parse_receiving_stats(soup, pfr_id)
        
        return passing_stats, rushing_stats, receiving_stats
    
    def _parse_passing_stats(self, soup: BeautifulSoup, pfr_id: str) -> List[PassingStats]:
        """Parse passing statistics table"""
        stats = []
        passing_table = soup.find('table', {'id': 'passing'})
        
        if not passing_table:
            return stats
        
        tbody = passing_table.find('tbody')
        if not tbody:
            return stats
        
        for row in tbody.find_all('tr'):
            if 'thead' in row.get('class', []):
                continue
                
            cells = row.find_all(['td', 'th'])
            if len(cells) < 15:  # Minimum expected columns
                continue
            
            try:
                year_text = cells[0].get_text().strip()
                if not year_text.isdigit():
                    continue
                    
                season = int(year_text)
                team = cells[2].get_text().strip()
                
                stats.append(PassingStats(
                    player_id=pfr_id,
                    season=season,
                    team=team,
                    games=self._safe_int(cells[4].get_text().strip()),
                    games_started=self._safe_int(cells[5].get_text().strip()),
                    completions=self._safe_int(cells[7].get_text().strip()),
                    attempts=self._safe_int(cells[8].get_text().strip()),
                    completion_pct=self._safe_float(cells[9].get_text().strip()),
                    passing_yards=self._safe_int(cells[10].get_text().strip()),
                    passing_tds=self._safe_int(cells[11].get_text().strip()),
                    interceptions=self._safe_int(cells[12].get_text().strip()),
                    yards_per_attempt=self._safe_float(cells[15].get_text().strip()),
                    quarterback_rating=self._safe_float(cells[17].get_text().strip()),
                ))
                
            except (IndexError, ValueError) as e:
                logger.warning(f"Error parsing passing row for {pfr_id}: {e}")
                continue
        
        return stats
    
    def _parse_rushing_stats(self, soup: BeautifulSoup, pfr_id: str) -> List[RushingStats]:
        """Parse rushing statistics table"""
        stats = []
        rushing_table = soup.find('table', {'id': 'rushing_and_receiving'})
        
        if not rushing_table:
            return stats
        
        tbody = rushing_table.find('tbody')
        if not tbody:
            return stats
        
        for row in tbody.find_all('tr'):
            if 'thead' in row.get('class', []):
                continue
                
            cells = row.find_all(['td', 'th'])
            if len(cells) < 10:
                continue
            
            try:
                year_text = cells[0].get_text().strip()
                if not year_text.isdigit():
                    continue
                    
                season = int(year_text)
                team = cells[2].get_text().strip()
                
                stats.append(RushingStats(
                    player_id=pfr_id,
                    season=season,
                    team=team,
                    games=self._safe_int(cells[4].get_text().strip()),
                    games_started=self._safe_int(cells[5].get_text().strip()),
                    rushing_attempts=self._safe_int(cells[6].get_text().strip()),
                    rushing_yards=self._safe_int(cells[7].get_text().strip()),
                    yards_per_attempt=self._safe_float(cells[8].get_text().strip()),
                    rushing_tds=self._safe_int(cells[9].get_text().strip()),
                    longest_rush=self._safe_int(cells[10].get_text().strip()),
                ))
                
            except (IndexError, ValueError) as e:
                logger.warning(f"Error parsing rushing row for {pfr_id}: {e}")
                continue
        
        return stats
    
    def _parse_receiving_stats(self, soup: BeautifulSoup, pfr_id: str) -> List[ReceivingStats]:
        """Parse receiving statistics table"""
        stats = []
        receiving_table = soup.find('table', {'id': 'rushing_and_receiving'})
        
        if not receiving_table:
            return stats
        
        tbody = receiving_table.find('tbody')
        if not tbody:
            return stats
        
        for row in tbody.find_all('tr'):
            if 'thead' in row.get('class', []):
                continue
                
            cells = row.find_all(['td', 'th'])
            if len(cells) < 18:  # Need receiving columns
                continue
            
            try:
                year_text = cells[0].get_text().strip()
                if not year_text.isdigit():
                    continue
                    
                season = int(year_text)
                team = cells[2].get_text().strip()
                
                stats.append(ReceivingStats(
                    player_id=pfr_id,
                    season=season,
                    team=team,
                    games=self._safe_int(cells[4].get_text().strip()),
                    games_started=self._safe_int(cells[5].get_text().strip()),
                    targets=self._safe_int(cells[11].get_text().strip()),
                    receptions=self._safe_int(cells[12].get_text().strip()),
                    receiving_yards=self._safe_int(cells[13].get_text().strip()),
                    yards_per_reception=self._safe_float(cells[14].get_text().strip()),
                    receiving_tds=self._safe_int(cells[15].get_text().strip()),
                    longest_reception=self._safe_int(cells[16].get_text().strip()),
                ))
                
            except (IndexError, ValueError) as e:
                logger.warning(f"Error parsing receiving row for {pfr_id}: {e}")
                continue
        
        return stats
    
    def search_player(self, name: str) -> List[str]:
        """Search for players by name and return PFR IDs"""
        # This is a simplified search - PFR has a search endpoint
        # For now, we'll generate the expected PFR ID format
        # Real implementation would use PFR's search API
        
        name_parts = name.strip().split()
        if len(name_parts) < 2:
            return []
        
        first_name = name_parts[0]
        last_name = name_parts[-1]
        
        # PFR ID format: LastName(first4chars)FirstName(first2chars)00
        # Examples: MahoPa00 (Mahomes + Pa), AlleJo02 (Allen + Jo)
        pfr_id = f"{last_name[:4]}{first_name[:2]}00"
        
        return [pfr_id]

if __name__ == "__main__":
    # Example usage
    scraper = PFRScraper()
    
    # Test with Patrick Mahomes
    pfr_id = "MahoPa00"
    
    print("Getting player info...")
    player_info = scraper.get_player_info(pfr_id)
    print(f"Player: {player_info}")
    
    print("\nGetting stats...")
    passing, rushing, receiving = scraper.get_player_stats(pfr_id)
    
    print(f"Found {len(passing)} passing seasons")
    print(f"Found {len(rushing)} rushing seasons")  
    print(f"Found {len(receiving)} receiving seasons")
    
    if passing:
        print(f"Latest passing stats: {passing[-1]}")