def reward(previous_state: dict, state: dict):
    """
    Calculate the reward based on the current and next state.
    
    Args:
        previous_state (dict): The oldest state of the environment.
        state (dict): The current state of the environment.
    
    Returns:
        tuple: A tuple containing the reward and a boolean indicating if the episode is done.
    """
    reward = 0.0
    done = False

    # velocity, position, current_lap, max_lap, wrong_way

    if state is None or previous_state is None:
        return reward, done

    current_position = state.get('position', 6)
    collision = state.get('collision', 0)
    outside_percentage = state.get('outside_percentage', 0.0)
    previous_position = previous_state.get('position', 6)
    max_velocity = 130.0

    # car start in 6th position
    # The car has moved forward
    # if current_position > 0:
    #     reward += 1.0/6 * (6 - current_position)  # Reward for moving up in position
    
    if current_position < previous_position:
        reward += 0.02  # Reward for moving forward in position
    elif current_position > previous_position:
        reward -= 0.03 # Penalty for moving backward in position

    # Penalty for going the wrong way
    if state['wrong_way']:
        reward -= 1.0 
    else:
    # Reward for moving forward proportional to velocity and inversely proportional to position
        if state['velocity'] > 0:
            reward += (0.02 * (state['velocity'] / max_velocity)) / current_position
    # Penalty for not moving
        else:
            reward -= 0.2

    # Penalty for collisions or going outside the track
    if collision > 0 or outside_percentage > 0:
        reward -= 0.02

    # Bonus for completing the race proportional to position
    if state['current_lap'] > 0 and state['max_lap'] > 0 and state['current_lap'] > state['max_lap'] \
        and state['current_lap'] < 5 and state['max_lap'] < 5 :
        reward += 1 / current_position
        done = True

    # Ensure the reward is within the range [-1.0, 1.0]
    if reward < -1.0:
        reward = -1.0
    if reward > 1.0:
        reward = 1.0

    return reward, done