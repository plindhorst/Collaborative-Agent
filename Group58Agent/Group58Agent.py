import random
from typing import Dict

from matrx.actions.door_actions import OpenDoorAction
from matrx.actions.object_actions import DropObject, GrabObject
from matrx.agents.agent_utils.navigator import Navigator
from matrx.agents.agent_utils.state_tracker import StateTracker

from Group58Agent.GoalDropper import GoalDropper
from Group58Agent.MessageHandler import MessageHandler
from Group58Agent.PhaseHandler import PhaseHandler, Phase
from Group58Agent.RoomChooser import RoomChooser
from Group58Agent.RoomVisiter import RoomVisiter
from Group58Agent.util import move_to, is_on_location, path
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

        # Temp variables for lazy
        self.skip_room_search = False
        self.skip_drop_off = False
        self.skip_move_to_room = False
        self._path_length_room = None
        self._path_length_move_to_room = None
        self._path_length_drop_off = None

        self._chosen_goal_block = []
        self._drop_off_n = []
        self.held_block_ids = []
        self.picked_up_blocks = 0

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
    # if all goals were delievered return None
    def get_next_drop_off(self):
        for drop_off in self.drop_offs:
            if not drop_off["delivered"] and not drop_off["grabbed"]:
                return drop_off
        return None

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

        self.state = state
        self._update_agent_locations()
        self.msg_handler.read_messages()

        # Choosing a room
        if self.phase_handler.phase_is(Phase.CHOOSE_ROOM):
            # Get closest room and distance to it
            room, distance = self.room_chooser.choose_room(self.agent_id)

            # All rooms have been visited
            if room is None:
                self.phase = Phase.CHOOSE_GOAL
                return None, {}

            # Check if we are the closest agent (with phase CHOOSE_ROOM) to the room
            if self.room_chooser.room_conflict(room, distance):
                # Continue with phase CHOOSE_ROOM
                return None, {}
            else:
                # We go to the room
                self._chosen_room = room
                self.phase = Phase.GO_TO_ROOM
                # Mark room as visited
                room = self.get_room(self._chosen_room["room_name"])
                room["visited"] = True
                room["visited_by_me"] = True
                room["last_agent_id"] = self.agent_id
                # Inform other agents that we are going to the room
                self.msg_handler.send_moving_to_room(self._chosen_room["room_name"])
                # Are we going to lazy/lie skip during moving to room
                self.skip_move_to_room = self.lazy_skip() or self.lie()

                # Store path length to room
                self._path_length_move_to_room = len(
                    path(self.agent_id, self.state, self.location, self._chosen_room["location"]))
                return move_to(self, self._chosen_room["location"])

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
                    return None, {}
                else:
                    return move_to(self, self._chosen_room["location"])

        # Opening a room door
        elif self.phase_handler.phase_is(Phase.OPEN_DOOR):
            self.phase = Phase.SEARCH_ROOM
            # Inform other agents that we are searching a room
            self.msg_handler.send_searching_room(self._chosen_room["room_name"])
            # Are we going to lazy/lie skip during the room search
            self.skip_room_search = self.lazy_skip() or self.lie()
            # Are we going to lie that we found a goal block
            if self.lie():
                # Send current goal block to all other agents at start position
                self.msg_handler.send_found_goal_block(
                    {"colour": self.drop_offs[0]["colour"], "shape": self.drop_offs[0]["shape"],
                     "location": (1, 1),
                     "size": self.drop_offs[0]["size"]})
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

            # No goal block found
            if self.settings["colourblind"] or goal_block is None:
                self.phase = Phase.CHOOSE_ROOM
                return None, {}

            # Check if we are the closest agent (with phase CHOOSE_GOAL) to the goal block
            if self.goal_dropper.grab_conflict(goal_block, distance):
                # Continue with phase CHOOSE_GOAL
                return None, {}
            else:
                # Next phase is going to the block
                self._chosen_goal_block.append(goal_block)
                self.phase = Phase.GRAB_GOAL
                # Mark drop goal as grabbed
                drop_off = self.get_next_drop_off()
                drop_off["grabbed"] = True
                self._drop_off_n.append(drop_off["n"])
                # Delete temp variable
                self._chosen_room = None
                # Remove grabbed block from found goal blocks
                found_goal_blocks = []
                for old_block in self.found_goal_blocks:
                    if old_block["location"] != goal_block["location"]:
                        found_goal_blocks.append(old_block)
                self.found_goal_blocks = found_goal_blocks
                # Inform other agents that we are grabbing this goal block
                self.msg_handler.send_pickup_goal_block(goal_block)
                self.picked_up_blocks += 1
                return move_to(self, goal_block["location"])

        # grab the goal block
        elif self.phase_handler.phase_is(Phase.GRAB_GOAL):
            if is_on_location(self, self._chosen_goal_block[-1]["location"]):

                block = self.goal_dropper.get_block_info(
                    self._chosen_goal_block[-1]["location"]
                )
                # Check if block is here and that it matches
                if block is None or self.drop_offs[self._drop_off_n[0]]["colour"] != block["colour"] or \
                        self.drop_offs[self._drop_off_n[0]]["shape"] != block["shape"]:
                    # TODO: Decrease Trust here, remember who send block found
                    # Infrom the other agents that grabbing was unsuccessful by dropping a wrong block
                    self.msg_handler.send_drop_goal_block(
                        {"colour": "#000000", "shape": -1,
                         "location": self.location, "size": 0.5},
                        self.location,
                    )
                    # Block is not there, find another goal
                    self.phase = Phase.CHOOSE_GOAL
                    # Reset grabbed and delete temp variables
                    self.drop_offs[self._drop_off_n[0]]["grabbed"] = False
                    self._chosen_goal_block.pop(0)
                    self._drop_off_n.pop(0)
                    return None, {}

                # If the agent is strong and holds less than 2 blocks
                # and there are were less than 2 pick ups already
                # search for another goal block next.
                if (
                        self.settings["strong"]
                        and len(self.held_block_ids) < 1
                        and self.picked_up_blocks < 2
                ):
                    self.phase = Phase.CHOOSE_GOAL
                else:
                    self.phase = Phase.DROP_GOAL

                # Save the ID to later know what to drop
                self.held_block_ids.append(block["obj_id"])

                # Are we going to lazy skip during the drop off
                self.skip_drop_off = self.lazy_skip()
                # Store path length to drop off location
                self._path_length_drop_off = len(
                    path(self.agent_id, self.state, self.location, self.drop_offs[self._drop_off_n[0]]["location"]))
                # Grab block
                return GrabObject.__name__, {"object_id": block["obj_id"]}
            else:
                return move_to(self, self._chosen_goal_block[-1]["location"])

        # drop the goal block
        elif self.phase_handler.phase_is(Phase.DROP_GOAL):
            if is_on_location(self, self.drop_offs[self._drop_off_n[0]]["location"]):
                # Check if we are first drop off or previous drop off was delivered
                if (
                        self._drop_off_n[0] == 0
                        or self.drop_offs[self._drop_off_n[0] - 1]["delivered"]
                ):
                    # Next phase is looking for another goal
                    self.phase = Phase.CHOOSE_GOAL
                    # Mark drop off as delivered

                    self.drop_offs[self._drop_off_n[0]]["delivered"] = True
                    # Inform other agents that we dropped the goal block
                    self.msg_handler.send_drop_goal_block(
                        self._chosen_goal_block[0],
                        self.drop_offs[self._drop_off_n[0]]["location"],
                    )

                    # Delete temp variables
                    if self.settings["strong"] and len(self.held_block_ids) > 1:
                        # If the agent is the strong one remove
                        # the head of the goal block list, drop_off_nth
                        self._chosen_goal_block.pop(0)
                        self._drop_off_n.pop(0)
                        self.phase = Phase.DROP_GOAL
                    else:
                        self._chosen_goal_block = []
                        self._drop_off_n = []
                    # pop the ID
                    obj_id = self.held_block_ids.pop(0)
                    return DropObject.__name__, {"object_id": obj_id}
                else:
                    return None, {}
            else:

                # We skip drop off if we are halfway through the path
                if self.skip_drop_off and len(path(self.agent_id, self.state, self.location,
                                                   self.drop_offs[self._drop_off_n[0]][
                                                       "location"])) / self._path_length_drop_off < 0.5:
                    # Make sure that we are not on another drop off location
                    for drop_off in self.drop_offs:
                        if drop_off != self.drop_offs[self._drop_off_n[0]] and is_on_location(self,
                                                                                              drop_off["location"]):
                            return move_to(self, self.drop_offs[self._drop_off_n[0]]["location"])
                    # Add dropped goal blocks to found goal blocks
                    self._chosen_goal_block[0]["location"] = self.location
                    self.found_goal_blocks.append(self._chosen_goal_block[0])
                    self.drop_offs[self._drop_off_n[0]]["grabbed"] = False
                    # Next phase is looking for another goal
                    self.phase = Phase.CHOOSE_ROOM

                    # Inform other agents that we dropped the goal block
                    self.msg_handler.send_drop_goal_block(self._chosen_goal_block[0], self.location)

                    # Delete temp vaiables
                    self._chosen_goal_block = []
                    self._drop_off_n = []
                    return DropObject.__name__, {}
                else:
                    return move_to(self, self.drop_offs[self._drop_off_n[0]]["location"])
