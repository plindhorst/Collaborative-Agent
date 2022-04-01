from Group58Agent.PhaseHandler import Phase
from Group58Agent.util import move_to, is_on_location


class RoomVisiter:
    def __init__(self, agent):
        self.agent = agent
        self.found_goal_blocks = []
        self._skipped = False

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
                if not self._skipped and i < len(locations) - 1:
                    # After entering the room check if lazy can skip room
                    if i == 2 and self.agent.skip_room_search:
                        self._skipped = True
                        return move_to(self.agent, locations[0])
                    else:
                        return move_to(self.agent, locations[i + 1])
                else:
                    # We completed the room search
                    self.agent.phase = Phase.CHOOSE_GOAL

                    # Check if previous agent did a good room search
                    if self.agent.get_room(room["room_name"])["last_agent_id"] is not None\
                            and self.agent.agent_id != self.agent.get_room(room["room_name"])["last_agent_id"]:
                        # If we found goal blocks but another agent was here before he skipped the room search
                        if len(self.found_goal_blocks) > 0:
                            self.agent.trust_model.decrease_room_search(
                                self.agent.get_room(room["room_name"])["last_agent_id"])
                        else:
                            self.agent.trust_model.increase_room_search(
                                self.agent.get_room(room["room_name"])["last_agent_id"])

                    self.agent.get_room(room["room_name"])["last_agent_id"] = self.agent.agent_id
                    self.agent.get_room(room["room_name"])["visited_by_me"] = True
                    # Send goal blocks locations to other agents
                    for goal_block in self.found_goal_blocks:
                        # Add goal block to our agent's blocks
                        if goal_block not in self.agent.found_goal_blocks:
                            self.agent.found_goal_blocks.append(goal_block)
                        self.agent.msg_handler.send_found_goal_block(goal_block)

                    # Reset temp variables
                    self.found_goal_blocks = []
                    self._skipped = False
                    return move_to(self.agent, locations[0])

    # Update the goal blocks seen in agent range
    def _update_room(self):
        blocks = self.agent.state.get_with_property({'is_collectable': True})
        if blocks is not None:
            # Go over each block in the field of view
            for block in blocks:
                block = {"colour": block["visualization"]["colour"], "shape": block["visualization"]["shape"],
                         "location": block["location"], "size": block["visualization"]["size"],
                         "found_by": self.agent.agent_id}
                # Check if the block is a goal block
                for drop_off in self.agent.drop_offs:
                    if (self.agent.settings["colourblind"] or block["colour"] == drop_off["colour"]) and block[
                        "shape"] == drop_off["shape"]:
                        if self.agent.settings["colourblind"]:
                            block["colour"] = ""

                        # Check if block was already found by someone else
                        _exists = False
                        for other_block in self.found_goal_blocks:
                            if block["colour"] == other_block["colour"] and block["shape"] == other_block["shape"] and \
                                    block["location"] == other_block["location"]:
                                _exists = True
                                break
                        if not _exists:
                            self.found_goal_blocks.append(block)
                        break
