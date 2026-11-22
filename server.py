#!/usr/bin/env python3
"""Simple static file server for the Recapper timeline editor prototype."""

from __future__ import annotations

import argparse
import functools
import http.server
import os
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the Recapper editor")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind")
    parser.add_argument("--port", default=8000, type=int, help="Port to bind")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    os.chdir(root)

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    server = http.server.ThreadingHTTPServer((args.host, args.port), handler)

    print(f"Recapper editor running at http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
