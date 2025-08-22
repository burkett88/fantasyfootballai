import webbrowser
import os
import re

def create_player_card(player_name, data):
    def convert_links(text):
        return re.sub(r'\[([^\]]+)\]\((https?://[^\)]+)\)', r'<a href="\2" target="_blank">\1</a>', text)

    def get_color_class(metric_name, value):
        if metric_name == "playing_time":
            if value <= -3:
                return "red"
            elif value >= 3:
                return "green"
            else:
                return "black"
        elif metric_name == "injury_risk":
            if value >= 3:
                return "red"
            else:
                return "black"
        elif metric_name == "breakout_risk":
            if value >= 3:
                return "green"
            else:
                return "black"
        elif metric_name == "bust_risk":
            if value >= 3:
                return "red"
            else:
                return "black"
        return "black"

    key_changes_html = convert_links(data.key_changes)
    outlook_html = convert_links(data.outlook)

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <title>Fantasy Football Player Card</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            background-color: #f0f2f5;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
        }}
        .card {{
            background-color: white;
            border-radius: 15px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
            padding: 20px;
            max-width: 600px;
            text-align: left;
        }}
        .header {{
            text-align: center;
            border-bottom: 1px solid #eee;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }}
        .header h1 {{
            margin: 0;
            color: #333;
        }}
        .section {{
            margin-bottom: 15px;
        }}
        .section h2 {{
            font-size: 1.2em;
            color: #555;
            border-bottom: 2px solid #eee;
            padding-bottom: 5px;
        }}
        .section p {{
            color: #666;
            line-height: 1.6;
        }}
        .metrics {{
            display: flex;
            justify-content: space-around;
            text-align: center;
            margin-bottom: 20px;
        }}
        .metric {{
            flex: 1;
        }}
        .metric h3 {{
            margin: 0;
            color: #333;
        }}
        .metric p {{
            margin: 5px 0 0 0;
            font-size: 1.5em;
            font-weight: bold;
        }}
        .scale {{
            font-size: 0.8em;
            color: #999;
        }}
        .red {{ color: red; }}
        .green {{ color: green; }}
        .black {{ color: black; }}
    </style>
    </head>
    <body>
    <div class="card">
        <div class="header">
            <h1>{player_name}</h1>
        </div>
        <div class="metrics">
            <div class="metric">
                <h3>Playing Time</h3>
                <p class="{get_color_class('playing_time', data.playing_time)}">{data.playing_time}</p>
                <span class="scale">(-5 to 5)</span>
            </div>
            <div class="metric">
                <h3>Injury Risk</h3>
                <p class="{get_color_class('injury_risk', data.injury_risk)}">{data.injury_risk}</p>
                <span class="scale">(0 to 5)</span>
            </div>
            <div class="metric">
                <h3>Breakout Risk</h3>
                <p class="{get_color_class('breakout_risk', data.breakout_risk)}">{data.breakout_risk}</p>
                <span class="scale">(0 to 5)</span>
            </div>
            <div class="metric">
                <h3>Bust Risk</h3>
                <p class="{get_color_class('bust_risk', data.bust_risk)}">{data.bust_risk}</p>
                <span class="scale">(0 to 5)</span>
            </div>
        </div>
        <div class="section">
            <h2>Key Changes</h2>
            <p>{key_changes_html}</p>
        </div>
        <div class="section">
            <h2>Outlook</h2>
            <p>{outlook_html}</p>
        </div>
    </div>
    </body>
    </html>
    """
    with open("player_card.html", "w") as f:
        f.write(html_content)

    filepath = os.path.abspath("player_card.html")
    webbrowser.open_new_tab(f"file://{filepath}")