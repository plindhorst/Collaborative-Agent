import json
from typing import Dict

from matrx.actions.door_actions import OpenDoorAction
from matrx.actions.object_actions import DropObject, GrabObject
from matrx.agents.agent_utils.navigator import Navigator
from matrx.agents.agent_utils.state import State
from matrx.agents.agent_utils.state_tracker import StateTracker

from Group58Agent.GoalDropper import find_goal_blocks
from Group58Agent.MessageHandler import MessageHandler
from Group58Agent.PhaseHandler import PhaseHandler, Phase
from Group58Agent.RoomChooser import RoomChooser
from Group58Agent.RoomVisiter import RoomVisiter
from Group58Agent.util import move_to, is_on_location
from bw4t.BW4TBrain import BW4TBrain


class Group58Agent(BW4TBrain):
    def __init__(self, settings: Dict[str, object]):
        super().__init__(settings)
        # self.phase = Phase.PLAN_PATH_TO_CLOSED_DOOR
        # self.started = False
        # self.team_members = []
        # self.visited = {}
        # self.doors = []
        # self.goal = []
        # self.carrying = None
        # self.state_tracker = None
        # self.navigator = None
        # self._door = None
        # self._grabbed_block = None
        # self.goal_dropzone = None
        self.state = None
        self.state_tracker = None
        self.navigator = None
        self.location = (1, 1)
        self.rooms = []
        self.goal_blocks = []
        self.found_goal_blocks = []
        self.other_agents = []
        self.agent_idx = None
        self.msg_handler = MessageHandler(self)
        self.phase_handler = PhaseHandler(self)
        self.room_chooser = RoomChooser(self)
        self.room_visiter = RoomVisiter(self)

        self.phase = Phase.CHOOSE_ROOM

        # Temporary variables
        self._chosen_room = None

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
                self.goal_blocks.append(
                    {"colour": block["visualization"]["colour"], "shape": block["visualization"]["shape"],
                     "location": block["location"], "delivered": False, "grabbed": False, "n": i})
                i += 1

        # Initialise room array
        for room in state.values():
            if "class_inheritance" in room and "Door" in room["class_inheritance"]:
                self.rooms.append(
                    {"room_name": room["room_name"], "location": (room["location"][0], room["location"][1] + 1),
                     "obj_id": room["obj_id"], "visited": False})

        # Initialise other_agents array
        for i, agent in enumerate(state["World"]["team_members"]):
            if agent == self.agent_id:
                self.agent_idx = i
            else:
                self.other_agents.append(
                    {"agent_id": agent, "agent_idx": i, "location": (1, 1), "phase": "CHOOSE_ROOM"})

    # return the next goal to be delivered
    # if all goals were delievered return None
    def get_next_goal(self):
        for block in self.goal_blocks:
            if not block["delivered"] and not block["grabbed"]:
                return block
        return None

    # Returns a room from a room name
    def get_room(self, room_name):
        for room in self.rooms:
            if room["room_name"] == room_name:
                return room

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
        if not self.other_agents:
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
                # Inform other agents that we are going to the room
                self.msg_handler.send_moving_to_room(self._chosen_room["room_name"])
                return move_to(self, self._chosen_room["location"])

        # Going to a room
        elif self.phase_handler.phase_is(Phase.GO_TO_ROOM):
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
        elif self.phase_handler.phase_is(Phase.FIND_GOAL):
            print(self.agent_id, self.found_goal_blocks)
            return None, {}
        #

        #
        # if Phase.FIND_GOAL == self.phase:
        #     update_map_info(self)
        #     if self._door is None or state[self.agent_id]["location"] == self._door["location"]:
        #         goal_blocks = find_goal_blocks(self, state)
        #         if goal_blocks is not None:
        #             goal_block = goal_blocks[0]
        #             my_action = '{ "agent_name":"' + self.agent_id + '", "action":"DROP_GOAL", "location": [' + str(
        #                 goal_block["location"][0]) + ', ' + str(
        #                 goal_block["location"][1]) + '] , "distance":' + str(
        #                 goal_block["distance"]) + '}'
        #             send_msg(self, my_action, self.agent_id)
        #             if can_grab(self, json.loads(my_action)):
        #                 self._grabbed_block = goal_block
        #                 # Remove goal from list
        #                 self.goal_dropzone = self.get_next_goal()
        #                 self.goal_dropzone["grabbed"] = True
        #                 self.phase = Phase.GRAB_GOAL
        #                 # Send message of current action
        #                 my_action = '{ "agent_name":"' + self.agent_id + '", "action":"GRABBED_BLOCK", "location": [' + str(
        #                     goal_block["location"][0]) + ', ' + str(
        #                     goal_block["location"][1]) + '] , "room_name": "' + str(
        #                     goal_block["room_name"]) + '", "goal_idx":' + str(self.goal_dropzone["n"]) + '}'
        #                 send_msg(self, my_action, self.agent_id)
        #                 self._door = None
        #                 return move_to(self, (goal_block["location"][0], goal_block["location"][1]), state)
        #             # if we do not grab anything keep room searching
        #             self.phase = Phase.PLAN_PATH_TO_CLOSED_DOOR
        #             return None, {}
        #         else:
        #             if len(self.visited) == len(self.doors):
        #                 self.phase = Phase.DONE
        #             else:
        #                 self.phase = Phase.PLAN_PATH_TO_CLOSED_DOOR
        #             return None, {}
        #     else:
        #         return move_to(self, self._door["location"], state)
        #
        # if Phase.GRAB_GOAL == self.phase:
        #     if state[self.agent_id]["location"] == (
        #             self._grabbed_block["location"][0], self._grabbed_block["location"][1]):
        #         self.phase = Phase.DROP_GOAL
        #         # Remove block from room array
        #         new_array = []
        #         for old_block in self.visited[self._grabbed_block["room_name"]]:
        #             if old_block["location"] != self._grabbed_block["location"]:
        #                 new_array.append(old_block)
        #         self.visited[self._grabbed_block["room_name"]] = new_array
        #         return GrabObject.__name__, {"object_id": self._grabbed_block["obj_id"]}
        #     else:
        #         return move_to(self, (self._grabbed_block["location"][0], self._grabbed_block["location"][1]), state)
        #
        # if Phase.DROP_GOAL == self.phase:
        #     update_map_info(self)
        #     # check if we are on location and if we bring the first block or the previous block was delivered
        #     if state[self.agent_id]["location"] == self.goal_dropzone["location"] and (
        #             self.goal_dropzone["n"] == 0 or self.goal[self.goal_dropzone["n"] - 1]["delivered"]):
        #         self.phase = Phase.FIND_GOAL
        #         self._door = None
        #         self.goal_dropzone["delivered"] = True
        #
        #         my_action = '{ "agent_name":"' + self.agent_id + '", "action":"DELIVERED_BLOCK", "goal_idx":' + str(
        #             self.goal_dropzone["n"]) + '}'
        #         send_msg(self, my_action, self.agent_id)
        #
        #         self._grabbed_block = None
        #         self.goal_dropzone = None
        #
        #         return DropObject.__name__, {}
        #     else:
        #         return move_to(self, self.goal_dropzone["location"], state)
