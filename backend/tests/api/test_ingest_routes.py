import json

from fastapi.testclient import TestClient

import src.api.routes as routes
from src.main import app

from tests.builders.source_builder import build_source

client = TestClient(app)


class FakeIngestion:

    def __init__(self):
        self.calls = []
        self.last_run = None

    def enabled_sources(self):
        return [build_source(id="bbc", name="BBC"), build_source(id="nasa", name="NASA")]

    def sources_for(self, groups=None, source_ids=None, edition="positive"):
        if edition == "devastating":
            return [
                build_source(id="bbc", name="BBC", devastating_groups=["violence", "hate", "despair", "catastrophe", "abuse_of_power"]),
                build_source(id="hrw", name="Human Rights Watch", devastating_groups=["violence", "hate", "abuse_of_power"]),
            ]
        return self.enabled_sources()

    def run(self, start_job, source_ids=None, per_source=3, groups=None):
        self.calls.append((source_ids, per_source) if groups is None else (source_ids, per_source, groups))
        job_id, _ = start_job("https://bbc.com/a")
        return {"sources": [], "totals": {"queued": 1}, "jobId": job_id}


def use_ingestion(monkeypatch):

    service = FakeIngestion()
    started = []

    monkeypatch.setattr(routes, "get_ingestion_service", lambda: service)
    monkeypatch.setattr(
        routes,
        "_start_job",
        lambda url, force, thresholds, purpose="article": (
            started.append((url, purpose)) or ("job-1", False)
        ),
    )

    return service, started


def test_ingest_queues_jobs_marked_as_ingestion(monkeypatch):
    """The purpose is what separates discovered articles in the scraper stats."""

    service, started = use_ingestion(monkeypatch)

    response = client.post("/ingest", json={"sources": ["nasa"], "perSource": 2})

    assert response.status_code == 200
    assert service.calls == [(["nasa"], 2)]
    assert started == [("https://bbc.com/a", "ingestion")]


def test_an_unknown_source_is_rejected_before_anything_runs(monkeypatch):

    service, _ = use_ingestion(monkeypatch)

    response = client.post("/ingest", json={"sources": ["nope"]})

    assert response.status_code == 422
    assert service.calls == []


def test_per_source_is_bounded(monkeypatch):
    """Each queued article is a full analysis; one call must not start hundreds."""

    use_ingestion(monkeypatch)

    assert client.post("/ingest", json={"perSource": 500}).status_code == 422


def test_the_sources_and_last_run_are_listed(monkeypatch):

    use_ingestion(monkeypatch)

    body = client.get("/ingest/sources").json()

    assert [source["id"] for source in body["sources"]] == ["bbc", "nasa"]
    assert body["lastRun"] is None


# ----------------------------------------------------------------------
# Topic groups and candidate rounds
# ----------------------------------------------------------------------


def test_ingest_can_be_narrowed_to_topic_groups(monkeypatch):

    service, _ = use_ingestion(monkeypatch)

    response = client.post("/ingest", json={"groups": ["environment", "science"]})

    assert response.status_code == 200
    assert service.calls == [(None, 3, ["environment", "science"])]


def test_at_most_three_known_groups_are_accepted(monkeypatch):

    service, _ = use_ingestion(monkeypatch)

    for groups in (["sports"], ["society", "science", "environment", "health"], []):
        assert client.post("/ingest", json={"groups": groups}).status_code == 422

    assert service.calls == []


def test_the_groups_and_their_source_counts_are_listed(monkeypatch):

    use_ingestion(monkeypatch)

    body = client.get("/ingest/sources").json()

    assert [group["id"] for group in body["groups"]] == ["society", "science", "environment", "culture", "health"]
    assert (body["maxGroups"], body["maxSelected"]) == (3, 20)
    assert (body["listed"], body["maxListed"]) == (20, 40)
    assert body["groups"][1]["topics"][0] == {"id": "space", "name": "Space"}


