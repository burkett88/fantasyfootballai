-- Fantasy Football AI Database Schema
-- Stores NFL player statistics from Pro Football Reference

-- Players table - basic player information
CREATE TABLE players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pfr_id VARCHAR(10) UNIQUE NOT NULL,  -- e.g., 'MahoPa00'
    name VARCHAR(100) NOT NULL,
    position VARCHAR(5),
    height VARCHAR(10),
    weight INTEGER,
    birth_date DATE,
    college VARCHAR(100),
    drafted_year INTEGER,
    drafted_round INTEGER,
    drafted_pick INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Teams table
CREATE TABLE teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    abbreviation VARCHAR(5) UNIQUE NOT NULL,  -- e.g., 'KAN', 'NE'
    name VARCHAR(50) NOT NULL,
    city VARCHAR(50) NOT NULL
);

-- Passing statistics
CREATE TABLE passing_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    season INTEGER NOT NULL,
    games INTEGER,
    games_started INTEGER,
    completions INTEGER,
    attempts INTEGER,
    completion_pct REAL,
    passing_yards INTEGER,
    passing_tds INTEGER,
    interceptions INTEGER,
    yards_per_attempt REAL,
    yards_per_completion REAL,
    quarterback_rating REAL,
    sacks INTEGER,
    sack_yards INTEGER,
    yards_per_game REAL,
    comeback_wins INTEGER,
    game_winning_drives INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (player_id) REFERENCES players (id),
    FOREIGN KEY (team_id) REFERENCES teams (id),
    UNIQUE(player_id, season, team_id)
);

-- Rushing statistics
CREATE TABLE rushing_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    season INTEGER NOT NULL,
    games INTEGER,
    games_started INTEGER,
    rushing_attempts INTEGER,
    rushing_yards INTEGER,
    yards_per_attempt REAL,
    rushing_tds INTEGER,
    longest_rush INTEGER,
    yards_per_game REAL,
    fumbles INTEGER,
    fumbles_lost INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (player_id) REFERENCES players (id),
    FOREIGN KEY (team_id) REFERENCES teams (id),
    UNIQUE(player_id, season, team_id)
);

-- Receiving statistics
CREATE TABLE receiving_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    season INTEGER NOT NULL,
    games INTEGER,
    games_started INTEGER,
    targets INTEGER,
    receptions INTEGER,
    receiving_yards INTEGER,
    yards_per_reception REAL,
    receiving_tds INTEGER,
    longest_reception INTEGER,
    yards_per_game REAL,
    catch_pct REAL,
    yards_per_target REAL,
    fumbles INTEGER,
    fumbles_lost INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (player_id) REFERENCES players (id),
    FOREIGN KEY (team_id) REFERENCES teams (id),
    UNIQUE(player_id, season, team_id)
);

-- Draft values table - stores fantasy draft values and rankings
CREATE TABLE draft_values (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    position VARCHAR(5) NOT NULL,
    rank_overall INTEGER NOT NULL,
    rank_position INTEGER,
    player_name VARCHAR(100) NOT NULL,
    team VARCHAR(5),
    draft_value INTEGER NOT NULL DEFAULT 0,
    season INTEGER DEFAULT 2025,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Draft player status table - stores user-specific draft status and preferences
CREATE TABLE draft_player_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_name VARCHAR(100) NOT NULL,
    season INTEGER DEFAULT 2025,
    is_target BOOLEAN DEFAULT FALSE,
    is_avoid BOOLEAN DEFAULT FALSE,
    is_drafted BOOLEAN DEFAULT FALSE,
    drafted_by VARCHAR(100),
    drafted_price INTEGER,
    has_injury_risk BOOLEAN DEFAULT FALSE,
    has_breakout_potential BOOLEAN DEFAULT FALSE,
    custom_tags TEXT,
    draft_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(player_name, season)
);

