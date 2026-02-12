import argparse
import asyncio
import importlib
import os
import platform
import pstats
import ssl
import cProfile
from pathlib import Path
from pstats import SortKey

import uvloop

from logging import getLogger
import numpy as np
import pandas as pd

_logger = getLogger(__name__)


def create_client_ssl_context():
    ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    ssl_context.load_default_certs(ssl.Purpose.SERVER_AUTH)
    ssl_context.check_hostname = False
    ssl_context.hostname_checks_common_name = False
    ssl_context.verify_mode = ssl.CERT_NONE
    return ssl_context


def print_result_and_plot(msg_size, results: pd.DataFrame, save_plot):
    colors_map = {
        "tornado": "aquamarine",
        "ws4py": "lightsteelblue",
        "websockets": "orange",
        "aiohttp": "green",
        "picows": "red",
        "picows_cyt": "darkred",
        "boost": "black"
    }

    try:
        import matplotlib.pyplot as plt

        clients = results.index
        client_names = results.index + "-" + results.version
        data = results.drop(columns=["version"])
        tests = [n.replace('-', '\n') for n in data.columns]

        x = np.arange(len(tests))
        width = 0.08

        plt.figure(figsize = (8, 4))

        for i, (client, name) in enumerate(zip(clients, client_names)):
            plt.bar(
                x + i * width,
                data.loc[client],
                width,
                label=name,
                color=colors_map.get(client)
            )

        plt.xticks(x + width * (len(clients) - 1) / 2, tests)
        plt.ylabel("request/second")
        plt.title(f'Echo round-trip performance \n(asyncio-{platform.python_version()}, uvloop-{uvloop.__version__}, msg_size={msg_size})')
        plt.legend()
        plt.tight_layout()
        plt.grid(axis='y', linestyle = '--', linewidth = 0.5)

        if save_plot:
            png_path = Path(os.path.dirname(
                __file__)) / '..' / 'results' / f'benchmark-{msg_size}.png'
            data_path = Path(os.path.dirname(
                __file__)) / '..' / 'results' / f'benchmark-{msg_size}.csv'
            plt.savefig(png_path, dpi=150, bbox_inches="tight")
            plt.close()

            results.to_csv(data_path)
        else:
            plt.show()
    except ImportError:
        pass


def main():
    parser = argparse.ArgumentParser(description="Benchmark for the various websocket clients",
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--host", default="127.0.0.1", help="Server host")
    parser.add_argument("--tcp-port", default="9001", help="Server port with plain tcp websockets")
    parser.add_argument("--ssl-port", default="9002", help="Server port with ssl websockets")
    parser.add_argument("--msg-size", default="256", help="Message size")
    parser.add_argument("--duration", default="5", help="duration of test in seconds")
    parser.add_argument("--loops", default="asyncio,uvloop", help="Comma separated list of event loops")
    parser.add_argument("--no-plot", action="store_true", help="Disable plots")
    parser.add_argument("--save-plot", action="store_true", help="Save plot to results folder instead of showing them")

    # I'm not sure if I did tornado client in the best possible way.
    # It shows remarkably bad performance, worse than websocket, so I disable it for now.
    parser.add_argument("--clients", default="tornado,ws4py,websockets,aiohttp,picows,picows_cyt,boost", help="Comma separated list of clients")
    parser.add_argument("--skip-tcp", action="store_true", help="Disable plain tcp client test")
    parser.add_argument("--skip-ssl", action="store_true", help="Disable ssl client test")

    parser.add_argument("--profile", action="store_true", help="Enable profiling, print profile stats afterwards")

    args = parser.parse_args()

    msg_size = int(args.msg_size)
    loops = args.loops.split(",")
    pd_index = (args.clients.split(","))
    modules = (f"websocket_benchmark.client_{c}" for c in pd_index)

    duration = int(args.duration)

    ssl_context = create_client_ssl_context()
    tcp_url = f"ws://{args.host}:{args.tcp_port}/"
    ssl_url = f"wss://{args.host}:{args.ssl_port}/"

    tcp_ssl_targets = []
    if not args.skip_ssl:
        tcp_ssl_targets.append((ssl_context, ssl_url))
    if not args.skip_tcp:
        tcp_ssl_targets.append((None, tcp_url))

    pr = cProfile.Profile()

    if args.profile:
        pr.enable()

    pd_columns = []
    results = []
    for module_idx, module_name in enumerate(modules):
        m = importlib.import_module(module_name, ".")
        module_results = [m.version]
        results.append(module_results)
        if module_idx == 0:
            pd_columns.append("version")
        for ctx, url in tcp_ssl_targets:
            msg = os.urandom(msg_size)

            if m.name not in ('c++ beast', 'ws4py'):
                for loop in loops:
                    if loop == "uvloop":
                        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
                    else:
                        asyncio.set_event_loop_policy(None)

                    tcp_ssl_name = 'tcp' if ctx is None else 'ssl'
                    print(f"Run {m.name} {tcp_ssl_name} {msg_size} bytes {loop} test")
                    rps = asyncio.run(m.run(args, url, msg, duration, 100, ctx))

                    if module_idx == 0:
                        pd_columns.append(f"{tcp_ssl_name}-{loop}")
                    module_results.append(rps)
            else:
                tcp_ssl_name = 'tcp' if ctx is None else 'ssl'
                print(f"Run {m.name} {tcp_ssl_name} {msg_size} bytes test")
                rps = asyncio.run(m.run(args, url, msg, duration, 100, ctx))

                for loop in loops:
                    if module_idx == 0:
                        pd_columns.append(f"{tcp_ssl_name}-{loop}")
                    module_results.append(rps)

    if args.profile:
        pr.disable()
        pr.print_stats()
        return

    df = pd.DataFrame(results, index=pd_index, columns=pd_columns)
    if not args.no_plot:
        print_result_and_plot(msg_size, df, args.save_plot)


if __name__ == '__main__':
    main()
