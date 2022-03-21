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
from Group58Agent.util import move_to, is_on_location
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

        # Temporary variables to communicate between phases
        self._chosen_room = None
        self._chosen_goal_block = None
        self._drop_off_n = None

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
            if "class_inheritance" in block and "GhostBlock" in block["class_inheritance"]:
                self.drop_offs.append(
                    {"colour": block["visualization"]["colour"], "shape": block["visualization"]["shape"],
                     "size": block["visualization"]["size"], "location": block["location"], "delivered": False,
                     "grabbed": False, "n": i})
                i += 1

        # Initialise room array
        for room in state.values():
            if "class_inheritance" in room and "Door" in room["class_inheritance"]:
                self.rooms.append(
                    {"room_name": room["room_name"], "location": (room["location"][0], room["location"][1] + 1),
                     "obj_id": room["obj_id"], "visited": False, "last_agent_id": None, "visited_by_me": False})

        # Initialise other_agents array
        for i, agent in enumerate(state["World"]["team_members"]):
            if agent == self.agent_id:
                self.agent_idx = i
            else:
                self.other_agents.append(
                    {"agent_id": agent, "agent_idx": i, "location": (1, 1), "phase": "CHOOSE_ROOM"})

    # Returns a room from a room name
    def get_room(self, room_name):
        for room in self.rooms:
            if room["room_name"] == room_name:
                return room

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
                other_agent["location"] = self.state[other_agent["agent_id"]]["location"]

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
                # TODO: what is next phase?
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
                return move_to(self, self._chosen_room["location"])

        # Going to a room
        elif self.phase_handler.phase_is(Phase.GO_TO_ROOM):
            # TODO: check if the room is not already visited
            if is_on_location(self, self._chosen_room["location"]):
                self.phase = Phase.OPEN_DOOR
                # Inform other agents that we are opening a door
                self.msg_handler.send_opening_door(self._chosen_room["room_name"])
                return None, {}
            else:
                return move_to(self, self._chosen_room["location"])

        # Opening a room door
        elif self.phase_handler.phase_is(Phase.OPEN_DOOR):
            self.phase = Phase.SEARCH_ROOM
            # Inform other agents that we are searching a room
            self.msg_handler.send_searching_room(self._chosen_room["room_name"])
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
            if goal_block is None:
                self.phase = Phase.CHOOSE_ROOM
                return None, {}

            # Check if we are the closest agent (with phase CHOOSE_GOAL) to the goal block
            if self.goal_dropper.grab_conflict(goal_block, distance):
                # Continue with phase CHOOSE_GOAL
                return None, {}
            else:
                # Next phase is going to the block
                self._chosen_goal_block = goal_block
                self.phase = Phase.GRAB_GOAL
                # Mark drop goal as grabbed
                drop_off = self.get_next_drop_off()
                drop_off["grabbed"] = True
                self._drop_off_n = drop_off["n"]
                # Delete temp variable
                self._chosen_room = None
                # Remove grabbed block from found goal blocks
                found_goal_blocks = []
                for old_block in self.found_goal_blocks:
                    if old_block["location"] != self._chosen_goal_block["location"]:
                        found_goal_blocks.append(old_block)
                self.found_goal_blocks = found_goal_blocks
                # Inform other agents that we are grabbing this goal block
                self.msg_handler.send_pickup_goal_block(self._chosen_goal_block)
                return move_to(self, self._chosen_goal_block["location"])

        # grab the goal block
        elif self.phase_handler.phase_is(Phase.GRAB_GOAL):
            # TODO: check if the block was already grabbed
            if is_on_location(self, self._chosen_goal_block["location"]):
                self.phase = Phase.DROP_GOAL
                obj_id = self.goal_dropper.get_block_obj_id(self._chosen_goal_block["location"])
                if obj_id is None:
                    # Block is not there, find another goal
                    self.phase = Phase.CHOOSE_GOAL
                    return None, {}
                # Grab block
                return GrabObject.__name__, {"object_id": obj_id}
            else:
                return move_to(self, self._chosen_goal_block["location"])

        # grab the goal block
        elif self.phase_handler.phase_is(Phase.DROP_GOAL):
            if is_on_location(self, self.drop_offs[self._drop_off_n]["location"]):
                # Check if we are first drop off or previous drop off was delivered
                if self._drop_off_n == 0 or self.drop_offs[self._drop_off_n - 1]["delivered"]:
                    # Next phase is looking for another goal
                    self.phase = Phase.CHOOSE_GOAL
                    # Mark drop off as delivered
                    self.drop_offs[self._drop_off_n]["delivered"] = True
                    # Inform other agnets that we dropped the goal block
                    self.msg_handler.send_drop_goal_block(self._chosen_goal_block,
                                                          self.drop_offs[self._drop_off_n]["location"])
                    # Delete temp vaiables
                    self._chosen_goal_block = None
                    self._drop_off_n = None
                    return DropObject.__name__, {}
                else:
                    return None, {}
            else:
                return move_to(self, self.drop_offs[self._drop_off_n]["location"])
