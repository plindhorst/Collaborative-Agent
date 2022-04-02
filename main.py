import argparse
import csv
import os
import time

import matplotlib.pyplot as plt
import numpy as np

from Group58Agent.Group58Agent import ColorblindAgent, LazyAgent, LiarAgent, StrongAgent
from bw4t.BW4TWorld import BW4TWorld, DEFAULT_WORLDSETTINGS
from bw4t.statistics import Statistics

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
            for agent_trust_ in trust_:
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
            "name": "lazy",
            "botclass": LazyAgent,
            "settings": {"color": "#FFFF00", "shape": 1},
        },
        {
            "name": "strong",
            "botclass": StrongAgent,
            "settings": {"color": "#0000FF", "shape": 2},
        },
        {
            "name": "colourblind",
            "botclass": ColorblindAgent,
            "settings": {"color": "#000000", "shape": 1},
        },
        {
            "name": "liar",
            "botclass": LiarAgent,
            "settings": {"color": "#FF0000", "shape": 1},
        },
    ]

    # parse given flag
    parser = argparse.ArgumentParser()
    parser.add_argument("-tournament", action='store_true', help="Are we going to run multiple times",
                        default=False)
    parser.add_argument("-visualizer", action='store_true', help="Show web visualizer", default=False)
    parser.add_argument("-n", action='store', help="How many times to run", default=10, type=int)

    args = parser.parse_args()

    if args.tournament and 1 < args.n:

        if not os.path.exists("./results/"):
            os.makedirs("./results/")

        start = time.time()
        if args.visualizer:
            print("Running " + str(args.n) + " times.")
        else:
            print("Running " + str(args.n) + " times. (no visualizer)")
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
        if not args.visualizer:
            world_settings["deadline"] = 1000
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

        ticks = []

        drops = {}
        for agent in agents:
            drops[agent["name"]] = 0
        completion = 0
        for round_ in results:
            if round_.isSucces() == "True":
                completion += 1
                ticks.append(int(round_.getLastTick()))
                agent_drops = round_.getDrops()
                for agent_name in agent_drops:
                    drops[agent_name] += agent_drops[agent_name]

        sum_drops = 0
        for agent_name in drops:
            sum_drops += drops[agent_name]

        drops_string = "Drops Percentages:\n"
        for agent in agents:
            drops_string += "* " + agent["name"] + ": " + str(round(drops[agent["name"]] * 100 / sum_drops, 2)) + "%\n"
        print(drops_string)

        print("Success rate: " + str(round(completion * 100 / len(results), 2)) + "%")

        # Plot statistics graph
        fig = plt.gcf()
        plt.rc("font", **{"size": 22})
        x = np.arange(len(ticks))
        coef = np.polyfit(x, ticks, 1)
        poly1d_fn = np.poly1d(coef)
        plt.plot(x, poly1d_fn(x), "--k", label="regression line")
        plt.plot(x, ticks, label="ticks", linewidth=3, marker="o")
        plt.xticks([np.min(x), np.max(x)])
        plt.xlabel("Rounds")
        plt.ylabel("Ticks")
        plt.title("Ticks per Round")
        plt.legend()
        fig.set_size_inches(20, 10)

        plt.savefig("./results/statistics.png", bbox_inches="tight")
        plt.close(fig)

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

        max_ /= (len(agents) - 1)
        min_ /= (len(agents) - 1)

        fig = plt.gcf()
        plt.scatter(0, min_, s=0)
        plt.scatter(0, max_, s=0)
        x = np.arange(args.n + 1)

        for i, agent_trust in enumerate(trust):
            trust_sum = []

            for j, y in enumerate(agent_trust[agents[i]["name"]][0]["drop_off"]):
                trust_sum.append(np.mean([y, agent_trust[agents[i]["name"]][1]["found_goal"][j],
                                          agent_trust[agents[i]["name"]][2]["room_search"][j]]))

            plt.plot(x, [y / (len(agents) - 1) for y in trust_sum], label=agents[i]["name"], linewidth=3,
                     marker="o")

        plt.xticks([np.min(x), np.max(x)])
        plt.xlabel("Rounds")
        plt.ylabel("Trust")
        plt.title("Average Trustworthiness")
        plt.legend()
        fig.set_size_inches(20, 10)
        plt.rc("font", **{"size": 22})
        plt.savefig("./results/all_agents.png", bbox_inches="tight")
        plt.close(fig)

        for i, agent_trust in enumerate(trust):
            fig = plt.gcf()
            plt.scatter(0, min_, s=0)
            plt.scatter(0, max_, s=0)
            x = np.arange(args.n + 1)

            plt.plot(x, [y / (len(agents) - 1) for y in agent_trust[agents[i]["name"]][0]["drop_off"]], c="green",
                     label="drop_off", linewidth=3, marker="o")
            plt.plot(x, [y / (len(agents) - 1) for y in agent_trust[agents[i]["name"]][1]["found_goal"]], c="blue",
                     label="found_goal", linewidth=3, marker="o")
            plt.plot(x, [y / (len(agents) - 1) for y in agent_trust[agents[i]["name"]][2]["room_search"]], c="red",
                     label="room_search", linewidth=3, marker="o")

            plt.xticks([np.min(x), np.max(x)])
            plt.yticks([min_, 0, max_])
            plt.xlabel("Rounds")
            plt.ylabel("Trust")
            plt.title("Trustworthiness of '" + agents[i]["name"] + "'")
            plt.legend()
            fig.set_size_inches(20, 10)
            plt.rc("font", **{"size": 22})
            plt.savefig("./results/" + agents[i]["name"] + ".png", bbox_inches="tight")
            plt.close(fig)
    else:
        print("Started world...")
        world = BW4TWorld(agents).run()
        print("DONE!")
        print(Statistics(world.getLogger().getFileName()))
