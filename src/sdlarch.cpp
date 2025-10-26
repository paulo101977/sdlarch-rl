
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
#include "sdlarch.h"

using namespace std;

// #ifdef __cplusplus
// extern "C" {
// #endif

SDLArch::SDLArch() {
}

// Global static variables --------------------------------- //
SDLArch::RetroContext SDLArch::g_retro{};
SDL_Window* SDLArch::g_win = NULL;
SDL_GLContext SDLArch::g_ctx = NULL;
SDL_AudioDeviceID SDLArch::g_pcm = 0;
int SDLArch::g_scale = 1;
bool SDLArch::m_buttonMask[SDLArch::MAX_PLAYERS][SDLArch::N_BUTTONS] = {};
bool SDLArch::is_desmume = false;
int SDLArch::g_last_frame_width = 0;
int SDLArch::g_last_frame_height = 0;
bool SDLArch::g_variables_updated = false;
int SDLArch::env_id = -1;
bool SDLArch::gameLoaded = false;
bool SDLArch::coreLoaded = false;
retro_system_av_info SDLArch::avInfo = {};
bool SDLArch::running = false;
char* SDLArch::m_romPath = NULL;
char* SDLArch::m_corePath = NULL;
std::vector<uint8_t> SDLArch::g_last_frame_buffer{};
std::vector<int16_t> SDLArch::audioData;
std::map<std::string, std::string> SDLArch::g_variable_overrides{};
// end Global static variables --------------------------------- //

// log function that prints to python console
void SDLArch::c_printf(const char* format, ...) {
#ifdef DEBUG
    char buffer[256];
    va_list args;
    va_start(args, format);
    vsnprintf(buffer, sizeof(buffer), format, args);
    va_end(args);
    
    py::print(buffer);
#endif
}

static struct {
	GLuint tex_id;
    GLuint fbo_id;
    GLuint rbo_id;

    int glmajor;
    int glminor;


	GLuint pitch;
	GLint tex_w, tex_h;
	GLuint clip_w, clip_h;

	GLuint pixfmt;
	GLuint pixtype;
	GLuint bpp;

    struct retro_hw_render_callback hw;
} g_video  = {0};

static struct {
    GLuint vao;
    GLuint vbo;
    GLuint program;

    GLint i_pos;
    GLint i_coord;
    GLint u_tex;
    GLint u_mvp;

} g_shader = {0};

static struct retro_variable *g_vars = NULL;

static const char *g_vshader_src =
    "#version 150\n"
    "in vec2 i_pos;\n"
    "in vec2 i_coord;\n"
    "out vec2 o_coord;\n"
    "uniform mat4 u_mvp;\n"
    "void main() {\n"
        "o_coord = i_coord;\n"
        "gl_Position = vec4(i_pos, 0.0, 1.0) * u_mvp;\n"
    "}";

static const char *g_fshader_src =
    "#version 150\n"
    "in vec2 o_coord;\n"
    "uniform sampler2D u_tex;\n"
    "void main() {\n"
        "gl_FragColor = texture2D(u_tex, o_coord);\n"
    "}";

static map<string, const char*> s_envVariables = {
	{ "pcsx2_enable_hw_hacks", "enabled" },
	{ "pcsx2_renderer", "OpenGL" },
	{ "pcsx2_software_clut_render", "Normal" },
	{ "pcsx2_fastboot", "enabled" },
    { "pcsx2_blending_accuracy", "Medium" },
	{ "pcsx2_pgs_ssaa", "Native" },
	{ "pcsx2_pgs_ss_tex", "disabled" },
	{ "pcsx2_pgs_deblur", "disabled" },
	{ "pcsx2_pgs_high_res_scanout", "disabled" },
	{ "pcsx2_pgs_disable_mipmaps", "disabled" },
	{ "pcsx2_nointerlacing_hint", "disabled" },
	{ "pcsx2_pcrtc_antiblur", "disabled" },
	{ "pcsx2_pcrtc_screen_offsets", "disabled" },
	{ "pcsx2_disable_interlace_offset", "disabled" },
	{ "pcsx2_deinterlace_mode", "Automatic" },
	{ "pcsx2_enable_cheats", "disabled" },
	{ "pcsx2_hint_language_unlock", "disabled" },
	{ "pcsx2_ee_cycle_rate", "100% (Normal Speed)" },
	{ "pcsx2_widescreen_hint", "disabled" },
	{ "pcsx2_uncapped_framerate_hint", "disabled" },
	{ "pcsx2_game_enhancements_hint", "disabled" },
	{ "pcsx2_ee_cycle_skip", "disabled" },
	{ "pcsx2_axis_scale1", "133%" },
	{ "pcsx2_axis_deadzone1", "0%" },
	{ "pcsx2_button_deadzone1", "0%" },
    { "pcsx2_button_deadzone2", "0%" },
	{ "pcsx2_enable_rumble1", "disabled" },
    { "pcsx2_enable_rumble2", "disabled" },
	{ "pcsx2_invert_left_stick1", "disabled" },
	{ "pcsx2_invert_right_stick1", "disabled" },
	{ "pcsx2_axis_scale2", "133%" },
	{ "pcsx2_axis_deadzone2", "15%" },
	{ "pcsx2_button_deadzone2", "0%" },
	{ "pcsx2_invert_left_stick2", "disabled" },
	{ "pcsx2_invert_right_stick2", "disabled" },
    { "dolphin_efb_scale", "x1 (640 x 528)" },
	{ "dolphin_log_level", "Info" },
	{ "dolphin_cpu_clock_rate", "100%" },
    { "dolphin_enable_rumble", "disabled" },
	{ "dolphin_renderer", "Hardware" },
	{ "dolphin_wiimote_continuous_scanning", "disabled" },
	{ "dolphin_shader_compilation_mode", "a-sync Skip Rendering" },
	{ "dolphin_efb_scaled_copy", "enabled" },
	{ "dolphin_efb_to_texture", "enabled" },
	{ "dolphin_gpu_texture_decoding", "enabled" },
	{ "dolphin_wait_for_shaders", "disabled" },
    { "desmume_opengl_mode", "disabled" },
    { "desmume_cpu_mode", "jit"},
    { "desmume_screens_layout", "top/bottom" },
	{ "dolphin_osd_enabled", "disabled" },
    { "ppsspp_internal_resolution", "480x272" },
    { "ppsspp_cpu_core", "jit" },
    { "ppsspp_locked_cpu_speed", "off" },
    { "ppsspp_language", "automatic" },
    { "ppsspp_button_preference", "cross" },
    { "ppsspp_rendering_mode", "buffered" },
    { "ppsspp_gpu_hardware_transform", "enabled" },
    { "ppsspp_texture_anisotropic_filtering", "off" },
    { "ppsspp_spline_quality", "low" },
    { "ppsspp_auto_frameskip", "disabled" },
    { "ppsspp_frameskip", "0" },
    { "ppsspp_frameskiptype", "number of frames" },
    { "ppsspp_frame_duplication", "disabled" },
    { "ppsspp_vertex_cache", "disabled" },
    { "ppsspp_fast_memory", "enabled" },
    { "ppsspp_block_transfer_gpu", "enabled" },
    { "ppsspp_software_skinning", "enabled" },
    { "ppsspp_lazy_texture_caching", "disabled" },
    { "ppsspp_retain_changed_textures", "disabled" },
    { "ppsspp_force_lag_sync", "disabled" },
    { "ppsspp_disable_slow_framebuffer_effects", "disabled" },
    { "ppsspp_lower_resolution_for_effects", "off" },
    { "ppsspp_texture_scaling_level", "1" },
    { "ppsspp_texture_scaling_type", "xbrz" },
    { "ppsspp_texture_filtering", "auto" },
    { "ppsspp_texture_deposterize", "disabled" },
    { "ppsspp_texture_replacement", "disabled" },
    { "ppsspp_io_threading", "enabled" },
    { "ppsspp_io_timing_method", "Fast" },
    { "ppsspp_ignore_bad_memory_access", "enabled" },
    { "ppsspp_cheats", "disabled" },
};

