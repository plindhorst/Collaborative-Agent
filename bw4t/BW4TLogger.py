import numpy as np
from matrx.logger.logger import GridWorldLogger
from matrx.grid_world import GridWorld


class BW4TLogger(GridWorldLogger):
    '''
    Logs the things we need for bw4t:
    agent actions, world-completed info, messages info
    '''
    def __init__(self, save_path="", file_name_prefix="", file_extension=".csv", delimeter=";"):
        super().__init__(save_path=save_path, file_name=file_name_prefix, file_extension=file_extension,
                         delimiter=delimeter, log_strategy=1)

    def log(self, grid_world:GridWorld, agent_data):
        # So agent_data is a dictionary of shape: {<agent id>: <result from agent's get_log_data>, ...}
        # Knowing that it contains only a boolean, a number of messages, and the agent's name lets format it in some
        # nice columns
        data = {}
        # simulation goal must be our CollectionGoal
        data['done'] = grid_world.simulation_goal.isBlocksPlaced(grid_world)
        for agent_id, agent_body in grid_world.registered_agents.items():
            data[agent_id+'_acts'] = agent_body.current_action

        gwmm = grid_world.message_manager
        t = grid_world.current_nr_ticks-1
        for agent_id, agent_body in grid_world.registered_agents.items():
            data[agent_id+'_mssg']=0
            for i in range(0,t):
                if i in gwmm.preprocessed_messages.keys():
                    for mssg in gwmm.preprocessed_messages[i]:
                        if mssg.from_id==agent_id:
                            data[agent_id+'_mssg']+=1
                            break
        return data

    # workaround for issue matrx267
    def getFileName(self):
        '''
        @return the log filename written by this logger
        '''
        return self._GridWorldLogger__file_name
    