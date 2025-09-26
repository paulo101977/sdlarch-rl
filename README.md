# sdlarch-rl

This is a fork of sdlarch that aims to develop RL (Reinforcement Learning) projects.

## sdlarch

sdlarch is a small libretro frontend (sdlarch.c has less than 1000 lines of
code) created for educational purposes. It only provides the required (video,
audio and basic input) features to run basic libretro cores and there's no UI
or configuration support.

## Building
First, remove any Makefile folders or files (CMakeCache.txt and CMakeFiles).

### Linux:

```shell
cmake .
make
```

### Windows:
Have Visual Studio Preview 2022 or later installed.

With the Visual Studio cmd open:

```shell
cmake . -G "NMake Makefiles"
nmake
```

## TODO

- [ ] Add Support to analog actions
- [ ] Cemu Core (It takes a lot of work to make the core libretro!!!)
- [ ] Run PPSSPP Core (PSP)
- [ ] Run DesMume Core (Nintendo DS)
- [ ] Run Citra Core (Nintendo 3DS)
- [x] Run Dolphin Core (need pass ID for env)
- [x] Run mupen64plus_next (n64) Core
- [x] Run PCSX2 Core
- [x] Run Flycast Core
- [ ] Compile cores in build
- [ ] Tool to add games/map memory/save states, etc.
- [x] Load state from file
- [x] Gymnasium compatibility
- [x] Load Emulator memory
- [ ] Load games in the same standard as stable-retro
- [ ] Improve performance

## Our Youtube Channel

If you are interested in our AI projects, visit our channel:

[AI Brain](https://www.youtube.com/@AiBrainAi?sub_confirmation=1)








