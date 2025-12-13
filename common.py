from pathlib import Path

from sdlarch_rl import make
from sdlarch_rl.utils.discretizer import MainDiscretizer
import gymnasium as gym
import numpy as np
from gymnasium.wrappers.frame_stack import FrameStack
import cv2

from sdlarch_rl.utils.utils import (
    FrameSkip,
    TimeLimit,
    ExcludeButtonsWrapper,
    AugmentObservation,
    RandomStateWrapper,
)

from stable_baselines3.common.atari_wrappers import WarpFrame
# from gym.wrappers import FrameStack

class MultiBinaryToDiscreteWrapper(gym.ActionWrapper):
    def __init__(self, env):
        super().__init__(env)

        original_shape = env.action_space.shape[0]
        self.action_space = gym.spaces.Discrete(2 ** original_shape)
        self.original_shape = original_shape
        print(f"Converted MultiBinary({original_shape}) to Discrete({2 ** original_shape})")
        
    def action(self, action):
        binary_action = [int(x) for x in bin(action)[2:].zfill(self.original_shape)]
        return np.array(binary_action, dtype=np.int8)

class WarpFrame(gym.ObservationWrapper):
    def __init__(self, env, width, height):
        super().__init__(env)
        self.width = width
        self.height = height
        self.observation_space = gym.spaces.Box(
            low=0, high=255,
            shape=(height, width),   # whithout extra channel
            dtype=np.uint8
        )

    def observation(self, obs):
        frame = cv2.resize(obs, (self.width, self.height))
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        return frame

class TransposeObs(gym.ObservationWrapper):
    def __init__(self, env):
        super().__init__(env)
        h, w, c = env.observation_space.shape  # H,W,C
        self.observation_space = gym.spaces.Box(
            low=0, high=255,
            shape=(c, h, w),  # C,H,W
            dtype=np.uint8
        )

    def observation(self, obs):
        if isinstance(obs, tuple):
            obs = obs[0]

        obs = np.array(obs)

        if obs.ndim == 2:
            obs = np.expand_dims(obs, axis=-1)

        if obs.ndim == 3:
            return obs.transpose(2, 0, 1)

        raise Exception(f"Invalid format: {obs.shape}")

class EnsureObsWrapper(gym.ObservationWrapper):
    """
    Converts whatever the previous wrappers return into a plain numpy array observation.
    If the env returns a tuple (obs, extra), keep only the first element.
    Also converts PIL images, lists, etc. into numpy arrays.
    """
    def __init__(self, env):
        super().__init__(env)

    def observation(self, obs):
        # If wrapper upstream returned (obs, info) as a tuple, keep only obs
        if isinstance(obs, tuple) or isinstance(obs, list):
            obs = obs[0]
        # If obs is a dict with 'obs' key (rare), extract
        if isinstance(obs, dict) and "obs" in obs:
            obs = obs["obs"]
        # Convert PIL image / list -> numpy array
        if not isinstance(obs, np.ndarray):
            try:
                obs = np.asarray(obs)
            except Exception:
                # last resort: convert to bytes then to array (unlikely)
                obs = np.array(obs)
        return obs

# =====================================================
# Configs
# =====================================================
MAX_STEPS = 4000

# =====================================================
# Create Env (same as SB3)
# =====================================================

def make_env():
    def _init():
        env = make("SuperStreetFighterIV-3DS")
        env = RandomStateWrapper(env, states=[
            'default',
            'ryu_ken_easy_south_asia',
            'ryu_guile_easy_skyscraper',
            'ryu_chunli_easy_asia_south'
        ])

        buttons = env.unwrapped.buttons
        to_exclude = ["START", "SELECT", "L2", "R2", "L3", "R3", "A", "X", "Y"]

        env = ExcludeButtonsWrapper(env, buttons, to_exclude)
        env = AugmentObservation(env)
        env = WarpFrame(env, width=96, height=96)
        env = FrameSkip(env, skip=6, stochastic=True)
        env = TimeLimit(env, max_steps=MAX_STEPS)
        # env = TransposeObs(env)
        # env = EnsureObsWrapper(env)
        env = MultiBinaryToDiscreteWrapper(env)
        env = FrameStack(env, 4)

        return env
    return _init