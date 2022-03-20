from matrx.messages import Message
import json
from Group58Agent.PhaseHandler import Phase


class MessageHandler:
    def __init__(self, agent):
        self.agent = agent

    def _send(self, msg):
        msg = Message(content=msg, from_id=self.agent.agent_id)
        if msg.content not in self.agent.received_messages:
            self.agent.send_message(msg)

    # What to update when receiving a move to message
    def _process_move_to(self, msg):
        # Update sender agent phase
        for other_agent in self.agent.other_agents:
            if other_agent["agent_id"] == msg.from_id:
                other_agent["phase"] = Phase.GO_TO_ROOM
                break

        # Mark room as visited
        room_name = msg.content.replace("Moving to ", "")
        room = self.agent.get_room(room_name)
        room["visited"] = True

    # What to update when receiving a open door message
    def _process_opening_door(self, msg):
        # Update sender agent phase
        for other_agent in self.agent.other_agents:
            if other_agent["agent_id"] == msg.from_id:
                other_agent["phase"] = Phase.OPEN_DOOR
                break

    # What to update when receiving a open door message
    def _process_searching(self, msg):
        # Update sender agent phase
        for other_agent in self.agent.other_agents:
            if other_agent["agent_id"] == msg.from_id:
                other_agent["phase"] = Phase.SEARCH_ROOM
                break

    # What to update when receiving a found block message
    def _process_found_goal_block(self, msg):
        # Update sender agent phase
        for other_agent in self.agent.other_agents:
            if other_agent["agent_id"] == msg.from_id:
                other_agent["phase"] = Phase.FIND_GOAL
                break

        # Parse message content
        goal_block = json.loads(msg.content[msg.content.index("{"):msg.content.index("}") + 1])
        location = json.loads("[" + msg.content[msg.content.index("(") + 1:msg.content.index(")")] + "]")
        goal_block["location"] = (location[0], location[1])

        # Add goal block to our agent's goal blocks
        if goal_block not in self.agent.found_goal_blocks:
            self.agent.found_goal_blocks.append(goal_block)

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
            'Found goal block {"size": ' + str(goal_block["size"]) + ', "shape": ' + str(
                goal_block["shape"]) + ', "colour": "' +
            goal_block["colour"] + '"} at location ' + str(goal_block["location"]))