struct keymap {
	unsigned k;
	unsigned rk;
};


static unsigned g_joy[RETRO_DEVICE_ID_JOYPAD_R3+1] = { 0 };

#define load_sym(V, S) do {\
    if (!((*(void**)&V) = SDL_LoadFunction(SDLArch::g_retro.handle, #S))) \
        die("Failed to load symbol '" #S "'': %s", SDL_GetError()); \
	} while (0)
#define load_retro_sym(S) load_sym(SDLArch::g_retro.S, S)


static void die(const char *fmt, ...) {
	char buffer[4096];

	va_list va;
	va_start(va, fmt);
	vsnprintf(buffer, sizeof(buffer), fmt, va);
	va_end(va);

	fputs(buffer, stderr);
	fputc('\n', stderr);
	fflush(stderr);

	exit(EXIT_FAILURE);
}

static GLuint compile_shader(unsigned type, unsigned count, const char **strings) {
    GLuint shader = glCreateShader(type);
    glShaderSource(shader, count, strings, NULL);
    glCompileShader(shader);

    GLint status;
    glGetShaderiv(shader, GL_COMPILE_STATUS, &status);

    if (status == GL_FALSE) {
        char buffer[4096];
        glGetShaderInfoLog(shader, sizeof(buffer), NULL, buffer);
        die("Failed to compile %s shader: %s", type == GL_VERTEX_SHADER ? "vertex" : "fragment", buffer);
    }

    return shader;
}

void ortho2d(float m[4][4], float left, float right, float bottom, float top) {
    m[0][0] = 1; m[0][1] = 0; m[0][2] = 0; m[0][3] = 0;
    m[1][0] = 0; m[1][1] = 1; m[1][2] = 0; m[1][3] = 0;
    m[2][0] = 0; m[2][1] = 0; m[2][2] = 1; m[2][3] = 0;
    m[3][0] = 0; m[3][1] = 0; m[3][2] = 0; m[3][3] = 1;

    m[0][0] = 2.0f / (right - left);
    m[1][1] = 2.0f / (top - bottom);
    m[2][2] = -1.0f;
    m[3][0] = -(right + left) / (right - left);
    m[3][1] = -(top + bottom) / (top - bottom);
}



static void init_shaders() {
    GLuint vshader = compile_shader(GL_VERTEX_SHADER, 1, &g_vshader_src);
    GLuint fshader = compile_shader(GL_FRAGMENT_SHADER, 1, &g_fshader_src);
    GLuint program = glCreateProgram();

    SDL_assert(program);

    glAttachShader(program, vshader);
    glAttachShader(program, fshader);
    glLinkProgram(program);

    glDeleteShader(vshader);
    glDeleteShader(fshader);

    glValidateProgram(program);

    GLint status;
    glGetProgramiv(program, GL_LINK_STATUS, &status);

    if(status == GL_FALSE) {
        char buffer[4096];
        glGetProgramInfoLog(program, sizeof(buffer), NULL, buffer);
        die("Failed to link shader program: %s", buffer);
    }

    g_shader.program = program;
    g_shader.i_pos   = glGetAttribLocation(program,  "i_pos");
    g_shader.i_coord = glGetAttribLocation(program,  "i_coord");
    g_shader.u_tex   = glGetUniformLocation(program, "u_tex");
    g_shader.u_mvp   = glGetUniformLocation(program, "u_mvp");

    glGenVertexArrays(1, &g_shader.vao);
    glGenBuffers(1, &g_shader.vbo);

    glUseProgram(g_shader.program);

    glUniform1i(g_shader.u_tex, 0);

    float m[4][4];
    if (g_video.hw.bottom_left_origin)
        ortho2d(m, -1, 1, 1, -1);
    else
        ortho2d(m, -1, 1, -1, 1);

    glUniformMatrix4fv(g_shader.u_mvp, 1, GL_FALSE, (float*)m);

    glUseProgram(0);
}


static void refresh_vertex_data() {
    SDL_assert(g_video.tex_w);
    SDL_assert(g_video.tex_h);
    SDL_assert(g_video.clip_w);
    SDL_assert(g_video.clip_h);

    float bottom = (float)g_video.clip_h / g_video.tex_h;
    float right  = (float)g_video.clip_w / g_video.tex_w;

    float vertex_data[] = {
        // pos, coord
        -1.0f, -1.0f, 0.0f,  bottom, // left-bottom
        -1.0f,  1.0f, 0.0f,  0.0f,   // left-top
         1.0f, -1.0f, right,  bottom,// right-bottom
         1.0f,  1.0f, right,  0.0f,  // right-top
    };

    glBindVertexArray(g_shader.vao);

    glBindBuffer(GL_ARRAY_BUFFER, g_shader.vbo);
    glBufferData(GL_ARRAY_BUFFER, sizeof(vertex_data), vertex_data, GL_STREAM_DRAW);

    glEnableVertexAttribArray(g_shader.i_pos);
    glEnableVertexAttribArray(g_shader.i_coord);
    glVertexAttribPointer(g_shader.i_pos, 2, GL_FLOAT, GL_FALSE, sizeof(float)*4, 0);
    glVertexAttribPointer(g_shader.i_coord, 2, GL_FLOAT, GL_FALSE, sizeof(float)*4, (void*)(2 * sizeof(float)));

    glBindVertexArray(0);
    glBindBuffer(GL_ARRAY_BUFFER, 0);
}

static void init_framebuffer(int width, int height)
{
    glGenFramebuffers(1, &g_video.fbo_id);
    glBindFramebuffer(GL_FRAMEBUFFER, g_video.fbo_id);

    glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, g_video.tex_id, 0);

    if (g_video.hw.depth && g_video.hw.stencil) {
        glGenRenderbuffers(1, &g_video.rbo_id);
        glBindRenderbuffer(GL_RENDERBUFFER, g_video.rbo_id);
        glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH24_STENCIL8, width, height);

        glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_STENCIL_ATTACHMENT, GL_RENDERBUFFER, g_video.rbo_id);
    } else if (g_video.hw.depth) {
        glGenRenderbuffers(1, &g_video.rbo_id);
        glBindRenderbuffer(GL_RENDERBUFFER, g_video.rbo_id);
        glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH_COMPONENT24, width, height);

        glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_RENDERBUFFER, g_video.rbo_id);
    }

    if (g_video.hw.depth || g_video.hw.stencil)
        glBindRenderbuffer(GL_RENDERBUFFER, 0);

    glBindRenderbuffer(GL_RENDERBUFFER, 0);

    SDL_assert(glCheckFramebufferStatus(GL_FRAMEBUFFER) == GL_FRAMEBUFFER_COMPLETE);

    glClearColor(0, 0, 0, 1);
    glClear(GL_COLOR_BUFFER_BIT);

    glBindFramebuffer(GL_FRAMEBUFFER, 0);
}


