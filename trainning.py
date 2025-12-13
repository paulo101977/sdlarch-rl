import os
import time
from pathlib import Path
import numpy as np
import torch
import torch.nn as nn
import torch.distributions as td
import gymnasium as gym

from common import make_env

from stable_baselines3.common.atari_wrappers import WarpFrame
from tianshou.env import SubprocVectorEnv, DummyVectorEnv

from tianshou.data import Collector
from tianshou.policy import PPOPolicy
from tianshou.trainer import OnpolicyTrainer

# from tianshou.env import AsyncVectorEnv
from tianshou.data import AsyncCollector, VectorReplayBuffer
from tianshou.trainer import OffpolicyTrainer

from tianshou.utils import TensorboardLogger
from torch.utils.tensorboard import SummaryWriter

from sdlarch_rl.utils.utils import (
    get_latest_model,
)

# =====================================================
# Configs
# =====================================================

NUM_ENV = 4
SAVE_DIR = Path("./model-tianshou-sf4")
TENSORBOARD = "./tensorboard-tianshousf4"
TOTAL_TIMESTEP_NUMB = 500_000_000
MAX_STEPS = 4000
CHECK_FREQ_NUMB = 5000

ENT_COEF = 0.001
n_steps = 2048
batch_size = 64 * NUM_ENV

writer = SummaryWriter(TENSORBOARD)
logger = TensorboardLogger(writer)
SAVE_DIR.mkdir(exist_ok=True)

global_step = 0


# venv = AsyncVectorEnv([make_env() for _ in range(NUM_ENV)])
# test_env = AsyncVectorEnv([make_env()])


# -----------------------------
# Backbone + Actor + Critic
# -----------------------------
class CNNBackbone(nn.Module):
    def __init__(self):
        super().__init__()
        # note: input shape expected N,H,W,C (NHWC) from your VecFrameStack wrapper
        # we'll permute to NCHW inside forward of actor/critic
        self.conv = nn.Sequential(
            nn.Conv2d(4, 32, 8, stride=4), nn.ReLU(),
            nn.Conv2d(32, 64, 4, stride=2), nn.ReLU(),
            nn.Conv2d(64, 64, 3, stride=1), nn.ReLU(),
            nn.Flatten()
        )
        # compute flattened feature dim
        with torch.no_grad():
            dummy = torch.zeros(1, 4, 96, 96)  # NCHW for conv
            feat = self.conv(dummy)
            self.feat_dim = feat.shape[1]

    def forward(self, obs_nchw):
        # obs_nchw expected NCHW already
        return self.conv(obs_nchw)


class ActorNet(nn.Module):
    def __init__(self, backbone: CNNBackbone, action_dim: int):
        super().__init__()
        self.backbone = backbone
        self.logits = nn.Linear(self.backbone.feat_dim, action_dim)

    def forward(self, obs, state=None, info=None):
        # Tianshou passes obs as NHWC by default in your setup,
        # so convert to NCHW here (handles numpy/tensor shapes)
        if isinstance(obs, np.ndarray):
            obs_t = torch.as_tensor(obs, dtype=torch.float32)
        else:
            obs_t = obs.float()
        if obs_t.ndim == 3:
            obs_t = obs_t.unsqueeze(0)
        feat = self.backbone(obs_t)
        logits = self.logits(feat)  # shape [B, action_dim]
        return logits, state


class CriticNet(nn.Module):
    def __init__(self, backbone: CNNBackbone):
        super().__init__()
        self.backbone = backbone
        self.v = nn.Linear(self.backbone.feat_dim, 1)

    def forward(self, obs, state=None, info=None):
        if isinstance(obs, np.ndarray):
            obs_t = torch.as_tensor(obs, dtype=torch.float32)
        else:
            obs_t = obs.float()

        if obs_t.ndim == 3:
            obs_t = obs_t.unsqueeze(0)
        feat = self.backbone(obs_t)
        value = self.v(feat).squeeze(-1)  # shape [B]
        return value, state

def multibinary_dist_fn(logits):
    return td.Independent(td.Bernoulli(logits=logits), 1)

