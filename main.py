import argparse
import time

from Group58Agent.Group58Agent import Group58Agent
from bw4t.BW4TWorld import BW4TWorld, DEFAULT_WORLDSETTINGS
from bw4t.statistics import Statistics

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
    parser.add_argument("-visualizer", action='store_true', help="Hide web visualizer", default=False)
    parser.add_argument("-n", action='store', help="How many times to run", default=10, type=int)

    args = parser.parse_args()

    if args.tournament and 1 < args.n:
        start = time.time()
        print("Running " + str(args.n) + " times.")
        results = []

        world_settings = DEFAULT_WORLDSETTINGS
        world_settings["tick_duration"] = 0
        world_settings["matrx_paused"] = False
        if args.visualizer:
            world_settings["run_matrx_api"] = False
            world_settings["run_matrx_visualizer"] = False
        world_settings["only_completable"] = True

        for i in range(args.n):
            world = BW4TWorld(agents, world_settings).run()
            statistics = Statistics(world.getLogger().getFileName())
            results.append(statistics)
            print("\n ### Run " + str(i + 1) + " statistics: ###\n")
            print(statistics)

        minutes, seconds = divmod(divmod(time.time() - start, 3600)[1], 60)
        print("\n### DONE!", "({:0>2}:{:05.2f}".format(int(minutes), seconds) + ") ###")
    else:
        print("Started world...")
        world = BW4TWorld(agents).run()
        print("DONE!")
        print(Statistics(world.getLogger().getFileName()))
