from Group58Agent.Group58Agent import Group58Agent
from agents1.BW4THuman import Human
from bw4t.BW4TWorld import BW4TWorld
from bw4t.statistics import Statistics

"""
This runs a single session. You have to log in on localhost:3000 and
press the start button in god mode to start the session.
"""

if __name__ == "__main__":
    agents = [
        {
            "name": "Lazy",
            "botclass": Group58Agent,
            "settings": {"color": "#FFFF00", "shape": 1, "strong": False, "colourblind": False, "lazy": True, "liar": False},
        },
        {
            "name": "Strong",
            "botclass": Group58Agent,
            "settings": {"color": "#0000FF", "shape": 2, "strong": True, "colourblind": False, "lazy": False, "liar": False},
        },
        {
            "name": "ColourBlind",
            "botclass": Group58Agent,
            "settings": {"color": "#000000", "shape": 1, "strong": False, "colourblind": True, "lazy": False, "liar": False},
        },
        {
            "name": "Liar",
            "botclass": Group58Agent,
            "settings": {"color": "#FF0000", "shape": 1, "strong": False, "colourblind": False, "lazy": False,
                         "liar": True},
        },
    ]

    print("Started world...")
    world = BW4TWorld(agents).run()
    print("DONE!")
    print(Statistics(world.getLogger().getFileName()))

    world2 = BW4TWorld(agents).run()
