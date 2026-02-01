#include <boost/beast/core.hpp>
#include <boost/beast/ssl.hpp>
#include <boost/beast/websocket.hpp>
#include <boost/beast/websocket/ssl.hpp>
#include <boost/asio/buffer.hpp>
#include <boost/asio/ssl.hpp>
#include <algorithm>
#include <cstdlib>
#include <functional>
#include <iostream>
#include <memory>
#include <string>

namespace beast = boost::beast;         // from <boost/beast.hpp>
namespace http = beast::http;           // from <boost/beast/http.hpp>
namespace websocket = beast::websocket; // from <boost/beast/websocket.hpp>
namespace net = boost::asio;            // from <boost/asio.hpp>
namespace ssl = boost::asio::ssl;
using tcp = boost::asio::ip::tcp;       // from <boost/asio/ip/tcp.hpp>

//------------------------------------------------------------------------------

double get_now()
{
    using clock = std::chrono::system_clock;
    using dsec = std::chrono::duration<double>;
    using tps = std::chrono::time_point<clock, dsec>;
    tps tp = clock::now();
    return tp.time_since_epoch().count();
}


// Report a failure
void fail(beast::error_code ec, char const* what)
{
    std::cerr << what << ": " << ec.message() << "\n";
}

// Echoes back all received WebSocket messages
template<typename UnderlyingStream>
class session : public std::enable_shared_from_this<session<UnderlyingStream>>
{
    websocket::stream<UnderlyingStream> ws_;
    beast::flat_buffer buffer_;

public:
    // Take ownership of the socket
    explicit session(websocket::stream<UnderlyingStream>&& ws)
        : ws_(std::move(ws))
    {
    }

    // Get on the correct executor
    void run()
    {
        ws_.auto_fragment(false);
        ws_.write_buffer_bytes(128*1024);
        beast::get_lowest_layer(ws_).socket().set_option(tcp::no_delay{true});
        beast::get_lowest_layer(ws_).socket().set_option(net::socket_base::receive_buffer_size(256 * 1024));

        if constexpr(std::is_same_v<UnderlyingStream, beast::ssl_stream<beast::tcp_stream>>)
        {
            beast::get_lowest_layer(ws_).expires_after(std::chrono::seconds(5));

             // Perform the SSL handshake
            ws_.next_layer().async_handshake(
                        ssl::stream_base::server,
                        beast::bind_front_handler(&session::on_ssl_handshake, session<UnderlyingStream>::shared_from_this()));
        }
        else
        {
            // Set suggested timeout settings for the websocket
            ws_.set_option(websocket::stream_base::timeout::suggested(beast::role_type::server));

            // Set a decorator to change the Server of the handshake
            ws_.set_option(websocket::stream_base::decorator(
                [](websocket::response_type& res)
                {
                    res.set(http::field::server,
                        std::string(BOOST_BEAST_VERSION_STRING) +
                            " websocket-server-async");
                }));

            // Accept the websocket handshake
            ws_.async_accept(beast::bind_front_handler(
                                 &session<UnderlyingStream>::on_websocket_handshake_done,
                                 session<UnderlyingStream>::shared_from_this()));
        }
    }

    void on_ssl_handshake(beast::error_code ec)
    {
        if(ec)
            return fail(ec, "handshake");

        // Turn off the timeout on the tcp_stream, because
        // the websocket stream has its own timeout system.
        beast::get_lowest_layer(ws_).expires_never();

        // Set suggested timeout settings for the websocket
        ws_.set_option(
            websocket::stream_base::timeout::suggested(
                beast::role_type::server));

        // Set a decorator to change the Server of the handshake
        ws_.set_option(websocket::stream_base::decorator(
            [](websocket::response_type& res)
            {
                res.set(http::field::server,
                    std::string(BOOST_BEAST_VERSION_STRING) +
                        " websocket-server-async-ssl");
            }));

        // Accept the websocket handshake
        ws_.async_accept(beast::bind_front_handler(
                             &session<UnderlyingStream>::on_websocket_handshake_done,
                             session<UnderlyingStream>::shared_from_this()));
    }

    void on_websocket_handshake_done(beast::error_code ec)
    {
        if(ec)
            return fail(ec, "accept");

        // Read a message
        do_read();
    }

    void do_read()
    {
        // Read a message into our buffer
        ws_.async_read(buffer_, beast::bind_front_handler(
                           &session<UnderlyingStream>::on_read,
                           session<UnderlyingStream>::shared_from_this()));
    }

