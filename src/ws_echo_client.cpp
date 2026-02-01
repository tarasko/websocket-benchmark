 #include <boost/beast/core.hpp>
#include <boost/beast/ssl.hpp>
#include <boost/beast/websocket.hpp>
#include <boost/asio/connect.hpp>
#include <boost/asio/ip/tcp.hpp>
#include <boost/asio/ssl/stream.hpp>
#include <cstdlib>
#include <iostream>
#include <string>
#include <chrono>
#include <algorithm>
#include <thread>

namespace beast = boost::beast;         // from <boost/beast.hpp>
namespace http = beast::http;           // from <boost/beast/http.hpp>
namespace websocket = beast::websocket; // from <boost/beast/websocket.hpp>
namespace net = boost::asio;            // from <boost/asio.hpp>
namespace ssl = boost::asio::ssl;       // from <boost/asio/ssl.hpp>
using tcp = boost::asio::ip::tcp;       // from <boost/asio/ip/tcp.hpp>

template<typename UnderlyingStream>
class EchoClient
{
public:
    using Clock = std::chrono::steady_clock;

    EchoClient(net::io_context& ctx, websocket::stream<UnderlyingStream>& ws, std::string host, std::string port, size_t msgSize, std::chrono::seconds duration)
        : mIoContext(ctx)
        , mWebsocket(ws)
        , mDuration(duration)
        , mMessage(msgSize, 'a')
    {
        // Look up domain name
        tcp::resolver resolver{mIoContext};
        auto const results = resolver.resolve(host, port);

        mWebsocket.write_buffer_bytes(std::max(size_t(4096), std::min(size_t(64*1024), msgSize)));

        // Make the connection on the IP address we get from a lookup
        auto endpoint = net::connect(beast::get_lowest_layer(mWebsocket), results);
        beast::get_lowest_layer(mWebsocket).set_option(tcp::no_delay{true});

        //
        if constexpr(std::is_same_v<UnderlyingStream, beast::ssl_stream<tcp::socket>>) {
            // Perform the SSL handshake
            mWebsocket.next_layer().handshake(ssl::stream_base::client);
        }

        mWebsocket.auto_fragment(false);

        // Set a decorator to change the User-Agent of the handshake
        mWebsocket.set_option(websocket::stream_base::decorator(
            [](websocket::request_type& req)
            {
                req.set(http::field::user_agent,
                    std::string(BOOST_BEAST_VERSION_STRING) +
                        " websocket-client");
            }));

        // Update the host_ string. This will provide the value of the
        // Host HTTP header during the WebSocket handshake.
        // See https://tools.ietf.org/html/rfc7230#section-5.4
        host += ':' + std::to_string(endpoint.port());

        // Perform the websocket handshake
        mWebsocket.handshake(host, "/");

        mWebsocket.binary(true);
        mWebsocket.compress(false);
    }

    void write_read_loop(bool async)
    {
        mStartTime = Clock::now();

        if (async)
            async_write_read_loop();
        else
            sync_write_read_loop();

        // Close the WebSocket connection
        mWebsocket.close(websocket::close_code::normal);
    }

private:
    void sync_write_read_loop()
    {
        while (Clock::now() - mStartTime < mDuration)
        {
            mWebsocket.write(net::buffer(mMessage));
            mWebsocket.read(mReadBuffer);
            mReadBuffer.clear();
            mRequestCounter++;
        }
    }

    void async_write_read_loop()
    {
        mWebsocket.write(net::buffer(mMessage));
        mWebsocket.async_read(mReadBuffer, beast::bind_front_handler(&EchoClient::on_read, this));
        mIoContext.run();
    }

    void on_read(beast::error_code ec, std::size_t bytes_transferred)
    {
        boost::ignore_unused(bytes_transferred);

        if(ec)
            return on_fail(ec, "read");

        mRequestCounter++;
        mReadBuffer.clear();

        if (Clock::now() - mStartTime < mDuration)
        {
            mWebsocket.write(net::buffer(mMessage));
            mWebsocket.async_read(mReadBuffer, beast::bind_front_handler(&EchoClient::on_read, this));
        }
    }

    void on_fail(beast::error_code ec, char const* what)
    {
        throw boost::system::system_error(ec);
    }

private:
    net::io_context& mIoContext;
    websocket::stream<UnderlyingStream>& mWebsocket;
    Clock::time_point mStartTime;
    Clock::duration mDuration;
    beast::flat_buffer mReadBuffer;
    std::string mMessage;

public:
    int mRequestCounter = 0;
};

void run_plain_client(net::io_context& ioc, std::string host, std::string port, size_t msgSize, int durationSec, bool isAsync)
{
    websocket::stream<tcp::socket> ws{ioc};

    EchoClient client{ioc, ws, host, port, msgSize, std::chrono::seconds{durationSec}};
    client.write_read_loop(isAsync);

    std::cout << "plain client:" << client.mRequestCounter/durationSec << std::endl;
}

void run_secure_client(net::io_context& ioc, std::string host, std::string port, size_t msgSize, int durationSec, bool isAsync)
{
    ssl::context ctx{ssl::context::tlsv12_client};
    ctx.set_verify_mode(boost::asio::ssl::verify_none);
    ctx.set_default_verify_paths();
    websocket::stream<beast::ssl_stream<tcp::socket>> ws{ioc, ctx};

    // TODO:
    // load_root_certificates(ctx);

    EchoClient client{ioc, ws, host, port, msgSize, std::chrono::seconds{durationSec}};
    client.write_read_loop(isAsync);

    std::cout << "ssl client:" << client.mRequestCounter/durationSec << std::endl;
}

// Sends a WebSocket message and prints the response
int main(int argc, char** argv)
{
    try
    {
        // Check command line arguments.
        if(argc != 7)
        {
            std::cerr <<
                "Usage: ws_echo_client <is_async{1|0} is_secure{1|0}> <host> <port> <msg_size> <duration_sec>\n" <<
                "Example:\n" <<
                "    ws_echo_client 1 0 echo.websocket.org 80 256 10\n";
            return EXIT_FAILURE;
        }
        bool isAsync = !!atoi(argv[1]);
        bool isSecure = !!atoi(argv[2]);
        std::string host = argv[3];
        auto const  port = argv[4];
        auto const  msgSize = (size_t)atoi(argv[5]);
        auto const durationSec = atoi(argv[6]);

        // The io_context is required for all I/O
        net::io_context ioc;
        if (isSecure)
            run_secure_client(ioc, host, port, msgSize, durationSec, isAsync);
        else
            run_plain_client(ioc, host, port, msgSize, durationSec, isAsync);
    }
    catch(std::exception const& e)
    {
        std::cerr << "Error: " << e.what() << std::endl;
        return EXIT_FAILURE;
    }
    return EXIT_SUCCESS;
}
