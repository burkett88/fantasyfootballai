import dspy
from dotenv import load_dotenv
import os
import argparse
from player_card import create_player_card

def main():
    parser = argparse.ArgumentParser(description="Fantasy football player analysis.")
    parser.add_argument("player_name", help="The name of the fantasy football player.")
    args = parser.parse_args()

    load_dotenv()

    lm = dspy.LM("openai/gpt-4o-search-preview-2025-03-11", api_key=os.getenv("OPENAI_API_KEY"), temperature=None)
    dspy.configure(lm=lm)

    class fantasyFootballSignature(dspy.Signature):
        """This tool is a researcher for players in the 2025 fantasy football season"""
        playerName: str = dspy.InputField(desc="Fantasy Football Player Name")
        playing_time: str = dspy.OutputField(desc="Indications about how this players snap count may compare vs the previous season.")
        injury_risk: str = dspy.OutputField(desc="Research on the injury risk for this player in 2025")
        breakout_risk: str = dspy.OutputField(desc="Research on whether people expect this player to potentially breakout, which we define as a significant improvement to their per game points")
        bust_risk: str = dspy.OutputField(desc="Research on whether this player could be a bust, particularly relative to where they are being drafted")
        key_changes: str = dspy.OutputField(desc="Personnel changes or coaching changes on the team that may affect their playing time or effectiveness")
        outlook: str = dspy.OutputField(desc="An overall assessment of their outlook")

    guru = dspy.Predict(fantasyFootballSignature)

    player_data = guru(playerName=args.player_name)
    print (player_data)
    #create_player_card(args.player_name, player_data)

if __name__ == "__main__":
    main()