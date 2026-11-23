"""
The news map's renderer spike (docs/goals.md, N2): regl against sigma.js
on the same synthetic points, in headless Chrome, on the dev laptop's
integrated GPU and on SwiftShader (software: a reader with no GPU).

    python scripts/bench_map_renderers.py [--no-build] [--counts 10000 50000]

Builds the frontend, starts it, opens /map/bench for each renderer, count
and GL backend, and writes what each page measured to
backend/data/evaluation/experiments/news-map/renderers-<date>.json, with
the machine's load average: on 29 Oct the model benchmark shared the CPU.
Needs a POSIX machine (e2e.py's DevTools pipe).
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from e2e import FRONTEND, Browser, find_chrome, free_port, get  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "backend" / "data" / "evaluation" / "experiments" / "news-map"

# Measured 29 Oct: these put headless Chrome on the Intel GPU ("Intel(R)
# Graphics (MTL)", Mesa, Vulkan); with none, or --disable-gpu, it draws on
# SwiftShader.
BACKENDS = {
    "intel-vulkan": ["--use-angle=vulkan", "--enable-features=Vulkan", "--ignore-gpu-blocklist"],
    "swiftshader": [],
}


def measure(chrome: str, base: str, renderer: str, count: int, backend: str) -> dict:

    # Chrome's GPU process can still be writing the profile as it exits.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as profile:
        browser = Browser(chrome, profile, BACKENDS[backend], gpu=backend != "swiftshader")
        try:
            browser.send("Page.navigate", {"url": f"{base}/map/bench?renderer={renderer}&n={count}"}, browser.session)
            done = "(() => { const e = document.querySelector('#bench-result'); return e && e.textContent !== 'running' ? e.textContent : null; })()"
            if not browser.until(done, timeout=180):
                return {"renderer": renderer, "count": count, "backend": backend, "error": "timed out"}
            return {"backend": backend, **json.loads(browser.evaluate(done))}
        finally:
            browser.close()


def main(argv=None) -> int:

    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--no-build", action="store_true")
    parser.add_argument("--counts", type=int, nargs="+", default=[10_000, 50_000])
    args = parser.parse_args(argv)

    chrome = find_chrome()
    if chrome is None:
        print("No Chrome found (set CHROME).", file=sys.stderr)
        return 2

    if not args.no_build and subprocess.run(["npm", "run", "build"], cwd=FRONTEND, stdout=subprocess.DEVNULL).returncode:
        print("npm run build failed.", file=sys.stderr)
        return 1

    port = free_port()
    server = subprocess.Popen(
        [str(FRONTEND / "node_modules" / ".bin" / "next"), "start", "-p", str(port), "-H", "127.0.0.1"],
        cwd=FRONTEND, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
    )
    base = f"http://127.0.0.1:{port}"

    results = []

    try:
        for _ in range(60):
            try:
                if get(f"{base}/map/bench")[0] == 200:
                    break
            except OSError:
                pass
            time.sleep(1)
        else:
            print("The frontend never answered.", file=sys.stderr)
            return 2

        for backend in BACKENDS:
            for count in args.counts:
                for renderer in ("regl", "sigma"):
                    try:
                        row = measure(chrome, base, renderer, count, backend)
                    except (TimeoutError, RuntimeError, OSError) as error:
                        row = {"renderer": renderer, "count": count, "backend": backend, "error": str(error)}
                    row["loadAverage"] = os.getloadavg()[0]
                    results.append(row)
                    print(json.dumps(row))
    finally:
        os.killpg(server.pid, signal.SIGTERM)
        server.wait(timeout=30)

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"renderers-{datetime.now():%Y-%m-%d}.json"
    path.write_text(json.dumps({"measuredAt": datetime.now().isoformat(timespec="seconds"), "results": results}, indent=2) + "\n")
    print(f"Written to {path.relative_to(ROOT)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
