from logging import getLogger
from libc.errno cimport errno

from picows.picows cimport WSFrame, WSTransport, WSListener, WSMsgType
from picows import ws_connect, __version__ as version

from time import time

_logger = getLogger(__name__)


name = "picows_cyt"


cdef class EchoClientListener(WSListener):
    cdef:
        WSTransport _transport
        double _start_time
        double _duration
        int _warmup_cycles_cnt
        int _cnt
        bytes _data
        readonly int rps

    def __init__(self, bytes data, double duration, int warmup_cycles_cnt):
        super().__init__()
        self._transport = None
        self._start_time = 0
        self._duration = duration
        self._warmup_cycles_cnt = warmup_cycles_cnt
        self._cnt = 0
        self._data = data
        self.rps = 0

    cpdef on_ws_connected(self, WSTransport transport):
        self._transport = transport
        if self._warmup_cycles_cnt == 0:
            self._start_time = time()
        self._transport.send(WSMsgType.BINARY, self._data)

    cpdef on_ws_frame(self, WSTransport transport, WSFrame frame):
        cdef double now = time()

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


async def run(args, url: str, data: bytes, duration: float, warmup_cycles_cnt: int, ssl_context):
    cdef EchoClientListener client
    cdef WSTransport transport
    (transport, client) = await ws_connect(lambda: EchoClientListener(data, duration, warmup_cycles_cnt),
                                   url,
                                   ssl_context=ssl_context,
                                   read_buffer_init_size = len(data) + 1024,
                                   zero_copy_unsafe_ssl_write=True)
    await transport.wait_disconnected()
    return client.rps

