import json

from matrx.messages import Message


def can_move(agent, my_action):
    """
    Process incoming messages and check if we can perform an action without duplicates
    Returns True if we can continue with our initial task
    """
    if not agent.started and len(agent.received_messages) > 0:
        agent.started = True
    if not agent.started:
        return False
    for msg in agent.received_messages:
        message = json.loads(msg.content)
        if message["action"] == "MOVE_TO_ROOM":
            agent.received_messages.remove(msg)
            # Check if we have the same action as another agent
            if message["action"] == "MOVE_TO_ROOM" and my_action is not None and my_action[
                "action"] == "MOVE_TO_ROOM" and my_action["room_name"] == message[
                "room_name"]:
                # Choose other agent if he has higher index
                if agent.team_members.index(my_action["agent_name"]) > agent.team_members.index(
                        message["agent_name"]):
                    if agent.visited.get(message["room_name"]) is None:
                        agent.visited[message["room_name"]] = []
                    return False
            else:
                if agent.visited.get(message["room_name"]) is None:
                    agent.visited[message["room_name"]] = []
    return True


def can_grab(agent, my_action):
    """
    check if no one else is grabbing this block
    """
    for msg in agent.received_messages:
        message = json.loads(msg.content)
        if message["action"] == "DROP_GOAL" and my_action["action"] == "DROP_GOAL" and my_action["location"] == message[
            "location"]:
            agent.received_messages.remove(msg)
            # TODO: make work for more than 2 agents
            return message["distance"] > my_action["distance"]
    return True


def update_map_info(agent):
    for msg in agent.received_messages:
        message = json.loads(msg.content)
        if message["action"] == "MOVE_TO_ROOM":
            if agent.visited.get(message["room_name"]) is None:
                agent.visited[message["room_name"]] = []
        elif message["action"] == "SEARCH_ROOM":
            agent.received_messages.remove(msg)
            agent.visited[message["room_name"]] = message["room_content"]
        elif message["action"] == "GRABBED_BLOCK":
            agent.received_messages.remove(msg)
            agent.goal.pop(0)


def send_msg(agent, msg, sender):
    msg = Message(content=msg, from_id=sender)
    if msg.content not in agent.received_messages:
        agent.send_message(msg)


class MessageHandler:
    pass
