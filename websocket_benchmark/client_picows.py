from picows import WSListener, WSTransport, WSMsgType, WSFrame, ws_connect, __version__ as version
from time import time
from typing import Optional


name = "picows"


class EchoClientListener(WSListener):
    _transport: Optional[WSTransport]
    _start_time: float
    _duration: float
    _warmup_cycles_cnt: int
    _cnt: int
    _data: bytes

    rps: int

    def __init__(self, data, duration, warmup_cycles_cnt):
        super().__init__()
        self._transport = None
        self._start_time = 0
        self._duration = duration
        self._warmup_cycles_cnt = warmup_cycles_cnt
        self._cnt = 0
        self._data = data
        self.rps = 0

    def on_ws_connected(self, transport: WSTransport):
        self._transport = transport
        if self._warmup_cycles_cnt == 0:
            self._start_time = time()
        self._transport.send(WSMsgType.BINARY, self._data)

    def on_ws_frame(self, transport: WSTransport, frame: WSFrame):
        now = time()

        if self._warmup_cycles_cnt > 0:
            self._warmup_cycles_cnt -= 1
            if self._warmup_cycles_cnt == 0:
                self._start_time = now
        else:
            self._cnt += 1

            if now - self._start_time >= self._duration:
                self.rps = int(self._cnt / self._duration)
                self._transport.disconnect()
                return

        self._transport.send(WSMsgType.BINARY, self._data)


async def run(args, endpoint: str, msg: bytes, duration: float, warmup_cycles_cnt: int, ssl_context):
    (transport, client) = await ws_connect(lambda: EchoClientListener(msg, duration, warmup_cycles_cnt),
                                   endpoint,
                                   ssl_context=ssl_context,
                                   read_buffer_init_size=len(msg) + 1024,
                                   zero_copy_unsafe_ssl_write=True)
    await transport.wait_disconnected()
    return client.rps
