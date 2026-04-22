cmake_minimum_required(VERSION 3.16)

project(websocket-benchmark)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CONAN_SYSTEM_INCLUDES ON)

set(Boost_USE_STATIC_LIBS ON)

find_package(Boost REQUIRED asio beast)
find_package(OpenSSL REQUIRED)

if (NOT "${CMAKE_CXX_COMPILER_ID}" STREQUAL "MSVC")
        add_compile_options(-march=native -mtune=native)
        add_compile_definitions(BOOST_ASIO_DISABLE_THREADS=1)
else()
        add_compile_options(/bigobj)
endif()
add_compile_definitions(BOOST_ASIO_DISABLE_VISIBILITY=1)
add_compile_definitions(BOOST_ASIO_NO_DEPRECATED=1)
add_compile_definitions(BOOST_ASIO_SEPARATE_COMPILATION=1)

add_compile_definitions(BOOST_BEAST_SEPARATE_COMPILATION=1)

add_subdirectory(src)
