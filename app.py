from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import os
import dspy
import traceback
import re
from dataclasses import dataclass
from typing import Optional

load_dotenv()

app = Flask(__name__)

# Check if API key is loaded
api_key = os.getenv("OPENAI_API_KEY")
print(f"API Key loaded: {'Yes' if api_key else 'No'}")
print(f"API Key starts with: {api_key[:10] if api_key else 'None'}...")

# Configure DSPy once at startup
lm = dspy.LM("openai/gpt-4o-search-preview-2025-03-11", api_key=api_key, temperature=None)
dspy.configure(lm=lm)

# Define the DSPy signature once
class fantasyFootballPlayerResearcher(dspy.Signature):
    """This is a very detailed report for football players in the 2025 fantasy football season. This summarizes data from data-driven sources of fantasy football knowledge and not just mainstream sources like cbs."""
    playerName: str = dspy.InputField(desc="Fantasy Football Player Name")
    playing_time: str = dspy.OutputField(desc="Indications about how this players snap count may compare vs the previous season.")
    injury_risk: str = dspy.OutputField(desc="Research on the injury risk for this player in 2025. Consider their injury history and usage.")
    breakout_risk: str = dspy.OutputField(desc="Research on whether people expect this player to potentially breakout, which we define as a significant improvement to their per game points. Include direct quotes where appropriate.")
    bust_risk: str = dspy.OutputField(desc="Research on whether this player could be a bust, particularly relative to where they are being drafted")
    key_changes: str = dspy.OutputField(desc="Personnel changes or coaching changes on the team that may affect their playing time or effectiveness")
    outlook: str = dspy.OutputField(desc="An overall assessment of their outlook")

# Create the predictor once
playerResearcher = dspy.Predict(fantasyFootballPlayerResearcher)

@dataclass
class PlayerAnalysis:
    playerName: str
    playing_time: str
    injury_risk: str
    breakout_risk: str
    bust_risk: str
    key_changes: str
    outlook: str

def convert_markdown_links(text: str) -> str:
    """Convert markdown-style links to HTML"""
    # Pattern to match [text](url)
    pattern = r'\[([^\]]+)\]\((https?://[^\)]+)\)'
    replacement = r'<a href="\2" target="_blank" class="text-blue-600 hover:text-blue-800 underline">\1</a>'
    return re.sub(pattern, replacement, text)

def get_player_analysis(player_name: str) -> Optional[PlayerAnalysis]:
    """Get player analysis using DSPy"""
    try:
        result = playerResearcher(playerName=player_name)
        
        return PlayerAnalysis(
            playerName=player_name,
            playing_time=convert_markdown_links(result.playing_time),
            injury_risk=convert_markdown_links(result.injury_risk),
            breakout_risk=convert_markdown_links(result.breakout_risk),
            bust_risk=convert_markdown_links(result.bust_risk),
            key_changes=convert_markdown_links(result.key_changes),
            outlook=convert_markdown_links(result.outlook)
        )
    except Exception as e:
        print(f"Error analyzing player {player_name}: {str(e)}")
        traceback.print_exc()
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze_player():
    player_name = request.form.get('player_name', '').strip()
    
    if not player_name:
        return render_template('error.html', error="Please enter a player name"), 400
    
    print(f"Starting analysis for player: {player_name}")
    analysis = get_player_analysis(player_name)
    
    if not analysis:
        print(f"Analysis failed for player: {player_name}")
        return render_template('error.html', error="Failed to analyze player. Please try again."), 500
    
    print(f"Analysis completed successfully for player: {player_name}")
    return render_template('player_card.html', analysis=analysis)

@app.route('/loading')
def loading():
    return render_template('loading.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)