class FakeSelection:

    def __init__(self, rounds=None):
        from src.services.selection.rounds import SelectionRounds
        self.calls = []
        self.emphases = []
        self.ai_running = False
        self.rounds = rounds or SelectionRounds()

    def create_round(self, groups, source_ids, per_source, listed=20, topic_emphasis=None, **trending):
        self.calls.append(("create", groups, source_ids, per_source, listed, *([trending] if trending else [])))
        self.emphases.append(topic_emphasis)
        if trending.get("seed") == "#fyp":
            from src.services.trends.seeds import SeedError
            raise SeedError("There is nothing to search for.")
        return {"id": "0123456789abcdef", "candidates": []}

    def get(self, round_id):
        from src.services.selection.selection_service import RoundNotFound
        if round_id != "0123456789abcdef":
            raise RoundNotFound(round_id)
        return {"id": round_id}

    def show_more(self, round_id):
        self.calls.append(("more", round_id))
        return {**self.get(round_id), "candidates": []}

    def list(self, limit=20):
        return []

    def start_ai_selection(self, round_id, limit, min_score, scorer="llm"):
        self.calls.append(("ai", round_id, limit, min_score, scorer))
        return {"status": "running"}

    def queue(self, round_id, urls, start_job, notes=None, reasons=None):
        from src.services.selection.selection_service import SelectionBusy
        self.calls.append(("queue", round_id, urls) + ((notes, reasons) if notes or reasons else ()))
        if self.ai_running:
            raise SelectionBusy(round_id)
        job_id, _ = start_job(urls[0])
        return {"jobs": [{"url": urls[0], "jobId": job_id}]}

    def reject(self, round_id, url, reasons=None, note=None, site=False, undo=False):
        from src.services.selection.selection_service import InvalidSelection
        self.calls.append(("reject", round_id, url, reasons, note, site, undo))
        self.get(round_id)
        if reasons and "boring" in reasons:
            raise InvalidSelection("Not a reason offered in this edition: boring")
        return {"rejected": {} if undo else {url: {"reasons": reasons or []}}, "counts": {"rejected": 1, "chosen": 0, "blockedSites": int(site)}}

    def forget(self, edition, url=None, host=None):
        self.calls.append(("forget", edition, url, host))
        return url == "https://news.example/1" or host == "news.example"

    def record_person_selection(self, round_id, urls, notes=None, reasons=None):
        from src.services.selection.selection_service import COMPARED, InvalidSelection, SelectionBusy
        self.calls.append(("person", round_id, urls, notes, reasons))
        self.get(round_id)
        if self.ai_running:
            raise SelectionBusy(round_id)
        if len(urls) > COMPARED:
            raise InvalidSelection(f"At most {COMPARED} articles to compare with the AI.")
        return {"urls": urls, "blind": True}


def use_selection(monkeypatch):

    _, started = use_ingestion(monkeypatch)
    selection = FakeSelection()
    monkeypatch.setattr(routes, "get_selection_service", lambda: selection)
    return selection, started


def test_a_round_needs_groups_and_known_sources(monkeypatch):

    selection, _ = use_selection(monkeypatch)

    assert client.post("/ingest/rounds", json={}).status_code == 422
    assert client.post("/ingest/rounds", json={"groups": ["science"], "sources": ["nope"]}).status_code == 422
    assert client.post("/ingest/rounds", json={"groups": ["science"], "perSource": 50}).status_code == 422
    # Twenty shown by default, forty at most.
    assert client.post("/ingest/rounds", json={"groups": ["science"], "listed": 41}).status_code == 422

    response = client.post("/ingest/rounds", json={"groups": ["science"], "sources": ["nasa"], "perSource": 4})

    assert response.status_code == 200
    assert selection.calls == [("create", ["science"], ["nasa"], 4, 20)]

    client.post("/ingest/rounds", json={"groups": ["science"], "listed": 40})

    assert selection.calls[-1] == ("create", ["science"], None, 3, 40)


