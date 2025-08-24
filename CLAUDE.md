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