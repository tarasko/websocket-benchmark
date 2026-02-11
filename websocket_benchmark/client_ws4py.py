import socket
from time import time
import wsaccel

from ws4py.client.threadedclient import WebSocketClient
from ws4py import __version__ as version

name = "ws4py"


wsaccel.patch_ws4py()


async def run(args, url: str, msg: bytes, duration: float, warmup_cycles_cnt: int, ssl_context):
    class Client(WebSocketClient):
        _start_time: float
        _warmup_cycles_cnt: int
        _cnt: int

        def opened(self):
            self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

            if warmup_cycles_cnt == 0:
                self._start_time = time()
            else:
                self._start_time = 0
            self._warmup_cycles_cnt = warmup_cycles_cnt
            self._cnt = 0
            self.send(msg, True)

        def received_message(self, m):
            if self._warmup_cycles_cnt > 0:
                self._warmup_cycles_cnt -= 1
                if self._warmup_cycles_cnt == 0:
                    self._start_time = time()
            else:
                self._cnt += 1

                if time() - self._start_time >= duration:
                    self.result = int(self._cnt / duration)
                    self.close()
                    return

            self.send(msg, True)

    ws = Client(url)
    ws.connect()
    ws.run_forever()
    return ws.result