def test_a_rounds_topic_emphasis_is_optional_and_between_zero_and_one(monkeypatch):

    selection, _ = use_selection(monkeypatch)

    for bad in (-0.1, 1.01, "a lot"):
        assert client.post("/ingest/rounds", json={"groups": ["science"], "topicEmphasis": bad}).status_code == 422

    assert selection.calls == []

    # Omitted - or null - is the default, decided by the ranking, not here.
    assert client.post("/ingest/rounds", json={"groups": ["science"]}).status_code == 200
    assert client.post("/ingest/rounds", json={"groups": ["science"], "topicEmphasis": None}).status_code == 200
    for value in (0, 0.25, 1):
        assert client.post("/ingest/rounds", json={"groups": ["science"], "topicEmphasis": value}).status_code == 200

    assert selection.emphases == [None, None, 0.0, 0.25, 1.0]


def test_the_catalogue_says_where_the_topic_emphasis_starts(monkeypatch):

    from src.services.selection.ranking import DEFAULT_TOPIC_EMPHASIS

    use_ingestion(monkeypatch)

    assert client.get("/ingest/sources").json()["topicEmphasis"] == DEFAULT_TOPIC_EMPHASIS


def test_more_of_a_round_is_shown_only_when_asked(monkeypatch):

    selection, _ = use_selection(monkeypatch)

    assert client.post("/ingest/rounds/0123456789abcdef/more").status_code == 200
    assert selection.calls == [("more", "0123456789abcdef")]
    assert client.post("/ingest/rounds/fedcba9876543210/more").status_code == 404
    assert client.post("/ingest/rounds/not-a-round/more").status_code == 422


def test_the_ai_selection_starts_in_the_background(monkeypatch):

    selection, _ = use_selection(monkeypatch)

    response = client.post("/ingest/rounds/0123456789abcdef/ai-selection", json={"limit": 12, "minScore": 7})

    assert response.status_code == 202
    assert selection.calls == [("ai", "0123456789abcdef", 12, 7.0, "llm")]
    assert client.post("/ingest/rounds/0123456789abcdef/ai-selection", json={"limit": 21}).status_code == 422

    client.post("/ingest/rounds/0123456789abcdef/ai-selection", json={"scorer": "laya"})
    assert selection.calls[-1][-1] == "laya"
    assert client.post("/ingest/rounds/0123456789abcdef/ai-selection", json={"scorer": "gpt"}).status_code == 422


def test_a_queued_selection_becomes_ingestion_jobs(monkeypatch):

    selection, started = use_selection(monkeypatch)

    response = client.post("/ingest/rounds/0123456789abcdef/queue", json={"urls": ["https://news.example/1"]})

    assert response.status_code == 200
    assert started == [("https://news.example/1", "ingestion")]
    assert client.post("/ingest/rounds/0123456789abcdef/queue", json={"urls": []}).status_code == 422
    assert client.post(
        "/ingest/rounds/0123456789abcdef/queue",
        json={"urls": [f"https://news.example/{i}" for i in range(21)]},
    ).status_code == 422


def test_a_round_is_not_sent_while_the_ai_reads_it(monkeypatch):

    selection, started = use_selection(monkeypatch)
    selection.ai_running = True

    response = client.post("/ingest/rounds/0123456789abcdef/queue", json={"urls": ["https://news.example/1"]})

    assert response.status_code == 409
    assert started == []


def test_a_persons_own_choice_is_recorded_to_compare_with_the_ai(monkeypatch):

    selection, started = use_selection(monkeypatch)

    response = client.post(
        "/ingest/rounds/0123456789abcdef/person-selection",
        json={
            "urls": ["https://news.example/1"],
            "notes": {"https://news.example/1": "a cure"},
            "reasons": {"https://news.example/1": ["positive", "trending"]},
        },
    )

    assert response.status_code == 200 and response.json()["blind"] is True
    assert selection.calls[-1] == (
        "person", "0123456789abcdef", ["https://news.example/1"],
        {"https://news.example/1": "a cure"}, {"https://news.example/1": ["positive", "trending"]},
    )
    assert started == []

    too_many = [f"https://news.example/{i}" for i in range(6)]
    assert client.post("/ingest/rounds/0123456789abcdef/person-selection", json={"urls": too_many}).status_code == 422
    assert client.post("/ingest/rounds/0123456789abcdef/person-selection", json={"urls": []}).status_code == 422
    assert client.post("/ingest/rounds/fedcba9876543210/person-selection", json={"urls": ["x"]}).status_code == 404

    selection.ai_running = True
    assert client.post("/ingest/rounds/0123456789abcdef/person-selection", json={"urls": ["x"]}).status_code == 409


