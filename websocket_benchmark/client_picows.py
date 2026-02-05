from picows import WSListener, WSTransport, WSMsgType, WSFrame, ws_connect, __version__ as version
from time import time


name = "picows"


async def run(args, endpoint: str, msg: bytes, duration: float, warmup_cycles_cnt: int, ssl_context):
    class PicowsClientListener(WSListener):
        _transport: WSTransport
        _start_time: float
        _warmup_cycles_cnt: int
        _cnt: int

        def on_ws_connected(self, transport: WSTransport):
            self._transport = transport
            if warmup_cycles_cnt == 0:
                self._start_time = time()
            else:
                self._start_time = 0
            self._warmup_cycles_cnt = warmup_cycles_cnt
            self._cnt = 0
            self._transport.send(WSMsgType.BINARY, msg)

        def on_ws_frame(self, transport: WSTransport, frame: WSFrame):
            if self._warmup_cycles_cnt > 0:
                self._warmup_cycles_cnt -= 1
                if self._warmup_cycles_cnt == 0:
                    self._start_time = time()
            else:
                self._cnt += 1

                if time() - self._start_time >= duration:
                    self.result = int(self._cnt / duration)
                    self._transport.disconnect()
                    return

            self._transport.send(WSMsgType.BINARY, msg)

    (_, client) = await ws_connect(PicowsClientListener, endpoint, ssl_context=ssl_context)
    await client._transport.wait_disconnected()
    return client.result
