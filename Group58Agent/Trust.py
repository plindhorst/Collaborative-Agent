import csv
import os

TRUST_FOLDER = "./trust/"
TRUST_POINTS = {"drop_off": [5.0, -1.0, 1.0, 0.0], "room_search": [5.0, -1.0, 1.0, 0.0],
                "found_goal": [5.0, -3.0, 3.0, 0.0]}


# initial value, deacrease, increase, trust threshold

class Trust:
    def __init__(self, agent):
        self.agent = agent
        self.headers = ['agent_id', 'drop_off', 'room_search', 'found_goal']
        self.file = TRUST_FOLDER + str(agent.agent_id) + '.csv'

        if not os.path.exists(TRUST_FOLDER):
            os.makedirs(TRUST_FOLDER)

        if not os.path.exists(self.file):
            with open(self.file, 'w+', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=self.headers)
                writer.writeheader()

        agents = self._get_trust()

        # Check if all agents have a row in trust file
        with open(self.file, 'a', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=self.headers)

            for other_agent in self.agent.other_agents:
                if other_agent["agent_id"] not in [_agent["agent_id"] for _agent in agents]:
                    writer.writerow({'agent_id': other_agent["agent_id"],
                                     'drop_off': TRUST_POINTS['drop_off'][0],
                                     'room_search': TRUST_POINTS['room_search'][0],
                                     'found_goal': TRUST_POINTS['found_goal'][0]})

    # Returns true if we can trust an agent to perform a certain task
    def _can_trust(self, agent_id, action):
        agents = self._get_trust()
        for agent in agents:
            if agent["agent_id"] == agent_id:
                return float(agent[action]) < TRUST_POINTS[action][3]

    # Returns true if we can trust an agent overall
    def _can_trust_overall(self, agent_id):
        agents = self._get_trust()
        for agent in agents:
            if agent["agent_id"] == agent_id:
                avg = (agent['drop_off'] + agent['room_search'] + agent['found_goal']) / 3
                return avg > 0

    # Update trust based on agent_id, action (header) and value
    def _update_trust(self, agent_id, action, value):
        if self.agent.agent_id == agent_id:
            return
        agents = self._get_trust()
        for agent in agents:
            if agent["agent_id"] == agent_id:
                agent[action] = str(float(agent[action]) + value)
                break
        # overwrite existing csv file
        with open(self.file, 'w+', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=self.headers)
            writer.writeheader()
            writer.writerows(agents)

    # Get trust as dictionary objects
    def _get_trust(self):
        agents = []

        with open(self.file, 'r') as file:
            csv_reader = csv.reader(file)
            next(csv_reader)  # skip headers
            for row in csv_reader:
                agent = {}
                for i, column in enumerate(row):
                    agent[self.headers[i]] = column

                agents.append(agent)
        return agents

    def can_trust_drop_off(self, agent_id):
        return self._can_trust(agent_id, "drop_off")

    # Decrease drop off trust
    def decrease_drop_off(self, agent_id):
        self._update_trust(agent_id, "drop_off", TRUST_POINTS["drop_off"][1])

    # Increase drop off trust
    def increase_drop_off(self, agent_id):
        self._update_trust(agent_id, "drop_off", TRUST_POINTS["drop_off"][2])

    def can_trust_found_goal(self, agent_id):
        return self._can_trust(agent_id, "found_goal")

    # Decrease found goal trust
    def decrease_found_goal(self, agent_id):
        self._update_trust(agent_id, "found_goal", TRUST_POINTS["found_goal"][1])

    # Increase found goal trust
    def increase_found_goal(self, agent_id):
        self._update_trust(agent_id, "found_goal", TRUST_POINTS["found_goal"][2])

    def can_trust_room_search(self, agent_id):
        return self._can_trust(agent_id, "room_search")

    # Decrease room search trust
    def decrease_room_search(self, agent_id):
        self._update_trust(agent_id, "room_search", TRUST_POINTS["room_search"][1])

    # Increase room search trust
    def increase_room_search(self, agent_id):
        self._update_trust(agent_id, "room_search", TRUST_POINTS["room_search"][2])