def test_why_each_was_sent_goes_with_the_queue(monkeypatch):

    selection, _ = use_selection(monkeypatch)

    client.post("/ingest/rounds/0123456789abcdef/queue", json={
        "urls": ["https://news.example/1"],
        "reasons": {"https://news.example/1": ["diversity"]},
    })

    assert selection.calls[-1] == ("queue", "0123456789abcdef", ["https://news.example/1"], None, {"https://news.example/1": ["diversity"]})


def test_a_candidate_marked_not_for_us_goes_to_the_service_with_why(monkeypatch):

    selection, started = use_selection(monkeypatch)

    response = client.post("/ingest/rounds/0123456789abcdef/reject", json={
        "url": "https://news.example/1", "reasons": ["no_impact", "politics"], "note": "a campaign", "site": True,
    })

    assert response.status_code == 200 and response.json()["counts"]["blockedSites"] == 1
    assert selection.calls[-1] == ("reject", "0123456789abcdef", "https://news.example/1", ["no_impact", "politics"], "a campaign", True, False)
    assert started == []

    client.post("/ingest/rounds/0123456789abcdef/reject", json={"url": "https://news.example/1", "undo": True})
    assert selection.calls[-1][-1] is True

    assert client.post("/ingest/rounds/0123456789abcdef/reject", json={"url": "x", "reasons": ["boring"]}).status_code == 422
    assert client.post("/ingest/rounds/0123456789abcdef/reject", json={}).status_code == 422
    assert client.post("/ingest/rounds/fedcba9876543210/reject", json={"url": "x"}).status_code == 404


def test_what_the_ranking_learned_is_listed_and_can_be_taken_back(monkeypatch, tmp_path):

    from src.services.selection.feedback import SelectionFeedback

    selection, _ = use_selection(monkeypatch)
    selection.feedback = SelectionFeedback(lambda: tmp_path)

    listed = client.get("/ingest/feedback?edition=devastating").json()
    assert listed["edition"] == "devastating" and listed["rejected"] == [] and listed["weights"][0]["weight"] == 0.5

    assert client.post("/ingest/feedback/forget", json={"url": "https://news.example/1"}).status_code == 200
    assert selection.calls[-1] == ("forget", "positive", "https://news.example/1", None)
    assert client.post("/ingest/feedback/forget", json={"host": "elsewhere.example"}).status_code == 404
    assert client.post("/ingest/feedback/forget", json={}).status_code == 422


def test_the_catalogue_offers_the_reasons_of_its_edition(monkeypatch):

    use_ingestion(monkeypatch)

    positive = [reason["id"] for reason in client.get("/ingest/sources").json()["pickReasons"]]
    devastating = [reason["id"] for reason in client.get("/ingest/sources?edition=devastating").json()["pickReasons"]]

    assert positive[:4] == ["positive", "solution", "topic", "trending"] and "diversity" in positive
    assert devastating[:2] == ["harm", "accountability"] and "positive" not in devastating

    rejecting = [reason["id"] for reason in client.get("/ingest/sources").json()["rejectReasons"]]
    assert rejecting[0] == "no_impact" and "politics" in rejecting
    assert client.get("/ingest/sources?edition=devastating").json()["rejectReasons"][0]["id"] == "no_harm"
    assert {"label", "hint"} <= set(client.get("/ingest/sources").json()["pickReasons"][0])


def test_a_kept_photo_is_served_with_the_type_its_bytes_proved(monkeypatch, tmp_path):

    from src.services.selection.rounds import SelectionRounds

    selection, _ = use_selection(monkeypatch)
    selection.rounds = SelectionRounds(tmp_path)

    folder = tmp_path / "photos" / "0123456789abcdef"
    folder.mkdir(parents=True)
    (folder / "00112233445566ff.jpg").write_bytes(b"\xff\xd8\xff\xe0 a photo")

    response = client.get("/ingest/rounds/0123456789abcdef/photos/00112233445566ff.jpg")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.content.startswith(b"\xff\xd8\xff")

    assert client.get("/ingest/rounds/0123456789abcdef/photos/ffffffffffffffff.jpg").status_code == 404
    assert client.get("/ingest/rounds/0123456789abcdef/photos/00112233445566ff.svg").status_code == 422
    assert client.get("/ingest/rounds/0123456789abcdef/photos/..%2Fsecret.jpg").status_code in (404, 422)


