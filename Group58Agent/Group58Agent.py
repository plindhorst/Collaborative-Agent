import csv
import enum
import json
import os
import random
from typing import Dict
import numpy as np

from matrx.actions.door_actions import OpenDoorAction
from matrx.actions.object_actions import DropObject, GrabObject
from matrx.agents.agent_utils.navigator import Navigator
from matrx.agents.agent_utils.state_tracker import StateTracker
from matrx.agents.agent_utils.navigator import AStarPlanner
from matrx.messages import Message

from bw4t.BW4TBrain import BW4TBrain


class Group58Agent(BW4TBrain):
    def __init__(self, settings: Dict[str, object]):
        super().__init__(settings)
        self.settings = settings
        self.state = None
        self.state_tracker = None
        self.navigator = None
        self.location = (1, 1)
        self.rooms = []
        self.drop_offs = []
        self.found_goal_blocks = []
        self.other_agents = []
        self.agent_idx = None
        self.msg_handler = MessageHandler(self)
        self.phase_handler = PhaseHandler(self)
        self.room_chooser = RoomChooser(self)
        self.room_visiter = RoomVisiter(self)
        self.goal_dropper = GoalDropper(self)
        self.trust_model = None

        # We start by choosing a room
        self.phase = Phase.CHOOSE_ROOM

        self.probability = 0
        # Set skip/lie probability for lazy and liar agents
        if settings["liar"]:
            self.probability = 0.8
        elif settings["lazy"]:
            self.probability = 0.5

        # Temporary variables to communicate between phases
        self._chosen_room = None

        # Temp variables for lazy/liar
        self.skip_room_search = False
        self.skip_drop_off = False
        self.skip_move_to_room = False
        self._path_length_room = None
        self._path_length_move_to_room = None
        self._path_length_drop_off = None
        self.lied_goal_n = 0

        self._chosen_goal_blocks = []

    def initialize(self):
        super().initialize()
        self.state_tracker = StateTracker(agent_id=self.agent_id)
        self.navigator = Navigator(
            agent_id=self.agent_id,
            action_set=self.action_set,
            algorithm=Navigator.A_STAR_ALGORITHM,
        )

    # Initialize doors and goal
    def _initialize_state(self, state):
        # Initialise goal block array
        i = 0
        for block in state.values():
            if (
                    "class_inheritance" in block
                    and "GhostBlock" in block["class_inheritance"]
            ):
                self.drop_offs.append(
                    {
                        "colour": block["visualization"]["colour"],
                        "shape": block["visualization"]["shape"],
                        "size": block["visualization"]["size"],
                        "location": block["location"],
                        "delivered": False,
                        "grabbed": False,
                        "n": i,
                    }
                )
                i += 1

        # Initialise room array
        for room in state.values():
            if "class_inheritance" in room and "Door" in room["class_inheritance"]:
                self.rooms.append(
                    {
                        "room_name": room["room_name"],
                        "location": (room["location"][0], room["location"][1] + 1),
                        "obj_id": room["obj_id"],
                        "visited": False,
                        "last_agent_id": None,
                        "visited_by_me": False,
                    }
                )

        # Initialise other_agents array
        for i, agent in enumerate(state["World"]["team_members"]):
            if agent == self.agent_id:
                self.agent_idx = i
            else:
                self.other_agents.append(
                    {
                        "agent_id": agent,
                        "agent_idx": i,
                        "location": (1, 1),
                        "phase": "CHOOSE_ROOM",
                    }
                )
        self.trust_model = Trust(self)

    # Returns a room from a room name
    def get_room(self, room_name):
        for room in self.rooms:
            if room["room_name"] == room_name:
                return room

    # Returns true with certain probability
    def lazy_skip(self):
        return self.settings["lazy"] and random.random() < self.probability

    # Returns true with certain probability
    def lie(self):
        return self.settings["liar"] and random.random() < self.probability

    # return the next goal to be delivered
    # if all goals were delivered return None
    def get_next_drop_off(self):
        if self.settings["strong"]:
            for drop_off in self.drop_offs:
                if not drop_off["delivered"] and not drop_off["grabbed"]:
                    return drop_off
        else:
            for drop_off in self.drop_offs:
                if not drop_off["delivered"]:
                    return drop_off
        return None

    # Return true if block matches drop off
    def matches_drop_off(self, block, drop_off_n):
        return block is not None and self.drop_offs[drop_off_n]["colour"] == block["colour"] and \
               self.drop_offs[drop_off_n]["shape"] == block["shape"]

    # Update the positions of all agents
    def _update_agent_locations(self):
        self.state_tracker.update(self.state)
        self.location = self.state[self.agent_id]["location"]

        for other_agent in self.other_agents:
            if self.state[other_agent["agent_id"]] is None:
                # The other agent is outside our range
                other_agent["location"] = None
            else:
                other_agent["location"] = self.state[other_agent["agent_id"]][
                    "location"
                ]

    # Choose action to perform
    def decide_on_bw4t_action(self, state):
        if not self.rooms:
            # we initialise our room map and goal array
            self._initialize_state(state)

        self._update_agent_locations()
        self.msg_handler.read_messages()
        self.state = state

        # Choosing a room
        if self.phase_handler.phase_is(Phase.CHOOSE_ROOM):
            # Get closest room and distance to it
            room = self.room_chooser.choose_room(self.agent_id)

            # All rooms have been visited
            if room is None:
                self.phase = Phase.CHOOSE_GOAL
                if self.settings["strong"] and len(self._chosen_goal_blocks) > 0:
                    self.phase = Phase.DROP_GOAL

                return None, {}

            # Check if we are the closest agent (with phase CHOOSE_ROOM) to the room
            if self.room_chooser.room_conflict(room):
                # Continue with phase CHOOSE_ROOM
                return None, {}
            else:
                # We go to the room
                self._chosen_room = room
                self.phase = Phase.GO_TO_ROOM
                # Inform other agents that we are going to the room
                # Mark room as visited
                room = self.get_room(self._chosen_room["room_name"])
                room["visited"] = True
                room["visited_by_me"] = True

                self.msg_handler.send_moving_to_room(room["room_name"])
                # Are we going to lazy/lie skip during moving to room
                self.skip_move_to_room = (self.lazy_skip() or self.lie()) and not self.room_chooser.all_rooms_visited()

                # Store path length to room
                self._path_length_move_to_room = len(
                    path(self.agent_id, self.state, self.location, room["location"]))
                return move_to(self, room["location"])

        # Going to a room
        elif self.phase_handler.phase_is(Phase.GO_TO_ROOM):
            if is_on_location(self, self._chosen_room["location"]):
                self.phase = Phase.OPEN_DOOR
                # Inform other agents that we are opening a door
                self.msg_handler.send_opening_door(self._chosen_room["room_name"])
                return None, {}
            else:
                # We skip moving to the room if we are halfway through the path
                if self.skip_move_to_room and len(path(self.agent_id, self.state, self.location, self._chosen_room[
                    "location"])) / self._path_length_move_to_room < 0.5:
                    self.phase = Phase.CHOOSE_ROOM
                    # Mark visited_by_me as False since we didnt fully visit the room
                    self.get_room(self._chosen_room["room_name"])["visited_by_me"] = False
                    # Delete temp variable
                    self._chosen_room = None
                    self.skip_move_to_room = False
                    return None, {}
                else:
                    return move_to(self, self._chosen_room["location"])

        # Opening a room door
        elif self.phase_handler.phase_is(Phase.OPEN_DOOR):
            self.phase = Phase.SEARCH_ROOM
            # Inform other agents that we are searching a room
            self.msg_handler.send_searching_room(self._chosen_room["room_name"])
            # Are we going to lazy/lie skip during the room search
            self.skip_room_search = (self.lazy_skip() or self.lie()) and not \
                self.room_chooser.all_rooms_visited()
            if self.skip_room_search:
                # Mark visited_by_me as False since we didnt fully visit the room
                self.get_room(self._chosen_room["room_name"])["visited_by_me"] = False

            # Are we going to lie that we found a goal block
            if self.lie():
                lie = True
                if lie and self.lied_goal_n < len(self.drop_offs):
                    # Send current goal block to all other agents at start position
                    self.msg_handler.send_found_goal_block(
                        {"colour": self.drop_offs[self.lied_goal_n]["colour"],
                         "shape": self.drop_offs[self.lied_goal_n]["shape"],
                         "location": (1, 1),
                         "size": self.drop_offs[self.lied_goal_n]["size"]})
                    self.lied_goal_n += 1

                    self.phase = Phase.CHOOSE_ROOM
                # Open door
            return OpenDoorAction.__name__, {"object_id": self._chosen_room["obj_id"]}

        # Searching goal blocks in a room
        elif self.phase_handler.phase_is(Phase.SEARCH_ROOM):
            # Walk through the whole room and observe what blocks are inside
            return self.room_visiter.visit_room(self._chosen_room)

        # Searching for closest goal block
        elif self.phase_handler.phase_is(Phase.CHOOSE_GOAL):
            # Get closest goal
            goal_block, distance = self.goal_dropper.find_goal_block(self.agent_id)

            # Reset temp variable
            self.skip_room_search = False

            # No goal block found
            if self.settings["colourblind"] or goal_block is None:
                self.phase = Phase.CHOOSE_ROOM
                return None, {}

            # Check if we are the closest agent (with phase CHOOSE_GOAL) to the goal block
            if self.goal_dropper.grab_conflict(goal_block, distance):
                # Continue with phase CHOOSE_GOAL
                return None, {}
            else:
                # Mark drop goal as grabbed
                drop_off = self.get_next_drop_off()
                drop_off["grabbed"] = True

                goal_block["drop_off_n"] = drop_off["n"]
                goal_block["drop_off_location"] = self.drop_offs[goal_block["drop_off_n"]]["location"]
                self._chosen_goal_blocks.append(goal_block)

                self.phase = Phase.GRAB_GOAL

                # Delete temp variable
                self._chosen_room = None

                return move_to(self, self._chosen_goal_blocks[-1]["location"])

        # grab the goal block
        elif self.phase_handler.phase_is(Phase.GRAB_GOAL):

            # take latest goal block in array
            goal_block = self._chosen_goal_blocks[-1]

            # Check if someone picked up the goal block
            picked_up = True
            for found_goal_block in self.found_goal_blocks:
                if goal_block["location"] == found_goal_block["location"]:
                    picked_up = False
                    break
            if picked_up:
                del self._chosen_goal_blocks[-1]
                self.phase = Phase.CHOOSE_GOAL
                return None, {}

            if is_on_location(self, goal_block["location"]):

                # Remove grabbed block from found goal blocks
                found_goal_blocks = []
                for old_block in self.found_goal_blocks:
                    if old_block["location"] != goal_block["location"]:
                        found_goal_blocks.append(old_block)
                self.found_goal_blocks = found_goal_blocks

                # Get block with obj_id
                block = self.goal_dropper.get_block_info(goal_block)

                # Check if block is on location
                if block is None:
                    # Lower trust of agent that said goal block was at location.
                    self.trust_model.decrease_found_goal(goal_block["found_by"])
                    self.msg_handler.send_decrease_trust_value(goal_block["found_by"], "found_goal")
                    del self._chosen_goal_blocks[-1]
                    self.phase = Phase.CHOOSE_GOAL
                    return None, {}

                goal_block["obj_id"] = block["obj_id"]
                goal_block["shape"] = block["shape"]
                goal_block["colour"] = block["colour"]

                # Check if block matches
                if self.matches_drop_off(block, goal_block["drop_off_n"]):
                    # Inform other agents that we are grabbing this goal block
                    self.msg_handler.send_pickup_goal_block(goal_block)
                    # If the agent is strong and holds less than 2 blocks
                    # search for another goal block next.
                    if self.settings["strong"] and len(self._chosen_goal_blocks) < 2 \
                            and self.get_next_drop_off() is not None:
                        self.phase = Phase.CHOOSE_GOAL
                    else:
                        self.phase = Phase.DROP_GOAL

                    # Increase trust of agent that said goal block was at location.
                    self.trust_model.increase_found_goal(goal_block["found_by"])

                    if self.settings["lazy"] or self.settings["liar"]:
                        # Are we going to lazy/lie skip during the drop off
                        self.skip_drop_off = self.lazy_skip() or self.lie()
                        # Store path length to drop off location
                        self._path_length_drop_off \
                            = len(path(self.agent_id, self.state, self.location, goal_block["drop_off_location"]))

                    # Remove grabbed block from found goal blocks
                    found_goal_blocks = []
                    for old_block in self.found_goal_blocks:
                        if old_block["location"] != goal_block["location"]:
                            found_goal_blocks.append(old_block)
                    self.found_goal_blocks = found_goal_blocks

                    # Grab block
                    return GrabObject.__name__, {"object_id": goal_block["obj_id"]}

                else:
                    # Lower trust of agent that said goal block was at location.
                    self.trust_model.decrease_found_goal(goal_block["found_by"])
                    self.msg_handler.send_decrease_trust_value(goal_block["found_by"], "found_goal")
                    # Tell others that we found a block
                    goal_block["found_by"] = self.agent_id
                    self.msg_handler.send_found_goal_block(goal_block)
                    self.found_goal_blocks.append(goal_block)

                    del self._chosen_goal_blocks[-1]
                    # Block is not there, find another goal
                    self.phase = Phase.CHOOSE_GOAL
                    # Reset grabbed
                    self.drop_offs[goal_block["drop_off_n"]]["grabbed"] = False
                    return None, {}
            else:
                return move_to(self, goal_block["location"])

        # drop the goal block
        elif self.phase_handler.phase_is(Phase.DROP_GOAL):
            # take earliest goal block in array
            goal_block = self._chosen_goal_blocks[0]

            # Check if someone grabbed/delivered the block before us
            if self.drop_offs[goal_block["drop_off_n"]]["delivered"]:
                # Make sure we do not drop on top of another block
                if self.goal_dropper.get_block_info({"location": self.location}) is None:
                    # Make sure that we are not on a drop off zone
                    for drop_off in self.drop_offs:
                        if drop_off["n"] != goal_block["drop_off_n"] and is_on_location(self, drop_off["location"]):
                            return move_to(self, (2, 2))

                    goal_block["found_by"] = self.agent_id
                    goal_block["location"] = self.location
                    self.found_goal_blocks.append(goal_block)
                    # Inform other agents that we dropped the goal block
                    self.msg_handler.send_drop_goal_block(
                        goal_block,
                        self.location,
                    )

                    self._chosen_goal_blocks.pop(0)
                    self.phase = Phase.CHOOSE_GOAL
                    if self.settings["strong"] and len(self._chosen_goal_blocks) > 0:
                        self.phase = Phase.DROP_GOAL

                    return DropObject.__name__, {"object_id": goal_block["obj_id"]}
                else:
                    return move_to(self, (2, 2))

            if is_on_location(self, goal_block["drop_off_location"]):
                # Check if we are first drop off or previous drop off was delivered
                if goal_block["drop_off_n"] == 0 or self.drop_offs[goal_block["drop_off_n"] - 1]["delivered"]:
                    self._chosen_goal_blocks.pop(0)

                    # Next phase is looking for another goal
                    self.phase = Phase.CHOOSE_GOAL

                    # Mark drop off as delivered
                    self.drop_offs[goal_block["drop_off_n"]]["delivered"] = True

                    # Check if goal was already dropped of
                    if self.goal_dropper.get_block_info({"location": self.location}) is None:
                        # Inform other agents that we dropped the goal block
                        self.msg_handler.send_drop_goal_block(
                            goal_block,
                            goal_block["drop_off_location"],
                        )
                    if self.settings["strong"] and 0 < len(self._chosen_goal_blocks):
                        # If the agent is the strong drop next goal
                        self.phase = Phase.DROP_GOAL
                    return DropObject.__name__, {"object_id": goal_block["obj_id"]}
                else:
                    return None, {}
            else:

                # We skip drop off if we are halfway through the path
                if self.skip_drop_off \
                        and len(path(self.agent_id, self.state, self.location, goal_block["drop_off_location"])) \
                        / self._path_length_drop_off < 0.5:

                    # Make sure that we are not on another drop off location
                    for drop_off in self.drop_offs:
                        if drop_off["n"] != goal_block["drop_off_n"] and is_on_location(self, drop_off["location"]):
                            return move_to(self, goal_block["drop_off_location"])

                    # Make sure that we are not on another block
                    if self.goal_dropper.get_block_info({"location": self.location}) is not None:
                        return move_to(self, goal_block["drop_off_location"])

                    # Add dropped goal blocks to found goal blocks
                    goal_block["location"] = self.location
                    goal_block["found_by"] = self.agent_id
                    self.found_goal_blocks.append(goal_block)
                    self.drop_offs[goal_block["drop_off_n"]]["grabbed"] = False
                    self._chosen_goal_blocks.pop(0)

                    # Next phase is room search
                    self.phase = Phase.CHOOSE_ROOM

                    # Inform other agents that we dropped the goal block
                    self.msg_handler.send_drop_goal_block(goal_block, self.location)

                    # Delete temp vaiables
                    self.skip_drop_off = False
                    return DropObject.__name__, {}
                else:
                    return move_to(self, goal_block["drop_off_location"])

