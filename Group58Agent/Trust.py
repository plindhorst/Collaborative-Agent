import csv
import os
import shutil
from tempfile import NamedTemporaryFile

class Trust:
    def __init__(self, agent):
        self.headers = ['ID', 'value']
        self.file = 'Group58Agent/trust' + str(agent.agent_id) + '.csv'

    # Initialize file if not existent
    def _initTrust(self, members):
        if os.path.exists(self.file):
            # If file not empty dont recreate
            with open(self.file, 'r') as file:
                csv_dict = [row for row in csv.DictReader(file)]
                if len(csv_dict) != 0:
                    return

        # Initialise file
        with open(self.file, 'w', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=self.headers)
            writer.writeheader()
            for member in members:
                writer.writerow({'ID': member["agent_id"],'value': 0.5})

    # Update trust based on value
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
