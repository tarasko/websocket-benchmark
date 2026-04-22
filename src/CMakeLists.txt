configure_file("${Boost_INCLUDE_DIR}/boost/beast/src.hpp" "${CMAKE_BINARY_DIR}/beast_src.cpp" COPYONLY)

add_library(asio STATIC asio.cpp)
target_link_libraries(asio boost::boost openssl::openssl)

add_library(beast STATIC "${CMAKE_BINARY_DIR}/beast_src.cpp")
target_link_libraries(beast asio)

add_executable(ws_echo_client ws_echo_client.cpp)
target_link_libraries(ws_echo_client asio beast)

add_executable(ws_echo_server ws_echo_server.cpp)
target_link_libraries(ws_echo_server asio beast)

if(CMAKE_SYSTEM_NAME STREQUAL "Linux")
    add_library(asio_ur STATIC asio.cpp)
    target_link_libraries(asio_ur boost::boost openssl::openssl uring)
    target_compile_definitions(asio_ur PUBLIC BOOST_ASIO_HAS_IO_URING=1)
    target_compile_definitions(asio_ur PUBLIC BOOST_ASIO_DISABLE_EPOLL=1)

    add_library(beast_ur STATIC "${CMAKE_BINARY_DIR}/beast_src.cpp")
    target_link_libraries(beast_ur asio_ur)

    add_executable(ws_echo_client_ur ws_echo_client.cpp)
    target_link_libraries(ws_echo_client_ur beast_ur)

    add_executable(ws_echo_server_ur ws_echo_server.cpp)
    target_link_libraries(ws_echo_server_ur beast_ur)
endif()