from picows import ws_connect, __version__ as version
from .picows_listener import EchoClientListener


name = "picows_core"


async def run(args, endpoint: str, msg: bytes, duration: float, warmup_cycles_cnt: int, ssl_context):
    (transport, client) = await ws_connect(lambda: EchoClientListener(msg, duration, warmup_cycles_cnt),
                                   endpoint,
                                   ssl_context=ssl_context,
                                   read_buffer_init_size=len(msg) + 1024,
                                   use_aiofastnet=True)
    await transport.wait_disconnected()
    return client.rps
