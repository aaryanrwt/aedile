from ai_module import ai_flight_hook
from cyber_roadster_3d import run_game

if __name__ == "__main__":
    run_game(variant_label="RTK (rtk-ai/rtk)", ai_hook=ai_flight_hook)
