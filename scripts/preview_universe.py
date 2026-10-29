"""
Look at the News Universe (universe/) with no published stories of your
own: the built site, served the way production serves it - static files,
with /api/map and /api/account passed to a backend - here the e2e stub,
serving a synthetic universe of `--count` stories placed by the real
layout (scripts/news_map_fixture.py), depth included.

    python scripts/preview_universe.py [--count 5000] [--port 4321] [--build]

Then open http://127.0.0.1:4321/. Ctrl-C stops it. A story's links and
the search are answered here from the synthetic map, as the backend
answers them (shared names weigh 2 over how many stories name them, a
shared topic 0.3; names, then words in titles); For you answers the
stub's canned result; accounts need the real backend.

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


def fold(text: str) -> str:
    import unicodedata

    plain = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))
    return " ".join(plain.casefold().split())


class Local:
    """What the stub cannot answer for a synthetic map: links and search."""

    def __init__(self, document: dict):

        self.document = document
        a = document["articles"]
        self.index = {article_id: i for i, article_id in enumerate(a["id"])}
        self.naming: dict[int, list[int]] = {}
        for i, refs in enumerate(a["e"]):
            for ref in refs:
                self.naming.setdefault(ref, []).append(i)

    def links(self, article_id: str) -> dict | None:

        d, a = self.document, self.document["articles"]
        i = self.index.get(article_id)
        if i is None:
            return None
        reasons: dict[int, list[dict]] = {}
        for ref in a["e"][i]:
            stories = self.naming[ref]
            for j in stories:
                if j != i:
                    reasons.setdefault(j, []).append({"kind": "entity", "via": d["entities"][ref]["n"], "weight": round(2 / len(stories), 4)})
        for t in a["t"][i]:
            for j, others in enumerate(a["t"]):
                if j != i and t in others and len(reasons.get(j, [])) < 3:
                    reasons.setdefault(j, []).append({"kind": "topic", "via": d["topics"][t]["name"], "weight": 0.3})
        ranked = sorted(reasons.items(), key=lambda item: -sum(r["weight"] for r in item[1]))[:10]
        return {
            "id": article_id, "title": a["title"][i], "x": a["x"][i], "y": a["y"][i],
            "topics": [{"key": d["topics"][t]["key"], "name": d["topics"][t]["name"], "confidence": 0.5} for t in a["t"][i]],
            "entities": [{"key": d["entities"][r]["k"], "name": d["entities"][r]["n"], "type": d["entities"][r]["t"], "articles": len(self.naming[r])} for r in a["e"][i]],
            "related": [{"id": a["id"][j], "title": a["title"][j], "x": a["x"][j], "y": a["y"][j],
                         "score": round(sum(r["weight"] for r in why), 4), "via": why} for j, why in ranked],
        }

    def search(self, query: str) -> dict:

        d, a = self.document, self.document["articles"]
        q = fold(query)
        results = []
        for ref, entity in enumerate(d["entities"]):
            name = fold(entity["n"])
            if q and (name.startswith(q) or f" {q}" in f" {name}"):
                stories = self.naming.get(ref, [])
                if stories:
                    results.append({"kind": "entity", "key": entity["k"], "name": entity["n"], "type": entity["t"], "articles": len(stories),
                                    "x": sum(a["x"][j] for j in stories) / len(stories), "y": sum(a["y"][j] for j in stories) / len(stories),
                                    "reason": "the name"})
        results = sorted(results, key=lambda r: -r["articles"])[:5]
        tokens = q.split()
        for i, title in enumerate(a["title"]):
            words = fold(title).split()
            if tokens and all(any(w.startswith(t) for w in words) for t in tokens):
                results.append({"kind": "article", "id": a["id"][i], "title": title, "x": a["x"][i], "y": a["y"][i], "reason": "in the title"})
                if len(results) >= 15:
                    break
        return {"query": query, "results": results, "semantic": "skipped"}


def handler_for(backend: str, local: Local | None = None):

    class Universe(SimpleHTTPRequestHandler):

        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(UNIVERSE / "dist"), **kwargs)

        def _local(self) -> bool:
            if local is None:
                return False
            from urllib.parse import parse_qs, urlsplit

            parts = urlsplit(self.path)
            answer = None
            if parts.path.startswith("/api/map/articles/") and parts.path.endswith("/links"):
                answer = local.links(parts.path.split("/")[4])
                if answer is None:
                    self.send_error(404)
                    return True
            elif parts.path == "/api/map/search":
                answer = local.search(parse_qs(parts.query).get("q", [""])[0])
            if answer is None:
                return False
            payload = json.dumps(answer).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return True

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
            if not self._local() and not self._proxy("GET"):
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

    site = ThreadingHTTPServer(("127.0.0.1", args.port), handler_for(f"http://127.0.0.1:{stub.server_address[1]}", Local(e2e.MAP)))
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
