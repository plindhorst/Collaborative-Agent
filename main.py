import argparse
import csv
import os
import time

from Group58Agent.Group58Agent import Group58Agent
from bw4t.BW4TWorld import BW4TWorld, DEFAULT_WORLDSETTINGS
from bw4t.statistics import Statistics

import matplotlib.pyplot as plt
import numpy as np

"""
This runs a single session. You have to log in on localhost:3000 and
press the start button in god mode to start the session.
"""


def get_trust_from_file(agent_id, agents):
    agents_ = []
    file = "./trust/" + agent_id + ".csv"

    if not os.path.exists(file):
        for agent_ in agents:
            if agent_["name"] != agent_id:
                agents_.append(
                    {'agent_id': agent_["name"], 'drop_off': '5.0', 'room_search': '5.0', 'found_goal': '5.0'})
        return agents_

    with open(file, 'r') as file:
        csv_reader = csv.reader(file)
        headers = next(csv_reader)
        for row in csv_reader:
            agent_ = {}
            for i_, column in enumerate(row):
                agent_[headers[i_]] = column

            agents_.append(agent_)
    return agents_


def append_trust_round(agents_, trust_, trust_all_):
    round_idx = len(trust_[0][agents_[0]["name"]][0]["drop_off"])
    for j, agent_ in enumerate(agents_):
        trust_from_file = get_trust_from_file(agent_["name"], agents_)

        for trust_other in trust_from_file:
            for i, agent_trust_ in enumerate(trust_):
                for agent_name in agent_trust_:
                    if agent_name == trust_other["agent_id"]:
                        for action_ in agent_trust_[agent_name]:
                            for action_name in action_:
                                if round_idx == len(action_[action_name]):
                                    action_[action_name].append(0)
                                action_[action_name][round_idx] += float(trust_other[action_name])
        for trust_other in trust_from_file:
            for i, agent_trust_ in enumerate(trust_all_):
                for agent_name in agent_trust_:
                    if agent_name == trust_other["agent_id"]:
                        if len(agent_trust_[agent_name]) == round_idx:
                            agent_trust_[agent_name].append(0)

                        for action_ in trust_[i][agent_name]:
                            for action_name in action_:
                                agent_trust_[agent_name][round_idx] += float(trust_other[action_name])


if __name__ == "__main__":
    agents = [
        {
            "name": "Lazy",
            "botclass": Group58Agent,
            "settings": {"color": "#FFFF00", "shape": 1, "strong": False, "colourblind": False, "lazy": True,
                         "liar": False},
        },
        {
            "name": "Strong",
            "botclass": Group58Agent,
            "settings": {"color": "#0000FF", "shape": 2, "strong": True, "colourblind": False, "lazy": False,
                         "liar": False},
        },
        {
            "name": "ColourBlind",
            "botclass": Group58Agent,
            "settings": {"color": "#000000", "shape": 1, "strong": False, "colourblind": True, "lazy": False,
                         "liar": False},
        },
        {
            "name": "Liar",
            "botclass": Group58Agent,
            "settings": {"color": "#FF0000", "shape": 1, "strong": False, "colourblind": False, "lazy": False,
                         "liar": True},
        },
    ]

    # parse given flag
    parser = argparse.ArgumentParser()
    parser.add_argument("-tournament", action='store_true', help="Are we going to run multiple times",
                        default=False)
    parser.add_argument("-visualizer", action='store_true', help="Hide web visualizer", default=False)
    parser.add_argument("-n", action='store', help="How many times to run", default=10, type=int)

    args = parser.parse_args()

    if args.tournament and 1 < args.n:

        if not os.path.exists("./results/"):
            os.makedirs("./results/")

        start = time.time()
        print("Running " + str(args.n) + " times.")
        results = []

        # Initialize trust array
        trust = []
        trust_all = []
        for agent in agents:
            trust.append({agent["name"]: [{"drop_off": []}, {"found_goal": []}, {"room_search": []}]})
            trust_all.append({agent["name"]: []})

        append_trust_round(agents, trust, trust_all)

        world_settings = DEFAULT_WORLDSETTINGS
        world_settings["tick_duration"] = 0.025
        world_settings["matrx_paused"] = False
        if args.visualizer:
            world_settings["tick_duration"] = 0
            world_settings["run_matrx_api"] = False
            world_settings["run_matrx_visualizer"] = False
        world_settings["only_completable"] = True

        for i in range(args.n):
            world = BW4TWorld(agents, world_settings).run()
            statistics = Statistics(world.getLogger().getFileName())
            results.append(statistics)
            print("\n### Run " + str(i + 1) + " statistics: ###\n")
            print(statistics)

            append_trust_round(agents, trust, trust_all)

        minutes, seconds = divmod(divmod(time.time() - start, 3600)[1], 60)
        print("\n### DONE!", "({:0>2}:{:05.2f}".format(int(minutes), seconds) + ") ###\n")

        # Get min and max values
        max_ = -np.inf
        min_ = np.inf
        for i, agent_trust in enumerate(trust):
            new_max_ = np.maximum(np.max(agent_trust[agents[i]["name"]][0]["drop_off"]),
                                  np.maximum(np.max(agent_trust[agents[i]["name"]][1]["found_goal"]),
                                             np.max(agent_trust[agents[i]["name"]][2]["room_search"])))
            if max_ < new_max_:
                max_ = new_max_

            new_min_ = np.minimum(np.min(agent_trust[agents[i]["name"]][0]["drop_off"]),
                                  np.minimum(np.min(agent_trust[agents[i]["name"]][1]["found_goal"]),
                                             np.min(agent_trust[agents[i]["name"]][2]["room_search"])))

            if min_ > new_min_:
                min_ = new_min_

        fig = plt.gcf()
        plt.scatter(0, min_ / (len(agents) - 1), s=0)
        plt.scatter(0, max_ / (len(agents) - 1), s=0)
        x = np.arange(args.n + 1)

        for i, agent in enumerate(agents):
            plt.plot(x, [y / (len(agents) - 1) for y in trust_all[i][agent["name"]]], label=agent["name"])

        plt.xticks(x)
        plt.xlabel("Rounds")
        plt.ylabel("Trust")
        plt.title("Average Trustworthiness")
        plt.legend()
        fig.set_size_inches(20, 10)
        plt.savefig("./results/all_agents.png", bbox_inches="tight")
        plt.close(fig)

        for i, agent_trust in enumerate(trust):
            fig = plt.gcf()
            plt.scatter(0, min_ / (len(agents) - 1), s=0)
            plt.scatter(0, max_ / (len(agents) - 1), s=0)
            x = np.arange(args.n + 1)

            plt.plot(x, [y / (len(agents) - 1) for y in agent_trust[agents[i]["name"]][0]["drop_off"]], c="green",
                     label="drop_off")
            plt.plot(x, [y / (len(agents) - 1) for y in agent_trust[agents[i]["name"]][1]["found_goal"]], c="blue",
                     label="found_goal")
            plt.plot(x, [y / (len(agents) - 1) for y in agent_trust[agents[i]["name"]][2]["room_search"]], c="red",
                     label="room_search")

            plt.xticks(x)
            plt.xlabel("Rounds")
            plt.ylabel("Trust")
            plt.title("Trustworthiness of '" + agents[i]["name"] + "'")
            plt.legend()
            fig.set_size_inches(20, 10)
            plt.savefig("./results/" + agents[i]["name"] + ".png", bbox_inches="tight")
            plt.close(fig)

    else:
        print("Started world...")
        world = BW4TWorld(agents).run()
        print("DONE!")
        print(Statistics(world.getLogger().getFileName()))
