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

option(FASTRW_ENABLE_CUDA "Build the NVIDIA CUDA backend when a CUDA compiler is available" ON)

if(FASTRW_ENABLE_CUDA)
    include(CheckLanguage)
    if(MSVC AND NOT CMAKE_CUDA_FLAGS MATCHES "allow-unsupported-compiler")
        set(CMAKE_CUDA_FLAGS
            "${CMAKE_CUDA_FLAGS} -allow-unsupported-compiler -D_ALLOW_COMPILER_AND_STL_VERSION_MISMATCH"
            CACHE STRING "CUDA compiler flags" FORCE)
    endif()
    check_language(CUDA)
    if(CMAKE_CUDA_COMPILER)
        enable_language(CUDA)
        set(CMAKE_CUDA_STANDARD 17)
        set(CMAKE_CUDA_STANDARD_REQUIRED ON)

        if(NOT DEFINED CMAKE_CUDA_ARCHITECTURES)
            # RTX 30-series (including the RTX 3050 Ti) uses compute capability 8.6.
            set(CMAKE_CUDA_ARCHITECTURES 86)
        endif()

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
        if(MSVC)
            target_compile_options(random_walker_cuda PRIVATE
                $<$<COMPILE_LANGUAGE:CUDA>:-allow-unsupported-compiler>
            )
        endif()
    else()
        message(STATUS "CUDA compiler not found; random_walker_cuda will not be built")
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