static void resize_cb(int w, int h) {
    if(SDLArch::is_desmume) {
       glViewport(0, h, w, 0); 
    } else {
        glViewport(0, 0, w, h);
    }
	
}


static void create_window(int width, int height) {
    SDL_GL_SetAttribute(SDL_GL_DOUBLEBUFFER, 1);
    SDL_GL_SetAttribute(SDL_GL_ACCELERATED_VISUAL, 1);
    SDL_GL_SetAttribute(SDL_GL_RED_SIZE, 8);
    SDL_GL_SetAttribute(SDL_GL_GREEN_SIZE, 8);
    SDL_GL_SetAttribute(SDL_GL_BLUE_SIZE, 8);
    SDL_GL_SetAttribute(SDL_GL_ALPHA_SIZE, 8);

    if (g_video.hw.context_type == RETRO_HW_CONTEXT_OPENGL_CORE || g_video.hw.version_major >= 3) {
        SDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, g_video.hw.version_major);
        SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, g_video.hw.version_minor);
        SDL_GL_SetAttribute(SDL_GL_CONTEXT_FLAGS, SDL_GL_CONTEXT_DEBUG_FLAG);
    }

    switch (g_video.hw.context_type) {
    case RETRO_HW_CONTEXT_OPENGL_CORE:
        SDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_CORE);
        break;
    case RETRO_HW_CONTEXT_OPENGLES2:
        SDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_ES);
        break;
    case RETRO_HW_CONTEXT_OPENGL:
        if (g_video.hw.version_major >= 3)
            SDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_COMPATIBILITY);
        break;
    
    default:
        die("Unsupported hw context %i. (only OPENGL, OPENGL_CORE and OPENGLES2 supported)", g_video.hw.context_type);
    }

    if(!SDLArch::g_win) {
        SDLArch::g_win = SDL_CreateWindow(
            "sdlarch", 
            SDL_WINDOWPOS_CENTERED,
            SDL_WINDOWPOS_CENTERED,
            width, 
            height, 
            SDL_WINDOW_OPENGL | SDL_WINDOW_HIDDEN
        );
    }
    

	if (!SDLArch::g_win)
        die("Failed to create window: %s", SDL_GetError());

    if(!SDLArch::g_ctx) {
        SDLArch::g_ctx = SDL_GL_CreateContext(SDLArch::g_win);
    }
    

    SDL_GL_MakeCurrent(SDLArch::g_win, SDLArch::g_ctx);

    if (!SDLArch::g_ctx)
        die("Failed to create OpenGL context: %s", SDL_GetError());

    if (g_video.hw.context_type == RETRO_HW_CONTEXT_OPENGLES2) {
        if (!gladLoadGLES2Loader((GLADloadproc)SDL_GL_GetProcAddress))
            die("Failed to initialize glad.");
    } else {
        if (!gladLoadGLLoader((GLADloadproc)SDL_GL_GetProcAddress))
            die("Failed to initialize glad.");
    }

