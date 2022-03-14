import enum
from typing import Dict

import numpy as np
from matrx import utils
from matrx.actions.door_actions import OpenDoorAction
from matrx.actions.object_actions import GrabObject, DropObject
from matrx.agents.agent_utils.navigator import Navigator
from matrx.agents.agent_utils.state import State
from matrx.agents.agent_utils.state_tracker import StateTracker
from matrx.messages.message import Message

from bw4t.BW4TBrain import BW4TBrain


class Phase(enum.Enum):
    PLAN_PATH_TO_CLOSED_DOOR = (1,)
    FOLLOW_PATH_TO_CLOSED_DOOR = (2,)
    OPEN_DOOR = 3
    SEARCH_ROOM = 4
    FOUND_GOAL_BLOCK = 5
    PICK_UP_GOAL_BLOCK = 6
    DROP_GOAL_BLOCK = 7


class Group58Agent(BW4TBrain):
    def __init__(self, settings: Dict[str, object]):
        super().__init__(settings)
        self._phase = Phase.PLAN_PATH_TO_CLOSED_DOOR
        self._teamMembers = []
        self._visited = {}
        self._doors = []
        self._goal = []
        self._carrying = None
        self._state_tracker = None
        self._navigator = None
        self._door = None

    def initialize(self):
        super().initialize()
        self._state_tracker = StateTracker(agent_id=self.agent_id)
        self._navigator = Navigator(
            agent_id=self.agent_id,
            action_set=self.action_set,
            algorithm=Navigator.A_STAR_ALGORITHM,
        )

    def filter_bw4t_observations(self, state):
        return state

    def decide_on_bw4t_action(self, state: State):
        if len(self._doors) == 0 and len(self._goal) == 0:
            self.init_state(state)

        agent_name = state[self.agent_id]["obj_id"]
        # Add team members
        for member in state["World"]["team_members"]:
            if member != agent_name and member not in self._teamMembers:
                self._teamMembers.append(member)
        # Process messages from team members
        received_messages = self._process_messages(self._teamMembers)
        # Update trust beliefs for team members
        self._trust(self._teamMembers, received_messages)

        while True:
            if Phase.PLAN_PATH_TO_CLOSED_DOOR == self._phase:
                self._navigator.reset_full()
                # Randomly pick a closed door
                self._door = self._choose_door(state)
                if self._door is None:
                    # Program ends here currently
                    print(self._visited)
                    return None, {}
                # Location in front of door is south from door
                door_location = self._door["location"][0], self._door["location"][1] + 1
                # Send message of current action
                self._sendMessage(
                    "Moving to door of " + self._door["room_name"], agent_name
                )
                self._navigator.add_waypoints([door_location])
                self._phase = Phase.FOLLOW_PATH_TO_CLOSED_DOOR

            if Phase.FOLLOW_PATH_TO_CLOSED_DOOR == self._phase:
                self._state_tracker.update(state)
                # Follow path to door
                action = self._navigator.get_move_action(self._state_tracker)
                if action is not None:
                    return action, {}
                self._phase = Phase.OPEN_DOOR

            if Phase.OPEN_DOOR == self._phase:
                # self._phase = Phase.PLAN_PATH_TO_CLOSED_DOOR
                self._phase = Phase.SEARCH_ROOM
                # Open door

                return OpenDoorAction.__name__, {"object_id": self._door["obj_id"]}

            if Phase.SEARCH_ROOM == self._phase:
                # Walk through the whole room and observe what kind of objects are there
                return self._visit_room(self._door, state)

            if Phase.FOUND_GOAL_BLOCK == self._phase:
                # Assign goal block to variable?
                self._phase = Phase.PICK_UP_GOAL_BLOCK

            if Phase.PICK_UP_GOAL_BLOCK == self._phase:
                # Do something
                self._phase = Phase.DROP_GOAL_BLOCK

            if Phase.DROP_GOAL_BLOCK == self._phase:
                location = self._goal[0]["location"]
                action, x = self._get_navigation_action(location, state)
                if (action != None):
                    self._phase = Phase.DROP_GOAL_BLOCK
                    return action, x

                self._phase = Phase.PLAN_PATH_TO_CLOSED_DOOR
                self._goal.pop(0)

                return DropObject.__name__, {}

    # Initialize doors and goal
    def init_state(self, state: State):
        self._goal = [
            block
            for block in state.values()
            if "class_inheritance" in block
               and "GhostBlock" in block["class_inheritance"]
        ]
        self._doors = [
            door
            for door in state.values()
            if "class_inheritance" in door
               and "Door" in door["class_inheritance"]
               and not door["is_open"]
        ]

    # returns doors ordered by distance to the agent
    def _get_doors_by_distance(self, state):
        agent_coords = state[self.agent_id]["location"]

        rooms = np.array(state.get_with_property({"class_inheritance": "Door", "room_name": None}, combined=True))

        def distance(x):
            room_coords = x['location']
            return utils.get_distance(agent_coords, room_coords)

        # order rooms by distance
        distances = np.array(list(map(distance, rooms)))
        for i, room in enumerate(rooms):
            room["distance"] = distances[i]
        return sorted(rooms, key=lambda x: x["distance"], reverse=False)

    # Choose door until all are visited.
    # TODO make it so that it chooses the first of a queue that can be updated
    # In beginning queue has all doors that are closed, when all doors open
    # it should go to doors with goal blocks (so these doors need to be added to queue)
    def _choose_door(self, state):
        if len(self._visited) <= len(self._doors):
            for door in self._get_doors_by_distance(state):
                if len(self._visited) == 0:
                    return door
                if len(self._visited) > 0 and door["room_name"] not in self._visited.keys():
                    return door

        return None

    # Visit room and record all blocks seen in visibleblocks.
    def _visit_room(self, door, state : State):
        action, x = self._update_visited(door, state)
        if (action != None):
            return action, x

        door_location = door["location"]
        self_location = state[self.agent_id]["location"]

        self._phase = Phase.SEARCH_ROOM
        # Top to bottom approach
        # Final step
        if self_location == (door_location[0] - 1, door_location[1] - 2):
            self._phase = Phase.PLAN_PATH_TO_CLOSED_DOOR

            next_location = door_location[0] - 1, door_location[1] - 1
            return self._get_navigation_action(next_location, state)
        # Second step
        elif self_location == (door_location[0], door_location[1] - 2):
            next_location = door_location[0] - 1, door_location[1] - 2
            return self._get_navigation_action(next_location, state)
        # First step
        else:
            next_location = door_location[0], door_location[1] - 2
            return self._get_navigation_action(next_location, state)

    # Get action for navigation
    def _get_navigation_action(self, location, state):
        self._navigator.reset_full()
        self._navigator.add_waypoints([location])
        self._state_tracker.update(state)
        return self._navigator.get_move_action(self._state_tracker), {}

    # Update the blocks seen in room
    def _update_visited(self, door, state):
        visibleblocks = [
            block["visualization"]
            for block in state.values()
            if "class_inheritance" in block
               and "CollectableBlock" in block["class_inheritance"]
        ]

        key = door["room_name"]

        if self._visited.get(key) is None:
            self._visited[key] = []

        self._visited[key].extend(visibleblocks)

        return self._check_goal_block(state)

    # Check if blocks in surrounding are goal block.
    def _check_goal_block(self, state):
        blocks = [
                    block
                    for block in state.values()
                    if "class_inheritance" in block
                    and "CollectableBlock" in block["class_inheritance"]
                ]
        if (len(blocks) > 0):
            if (blocks[0]["visualization"]["colour"] == self._goal[0]["visualization"]["colour"] 
                and blocks[0]["visualization"]["shape"] == self._goal[0]["visualization"]["shape"]):
                
                self._phase = Phase.FOUND_GOAL_BLOCK
                self._carrying = blocks[0]
                
                return GrabObject.__name__, {"object_id": blocks[0]["obj_id"]}

        return None, {}


    def _sendMessage(self, mssg, sender):
        """
        Enable sending messages in one line of code
        """
        msg = Message(content=mssg, from_id=sender)
        if msg.content not in self.received_messages:
            self.send_message(msg)

    def _process_messages(self, teamMembers):
        """
        Process incoming messages and create a dictionary with received messages from each team member.
        """
        received_messages = {}
        for member in teamMembers:
            received_messages[member] = []
        for mssg in self.received_messages:
            for member in teamMembers:
                if mssg.from_id == member:
                    received_messages[member].append(mssg.content)
        return received_messages

    def _trust(self, member, received):
        """
        Baseline implementation of a trust belief. Creates a dictionary with trust belief scores for each team member,
        for example based on the received messages.
        """
        # You can change the default value to your preference
        default = 0.5
        trust_beliefs = {}
        for member in received.keys():
            trust_beliefs[member] = default
        for member in received.keys():
            for message in received[member]:
                if "Found" in message and "colour" not in message:
                    trust_beliefs[member] -= 0.1
                    break
        return trust_beliefs
