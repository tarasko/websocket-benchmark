import os
import subprocess
from pathlib import Path


version = "1.90.0"
name = "c++ beast"


async def run(args, url: str, msg: bytes, duration: int, ssl_context):
    client_path = Path(os.path.dirname(__file__)) / '..' / 'build' / 'src' / 'ws_echo_client'
    working_dir = Path(os.path.dirname(__file__)) / '..'

    pr = subprocess.run([client_path,
                         b"1", # async client implements a real world epoll/recvmsg call sequence
                         b"0" if ssl_context is None else b"1",
                         args.host.encode(),
                         args.plain_port if ssl_context is None else args.ssl_port,
                         args.msg_size, args.duration],
                        shell=False, check=True, capture_output=True,
                        cwd=working_dir)
    _, rps = pr.stdout.split(b":", 2)
    return int(rps.decode())