#ifdef DEBUG
    fprintf(stderr, "GL_SHADING_LANGUAGE_VERSION: %s\n", glGetString(GL_SHADING_LANGUAGE_VERSION));
    fprintf(stderr, "GL_VERSION: %s\n", glGetString(GL_VERSION));
#endif


    init_shaders();

    SDL_GL_SetSwapInterval(0); // disable vsync
    SDL_GL_SwapWindow(SDLArch::g_win); // make apitrace output nicer

    resize_cb(width, height);

    if (g_video.hw.context_reset) {
        g_video.hw.context_reset();
    }
}


static void resize_to_aspect(double ratio, int sw, int sh, int *dw, int *dh) {
	*dw = sw;
	*dh = sh;

	if (ratio <= 0)
		ratio = (double)sw / sh;

	if ((float)sw / sh < 1)
		*dw = (int)(*dh * ratio);
	else
		*dh = (int)(*dw / ratio);
}


static void video_configure(const struct retro_game_geometry *geom) {
	int nwidth, nheight, scale;

    scale = (int)(SDLArch::g_scale);

	resize_to_aspect(
        geom->aspect_ratio, 
        geom->base_width * scale, 
        geom->base_height * scale, 
        &nwidth, 
        &nheight
    );

	nwidth *= scale;
	nheight *= scale;

	if (!SDLArch::g_win)
		create_window(nwidth, nheight);
    else {
        SDL_SetWindowSize(SDLArch::g_win, nwidth, nheight);
    }

	if (g_video.tex_id)
		glDeleteTextures(1, &g_video.tex_id);

	g_video.tex_id = 0;

	if (!g_video.pixfmt)
		g_video.pixfmt = GL_UNSIGNED_SHORT_5_5_5_1;

    // SDL_SetWindowSize(SDLArch::g_win, nwidth, nheight);

	glGenTextures(1, &g_video.tex_id);

	if (!g_video.tex_id)
		die("Failed to create the video texture");

	g_video.pitch = geom->max_width * g_video.bpp;

	glBindTexture(GL_TEXTURE_2D, g_video.tex_id);

//	glPixelStorei(GL_UNPACK_ALIGNMENT, s_video.pixfmt == GL_UNSIGNED_INT_8_8_8_8_REV ? 4 : 2);
//	glPixelStorei(GL_UNPACK_ROW_LENGTH, s_video.pitch / s_video.bpp);

	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);

	glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, geom->max_width, geom->max_height, 0,
			g_video.pixtype, g_video.pixfmt, NULL);

	glBindTexture(GL_TEXTURE_2D, 0);

    init_framebuffer(geom->max_width, geom->max_height);

	g_video.tex_w = geom->max_width;
	g_video.tex_h = geom->max_height;
	g_video.clip_w = geom->base_width;
	g_video.clip_h = geom->base_height;

    SDLArch::g_retro.width = geom->base_width;
    SDLArch::g_retro.height = geom->base_height;

    SDL_SetWindowSize(SDLArch::g_win, geom->base_width, geom->base_height);
    resize_cb(geom->base_width, geom->base_height);
    
	refresh_vertex_data();

    if (g_video.hw.context_reset) {
        g_video.hw.context_reset();
    }
}


static bool video_set_pixel_format(unsigned format) {
	switch (format) {
	case RETRO_PIXEL_FORMAT_0RGB1555:
		g_video.pixfmt = GL_UNSIGNED_SHORT_5_5_5_1;
		g_video.pixtype = GL_BGRA;
		g_video.bpp = sizeof(uint16_t);
		break;
	case RETRO_PIXEL_FORMAT_XRGB8888:
		g_video.pixfmt = GL_UNSIGNED_INT_8_8_8_8_REV;
		g_video.pixtype = GL_BGRA;
		g_video.bpp = sizeof(uint32_t);
		break;
	case RETRO_PIXEL_FORMAT_RGB565:
		g_video.pixfmt  = GL_UNSIGNED_SHORT_5_6_5;
		g_video.pixtype = GL_RGB;
		g_video.bpp = sizeof(uint16_t);
		break;
	default:
		die("Unknown pixel type %u", format);
	}

	return true;
}


