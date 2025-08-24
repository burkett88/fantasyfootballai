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

    class fantasyFootballPlayerResearcher(dspy.Signature):
        """This is a very detailed report for football players in the 2025 fantasy football season. This summarizes data from data-driven sources of fantasy football knowledge and not just mainstream sources like cbs."""
        playerName: str = dspy.InputField(desc="Fantasy Football Player Name")
        playing_time: str = dspy.OutputField(desc="Indications about how this players snap count may compare vs the previous season.")
        injury_risk: str = dspy.OutputField(desc="Research on the injury risk for this player in 2025. Consider their injury history and usage.")
        breakout_risk: str = dspy.OutputField(desc="Research on whether people expect this player to potentially breakout, which we define as a significant improvement to their per game points. Include direct quotes where appropriate.")
        bust_risk: str = dspy.OutputField(desc="Research on whether this player could be a bust, particularly relative to where they are being drafted")
        key_changes: str = dspy.OutputField(desc="Personnel changes or coaching changes on the team that may affect their playing time or effectiveness")
        outlook: str = dspy.OutputField(desc="An overall assessment of their outlook")

    playerResearcher = dspy.Predict(fantasyFootballPlayerResearcher)

    player_data = playerResearcher(playerName=args.player_name)
    print (player_data)

if __name__ == "__main__":
    main()