if __name__ == "__main__":
    # =====================================================
    # VecEnv
    # =====================================================

    if NUM_ENV == 1:
        venv = DummyVectorEnv([make_env()])
    else:
        venv = SubprocVectorEnv([make_env() for _ in range(NUM_ENV)])

    # env = venv._env_fns[0]()

    # obs, info = env.reset()
    # print("OBS:", type(obs), getattr(obs, 'shape', None))

    test_env = DummyVectorEnv([make_env()])

    # -----------------------------
    # instantiate nets and policy
    # -----------------------------
    # detect action dim from action_space (assume Discrete or MultiBinary -> map to discrete count)
    if isinstance(venv.action_space, list): 
        action_space = venv.action_space[0] 
    else: 
        action_space = venv.action_space


    if hasattr(action_space, "n"):
        action_dim = int(action_space.n)
    elif hasattr(action_space, "shape"):
        # fallback for binary/multi-binary -> convert to number of discrete combos if you used discretizer
        # but here we just use action_space.n when discretizer applied. If not, convert externally.
        action_dim = int(np.prod(action_space.shape))
    else:
        raise RuntimeError("Cannot infer action dim from action_space")

    if isinstance(action_space, gym.spaces.Discrete):
        action_dim = action_space.n
        dist_fn = lambda logits: torch.distributions.Categorical(logits=logits)
        print(f"Using Discrete action space with {action_dim} actions")
    elif isinstance(action_space, gym.spaces.MultiBinary):
        action_dim = action_space.shape[0]
        dist_fn = multibinary_dist_fn
        print(f"Using MultiBinary action space with {action_dim} dimensions")
    else:
        raise RuntimeError(f"Unsupported action space: {type(action_space)}")

    backbone = CNNBackbone()
    actor = ActorNet(backbone, action_dim)
    critic = CriticNet(backbone)

    # optimizer should include both actor + critic params
    optim = torch.optim.Adam(list(actor.parameters()) + list(critic.parameters()), lr=2.5e-4)

    # now create PPOPolicy with actor and critic modules (these accept state/info)
    policy = PPOPolicy(
        actor=actor,
        critic=critic,
        optim=optim,
        dist_fn=dist_fn,
        action_space=action_space,
        discount_factor=0.99,
        gae_lambda=0.95,
        max_grad_norm=0.5,
        vf_coef=0.5,
        ent_coef=ENT_COEF,
        eps_clip=0.2,
        advantage_normalization=True,
        recompute_advantage=False,
        action_scaling=False,
        action_bound_method=None,
    )

    # =====================================================
    # Collector
    # =====================================================

    buffer = VectorReplayBuffer(n_steps * NUM_ENV, NUM_ENV, stack_num=4)

    train_collector = AsyncCollector(
        policy,
        venv,
        buffer,
        exploration_noise=True,
    )

    test_collector = Collector(
        policy,
        test_env,
        VectorReplayBuffer(10000, 1, stack_num=4),
        exploration_noise=False
    )


    # =====================================================
    # Load previous checkpoint
    # =====================================================

    latest_model_path = get_latest_model(SAVE_DIR)

    if latest_model_path:
        print(f"Loading checkpoint: {latest_model_path}")
        policy.load_state_dict(torch.load(latest_model_path))
    else:
        print("No previous checkpoint found — starting fresh.")


    # =====================================================
    # Training Loop (Tianshou version)
    # =====================================================

    def save_best_fn(policy):
        save_path = SAVE_DIR / f"best_model_{global_step}.pth"
        torch.save(policy.state_dict(), save_path)
        print("Saved:", save_path)

    def train_fn(epoch, env_step):
        global global_step
        global_step = env_step


    trainer = OnpolicyTrainer(
        policy=policy,
        train_collector=train_collector,
        test_collector=test_collector,
        max_epoch=int(TOTAL_TIMESTEP_NUMB / (n_steps * NUM_ENV)),
        step_per_epoch=n_steps * NUM_ENV,
        step_per_collect=n_steps,
        repeat_per_collect=10,
        episode_per_test=2,
        batch_size=batch_size,
        train_fn=train_fn,
        save_best_fn=save_best_fn,
        logger=logger,
    )

    # trainer = OffpolicyTrainer(
    #     policy=policy,
    #     buffer=buffer,
    #     train_collector=train_collector,
    #     test_collector=test_collector,
    #     max_epoch=int(TOTAL_TIMESTEP_NUMB / (n_steps * NUM_ENV)),
    #     step_per_epoch=n_steps * NUM_ENV,
    #     step_per_collect=0,         # collect continuoes
    #     update_per_step=1,          # PPO stable
    #     episode_per_test=2,
    #     batch_size=batch_size,
    #     train_fn=lambda epoch, env_step: buffer.clear(),   # keep on-policy
    #     save_best_fn=save_best_fn,
    #     logger=logger,
    # )

    result = trainer.run()


    # =====================================================
    # Save final
    # =====================================================

    torch.save(policy.state_dict(), "final_sf4_policy.pth")
    venv.close()
