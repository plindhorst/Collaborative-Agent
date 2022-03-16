import json
from typing import Dict

from matrx.actions.door_actions import OpenDoorAction
from matrx.actions.object_actions import DropObject
from matrx.agents.agent_utils.navigator import Navigator
from matrx.agents.agent_utils.state import State
from matrx.agents.agent_utils.state_tracker import StateTracker

from Group58Agent.MessageHandler import send_msg, can_move, update_map_info
from Group58Agent.RoomChooser import choose_door
from Group58Agent.RoomVisiter import visit_room
from Group58Agent.util import get_navigation_action, Phase
from bw4t.BW4TBrain import BW4TBrain


class Group58Agent(BW4TBrain):
    def __init__(self, settings: Dict[str, object]):
        super().__init__(settings)
        self.phase = Phase.PLAN_PATH_TO_CLOSED_DOOR
        self.team_members = []
        self.visited = {}
        self.doors = []
        self.goal = []
        self.carrying = None
        self.state_tracker = None
        self.navigator = None
        self._door = None

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
        self.goal = [
            block
            for block in state.values()
            if "class_inheritance" in block
               and "GhostBlock" in block["class_inheritance"]
        ]
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

        # Update trust beliefs for team members
        # self._trust(self._teamMembers, received_messages)

        if Phase.PLAN_PATH_TO_CLOSED_DOOR == self.phase:
            self._door = choose_door(self, state)
            if self._door is None:
                # Program ends here currently
                print(self.visited)
                return None, {}

            # Send message of current action
            my_action = '{ "agent_name":"' + self.agent_id + '", "action":"MOVE_TO_ROOM", "room_name":"' + self._door[
                "room_name"] + '"}'
            send_msg(self, my_action, self.agent_id)

            if can_move(self, json.loads(my_action)):
                self.phase = Phase.FOLLOW_PATH_TO_CLOSED_DOOR
                # Location in front of door is south from door
                door_location = self._door["location"][0], self._door["location"][1] + 1

                self.navigator.add_waypoints([door_location])
            else:
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
            # self._phase = Phase.PLAN_PATH_TO_CLOSED_DOOR
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

        if Phase.FOUND_GOAL_BLOCK == self.phase:
            # Assign goal block to variable?
            self.phase = Phase.PICK_UP_GOAL_BLOCK

        if Phase.PICK_UP_GOAL_BLOCK == self.phase:
            # Do something
            self.phase = Phase.DROP_GOAL_BLOCK

        if Phase.DROP_GOAL_BLOCK == self.phase:
            location = self.goal[0]["location"]
            action, x = get_navigation_action(self, location, state)
            if action is not None:
                self.phase = Phase.DROP_GOAL_BLOCK
                return action, x

            self.phase = Phase.PLAN_PATH_TO_CLOSED_DOOR
            self.goal.pop(0)

            return DropObject.__name__, {}
