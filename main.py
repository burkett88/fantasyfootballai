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
        playing_time: int = dspy.OutputField(desc="A value from -5 to 5 indicating whether we should expect more or less playing time. -5 means way less vs 2024. 0 means about the same, 5 means more playing time")
        injury_risk: int = dspy.OutputField(desc="A value from 0 to 5 indicating likelihood for injury. 0 means very low likelihood, while 5 means very high likelihood")
        breakout_risk: int = dspy.OutputField(desc="A rating from 0 to 5 indicating the likelihood that they have a significantly better year. 0 means low likelihood. 5 means high likelihood")
        bust_risk: int = dspy.OutputField(desc="A rating from 0 to 5 indicating the likelihood that they have a significantly worse year. 0 means low likehood. 5 means high likelihood")
        key_changes: str = dspy.OutputField(desc="Personnel changes or coaching changes on the team that may affect their playing time or effectiveness")
        outlook: str = dspy.OutputField(desc="An overall assessment of their outlook")

    guru = dspy.Predict(fantasyFootballSignature)

    player_data = guru(playerName=args.player_name)
    create_player_card(args.player_name, player_data)

if __name__ == "__main__":
    main()