import numpy as np

from Group58Agent.util import path


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
