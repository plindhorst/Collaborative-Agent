import csv
import shutil
from tempfile import NamedTemporaryFile

class Trust:

    def __init__(self, agent):
        self.headers = ['ID', 'value']
        self.file = 'Group58Agent/trust' + str(agent.agent_id) + '.csv'

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

    def _initTrust(self, members):
        with open(self.file, 'w', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=self.headers)
            writer.writeheader()
            for member in members:
                writer.writerow({'ID': member["agent_id"],'value': 0.5})

    def _updateTrust(self, member, value):
        tempfile = NamedTemporaryFile(mode='w', delete=False, newline='')

        with open(self.file, 'r', newline='') as file, tempfile:
            reader = csv.DictReader(file, fieldnames=self.headers)
            writer = csv.DictWriter(tempfile, fieldnames=self.headers)
            for row in reader:
                if row['ID'] == str(member):
                    row['value'] = float(row['value']) + value
                row = {'ID': row['ID'], 'value': row['value']}
                writer.writerow(row)

        shutil.move(tempfile.name, self.file)