class LazyAgent(Group58Agent):
    def __init__(self, settings: Dict[str, object]):
        settings["strong"] = False
        settings["colourblind"] = False
        settings["lazy"] = True
        settings["liar"] = False
        super().__init__(settings)

class ColorblindAgent(Group58Agent):
    def __init__(self, settings: Dict[str, object]):
        settings["strong"] = False
        settings["colourblind"] = True
        settings["lazy"] = False
        settings["liar"] = False
        super().__init__(settings)

class StrongAgent(Group58Agent):
    def __init__(self, settings: Dict[str, object]):
        settings["strong"] = True
        settings["colourblind"] = False
        settings["lazy"] = False
        settings["liar"] = False
        super().__init__(settings)

class LiarAgent(Group58Agent):
    def __init__(self, settings: Dict[str, object]):
        settings["strong"] = False
        settings["colourblind"] = False
        settings["lazy"] = False
        settings["liar"] = True
        super().__init__(settings)

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
            if (found_goal_block["colour"] == current_drop_off["colour"] or found_goal_block["colour"] == "") \
                    and found_goal_block["shape"] == current_drop_off["shape"]:
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
        # Ignore agents that have low trust values for drop off
        for other_agent in self.agent.other_agents:
            if (
                    other_agent["phase"] == "CHOOSE_GOAL"
                    and self.agent.trust_model.can_trust_drop_off(other_agent["agent_id"])
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

    # Returns the block at a certain location
    def get_block_info(self, find_block):
        blocks = self.agent.state.get_with_property({"is_collectable": True})
        if blocks is not None:
            # Go over each block in the field of view
            for block in blocks:
                if find_block["location"] == block["location"]:
                    block = {"colour": block["visualization"]["colour"], "shape": block["visualization"]["shape"],
                             "location": block["location"], "size": block["visualization"]["size"],
                             "obj_id": block["obj_id"]}
                    return block
        return None

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
        # Mark room as visited
        room_name = msg.content.replace("Moving to ", "")
        room = self.agent.get_room(room_name)
        room["visited"] = True
        room["last_visited_id"] = msg.from_id

        # Update sender agent phase
        self._update_other_agent_phase(msg.from_id, Phase.GO_TO_ROOM)

    # What to update when receiving a open door message
    def _process_opening_door(self, msg):
        # Update sender agent phase
        self._update_other_agent_phase(msg.from_id, Phase.OPEN_DOOR)

    # What to update when receiving a search room message
    def _process_searching(self, msg):
        # Parse message content
        room_name = msg.content[18:]
        self.agent.get_room(room_name)["last_agent_id"] = msg.from_id
        self.agent.get_room(room_name)["visited"] = True

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
        if msg.from_id != self.agent.agent_id and \
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
        if msg.from_id != self.agent.agent_id and \
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

    # What to update when receiving a decrease trust message
    def _process_decrease_trust_value(self, msg):
        trust = json.loads(
            msg.content[msg.content.index("{"): msg.content.index("}") + 1]
        )
        if self.agent.trust_model.can_trust_overall(msg.from_id):
            self.agent.trust_model._update_trust(trust["agent"], trust["action"], -1.0)

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
            'Decrease trust {"agent": "'
            + str(agent)
            + '", "action": "'
            + str(action)
            + '"}'
        )

