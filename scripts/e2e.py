#!/usr/bin/env python3
"""
End-to-end checks of the frontend, as a reader and a poller meet it:
`./scripts/check.sh e2e`.

    python scripts/e2e.py [--no-build]

The frontend has no test runner and takes no dependency beyond next and
react (frontend/CLAUDE.md), so this is the standard library and a headless
Chrome: it builds the frontend, serves it with `next start` against a stub
backend run here, and reads the pages as a browser renders them
(`--dump-dom`, after the page's scripts ran).

What it holds:

- **The polling incident** (frontend/CLAUDE.md, "Two things that must not
  be removed"): /api/jobs/<id> polled twice must reach the backend twice
  and return its newer answer. Next.js caches GET fetches by default, and
  the route's `cache: "no-store"` is what stops it; without it the second
  poll returned the first, stale snapshot - reproduced live once.
- **The polling hook's `cancelled` guard** (the second of those two
  things): a job started on the Analyze page whose first poll is still in
  flight when the page is left must not go on polling. Driven over the
  DevTools protocol (`--remote-debugging-pipe`): the stub holds that poll
  for three seconds, the page navigates away meanwhile, and no poll may
  arrive afterwards; without the guard one arrives every second. Once for
  a single job (`useAnalysisJob`) and once in bulk mode
  (`useBatchAnalysisJobs`, the same guard).
- **The reader in its three languages**: the feed, an article with its
  verdict panel and the badge links to the guide, the guide, a story and
  a withdrawn story's real 404, the RSS feed and the sitemap (well-formed
  XML, absolute links), and an operator page still in English.
- **A story from a trend loads nothing from TikTok until the reader
  clicks** (docs/decisions/trends.md, "The story"): Chrome is told that
  tiktok.com is a local port that only counts connections - http, https
  or a preconnect alike. Rendered, the facade is there and nothing
  connected; clicked (over the DevTools protocol), the player's iframe
  appears and TikTok is connected to.

Not in `./scripts/check.sh` (all): it builds the frontend (a minute) and
needs Chrome, like `graph` needs Neo4j, and a POSIX system. Exits 1
when a check fails, 2 when Chrome is missing, the server never answers
or it is run on Windows.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import xml.dom.minidom
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"

STORY_ID = "0123456789abcdef"
ARTICLE_ID = "fedcba9876543210"

SUMMARY = {
    "overall": "UNVERIFIED", "display": "UNVERIFIED", "confidence": 0.62, "claimsTotal": 4, "claimsChecked": 2,
    "counts": {"TRUE": 1}, "notJudged": 1, "searchUnavailable": 1, "llmUnreachable": 0, "noAnswer": 0,
    "sourcesCited": 1, "belowAnchorFloor": False,
}
CARD = {
    "id": ARTICLE_ID, "url": "https://elpais.com/a", "headline": "Las renovables superan al carbón",
    "titleExtracted": True, "source": {"id": "elpais", "name": "El País", "domain": "elpais.com"},
    "language": "es", "topic": "Energy", "publishedAt": "2026-10-01T08:00:00", "checkedAt": "2026-10-02T09:00:00",
    "excerpt": "Por primera vez, las renovables generaron más que el carbón.", "verdict": SUMMARY,
}
SOURCE = {
    "url": "https://ine.es/x", "title": "Informe anual", "domain": "ine.es", "origin": "web",
    "publishedAt": "2026-09-12T00:00:00", "snippet": "", "cited": True, "stance": "supports",
    "quote": "generaron el 52%", "reliabilityKnown": False, "foundBy": ["anchor"],
    "scores": {"relevance": 0.7, "pertinence": 0.6, "semantic": 0.8, "lexical": 0.5, "recency": 0.9, "reliability": 0.5},
}
ARTICLE = {
    **CARD, "author": "Ana Pérez", "summary": "Por primera vez...", "topics": [], "keywords": [],
    "claimsAvailable": True, "uncheckedClaims": [], "uncheckedTotal": 0,
    "checkedWith": {"model": "llama3.2:3b", "pipelineVersion": "1.4"},
    "claims": [
        {"index": 0, "text": "Las renovables generaron el 52%.", "verdict": "TRUE", "confidence": 0.8,
         "outcome": "judged", "explanation": "", "modelVerdict": None, "note": None, "searchUnavailable": False,
         "independentDomains": 1, "agreements": [], "discrepancies": [], "sources": [SOURCE], "notUsed": [],
         "notUsedTotal": 0},
        {"index": 1, "text": "El carbón cayó un 30%.", "verdict": "UNVERIFIED", "confidence": 0.0,
         "outcome": "search_unavailable", "explanation": "", "modelVerdict": None, "note": None,
         "searchUnavailable": True, "independentDomains": 0, "agreements": [], "discrepancies": [], "sources": [],
         "notUsed": [], "notUsedTotal": 0},
    ],
}
VIDEO_ID = "6718335390845095173"

STORY = {
    "id": STORY_ID, "sourceArticleId": ARTICLE_ID, "language": "ca",
    "content": {"title": "Les plaques solars arriben a les escoles", "subtitle": "Un pla", "body": "El pla [1]."},
    "sources": [{"url": "https://ine.es/a", "title": "Informe", "domain": "ine.es", "origin": "evidence",
                 "publishedAt": "2026-09-12T00:00:00"}],
    "factChecks": [], "metadata": {"slug": "x", "seoDescription": "", "keywords": [], "topic": "Energy", "tags": []},
    "disclosure": {"aiWritten": True, "models": ["writer"], "humanEdited": False},
    "publishedAt": "2026-10-15T10:00:00Z",
    "trend": {"name": "farmear aura", "signalName": "Typed by a person", "video": {
        "provider": "tiktok", "id": VIDEO_ID, "url": f"https://www.tiktok.com/@scout2015/video/{VIDEO_ID}",
        "title": "Scramble up ur name", "author": "scout2015"}},
}
FEED = {"total": 1, "offset": 0, "limit": 20, "items": [CARD], "topics": [{"topic": "Energy", "count": 1}],
        "languages": [{"language": "es", "count": 1}], "lake": {"analysed": 3, "publishable": 1}}
STORIES = {"total": 1, "offset": 0, "limit": 4, "published": 1, "topics": [], "languages": [], "items": [{
    "id": STORY_ID, "language": "ca", "title": STORY["content"]["title"], "subtitle": "Un pla", "description": "",
    "topic": "Energy", "publishedAt": "2026-10-15T10:00:00Z", "sourceArticleId": ARTICLE_ID,
    "disclosure": STORY["disclosure"]}]}


HELD_SECONDS = 3.0


class Stub(BaseHTTPRequestHandler):
    """
    The backend's open reader routes; one job, which finishes on its
    second poll; and one that never finishes, whose first poll is held.
    """

    job_polls = 0
    slow_polls: list[float] = []
    lock = threading.Lock()

    def do_POST(self):

        path = self.path.split("?")[0]
        self.rfile.read(int(self.headers.get("Content-Length") or 0))

        if path == "/analyze/jobs":
            return self._json(202, {"jobId": "slow1", "status": "queued", "reused": False})

        if path == "/analyze/jobs/batch":
            return self._json(202, {"jobs": [{"url": "https://example.org/a", "jobId": "slow2", "reused": False}]})

        return self._json(404, {"detail": "Not found"})

    def _held_poll(self) -> None:
        """Count it; hold the first one, so the page can be left while it is in flight."""

        with Stub.lock:
            Stub.slow_polls.append(time.monotonic())
            first = len(Stub.slow_polls) == 1
        if first:
            time.sleep(HELD_SECONDS)

    def do_GET(self):

        path = self.path.split("?")[0]

        if path == "/analyze/jobs/job1":
            with Stub.lock:
                Stub.job_polls += 1
                polls = Stub.job_polls
            body = {"jobId": "job1", "status": "running" if polls == 1 else "done", "events": [], "polls": polls}
            return self._json(200, body)

        if path == "/analyze/jobs/slow1":
            self._held_poll()
            return self._json(200, {"jobId": "slow1", "url": "https://example.org/a", "status": "running", "events": []})

        if path == "/analyze/jobs/batch":
            self._held_poll()
            return self._json(200, {"jobs": [{"jobId": "slow2", "url": "https://example.org/a", "status": "running", "events": []}]})

        routes = {
            "/reader/articles": FEED, f"/reader/articles/{ARTICLE_ID}": ARTICLE,
            "/reader/stories": STORIES, f"/reader/stories/{STORY_ID}": STORY,
        }

        if path in routes:
            return self._json(200, routes[path])

        return self._json(404, {"detail": "Not found"})

    def _json(self, status, body):

        data = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


def free_port() -> int:

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def find_chrome() -> str | None:

    for name in (os.environ.get("CHROME"), "google-chrome", "chromium", "chromium-browser", "chrome"):
        if name and shutil.which(name):
            return shutil.which(name)
    return None


class Checks:

    def __init__(self):
        self.failed = 0

    def check(self, name: str, ok: bool, detail: str = "") -> None:

        mark = "\033[32m✓\033[0m" if ok else "\033[31m✗\033[0m"
        print(f"  {mark} {name}" + ("" if ok or not detail else f" - {detail}"))
        if not ok:
            self.failed += 1


def get(url: str, headers: dict | None = None) -> tuple[int, str]:

    request = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8", "replace")


def dom(chrome: str, url: str, lang: str = "en", extra: list[str] | None = None) -> str:
    """The page after its scripts ran, as headless Chrome renders it."""

    result = subprocess.run(
        [chrome, "--headless=new", "--disable-gpu", "--no-sandbox", f"--lang={lang}",
         "--virtual-time-budget=8000", *(extra or []), "--dump-dom", url],
        # The DOM is UTF-8 whatever the platform: on Windows text=True alone
        # decoded it as cp1252 and failed on the first accented byte.
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90,
    )
    return result.stdout


class Connections:
    """
    A port that accepts and counts connections and says nothing: what
    "tiktok.com" resolves to in the trend checks (tiktok_rules). An https
    request never gets past its handshake here, so it is the connection
    that is counted, not a request.
    """

    def __init__(self):

        self.count = 0
        self._socket = socket.socket()
        self._socket.bind(("127.0.0.1", 0))
        self._socket.listen(16)
        self.port = self._socket.getsockname()[1]
        threading.Thread(target=self._accept, daemon=True).start()

    def _accept(self):

        while True:
            try:
                connection, _ = self._socket.accept()
            except OSError:
                return
            self.count += 1
            connection.close()

    def reset(self) -> None:

        self.count = 0


def tiktok_rules(port: int) -> list[str]:
    """Chrome flags that send every tiktok.com connection to `port` (a Connections)."""

    return [f"--host-resolver-rules=MAP *.tiktok.com 127.0.0.1:{port},MAP tiktok.com 127.0.0.1:{port}"]


class Browser:
    """
    Headless Chrome driven over the DevTools protocol on a pipe (fd 3 in,
    fd 4 out, messages ended by a NUL), so no websocket library is needed.
    One page, attached in flat mode; events are read and dropped.
    """

    def __init__(self, chrome: str, profile: str, extra: list[str] | None = None):

        to_chrome_r, self._to_chrome = os.pipe()
        self._from_chrome, from_chrome_w = os.pipe()

        def wire():
            os.dup2(to_chrome_r, 3)
            os.dup2(from_chrome_w, 4)

        self.process = subprocess.Popen(
            [chrome, "--headless=new", "--disable-gpu", "--no-sandbox", "--remote-debugging-pipe",
             f"--user-data-dir={profile}", *(extra or []), "about:blank"],
            preexec_fn=wire, close_fds=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        os.close(to_chrome_r)
        os.close(from_chrome_w)

        self._next = 0
        self._answers: dict[int, dict] = {}
        self._ready = threading.Condition()
        threading.Thread(target=self._read, daemon=True).start()

        target = self.send("Target.createTarget", {"url": "about:blank"})["targetId"]
        self.session = self.send("Target.attachToTarget", {"targetId": target, "flatten": True})["sessionId"]

    def _read(self):

        buffer = b""
        while chunk := os.read(self._from_chrome, 65536):
            buffer += chunk
            *messages, buffer = buffer.split(b"\0")
            for raw in messages:
                message = json.loads(raw)
                if "id" in message:
                    with self._ready:
                        self._answers[message["id"]] = message
                        self._ready.notify_all()

    def send(self, method: str, params: dict | None = None, session: str | None = None, timeout: float = 30) -> dict:

        self._next += 1
        ident = self._next
        message = {"id": ident, "method": method, "params": params or {}}
        if session:
            message["sessionId"] = session
        os.write(self._to_chrome, json.dumps(message).encode("utf-8") + b"\0")

        with self._ready:
            if not self._ready.wait_for(lambda: ident in self._answers, timeout=timeout):
                raise TimeoutError(f"no answer to {method}")
            answer = self._answers.pop(ident)

        if "error" in answer:
            raise RuntimeError(f"{method}: {answer['error']}")
        return answer.get("result", {})

    def evaluate(self, expression: str):

        result = self.send("Runtime.evaluate", {"expression": expression, "returnByValue": True}, self.session)
        return result.get("result", {}).get("value")

    def until(self, expression: str, timeout: float = 30) -> bool:

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.evaluate(expression):
                return True
            time.sleep(0.1)
        return False

    def close(self):

        self.process.terminate()
        try:
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.kill()
        os.close(self._to_chrome)


# React keeps a controlled textarea's value in its own state: set through
# the native setter and announced with an input event, or React restores
# the old value on the next render.
START_JOB = """
((bulk) => {
  if (bulk) {
    const box = [...document.querySelectorAll('label.checkbox-label')]
      .find((label) => label.textContent.includes('Bulk mode')).querySelector('input');
    if (!box.checked) box.click();
  }
  const area = document.querySelector('#urls-input');
  const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set;
  setter.call(area, 'https://example.org/a');
  area.dispatchEvent(new Event('input', { bubbles: true }));
  setTimeout(() => document.querySelector('form button[type=submit]').click(), 50);
  return true;
})(%s)
"""


def leave_while_polling(chrome: str, base: str, bulk: bool = False) -> tuple[bool, str]:
    """Start a job, leave the page while its first poll is held, count the polls after."""

    import tempfile

    Stub.slow_polls.clear()

    with tempfile.TemporaryDirectory() as profile:

        browser = Browser(chrome, profile)

        try:
            browser.send("Page.navigate", {"url": f"{base}/"}, browser.session)
            if not browser.until("!!document.querySelector('#urls-input') && document.readyState === 'complete'"):
                return False, "the Analyze page never loaded"

            browser.evaluate(START_JOB % ("true" if bulk else "false"))

            deadline = time.monotonic() + 15
            while not Stub.slow_polls and time.monotonic() < deadline:
                time.sleep(0.05)
            if not Stub.slow_polls:
                return False, "the job was never polled"

            # Client-side navigation: Next's Link unmounts the job card
            # while the first poll is still held by the stub.
            browser.evaluate("document.querySelector('a[href=\"/reader\"]').click()")
            if not browser.until("location.pathname === '/reader'", timeout=10):
                return False, "the page never left /"
            left = time.monotonic()

            time.sleep(HELD_SECONDS + 4)

        finally:
            browser.close()

    after = [moment for moment in Stub.slow_polls if moment > left]

    return not after, f"{len(after)} poll(s) after leaving the page, {len(Stub.slow_polls)} in all"


HYDRATED = (
    "(() => { const b = document.querySelector('[data-testid=tiktok-load]');"
    " return !!b && Object.keys(b).some((k) => k.startsWith('__reactProps')); })()"
)


def click_tiktok(chrome: str, base: str, tiktok: Connections) -> tuple[bool, str]:
    """Open the trend's story, click the facade, and see the player's iframe appear and TikTok connected to."""

    import tempfile

    tiktok.reset()

    with tempfile.TemporaryDirectory() as profile:

        browser = Browser(chrome, profile, tiktok_rules(tiktok.port))

        try:
            browser.send("Page.navigate", {"url": f"{base}/reader/stories/{STORY_ID}"}, browser.session)
            # The button is in the server's HTML before React hydrates it, and
            # a click before that does nothing: wait for React's own key.
            if not browser.until(HYDRATED):
                return False, "the facade never appeared, or never came alive"
            if browser.evaluate("!!document.querySelector('iframe')") or tiktok.count:
                return False, "TikTok was loaded before the click"

            browser.evaluate("document.querySelector('[data-testid=tiktok-load]').click()")
            src = f"https://www.tiktok.com/player/v1/{VIDEO_ID}"
            if not browser.until(f"document.querySelector('iframe')?.src === '{src}'", timeout=10):
                return False, "no player iframe after the click"

            deadline = time.monotonic() + 10
            while not tiktok.count and time.monotonic() < deadline:
                time.sleep(0.1)

        finally:
            browser.close()

    return bool(tiktok.count), f"{tiktok.count} connection(s) to TikTok after the click"


def main(argv=None) -> int:

    parser = argparse.ArgumentParser(description="End-to-end checks of the frontend.")
    parser.add_argument("--no-build", action="store_true", help="use the existing .next build")
    args = parser.parse_args(argv)

    # Chrome's DevTools pipe is handed over as file descriptors 3 and 4
    # (preexec_fn and dup2, in Browser), and the server is stopped by its
    # process group: neither exists on Windows. Run here, the script died
    # on `npm` (npm.cmd) with a bare FileNotFoundError (2026-10-28).
    if os.name == "nt":
        print("The e2e checks need Linux or macOS (Chrome's DevTools pipe on fds 3 and 4): "
              "run them in WSL or on a POSIX machine.", file=sys.stderr)
        return 2

    chrome = find_chrome()
    if chrome is None:
        print("No Chrome or Chromium found (set CHROME to its path): the e2e checks need one.", file=sys.stderr)
        return 2

    if not args.no_build:
        print("Building the frontend...")
        if subprocess.run(["npm", "run", "build"], cwd=FRONTEND, stdout=subprocess.DEVNULL).returncode != 0:
            print("npm run build failed.", file=sys.stderr)
            return 1

    stub_port, web_port = free_port(), free_port()

    stub = ThreadingHTTPServer(("127.0.0.1", stub_port), Stub)
    threading.Thread(target=stub.serve_forever, daemon=True).start()

    env = {**os.environ, "BACKEND_URL": f"http://127.0.0.1:{stub_port}"}
    env.pop("STORAGE_API_KEY", None)
    env.pop("PUBLIC_SITE_URL", None)

    # Its own process group, killed whole at the end: `npx`/`next start`
    # leave a node child that outlives its parent, and a stale server on
    # the port answers the next run's requests from an old build.
    server = subprocess.Popen(
        [str(FRONTEND / "node_modules" / ".bin" / "next"), "start", "-p", str(web_port), "-H", "127.0.0.1"],
        cwd=FRONTEND, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
    )

    base = f"http://127.0.0.1:{web_port}"

    try:
        for _ in range(60):
            try:
                if get(f"{base}/reader")[0] == 200:
                    break
            except OSError:
                pass
            time.sleep(1)
        else:
            print("The frontend never answered.", file=sys.stderr)
            return 2

        checks = Checks()
        run(checks, chrome, base, Connections())

    finally:
        try:
            os.killpg(server.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        server.wait(timeout=30)
        stub.shutdown()

    print(f"\n{'All e2e checks passed.' if not checks.failed else f'{checks.failed} e2e check(s) failed.'}")

    return 1 if checks.failed else 0


def run(checks: Checks, chrome: str, base: str, tiktok: Connections) -> None:

    print("Job polling")
    first = json.loads(get(f"{base}/api/jobs/job1")[1])
    second = json.loads(get(f"{base}/api/jobs/job1")[1])
    checks.check(
        "every poll reaches the backend (no Data Cache on /api/jobs/<id>)",
        (first.get("status"), second.get("status"), Stub.job_polls) == ("running", "done", 2),
        f"got {first.get('status')} then {second.get('status')}, {Stub.job_polls} backend hit(s)",
    )

    ok, detail = leave_while_polling(chrome, base)
    checks.check("leaving the page mid-poll stops the polling (the cancelled guard)", ok, detail)

    ok, detail = leave_while_polling(chrome, base, bulk=True)
    checks.check("the same in bulk mode (useBatchAnalysisJobs' guard)", ok, detail)

    print("The reader")
    for lang, title in (("ca", "Articles verificats"), ("es", "Artículos verificados"), ("en", "Checked articles")):
        page = dom(chrome, f"{base}/reader?lang={lang}")
        checks.check(f"feed in {lang}", title in page and f'lang="{lang}"' in page, "title or <html lang> missing")

    page = dom(chrome, f"{base}/reader", lang="es")
    checks.check("feed in the browser's language without ?lang", "Artículos verificados" in page)

    page = dom(chrome, f"{base}/reader/{ARTICLE_ID}?lang=ca")
    checks.check("article: verdict panel in Catalan", "No verificat" in page and "1 certa" in page)
    checks.check("article: a failed search reads Sense comprovar, not a verdict", "Sense comprovar" in page)
    checks.check("article: badges link to the guide", f'href="/reader/guide?lang=ca#unverified"' in page)

    page = dom(chrome, f"{base}/reader/{ARTICLE_ID}")
    checks.check("article in its own language without ?lang", "No verificado" in page and 'lang="es"' in page)

    status, html = get(f"{base}/reader/guide", headers={"Accept-Language": "fr,ca;q=0.8"})
    checks.check("guide, server-rendered, from Accept-Language", status == 200 and "Com llegir els nostres veredictes" in html)

    status, html = get(f"{base}/reader/stories/{STORY_ID}")
    checks.check("story in its language, server-rendered", status == 200 and "La nostra redacció" in html)

    status, _ = get(f"{base}/reader/stories/ffffffffffffffff")
    checks.check("a withdrawn story answers a real 404", status == 404, f"got {status}")

    for path, root in (("/reader/feed.xml?lang=es", "rss"), ("/reader/sitemap.xml", "urlset")):
        status, text = get(f"{base}{path}")
        try:
            document = xml.dom.minidom.parseString(text.encode("utf-8"))
            ok = status == 200 and document.documentElement.tagName == root and f"{base}/reader" in text
        except Exception as exc:  # noqa: BLE001 - any parse failure is the finding
            ok, text = False, str(exc)
        checks.check(f"{path.split('?')[0]} is well-formed with absolute links", ok)

    page = dom(chrome, f"{base}/claim", lang="ca")
    checks.check("an operator page stays English", 'lang="en"' in page and "Claim Check" in page)

    print("A story from a trend")
    tiktok.reset()
    page = dom(chrome, f"{base}/reader/stories/{STORY_ID}", extra=tiktok_rules(tiktok.port))
    checks.check(
        "the trend is named and the video waits behind a click",
        "farmear aura" in page and 'data-testid="tiktok-load"' in page and "<iframe" not in page,
    )
    checks.check("nothing connects to TikTok before the click", not tiktok.count, f"{tiktok.count} connection(s)")

    ok, detail = click_tiktok(chrome, base, tiktok)
    checks.check("after the click, TikTok's player loads (and only then)", ok, detail)


if __name__ == "__main__":
    sys.exit(main())
