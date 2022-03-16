from Group58Agent.util import path


def find_goal_blocks(agent, state):
    if len(agent.goal) == 0:
        return None
    available_goal_blocks = []
    for room in agent.visited:
        for block in agent.visited[room]:
            if block["colour"] == agent.goal[0]["colour"] and block["shape"] == agent.goal[0]["shape"]:
                coords = path(agent, state, block["location"])
                if coords != state[agent.agent_id][
                    "location"]:  # if path is same as agent coords then no path was found
                    block["distance"] = len(coords)
                    available_goal_blocks.append(block)

    if len(available_goal_blocks) > 0:
        # return closest goal blocks
        return sorted(available_goal_blocks, key=lambda x: x["distance"], reverse=False)
    else:  # no goal blocks found
        return None


class GoalDropper:
    pass
