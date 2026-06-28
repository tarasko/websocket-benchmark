from websocket_rs import connect
from time import time


name = "websockets_rs"
version = "0.7.1"


async def run(args, endpoint: str, msg: bytes, duration: float, warmup_cycles_cnt: int, ssl_context):
    async with await connect(
        endpoint,
        ssl_context=ssl_context,
        compression=False,
    ) as websocket:
        start_time = 0
        websocket.send(msg)
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

            websocket.send(msg)

        return int(cnt / duration)
