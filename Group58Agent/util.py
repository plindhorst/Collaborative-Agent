# Get action for navigation
import enum


def get_navigation_action(agent, location, state):
    agent.navigator.reset_full()
    agent.navigator.add_waypoints([location])
    agent.state_tracker.update(state)
    return agent.navigator.get_move_action(agent.state_tracker), {}


class Phase(enum.Enum):
    PLAN_PATH_TO_CLOSED_DOOR = (1,)
    FOLLOW_PATH_TO_CLOSED_DOOR = (2,)
    OPEN_DOOR = 3
    SEARCH_ROOM = 4
    FOUND_GOAL_BLOCK = 5
    PICK_UP_GOAL_BLOCK = 6
    DROP_GOAL_BLOCK = 7