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

if os.name != 'nt':
    import uvloop
else:
    import winloop

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
        "picows_no_aiofastnet": "red",
        "picows": "darkred",
        "picows_cyt": "darkred",
        "boost": "black"
    }

    try:
        import matplotlib.pyplot as plt
        from matplotlib.font_manager import FontProperties

        clients = results.index
        client_names = results.index + "-" + results.version
        data = results.drop(columns=["version"])
        tests = [n for n in data.columns]

        x = np.arange(len(tests))
        width = 0.08

        fig, ax = plt.subplots(figsize=(8, 4.8))

        for i, (client, name) in enumerate(zip(clients, client_names)):
            ax.bar(
                x + i * width,
                data.loc[client],
                width,
                label=name,
                color=colors_map.get(client)
            )

        ax.set_xticks(x + width * (len(clients) - 1) / 2, tests)
        ax.set_ylabel("request/second")
        headers = [
            'Echo round-trip performance',            
        ]        
        if os.name != 'nt':
            headers.append(f'Python-{platform.python_version()}, uvloop-{uvloop.__version__}, msg_size={msg_size}')
        else:
            headers.append(f'Python-{platform.python_version()}, winloop-{winloop.__version__}, msg_size={msg_size}')
        headers.append(f"{platform.system()} - {platform.processor()}")
        ax.set_title("\n".join(headers))
        handles, labels = ax.get_legend_handles_labels()
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        axes_width_px = ax.get_window_extent(renderer=renderer).width
        font_properties = FontProperties(size=plt.rcParams["legend.fontsize"])

        text_widths = [
            renderer.get_text_width_height_descent(label, font_properties, ismath=False)[0]
            for label in labels
        ]

        legend_cols = 1
        handle_width_px = 40
        column_spacing_px = 24
        for candidate_cols in range(len(labels), 0, -1):
            candidate_rows = int(np.ceil(len(labels) / candidate_cols))
            column_widths = []
            for col in range(candidate_cols):
                column_items = text_widths[col::candidate_cols]
                if not column_items:
                    continue
                column_widths.append(max(column_items) + handle_width_px)

            total_width = sum(column_widths) + max(len(column_widths) - 1, 0) * column_spacing_px
            if total_width <= axes_width_px:
                legend_cols = candidate_cols
                break

        legend_rows = int(np.ceil(len(handles) / legend_cols))
        legend_order = []
        for col in range(legend_cols):
            for row in range(legend_rows):
                idx = row * legend_cols + col
                if idx < len(handles):
                    legend_order.append(idx)
        ax.legend(
            [handles[idx] for idx in legend_order],
            [labels[idx] for idx in legend_order],
            loc="upper center",
            bbox_to_anchor=(0.0, -0.22, 1.0, 0.1),
            mode="expand",
            ncol=legend_cols,
            frameon=True,
            borderaxespad=0.0,
        )
        fig.tight_layout(rect=(0, 0.08, 1, 1))
        ax.grid(axis='y', linestyle='--', linewidth=0.5)

        if save_plot:
            png_path = Path(os.path.dirname(
                __file__)) / '..' / 'results' / f'benchmark-{platform.system()}-{msg_size}.png'
            data_path = Path(os.path.dirname(
                __file__)) / '..' / 'results' / f'benchmark-{platform.system()}-{msg_size}.csv'
            fig.savefig(png_path, dpi=150, bbox_inches="tight")
            plt.close(fig)

            results.to_csv(data_path)
        else:
            plt.show()
    except ImportError:
        pass


def main():
    parser = argparse.ArgumentParser(description="Benchmark for the various websocket clients",
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--host", default="127.0.0.1", help="Server host")
    parser.add_argument("--tcp-port", type=int, default="9001", help="Server port with plain tcp websockets")
    parser.add_argument("--ssl-port", type=int, default="9002", help="Server port with ssl websockets")
    parser.add_argument("--msg-size", type=int, default="256", help="Message size")
    parser.add_argument("--duration", type=int, default="5", help="duration of test in seconds")
    if os.name != 'nt':
        parser.add_argument("--loops", default="asyncio,uvloop", help="Comma separated list of event loops")
    else:
        parser.add_argument("--loops", default="asyncio_pro,asyncio_sel,winloop", help="Comma separated list of event loops")
    parser.add_argument("--no-plot", action="store_true", help="Disable plots")
    parser.add_argument("--save-plot", action="store_true", help="Save plot to results folder instead of showing them")

    parser.add_argument("--clients",
                        default="tornado,ws4py,websockets,aiohttp,picows,boost",
                        help="Comma separated list of clients")
    parser.add_argument("--skip-tcp", action="store_true", help="Disable plain tcp client test")
    parser.add_argument("--skip-ssl", action="store_true", help="Disable ssl client test")

    parser.add_argument("--profile", action="store_true", help="Enable profiling, print profile stats afterwards")

    args = parser.parse_args()

    loops = args.loops.split(",")
    pd_index = (args.clients.split(","))
    modules = (f"wsbench.client_{c}" for c in pd_index)

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
            msg = os.urandom(args.msg_size)

            if m.name not in ('c++ beast', 'ws4py'):
                for loop in loops:
                    if loop == "uvloop":
                        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
                    elif loop == 'winloop':
                        asyncio.set_event_loop_policy(winloop.EventLoopPolicy())
                    elif loop == 'asyncio_sel':
                        asyncio.set_event_loop_policy(asyncio._WindowsSelectorEventLoopPolicy())
                    else:
                        asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())

                    tcp_ssl_name = 'tcp' if ctx is None else 'ssl'
                    print(f"Run {m.name} {tcp_ssl_name} {args.msg_size} bytes {loop} test")
                    rps = asyncio.run(m.run(args, url, msg, args.duration, 100, ctx))

                    if module_idx == 0:
                        pd_columns.append(f"{tcp_ssl_name}-{loop}")
                    module_results.append(rps)
            else:
                tcp_ssl_name = 'tcp' if ctx is None else 'ssl'
                print(f"Run {m.name} {tcp_ssl_name} {args.msg_size} bytes test")
                rps = asyncio.run(m.run(args, url, msg, args.duration, 100, ctx))

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
        print_result_and_plot(args.msg_size, df, args.save_plot)


if __name__ == '__main__':
    main()
