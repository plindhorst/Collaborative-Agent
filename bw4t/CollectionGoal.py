import numpy as np # type: ignore

from matrx.goals import WorldGoal # type: ignore
from matrx.grid_world import GridWorld # type: ignore
from matrx.objects.env_object import EnvObject # type: ignore


class CollectionGoal(WorldGoal):
    '''
    The goal for BW4T world (the simulator), so determines
    when the simulator should stop.
    '''
    def __init__(self, max_nr_ticks:int):
        '''
        @param max_nr_ticks the max number of ticks to be used for this task
        '''
        super().__init__()
        self.max_nr_ticks = max_nr_ticks

        # A dictionary of all drop locations. The keys is the drop zone number, the value another dict.
        # This dictionary contains as key the rank of the to be collected object and as value the location
        # of where it should be dropped, the shape and colour of the block, and the tick number the correct
        # block was delivered. The rank and tick number is there so we can check if objects are dropped in
        # the right order.
        self.__drop_off:dict = {}

        # We also track the progress
        self.__progress = 0

    #override
    def goal_reached(self, grid_world: GridWorld):
        if grid_world.current_nr_ticks >= self.max_nr_ticks:
            return True
        return self.isBlocksPlaced(grid_world)

    def isBlocksPlaced(self, grid_world:GridWorld):
        '''
        @return true if all blocks have been placed in right order
        '''

        if self.__drop_off =={}:  # find all drop off locations, its tile ID's and goal blocks
            self.__find_drop_off_locations(grid_world)

        # Go through each drop zone, and check if the blocks are there in the right order
        is_satisfied, progress = self.__check_completion(grid_world)

        # Progress in percentage
        self.__progress = progress / sum([len(goal_blocks)\
            for goal_blocks in self.__drop_off.values()])
        return is_satisfied

    def __find_drop_off_locations(self, grid_world:GridWorld):

        goal_blocks = {}  # dict with as key the zone nr and values list of ghostly goal blocks
        all_objs = grid_world.environment_objects
        for obj_id, obj in all_objs.items():  # go through all objects
            if "drop_zone_nr" in obj.properties.keys():  # check if the object is part of a drop zone
                zone_nr = obj.properties["drop_zone_nr"]  # obtain the zone number
                if obj.properties["is_goal_block"]:  # check if the object is a ghostly goal block
                    if zone_nr in goal_blocks.keys():  # create or add to the list
                        goal_blocks[zone_nr].append(obj)
                    else:
                        goal_blocks[zone_nr] = [obj]

        self.__drop_off:dict = {}
        for zone_nr in goal_blocks.keys():  # go through all drop of zones and fill the drop_off dict
            # Instantiate the zone's dict.
            self.__drop_off[zone_nr] = {}

            # Obtain the zone's goal blocks.
            blocks = goal_blocks[zone_nr].copy()

            # The number of blocks is the maximum the max number blocks to collect for this zone.
            max_rank = len(blocks)

            # Find the 'bottom' location
            bottom_loc = (-np.inf, -np.inf)
            for block in blocks:
                if block.location[1] > bottom_loc[1]:
                    bottom_loc = block.location

            # Now loop through blocks lists and add them to their appropriate ranks
            for rank in range(max_rank):
                loc = (bottom_loc[0], bottom_loc[1] - rank)

                # find the block at that location
                for block in blocks:
                    if block.location == loc:
                        # Add to self.drop_off
                        self.__drop_off[zone_nr][rank] = [loc, block.visualize_shape, block.visualize_colour, None]

    def __check_completion(self, grid_world:GridWorld):
        # Get the current tick number
        curr_tick = grid_world.current_nr_ticks

        # loop through all zones, check the blocks and set the tick if satisfied
        for zone_nr, goal_blocks in self.__drop_off.items():
            # Go through all ranks of this drop off zone
            for rank, block_data in goal_blocks.items():
                loc = block_data[0]  # the location, needed to find blocks here
                shape = block_data[1]  # the desired shape
                colour = block_data[2]  # the desired colour
                tick = block_data[3]

                # Retrieve all objects, the object ids at the location and obtain all BW4T Blocks from it
                all_objs = grid_world.environment_objects
                obj_ids = grid_world.get_objects_in_range(loc, object_type=EnvObject, sense_range=0)
                blocks = [all_objs[obj_id] for obj_id in obj_ids
                          if obj_id in all_objs.keys() and "is_collectable" in all_objs[obj_id].properties.keys()]
                blocks = [b for b in blocks if b.properties["is_collectable"]]

                # Check if there is a block, and if so if it is the right one and the tick is not yet set, then set the
                # current tick.
                if len(blocks) > 0 and blocks[0].visualize_shape == shape and blocks[0].visualize_colour == colour and \
                        tick is None:
                    self.__drop_off[zone_nr][rank][3] = curr_tick
                # if there is no block, reset its tick to None
                elif len(blocks) == 0:
                    self.__drop_off[zone_nr][rank][3] = None

        # Now check if all blocks are collected in the right order
        is_satisfied = True
        progress = 0
        for zone_nr, goal_blocks in self.__drop_off.items():
            zone_satisfied = True
            ticks = [goal_blocks[r][3] for r in range(len(goal_blocks))]  # list of ticks in rank order

            # check if all ticks are increasing
            for idx, tick in enumerate(ticks[:-1]):
                if tick is None or ticks[idx+1] is None or not tick < ticks[idx+1]:
                    progress += (idx+1) if tick is not None else idx  # increment progress
                    zone_satisfied = False  # zone is not complete or ordered
                    break  # break this loop

            # if all ticks were increasing, check if the last tick is set and set progress to full for this zone
            if zone_satisfied and ticks[-1] is not None:
                progress += len(goal_blocks)

            # update our satisfied boolean
            is_satisfied = is_satisfied and zone_satisfied

        return is_satisfied, progress