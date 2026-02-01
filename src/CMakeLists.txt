configure_file("${Boost_INCLUDE_DIR}/boost/beast/src.hpp" "${CMAKE_BINARY_DIR}/beast_src.cpp" COPYONLY)

add_library(asio STATIC asio.cpp)
target_link_libraries(asio boost::boost openssl::openssl uring)

add_library(beast STATIC "${CMAKE_BINARY_DIR}/beast_src.cpp")
target_link_libraries(beast asio)

add_executable(ws_echo_client ws_echo_client.cpp)
target_link_libraries(ws_echo_client asio beast)

add_executable(ws_echo_server ws_echo_server.cpp)
target_link_libraries(ws_echo_server asio beast)


