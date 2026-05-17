from picows.websockets import connect
from time import time


name = "picows_websockets"
from picows import __version__ as version


async def run(args, endpoint: str, msg: bytes, duration: float, warmup_cycles_cnt: int, ssl_context):
    async with connect(
        endpoint,
        ssl=ssl_context,
        compression=None,
        max_queue=None,
        max_size=None,
        ping_interval=None,
    ) as websocket:
        start_time = 0
        await websocket.send(msg)
        cnt = 0
        while True:
            await websocket.recv()
            if warmup_cycles_cnt > 0:
                warmup_cycles_cnt -= 1
                if warmup_cycles_cnt == 0:
                    start_time = time()
            else:
                cnt += 1
                if time() - start_time >= duration:
                    break

            await websocket.send(msg)

        return int(cnt / duration)

