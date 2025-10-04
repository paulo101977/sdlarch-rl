#ifndef SDLARCH_H
#define SDLARCH_H

#include <SDL.h>
#include "libretro.h"
#include "glad.h"
#include <map>
#include <string>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <vector>
#include <cstdint>
#include <cstdio>
#include <filesystem>

#ifdef _WIN32
#include <direct.h>
#define _CRT_SECURE_NO_WARNINGS
#endif

#ifdef _WIN32
#define EXPORT __declspec(dllexport)
#else
#define EXPORT
#endif

// Define Wii and GC devices
#define RETRO_DEVICE_WIIMOTE RETRO_DEVICE_JOYPAD
#define RETRO_DEVICE_WIIMOTE_SW ((2 << 8) | RETRO_DEVICE_JOYPAD)
#define RETRO_DEVICE_WIIMOTE_NC ((3 << 8) | RETRO_DEVICE_JOYPAD)
#define RETRO_DEVICE_WIIMOTE_CC ((4 << 8) | RETRO_DEVICE_JOYPAD)
#define RETRO_DEVICE_WIIMOTE_CC_PRO ((5 << 8) | RETRO_DEVICE_JOYPAD)
#define RETRO_DEVICE_GC_ON_WII ((6 << 8) | RETRO_DEVICE_JOYPAD)
#define RETRO_DEVICE_REAL_WIIMOTE ((6 << 8) | RETRO_DEVICE_NONE)

// using namespace std;

static SDL_Window *g_win = NULL;
static SDL_GLContext g_ctx = NULL;
static SDL_AudioDeviceID g_pcm = 0;
static struct retro_frame_time_callback runloop_frame_time;
static retro_usec_t runloop_frame_time_last = 0;
static const uint8_t *g_kbd = NULL;
static struct retro_audio_callback audio_callback;
static char* m_romPath;
static char* m_corePath;
static bool coreLoaded = false;
static bool gameLoaded = false;
static bool g_variables_updated = false;
static std::vector<uint8_t> g_last_frame_buffer;
static int g_last_frame_width = 0;
static int g_last_frame_height = 0;
static bool is_desmume = false;
static int env_id = -1;

static int g_scale = 1;
static bool running = true;

const int N_BUTTONS = 16;
const int MAX_PLAYERS = 2;
static bool m_buttonMask[MAX_PLAYERS][N_BUTTONS]{};
static std::map<std::string, std::string> g_variable_overrides;

// Audio buffer; accumulated during run()
static std::vector<int16_t> audioData;
static retro_system_av_info avInfo = {};

static struct {
	void *handle;
	bool initialized;
	bool supports_no_game;
	// The last performance counter registered. TODO: Make it a linked list.
	struct retro_perf_counter* perf_counter_last;

	void (*retro_init)(void);
	void (*retro_deinit)(void);
	unsigned (*retro_api_version)(void);
	void (*retro_get_system_info)(struct retro_system_info *info);
	void (*retro_get_system_av_info)(struct retro_system_av_info *info);
	void (*retro_set_controller_port_device)(unsigned port, unsigned device);
	void (*retro_reset)(void);
	void (*retro_run)(void);
    size_t (*retro_serialize_size)(void);
    bool (*retro_serialize)(void *data, size_t size);
    bool (*retro_unserialize)(const void *data, size_t size);
//	void retro_cheat_reset(void);
//	void retro_cheat_set(unsigned index, bool enabled, const char *code);
	bool (*retro_load_game)(const struct retro_game_info *game);
//	bool retro_load_game_special(unsigned game_type, const struct retro_game_info *info, size_t num_info);
	void (*retro_unload_game)(void);
//	unsigned retro_get_region(void);
	void* (*retro_get_memory_data)(unsigned id);
	size_t (*retro_get_memory_size)(unsigned id);
    int width;
    int height;
} g_retro;



void init(char *core, char *game, int id);
void run();
void runAlone();
void reset();
void closeEnv();
size_t get_state_size();
void set_variable(const std::string& key, const std::string& value);
void get_frame(uint8_t* buffer, int width, int height);
void set_key(int port, int key, bool active);
void c_printf(const char* format, ...);
void unload_game();
void core_load_game(const char *filename);



#endif // SDLARCH_H