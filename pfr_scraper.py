
import requests
from bs4 import BeautifulSoup
import time
import re
from typing import List, Optional, Tuple
from dataclasses import dataclass
from urllib.parse import urljoin, quote
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
            time.sleep(self.delay)
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
            info_box = soup.find('div', {'id': 'info'})
            if not info_box:
                return None

            # Get name from h1 tag
            name_elem = soup.find('h1', {'itemprop': 'name'})
            if not name_elem:
                name_elem = soup.find('h1')
            name = name_elem.get_text().strip() if name_elem else ""

            # Position from the meta info - look for span or text containing position
            position = ""
            pos_elem = info_box.find('p', string=re.compile(r'Position:'))
            if pos_elem:
                pos_text = pos_elem.get_text()
                pos_match = re.search(r'Position:\s*(\w+)', pos_text)
                position = pos_match.group(1) if pos_match else ""
            else:
                # Try alternative approach - look for position in text
                strong_tags = info_box.find_all('strong')
                for strong in strong_tags:
                    text = strong.get_text()
                    if 'Position:' in text:
                        position = text.replace('Position:', '').strip().split()[0]
            
            # Height and weight
            height = weight = None
            hw_elem = info_box.find('span', {'itemprop': 'height'})
            if hw_elem:
                height = hw_elem.get_text().strip()
            
            wt_elem = info_box.find('span', {'itemprop': 'weight'})
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
        
        # Sort all stats by season descending (most recent first)
        passing_stats.sort(key=lambda x: x.season, reverse=True)
        rushing_stats.sort(key=lambda x: x.season, reverse=True)
        receiving_stats.sort(key=lambda x: x.season, reverse=True)
        
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
            
            try:
                year_cell = row.find('th', {'data-stat': 'year_id'})
                if not year_cell:
                    continue
                year_text = year_cell.get_text().strip()
                if not year_text.isdigit():
                    continue
                    
                season = int(year_text)
                team_cell = row.find('td', {'data-stat': 'team_name_abbr'})
                if not team_cell:
                    continue
                team = team_cell.get_text().strip()
                
                # Helper function to safely get cell text
                def get_cell_value(stat_name):
                    cell = row.find('td', {'data-stat': stat_name})
                    return cell.get_text().strip() if cell else None
                
                stats.append(PassingStats(
                    player_id=pfr_id,
                    season=season,
                    team=team,
                    games=self._safe_int(get_cell_value('games')),
                    games_started=self._safe_int(get_cell_value('games_started')),
                    completions=self._safe_int(get_cell_value('pass_cmp')),
                    attempts=self._safe_int(get_cell_value('pass_att')),
                    completion_pct=self._safe_float(get_cell_value('pass_cmp_pct')),
                    passing_yards=self._safe_int(get_cell_value('pass_yds')),
                    passing_tds=self._safe_int(get_cell_value('pass_td')),
                    interceptions=self._safe_int(get_cell_value('pass_int')),
                    yards_per_attempt=self._safe_float(get_cell_value('pass_yds_per_att')),
                    quarterback_rating=self._safe_float(get_cell_value('pass_rating')),
                ))
                
            except (AttributeError, ValueError) as e:
                logger.warning(f"Error parsing passing row for {pfr_id}: {e}")
                continue
        
        return stats
    
    def _parse_rushing_stats(self, soup: BeautifulSoup, pfr_id: str) -> List[RushingStats]:
        """Parse rushing statistics table"""
        stats = []
        rushing_table = soup.find('table', {'id': 'rushing_and_receiving'}) or soup.find('table', {'id': 'receiving_and_rushing'})
        
        if not rushing_table:
            return stats
        
        tbody = rushing_table.find('tbody')
        if not tbody:
            return stats
        
        for row in tbody.find_all('tr'):
            if 'thead' in row.get('class', []):
                continue
            
            try:
                year_cell = row.find('th', {'data-stat': 'year_id'})
                if not year_cell:
                    continue
                year_text = year_cell.get_text().strip()
                if not year_text.isdigit():
                    continue
                    
                season = int(year_text)
                team_cell = row.find('td', {'data-stat': 'team_name_abbr'})
                if not team_cell:
                    continue
                team = team_cell.get_text().strip()
                
                # Helper function to safely get cell text by data-stat attribute
                def get_cell_value(stat_name):
                    cell = row.find('td', {'data-stat': stat_name})
                    return cell.get_text().strip() if cell else None
                
                stats.append(RushingStats(
                    player_id=pfr_id,
                    season=season,
                    team=team,
                    games=self._safe_int(get_cell_value('games')),
                    games_started=self._safe_int(get_cell_value('games_started')),
                    rushing_attempts=self._safe_int(get_cell_value('rush_att')),
                    rushing_yards=self._safe_int(get_cell_value('rush_yds')),
                    yards_per_attempt=self._safe_float(get_cell_value('rush_yds_per_att')),
                    rushing_tds=self._safe_int(get_cell_value('rush_td')),
                    longest_rush=self._safe_int(get_cell_value('rush_long')),
                ))
                
            except (AttributeError, ValueError) as e:
                logger.warning(f"Error parsing rushing row for {pfr_id}: {e}")
                continue
        
        return stats
    
    def _parse_receiving_stats(self, soup: BeautifulSoup, pfr_id: str) -> List[ReceivingStats]:
        """Parse receiving statistics table"""
        stats = []
        receiving_table = soup.find('table', {'id': 'rushing_and_receiving'}) or soup.find('table', {'id': 'receiving_and_rushing'})
        
        if not receiving_table:
            return stats
        
        tbody = receiving_table.find('tbody')
        if not tbody:
            return stats
        
        for row in tbody.find_all('tr'):
            if 'thead' in row.get('class', []):
                continue
            
            try:
                year_cell = row.find('th', {'data-stat': 'year_id'})
                if not year_cell:
                    continue
                year_text = year_cell.get_text().strip()
                if not year_text.isdigit():
                    continue
                    
                season = int(year_text)
                team_cell = row.find('td', {'data-stat': 'team_name_abbr'})
                if not team_cell:
                    continue
                team = team_cell.get_text().strip()
                
                # Helper function to safely get cell text by data-stat attribute
                def get_cell_value(stat_name):
                    cell = row.find('td', {'data-stat': stat_name})
                    return cell.get_text().strip() if cell else None
                
                stats.append(ReceivingStats(
                    player_id=pfr_id,
                    season=season,
                    team=team,
                    games=self._safe_int(get_cell_value('games')),
                    games_started=self._safe_int(get_cell_value('games_started')),
                    targets=self._safe_int(get_cell_value('targets')),
                    receptions=self._safe_int(get_cell_value('rec')),
                    receiving_yards=self._safe_int(get_cell_value('rec_yds')),
                    yards_per_reception=self._safe_float(get_cell_value('rec_yds_per_rec')),
                    receiving_tds=self._safe_int(get_cell_value('rec_td')),
                    longest_reception=self._safe_int(get_cell_value('rec_long')),
                ))
                
            except (AttributeError, ValueError) as e:
                logger.warning(f"Error parsing receiving row for {pfr_id}: {e}")
                continue
        
        return stats
    
    def search_player(self, name: str) -> List[str]:
        """Search for players by name and return PFR IDs"""
        search_url = f"{self.BASE_URL}/search/search.fcgi?search={quote(name)}"
        
        try:
            logger.info(f"Fetching: {search_url}")
            response = self.session.get(search_url)
            response.raise_for_status()
            time.sleep(self.delay)
            
            # Check if we were redirected directly to a player page
            if '/players/' in response.url:
                # Extract PFR ID from the URL
                pfr_id = response.url.split('/')[-1].replace('.htm', '')
                logger.info(f"Search redirected to player page: {pfr_id}")
                return [pfr_id]
            
            # Parse search results page
            soup = BeautifulSoup(response.content, 'html.parser')
            pfr_ids = []
            search_results = soup.find('div', {'id': 'players'})
            if search_results:
                for item in search_results.find_all('div', {'class': 'search-item'}):
                    link = item.find('a')
                    if link and 'players' in link['href']:
                        pfr_id = link['href'].split('/')[-1].replace('.htm', '')
                        pfr_ids.append(pfr_id)
            return pfr_ids
            
        except requests.RequestException as e:
            logger.error(f"Error searching for {name}: {e}")
            return []

if __name__ == "__main__":
    # Example usage
    scraper = PFRScraper()
    
    # Test with JackLa00
    pfr_id = "JackLa00"
    
    print("Getting player info...")
    player_info = scraper.get_player_info(pfr_id)
    print(f"Player: {player_info}")
