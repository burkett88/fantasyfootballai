# Fantasy Football Draft Assistant

## 🏈 Overview
A comprehensive single-page application that combines all the fantasy football analysis tools into one unified draft-day assistant. Built with Flask, HTMX, and integrates with your existing player analysis system.

## ✨ Features

### Core Functionality
- **Player Database**: Complete player list with Fantasy Pros auction values
- **Real-time Search**: Fast player lookup during draft
- **Status Management**: Tag players as Target/Avoid/Drafted
- **Visual Indicators**: Color-coded status and emoji risk indicators (🚑 injury, 💥 breakout)
- **Player Details**: Comprehensive stats, teammates, and LLM analysis
- **Responsive Design**: Works on desktop and tablet

### Player Management
- **Target Players**: Green border highlight 
- **Avoid Players**: Red border highlight
- **Drafted Players**: Grayed out with strikethrough
- **Status Filters**: View All/Available/Targets/Avoid/Drafted
- **Quick Actions**: One-click status toggles

### Player Analysis Integration
- **LLM Analysis**: Pre-loaded AI analysis for each player
- **Risk Scores**: Playing time, injury, breakout, and bust risk (0-5 scales)
- **Teammate Context**: View offensive teammates for context
- **Fantasy Values**: Prominent display of auction values

## 🚀 Quick Start

### 1. Run the Draft Assistant
```bash
python draft_app.py
```
Access at: http://localhost:5001

### 2. Populate Player Analysis (Optional)
```bash
python populate_analysis.py
```
This generates LLM analysis for the top 25 players using your existing DSPy system.

## 📊 Database Schema

The app uses these key tables:

### `draft_values`
- Player rankings and Fantasy Pros auction values
- Auto-populated from your `draft_values.csv`

### `draft_player_status` 
- User draft preferences (target/avoid/drafted)
- Draft notes and custom tags
- Drafted by/price tracking

### `player_analysis`
- LLM-generated player analysis
- Risk scores and outlooks
- Integrates with existing `main.py` analysis system

### `player_teammates`
- Offensive teammate mappings
- Provides context for player evaluation

## 🎯 Draft Day Workflow

1. **Pre-Draft**: Use `populate_analysis.py` to generate analysis for key players
2. **Draft Setup**: Open the app, search and tag Target/Avoid players
3. **During Draft**: 
   - Quick search as players are nominated
   - One-click to mark players as drafted
   - View player details and analysis instantly
   - Add draft notes on the fly

## 🛠️ Technical Stack

- **Backend**: Flask with SQLite database
- **Frontend**: Vanilla JavaScript with HTMX
- **Styling**: Embedded CSS with responsive grid layout
- **AI Integration**: DSPy + OpenAI GPT-4o for player analysis
- **Data**: Pro Football Reference scraping + Fantasy Pros values

## 📱 User Interface

### Player List View
- Grid layout showing: Rank, Position, Name, Team, Value, Indicators, Actions
- Color-coded position badges (QB=orange, RB=green, WR=blue, etc.)
- Status indicators and quick action buttons

### Player Details Panel
- Key stats and auction value prominently displayed  
- Offensive teammates in horizontal card layout
- LLM analysis with risk scores
- Expandable sections for notes and analysis

### Search & Filtering
- **Real-time search**: Find players as you type
- **Status filters**: All, Available, Targets, Avoid, Drafted
- **Position filters**: All, QB, RB, WR, TE, DST, K
- **Combined filtering**: Use status + position filters together
- **Maintains state**: Filters persist during draft session

## 🔧 Integration with Existing Tools

The draft app seamlessly integrates with your existing fantasy football tools:

- **`main.py`**: Uses same DSPy analysis signature and OpenAI setup
- **`database.py`**: Extends existing database with draft-specific tables
- **`pfr_scraper.py`**: Can be used to populate additional player data
- **`player_card.py`**: HTML generation techniques adapted for the web interface

## 🎨 Customization

### Adding Custom Risk Indicators
Edit the `populate_analysis.py` script to add custom emoji indicators or modify risk scoring.

### Styling Changes
The CSS is embedded in `draft_app.py` - search for the `<style>` section to customize colors, layouts, or responsive breakpoints.

### Additional Data Sources
Extend the database schema and add new API endpoints in `draft_app.py` to integrate additional data sources.

## 📈 Performance

- **Local SQLite**: Fast queries and no external dependencies
- **Responsive Design**: Optimized for quick loading and scrolling
- **Efficient Filtering**: Client-side rendering with server-side data
- **Memory Friendly**: Lazy loading of detailed player information

## 🤝 Draft Day Tips

1. **Pre-populate targets**: Use the Target button for players you want
2. **Position-focused strategy**: Use position filters to focus on needs (e.g., click "RB" to see all running backs)
3. **Combined filtering**: Use "Available + RB" to see only undrafted running backs
4. **Mark injury risks**: Use 🚑 emoji indicator for players with injury concerns  
5. **Track breakouts**: Use 💥 emoji for players with upside potential
6. **Quick search**: Use the search box to find players as they're nominated
7. **Status tracking**: Use filters to focus on available players during draft

---

This draft assistant consolidates all your fantasy football research into a single, efficient interface optimized for live draft usage. The combination of pre-loaded analysis, real-time status tracking, and intuitive design makes it the perfect companion for fantasy success! 🏆