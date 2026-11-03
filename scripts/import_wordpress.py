#!/usr/bin/env python3
"""
Send a WordPress export to the backend and follow it: every post enriched,
through admission (recorded, deciding nothing), into the lake and the graph,
not fact-checked (backend/src/services/imports/wordpress_import.py).

    python3 scripts/import_wordpress.py ~/Descargas/<site>.WordPress.<date>.xml
    python3 scripts/import_wordpress.py export.xml --statuses publish,private,draft
    python3 scripts/import_wordpress.py export.xml --limit 3        # try it first
    python3 scripts/import_wordpress.py export.xml --verify         # later: the same posts, checked

It keeps the posts as read (snapshot.jsonl), each post's result (results.jsonl)
and the summary in backend/data/imports/<file name>/, which git ignores: the
export holds unpublished posts too. Two runs read the same words when their
snapshots' content hashes agree.

Standard library only, like the labeller. The key is STORAGE_API_KEY, from
the environment or backend/.env; the backend from --backend (default
http://localhost:8000, the dev stack's published port).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def api_key() -> str | None:

    if os.environ.get("STORAGE_API_KEY"):
        return os.environ["STORAGE_API_KEY"]

    env = ROOT / "backend" / ".env"

    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("STORAGE_API_KEY="):
                return line.split("=", 1)[1].strip().strip("'\"") or None

    return None


def call(method: str, url: str, key: str | None, body: bytes | None = None, content_type: str | None = None):

    request = urllib.request.Request(url, data=body, method=method)

    if key:
        request.add_header("X-API-Key", key)
    if content_type:
        request.add_header("Content-Type", content_type)

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def main(argv=None) -> int:

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("export", type=Path, help="the WordPress export (.xml)")
    parser.add_argument("--statuses", default="publish", help="which posts: publish (default), private, draft, comma-separated")
    parser.add_argument("--verify", action="store_true", help="fact-check them too (minutes per article)")
    parser.add_argument("--limit", type=int, help="only the first N posts, oldest first")
    parser.add_argument("--backend", default=os.environ.get("BACKEND_URL", "http://localhost:8000"))
    parser.add_argument("--out", type=Path, help="where to keep the results (default backend/data/imports/<file name>)")
    args = parser.parse_args(argv)

    if not args.export.is_file():
        print(f"No such file: {args.export}", file=sys.stderr)
        return 2

    key = api_key()
    base = args.backend.rstrip("/")
    query = f"statuses={args.statuses}&verify={'true' if args.verify else 'false'}" + (f"&limit={args.limit}" if args.limit else "")

    status, body = call("POST", f"{base}/imports/wordpress?{query}", key, args.export.read_bytes(), "application/xml")

    if status != 202:
        print(f"The backend refused the import ({status}): {body.decode('utf-8', 'replace')}", file=sys.stderr)
        return 1

    started = json.loads(body)
    print(f"Import {started['importId']}: {started['total']} posts of {started['site']} "
          f"({', '.join(started['statuses'])}), {'verified' if args.verify else 'not verified'}.")

    shown = 0

    while True:

        time.sleep(2)
        status, body = call("GET", f"{base}/imports/wordpress", key)

        if status != 200:
            print(f"Lost the backend ({status}); the import carries on there. Run again with GET /imports/wordpress.", file=sys.stderr)
            return 1

        state = json.loads(body)

        for line in state["results"][shown:]:
            verdict = "error: " + line["error"] if "error" in line else (
                "passes the filters" if line["passedFilters"] else "rejected: " + ", ".join(line["rejectedFor"]))
            print(f"  {line.get('wpId'):>5}  {line['title'][:70]:<70}  {verdict}")
        shown = len(state["results"])

        if not state["running"]:
            break

    out = args.out or ROOT / "backend" / "data" / "imports" / args.export.stem
    out.mkdir(parents=True, exist_ok=True)

    (out / "results.jsonl").write_text(
        "".join(json.dumps(line, ensure_ascii=False) + "\n" for line in state["results"]), encoding="utf-8")
    (out / "summary.json").write_text(
        json.dumps({key: value for key, value in state.items() if key != "results"}, ensure_ascii=False, indent=2),
        encoding="utf-8")

    status, body = call("GET", f"{base}/imports/wordpress/snapshot", key)
    if status == 200:
        (out / "snapshot.jsonl").write_bytes(body)

    summary = state.get("summary") or {}
    print()
    print(f"Imported {summary.get('imported', 0)} of {state['total']}, {summary.get('failed', 0)} failed.")
    print(f"Would pass the filters: {summary.get('passedFilters', 0)}; rejected: {summary.get('rejected', 0)} {summary.get('rejectedFor') or ''}")
    print(f"Duplicates within the file: {summary.get('duplicatesInFile', 0)}. Claims found: {summary.get('claims', 0)}.")
    print(f"Kept in {out}")

    if state.get("error"):
        print(f"The import stopped: {state['error']}", file=sys.stderr)
        return 1

    return 0 if not summary.get("failed") else 1


if __name__ == "__main__":
    sys.exit(main())