static void video_refresh(const void *data, unsigned width, unsigned height, size_t pitch) {
    if( width != 0 && height != 0) {
        SDLArch::g_retro.width = width;
        SDLArch::g_retro.height = height; 
    }

    glBindFramebuffer(GL_FRAMEBUFFER, g_video.fbo_id);

    if (data == RETRO_HW_FRAME_BUFFER_VALID) {
        glBindFramebuffer(GL_READ_FRAMEBUFFER, (GLuint)(g_video.hw.get_current_framebuffer()));
        glBindFramebuffer(GL_DRAW_FRAMEBUFFER, g_video.fbo_id);
        glBlitFramebuffer(0, 0, width, height, 0, 0, width, height, GL_COLOR_BUFFER_BIT, GL_NEAREST);
    } else if (data) {
        glBindTexture(GL_TEXTURE_2D, g_video.tex_id);
        glPixelStorei(GL_UNPACK_ROW_LENGTH, ((int)pitch) / g_video.bpp);
        glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, width, height, g_video.pixtype, g_video.pixfmt, data);
        glUseProgram(g_shader.program);
        glActiveTexture(GL_TEXTURE0);
        glBindTexture(GL_TEXTURE_2D, g_video.tex_id);
        glBindVertexArray(g_shader.vao);
        glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);
    }

    if (width > 0 && height > 0) {
        size_t buffer_size = width * height * 3;
        if (SDLArch::g_last_frame_buffer.size() != buffer_size) {
            SDLArch::g_last_frame_buffer.resize(buffer_size);
            SDLArch::g_last_frame_width = width;
            SDLArch::g_last_frame_height = height;
        }
        glBindFramebuffer(GL_READ_FRAMEBUFFER, g_video.fbo_id);
        glReadBuffer(GL_COLOR_ATTACHMENT0);
        glReadPixels(0, 0, width, height, GL_RGB, GL_UNSIGNED_BYTE, SDLArch::g_last_frame_buffer.data());
    }

    glBindFramebuffer(GL_READ_FRAMEBUFFER, g_video.fbo_id);
    glBindFramebuffer(GL_DRAW_FRAMEBUFFER, 0);
    glBlitFramebuffer(0, 0, width, height, 0, 0, width, height, GL_COLOR_BUFFER_BIT, GL_NEAREST);
}

static void video_deinit() {
    if (g_video.fbo_id)
        glDeleteFramebuffers(1, &g_video.fbo_id);

	if (g_video.tex_id)
		glDeleteTextures(1, &g_video.tex_id);

    if (g_shader.vao)
        glDeleteVertexArrays(1, &g_shader.vao);

    if (g_shader.vbo)
        glDeleteBuffers(1, &g_shader.vbo);

    if (g_shader.program)
        glDeleteProgram(g_shader.program);

    g_video.fbo_id = 0;
	g_video.tex_id = 0;
    g_shader.vao = 0;
    g_shader.vbo = 0;
    g_shader.program = 0;

    SDL_GL_MakeCurrent(SDLArch::g_win, SDLArch::g_ctx);
    SDL_GL_DeleteContext(SDLArch::g_ctx);

    SDLArch::g_ctx = NULL;

    SDL_DestroyWindow(SDLArch::g_win);
}


static void core_log(enum retro_log_level level, const char *fmt, ...) {
#ifdef DEBUG
	char buffer[4096] = {0};
	static const char * levelstr[] = { "dbg", "inf", "wrn", "err" };
	va_list va;

	va_start(va, fmt);
	vsnprintf(buffer, sizeof(buffer), fmt, va);
	va_end(va);

	if (level == 0)
		return;

	fprintf(stderr, "[%s] %s", levelstr[level], buffer);
	fflush(stderr);

	// if (level == RETRO_LOG_ERROR)
	// 	exit(EXIT_FAILURE);
#endif
}

static uintptr_t core_get_current_framebuffer() {
    return g_video.fbo_id;
}

/**
 * Log and display the state of performance counters.
 *
 * @see retro_perf_log_t
 */
static void core_perf_log() {
    // TODO: Use a linked list of counters, and loop through them all.
    core_log(RETRO_LOG_INFO, "[timer] %s: %i - %i", SDLArch::g_retro.perf_counter_last->ident, SDLArch::g_retro.perf_counter_last->start, SDLArch::g_retro.perf_counter_last->total);
}


void SDLArch::set_variable(const std::string& key, const std::string& value) {
    SDLArch::g_variable_overrides[key] = value;
    printf("Set variable override: %s = %s\n", key.c_str(), value.c_str());
}

