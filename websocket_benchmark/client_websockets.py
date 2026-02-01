from websockets import connect, __version__ as version
from time import time


name = "websockets"


async def run(args, endpoint: str, msg: bytes, duration: int, ssl_context):
    async with connect(
        endpoint,
        ssl=ssl_context,
        compression=None,
        max_queue=None,
        max_size=None,
        ping_interval=None,
    ) as websocket:
        await websocket.send(msg)
        start_time = time()
        cnt = 0
        while True:
            await websocket.recv()
            cnt += 1
            if time() - start_time >= duration:
                break
            else:
                await websocket.send(msg)

        return int(cnt / duration)

