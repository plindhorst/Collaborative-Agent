import numpy as np
from matrx.agents import StateTracker
from matrx.agents.agent_utils.navigator import AStarPlanner


# uses the path planer to compute the distance agent->room door
def _path_distance(agent, state, room):
    state_tracker = StateTracker(agent.agent_id)
    occupation_map, _ = state_tracker.get_traversability_map(inverted=True, state=state)
    navigator_temp = AStarPlanner(state[agent.agent_id]["action_set"])
    return len(
        navigator_temp.plan(state[agent.agent_id]["location"], (room["location"][0], room["location"][1] + 1),
                            occupation_map))


# returns doors ordered by distance to the agent
def _get_doors_by_distance(agent, state):
    rooms = np.array(state.get_with_property({"class_inheritance": "Door", "room_name": None}, combined=True))

    # order rooms by distance
    for i, room in enumerate(rooms):
        room["distance"] = _path_distance(agent, state, room)
    return sorted(rooms, key=lambda x: x["distance"], reverse=False)


# Choose door until all are visited.
# TODO make it so that it chooses the first of a queue that can be updated
# In beginning queue has all doors that are closed, when all doors open
# it should go to doors with goal blocks (so these doors need to be added to queue)
def choose_door(agent, state):
    if len(agent.visited) <= len(agent.doors):
        for door in _get_doors_by_distance(agent, state):
            if len(agent.visited) == 0:
                return door
            if len(agent.visited) > 0 and door["room_name"] not in agent.visited.keys():
                return door

    return None


class RoomChooser:
    pass