static bool core_environment(unsigned cmd, void *data) {
	switch (cmd) {
    case RETRO_ENVIRONMENT_GET_RUMBLE_INTERFACE:
        
        return false;
    case RETRO_ENVIRONMENT_GET_INPUT_DEVICE_CAPABILITIES: {
        uint64_t* caps = (uint64_t*)data;
        *caps = (1 << RETRO_DEVICE_JOYPAD);
        return true;
    }

    case RETRO_ENVIRONMENT_SET_VARIABLES: {
        const struct retro_variable *vars = (const struct retro_variable *)data;
        size_t num_vars = 0;

        for (const struct retro_variable *v = vars; v->key; ++v) {
            num_vars++;
        }

        g_vars = (struct retro_variable*)calloc(num_vars + 1, sizeof(*g_vars));
        for (unsigned i = 0; i < num_vars; ++i) {
            const struct retro_variable *invar = &vars[i];
            struct retro_variable *outvar = &g_vars[i];

            const char *semicolon = strchr(invar->value, ';');
            const char *first_pipe = strchr(invar->value, '|');

            SDL_assert(semicolon && *semicolon);
            semicolon++;
            while (isspace(*semicolon))
                semicolon++;

            if (first_pipe) {
                outvar->value = (const char*)malloc((first_pipe - semicolon) + 1);
                memcpy((char*)outvar->value, semicolon, first_pipe - semicolon);
                ((char*)outvar->value)[first_pipe - semicolon] = '\0';
            } else {
                outvar->value = _strdup(semicolon);
            }

            outvar->key = _strdup(invar->key);

            if (s_envVariables.count(string(outvar->key))) {
                // var->value = s_envVariables[string(var->key)];
                outvar->value = _strdup(s_envVariables[string(outvar->key)]);
            }

            // if(!strcmp(outvar->key, "dolphin_renderer")) {
            //     free((void*)outvar->value);
            //     outvar->value = _strdup("Software");
            // }

            // if(!strcmp(outvar->key, "pcsx2_renderer")) {
            //     free((void*)outvar->value);
            //     outvar->value = _strdup("Software");
            // }

            SDLArch::c_printf("Variable: %s = %s\n", outvar->key, outvar->value);

            SDL_assert(outvar->key && outvar->value);
        }

        for (auto const& [key, val] : SDLArch::g_variable_overrides) {
            for (struct retro_variable *var = g_vars; var->key; var++) {
                if (std::string(var->key) == key) {
                    free((void*)var->value);
                    var->value = _strdup(val.c_str());
                    SDLArch::c_printf("Variable custom applied: %s = %s\n", key.c_str(), val.c_str());
                }
            }
        }

        return true;
    }


    case RETRO_ENVIRONMENT_GET_VARIABLE: {
        struct retro_variable *var = (struct retro_variable *)data;

        if (!g_vars)
            return false;

        for (const struct retro_variable *v = g_vars; v->key; ++v) {
            if (strcmp(var->key, v->key) == 0) {
                var->value = v->value;
                break;
            }
        }

        return true;
    }

    case RETRO_ENVIRONMENT_GET_VARIABLE_UPDATE: {
        bool *bval = (bool*)data;
		*bval = SDLArch::g_variables_updated;
        SDLArch::g_variables_updated = false;
        return true;
    }
	case RETRO_ENVIRONMENT_GET_LOG_INTERFACE: {
		struct retro_log_callback *cb = (struct retro_log_callback *)data;
		cb->log = core_log;
        return true;
	}
	case RETRO_ENVIRONMENT_SET_PIXEL_FORMAT: {
		const enum retro_pixel_format *fmt = (enum retro_pixel_format *)data;

		if (*fmt > RETRO_PIXEL_FORMAT_RGB565)
			return false;

		return video_set_pixel_format(*fmt);
	}
    case RETRO_ENVIRONMENT_GET_PREFERRED_HW_RENDER: {
        unsigned *fmt = (unsigned*)data;
        // *fmt = RETRO_HW_CONTEXT_OPENGL_CORE;
        *fmt = RETRO_HW_CONTEXT_OPENGL;
        return true;
    }

    case RETRO_ENVIRONMENT_SET_HW_RENDER: {
        struct retro_hw_render_callback *hw = (struct retro_hw_render_callback*)data;
        hw->get_current_framebuffer = core_get_current_framebuffer;
        hw->get_proc_address = (retro_hw_get_proc_address_t)SDL_GL_GetProcAddress;
        g_video.hw = *hw;
        return true;
    }
    
    case RETRO_ENVIRONMENT_GET_CORE_ASSETS_DIRECTORY:
    case RETRO_ENVIRONMENT_GET_SAVE_DIRECTORY:
    case RETRO_ENVIRONMENT_GET_SYSTEM_DIRECTORY: {
        const char **dir = (const char**)data;

#ifdef _WIN32
        static char absolute_path[1024];
        if (SDLArch::m_corePath && strstr(SDLArch::m_corePath, "ppsspp"))
        {
            SDLArch::c_printf("PPSSPP core system path\n");
            *dir = "./system";
            return true;
        }
        if (SDLArch::env_id >= 0) {
            snprintf(absolute_path, sizeof(absolute_path), "\\system\\dolphin-%d", SDLArch::env_id);
        } else {
            snprintf(absolute_path, sizeof(absolute_path), "\\system");
        }

        if (_fullpath(absolute_path, absolute_path, sizeof(absolute_path)) != NULL) {
            *dir = absolute_path;
        } else {
            *dir = "./system";
        }
        _mkdir(absolute_path);
#else
        static char system_path[1024];
        if (SDLArch::env_id >= 0) {
            snprintf(system_path, sizeof(system_path), "./system/dolphin-%d", SDLArch::env_id);
        } else {
            snprintf(system_path, sizeof(system_path), "./system");
        }
        *dir = system_path;
        mkdir(system_path, 0777);
#endif
        return true;
    }
    case RETRO_ENVIRONMENT_SET_GEOMETRY: {
        const struct retro_game_geometry *geom = (const struct retro_game_geometry *)data;
        g_video.clip_w = geom->base_width;
        g_video.clip_h = geom->base_height;

        SDLArch::g_retro.width = geom->base_width;
        SDLArch::g_retro.height = geom->base_height;

        // some cores call this before we even have a window
        if (SDLArch::g_win) {
            refresh_vertex_data();

            int ow = 0, oh = 0;
            resize_to_aspect(geom->aspect_ratio, geom->base_width, geom->base_height, &ow, &oh);

            ow *= SDLArch::g_scale;
            oh *= SDLArch::g_scale;

            SDL_SetWindowSize(SDLArch::g_win, geom->base_width, geom->base_height);

            resize_cb(geom->base_width, geom->base_height);
        }
        return true;
    }
    case RETRO_ENVIRONMENT_SET_SUPPORT_NO_GAME: {
        // SDLArch::g_retro.supports_no_game = *(bool*)data;
        return true;
    }
    // case RETRO_ENVIRONMENT_GET_AUDIO_VIDEO_ENABLE: {
    //     int *value = (int*)data;
    //     *value = 1 << 0 | 1 << 1;
    //     return true;
    // }
	default:
		core_log(RETRO_LOG_DEBUG, "Unhandled env #%u", cmd);
		return false;
	}

    return false;
}


static void core_video_refresh(const void *data, unsigned width, unsigned height, size_t pitch) {
    video_refresh(data, width, height, pitch);
}


static void core_input_poll(void) {
}


