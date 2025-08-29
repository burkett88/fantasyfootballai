# Fantasy Football AI

## Overview
A Python-based fantasy football player analysis tool that uses DSPy and OpenAI's GPT-4 to generate detailed player reports and visual cards for the 2025 fantasy football season.

## Architecture
- **Language**: Python 3.13+
- **Main Framework**: DSPy for structured LLM interactions
- **LLM**: OpenAI GPT-4o (search-preview-2025-03-11)
- **Output**: HTML-based player cards with automatic browser launch

## Key Files

### `main.py:1-34`
Entry point that:
- Parses command line arguments for player names
- Configures DSPy with OpenAI LLM
- Defines structured signature for fantasy football analysis
- Executes player research and outputs results

### `player_card.py:1-153`
HTML card generation functionality:
- Converts markdown links to HTML
- Color-codes metrics based on risk levels
- Generates responsive HTML cards with CSS styling
- Automatically opens cards in browser

### Core Analysis Fields
The DSPy signature analyzes:
- **Playing Time**: Snap count projections vs previous season
- **Injury Risk**: Historical injury data and usage concerns
- **Breakout Risk**: Potential for significant improvement
- **Bust Risk**: Risk relative to draft position
- **Key Changes**: Team personnel/coaching changes
- **Outlook**: Overall season assessment

## Usage
```bash
python main.py "Player Name"
```

## Dependencies
- `dspy>=3.0.1`: LLM framework for structured outputs
- `python-dotenv>=1.1.1`: Environment variable management
- Requires `OPENAI_API_KEY` environment variable

## Output
- Terminal: Structured player analysis data
- Browser: Visual HTML card with color-coded metrics and linked sources

## Development Notes
- Uses data-driven fantasy football sources (not mainstream media)
- Metrics are scaled (playing time: -5 to 5, others: 0 to 5)
- HTML cards include embedded CSS and responsive design
- Generated cards are saved as `player_card.html`

## Draft Application (`draft_app.py`)

### Architecture
- **Framework**: Flask web application with SQLite database
- **Frontend**: Single-page application with embedded HTML/CSS/JavaScript
- **Database**: SQLite with comprehensive fantasy football schema
- **Responsive Design**: CSS Grid with mobile-first approach

### Key Features
- **Auction Value Inflation**: 11% market adjustment factor for current conditions
- **4-Column Position Layout**: QB, RB, WR, TE split for optimal draft visibility
- **Position Filtering**: K and DST positions filtered by default
- **Modal-Based Player Profiles**: Replace side panels for better UX
- **Status Management**: Target/avoid/drafted with mutual exclusion logic
- **Compact Design**: Maximizes visible players with tight spacing

### Technical Implementation Lessons

#### CSS Grid Layout Challenges
- **Problem**: Variable player name lengths caused T/A/D button alignment issues
- **Solution**: Fixed-width columns (`100px` for names) with `text-overflow: ellipsis`
- **Learning**: Use fixed widths for alignment-critical layouts, not flexible (`1fr`)

#### Responsive Design Strategy
```css
.main-container {
    grid-template-columns: 1fr 1fr 1fr 1fr;  /* Desktop: 4 columns */
}

@media (max-width: 1200px) {
    .main-container {
        grid-template-columns: 1fr 1fr;      /* Tablet: 2x2 grid */
        grid-template-rows: 1fr 1fr;
    }
}

@media (max-width: 768px) {
    .main-container {
        grid-template-columns: 1fr;          /* Mobile: stacked */
        grid-template-rows: 1fr 1fr 1fr 1fr;
    }
}
```

#### Database Query Optimization
- **Inflation Calculation**: Done at database level (`ROUND(dv.draft_value * ?)`) 
- **Position Filtering**: Server-side filtering (`NOT IN ('K', 'DST')`)
- **Status Joins**: LEFT JOIN for optional player status data

#### JavaScript State Management
- **Problem**: Managing player data across 4 separate position grids
- **Solution**: Async loading per position with shared status update functions
- **Pattern**: `loadAllPositions()` → `renderPositionList()` per position

#### Modal vs Side Panel UX
- **Before**: Side panel competed for screen real estate
- **After**: Modal overlay provides focused player view without layout disruption
- **Implementation**: Fixed positioning with backdrop blur and centered content

#### Status Logic Patterns
```javascript
// Mutual exclusion between drafted and target status
if (!player.is_drafted) {
    updates.is_target = false;  // Drafting removes target
}

if (statusType === 'target' && !player.is_target && player.is_drafted) {
    updates.is_drafted = false;  // Targeting removes drafted
}
```

### Performance Optimizations
- **Compact Font Sizes**: `0.65rem` base with `0.5rem` for secondary info
- **Minimal Padding**: `0.2rem 0.25rem` for tight row spacing
- **Grid Gap Reduction**: `0.1rem` gaps instead of `0.5rem`
- **Fixed Row Heights**: `min-height: 22px` for consistent spacing

### Common Pitfalls Avoided
1. **Horizontal Scrolling**: Careful width calculations prevent overflow
2. **Button Visibility**: Fixed widths ensure buttons always appear
3. **Modal Accessibility**: Proper backdrop and close button positioning
4. **Database Consistency**: Proper transaction handling for status updates
5. **Responsive Breakpoints**: Tested across device sizes for optimal layout

### Testing Commands
```bash
# Start development server
python draft_app.py

# Database queries for debugging
sqlite3 football_stats.db "SELECT * FROM draft_values LIMIT 5;"

# Check git status and commit
git status && git add . && git commit -m "message" && git push
```