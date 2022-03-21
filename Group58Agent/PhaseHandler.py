import enum


class PhaseHandler:
    def __init__(self, agent):
        self.agent = agent

    # return true if phase is equal to current phase
    def phase_is(self, phase):
        return self.agent.phase == phase


class Phase(enum.Enum):
    CHOOSE_ROOM = 1
    GO_TO_ROOM = 2
    OPEN_DOOR = 3
    SEARCH_ROOM = 4
    CHOOSE_GOAL = 5
    GRAB_GOAL = 6
    DROP_GOAL = 7
    DONE = 8
