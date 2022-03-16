from matrx.actions import GrabObject

from Group58Agent.util import get_navigation_action
from Group58Agent.util import Phase


# Visit room and record all blocks seen in visibleblocks.
def visit_room2(agent, door, state):
    _update_visited(agent, door, state)

    door_location = door["location"]
    self_location = state[agent.agent_id]["location"]

    agent.phase = Phase.SEARCH_ROOM
    # Top to bottom approach
    # Final step

    if self_location == (door_location[0] - 1, door_location[1] - 2):
        agent.phase = Phase.PLAN_PATH_TO_CLOSED_DOOR
        next_location = door_location[0] - 1, door_location[1] - 1
        return get_navigation_action(agent, next_location, state)
    # Second step
    elif self_location == (door_location[0], door_location[1] - 2):
        next_location = door_location[0] - 1, door_location[1] - 2
        return get_navigation_action(agent, next_location, state)
    # First step
    else:
        next_location = door_location[0], door_location[1] - 2
        return get_navigation_action(agent, next_location, state)


def visit_room(agent, door, state):
    if agent.visited.get(door["room_name"]) is None:
        agent.visited[door["room_name"]] = []
    door_location = door["location"]
    self_location = state[agent.agent_id]["location"]

    agent.phase = Phase.SEARCH_ROOM
    if self_location == (door_location[0] - 1, door_location[1] - 2):
        _update_visited(agent, door, state)
        agent.phase = Phase.PLAN_PATH_TO_CLOSED_DOOR
        return None, {}
    elif self_location == (door_location[0], door_location[1] - 2):
        _update_visited(agent, door, state)
        next_location = door_location[0] - 1, door_location[1] - 2
        return get_navigation_action(agent, next_location, state)
    else:
        next_location = door_location[0], door_location[1] - 2
        return get_navigation_action(agent, next_location, state)


# Update the blocks seen in room
def _update_visited(agent, door, state):
    visibleblocks = state.get_with_property({'is_collectable': True})
    if visibleblocks is not None:

        for block in visibleblocks:
            block = {"colour": block["visualization"]["colour"], "shape": block["visualization"]["shape"],
                     "location": block["location"]}
            if block not in agent.visited[door["room_name"]]:
                agent.visited[door["room_name"]].append(block)


# Check if blocks in surrounding are goal block.
def _check_goal_block(agent, state):
    blocks = [
        block
        for block in state.values()
        if "class_inheritance" in block
           and "CollectableBlock" in block["class_inheritance"]
    ]
    if len(blocks) > 0:
        if (blocks[0]["visualization"]["colour"] == agent.goal[0]["visualization"]["colour"]
                and blocks[0]["visualization"]["shape"] == agent.goal[0]["visualization"]["shape"]):
            agent.phase = Phase.FOUND_GOAL_BLOCK
            agent.carrying = blocks[0]

            return GrabObject.__name__, {"object_id": blocks[0]["obj_id"]}

    return None, {}


class RoomVisiter:
    pass