-- Player analysis table - stores LLM-generated analysis for each player  
CREATE TABLE player_analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_name VARCHAR(100) NOT NULL,
    season INTEGER DEFAULT 2025,
    analysis_text TEXT NOT NULL,
    playing_time_score INTEGER,      -- -5 to 5 scale
    injury_risk_score INTEGER,       -- 0 to 5 scale  
    breakout_risk_score INTEGER,     -- 0 to 5 scale
    bust_risk_score INTEGER,         -- 0 to 5 scale
    key_changes TEXT,
    outlook TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(player_name, season)
);

-- Player teammates table - maps offensive teammates for context
CREATE TABLE player_teammates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_name VARCHAR(100) NOT NULL,
    teammate_name VARCHAR(100) NOT NULL,
    teammate_position VARCHAR(5) NOT NULL,
    season INTEGER DEFAULT 2025,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(player_name, teammate_name, season)
);

-- Indexes for better query performance
CREATE INDEX idx_players_pfr_id ON players(pfr_id);
CREATE INDEX idx_players_name ON players(name);
CREATE INDEX idx_players_position ON players(position);

CREATE INDEX idx_passing_player_season ON passing_stats(player_id, season);
CREATE INDEX idx_passing_season ON passing_stats(season);

CREATE INDEX idx_rushing_player_season ON rushing_stats(player_id, season);
CREATE INDEX idx_rushing_season ON rushing_stats(season);

CREATE INDEX idx_receiving_player_season ON receiving_stats(player_id, season);
CREATE INDEX idx_receiving_season ON receiving_stats(season);

CREATE INDEX idx_draft_values_position ON draft_values(position);
CREATE INDEX idx_draft_values_player ON draft_values(player_name);
CREATE INDEX idx_draft_values_rank ON draft_values(rank_overall);
CREATE INDEX idx_draft_values_season ON draft_values(season);

CREATE INDEX idx_draft_status_player ON draft_player_status(player_name);
CREATE INDEX idx_draft_status_season ON draft_player_status(season);
CREATE INDEX idx_draft_status_target ON draft_player_status(is_target);
CREATE INDEX idx_draft_status_drafted ON draft_player_status(is_drafted);

CREATE INDEX idx_analysis_player ON player_analysis(player_name);
CREATE INDEX idx_analysis_season ON player_analysis(season);

CREATE INDEX idx_teammates_player ON player_teammates(player_name);
CREATE INDEX idx_teammates_season ON player_teammates(season);

-- Insert common NFL teams (ignore if already exists)
INSERT OR IGNORE INTO teams (abbreviation, name, city) VALUES
('ARI', 'Cardinals', 'Arizona'),
('ATL', 'Falcons', 'Atlanta'),
('BAL', 'Ravens', 'Baltimore'),
('BUF', 'Bills', 'Buffalo'),
('CAR', 'Panthers', 'Carolina'),
('CHI', 'Bears', 'Chicago'),
('CIN', 'Bengals', 'Cincinnati'),
('CLE', 'Browns', 'Cleveland'),
('DAL', 'Cowboys', 'Dallas'),
('DEN', 'Broncos', 'Denver'),
('DET', 'Lions', 'Detroit'),
('GB', 'Packers', 'Green Bay'),
('HOU', 'Texans', 'Houston'),
('IND', 'Colts', 'Indianapolis'),
('JAX', 'Jaguars', 'Jacksonville'),
('KC', 'Chiefs', 'Kansas City'),
('KAN', 'Chiefs', 'Kansas City'),
('LV', 'Raiders', 'Las Vegas'),
('LAC', 'Chargers', 'Los Angeles'),
('LAR', 'Rams', 'Los Angeles'),
('MIA', 'Dolphins', 'Miami'),
('MIN', 'Vikings', 'Minnesota'),
('NE', 'Patriots', 'New England'),
('NO', 'Saints', 'New Orleans'),
('NYG', 'Giants', 'New York'),
('NYJ', 'Jets', 'New York'),
('PHI', 'Eagles', 'Philadelphia'),
('PIT', 'Steelers', 'Pittsburgh'),
('SF', '49ers', 'San Francisco'),
('SEA', 'Seahawks', 'Seattle'),
('TB', 'Buccaneers', 'Tampa Bay'),
('TEN', 'Titans', 'Tennessee'),
('WAS', 'Commanders', 'Washington');