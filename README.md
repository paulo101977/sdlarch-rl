# sdlarch-rl

This is a fork of sdlarch that aims to develop RL (Reinforcement Learning) projects.

## Our Youtube Channel

If you are interested in our AI projects, visit our channel:

[AI Brain](https://www.youtube.com/@AiBrainAi?sub_confirmation=1)

## sdlarch

sdlarch is a small libretro frontend (sdlarch.c has less than 1000 lines of
code) created for educational purposes. It only provides the required (video,
audio and basic input) features to run basic libretro cores and there's no UI
or configuration support.

## Building
First, remove any Makefile folders or files (CMakeCache.txt and CMakeFiles).

### Linux:

```shell
cmake -B build -S . -DCMAKE_BUILD_TYPE=Release
cmake --build build
```

### Windows:
Have Visual Studio Preview 2022 or later installed.

With the Visual Studio cmd open:

```shell
cmake -B build -S . -DCMAKE_BUILD_TYPE=Release
cmake --build build
```

Notes:
- SDLArch-RL needs (on windows) the DLLs SDL2.dll and msvcrt.dll in the project root folder.
- SDLArch-RL creates the system folder in the project root on Linux and in the root of your driver on Windows (if running on the C drive, it will create c:\system). This folder should contain the bios and files needed for each Libretro core.

## TODO

- [ ] Create context without a window (Currently the window is hidden)
- [ ] Tool to add games/map memory/save states, etc.
- [ ] Add Support to analog actions
- [ ] Cemu Core (It takes a lot of work to make the core libretro!!!)
- [ ] Xemu Core (It takes a lot of work to make the core libretro!!!)
- [ ] Rpcs3 Core (It takes a lot of work to make the core libretro!!!)
- [ ] Xenia Core (It takes a lot of work to make the core libretro!!!)
- [ ] Run PPSSPP Core (PSP) (currently running on linux)
- [x] Run DesMume Core (Nintendo DS)
- [ ] Run Citra Core (Nintendo 3DS)
- [x] Run Dolphin Core (need pass ID for env)
- [x] Run mupen64plus_next (n64) Core
- [x] Run PCSX2 Core
- [x] Run Flycast Core
- [ ] Compile cores in build
- [x] Load state from file
- [x] Gymnasium compatibility
- [x] Load Emulator memory
- [x] Load games in the same standard as stable-retro
- [ ] Improve performance