def test_an_unknown_or_malformed_round_id(monkeypatch):

    use_selection(monkeypatch)

    assert client.get("/ingest/rounds/fedcba9876543210").status_code == 404
    assert client.get("/ingest/rounds/not-a-round").status_code == 422


# ----------------------------------------------------------------------
# Trending rounds (docs/decisions/trends.md)
# ----------------------------------------------------------------------


def test_a_trending_round_needs_no_group(monkeypatch):

    selection, _ = use_selection(monkeypatch)

    response = client.post("/ingest/rounds", json={"trending": True, "perSource": 2})

    assert response.status_code == 200
    assert selection.calls == [("create", [], None, 2, 20, {
        "trending": True, "signal_ids": None, "seed": None, "search": False,
    })]


def test_a_trending_round_may_order_by_up_to_three_known_groups(monkeypatch):

    selection, _ = use_selection(monkeypatch)

    ok = client.post("/ingest/rounds", json={
        "trending": True, "groups": ["culture"], "signals": ["google_trends_es"], "seed": "  #FarmearAura ",
        "search": True, "topicEmphasis": 0.3,
    })

    assert ok.status_code == 200
    assert selection.calls[-1] == ("create", ["culture"], None, 3, 20, {
        "trending": True, "signal_ids": ["google_trends_es"], "seed": "#FarmearAura", "search": True,
    })
    assert selection.emphases[-1] == 0.3

    assert client.post("/ingest/rounds", json={"trending": True, "groups": ["nope"]}).status_code == 422
    assert client.post("/ingest/rounds", json={
        "trending": True, "groups": ["culture", "science", "health", "society"],
    }).status_code == 422


def test_a_trending_rounds_signals_seed_and_size_are_checked(monkeypatch):

    selection, _ = use_selection(monkeypatch)

    # Signals that do not exist, or none and no seed: nothing to read.
    assert client.post("/ingest/rounds", json={"trending": True, "signals": ["tiktok"]}).status_code == 422
    assert client.post("/ingest/rounds", json={"trending": True, "signals": []}).status_code == 422
    # At most five articles a trend.
    assert client.post("/ingest/rounds", json={"trending": True, "perSource": 6}).status_code == 422
    # A seed is a line, not an essay.
    assert client.post("/ingest/rounds", json={"trending": True, "seed": "x" * 301}).status_code == 422

    assert selection.calls == []

    # A seed with nothing to search for comes back as the lens's own reason.
    response = client.post("/ingest/rounds", json={"trending": True, "signals": [], "seed": "#fyp"})

    assert response.status_code == 422
    assert "nothing to search for" in response.json()["detail"]


def test_signals_seed_and_search_belong_to_a_trending_round(monkeypatch):

    selection, _ = use_selection(monkeypatch)

    for extra in ({"signals": ["google_trends_es"]}, {"seed": "#x"}, {"search": True}):
        assert client.post("/ingest/rounds", json={"groups": ["science"], **extra}).status_code == 422

    assert selection.calls == []


def test_the_catalogue_lists_the_trend_signals_and_the_lenss_limits(monkeypatch):

    use_ingestion(monkeypatch)

    body = client.get("/ingest/sources").json()

    assert {signal["id"] for signal in body["signals"]} >= {"google_trends_es", "uplifting_news"}
    assert body["trending"] == {"perTrend": 2, "maxPerTrend": 5, "maxTrendAgeHours": 72, "maxArticleAgeDays": 7, "maxCandidates": 20}


# ----------------------------------------------------------------------
# The editions (docs/decisions/editions.md)
# ----------------------------------------------------------------------


