def reward(prev: dict, cur: dict):
    """
    Calculate the reward based on the current and next state.
    
    Args:
        prev (dict): The oldest state of the environment.
        cur (dict): The current state of the environment.
    
    Returns:
        tuple: A tuple containing the reward and a boolean indicating if the episode is done.
    """
    if not prev or not cur:
        return 0.0, False

    reward = 0.0

    # current HP
    p1 = cur["player1"]
    p2 = cur["player2"]
    
    # previus HP
    p1_prev = prev["player1"]
    p2_prev = prev["player2"]

    # --- damage taken ---
    damage_taken = p1_prev - p1
    # if damage_taken > 0:
    if damage_taken > 1.4: # ignore defense move
        reward -= damage_taken * 0.1

    # --- damage done ---
    damage_done = p2_prev - p2
    if damage_done > 0:
        reward += damage_done * 0.1

    # --- win / lose ---
    done = False
    if p1 == 0:
        reward -= 1
        done = True
    if p2 == 0:
        reward += 1
        done = True

    # --- Timeout ---
    if cur["time"] == 0 and not done:
        if p1 < p2:
            reward -= 0.5
        else:
            reward += 0.5
        done = True

    if reward > 1:
        reward = 1
    if reward < -1:
        reward = -1

    return reward, done