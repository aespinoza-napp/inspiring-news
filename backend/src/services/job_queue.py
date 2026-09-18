from concurrent.futures import ThreadPoolExecutor
from typing import Callable


class AnalysisJobQueue:
    """
    Bounds how many /analyze/jobs runs execute at once, across both the
    single-URL and batch routes. `BackgroundTasks` alone has no such cap -
    N near-simultaneous POSTs spawn N concurrent pipeline runs, each doing
    real scraping, inference/ HTTP calls, a SearXNG search and an LLM
    call. A plain bounded ThreadPoolExecutor queues the excess instead of
    running it all at once; nothing pipeline-specific lives here.
    """

    def __init__(self, max_workers: int):
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="analysis-job",
        )

    def submit(self, fn: Callable, *args, **kwargs):
        return self._executor.submit(fn, *args, **kwargs)
