import numpy as np

from Group58Agent.util import path


class GoalDropper:
    def __init__(self, agent):
        self.agent = agent

    # returns the closest goal block that can be delivered and its distance to agent
    def find_goal_block(self, agent_id):
        current_drop_off = self.agent.get_next_drop_off()
        if current_drop_off is None or len(self.agent.found_goal_blocks) == 0:
            return None, None

        # Order possible goal blocks by distance to agent
        distances = []
        current_goal_blocks_found = []
        for found_goal_block in self.agent.found_goal_blocks:
            if (
                found_goal_block["colour"] == current_drop_off["colour"]
                and found_goal_block["shape"] == current_drop_off["shape"]
            ):
                start_location = self.agent.state[agent_id]["location"]
                target_location = found_goal_block["location"]
                distances.append(
                    len(
                        path(
                            agent_id, self.agent.state, start_location, target_location
                        )
                    )
                )
                current_goal_blocks_found.append(found_goal_block)

        if len(distances) > 0:
            # return closest goal block
            idx = np.argsort(distances)
            return (
                np.array(current_goal_blocks_found)[idx][0],
                np.array(distances)[idx][0],
            )
        else:  # no goal blocks found
            return None, None

    # Returns true if another agent should grab the block
    def grab_conflict(self, goal_block, distance):
        # Go over all other agents, if we chose the same block take the one closest to it.
        # In case of draw choose smallest agent_idx
        for other_agent in self.agent.other_agents:
            if (
                other_agent["phase"] == "CHOOSE_GOAL"
                and other_agent["location"] is not None
            ):
                other_goal_block, other_distance = self.find_goal_block(
                    other_agent["agent_id"]
                )
                if goal_block["location"] == other_goal_block["location"]:
                    if distance == other_distance:
                        # choose agent with lowest idx
                        if self.agent.agent_idx > other_agent["agent_idx"]:
                            return True
                    else:
                        # choose smallest distance
                        if distance > other_distance:
                            return True
        return False

    # Returns the obj id of a block at a certain location
    def get_block_obj_id(self, location):
        blocks = self.agent.state.get_with_property({"is_collectable": True})
        if blocks is not None:
            # Go over each block in the field of view
            for block in blocks:
                if location == block["location"]:
                    return block["obj_id"]
        return None
