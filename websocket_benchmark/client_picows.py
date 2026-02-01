from picows import WSListener, WSTransport, WSMsgType, WSFrame, ws_connect, __version__ as version
from time import time


name = "picows"


async def run(args, endpoint: str, msg: bytes, duration: int, ssl_context):
    class PicowsClientListener(WSListener):
        _transport: WSTransport
        _start_time: float
        _cnt: int

        def __init__(self):
            super().__init__()

        def on_ws_connected(self, transport: WSTransport):
            self._transport = transport
            self._start_time = time()
            self._cnt = 0
            self._transport.send(WSMsgType.BINARY, msg)

        def on_ws_frame(self, transport: WSTransport, frame: WSFrame):
            self._cnt += 1

            if time() - self._start_time >= duration:
                self.result = int(self._cnt / duration)
                self._transport.disconnect()
            else:
                self._transport.send(WSMsgType.BINARY, msg)

    (_, client) = await ws_connect(PicowsClientListener, endpoint, ssl_context=ssl_context)
    await client._transport.wait_disconnected()
    return client.result