class PhaseHandler:
    def __init__(self, agent):
        self.agent = agent

    # return true if phase is equal to current phase
    def phase_is(self, phase):
        return self.agent.phase == phase


class Phase(enum.Enum):
    CHOOSE_ROOM = 1
    GO_TO_ROOM = 2
    OPEN_DOOR = 3
    SEARCH_ROOM = 4
    CHOOSE_GOAL = 5
    GRAB_GOAL = 6
    DROP_GOAL = 7
    DONE = 8

class RoomChooser:
    def __init__(self, agent):
        self.agent = agent

    # Returns closest non-visited room and distance
    def choose_room(self, agent_id):
        unvisited = self._get_unvisited_rooms()
        order_by_trustworthiness = False

        if len(unvisited) == 0:
            # Look inside rooms not visited by us
            order_by_trustworthiness = True
            unvisited = self._get_unvisited_by_me()
            if len(unvisited) == 0:
                # All rooms were visited by us
                return None
        # order rooms by distance
        for room in unvisited:
            start_location = self.agent.state[agent_id]["location"]
            target_location = room["location"]
            room["distance"] = len(path(agent_id, self.agent.state, start_location, target_location))

            if room["last_agent_id"] is None or room["last_agent_id"] == self.agent.agent_id:
                room["last_agent_trustworthiness"] = np.inf
            else:
                room["last_agent_trustworthiness"] = self.agent.trust_model.get_value_room_search(room["last_agent_id"])

        if order_by_trustworthiness:
            # Order by rooms we think are not fully searched -> lowest trustworhiness first
            return sorted(unvisited, key=lambda x: (x["distance"], x["last_agent_trustworthiness"]))[0]
        else:
            return sorted(unvisited, key=lambda x: (x["distance"]))[0]

    # Returns true if another agent chose this room and is closer to it
    def room_conflict(self, room):
        # Go over all other agents, if we chose the same room take the one closest to it.
        # In case of draw choose smallest agent_idx
        for other_agent in self.agent.other_agents:
            if (
                    other_agent["phase"] == "CHOOSE_ROOM"
                    and other_agent["location"] is not None
            ):
                other_room = self.choose_room(other_agent["agent_id"])
                if room["room_name"] == other_room["room_name"]:
                    if room["distance"] == other_room["distance"]:
                        # choose agent with lowest idx
                        if self.agent.agent_idx > other_agent["agent_idx"]:
                            return True
                    else:
                        # choose smallest distance
                        if room["distance"] > other_room["distance"]:
                            return True
        return False

    # Returns all rooms that have not been visited
    def _get_unvisited_rooms(self):
        unvisited = []
        for room in self.agent.rooms:
            if not room["visited"]:
                unvisited.append(room)
        return unvisited

    # Returns all rooms that have not been visited by us
    def _get_unvisited_by_me(self):
        unvisited = []
        for room in self.agent.rooms:
            if not room["visited_by_me"]:
                unvisited.append(room)
        return unvisited

    # Returns True if all rooms have been visited
    def all_rooms_visited(self):
        visited_n = 0
        for room in self.agent.rooms:
            if room["visited"]:
                visited_n += 1
        return visited_n == len(self.agent.rooms)

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

