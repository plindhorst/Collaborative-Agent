from Group58Agent.Group58Agent import Group58Agent
from agents1.BW4THuman import Human
from bw4t.BW4TWorld import BW4TWorld, DEFAULT_WORLDSETTINGS
from bw4t.statistics import Statistics
import argparse

"""
This runs a single session. You have to log in on localhost:3000 and
press the start button in god mode to start the session.
"""

if __name__ == "__main__":
    agents = [
        # {
        #     "name": "Lazy",
        #     "botclass": Group58Agent,
        #     "settings": {"color": "#FFFF00", "shape": 1, "strong": False, "colourblind": False, "lazy": True, "liar": False},
        # },
        # {
        #     "name": "Strong",
        #     "botclass": Group58Agent,
        #     "settings": {"color": "#0000FF", "shape": 2, "strong": True, "colourblind": False, "lazy": False, "liar": False},
        # },
        # {
        #     "name": "ColourBlind",
        #     "botclass": Group58Agent,
        #     "settings": {"color": "#000000", "shape": 1, "strong": False, "colourblind": True, "lazy": False, "liar": False},
        # },
        # {
        #     "name": "Liar",
        #     "botclass": Group58Agent,
        #     "settings": {"color": "#FF0000", "shape": 1, "strong": False, "colourblind": False, "lazy": False,
        #                  "liar": True},
        # },
        {
            "name": "Normal0",
            "botclass": Group58Agent,
            "settings": {"color": "#0000FF", "shape": 1, "strong": False, "colourblind": False, "lazy": False,
                         "liar": False},
        },
        {
            "name": "Normal1",
            "botclass": Group58Agent,
            "settings": {"color": "#0000FF", "shape": 1, "strong": False, "colourblind": False, "lazy": False,
                         "liar": False},
        },
        {
            "name": "Normal2",
            "botclass": Group58Agent,
            "settings": {"color": "#0000FF", "shape": 1, "strong": False, "colourblind": False, "lazy": False,
                         "liar": False},
        },
        {
            "name": "Normal3",
            "botclass": Group58Agent,
            "settings": {"color": "#0000FF", "shape": 1, "strong": False, "colourblind": False, "lazy": False,
                         "liar": False},
        },
    ]

    # parse given flag
    parser = argparse.ArgumentParser()
    parser.add_argument("-tournament", action='store_true', help="Are we going to run multiple times", default=False)
    parser.add_argument("-n", action='store', help="How many times to run", default=10, type=int)

    args = parser.parse_args()

    if args.tournament and 1 < args.n:
        print("Running " + str(args.n) + " times.")
        _DEFAULT_WORLDSETTINGS = DEFAULT_WORLDSETTINGS
        for i in range(args.n):
            world = BW4TWorld(agents, only_completable=True, auto_run=True).run()
            print(Statistics(world.getLogger().getFileName()))
    else:
        print("Started world...")
        world = BW4TWorld(agents).run()
        print("DONE!")
        print(Statistics(world.getLogger().getFileName()))
