from src.services.run_metrics import RunClock, RunMetrics


class FakeClock:

    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def sample(text: str, name: str) -> float:
    """The value of the one line in `text` starting with `name `."""

    for line in text.splitlines():
        if line.startswith(name + " "):
            return float(line.rsplit(" ", 1)[1])

    raise AssertionError(f"{name} not in:\n{text}")


def test_a_stage_is_timed_from_its_own_start_to_its_own_end():

    metrics, time = RunMetrics(), FakeClock()
    clock = RunClock(metrics, "article", clock=time)

    time.now = 1.0
    clock.observe("enriching", {})
    time.now = 9.5
    clock.observe("enriched", {})

    text = metrics.render()

    assert sample(text, 'inspiring_stage_seconds_sum{stage="enrich"}') == 8.5
    assert sample(text, 'inspiring_stage_seconds_count{stage="enrich"}') == 1


def test_concurrent_claims_are_paired_by_claim_index_not_by_order():
    """
    Two claims search at once, and claim 1 finishes first. Timed between
    consecutive events - what the job runner's log line shows - claim
    1's search would read 1s and claim 0's 2s. Paired by claimIndex,
    they are what they were: 5s and 6s.
    """

    metrics, time = RunMetrics(), FakeClock()
    clock = RunClock(metrics, "article", clock=time)

    time.now = 0.0
    clock.observe("searching_web", {"claimIndex": 0})
    time.now = 1.0
    clock.observe("searching_web", {"claimIndex": 1})
    time.now = 6.0
    clock.observe("web_results", {"claimIndex": 1, "webCount": 3})
    time.now = 6.0
    clock.observe("web_results", {"claimIndex": 0, "webCount": 2})

    text = metrics.render()

    assert sample(text, 'inspiring_stage_seconds_sum{stage="web_search"}') == 11.0
    assert sample(text, 'inspiring_stage_seconds_count{stage="web_search"}') == 2


def test_an_end_without_its_start_is_not_counted():

    metrics = RunMetrics()
    clock = RunClock(metrics, "article", clock=FakeClock())

    clock.observe("scraped", {})

    assert "stage=" not in metrics.render()


def test_searches_are_counted_by_what_came_back():
    """An empty or failed search still ends in a verdict, so it is counted on its own."""

    metrics = RunMetrics()
    clock = RunClock(metrics, "article", clock=FakeClock())

    clock.observe("web_results", {"claimIndex": 0, "webCount": 4, "searchUnavailable": False})
    clock.observe("web_results", {"claimIndex": 1, "webCount": 0, "searchUnavailable": False})
    clock.observe("web_results", {"claimIndex": 2, "webCount": 0, "searchUnavailable": True})
    clock.observe("web_results", {"claimIndex": 3, "webCount": 0, "searchUnavailable": True})

    text = metrics.render()

    assert sample(text, 'inspiring_web_searches_total{result="results"}') == 1
    assert sample(text, 'inspiring_web_searches_total{result="empty"}') == 1
    assert sample(text, 'inspiring_web_searches_total{result="unavailable"}') == 2


def test_verdicts_and_run_outcomes_are_counted():
    """
    The real event carries the Verdict enum, not its string: labelled with
    str() it read "Verdict.TRUE" on the first production run.
    """

    from src.models.fact_checker.fact_check import Verdict

    metrics, time = RunMetrics(), FakeClock()
    clock = RunClock(metrics, "ingestion", clock=time)

    clock.observe("claim_checked", {"claimIndex": 0, "verdict": Verdict.TRUE})
    clock.observe("claim_checked", {"claimIndex": 1, "verdict": "UNVERIFIED"})
    time.now = 75.0
    clock.observe("done", {})

    text = metrics.render()

    assert sample(text, 'inspiring_claims_checked_total{verdict="TRUE"}') == 1
    assert sample(text, 'inspiring_claims_checked_total{verdict="UNVERIFIED"}') == 1
    assert sample(text, 'inspiring_runs_total{outcome="done",purpose="ingestion"}') == 1
    assert sample(text, 'inspiring_run_seconds_sum{outcome="done",purpose="ingestion"}') == 75.0


def test_every_sample_line_is_declared_with_help_and_type():
    """What a Prometheus scrape needs to parse the page at all."""

    metrics = RunMetrics()
    clock = RunClock(metrics, "article", clock=FakeClock())
    clock.observe("scraping", {})
    clock.observe("scraped", {})
    clock.observe("done", {})

    text = metrics.render()
    declared = {
        line.split()[2] for line in text.splitlines() if line.startswith("# TYPE ")
    }

    for line in text.splitlines():
        if line and not line.startswith("#"):
            name = line.split("{")[0].split(" ")[0]
            base = name.removesuffix("_sum").removesuffix("_count")
            assert base in declared, line

    assert text.endswith("\n")
