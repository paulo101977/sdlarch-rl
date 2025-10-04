cmake_minimum_required(VERSION 3.12)
project(sdlarch_rl LANGUAGES C CXX)

if(CMAKE_SOURCE_DIR STREQUAL CMAKE_BINARY_DIR)
    message(FATAL_ERROR "
    WARNING: Do not build from the source folder!
    Please use a separate build folder:

    use: 
    cmake -B build -S . -DCMAKE_BUILD_TYPE=Release
    cmake --build build
    ")
endif()

# Define the default build type
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

if(CMAKE_BUILD_TYPE STREQUAL "Debug")
    add_definitions(-DDEBUG)
    message(STATUS "Debug mode: DEBUG macro defined")
else()
    message(STATUS "Release mode: DEBUG macro not defined")
endif()

message(STATUS "Build type: ${CMAKE_BUILD_TYPE}")

set(SRC_FOLDER ${CMAKE_SOURCE_DIR}/src)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY_DEBUG ${CMAKE_BINARY_DIR}/Debug)
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY_DEBUG ${CMAKE_BINARY_DIR}/Debug)
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_DEBUG ${CMAKE_BINARY_DIR}/Debug)

set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY_RELEASE ${CMAKE_BINARY_DIR}/Release)
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY_RELEASE ${CMAKE_BINARY_DIR}/Release)
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_RELEASE ${CMAKE_BINARY_DIR}/Release)

add_definitions(-DGLAD_GLAPI_EXPORT)
add_definitions(-DGLAD_GLAPI_EXPORT_BUILD)

add_subdirectory("third-party/pybind11")

find_package(Python3 COMPONENTS Development REQUIRED)
# find_package(pybind11 REQUIRED)

if(UNIX AND NOT APPLE AND NOT PYTHON3_EXTENSION_SUFFIX)
    set(PYTHON3_EXTENSION_SUFFIX ".so")
    message(STATUS "Setting manual Python extension suffix: ${PYTHON3_EXTENSION_SUFFIX}")
endif()

message(STATUS "Python include dirs: ${Python3_INCLUDE_DIRS}")
message(STATUS "Python library: ${Python3_LIBRARIES}")
message(STATUS "pybind11 found: ${pybind11_FOUND}")

if(WIN32)
    set(CMAKE_WINDOWS_EXPORT_ALL_SYMBOLS ON)
    add_definitions(-D_WINDOWS -D_USRDLL)

    set(SDL2_POSSIBLE_PATHS
        "C:/SDL2"
        "C:/Program Files/SDL2"
        "D:/SDL2"
        "C:/Program Files (x86)/SDL2"
        "${CMAKE_SOURCE_DIR}/SDL2"
        "${CMAKE_SOURCE_DIR}/../SDL2"
    )
    
    find_path(SDL2_INCLUDE_DIR SDL.h
        PATHS ${SDL2_POSSIBLE_PATHS}
        PATH_SUFFIXES include
    )
    
    find_library(SDL2_LIBRARY
        NAMES SDL2
        PATHS ${SDL2_POSSIBLE_PATHS}
        PATH_SUFFIXES lib/x64 lib lib64
    )
    
    if(SDL2_INCLUDE_DIR AND SDL2_LIBRARY)
        message(STATUS "Found SDL2: ${SDL2_LIBRARY}")
        set(SDL2_FOUND TRUE)
    else()
        message(FATAL_ERROR "SDL2 not found! Please install SDL2 or set SDL2_ROOT")
    endif()

else()
    # Linux/WSL
    find_package(SDL2 REQUIRED)
    find_package(OpenGL REQUIRED)
    set(SDL2_FOUND TRUE)
endif()

add_library(glad STATIC ${SRC_FOLDER}/glad.c)
set_target_properties(glad PROPERTIES
    POSITION_INDEPENDENT_CODE ON
)

add_library(pcsx2_headless SHARED
    ${SRC_FOLDER}/sdlarch.cpp
)