static int16_t core_input_state(unsigned port, unsigned device, unsigned index, unsigned id) {

    if (port >= SDLArch::MAX_PLAYERS) return 0;

    // analog button (treat as digital)
    if (index == RETRO_DEVICE_INDEX_ANALOG_BUTTON && device == RETRO_DEVICE_ANALOG) {
        // int16_t value = g_joy[id] ? 255 : 0;
        int16_t value = g_joy[id] ? 32767 : 0;
        return value;
    }
    
    // convert to button mask (PCSX2 style)
    if (device == RETRO_DEVICE_JOYPAD && id == RETRO_DEVICE_ID_JOYPAD_MASK) {
        int16_t mask = 0;
        for (int i = 0; i < SDLArch::N_BUTTONS; i++) {
            if (SDLArch::m_buttonMask[port][i]) {
                mask |= (1 << i);
            }
        }
        return mask;
    }
    

    if (device == RETRO_DEVICE_JOYPAD && id < SDLArch::N_BUTTONS) {
        return SDLArch::m_buttonMask[port][id] ? 1 : 0;
    }

    // FIXME: handle analog properly
    if(device == RETRO_DEVICE_ANALOG && index == RETRO_DEVICE_INDEX_ANALOG_LEFT ) {
        if(id == RETRO_DEVICE_ID_ANALOG_X) {
            if(SDLArch::m_buttonMask[port][RETRO_DEVICE_ID_JOYPAD_LEFT] == 1) {
                return -32767;
            } else if(SDLArch::m_buttonMask[port][RETRO_DEVICE_ID_JOYPAD_RIGHT] == 1) {
                return 32767;
            } else {
                return 0;
            }
        }

        if(id == RETRO_DEVICE_ID_ANALOG_Y) {
            if(SDLArch::m_buttonMask[port][RETRO_DEVICE_ID_JOYPAD_UP] == 1) {
                return -32767;
            } else if(SDLArch::m_buttonMask[port][RETRO_DEVICE_ID_JOYPAD_DOWN] == 1) {
                return 32767;
            } else {
                return 0;
            }
        }
        return 0;
    }
    

    if (device == RETRO_DEVICE_ANALOG) {
        return 0;
    }
    
    return 0;
}

static void core_audio_sample(int16_t left, int16_t right) {
    SDLArch::audioData.push_back(left);
	SDLArch::audioData.push_back(right);
}

static size_t core_audio_sample_batch(const int16_t *data, size_t frames) {
	SDLArch::audioData.insert(SDLArch::audioData.end(), data, &data[frames * 2]);
	return frames;
}


static void core_load(const char *sofile) {
	void (*set_environment)(retro_environment_t) = NULL;
	void (*set_video_refresh)(retro_video_refresh_t) = NULL;
	void (*set_input_poll)(retro_input_poll_t) = NULL;
	void (*set_input_state)(retro_input_state_t) = NULL;
	void (*set_audio_sample)(retro_audio_sample_t) = NULL;
	void (*set_audio_sample_batch)(retro_audio_sample_batch_t) = NULL;
	memset(&SDLArch::g_retro, 0, sizeof(SDLArch::g_retro));
    SDLArch::g_retro.handle = SDL_LoadObject(sofile);

	if (!SDLArch::g_retro.handle)
        die("Failed to load core: %s", SDL_GetError());

	load_retro_sym(retro_init);
	load_retro_sym(retro_deinit);
	load_retro_sym(retro_api_version);
	load_retro_sym(retro_get_system_info);
	load_retro_sym(retro_get_system_av_info);
	load_retro_sym(retro_set_controller_port_device);
	load_retro_sym(retro_reset);
	load_retro_sym(retro_run);
	load_retro_sym(retro_load_game);
    load_retro_sym(retro_unserialize);
    load_retro_sym(retro_serialize);
    load_retro_sym(retro_serialize_size);
	load_retro_sym(retro_unload_game);
    load_retro_sym(retro_get_memory_data);
    load_retro_sym(retro_get_memory_size);

	load_sym(set_environment, retro_set_environment);
	load_sym(set_video_refresh, retro_set_video_refresh);
	load_sym(set_input_poll, retro_set_input_poll);
	load_sym(set_input_state, retro_set_input_state);
	load_sym(set_audio_sample, retro_set_audio_sample);
	load_sym(set_audio_sample_batch, retro_set_audio_sample_batch);

	set_environment(core_environment);
	set_video_refresh(core_video_refresh);
	set_input_poll(core_input_poll);
	set_input_state(core_input_state);
	set_audio_sample(core_audio_sample);
	set_audio_sample_batch(core_audio_sample_batch);

	SDLArch::g_retro.retro_init();
	SDLArch::g_retro.initialized = true;
}

void SDLArch::unload_game() {
    SDLArch::g_retro.retro_unload_game();
}


void SDLArch::core_load_game(const char *filename) {
	// struct retro_system_av_info av = {0};
	struct retro_system_info system = {0};
	struct retro_game_info info = { filename, 0 };
    
    if (SDLArch::gameLoaded) {
        unload_game();
        SDLArch::gameLoaded = false;
    }

    info.path = filename;
    info.meta = "";
    info.data = NULL;
    info.size = 0;

    if (filename) {
        SDLArch::g_retro.retro_get_system_info(&system);

        if (!system.need_fullpath) {
            SDL_RWops *file = SDL_RWFromFile(filename, "rb");
            Sint64 size;

            if (!file)
                die("Failed to load %s: %s", filename, SDL_GetError());

            size = SDL_RWsize(file);

            if (size < 0)
                die("Failed to query game file size: %s", SDL_GetError());

            info.size = size;
            info.data = SDL_malloc(info.size);

            if (!info.data)
                die("Failed to allocate memory for the content");

            if (!SDL_RWread(file, (void*)info.data, info.size, 1))
                die("Failed to read file data: %s", SDL_GetError());

            SDL_RWclose(file);
        }
    }

	if (!SDLArch::g_retro.retro_load_game(&info))
		die("The core failed to load the content.");

	SDLArch::g_retro.retro_get_system_av_info(&SDLArch::avInfo);
    SDLArch::gameLoaded = true;

	video_configure(&SDLArch::avInfo.geometry);

    if (info.data)
        SDL_free((void*)info.data);

    // Now that we have the system info, set the window title.
    char window_title[255];
    snprintf(window_title, sizeof(window_title), "sdlarch %s %s", system.library_name, system.library_version);
    SDL_SetWindowTitle(SDLArch::g_win, window_title);
}

