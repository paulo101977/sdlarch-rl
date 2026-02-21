
import gymnasium as gym
import subprocess
import win32gui
import win32ui
from ctypes import windll
import numpy as np
import win32process
import time
import psutil
import vgamepad as vg
import cv2
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor
import torch as th
import torch.nn as nn

TARGET_FPS = 60
FRAME_TIME = 1.0 / TARGET_FPS

class STF6Env(gym.Env):

    def __init__(
        self, 
    ) -> None:

        self.hwnd = self.find_window_by_process_name("StreetFighter6")
        process = None
        self.pid = None

        if not self.hwnd:
            process = subprocess.Popen([
                r"F:\SteamLibrary\steamapps\common\Street Fighter 6\StreetFighter6.exe"
            ])

            self.pid = process.pid

        self.hide_window = False



        # search process ID
        self.wait_start()

        self.gamepad = vg.VDS4Gamepad()

        self.prev_keys = set()

        self.action_space = gym.spaces.MultiBinary(7)

        self.height = 128
        self.width = 228

        self.observation_space = gym.spaces.Box(
            low=0,
            high=255,
            shape=(self.height, self.width, 3),
            dtype=np.uint8,
        )

        self.img = None

    def render(self):
        return self.img

    def reset(self, seed=None, options=None) -> tuple[np.ndarray, dict]:
        super().reset(seed=seed, options=options)

        self.prev_keys = set()

        observation = self._get_observation()

        print("reset obs shape", observation.shape)
        
        return observation, {}

    def step(self, actions: np.ndarray):
        frame_start = time.perf_counter()
        current = set()

        x_value = 0
        y_value = 0

        if not len(actions) > 1:
           actions = actions[0]

        # dpad
        if actions[0] > 0:
            # current.add(vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP)
            current.add(-2)
            y_value = -1.0

        if actions[1]:
            # current.add(vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN)
            current.add(-2)
            y_value = 1.0
  
        if actions[2]:
            # current.add(vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT)
            current.add(-2)
            x_value = -1.0

        if  actions[3]:
            # current.add(vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT)
            current.add(-2)
            x_value = 1.0
  

        # buttons
        if actions[4]:
            current.add(vg.DS4_BUTTONS.DS4_BUTTON_CROSS) # light kick

        if actions[5]:
            # current.add(vg.DS4_BUTTONS.DS4_BUTTON_SHOULDER_RIGHT) # strong punch
            current.add(vg.DS4_BUTTONS.DS4_BUTTON_TRIANGLE) # special

        if actions[6]: # strong kick
            # current.add(vg.DS4_BUTTONS.DS4_BUTTON_TRIGGER_RIGHT ) # right analog trigger
            current.add(vg.DS4_BUTTONS.DS4_BUTTON_CIRCLE) # heavy attack



        for b in current - self.prev_keys:
            if b > 0:
                self.gamepad.press_button(b)
            elif b == -1:
                self.gamepad.right_trigger_float(value_float=1.0)

        if -2 in current:
            self.gamepad.left_joystick_float(x_value_float=x_value, y_value_float=y_value)


        for b in self.prev_keys - current:
            if b > 0:
                self.gamepad.release_button(b)
            elif b == -1:
                self.gamepad.right_trigger_float(value_float=0)
            elif b <= -2:
                self.gamepad.left_joystick_float(x_value_float=0.0, y_value_float=0.0)

        self.gamepad.update()
        self.prev_keys = current.copy()


        observation = self._get_observation()

        elapsed = time.perf_counter() - frame_start
        sleep_time = FRAME_TIME - elapsed
        if sleep_time > 0:
            time.sleep(sleep_time)

        return observation, 0.0, False, False, {}

    def _get_observation(self):
        if self.hwnd == 0:
            raise ValueError("HWND of window not founded")

        left, top, right, bot = win32gui.GetClientRect(self.hwnd)
        width =  right - left
        height = bot - top + 70

        hwndDC = win32gui.GetWindowDC(self.hwnd)
        mfcDC = win32ui.CreateDCFromHandle(hwndDC)
        saveDC = mfcDC.CreateCompatibleDC()

        saveBitMap = win32ui.CreateBitmap()
        saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
        saveDC.SelectObject(saveBitMap)


        result = windll.user32.PrintWindow(self.hwnd, saveDC.GetSafeHdc(), 2)
        
        bmpinfo = saveBitMap.GetInfo()
        bmpstr = saveBitMap.GetBitmapBits(True)
        img = np.frombuffer(bmpstr, dtype='uint8').reshape((bmpinfo['bmHeight'], bmpinfo['bmWidth'], 4))
        
        img_rgb = img[100:, 20:, [2, 1, 0]]

        win32gui.DeleteObject(saveBitMap.GetHandle())
        saveDC.DeleteDC()
        mfcDC.DeleteDC()
        win32gui.ReleaseDC(self.hwnd, hwndDC)

        self.img = img_rgb

        img_rgb = cv2.resize(img_rgb, (self.width, self.height))

        return img_rgb

    def find_window_by_process_name(self, process_name):
        def callback(hwnd, result):
            if win32gui.IsWindowVisible(hwnd):
                tid, win_pid = win32process.GetWindowThreadProcessId(hwnd)
                try:
                    process = psutil.Process(win_pid)
                    if process_name.lower() in process.name().lower():
                        result.append(hwnd)
                except:
                    pass
            return True

        result = []
        win32gui.EnumWindows(callback, result)
        return result[0] if result else None

    def wait_start(self):
        timeout = 120
        start_time = time.time()
        while time.time() - start_time < timeout:
            self.hwnd = self.find_window_by_process_name("StreetFighter6")
            if self.hwnd:
                print(f"Window founded HWND: {self.hwnd}.")
                
                # <<< Hide the emulator window >>>
                if self.hide_window:
                    print("Hide the window...")
                    # SW_HIDE = 0. Hide the window.
                    # win32gui.ShowWindow(hwnd, win32con.SW_HIDE)

                    rect = win32gui.GetWindowRect(self.hwnd)

                    x, y, w, h = rect[0], rect[1], rect[2]-rect[0], rect[3]-rect[1]
                    win32gui.MoveWindow(self.hwnd, -w, -h, w, h, True)
                break
            print("next search...")
            time.sleep(1)


