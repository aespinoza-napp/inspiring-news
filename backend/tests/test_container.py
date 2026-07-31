import threading
import time

import src.container as container


def _reset(*names):
    for name in names:
        setattr(container, name, None)


def test_get_vector_repository_builds_exactly_once_under_concurrency(monkeypatch):
    """
    Regression test: two /analyze/jobs requests arriving close together
    (e.g. React 18 dev-mode Strict Mode's double-effect-invoke firing two
    near-simultaneous POSTs) run in FastAPI's background threadpool and
    can both observe "not built yet" before either finishes constructing
    - without a lock, both would race to open the same exclusive-lock
    Qdrant storage path concurrently, and one would fail with "already
    accessed by another instance" even though only one process was ever
    involved. Reproduced live before this fix.
    """

    _reset("_vector_repository")

    call_count = {"n": 0}

    class SlowFakeRepository:
        def __init__(self, database):
            call_count["n"] += 1
            time.sleep(0.05)  # widen the race window

    monkeypatch.setattr(container, "VectorRepository", SlowFakeRepository)
    monkeypatch.setattr(container, "QdrantDatabase", lambda: None)

    results = []

    def worker():
        results.append(container.get_vector_repository())

    threads = [threading.Thread(target=worker) for _ in range(10)]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    assert call_count["n"] == 1
    assert len({id(result) for result in results}) == 1

    _reset("_vector_repository")


def test_get_text_corrector_builds_exactly_once_under_concurrency(monkeypatch):

    _reset("_text_corrector")

    call_count = {"n": 0}

    class SlowFakeTextCorrector:
        def __init__(self):
            call_count["n"] += 1
            time.sleep(0.05)

    monkeypatch.setattr(container, "TextCorrector", SlowFakeTextCorrector)

    results = []

    def worker():
        results.append(container.get_text_corrector())

    threads = [threading.Thread(target=worker) for _ in range(10)]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    assert call_count["n"] == 1
    assert len({id(result) for result in results}) == 1

    _reset("_text_corrector")
