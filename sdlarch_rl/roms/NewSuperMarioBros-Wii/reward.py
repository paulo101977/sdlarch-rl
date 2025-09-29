def reward(previous_state: dict, state: dict) -> dict[float, bool]:
    """
    Calculate the reward based on the current and next state.
    
    Args:
        previous_state (dict): The oldest state of the environment.
        state (dict): The current state of the environment.
    
    Returns:
        tuple: A tuple containing the float reward and a boolean indicating if the episode is done.
    """
    reward = 0.0
    done = False
    
    if previous_state is None or state is None:
        return reward, done

    # TODO: Implement specific reward logic for New Super Mario Bros
    # print(previous_state, state)
    max_speed = 19
    max_x = 6681.0

    x = state.get("x", 0)
    lives = state.get("lives", 0)
    c_time = state.get("time", 0)
    old_x = previous_state.get("x", 0)
    old_lives = previous_state.get("lives", 0)
    g_time = 500 # max global time
    max_time = 43 # target time to finish the level (or less)

    # reward based on speed
    if x > old_x:
        speed = x - old_x
        reward += 0.02 * (speed / max_speed) # this value tends to 1 multiplied by the maximum reward
    else:
        reward -= 0.02


    if lives < old_lives:
        reward -= 1.0
        done = True

    # finish / Applies time factor to reward (this value tends to 1)
    if x > max_x:
        time_factor =  max_time / (g_time - c_time)
        reward += 1.0 * time_factor
        done = True


    if reward > 1:
        reward = 1
    if reward < -1:
        reward = -1

    return reward, done