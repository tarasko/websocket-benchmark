import argparse
import asyncio
import importlib
import os
import platform
import ssl

from logging import getLogger
from typing import List, Dict

import numpy as np


RPS: Dict[str, List[float]] = {"ssl": [], "plain": []}
NAMES: List[str] = []
_logger = getLogger(__name__)


def create_client_ssl_context():
    ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    ssl_context.load_default_certs(ssl.Purpose.SERVER_AUTH)
    ssl_context.check_hostname = False
    ssl_context.hostname_checks_common_name = False
    ssl_context.verify_mode = ssl.CERT_NONE
    return ssl_context


def run(name, args, plain_url, ssl_url, ssl_context, msg, duration):
    m = importlib.import_module(name, ".")

    if not args.skip_plain:
        print(f"Run {m.name} plain client")
        rps = asyncio.run(m.run(args, plain_url, msg, duration, None))
        RPS["plain"].append(rps)

    if not args.skip_ssl:
        print(f"Run {m.name} ssl client")
        rps = asyncio.run(m.run(args, ssl_url, msg, duration, ssl_context))
        RPS["ssl"].append(rps)

    NAMES.append(f"{m.name}\n({m.version})")


def print_result():
    for k, v in RPS.items():
        print(k.replace("\n", " "), v)


def print_result_and_plot(loop_name, msg_size):
    print_result()
    print("names:", " | ".join(n.replace("\n", " ") for n in NAMES))

    try:
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(layout='constrained')

        x = np.arange(len(NAMES))
        width = 0.25  # the width of the bars
        multiplier = 0

        for cl_type, measurement in RPS.items():
            offset = width * multiplier
            ax.bar(x + offset, measurement, width, label=cl_type)
            multiplier += 1

        ax.set_ylabel('request/second')
        ax.set_title(f'Echo round-trip performance \n(python {platform.python_version()}, {loop_name}, msg_size={msg_size})')
        ax.set_xticks(x + width, NAMES)
        ax.legend(loc='upper left', ncols=3)

        plt.show()
    except ImportError:
        pass


def main():
    parser = argparse.ArgumentParser(description="Benchmark for the various websocket clients",
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--host", default="127.0.0.1", help="Server host")
    parser.add_argument("--plain-port", default="9001", help="Server port with plain websockets")
    parser.add_argument("--ssl-port", default="9002", help="Server port with secure websockets")
    parser.add_argument("--msg-size", default="256", help="Message size")
    parser.add_argument("--duration", default="5", help="duration of test in seconds")
    parser.add_argument("--disable-uvloop", action="store_true", help="Disable uvloop")
    parser.add_argument("--no-plot", action="store_true", help="Disable plots")
    parser.add_argument("--clients", default="websockets,aiohttp,picows,picows_cython,boost", help="Comma separated list of clients")
    parser.add_argument("--skip-plain", action="store_true", help="Disable plain client test")
    parser.add_argument("--skip-ssl", action="store_true", help="Disable ssl client test")

    args = parser.parse_args()

    msg_size = int(args.msg_size)
    msg = os.urandom(msg_size)
    duration = int(args.duration)

    loop_name = "asyncio"
    if not args.disable_uvloop:
        if os.name != 'nt':
            import uvloop
            asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
            loop_name = f"uvloop {uvloop.__version__}"

    ssl_context = create_client_ssl_context()
    plain_url = f"ws://{args.host}:{args.plain_port}/"
    ssl_url = f"wss://{args.host}:{args.ssl_port}/"

    modules = (f"websocket_benchmark.client_{c}" for c in args.clients.split(","))

    for m in modules:
        run(m, args, plain_url, ssl_url, ssl_context, msg, duration)

    if not args.no_plot:
        print_result_and_plot(loop_name, msg_size)


if __name__ == '__main__':
    main()
