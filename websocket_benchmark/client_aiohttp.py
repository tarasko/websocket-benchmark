from aiohttp import ClientSession, WSMsgType, __version__ as version
from time import time


name = "aiohttp"


async def run(args, url: str, data: bytes, duration: int, ssl_context):
    async with ClientSession() as session:
        async with session.ws_connect(url, ssl_context=ssl_context) as ws:
            # send request
            cnt = 0
            start_time = time()
            await ws.send_bytes(data)

            while True:
                msg = await ws.receive()

                if msg.type == WSMsgType.BINARY:
                    cnt += 1
                    if time() - start_time >= duration:
                        await ws.close()
                        return int(cnt/duration)
                    else:
                        await ws.send_bytes(data)
                else:
                    if msg.type == WSMsgType.CLOSE:
                        await ws.close()
                    elif msg.type == WSMsgType.ERROR:
                        print("Error during receive %s" % ws.exception())
                    elif msg.type == WSMsgType.CLOSED:
                        pass

                    break
