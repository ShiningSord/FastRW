cmake_minimum_required(VERSION 3.14)
project(ResRW LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(Threads REQUIRED)

add_executable(random_walker
    src/main.cpp
    src/geometry.cpp
    src/simulation_config.cpp
    src/walker.cpp
)

target_include_directories(random_walker PRIVATE
    ${CMAKE_SOURCE_DIR}/include
    ${CMAKE_SOURCE_DIR}/third_party/nlohmann
)

target_link_libraries(random_walker PRIVATE Threads::Threads)

option(FASTRW_ENABLE_CUDA "Build the experimental NVIDIA CUDA backend (not rigorously tested)" OFF)

if(FASTRW_ENABLE_CUDA)
    include(CheckLanguage)
    if(CMAKE_VERSION VERSION_LESS 3.18)
        message(FATAL_ERROR "The experimental CUDA backend requires CMake 3.18 or newer")
    endif()
    if(NOT DEFINED CMAKE_CUDA_ARCHITECTURES)
        set(CMAKE_CUDA_ARCHITECTURES 86)
    endif()
    check_language(CUDA)
    if(CMAKE_CUDA_COMPILER)
        enable_language(CUDA)
        set(CMAKE_CUDA_STANDARD 17)
        set(CMAKE_CUDA_STANDARD_REQUIRED ON)

        find_package(CUDAToolkit REQUIRED)
        add_executable(random_walker_cuda
            src/main_cuda.cpp
            src/geometry.cpp
            src/simulation_config.cpp
            src/walker_cuda.cu
        )
        target_include_directories(random_walker_cuda PRIVATE
            ${CMAKE_SOURCE_DIR}/include
            ${CMAKE_SOURCE_DIR}/third_party/nlohmann
        )
        target_link_libraries(random_walker_cuda PRIVATE
            Threads::Threads
            CUDA::cudart
        )
        set_target_properties(random_walker_cuda PROPERTIES
            CUDA_SEPARABLE_COMPILATION OFF
        )
    else()
        message(FATAL_ERROR "FASTRW_ENABLE_CUDA is ON but no CUDA compiler was found")
    endif()
endif()

if(APPLE)
    enable_language(OBJCXX)

    add_executable(random_walker_metal
        src/main_metal.cpp
        src/geometry.cpp
        src/simulation_config.cpp
        src/walker_metal.mm
    )

    target_include_directories(random_walker_metal PRIVATE
        ${CMAKE_SOURCE_DIR}/include
        ${CMAKE_SOURCE_DIR}/third_party/nlohmann
    )

    target_compile_options(random_walker_metal PRIVATE
        "$<$<COMPILE_LANGUAGE:OBJCXX>:-fobjc-arc>"
    )

    target_link_libraries(random_walker_metal PRIVATE
        Threads::Threads
        "-framework Foundation"
        "-framework Metal"
    )
endif()
