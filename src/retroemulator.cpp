#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include "sdlarch.h"

namespace py = pybind11;

class RetroEmulator {

    private:
        SDLArch sdlarch;

    public:
        RetroEmulator() {

            if(SDLArch::coreLoaded) {
                throw std::runtime_error(
                    "Cannot create multiple emulator instances per process, make sure to "
                    "call env.close() on each environment before creating a new one"
                );
            }
            
        }
    
    
        double getFrameRate() { 
            return  sdlarch.avInfo.timing.fps;
        }

        double getAudioRate() { 
            return  sdlarch.avInfo.timing.sample_rate;
        }

        int getAudioSamples() { 
            return (int)(SDLArch::audioData.size()) / 2; 
        }
        const int16_t* getAudioData() {
            return SDLArch::audioData.data(); 
        }

        py::array_t<int16_t> getAudio() {
            py::array_t<int16_t> arr(py::array::ShapeContainer{ getAudioSamples(), 2 });
            int16_t* data = arr.mutable_data();
            memcpy(data, getAudioData(), getAudioSamples() * 4);
            return arr;
        }

        void initCore(char *core, char *game, int id) {
            sdlarch.init(core, game, id);
        }

        void runCore() {
            sdlarch.run();
        }

        void runCoreAlone() {
            sdlarch.runAlone();
        }

        void resetCore() {
            sdlarch.reset();
        }

        void closeCore() {
            sdlarch.closeEnv();
        }

        bool setState(py::bytes o) {
            try {
                return SDLArch::g_retro.retro_unserialize(PyBytes_AsString(o.ptr()), PyBytes_Size(o.ptr()));
            } catch(...) {
                return false;
            }
            
        }

        py::bytes getState() {
            size_t size = sdlarch.get_state_size();
            py::bytes bytes(NULL, size);
            SDLArch::g_retro.retro_serialize(PyBytes_AsString(bytes.ptr()), size);
            return bytes;
        }

        void* getMemoryPointer() {
            return SDLArch::g_retro.retro_get_memory_data(RETRO_MEMORY_SYSTEM_RAM);
        }

        py::array_t<uint8_t> getMemoryByType(unsigned type) {
            // Get memory pointer and size from core
            void* memory_data =  SDLArch::g_retro.retro_get_memory_data(type);
            size_t memory_size =  SDLArch::g_retro.retro_get_memory_size(type);
            
            if (!memory_data || memory_size == 0) {
                throw std::runtime_error("Invalid memory region or not available");
            }
            
            // Create a numpy array that references the memory without copying
            py::array_t<uint8_t> array(
                {memory_size},                            // shape
                {sizeof(uint8_t)},                        // strides
                static_cast<uint8_t*>(memory_data),       // data pointer
                py::capsule(memory_data, [](void* f) {})  // capsule (no deleter since we don't own the memory)
            );
            
            return array;
        }

        void setVariable(const std::string& key, const std::string& value) {
             sdlarch.set_variable(key, value);
        }

        py::array_t<uint8_t> getRAM() {
            return getMemoryByType(RETRO_MEMORY_SYSTEM_RAM);
        }

        void getFrame(py::buffer buf, int width, int height) {
            py::buffer_info info = buf.request();

            uint8_t* buffer = static_cast<uint8_t*>(info.ptr);

            sdlarch.get_frame(buffer, width, height);
        }

        py::tuple getShape() {
            return py::make_tuple(SDLArch::g_retro.height, SDLArch::g_retro.width);
        }

        void setButtonMask(py::array_t<uint8_t> mask, unsigned player) {
            if (mask.size() >  sdlarch.N_BUTTONS) {
                throw std::runtime_error("mask.size() > N_BUTTONS");
            }
            if (player >=  sdlarch.MAX_PLAYERS) {
                throw std::runtime_error("player >= MAX_PLAYERS");
            }

            for (int key = 0; key < mask.size(); ++key) {
                sdlarch.set_key(player, key, mask.data()[key]);
            }
        }

        void reloadGame() {
            if (!sdlarch.gameLoaded || !SDLArch::m_romPath) {
               SDLArch::c_printf("Warning: core or game not loaded.\n");
                return;
            }
            SDLArch::c_printf("Reloading game to apply variables...\n");
            SDLArch::unload_game();
            SDLArch::core_load_game(SDLArch::m_romPath);
        }
};

PYBIND11_MODULE(_retro, m) {
    py::class_<RetroEmulator>(m, "RetroEmulator")
        .def(py::init<>())
        .def("run", &RetroEmulator::runCore)
        .def("reset", &RetroEmulator::resetCore)
        .def("set_button_mask", &RetroEmulator::setButtonMask, py::arg("mask"), py::arg("player")=0)
        .def("get_state", &RetroEmulator::getState)
        .def("set_state", &RetroEmulator::setState)
        .def("get_frame", &RetroEmulator::getFrame, py::arg("buffer"), py::arg("width"), py::arg("height"))
        .def("get_shape", &RetroEmulator::getShape)
        .def("get_ram", &RetroEmulator::getRAM)
        .def("close", &RetroEmulator::closeCore)
        .def("init", &RetroEmulator::initCore, py::arg("core"), py::arg("game"), py::arg("id")=-1)
        .def("get_frame_rate", &RetroEmulator::getFrameRate)
        .def("get_audio_rate", &RetroEmulator::getAudioRate)
        .def("get_audio", &RetroEmulator::getAudio)
        .def("run_alone", &RetroEmulator::runCoreAlone)
        .def("set_variable", &RetroEmulator::setVariable, py::arg("key"), py::arg("value"))
        .def("reload_game", &RetroEmulator::reloadGame)
        .def("get_memory_pointer", &RetroEmulator::getMemoryPointer);
}