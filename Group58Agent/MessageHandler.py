import json

from matrx.messages import Message
from Group58Agent.PhaseHandler import Phase


class MessageHandler:
    def __init__(self, agent):
        self.agent = agent

    def _send(self, msg):
        msg = Message(content=msg, from_id=self.agent.agent_id)
        if msg.content not in self.agent.received_messages:
            self.agent.send_message(msg)

    # Update the phase of the other agent in our agent array
    def _update_other_agent_phase(self, agent_id, phase):
        # Update sender agent phase
        for other_agent in self.agent.other_agents:
            if other_agent["agent_id"] == agent_id:
                other_agent["phase"] = phase
                break

    # What to update when receiving a move to message
    def _process_move_to(self, msg):
        # Update sender agent phase
        self._update_other_agent_phase(msg.from_id, Phase.GO_TO_ROOM)

        # Mark room as visited
        room_name = msg.content.replace("Moving to ", "")
        room = self.agent.get_room(room_name)
        room["visited"] = True
        room["last_visited_id"] = msg.from_id

    # What to update when receiving a open door message
    def _process_opening_door(self, msg):
        # Update sender agent phase
        self._update_other_agent_phase(msg.from_id, Phase.OPEN_DOOR)

    # What to update when receiving a search room message
    def _process_searching(self, msg):
        # Update sender agent phase
        self._update_other_agent_phase(msg.from_id, Phase.SEARCH_ROOM)

    # What to update when receiving a found block message
    def _process_found_goal_block(self, msg):
        # Update sender agent phase
        self._update_other_agent_phase(msg.from_id, Phase.CHOOSE_GOAL)

        # Parse message content
        goal_block = json.loads(
            msg.content[msg.content.index("{"): msg.content.index("}") + 1]
        )
        location = json.loads(
            "[" + msg.content[msg.content.index("(") + 1: msg.content.index(")")] + "]"
        )
        goal_block["location"] = (location[0], location[1])
        goal_block["found_by"] = msg.from_id
        # Add goal block to our agent's goal blocks
        if  msg.from_id != self.agent.agent_id and \
            self.agent.trust_model.can_trust_found_goal(msg.from_id) and \
            goal_block not in self.agent.found_goal_blocks:
            self.agent.found_goal_blocks.append(goal_block)

    # What to update when receiving a pickup block message
    def _process_pickup_goal_block(self, msg):
        # Update sender agent phase
        self._update_other_agent_phase(msg.from_id, Phase.GRAB_GOAL)

        # Parse message content
        goal_block = json.loads(
            msg.content[msg.content.index("{"): msg.content.index("}") + 1]
        )
        location = json.loads(
            "[" + msg.content[msg.content.index("(") + 1: msg.content.index(")")] + "]"
        )
        goal_block["location"] = (location[0], location[1])

        # Remove grabbed block from found goal blocks
        found_goal_blocks = []
        for old_block in self.agent.found_goal_blocks:
            if old_block["location"] != goal_block["location"]:
                found_goal_blocks.append(old_block)
        self.agent.found_goal_blocks = found_goal_blocks

        # Update drop off as grabbed
        next_drop_off = self.agent.get_next_drop_off()
        if  msg.from_id != self.agent.agent_id and \
            self.agent.trust_model.can_trust_drop_off(msg.from_id) and \
            next_drop_off is not None:
            next_drop_off["grabbed"] = True

    # What to update when receiving a drop block message
    def _process_drop_goal_block(self, msg):
        # Update sender agent phase
        self._update_other_agent_phase(msg.from_id, Phase.CHOOSE_GOAL)

        # Parse message content
        goal_block = json.loads(
            msg.content[msg.content.index("{"): msg.content.index("}") + 1]
        )
        location = json.loads(
            "[" + msg.content[msg.content.index("(") + 1: msg.content.index(")")] + "]"
        )
        drop_off_location = (location[0], location[1])

        for drop_off in self.agent.drop_offs:
            if drop_off["location"] == drop_off_location:
                drop_off["delivered"] = True
                self.agent.trust_model.increase_drop_off(msg.from_id)
                return

        # If we are here then the dropped block is not delivered
        # Add dropped goal blocks to found goal blocks
        goal_block["location"] = drop_off_location
        goal_block["found_by"] = msg.from_id
        # Check if the block is a goal block
        for drop_off in self.agent.drop_offs:
            if goal_block["colour"] == drop_off["colour"] and goal_block["shape"] == drop_off["shape"]:
                self.agent.found_goal_blocks.append(goal_block)
                self.agent.trust_model.decrease_drop_off(msg.from_id)
        # Undo all undelivered grabbed drop offs since we do not know for which drop off the block was mis-dropped
        for drop_off in self.agent.drop_offs:
            if not drop_off["delivered"] and drop_off["grabbed"]:
                drop_off["grabbed"] = False

    #What to update when receiving a decrease trust message
    def _process_decrease_trust_value(self, msg):
        trust = json.loads(
            msg.content[msg.content.index("{"): msg.content.index("}") + 1]
        )
        if self.agent.trust_model._can_trust_overall(msg.from_id):
            self.agent.trust_model._update_trust(trust["agent"], trust["action"], 1.0)

    # Go over received messages and perform updates
    def read_messages(self):
        for msg in self.agent.received_messages:
            if msg.from_id != self.agent.agent_id:
                if "Moving to" in msg.content:
                    self._process_move_to(msg)
                elif "Opening door of" in msg.content:
                    self._process_opening_door(msg)
                elif "Searching through" in msg.content:
                    self._process_searching(msg)
                elif "Found goal block" in msg.content:
                    self._process_found_goal_block(msg)
                elif "Picking up goal block" in msg.content:
                    self._process_pickup_goal_block(msg)
                elif "Dropped goal block" in msg.content:
                    self._process_drop_goal_block(msg)
                elif "Decrease trust" in msg.content:
                    self._process_decrease_trust_value(msg)
        # Delete messages
        self.agent.received_messages = []

    def send_moving_to_room(self, room_name):
        self._send("Moving to " + room_name)

    def send_opening_door(self, room_name):
        self._send("Opening door of " + room_name)

    def send_searching_room(self, room_name):
        self._send("Searching through " + room_name)

    def send_found_goal_block(self, goal_block):
        self._send(
            'Found goal block {"size": '
            + str(goal_block["size"])
            + ', "shape": '
            + str(goal_block["shape"])
            + ', "colour": "'
            + goal_block["colour"]
            + '"} at location '
            + str(goal_block["location"])
        )

    def send_pickup_goal_block(self, goal_block):
        self._send(
            'Picking up goal block {"size": '
            + str(goal_block["size"])
            + ', "shape": '
            + str(goal_block["shape"])
            + ', "colour": "'
            + goal_block["colour"]
            + '"} at location '
            + str(goal_block["location"])
        )

    def send_drop_goal_block(self, goal_block, drop_off_location):
        self._send(
            'Dropped goal block {"size": '
            + str(goal_block["size"])
            + ', "shape": '
            + str(goal_block["shape"])
            + ', "colour": "'
            + goal_block["colour"]
            + '"} at location '
            + str(drop_off_location)
        )

    def send_decrease_trust_value(self, agent, action):
        self._send(
            'Decrease trust {"agent": '
            + str(agent)
            + ', "action": '
            + str(action)
            + '}'
        )
