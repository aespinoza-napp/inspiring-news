import json
import threading

from src.services.scraper.request_stats import Outcome, Purpose, RequestStats, domain_of


def test_domains_are_compared_without_www_or_case():

    assert domain_of("https://WWW.Example.com/a?b=1") == "example.com"
    assert domain_of("https://news.example.com/a") == "news.example.com"


def test_counts_are_kept_per_domain_and_outcome():

    stats = RequestStats()

    stats.record("https://a.com/1", Outcome.OK)
    stats.record("https://a.com/2", Outcome.TIMEOUT, error="timed out")
    stats.record("https://b.com/1", Outcome.OK, purpose=Purpose.EVIDENCE)

    snapshot = stats.snapshot()

    assert snapshot["totals"] == {
        "domains": 2,
        "requests": 3,
        "ok": 2,
        "failed": 1,
        "outcomes": {"ok": 2, "timeout": 1},
    }

    # Busiest domain first.
    [a, b] = snapshot["domains"]
    assert a["domain"] == "a.com"
    assert a["requests"] == 2
    assert a["successRate"] == 0.5
    assert b["purposes"] == {"evidence": 1}


def test_the_last_failure_survives_a_later_success():
    """
    Once a source recovers, why it failed must still be answerable -
    that is the question someone opening this page is asking.
    """

    stats = RequestStats()

    stats.record("https://a.com/1", Outcome.HTTP_ERROR, status=503, error="HTTP 503")
    stats.record("https://a.com/2", Outcome.OK, status=200)

    [entry] = stats.snapshot()["domains"]

    assert entry["lastOutcome"] == "ok"
    assert entry["lastStatus"] == 200
    assert entry["lastError"] == "HTTP 503"


def test_counts_survive_a_restart(tmp_path):

    path = tmp_path / "stats" / "scraper_requests.json"

    first = RequestStats(path)
    first.record("https://a.com/1", Outcome.OK, elapsed_ms=100)
    first.record("https://a.com/2", Outcome.BLOCKED, elapsed_ms=300)

    second = RequestStats(path)
    second.record("https://a.com/3", Outcome.OK, elapsed_ms=200)

    [entry] = second.snapshot()["domains"]

    assert entry["requests"] == 3
    assert entry["outcomes"] == {"ok": 2, "blocked": 1}
    assert entry["avgMs"] == 200

    assert json.loads(path.read_text(encoding="utf-8"))["totals"]["requests"] == 3


def test_an_unreadable_file_starts_from_zero_rather_than_failing(tmp_path):

    path = tmp_path / "scraper_requests.json"
    path.write_text("{ not json", encoding="utf-8")

    stats = RequestStats(path)
    stats.record("https://a.com/1", Outcome.OK)

    assert stats.snapshot()["totals"]["requests"] == 1


def test_concurrent_records_are_all_counted(tmp_path):
    """Claims fetch their evidence from several threads at once."""

    stats = RequestStats(tmp_path / "scraper_requests.json")

    def fetch_many():
        for index in range(50):
            stats.record(f"https://a.com/{index}", Outcome.OK)

    threads = [threading.Thread(target=fetch_many) for _ in range(8)]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    assert stats.snapshot()["totals"]["requests"] == 400
    assert RequestStats(tmp_path / "scraper_requests.json").snapshot()["totals"]["requests"] == 400