def test_the_catalogue_offers_the_devastating_editions_own_groups(monkeypatch):

    use_ingestion(monkeypatch)

    body = client.get("/ingest/sources", params={"edition": "devastating"}).json()

    assert body["edition"] == "devastating"
    assert [group["id"] for group in body["groups"]] == ["violence", "hate", "despair", "catastrophe", "abuse_of_power"]
    assert body["groups"][0]["topics"][0] == {"id": "terrorism", "name": "Terrorism"}
    # Counted by the groups each source names for this edition.
    assert {group["id"]: group["sources"] for group in body["groups"]} == {
        "violence": 2, "hate": 2, "despair": 1, "catastrophe": 1, "abuse_of_power": 2,
    }
    assert [source["id"] for source in body["sources"]] == ["bbc", "hrw"]
    assert "uplifting_news" not in {signal["id"] for signal in body["signals"]}

    assert client.get("/ingest/sources", params={"edition": "cheerful"}).status_code == 422


def test_a_round_takes_only_its_editions_groups(monkeypatch):

    selection, _ = use_selection(monkeypatch)

    assert client.post("/ingest/rounds", json={"groups": ["science"], "edition": "devastating"}).status_code == 422
    assert client.post("/ingest/rounds", json={"groups": ["violence"]}).status_code == 422
    assert selection.calls == []

    response = client.post("/ingest/rounds", json={"groups": ["violence", "hate"], "edition": "devastating"})

    assert response.status_code == 200
    assert selection.calls == [("create", ["violence", "hate"], None, 3, 20, {"edition": "devastating"})]


def test_a_rounds_picks_are_analysed_in_the_rounds_edition(monkeypatch):
    """Whatever the request says: a Devastating round's picks judged by the positive gate would all be turned away."""

    selection, _ = use_selection(monkeypatch)
    selection.get = lambda round_id: {"id": round_id, "edition": "devastating"}

    editions = []
    monkeypatch.setattr(
        routes,
        "_start_job",
        lambda url, force, thresholds, purpose="article": editions.append(thresholds.edition) or ("job-1", False),
    )

    response = client.post(
        "/ingest/rounds/0123456789abcdef/queue",
        json={"urls": ["https://bbc.com/a"], "thresholds": {"edition": "positive"}},
    )

    assert response.status_code == 200
    assert editions == ["devastating"]


def test_the_judgements_are_listed_and_their_dataset_downloads_as_json_lines_or_csv(monkeypatch, tmp_path):

    from types import SimpleNamespace

    from src.services.selection.judgements import CSV_COLUMNS, SelectionJudgements

    log = SelectionJudgements(tmp_path)
    round_ = {
        "id": "0123456789abcdef", "startedAt": "2026-11-26T10:00:00+00:00", "edition": "positive", "groups": ["health"],
        "candidates": [{"url": "https://news.example/1", "title": "One"}, {"url": "https://news.example/2", "title": "Two"}],
        "queued": {"at": "2026-11-26T10:05:00+00:00", "urls": ["https://news.example/2"], "reasons": {"https://news.example/2": ["positive"]}},
    }
    log.backfill([round_])
    monkeypatch.setattr(routes, "get_selection_service", lambda: SimpleNamespace(judgements=log))

    summary = client.get("/ingest/judgements").json()
    assert summary["rows"] == 2 and summary["labels"]["chosen"] == 1 and summary["latest"][0]["kind"] == "sent"
    assert client.get("/ingest/judgements?edition=devastating").json()["rows"] == 0
    assert client.get("/ingest/judgements?edition=other").status_code == 422

    events = client.get("/ingest/judgements/events")
    assert [json.loads(line)["kind"] for line in events.text.splitlines()] == ["shown", "sent"]

    rows = client.get("/ingest/judgements/dataset")
    assert [json.loads(line)["label"] for line in rows.text.splitlines()] == ["not_chosen", "chosen"]
    assert 'filename="judgements-all.jsonl"' in rows.headers["content-disposition"]

    table = client.get("/ingest/judgements/dataset?format=csv&edition=positive")
    assert table.headers["content-type"].startswith("text/csv")
    assert table.text.splitlines()[0] == ",".join(CSV_COLUMNS) and len(table.text.splitlines()) == 3
    assert client.get("/ingest/judgements/dataset?format=xlsx").status_code == 422
