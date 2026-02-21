
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

TARGET_FPS = 60
FRAME_TIME = 1.0 / TARGET_FPS

class STF6Env(gym.Env):

    def __init__(
        self, 
    ) -> None:
        process = subprocess.Popen([
            r"F:\SteamLibrary\steamapps\common\Street Fighter 6\StreetFighter6.exe"
        ])

        self.pid = process.pid

        self.hide_window = True

        self.hwnd = None

        # search process ID
        self.wait_start()

        self.gamepad = vg.VX360Gamepad()

        self.prev_keys = set()

        self.action_space = gym.spaces.MultiBinary(16)

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

        if not len(actions) > 1:
           actions = actions[0]

        # dpad
        if actions[4] > 0:
            current.add(vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP) # 4

        if actions[5]:
            current.add(vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN) # 5
  
        if actions[6]:
            current.add(vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT) # 6

        if  actions[7]:
            current.add(vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT) # 7
  

        # buttons
        if actions[8]:
            current.add(vg.XUSB_BUTTON.XUSB_GAMEPAD_A) # light kick # 8

        if actions[10]:
            current.add(vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER) # strong punch # 10

        if actions[11]: # strong kick # 11
            current.add(-1) # right analog trigger


        for b in current - self.prev_keys:
            if b > 0:
                self.gamepad.press_button(b)
            elif b < 0:
                self.gamepad.right_trigger_float(value_float=1.0)


        for b in self.prev_keys - current:
            if b > 0:
                self.gamepad.release_button(b)
            elif b < 0:
                self.gamepad.right_trigger_float(value_float=0)

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
        width = right - left
        height = bot - top + 100

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
        
        img_rgb = img[100:, :, [2, 1, 0]]

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
            # hwnd = _find_window_for_pid(pid)
            self.hwnd = self.find_window_by_process_name("StreetFighter6")
            if self.hwnd:
                print(f"Window founded HWND: {self.hwnd}.")
                
                # <<< Hide the emulator window >>>
                # if self.hide_window:
                #     print("Hide the window...")
                #     # SW_HIDE = 0. Hide the window.
                #     # win32gui.ShowWindow(hwnd, win32con.SW_HIDE)

                #     rect = win32gui.GetWindowRect(self.hwnd)

                #     x, y, w, h = rect[0], rect[1], rect[2]-rect[0], rect[3]-rect[1]
                #     win32gui.MoveWindow(self.hwnd, -w, -h, w, h, True)
                break
            print("next search...")
            time.sleep(1)