TRUST_FOLDER = "./trust/"
TRUST_POINTS = {"drop_off": [5.0, -1.0, 1.1, 0.0], "room_search": [5.0, -1.0, 1.1, 0.0],
                "found_goal": [5.0, -2, 1.0, 0.0]}  # initial value, decrease, increase, trust threshold


class Trust:
    def __init__(self, agent):
        self.agent = agent
        self.headers = ['agent_id', 'drop_off', 'room_search', 'found_goal']
        self.file = TRUST_FOLDER + str(agent.agent_id) + '.csv'

        if not os.path.exists(TRUST_FOLDER):
            os.makedirs(TRUST_FOLDER)

        if not os.path.exists(self.file):
            with open(self.file, 'w+', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=self.headers)
                writer.writeheader()

        agents = self._get_trust()

        # Check if all agents have a row in trust file
        with open(self.file, 'a', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=self.headers)

            for other_agent in self.agent.other_agents:
                if other_agent["agent_id"] not in [_agent["agent_id"] for _agent in agents]:
                    writer.writerow({'agent_id': other_agent["agent_id"],
                                     'drop_off': TRUST_POINTS['drop_off'][0],
                                     'room_search': TRUST_POINTS['room_search'][0],
                                     'found_goal': TRUST_POINTS['found_goal'][0]})

    # Returns true if we can trust an agent to perform a certain task
    def _can_trust(self, agent_id, action):
        agents = self._get_trust()
        for agent in agents:
            if agent["agent_id"] == agent_id:
                return TRUST_POINTS[action][3] < float(agent[action])

    # Returns true if we can trust an agent overall
    def can_trust_overall(self, agent_id):
        agents = self._get_trust()
        for agent in agents:
            if agent["agent_id"] == agent_id:
                avg = (float(agent['drop_off']) + float(agent['room_search']) + float(agent['found_goal'])) / 3
                return avg > 0

    # Update trust based on agent_id, action (header) and value
    def _update_trust(self, agent_id, action, value):
        if self.agent.agent_id == agent_id:
            return
        agents = self._get_trust()
        for agent in agents:
            if agent["agent_id"] == agent_id:
                agent[action] = str(float(agent[action]) + value)
                break
        # overwrite existing csv file
        with open(self.file, 'w+', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=self.headers)
            writer.writeheader()
            writer.writerows(agents)

    # Get trust as dictionary objects
    def _get_trust(self):
        agents = []

        with open(self.file, 'r') as file:
            csv_reader = csv.reader(file)
            next(csv_reader)  # skip headers
            for row in csv_reader:
                agent = {}
                for i, column in enumerate(row):
                    agent[self.headers[i]] = column

                agents.append(agent)
        return agents

    def can_trust_drop_off(self, agent_id):
        return self._can_trust(agent_id, "drop_off")

    # Decrease drop off trust
    def decrease_drop_off(self, agent_id):
        self._update_trust(agent_id, "drop_off", TRUST_POINTS["drop_off"][1])

    # Increase drop off trust
    def increase_drop_off(self, agent_id):
        self._update_trust(agent_id, "drop_off", TRUST_POINTS["drop_off"][2])

    def can_trust_found_goal(self, agent_id):
        return self._can_trust(agent_id, "found_goal")

    # Decrease found goal trust
    def decrease_found_goal(self, agent_id):
        self._update_trust(agent_id, "found_goal", TRUST_POINTS["found_goal"][1])

    # Increase found goal trust
    def increase_found_goal(self, agent_id):
        self._update_trust(agent_id, "found_goal", TRUST_POINTS["found_goal"][2])

    def get_value_room_search(self, agent_id):
        agents = self._get_trust()
        for agent in agents:
            if agent["agent_id"] == agent_id:
                return float(agent["room_search"])

    # Decrease room search trust
    def decrease_room_search(self, agent_id):
        self._update_trust(agent_id, "room_search", TRUST_POINTS["room_search"][1])

    # Increase room search trust
    def increase_room_search(self, agent_id):
        self._update_trust(agent_id, "room_search", TRUST_POINTS["room_search"][2])


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