static void core_unload() {
	if (SDLArch::g_retro.initialized)
		SDLArch::g_retro.retro_deinit();

	if (SDLArch::g_retro.handle)
        SDL_UnloadObject(SDLArch::g_retro.handle);
}

static void noop() {}


bool get_state(void* data) {
    size_t size = SDLArch::g_retro.retro_serialize_size();
    return SDLArch::g_retro.retro_serialize(data, size);
}

size_t SDLArch::get_state_size() {
    return SDLArch::g_retro.retro_serialize_size();
}

bool load_state(const void* data, size_t size) {
    return SDLArch::g_retro.retro_unserialize(data, size);
}

bool is_hardware_rendering() {
    return g_video.hw.context_type != RETRO_HW_CONTEXT_NONE;
}

void SDLArch::get_frame(uint8_t* buffer, int width, int height) {
    if (!SDLArch::g_last_frame_buffer.empty() && width == SDLArch::g_last_frame_width && height == SDLArch::g_last_frame_height) {
        memcpy(buffer, SDLArch::g_last_frame_buffer.data(), SDLArch::g_last_frame_buffer.size());
    }
}

void SDLArch::run() {
    SDLArch::g_last_frame_buffer.clear();
    
    SDLArch::audioData.clear();
    SDLArch::g_retro.retro_run();
}

// only for testing core without window
void SDLArch::runAlone() {
    SDLArch::g_retro.retro_run();
}

void SDLArch::reset() {
    memset(SDLArch::m_buttonMask, 0, sizeof(SDLArch::m_buttonMask));

    // restore context
	if (SDLArch::g_win && SDLArch::g_ctx) {
        SDL_GL_MakeCurrent(SDLArch::g_win, SDLArch::g_ctx);
    }

    SDLArch::g_retro.retro_reset();
    
    // clear framebuffer
    SDLArch::g_last_frame_buffer.clear();
    
}

void SDLArch::set_key(int port, int key, bool active) { 
    SDLArch::m_buttonMask[port][key] = active; 
}

void SDLArch::init(char *core, char *game, int id) {
    if (SDL_Init(SDL_INIT_VIDEO|SDL_INIT_EVENTS) < 0) {
    // if (SDL_Init(SDL_INIT_VIDEO|SDL_INIT_AUDIO|SDL_INIT_EVENTS) < 0) {
        printf("SDL_Init failed: %s\n", SDL_GetError());
        die("Failed to initialize SDL");
    }

    SDLArch::env_id = id;
    SDLArch::coreLoaded = false;

    SDL_SetHint(SDL_HINT_RENDER_DRIVER, "opengl");
    SDL_SetHint(SDL_HINT_RENDER_OPENGL_SHADERS, "1");
    SDL_SetHint(SDL_HINT_RENDER_SCALE_QUALITY, "0"); // Nearest neighbor
    SDL_SetHint(SDL_HINT_RENDER_VSYNC, "0");

    // Use proper way to delete the dolphin folder
    #ifndef _WIN32
    system("rm -rf ./system/User");
    #endif

    SDLArch::m_romPath = _strdup(game);
    SDLArch::m_corePath = _strdup(core);

    if(strstr(SDLArch::m_corePath, "desmume")) {
       SDLArch::is_desmume = true;
    }
    

    g_video.hw.version_major = 4;
    g_video.hw.version_minor = 5;
    // g_video.hw.context_type  = RETRO_HW_CONTEXT_OPENGL_CORE;
    g_video.hw.context_type  = RETRO_HW_CONTEXT_OPENGL;
    g_video.hw.context_reset   = noop;
    g_video.hw.context_destroy = noop;

    // Initial context
    create_window(640, 480);
    // Load the core.
    core_load(core);
    create_window(640, 480);

    // Load the game.
    core_load_game(game);

    SDLArch::coreLoaded = true;

    // Configure the player input devices.
    for(int i = 0; i < SDLArch::MAX_PLAYERS; i++) {
        SDLArch::g_retro.retro_set_controller_port_device(i, RETRO_DEVICE_JOYPAD);
    }

    SDL_GL_MakeCurrent(SDLArch::g_win, SDLArch::g_ctx);
}

void SDLArch::closeEnv() {
    if(SDLArch::coreLoaded) {
       core_unload(); 
    }

	video_deinit();
    SDLArch::gameLoaded = false;
    SDLArch::coreLoaded = false;

    if (SDLArch::g_win) {
        SDLArch::g_win = NULL;
    }
    
    if (SDLArch::g_ctx) {
        SDLArch::g_ctx = NULL;
    }

    if (g_vars) {
        for (const struct retro_variable *v = g_vars; v->key; ++v) {
            free((char*)v->key);
            free((char*)v->value);
        }
        free(g_vars);
    }

    SDL_Quit();
    SDLArch::audioData.clear();
    SDLArch::g_last_frame_buffer.clear();
}

// #ifdef __cplusplus
// }
// #endif