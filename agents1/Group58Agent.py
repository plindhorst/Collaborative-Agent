from os import stat
from typing import final, List, Dict, Final
import enum
import random
from bw4t.BW4TBrain import BW4TBrain
from matrx.agents.agent_utils.state import State
from matrx.agents.agent_utils.navigator import Navigator
from matrx.agents.agent_utils.state_tracker import StateTracker
from matrx.actions.door_actions import OpenDoorAction
from matrx.actions.object_actions import GrabObject, DropObject
from matrx.messages.message import Message


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
            self.initializeParametersOnState(state)

        agent_name = state[self.agent_id]["obj_id"]
        # Add team members
        for member in state["World"]["team_members"]:
            if member != agent_name and member not in self._teamMembers:
                self._teamMembers.append(member)
        # Process messages from team members
        receivedMessages = self._processMessages(self._teamMembers)
        # Update trust beliefs for team members
        self._trustBlief(self._teamMembers, receivedMessages)

        while True:
            if Phase.PLAN_PATH_TO_CLOSED_DOOR == self._phase:
                self._navigator.reset_full()
                # Randomly pick a closed door
                self._door = self._chooseDoor()
                if (self._door == None):\
                    #Program ends here currently
                    print(self._visited)
                    return None, {}
                doorLoc = self._door["location"]
                # Location in front of door is south from door
                doorLoc = doorLoc[0], doorLoc[1] + 1
                # Send message of current action
                self._sendMessage(
                    "Moving to door of " + self._door["room_name"], agent_name
                )
                self._navigator.add_waypoints([doorLoc])
                self._phase = Phase.FOLLOW_PATH_TO_CLOSED_DOOR

            if Phase.FOLLOW_PATH_TO_CLOSED_DOOR == self._phase:
                self._state_tracker.update(state)
                # Follow path to door
                action = self._navigator.get_move_action(self._state_tracker)
                if action != None:
                    return action, {}
                self._phase = Phase.OPEN_DOOR

            if Phase.OPEN_DOOR == self._phase:
                # self._phase = Phase.PLAN_PATH_TO_CLOSED_DOOR
                self._phase = Phase.SEARCH_ROOM
                # Open door
                    
                return OpenDoorAction.__name__, {"object_id": self._door["obj_id"]}

            if Phase.SEARCH_ROOM == self._phase:
                # TODO: walk through the whole room and observe what kind of objects are there
                return self._visitRoom(self._door, state)

    # Initialize doors and goal
    def initializeParametersOnState(self, state: State):
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
                
    # Choose door until all are visited.
    # TODO make it so that it chooses the first of a queue that can be updated
    # In beginning queue has all doors that are closed, when all doors open
    # it should go to doors with goal blocks (so these doors need to be added to queue)
    def _chooseDoor(self):
        if (len(self._visited) <= len(self._doors)):
            for door in self._doors:
                if (len(self._visited) == 0):
                    return door
                if (len(self._visited) > 0 and door["room_name"] not in self._visited.keys()):
                    return door

        return None

    # Visit room and record all blocks seen in visibleblocks.
    def _visitRoom(self, door, state : State):
        self._update_visited(door, state)
        doorLocation = door["location"]
        selfLocation = state[self.agent_id]["location"]

        self._phase = Phase.SEARCH_ROOM
        # Top to bottom approach
        # Final step
        if (selfLocation == (doorLocation[0] - 1, doorLocation[1] - 2)):
            self._phase = Phase.PLAN_PATH_TO_CLOSED_DOOR

            nextLocation = doorLocation[0] - 1, doorLocation[1] - 1
            return self._get_navigation_action(nextLocation, state)
        # Second step
        elif (selfLocation == (doorLocation[0], doorLocation[1] - 2)):
            nextLocation = doorLocation[0] - 1, doorLocation[1] - 2
            return self._get_navigation_action(nextLocation, state)
        # First step
        else:
            nextLocation = doorLocation[0], doorLocation[1] - 2
            return self._get_navigation_action(nextLocation, state)

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
        
        if self._visited.get(key) == None:
             self._visited[key] = []

        self._visited[key].extend(visibleblocks)


    def _sendMessage(self, mssg, sender):
        """
        Enable sending messages in one line of code
        """
        msg = Message(content=mssg, from_id=sender)
        if msg.content not in self.received_messages:
            self.send_message(msg)

    def _processMessages(self, teamMembers):
        """
        Process incoming messages and create a dictionary with received messages from each team member.
        """
        receivedMessages = {}
        for member in teamMembers:
            receivedMessages[member] = []
        for mssg in self.received_messages:
            for member in teamMembers:
                if mssg.from_id == member:
                    receivedMessages[member].append(mssg.content)
        return receivedMessages

    def _trustBlief(self, member, received):
        """
        Baseline implementation of a trust belief. Creates a dictionary with trust belief scores for each team member, for example based on the received messages.
        """
        # You can change the default value to your preference
        default = 0.5
        trustBeliefs = {}
        for member in received.keys():
            trustBeliefs[member] = default
        for member in received.keys():
            for message in received[member]:
                if "Found" in message and "colour" not in message:
                    trustBeliefs[member] -= 0.1
                    break
        return trustBeliefs
