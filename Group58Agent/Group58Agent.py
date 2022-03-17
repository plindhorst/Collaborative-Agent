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
        self._grabbed_block = None
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
        i = 0
        for block in state.values():
            if "class_inheritance" in block and "GhostBlock" in block["class_inheritance"]:
                self.goal.append({"colour": block["visualization"]["colour"], "shape": block["visualization"]["shape"],
                                  "location": block["location"], "delivered": False, "grabbed": False, "n": i})
                i += 1

        self.doors = [
            door
            for door in state.values()
            if "class_inheritance" in door
               and "Door" in door["class_inheritance"]
               and not door["is_open"]
        ]
        self.team_members = state["World"]["team_members"]

    # return the next goal to be delivered
    # if all goals were delievered return None
    def get_next_goal(self):
        for block in self.goal:
            if not block["delivered"] and not block["grabbed"]:
                return block
        return None

    # Choose action to perform
    def decide_on_bw4t_action(self, state: State):
        if not self.team_members:
            # we initialise our map and goal arrays
            self._initialize_state(state)

        self.state_tracker.update(state)

        # if all doors have been opened
        # TODO: phase done also when all doors have been opened and no goals blocks found
        if self.phase == Phase.DONE or (self.get_next_goal() is None and self._grabbed_block is None):
            # print(self.agent_id + ' is done.')
            self.phase = Phase.DONE
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
            update_map_info(self)
            # Walk through the whole room and observe what kind of objects are there
            action = visit_room(self, self._door, state)

            my_action = '{ "agent_name":"' + self.agent_id + '", "action":"SEARCH_ROOM", "room_name":"' + self._door[
                "room_name"] + '", "room_content":' + json.dumps(self.visited[self._door["room_name"]]) + '}'
            send_msg(self, my_action, self.agent_id)

            return action

        if Phase.FIND_GOAL == self.phase:
            update_map_info(self)
            if self._door is None or state[self.agent_id]["location"] == self._door["location"]:
                goal_blocks = find_goal_blocks(self, state)
                if goal_blocks is not None:
                    goal_block = goal_blocks[0]
                    my_action = '{ "agent_name":"' + self.agent_id + '", "action":"DROP_GOAL", "location": [' + str(
                        goal_block["location"][0]) + ', ' + str(
                        goal_block["location"][1]) + '] , "distance":' + str(
                        goal_block["distance"]) + '}'
                    send_msg(self, my_action, self.agent_id)
                    if can_grab(self, json.loads(my_action)):
                        self._grabbed_block = goal_block
                        # Remove goal from list
                        self.goal_dropzone = self.get_next_goal()
                        self.goal_dropzone["grabbed"] = True
                        self.phase = Phase.GRAB_GOAL
                        # Send message of current action
                        my_action = '{ "agent_name":"' + self.agent_id + '", "action":"GRABBED_BLOCK", "location": [' + str(
                            goal_block["location"][0]) + ', ' + str(
                            goal_block["location"][1]) + '] , "room_name": "' + str(
                            goal_block["room_name"]) + '", "goal_idx":' + str(self.goal_dropzone["n"]) + '}'
                        send_msg(self, my_action, self.agent_id)
                        self._door = None
                        return move_to(self, (goal_block["location"][0], goal_block["location"][1]), state)
                    # if we do not grab anything keep room searching
                    self.phase = Phase.PLAN_PATH_TO_CLOSED_DOOR
                    return None, {}
                else:
                    if len(self.visited) == len(self.doors):
                        self.phase = Phase.DONE
                    else:
                        self.phase = Phase.PLAN_PATH_TO_CLOSED_DOOR
                    return None, {}
            else:
                return move_to(self, self._door["location"], state)

        if Phase.GRAB_GOAL == self.phase:
            if state[self.agent_id]["location"] == (
                    self._grabbed_block["location"][0], self._grabbed_block["location"][1]):
                self.phase = Phase.DROP_GOAL
                # Remove block from room array
                new_array = []
                for old_block in self.visited[self._grabbed_block["room_name"]]:
                    if old_block["location"] != self._grabbed_block["location"]:
                        new_array.append(old_block)
                self.visited[self._grabbed_block["room_name"]] = new_array
                return GrabObject.__name__, {"object_id": self._grabbed_block["obj_id"]}
            else:
                return move_to(self, (self._grabbed_block["location"][0], self._grabbed_block["location"][1]), state)

        if Phase.DROP_GOAL == self.phase:
            update_map_info(self)
            # check if we are on location and if we bring the first block or the previous block was delivered
            if state[self.agent_id]["location"] == self.goal_dropzone["location"] and (
                    self.goal_dropzone["n"] == 0 or self.goal[self.goal_dropzone["n"] - 1]["delivered"]):
                self.phase = Phase.FIND_GOAL
                self._door = None
                self.goal_dropzone["delivered"] = True

                my_action = '{ "agent_name":"' + self.agent_id + '", "action":"DELIVERED_BLOCK", "goal_idx":' + str(
                    self.goal_dropzone["n"]) + '}'
                send_msg(self, my_action, self.agent_id)

                self._grabbed_block = None
                self.goal_dropzone = None

                return DropObject.__name__, {}
            else:
                return move_to(self, self.goal_dropzone["location"], state)
