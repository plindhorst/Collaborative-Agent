import numpy as np

# returns doors ordered by distance to the agent
from Group58Agent.util import path


def _get_doors_by_distance(agent, state):
    rooms = np.array(state.get_with_property({"class_inheritance": "Door", "room_name": None}, combined=True))

    # order rooms by distance
    for i, room in enumerate(rooms):
        room["distance"] = len(path(agent, state, room["location"]))
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