pybind11_add_module(_retro
    ${SRC_FOLDER}/retroemulator.cpp
    ${SRC_FOLDER}/sdlarch.cpp
    ${SRC_FOLDER}/glad.c
)

target_include_directories(pcsx2_headless PRIVATE
    ${SDL2_INCLUDE_DIR}
    ${Python3_INCLUDE_DIRS}
    ${pybind11_INCLUDE_DIRS}
    .
)



target_include_directories(_retro PRIVATE
    ${SDL2_INCLUDE_DIR}
    ${Python3_INCLUDE_DIRS}
    ${pybind11_INCLUDE_DIRS}
    .
)

target_include_directories(glad PRIVATE
    .
)

if(WIN32)
    target_link_libraries(pcsx2_headless PRIVATE
        glad  
        ${SDL2_LIBRARY}
        opengl32.lib
        ${Python3_LIBRARIES}
    )
    
    target_link_libraries(_retro PRIVATE
        pcsx2_headless
        ${SDL2_LIBRARY}
        opengl32.lib
        ${Python3_LIBRARIES}
        pybind11::module
    )
    
    # set_target_properties(pcsx2_headless PROPERTIES
    #     PREFIX ""
    #     SUFFIX ".dll"
    # )
    
    set_target_properties(_retro PROPERTIES
        OUTPUT_NAME "_retro"
        SUFFIX ".pyd"
        PREFIX ""
    )
    
else()
    # Linux/WSL
    target_link_libraries(pcsx2_headless PRIVATE
        SDL2::SDL2
        OpenGL::GL
        dl
        pthread
        ${Python3_LIBRARIES}
    )
    
    target_link_libraries(_retro PRIVATE
        pcsx2_headless
        SDL2::SDL2
        OpenGL::GL
        dl
        pthread
        ${Python3_LIBRARIES}
        pybind11::module
    )
    
    # set_target_properties(pcsx2_headless PROPERTIES
    #     PREFIX ""
    #     SUFFIX ".so"
    # )
    
    set_target_properties(_retro PROPERTIES
        OUTPUT_NAME "_retro"
        SUFFIX "${PYTHON3_EXTENSION_SUFFIX}"
        PREFIX ""
    )
endif()

set_source_files_properties(${SRC_FOLDER}/glad.c PROPERTIES
    LANGUAGE C
    C_STANDARD 11
)

message(STATUS "Platform: ${CMAKE_SYSTEM_NAME}")
message(STATUS "Building for: ${CMAKE_SYSTEM}")
message(STATUS "SDL2 include: ${SDL2_INCLUDE_DIR}")
message(STATUS "SDL2 library: ${SDL2_LIBRARY}")
message(STATUS "Python version: ${Python3_VERSION}")
message(STATUS "Python extension suffix: ${PYTHON3_EXTENSION_SUFFIX}")

# install(TARGETS pcsx2_headless
#     RUNTIME DESTINATION bin
#     LIBRARY DESTINATION lib
#     ARCHIVE DESTINATION lib
# )

# install(TARGETS _retro
#     LIBRARY DESTINATION lib
# )

# copy artifacts fn
function(copy_artifacts_target target_name)
    add_custom_command(TARGET ${target_name} POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E copy
            $<TARGET_FILE:${target_name}>
            ${CMAKE_SOURCE_DIR}/
        COMMENT "Copying ${target_name} from ${CMAKE_BUILD_TYPE} to project root"
    )
endfunction()

# apply to both targets
copy_artifacts_target(pcsx2_headless)
copy_artifacts_target(_retro)

# add_custom_target(copy_all_artifacts
#     COMMAND ${CMAKE_COMMAND} -E copy
#         ${CMAKE_LIBRARY_OUTPUT_DIRECTORY}/${CMAKE_BUILD_TYPE}/*
#         ${CMAKE_SOURCE_DIR}/
#     COMMENT "Copying all artifacts to project root"
#     DEPENDS pcsx2_headless _retro
# )