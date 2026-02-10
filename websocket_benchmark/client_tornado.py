import socket
from time import time

from tornado.httpclient import HTTPRequest
from tornado.websocket import websocket_connect

name = "tornado"
from tornado import version


async def run(args, url: str, msg: bytes, duration: float, warmup_cycles_cnt: int, ssl_context):
    req = HTTPRequest(
        url=url,
        ssl_options=ssl_context,
        connect_timeout=5,
        request_timeout=10,
    )

    websocket = await websocket_connect(req)
    websocket.stream.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    start_time = 0
    await websocket.write_message(msg, True)
    cnt = 0
    while True:
        await websocket.read_message()
        if warmup_cycles_cnt > 0:
            warmup_cycles_cnt -= 1
            if warmup_cycles_cnt == 0:
                start_time = time()
        else:
            cnt += 1
            if time() - start_time >= duration:
                break

        await websocket.write_message(msg, True)

    websocket.close()

    return int(cnt / duration)

