from Group58Agent.util import path


def find_goal_blocks(agent, state):
    if len(agent.goal) == 0:
        return None
    available_goal_blocks = []
    current_goal = agent.get_next_goal()
    if current_goal is None:
        return None
    for room_name in agent.visited:
        for block in agent.visited[room_name]:
            if block["colour"] == current_goal["colour"] and block["shape"] == current_goal["shape"]:
                coords = path(agent, state, block["location"])
                if coords != state[agent.agent_id][
                    "location"]:  # if path is same as agent coords then no path was found
                    block["distance"] = len(coords)
                    block["room_name"] = room_name
                    available_goal_blocks.append(block)

    if len(available_goal_blocks) > 0:
        # return closest goal blocks
        return sorted(available_goal_blocks, key=lambda x: x["distance"], reverse=False)
    else:  # no goal blocks found
        return None


class GoalDropper:
    pass
