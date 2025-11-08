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
import pygame
from typing import List, Dict

class SDLEnv(gym.Env):
    """
    SDL environment class

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
        env_variables:List[Dict[str, str]] =None,
        statename=None,
    ) -> None:

        self.env_id = env_id

        self.em = RetroEmulator()
        self.players = players
        self.gamename = gamename
        self.env_variables = env_variables

        # workaround to prevent frame freeze
        self._last_frames = []  # frame buffer
        self._max_identical_frames = 30
        
        # try force gc free resources
        gc.collect()
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
            for item in self.env_variables:
                keys = item.keys()

                for key in keys:
                    value = item[key]
                    print(f"Set env variable {key} to {value}")
                    self.em.set_variable(key, value)

        # We need flip the image on desmume
        self.invert_img = "desmume" in core
            
        # starts the emulator main process
        if "dolphin" in core:
            if self.env_id is None or self.env_id == -1:
                raise ValueError("Please provide env_id for dolphin core...")
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

        self._pygame_initialized = False
        self._screen = None
        self._clock = None
        
        if self.render_mode == "human":
            self._init_pygame()

        self.initial_state = None
        self.statename = statename
        self.load_state(self.statename)

    def _init_pygame(self):
        """Initialize Pygame for rendering"""
        try:
            pygame.init()
            # get the current shape of obs
            height, width = self.em.get_shape()
            
            # Limit image size
            max_width = 1200
            max_height = 800
            
            # calculate aspect ration
            aspect_ratio = width / height
            if width > max_width:
                width = max_width
                height = int(width / aspect_ratio)
            if height > max_height:
                height = max_height
                width = int(height * aspect_ratio)
            
            self._screen = pygame.display.set_mode((width, height))
            pygame.display.set_caption(f"SDLEnv - {self.gamename}")
            self._clock = pygame.time.Clock()
            self._pygame_initialized = True
            print(f"🎮 Pygame initialized: {width}x{height}")
        except Exception as e:
            print(f"⚠️ Failed to initialize Pygame: {e}")
            self._pygame_initialized = False

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
        ext = "_libretro."
        if gamename.endswith("-ps2"):
            return "ps2/pcsx2" + ext
        if gamename.endswith("-3ds"):
            return "3ds/citra" + ext
        if gamename.endswith("-snes"):
            return "snes/snes9x" + ext
        if gamename.endswith("-ps1"):
            return "ps1/pcsx_rearmed" + ext
        # dolphin core is used for both wii and gamecube
        if gamename.endswith("-wii") or gamename.endswith("-gc"):
            return "dolphin/dolphin" + ext
            # return "dolphin/dolphin_new" + ext
        # dreamcast and naomi use the same core (flycast)
        if gamename.endswith("-dc") or gamename.endswith("-nm"):
            return "flycast/flycast" + ext
        # nintendo 64 supports two cores, but we use mupen64plus_next here
        if gamename.endswith("-n64"):
            return "n64/mupen64plus_next" + ext
        if gamename.endswith("-nds"):
            return "nds/desmume" + ext
        if gamename.endswith("-psp"):
            return "psp/ppsspp" + ext
        raise ValueError(f"Unsupported game type for game: {self.gamename}")

    def load_state(self, statename="default.state"):
        """
        Load an initial state
        :param   statename: The state to be loaded.
        """
        has_state = False

        if statename is None:
            print("statename is None setting to default state")
            statename="default.state"

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

        if hasattr(self, '_last_frames'):
            self._last_frames.clear()

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

    def _detect_frozen_frame(self, new_frame: np.ndarray):
        """Fastest frame frozen detection"""
        if not hasattr(self, '_last_frame_sample'):
            # 100x more fast frozen frame detection
            h, w = new_frame.shape[:2]
            sample_h, sample_w = h // 10, w // 10  # 1% of pixels
            self._last_frame_sample = new_frame[::10, ::10].copy()
            self._identical_count = 0
            return False
        
        # 1% of frame sample
        current_sample = new_frame[::10, ::10]
        
        # fast compare frames
        if np.array_equal(current_sample, self._last_frame_sample):
            self._identical_count += 1
        else:
            self._identical_count = 0
            self._last_frame_sample = current_sample.copy()
        
        # Threshold for trainning
        if self._identical_count > 300:
            self._last_frames.clear()
            return True
        
        return False

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

        # TODO fix the workaround
        if self._detect_frozen_frame(self.img):
            print("Frozen detected\n")
            # self.em.reset()
            return observation, 0, True, False, self.old_info

        if self.render_mode == "human":
            self.render()

        return observation, reward, done, False, info

    def close(self) -> None:
        """
        Close the controller and clean up resources.
        """
        try:
            if hasattr(self, 'em') and self.em is not None:
                self.em.close()
                self.em = None

            if self._pygame_initialized:
                pygame.quit()
                self._pygame_initialized = False
                self._screen = None
                self._clock = None

        except Exception as e:
            print(f"Error during close: {e}")
        finally:
            # Force garbage collection
            # try force gc free resources
            gc.collect()
            gc.collect()

    def _get_observation(self) -> np.ndarray:
        height, width = self.em.get_shape()

        buffer = (ctypes.c_uint8 * (width * height * 3))()
        self.em.get_frame(buffer, width, height)
        
        img = np.frombuffer(buffer, dtype=np.uint8)
        img = img.reshape((height, width, 3))[::-1]

        if self.meta and 'crop' in self.meta:
            crop = self.meta['crop']
            img = img[crop['top']:height - crop['bottom'], crop['left']:width - crop['right'], :]

        # flip imaga
        if self.invert_img:
            img = img[::-1, :, :]

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
        if self._pygame_initialized and self._screen is not None:
            try:
                # Process event of pygame
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        print("Window closed by user")
                        raise KeyboardInterrupt("User closed window")
                    elif event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_ESCAPE:
                            print("Escape pressed by user")
                            raise KeyboardInterrupt("User pressed ESC")
                
                img_rgb = np.ascontiguousarray(self.img)
                pygame_surface = pygame.surfarray.make_surface(img_rgb.swapaxes(0, 1))
                
                # resize screen
                window_width, window_height = self._screen.get_size()
                img_height, img_width = img_rgb.shape[:2]
                
                if img_width != window_width or img_height != window_height:
                    pygame_surface = pygame.transform.scale(pygame_surface, (window_width, window_height))
                
                # draw on screen
                self._screen.blit(pygame_surface, (0, 0))
                pygame.display.flip()
                
                # fps
                # self._clock.tick(60)
                
            except Exception as e:
                print(f"Pygame render error: {e}")
                # Try render a Pygame
                try:
                    self._init_pygame()
                except:
                    self._pygame_initialized = False
        
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
        