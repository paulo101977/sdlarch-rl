
import os
import time
import numpy as np
import gymnasium as gym
import json
import cv2
import importlib.util as import_util
import gc
from _retro import RetroEmulator
import ctypes
import gzip
import re

class SDLEnv(gym.Env):
    """
    PCSX2 environment class

    Provides a Gym interface to classic video games
    """

    metadata = {"render_modes": ["human", "rgb_array"], "video.frames_per_second": 60.0}
    _instance_counter = 0

    def __init__(
        self, 
        gamename: str,
        players = 1,
        env_id=None,
        render_mode="rgb_array",
        env_variables=None,
    ) -> None:

        self.env_id = env_id

        self.em = RetroEmulator()
        self.players = players
        self.gamename = gamename
        self.env_variables = env_variables
        
        gc.collect()

        if not hasattr(self, "spec"):
            self.spec = None

        self.dirname = os.path.dirname(__file__)

        core_ext = "so"
        if os.name == 'nt':
            core_ext = "dll"
        elif os.name == 'posix':
            core_ext = "so"

        emu_name = self._get_emu_name()

        core = os.path.join(self.dirname, "./cores/" + emu_name + core_ext)

        if not os.path.isfile(core):
            raise FileNotFoundError(f"Core file not found: {core}. Please ensure the path is correct.")
        
    

        if not os.path.exists(os.path.join(self.dirname, r"roms", f"{gamename}")):
            raise FileNotFoundError(
                f"Game directory not found: {os.path.join(self.dirname, r'roms', f'{gamename}')}. Please ensure the path is correct."
            )

        game = self._get_rom_file_name()


        if not os.path.isfile(game):
            raise FileNotFoundError(f"ROM file not found: {game}. Please ensure the path is correct.")

        
        # change environment variables
        if self.env_variables:
            for key, value in self.env_variables:
                print(f"Set env variable {key} to {value}")
                self.em.set_variable(key, value)
            
        # starts the emulator main process
        if "dolphin" in core:
            if self.env_id is None or self.env_id == -1:
                raise ValueError("Please provide env_id for dolphin core...")
            print("Starting dolphin core...", core, game, self.env_id)
            self.em.init(core, game, self.env_id)
        else:
            self.em.init(core, game)
        
        self.em.run()

        # TODO: other configurations for other cores
        pcsx2_json = os.path.join(self.dirname, r"cores/ps2/pcsx2.json")

        with open(pcsx2_json) as f:
            pcsx2_button = json.load(f)

        self.buttons = pcsx2_button['buttons']

        meta_path = os.path.join(self.dirname, r"roms", f"{gamename}", f"meta.json")

        if not os.path.isfile(meta_path):
            raise FileNotFoundError(f"Meta file not found: {meta_path}. Please ensure the path is correct.")

        with open(meta_path) as meta:
            self.meta = json.load(meta)

        self.action_space = gym.spaces.MultiBinary(len(self.buttons) * players)

        observation = self._get_observation()

        self.observation_space = gym.spaces.Box(
            low=0,
            high=255,
            shape=observation.shape,
            dtype=np.uint8,
        )
        
        self.img = None

        reward_path = os.path.join(self.dirname, r"roms", f"{gamename}", f"reward.py")

        if not os.path.isfile(reward_path):
            raise FileNotFoundError(f"Reward file not found: {reward_path}. Please ensure the path is correct.")

        # Load the reward function from the specified file
        spec = import_util.spec_from_file_location("dynamic_module", reward_path)
        module = import_util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.reward_fn = module.reward

        self.count = 0

        self.render_mode = render_mode

        self.initial_state = None
        self.load_state()

    def _get_rom_file_name(self) -> str:
        directory_path = os.path.join(self.dirname, r"roms", f"{self.gamename}")
        roms = []

        for root, dirs, files in os.walk(directory_path):
            for filename in files:
                if filename.startswith("rom."):
                    full_path = os.path.join(root, filename)
                    roms.append(full_path)

        if len(roms) == 0:
            raise FileNotFoundError(f"No rom file found in directory: {directory_path}. Please ensure the path is correct.")
        if len(roms) == 1:
            return roms[0]
        raise ValueError(f"Multiple rom files found in directory: {directory_path}. Please ensure there is only one rom file.")
        
    def _get_emu_name(self) -> str:
        gamename = self.gamename.lower()
        print(f"Detected game: {gamename}")
        ext = "_libretro."
        if gamename.endswith("-ps2"):
            return "ps2/pcsx2" + ext
        # dolphin core is used for both wii and gamecube
        if gamename.endswith("-wii") or gamename.endswith("-gc"):
            return "dolphin/dolphin" + ext
        # dreamcast and naomi use the same core (flycast)
        if gamename.endswith("-dc") or gamename.endswith("-nm"):
            return "flycast/flycast" + ext
        # nintendo 64 supports two cores, but we use mupen64plus_next here
        if gamename.endswith("-n64"):
            return "n64/mupen64plus_next" + ext
        if gamename.endswith("-nds"):
            return "nds/desmume" + ext
        raise ValueError(f"Unsupported game type for game: {self.gamename}")

    def load_state(self, statename="default.state"):
        has_state = False
        if not statename.endswith(".state"):
            statename += ".state"

        state_path = os.path.join(self.dirname, r"roms", f"{self.gamename}", statename)
        has_state = os.path.isfile(state_path)
        if not has_state:
            print(f"State file not found: {state_path}. Starting without initial state.")
            return
        

        with gzip.open(
            state_path,
            "rb",
        ) as fh:
            self.initial_state = fh.read()

    def reset(self, seed=None, options=None) -> tuple[np.ndarray, dict]:
        """
        Reset the controller and ensure the PCSX2 emulator is started.
        :return: A tuple containing the next state and additional info.
        """

        super().reset(seed=seed, options=options)

        time.sleep(0.3)

        if self.initial_state:
            self.em.run()
            self.em.set_state(self.initial_state)
        else:
            self.em.reset()

        for p in range(self.players):
            self.em.set_button_mask(np.zeros([len(self.buttons)], np.uint8), p)

        self.em.run()

        observation = self._get_observation()

        self.count = 0

        self.old_info = self._memory_to_info()
        
        return observation, self.old_info

    def _get_memory_value(self, address: int, type: str, ram) -> float:
        """
        Read a value from the specified memory address.
        """
        size = int(re.findall(r'\d+', type)[0])
        return float(np.frombuffer(ram[address:address + size], dtype=type)[0])
    
    def set_buttons(self, buttons: np.ndarray):
        """
        Set the button mapping for the emulator.
        :param buttons: A numpy array representing the button mapping.
        """
        self.buttons = buttons

    def step(self, actions: np.ndarray):
        """
        Execute one time step within the environment.
        :param actions: The actions to be executed.
        :return: A tuple containing the next state, reward, done flag, truncated, and additional info.
        """

        if self.img is None:
            raise RuntimeError("Please call env.reset() before env.step()")

        # TODO: set buttons for all players
        for player in range(self.players):
            self.em.set_button_mask(actions, player)

        self.em.run()

        observation = self._get_observation()

        info = self._memory_to_info()

        reward, done = self._get_reward(self.old_info, info)

        self.old_info = info

        self.count += 1

        if self.render_mode == "human":
            self.render()

        return observation, reward, done, False, info

    def close(self) -> None:
        """
        Close the controller and clean up resources.
        """
        self.em.close()
        pass

    def _get_observation(self) -> np.ndarray:
        height, width = self.em.get_shape()

        buffer = (ctypes.c_uint8 * (width * height * 3))()
        self.em.get_frame(buffer, width, height)
        
        img = np.frombuffer(buffer, dtype=np.uint8)
        img = img.reshape((height, width, 3))[::-1]
        self.img = img
        return self.img

    
    def _memory_to_info(self) -> dict:
        """
        Reads specific memory addresses to extract game-related information.
        :return: A dictionary containing game-related information.
        """

        info = {
        }

        ram = self.em.get_ram()

        for item in self.meta['variables']:
            info[item['name']] = self._get_memory_value(
                int(item['address'], 16), 
                item['type'],
                ram
            )
       
        return info

    def render(self) -> np.ndarray | None:
        if self.render_mode == "human":
            if self.img is None:
                return None

            img = cv2.cvtColor(self.img, cv2.COLOR_RGB2BGR)
            cv2.imshow("env", img)
            cv2.waitKey(1)
            return None
        elif self.render_mode == "rgb_array":
            if self.img is None:
                return None
            return self.img
        return None
    def _get_reward(self, old_info: dict, info: dict) -> tuple[dict, dict]:
        """
        Calculate the reward based on the current game state.
        :param      old_info: The previous state information.
        :param      info: The current state information.
        :return:   A tuple containing the reward and a boolean indicating if the episode is done.
        """
        return self.reward_fn(old_info, info)
        