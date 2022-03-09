from matrx.objects import EnvObject

class CollectableBlock(EnvObject):
    '''
    A block that can be picked up.
    '''
    def __init__(self, location, name, visualize_colour, visualize_shape, block_size):
        super().__init__(location, name, is_traversable=True, is_movable=True,
                         visualize_colour=visualize_colour, visualize_shape=visualize_shape,
                         visualize_size=block_size, class_callable=CollectableBlock,
                         is_drop_zone=False, is_goal_block=False, is_collectable=True)


class GhostBlock(EnvObject):
    '''
    Looks like block but not pickable. Used to indicate dropzones
    '''
    def __init__(self, location, drop_zone_nr, name, visualize_colour, visualize_shape, block_size):
        super().__init__(location, name, is_traversable=True, is_movable=False,
                         visualize_colour=visualize_colour, visualize_shape=visualize_shape,
                         visualize_size=block_size, class_callable=GhostBlock,
                         visualize_depth=85, drop_zone_nr=drop_zone_nr, visualize_opacity=0.5,
                         is_drop_zone=False, is_goal_block=True, is_collectable=False)

