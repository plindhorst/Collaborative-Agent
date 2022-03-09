from typing import final, List, Dict, Final
from bw4t.BW4THumanBrain import HumanBrain

class Human(HumanBrain):
    def __init__(self, settings:Dict[str,object]):
        super().__init__()