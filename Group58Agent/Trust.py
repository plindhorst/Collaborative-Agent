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