    void on_read(beast::error_code ec, std::size_t bytes_transferred)
    {
        boost::ignore_unused(bytes_transferred);

        // This indicates that the session was closed
        if(ec == websocket::error::closed)
            return;

        if(ec)
            return fail(ec, "read");

        // Echo the message
        ws_.text(ws_.got_text());
        ws_.async_write(buffer_.data(), beast::bind_front_handler(
                            &session<UnderlyingStream>::on_write,
                            session<UnderlyingStream>::shared_from_this()));

    }

    void on_write(beast::error_code ec, std::size_t bytes_transferred)
    {
        if(ec)
            return fail(ec, "write");

        // Clear the buffer
        buffer_.consume(bytes_transferred);

        do_read();
    }
};

//------------------------------------------------------------------------------

// Accepts incoming connections and launches the sessions
class listener : public std::enable_shared_from_this<listener>
{
    net::io_context& ioc_;
    ssl::context& ctx_;
    tcp::acceptor acceptor_;
    bool secure_;

public:
    listener(net::io_context& ioc, ssl::context& ctx, tcp::endpoint endpoint, bool secure)
        : ioc_(ioc)
        , ctx_(ctx)
        , acceptor_(ioc)
        , secure_{secure}
    {
        beast::error_code ec;

        // Open the acceptor
        acceptor_.open(endpoint.protocol(), ec);
        if(ec)
        {
            fail(ec, "open");
            return;
        }

        // Allow address reuse
        acceptor_.set_option(net::socket_base::reuse_address(true), ec);
        if(ec)
        {
            fail(ec, "set_option");
            return;
        }

        // Bind to the server address
        acceptor_.bind(endpoint, ec);
        if(ec)
        {
            fail(ec, "bind");
            return;
        }

        // Start listening for connections
        acceptor_.listen(net::socket_base::max_listen_connections, ec);
        if(ec)
        {
            fail(ec, "listen");
            return;
        }
    }

    // Start accepting incoming connections
    void start_accepting()
    {
        // The new connection gets its own strand
        acceptor_.async_accept(beast::bind_front_handler(&listener::on_accept, shared_from_this()));
    }

private:
    void on_accept(beast::error_code ec, tcp::socket socket)
    {
        if(ec)
        {
            fail(ec, "accept");
        }
        else
        {
            if (secure_)
            {
                websocket::stream<beast::ssl_stream<beast::tcp_stream>> ws{std::move(socket), ctx_};
                std::make_shared<session<beast::ssl_stream<beast::tcp_stream>>>(std::move(ws))->run();
            }
            else
            {
                websocket::stream<beast::tcp_stream> ws{std::move(socket)};
                std::make_shared<session<beast::tcp_stream>>(std::move(ws))->run();
            }
        }

        // Accept another connection
        start_accepting();
    }
};

//------------------------------------------------------------------------------

int main(int argc, char* argv[])
{
    // Check command line arguments.
    if (argc != 4)
    {
        std::cerr <<
            "Usage: websocket-server-async <address> <plain_port> <ssl_port>\n" <<
            "Example:\n" <<
            "    ws_echo_server 127.0.0.1 9001 9002\n";
        return EXIT_FAILURE;
    }
    auto const address = net::ip::make_address(argv[1]);
    auto const plainPort = static_cast<unsigned short>(std::atoi(argv[2]));
    auto const sslPort = static_cast<unsigned short>(std::atoi(argv[3]));

    // The io_context is required for all I/O
    net::io_context ioc{BOOST_ASIO_CONCURRENCY_HINT_UNSAFE};
    ssl::context ctx{ssl::context::tlsv12};

    ctx.set_verify_mode(boost::asio::ssl::verify_none);
    ctx.set_default_verify_paths();
    ctx.use_certificate_file("cert/test.crt", ssl::context::pem);
    ctx.use_private_key_file("cert/test.key", ssl::context::pem);

    // Create and launch a listening port
    std::make_shared<listener>(ioc, ctx, tcp::endpoint{address, plainPort}, false)->start_accepting();
    std::make_shared<listener>(ioc, ctx, tcp::endpoint{address, sslPort}, true)->start_accepting();

    for(;;) try
    {
        ioc.run();
        break;
    }
    catch (std::exception& ex)
    {
        std::cerr << "io_context::run exception " << ex.what() << std::endl;
    }

    return EXIT_SUCCESS;
}
