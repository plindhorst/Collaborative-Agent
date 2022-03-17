from Group58Agent.util import Phase
from Group58Agent.util import move_to


def visit_room(agent, door, state):
    if agent.visited.get(door["room_name"]) is None:
        agent.visited[door["room_name"]] = []
    door_location = door["location"]
    self_location = state[agent.agent_id]["location"]

    agent.phase = Phase.SEARCH_ROOM
    if self_location == (door_location[0] - 1, door_location[1] - 1):
        _update_visited(agent, door, state)
        agent.phase = Phase.FIND_GOAL
        return move_to(agent, door_location, state)
    elif self_location == (door_location[0] - 1, door_location[1] - 2):
        _update_visited(agent, door, state)
        next_location = door_location[0] - 1, door_location[1] - 1
        return move_to(agent, next_location, state)
    elif self_location == (door_location[0], door_location[1] - 2):
        _update_visited(agent, door, state)
        next_location = door_location[0] - 1, door_location[1] - 2
        return move_to(agent, next_location, state)
    else:
        next_location = door_location[0], door_location[1] - 2
        return move_to(agent, next_location, state)


# Update the blocks seen in room
def _update_visited(agent, door, state):
    visibleblocks = state.get_with_property({'is_collectable': True})
    if visibleblocks is not None:

        for block in visibleblocks:
            block = {"colour": block["visualization"]["colour"], "shape": block["visualization"]["shape"],
                     "location": block["location"], "obj_id": block["obj_id"]}
            if block not in agent.visited[door["room_name"]]:
                agent.visited[door["room_name"]].append(block)


class RoomVisiter:
    pass
