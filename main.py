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
        {"name": "agent1", "botclass": Group58Agent, "settings": {"color": "#000000", "shape": 1}},
        {"name": "agent2", "botclass": Group58Agent, "settings": {"color": "#000000", "shape": 2}},
        {"name": "agent3", "botclass": Group58Agent, "settings": {"color": "#000000", "shape": 0}},
        {"name": "agent4", "botclass": Group58Agent, "settings": {"color": "#FF0000", "shape": 2}},
    ]

    print("Started world...")
    world = BW4TWorld(agents).run()
    print("DONE!")
    print(Statistics(world.getLogger().getFileName()))
