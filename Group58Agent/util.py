from matrx.agents import StateTracker
from matrx.agents.agent_utils.navigator import AStarPlanner


# uses the path planer to compute the distance agent->target
def path(agent_id, state, start_location, target_location):
    state_tracker = StateTracker(agent_id)
    occupation_map, _ = state_tracker.get_traversability_map(inverted=True, state=state)
    navigator_temp = AStarPlanner(state[agent_id]["action_set"])
    return navigator_temp.plan(start_location, target_location, occupation_map)


# Get action for navigation
def move_to(agent, location):
    agent.navigator.reset_full()
    agent.navigator.add_waypoints([location])
    agent.state_tracker.update(agent.state)
    return agent.navigator.get_move_action(agent.state_tracker), {}


# Returns True if the agent is on the coordinates of the location
def is_on_location(agent, location):
    return agent.location == location
