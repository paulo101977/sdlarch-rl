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

    if state is None or previous_state is None:
        return reward, done

    # --- 1. State Variables ---
    velocity = state.get('velocity', 0)
    current_pos = state.get('position', 6)
    prev_pos = previous_state.get('position', 6)
    collision = state.get('collision', 0)
    outside = state.get('outside_percentage', 0)
    max_velocity = 130.0
    prev_lap = previous_state.get('current_lap', 0)

    # --- 2. Velocity bonus
    vel_ratio = velocity / max_velocity
    reward += vel_ratio * 0.5

    if velocity < 10:
        reward -= 0.3

    # --- 3. Race Progress (Positioning)---
    if current_pos < prev_pos:
        reward += 0.5  
    elif current_pos > prev_pos:
        reward -= 0.4

    # --- 4. penality wrong direction ---
    if state['wrong_way']:
        reward -= 0.8
        # done = True  # Optional
    
    # Exiting area penality
    if collision > 0 or outside > 0:
        reward -= 0.15

    # --- 5. Finishing Lap Bonus ---
    # if state['current_lap'] > prev_lap and state['current_lap'] > 1 and state['max_lap'] > 0:
    #     reward += 1.0
        # done = True

    # --- 5. Finishing Bonus ---
    # if state['current_lap'] > state['max_lap'] and state['max_lap'] > 0:
    #     reward += 1.0
    #     done = True

    # --- 6. Clipping
    reward = max(min(reward, 1.0), -1.0)

    return reward, done