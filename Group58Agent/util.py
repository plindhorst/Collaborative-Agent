# Get action for navigation
import enum

from matrx.agents import StateTracker
from matrx.agents.agent_utils.navigator import AStarPlanner


# uses the path planer to compute the distance agent->room door
def path(agent, state, location):
    state_tracker = StateTracker(agent.agent_id)
    occupation_map, _ = state_tracker.get_traversability_map(inverted=True, state=state)
    navigator_temp = AStarPlanner(state[agent.agent_id]["action_set"])
    return navigator_temp.plan(state[agent.agent_id]["location"], (location[0], location[1] + 1),
                               occupation_map)


def move_to(agent, location, state):
    agent.navigator.reset_full()
    agent.navigator.add_waypoints([location])
    agent.state_tracker.update(state)
    return agent.navigator.get_move_action(agent.state_tracker), {}


class Phase(enum.Enum):
    DONE = 0
    PLAN_PATH_TO_CLOSED_DOOR = (1,)
    FOLLOW_PATH_TO_CLOSED_DOOR = (2,)
    OPEN_DOOR = 3
    SEARCH_ROOM = 4
    FIND_GOAL = 5
    GRAB_GOAL = 6
    DROP_GOAL = 7