class StreetFighterCNN(BaseFeaturesExtractor):
    def __init__(self, observation_space: gym.spaces.Box, features_dim: int = 256):
        super().__init__(observation_space, features_dim)
        n_input_channels = observation_space.shape[0]  # 4 channels
        
        # self.cnn = nn.Sequential(
        #     nn.Conv2d(n_input_channels, 32, kernel_size=8, stride=4),
        #     nn.ReLU(),
        #     nn.Conv2d(32, 64, kernel_size=4, stride=2),
        #     nn.ReLU(),
        #     nn.Conv2d(64, 64, kernel_size=3, stride=1),
        #     nn.ReLU(),
        #     nn.Flatten(),
        # )

        # self.cnn = nn.Sequential(
        #     nn.Conv2d(n_input_channels, 32, kernel_size=5, stride=2), 
        #     nn.ReLU(),
        #     nn.Conv2d(32, 64, kernel_size=3, stride=2),
        #     nn.ReLU(),
        #     nn.Conv2d(64, 128, kernel_size=3, stride=1),
        #     nn.ReLU(),
        #     nn.Flatten(),
        # )
        

        # with th.no_grad():
        #     # sample = th.zeros(1, n_input_channels, 96, 96)
        #     sample = th.zeros(1, n_input_channels, 64, 64)
        #     n_flatten = self.cnn(sample).shape[1]
        
        # self.linear = nn.Sequential(
        #     nn.Linear(n_flatten, features_dim),
        #     nn.ReLU(),
        # )

        self.cnn = nn.Sequential(
            nn.Conv2d(n_input_channels, 32, kernel_size=3, stride=2, padding=1),
            nn.ReLU(),
            nn.Conv2d(32, 64, kernel_size=3, stride=2, padding=1),
            nn.ReLU(),
            nn.Conv2d(64, 128, kernel_size=3, stride=2, padding=1),
            nn.ReLU(),
            nn.Conv2d(128, 256, kernel_size=3, stride=1, padding=1),
            nn.ReLU(),
            nn.Flatten(),
        )

        with th.no_grad():
            sample = th.zeros(1, n_input_channels, 64, 64)
            n_flatten = self.cnn(sample).shape[1]
        
        self.linear = nn.Sequential(
            nn.Linear(n_flatten, features_dim),
            nn.ReLU(),
            nn.Linear(features_dim, features_dim),
            nn.ReLU(),
        )
    
    def forward(self, observations: th.Tensor) -> th.Tensor:
        observations = observations.float()
        
        if observations.max() > 1.0:
            observations = observations / 255.0
        
        return self.linear(self.cnn(observations))