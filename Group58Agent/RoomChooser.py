import numpy as np

from Group58Agent.util import path


class RoomChooser:
    def __init__(self, agent):
        self.agent = agent

    # Returns closest non-visited room and distance
    def choose_room(self, agent_id):
        unvisited = self._get_unvisited_rooms()

        if len(unvisited) == 0:
            return None, None
        # order rooms by distance
        distances = []
        for room in unvisited:
            start_location = self.agent.state[agent_id]["location"]
            target_location = room["location"]
            distances.append(len(path(agent_id, self.agent.state, start_location, target_location)))
        idx = np.argsort(distances)
        return np.array(unvisited)[idx][0], np.array(distances)[idx][0]

    # Returns true if another agent chose this room and is closer to it
    def room_conflict(self, room, distance):
        # Go over all other agents, if we chose the same room take the one closest to it.
        # In case of draw choose smallest agent_idx
        for other_agent in self.agent.other_agents:
            if other_agent["phase"] == "CHOOSE_ROOM" and other_agent["location"] is not None:
                other_room, other_distance = self.choose_room(other_agent["agent_id"])
                if room["room_name"] == other_room["room_name"]:
                    if distance == other_distance:
                        # choose agent with lowest idx
                        if self.agent.agent_idx > other_agent["agent_idx"]:
                            return True
                    else:
                        # choose smallest distance
                        if distance > other_distance:
                            return True
        return False

    # Returns all rooms that have not been visited
    def _get_unvisited_rooms(self):
        unvisited = []
        for room in self.agent.rooms:
            if not room["visited"]:
                unvisited.append(room)
        return unvisited
