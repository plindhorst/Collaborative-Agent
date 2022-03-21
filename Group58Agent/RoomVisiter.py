from Group58Agent.PhaseHandler import Phase
from Group58Agent.util import move_to, is_on_location


class RoomVisiter:
    def __init__(self, agent):
        self.agent = agent
        self.found_goal_blocks = []

    def visit_room(self, room):

        locations = [room["location"],
                     (room["location"][0], room["location"][1] - 1),
                     (room["location"][0], room["location"][1] - 2),
                     (room["location"][0], room["location"][1] - 3),
                     (room["location"][0] - 1, room["location"][1] - 3),
                     (room["location"][0] - 1, room["location"][1] - 2)]

        for i, location in enumerate(locations):
            if is_on_location(self.agent, location):
                self._update_room()
                if i < len(locations) - 1:
                    return move_to(self.agent, locations[i + 1])
                else:
                    # We completed the room search
                    self.agent.phase = Phase.CHOOSE_GOAL
                    # Send goal blocks locations to other agents
                    for goal_block in self.found_goal_blocks:
                        # Add goal block to our agent's blocks
                        if goal_block not in self.agent.found_goal_blocks:
                            self.agent.found_goal_blocks.append(goal_block)
                        self.agent.msg_handler.send_found_goal_block(goal_block)

                    self.found_goal_blocks = []
                    return move_to(self.agent, locations[0])

    # Update the goal blocks seen in agent range
    def _update_room(self):
        blocks = self.agent.state.get_with_property({'is_collectable': True})
        if blocks is not None:
            # Go over each block in the field of view
            for block in blocks:
                block = {"colour": block["visualization"]["colour"], "shape": block["visualization"]["shape"],
                         "location": block["location"], "size": block["visualization"]["size"]}
                # Check if the block is a goal block
                for drop_off in self.agent.drop_offs:
                    if block["colour"] == drop_off["colour"] and block["shape"] == drop_off["shape"]:
                        if block not in self.found_goal_blocks:
                            self.found_goal_blocks.append(block)
                        break
