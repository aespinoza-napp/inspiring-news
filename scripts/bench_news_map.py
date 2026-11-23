"""
The news map's rendering budget (docs/goals.md, N8), measured.

    python scripts/bench_news_map.py [--no-build] [--counts 2000 10000 50000]

For each count: a synthetic map (scripts/news_map_fixture.py, the real
layout) served by the e2e stub backend to the built frontend, opened in
headless Chrome on the dev laptop's Intel GPU (the flags that put it
there, measured 29 Oct: scripts/bench_map_renderers.py). Measured, as a
reader meets them:

- first paint: navigation to the first frame with stories drawn
  (NewsMap's `news-map:first-frame` mark), cold and from a warm cache;
- the payload: the map's bytes over the wire (Resource Timing);
- frames: requestAnimationFrame intervals while the map is panned and
  zoomed every frame for 4 s - normal drawing, nothing read back, so
  this is what the reader sees (the renderer spike read pixels back,
  which only ranks renderers) - and how many were dropped (DROPPED_MS);
- picking: each hover's milliseconds (NewsMap records them when the
  page sets window.__newsMapPerf).

The budget at 10k: first paint (warm) under 1.5 s, the payload under
1 MB, no frame dropped, picking p95 under 4 ms; at 50k, under 5% of
frames dropped and first paint under 3 s. Fails (exit 1) if 2k or
10k is over budget; 50k is recorded either way. Writes everything to
backend/data/evaluation/experiments/news-map/rendering-<date>.json with
the load average, since a loaded machine is a slower one.

Not in ./scripts/check.sh e2e: a wall-clock budget there would fail on
any loaded or GPU-less machine, which is what the backend's first
timing test did on 29 Oct.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import e2e  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "backend" / "data" / "evaluation" / "experiments" / "news-map"
GPU = ["--use-angle=vulkan", "--enable-features=Vulkan", "--ignore-gpu-blocklist"]

# 60 fps is no frame dropped: requestAnimationFrame fires every 16.67 ms
# with a little jitter (16.8 at the p95 on 29 Oct, nothing dropped), and a
# dropped frame shows as 33 ms. So the frame budget is the share of
# intervals over 25 ms - none at 10k, under 5% at 50k (30 fps or better) -
# not a p95 against exactly 16.7, which jitter alone fails.
DROPPED_MS = 25.0

BUDGET = {
    "firstPaintWarmMs": {10_000: 1500, 50_000: 3000},
    "payloadBytes": {10_000: 1_000_000},
    "droppedPercent": {10_000: 0.0, 50_000: 5.0},
    "pickP95Ms": {10_000: 4.0},
}

# Every frame for four seconds: a wheel event (zoom in, then out) and a
# drag step, while recording when each frame began.
PAN_AND_ZOOM = """
new Promise((resolve) => {
  const frame = document.querySelector('[aria-roledescription=map]');
  const box = frame.getBoundingClientRect();
  const x = box.left + box.width / 2, y = box.top + box.height / 2;
  const times = [];
  const started = performance.now();
  let step = 0;
  function tick(now) {
    times.push(now);
    const zoomIn = (step % 120) < 60;
    frame.dispatchEvent(new WheelEvent('wheel', { deltaY: zoomIn ? -40 : 40, clientX: x + 50 * Math.cos(step / 20), clientY: y, bubbles: true, cancelable: true }));
    step++;
    if (now - started < 4000) requestAnimationFrame(tick);
    else resolve(times.slice(1).map((t, i) => t - times[i]));
  }
  requestAnimationFrame(tick);
})
"""

# NewsMap reads window.__newsMapPerf on every pick, so setting it here is
# enough; an error resolves with what was measured rather than hanging.
HOVER = """
new Promise((resolve) => {
  window.__newsMapPerf = { picks: [] };
  const frame = document.querySelector('[aria-roledescription=map]');
  const box = frame.getBoundingClientRect();
  let n = 0;
  function move() {
    try {
      const x = box.left + box.width * (0.2 + 0.6 * ((n * 37) % 100) / 100);
      const y = box.top + box.height * (0.2 + 0.6 * ((n * 61) % 100) / 100);
      frame.dispatchEvent(new PointerEvent('pointermove', { clientX: x, clientY: y, bubbles: true, pointerId: 1 }));
    } catch (error) {
      return resolve(window.__newsMapPerf.picks.slice());
    }
    n++;
    if (n < 300) setTimeout(move, 0); else resolve(window.__newsMapPerf.picks.slice());
  }
  move();
})
"""


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(p / 100 * len(ordered)))] if ordered else float("nan")


def run_for(chrome: str, base: str, count: int) -> dict:

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as profile:
        browser = e2e.Browser(chrome, profile, GPU, gpu=True)
        try:
            session = browser.session
            browser.send("Emulation.setDeviceMetricsOverride", {"width": 1440, "height": 1000, "deviceScaleFactor": 1, "mobile": False}, session)

            def load() -> tuple[float | None, dict]:
                browser.send("Page.navigate", {"url": f"{base}/map"}, session)
                browser.until(f"document.body.innerText.includes('of {count} articles')", timeout=120)
                browser.until("performance.getEntriesByName('news-map:first-frame').length > 0", timeout=60)
                first = browser.evaluate("performance.getEntriesByName('news-map:first-frame')[0].startTime")
                resource = browser.evaluate(
                    "(() => { const r = performance.getEntriesByType('resource').find(e => e.name.includes('/api/map/articles'));"
                    " return r ? { transfer: r.transferSize, decoded: r.decodedBodySize } : {}; })()"
                )
                return first, resource

            cold, cold_resource = load()
            warm, _ = load()

            def run(expression):
                answer = browser.send("Runtime.evaluate", {"expression": expression, "awaitPromise": True, "returnByValue": True}, session, timeout=60)
                return answer["result"].get("value") or []

            frames = run(PAN_AND_ZOOM)
            picks = run(HOVER)
            gpu = browser.evaluate(
                "(() => { const g = document.querySelector('canvas').getContext('webgl'); const e = g && g.getExtension('WEBGL_debug_renderer_info');"
                " return e ? g.getParameter(e.UNMASKED_RENDERER_WEBGL) : 'unknown'; })()"
            )
        finally:
            browser.close()

    return {
        "count": count,
        "gpu": gpu,
        "firstPaintColdMs": round(cold or 0, 1),
        "firstPaintWarmMs": round(warm or 0, 1),
        "payloadBytes": cold_resource.get("transfer"),
        "payloadDecodedBytes": cold_resource.get("decoded"),
        "frames": len(frames),
        "frameMedianMs": round(percentile(frames, 50), 2),
        "frameP95Ms": round(percentile(frames, 95), 2),
        "droppedPercent": round(100 * sum(f > DROPPED_MS for f in frames) / max(1, len(frames)), 2),
        "picks": len(picks),
        "pickP95Ms": round(percentile(picks, 95), 3),
        "loadAverage": os.getloadavg()[0],
    }


def over_budget(row: dict) -> list[str]:

    failures = []
    for metric, limits in BUDGET.items():
        limit = limits.get(row["count"])
        value = row.get(metric)
        if limit is not None and value is not None and value > limit:
            failures.append(f"{metric} {value} > {limit}")
    return failures


def main(argv=None) -> int:

    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--no-build", action="store_true")
    parser.add_argument("--counts", type=int, nargs="+", default=[2_000, 10_000, 50_000])
    args = parser.parse_args(argv)

    chrome = e2e.find_chrome()
    if chrome is None:
        print("No Chrome found (set CHROME).", file=sys.stderr)
        return 2

    if not args.no_build and subprocess.run(["npm", "run", "build"], cwd=e2e.FRONTEND, stdout=subprocess.DEVNULL).returncode:
        print("npm run build failed.", file=sys.stderr)
        return 1

    results, failed = [], False

    for count in args.counts:

        made = subprocess.run(["uv", "run", "python", "../scripts/news_map_fixture.py", str(count)],
                              cwd=ROOT / "backend", capture_output=True, text=True, check=True)
        e2e.MAP.clear()
        e2e.MAP.update(json.loads(made.stdout))

        stub = ThreadingHTTPServer(("127.0.0.1", 0), e2e.Stub)
        threading.Thread(target=stub.serve_forever, daemon=True).start()
        port = e2e.free_port()
        env = {**os.environ, "BACKEND_URL": f"http://127.0.0.1:{stub.server_address[1]}"}
        env.pop("STORAGE_API_KEY", None)
        server = subprocess.Popen([str(e2e.FRONTEND / "node_modules" / ".bin" / "next"), "start", "-p", str(port), "-H", "127.0.0.1"],
                                  cwd=e2e.FRONTEND, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        base = f"http://127.0.0.1:{port}"

        try:
            for _ in range(60):
                try:
                    if e2e.get(f"{base}/reader")[0] == 200:
                        break
                except OSError:
                    pass
                time.sleep(1)

            row = run_for(chrome, base, count)
        finally:
            os.killpg(server.pid, signal.SIGTERM)
            server.wait(timeout=30)
            stub.shutdown()

        row["overBudget"] = over_budget(row)
        results.append(row)
        print(json.dumps(row))

        if row["overBudget"] and count <= 10_000:
            failed = True

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"rendering-{datetime.now():%Y-%m-%d}.json"
    path.write_text(json.dumps({"measuredAt": datetime.now().isoformat(timespec="seconds"), "budget": {k: {str(c): v for c, v in l.items()} for k, l in BUDGET.items()}, "results": results}, indent=2) + "\n")
    print(f"Written to {path.relative_to(ROOT)}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
