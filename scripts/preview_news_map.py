"""
Look at the news map without published stories of your own: the built
frontend in front of the e2e stub backend, serving a synthetic map of
`--count` stories placed by the real layout (scripts/news_map_fixture.py).

    python scripts/preview_news_map.py [--count 3000] [--port 3100] [--build]

Then open http://127.0.0.1:3100/map (also /today and /for-you). Ctrl-C
stops it.

What works: the map, its panel and lines, filters, the list, Today, For
you signed out (it answers every profile with the stub's one story), the
day pages. What does not: search answers the stub's one canned result,
and accounts need the real backend (the stub has no /account).
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import e2e  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def main(argv=None) -> int:

    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--count", type=int, default=3000)
    parser.add_argument("--port", type=int, default=3100)
    parser.add_argument("--build", action="store_true", help="npm run build first")
    args = parser.parse_args(argv)

    if args.build or not (e2e.FRONTEND / ".next" / "BUILD_ID").exists():
        print("Building the frontend...")
        if subprocess.run(["npm", "run", "build"], cwd=e2e.FRONTEND, stdout=subprocess.DEVNULL).returncode:
            print("npm run build failed.", file=sys.stderr)
            return 1

    print(f"Placing {args.count} synthetic stories...")
    made = subprocess.run(["uv", "run", "python", "../scripts/news_map_fixture.py", str(args.count)],
                          cwd=ROOT / "backend", capture_output=True, text=True, check=True)
    e2e.MAP.clear()
    e2e.MAP.update(json.loads(made.stdout))

    stub = ThreadingHTTPServer(("127.0.0.1", 0), e2e.Stub)
    threading.Thread(target=stub.serve_forever, daemon=True).start()

    env = {**os.environ, "BACKEND_URL": f"http://127.0.0.1:{stub.server_address[1]}"}
    env.pop("STORAGE_API_KEY", None)
    server = subprocess.Popen(
        [str(e2e.FRONTEND / "node_modules" / ".bin" / "next"), "start", "-p", str(args.port), "-H", "127.0.0.1"],
        cwd=e2e.FRONTEND, env=env, start_new_session=True,
    )

    def stop(*_):
        try:
            os.killpg(server.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        stub.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    for _ in range(60):
        try:
            if e2e.get(f"http://127.0.0.1:{args.port}/map")[0] == 200:
                break
        except OSError:
            pass
        time.sleep(1)

    print(f"\nOpen http://127.0.0.1:{args.port}/map  (also /today and /for-you). Ctrl-C stops it.")
    server.wait()
    return 0


if __name__ == "__main__":
    sys.exit(main())
