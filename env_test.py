import ctypes
import numpy as np
import time
import cv2
import gc
import os
import zlib
from sdlarch_rl import make
import pygame
from IPython.display import Audio

# env = make("GranTurismo3-Ps2")
# env = make("NewSuperMarioBros-Wii")
env = make("MarioDash-GC")

obs, info = env.reset()

count = 0
global initial_state
initial_state = None

ar = env.unwrapped.em.get_audio_rate()
print("Frame rate:", env.unwrapped.em.get_frame_rate())
print("Audio rate:", ar)

while True:
    action = np.zeros(16, dtype=np.uint8)

    max_count = 3000
    # press Y button

    action[8] = 1

    # if count == 300:
    #     if not initial_state:
    #         print("Before get_state")
    #         initial_state = env.unwrapped.em.get_state()
    #         print("Before set_state")
    #         # time.sleep(2)
    #         env.unwrapped.em.run()
    #         env.unwrapped.em.set_state(initial_state)
    #         print("After set_state")
    
    # if count % 100 == 0 and count > 0 and count < max_count:
    #     # press start
    #     if count < 1000:
    #         # action[3] = 1
    #         pass
    #     action[0] = 1
    # elif count > max_count:
    #     action = np.zeros(16, dtype=np.uint8)

    #     action[0] = 1

    #     if not initial_state:
    #         initial_state = env.unwrapped.em.get_state()
            
    #     if count > 4000:
    #         env.unwrapped.em.run()
    #         env.unwrapped.em.set_state(initial_state)
    #         print("After set_state")
    #         count = 3001

    obs, rew, done, _, info = env.step(action)

    # address=0x01487780
    # ram = env.unwrapped.em.get_ram()
    # arr = np.frombuffer(ram[address:address+4], dtype=">f4")  # big-endian float32
    # print(arr[0])
    print(info)

    data = env.unwrapped.em.get_audio()

    # print(data)

    # Audio(data, rate=ar)
    # time.sleep(1/60)

    # print(env.get_memory(0x01FA1E7C))

    # print(obs)
    
    obs = cv2.cvtColor(obs, cv2.COLOR_RGB2BGR)
    cv2.imshow("env", obs)
    cv2.waitKey(1)

    count += 1

    # break

    if count % 1000 == 0:
        # env.reset()
        pass

    