"""
Look at the News Universe (universe/) with no published stories of your
own: the built site, served the way production serves it - static files,
with /api/map and /api/account passed to a backend - here the e2e stub,
serving a synthetic universe of `--count` stories placed by the real
layout (scripts/news_map_fixture.py), depth included.

    python scripts/preview_universe.py [--count 5000] [--port 4321] [--build]

Then open http://127.0.0.1:4321/. Ctrl-C stops it. Search and For you
answer the stub's canned results; accounts need the real backend.

Not `astro dev`: Astro 7 started it as a background daemon when there was
no terminal (29 Oct), so a script could not hold it. A static build and
this proxy are also what Caddy does in production.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import e2e  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
UNIVERSE = ROOT / "universe"


def handler_for(backend: str):

    class Universe(SimpleHTTPRequestHandler):

        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(UNIVERSE / "dist"), **kwargs)

        def _proxy(self, method: str) -> bool:
            for prefix, target in (("/api/map", "/map"), ("/api/account", "/account")):
                if self.path.startswith(prefix):
                    length = int(self.headers.get("Content-Length") or 0)
                    body = self.rfile.read(length) if length else None
                    headers = {k: v for k, v in self.headers.items() if k.lower() in ("content-type", "cookie", "x-csrf-token", "x-requested-with", "if-none-match")}
                    request = urllib.request.Request(backend + target + self.path[len(prefix):], data=body, method=method, headers=headers)
                    try:
                        with urllib.request.urlopen(request, timeout=60) as answer:
                            status, payload, kept = answer.status, answer.read(), answer.headers
                    except urllib.error.HTTPError as error:
                        status, payload, kept = error.code, error.read(), error.headers
                    self.send_response(status)
                    for name in ("Content-Type", "ETag", "Set-Cookie", "Retry-After", "Cache-Control"):
                        for value in kept.get_all(name) or []:
                            self.send_header(name, value)
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                    return True
            return False

        def do_GET(self):
            if not self._proxy("GET"):
                super().do_GET()

        def do_POST(self):
            if not self._proxy("POST"):
                self.send_error(404)

        def log_message(self, *args):
            pass

    return Universe


def main(argv=None) -> int:

    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--count", type=int, default=5000)
    parser.add_argument("--port", type=int, default=4321)
    parser.add_argument("--build", action="store_true", help="npm run build first")
    args = parser.parse_args(argv)

    if args.build or not (UNIVERSE / "dist" / "index.html").exists():
        print("Building the universe...")
        if subprocess.run(["npm", "run", "build"], cwd=UNIVERSE, stdout=subprocess.DEVNULL).returncode:
            print("npm run build failed.", file=sys.stderr)
            return 1

    print(f"Placing {args.count} synthetic stories...")
    made = subprocess.run(["uv", "run", "python", "../scripts/news_map_fixture.py", str(args.count)],
                          cwd=ROOT / "backend", capture_output=True, text=True, check=True)
    e2e.MAP.clear()
    e2e.MAP.update(json.loads(made.stdout))

    stub = ThreadingHTTPServer(("127.0.0.1", 0), e2e.Stub)
    threading.Thread(target=stub.serve_forever, daemon=True).start()

    site = ThreadingHTTPServer(("127.0.0.1", args.port), handler_for(f"http://127.0.0.1:{stub.server_address[1]}"))
    print(f"\nOpen http://127.0.0.1:{args.port}/  Ctrl-C stops it.")

    try:
        site.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        site.server_close()
        stub.shutdown()

    return 0


if __name__ == "__main__":
    sys.exit(main())
