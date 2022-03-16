import json
from typing import Dict

from matrx.actions.door_actions import OpenDoorAction
from matrx.actions.object_actions import DropObject, GrabObject
from matrx.agents.agent_utils.navigator import Navigator
from matrx.agents.agent_utils.state import State
from matrx.agents.agent_utils.state_tracker import StateTracker

from Group58Agent.GoalDropper import find_goal_blocks
from Group58Agent.MessageHandler import send_msg, can_move, update_map_info, can_grab
from Group58Agent.RoomChooser import choose_door
from Group58Agent.RoomVisiter import visit_room
from Group58Agent.util import move_to, Phase
from bw4t.BW4TBrain import BW4TBrain


class Group58Agent(BW4TBrain):
    def __init__(self, settings: Dict[str, object]):
        super().__init__(settings)
        self.phase = Phase.PLAN_PATH_TO_CLOSED_DOOR
        self.started = False
        self.team_members = []
        self.visited = {}
        self.doors = []
        self.goal = []
        self.carrying = None
        self.state_tracker = None
        self.navigator = None
        self._door = None
        self._grabed_block = None
        self.goal_dropzone = None

    def initialize(self):
        super().initialize()
        self.state_tracker = StateTracker(agent_id=self.agent_id)
        self.navigator = Navigator(
            agent_id=self.agent_id,
            action_set=self.action_set,
            algorithm=Navigator.A_STAR_ALGORITHM,
        )

    def filter_bw4t_observations(self, state):
        return state

    # Initialize doors and goal
    def _initialize_state(self, state):
        self.goal = []
        for block in state.values():
            if "class_inheritance" in block and "GhostBlock" in block["class_inheritance"]:
                self.goal.append({"colour": block["visualization"]["colour"], "shape": block["visualization"]["shape"],
                                  "location": block["location"]})

        self.doors = [
            door
            for door in state.values()
            if "class_inheritance" in door
               and "Door" in door["class_inheritance"]
               and not door["is_open"]
        ]
        self.team_members = state["World"]["team_members"]

    # Choose action to perform
    def decide_on_bw4t_action(self, state: State):
        if not self.team_members:
            self._initialize_state(state)

        if len(self.goal) == 0 and self.phase != Phase.DROP_GOAL and self.phase != Phase.GRAB_GOAL:
            # print(self.agent_id + ' is done.')
            return move_to(self, (1, 1), state)

        if Phase.PLAN_PATH_TO_CLOSED_DOOR == self.phase:
            self._door = choose_door(self, state)
            if self._door is not None:
                # Send message of current action
                my_action = '{ "agent_name":"' + self.agent_id + '", "action":"MOVE_TO_ROOM", "room_name":"' + \
                            self._door[
                                "room_name"] + '"}'
                send_msg(self, my_action, self.agent_id)

                if can_move(self, json.loads(my_action)):
                    self.phase = Phase.FOLLOW_PATH_TO_CLOSED_DOOR
                    # Location in front of door is south from door
                    door_location = self._door["location"][0], self._door["location"][1] + 1

                    self.navigator.add_waypoints([door_location])
                else:
                    return None, {}
            else:
                self.phase = Phase.FIND_GOAL
                return None, {}

        if Phase.FOLLOW_PATH_TO_CLOSED_DOOR == self.phase:
            update_map_info(self)
            self.state_tracker.update(state)
            # Follow path to door
            action = self.navigator.get_move_action(self.state_tracker)
            if action is not None:
                return action, {}
            self.phase = Phase.OPEN_DOOR

        if Phase.OPEN_DOOR == self.phase:
            update_map_info(self)
            self.phase = Phase.SEARCH_ROOM
            # Open door
            return OpenDoorAction.__name__, {"object_id": self._door["obj_id"]}

        if Phase.SEARCH_ROOM == self.phase:
            self.state_tracker.update(state)
            update_map_info(self)
            # Walk through the whole room and observe what kind of objects are there
            action = visit_room(self, self._door, state)

            my_action = '{ "agent_name":"' + self.agent_id + '", "action":"SEARCH_ROOM", "room_name":"' + self._door[
                "room_name"] + '", "room_content":' + json.dumps(self.visited[self._door["room_name"]]) + '}'
            send_msg(self, my_action, self.agent_id)

            return action

        if Phase.FIND_GOAL == self.phase:
            self.state_tracker.update(state)
            update_map_info(self)
            if self._door is None or state[self.agent_id]["location"] == self._door[
                "location"]:  # check if we can look for goals
                goal_blocks = find_goal_blocks(self, state)
                if goal_blocks is not None and len(goal_blocks) > 0:
                    for block in goal_blocks:
                        my_action = '{ "agent_name":"' + self.agent_id + '", "action":"DROP_GOAL", "location": [' + str(
                            block["location"][0]) + ', ' + str(block["location"][1]) + ' ], "distance":' + str(
                            block["distance"]) + '}'
                        send_msg(self, my_action, self.agent_id)
                        if can_grab(self, json.loads(my_action)):
                            self.goal_dropzone = self.goal[0]
                            self._grabed_block = block
                            # Remove goal from list
                            self.goal.pop(0)
                            self.phase = Phase.GRAB_GOAL
                            # Send message of current action
                            my_action = '{ "agent_name":"' + self.agent_id + '", "action":"GRABBED_BLOCK"}'
                            send_msg(self, my_action, self.agent_id)
                            self._door = None
                            return move_to(self, (self._grabed_block["location"][0], self._grabed_block["location"][1]),
                                           state)
                else:
                    self.phase = Phase.PLAN_PATH_TO_CLOSED_DOOR
                    return None, {}
            else:
                return move_to(self, self._door["location"], state)

        if Phase.GRAB_GOAL == self.phase:
            self.state_tracker.update(state)
            if state[self.agent_id]["location"] == (
            self._grabed_block["location"][0], self._grabed_block["location"][1]):
                self.phase = Phase.DROP_GOAL
                return GrabObject.__name__, {"object_id": self._grabed_block["obj_id"]}
            else:
                return move_to(self, (self._grabed_block["location"][0], self._grabed_block["location"][1]), state)

        if Phase.DROP_GOAL == self.phase:
            self.state_tracker.update(state)
            if state[self.agent_id]["location"] == self.goal_dropzone["location"]:
                self.phase = Phase.FIND_GOAL
                self._door = None
                # TODO: make sure that previous goal block was dropped
                return DropObject.__name__, {}
            else:
                return move_to(self, self.goal_dropzone["location"], state)
