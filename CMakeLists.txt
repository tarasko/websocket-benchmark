cmake_minimum_required(VERSION 3.16)

project(websocket-benchmark)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CONAN_SYSTEM_INCLUDES ON)

set(Boost_USE_STATIC_LIBS ON)

find_package(Boost REQUIRED)
find_package(OpenSSL REQUIRED)

add_definitions(-march=native -mtune=native)
add_definitions(-DBOOST_ASIO_DISABLE_VISIBILITY=1)
add_definitions(-DBOOST_ASIO_NO_DEPRECATED=1)
add_definitions(-DBOOST_ASIO_SEPARATE_COMPILATION=1)
add_definitions(-DBOOST_ASIO_DISABLE_THREADS=1)

add_definitions(-DBOOST_BEAST_SEPARATE_COMPILATION=1)

# add_definitions(-DBOOST_ASIO_HAS_IO_URING=1)
# add_definitions(-DBOOST_ASIO_DISABLE_EPOLL=1)

add_subdirectory(src)
