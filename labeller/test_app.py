"""
Standard library only, like the app:  python -m unittest labeller/test_app.py
(./scripts/check.sh runs it too). Every test writes to a temporary
folder - never to backend/data/evaluation/manual/.
"""

import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import app  # noqa: E402

PILOT = app.ROOT / "backend" / "data" / "evaluation" / "xfact_en_es_pilot.jsonl"


def fact(**overrides):

    data = {
        "claim": "The reserve's otter population doubled between 2015 and 2024.",
        "language": "en",
        "articleUrl": "https://www.positive.news/environment/otters/",
        "claimDate": "2025-03-02",
        "label": "TRUE",
        "referenceEvidenceLinks": ["https://example.org/census-2024.pdf"],
        "topic": "nature",
        "claimType": "numerical",
        "sourceTier": "primary",
    }
    data.update(overrides)

    return data


class LabellerTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name) / "manual"
        self.store = app.Store(self.folder)

    def tearDown(self):
        self.tmp.cleanup()

    def create(self, **overrides):
        record, errors = self.store.create(fact(**overrides))
        self.assertEqual(errors, [])
        return record

    def errors(self, **overrides):
        return " ".join(app.validate(fact(**overrides), self.store.topics)[1])

    # ------------------------------------------------------------------
    # One file per fact, in x-fact's format
    # ------------------------------------------------------------------

    def test_each_fact_is_its_own_numbered_file(self):

        self.create()
        self.create(claim="Another claim.")

        self.assertEqual(sorted(p.name for p in self.folder.iterdir()), ["fact001.json", "fact002.json"])

    def test_a_fact_left_out_of_the_set_keeps_its_number(self):

        self.create()
        self.create(claim="Off-mission claim.")
        excluded = self.folder.parent / "excluded"
        excluded.mkdir()
        (self.folder / "fact002.json").rename(excluded / "fact002.json")

        self.assertEqual(self.create(claim="Next claim.")["id"], "fact003")
        self.assertEqual([f["id"] for f in self.store.load()[0]], ["fact001", "fact003"])

    # ------------------------------------------------------------------
    # Synthetic FALSE facts: one element of a TRUE claim substituted
    # ------------------------------------------------------------------

    def test_a_mutation_is_false_carries_its_sources_evidence_and_names_it(self):

        source = self.create()
        record, errors = self.store.mutate(
            source["id"], "The reserve's otter population halved between 2015 and 2024.", "relation",
        )

        self.assertEqual(errors, [])
        self.assertEqual((record["label"], record["labelRaw"]), ("FALSE", "refuted"))
        self.assertEqual((record["mutatedFrom"], record["mutation"]), ("fact001", "relation"))
        for key in app.MUTATION_COPIES:
            self.assertEqual(record[key], source[key], key)

    def test_only_a_natural_true_fact_is_mutated_and_the_claim_must_change(self):

        unverified = self.create(label="UNVERIFIED", referenceEvidenceLinks=[])
        true = self.create(claim="Another claim.")
        mutation, _ = self.store.mutate(true["id"], "A changed claim.", "entity")

        self.assertIn("not a natural TRUE fact", " ".join(self.store.mutate(unverified["id"], "Changed.", "number")[1]))
        self.assertIn("not a natural TRUE fact", " ".join(self.store.mutate(mutation["id"], "Changed again.", "number")[1]))
        self.assertIn("unchanged", " ".join(self.store.mutate(true["id"], "Another claim.", "number")[1]))
        self.assertIn("not in the set", " ".join(self.store.mutate("fact099", "Changed.", "number")[1]))

    def test_a_mutation_is_labelled_false_and_never_a_negation(self):

        self.assertIn("label it FALSE", self.errors(mutatedFrom="fact001", mutation="number"))
        # "not" is how a model learns to guess REFUTES without evidence.
        self.assertIn("mutation must be one of", self.errors(label="FALSE", mutatedFrom="fact001", mutation="negation"))
        self.assertIn("mutatedFrom must name", self.errors(label="FALSE", mutation="number"))

    def test_editing_a_mutation_in_the_form_keeps_it_a_mutation(self):

        source = self.create()
        mutation, _ = self.store.mutate(source["id"], "The otter population halved.", "relation")
        form = {k: v for k, v in mutation.items() if k not in ("mutatedFrom", "mutation")}

        record, errors = self.store.update(mutation["id"], {**form, "annotatorNote": "Checked by hand."})

        self.assertEqual(errors, [])
        self.assertEqual((record["mutatedFrom"], record["mutation"]), ("fact001", "relation"))

    def test_a_mutation_whose_source_is_relabelled_is_flagged(self):

        source = self.create()
        mutation, _ = self.store.mutate(source["id"], "The otter population halved.", "relation")
        self.assertEqual(app.summarise(self.store.load()[0])["staleMutations"], [])

        self.store.update(source["id"], fact(label="PARTIALLY_TRUE"))
        summary = app.summarise(self.store.load()[0])

        self.assertEqual(summary["staleMutations"], [mutation["id"]])
        self.assertEqual(summary["mutated"], 1)

    def test_a_fact_file_starts_with_xfacts_keys_in_xfacts_order(self):

        self.create()
        row = json.loads((self.folder / "fact001.json").read_text(encoding="utf-8"))

        self.assertEqual(tuple(row)[: len(app.XFACT_FIELDS)], app.XFACT_FIELDS)
        self.assertEqual((row["id"], row["labelRaw"], row["split"]), ("fact001", "supported", "test"))

    def test_the_xfact_keys_carry_the_pilots_types(self):
        """Whatever loads the x-fact set must load the joined custom set."""

        self.create()
        ours = json.loads((self.folder / "fact001.json").read_text(encoding="utf-8"))
        theirs = json.loads(PILOT.read_text(encoding="utf-8").splitlines()[0])

        self.assertEqual(tuple(theirs), app.XFACT_FIELDS)
        for key in app.XFACT_FIELDS:
            if theirs[key] is not None and ours[key] is not None:
                self.assertIs(type(ours[key]), type(theirs[key]), key)

    def test_spanish_is_written_readable(self):

        self.create(claim="La población de nutrias se duplicó.", language="es")

        self.assertIn("población", (self.folder / "fact001.json").read_text(encoding="utf-8"))

    def test_topics_come_from_the_classifier_and_each_has_one_group(self):

        topics = app.load_topics()

        self.assertEqual(len(topics), 23)
        self.assertEqual(topics["mental_health"], "Mental Health")
        self.assertEqual(sorted(app.GROUP_OF), sorted(topics))

    # ------------------------------------------------------------------
    # The guide's rules
    # ------------------------------------------------------------------

    def test_a_verdict_other_than_unverified_needs_a_link(self):

        self.assertIn("evidence link", self.errors(referenceEvidenceLinks=[]))
        self.assertEqual(self.errors(label="UNVERIFIED", referenceEvidenceLinks=[]), "")

    def test_only_the_organisations_own_source_is_not_enough_evidence(self):

        self.assertIn("UNVERIFIED", self.errors(onlyOwnSource=True, annotatorNote="NGO release"))
        self.assertIn("note", self.errors(onlyOwnSource=True, label="UNVERIFIED"))
        self.assertEqual(self.errors(onlyOwnSource=True, label="UNVERIFIED", annotatorNote="NGO release"), "")

    def test_evidence_newer_than_the_article_is_rejected(self):

        self.assertIn("newer than the article", self.errors(evidenceDate="2025-04-01"))
        self.assertEqual(self.errors(evidenceDate="2025-03-02"), "")

    def test_bad_values_are_all_reported_at_once(self):

        text = self.errors(topic="politics", label="MAYBE", referenceEvidenceLinks=["javascript:alert(1)"], claimDate="soon")

        for expected in ("topic", "label", "javascript", "claimDate"):
            self.assertIn(expected, text)

    def test_the_site_defaults_to_the_articles_domain(self):

        self.assertEqual(self.create()["site"], "positive.news")
        self.assertIn("site", self.errors(articleUrl=None))

    # ------------------------------------------------------------------
    # Editing and review
    # ------------------------------------------------------------------

    def test_an_edit_rewrites_the_same_file_and_keeps_its_creation_date(self):

        first = self.create()
        edited, errors = self.store.update("fact001", fact(label="FALSE"))

        self.assertEqual(errors, [])
        self.assertEqual((edited["label"], edited["createdAt"]), ("FALSE", first["createdAt"]))
        self.assertEqual([p.name for p in self.folder.iterdir()], ["fact001.json"])
        self.assertEqual(self.store.update("fact009", fact())[1], ["Fact not found."])

    # ------------------------------------------------------------------
    # Time per fact
    # ------------------------------------------------------------------

    def timed(self, opened="2026-10-20T10:00:00Z", active=300, now="2026-10-20T10:12:00", **overrides):
        from unittest import mock
        with mock.patch.object(app, "_now", return_value=now):
            return self.store.create(fact(timing={"openedAt": opened, "activeSeconds": active}, **overrides))

    def test_a_new_fact_records_how_long_it_took_after_every_other_key(self):

        record, errors = self.timed()

        self.assertEqual(errors, [])
        self.assertEqual(record["timing"], {
            "openedAt": "2026-10-20T10:00:00", "savedAt": "2026-10-20T10:12:00", "activeSeconds": 300,
        })

        row = json.loads((self.folder / "fact001.json").read_text(encoding="utf-8"))
        self.assertEqual(list(row)[-1], "timing")
        # x-fact's ten keys still lead, in x-fact's order.
        self.assertEqual(tuple(row)[: len(app.XFACT_FIELDS)], app.XFACT_FIELDS)

    def test_an_edit_keeps_the_first_saves_timing(self):

        first, _ = self.timed()
        edited, errors = self.store.update(
            "fact001", fact(label="FALSE", timing={"openedAt": "2026-10-21T09:00:00Z", "activeSeconds": 5}),
        )

        self.assertEqual(errors, [])
        self.assertEqual(edited["timing"], first["timing"])

    def test_a_timing_that_does_not_add_up_is_dropped_and_never_blocks_a_save(self):

        cases = [
            {"active": 2000},                             # more visible seconds than the form was open
            {"active": -1},
            {"active": "soon"},
            {"opened": "yesterday"},
            {"opened": "2026-10-20T01:00:00Z"},           # open for 11 hours: a forgotten tab
        ]

        for case in cases:
            record, errors = self.timed(**case, claim=f"Claim for {case}.")
            self.assertEqual(errors, [], case)
            self.assertIsNone(record["timing"], case)

        # A fact saved without one, from the command line or an old page.
        self.assertIsNone(self.create(claim="No timing at all.")["timing"])

    def test_the_review_sample_is_a_stable_fifth(self):

        for i in range(11):
            self.create(claim=f"Claim {i}")

        facts, _ = self.store.load()
        sample = app.review_sample(facts)

        self.assertEqual(len(sample), 3)  # ceil(11 * 0.2)
        self.assertEqual([f["id"] for f in app.review_sample(list(reversed(facts)))], [f["id"] for f in sample])

    def test_the_review_is_blind(self):

        self.create(annotatorNote="Checked the census PDF")

        item = app.state(self.store)["review"]["sample"][0]

        for hidden in ("label", "labelRaw", "annotatorNote", "onlyOwnSource"):
            self.assertNotIn(hidden, item)

    def test_agreement_is_measured_on_the_first_label_even_after_a_correction(self):

        self.create()
        self.store.review("fact001", "PARTIALLY_TRUE", None)
        # The disagreement is settled by correcting the label ...
        self.store.update("fact001", fact(label="PARTIALLY_TRUE"))

        # ... which must not turn it into an agreement afterwards.
        result = app.agreement(self.store.load()[0])

        self.assertEqual((result["reviewed"], result["observed"]), (1, 0))
        self.assertEqual(result["disagreements"][0]["firstLabel"], "TRUE")

    def test_cohens_kappa_discounts_chance_agreement(self):

        # Three of four agree: observed 0.75. First labels TRUE 2 / FALSE 2,
        # second TRUE 3 / FALSE 1: expected (2*3 + 2*1) / 16 = 0.5, so
        # kappa = (0.75 - 0.5) / (1 - 0.5) = 0.5.
        for i, (first, second) in enumerate([("TRUE", "TRUE"), ("TRUE", "TRUE"), ("FALSE", "FALSE"), ("FALSE", "TRUE")]):
            record = self.create(claim=f"Claim {i}", label=first)
            self.store.review(record["id"], second, None)

        result = app.agreement(self.store.load()[0])

        self.assertEqual((result["observed"], result["kappa"]), (0.75, 0.5))

    def test_kappa_is_undefined_when_every_label_is_the_same(self):

        self.create()
        self.store.review("fact001", "TRUE", None)

        self.assertIsNone(app.agreement(self.store.load()[0])["kappa"])

    # ------------------------------------------------------------------
    # The tuning/test split
    # ------------------------------------------------------------------

    def article(self, n):
        return f"https://www.positive.news/environment/story-{n}/"

    def test_an_articles_facts_and_a_mutation_with_its_source_share_a_side(self):

        for n in range(6):
            self.create(claim=f"First claim {n}", articleUrl=self.article(n))
            self.create(claim=f"Second claim {n}", articleUrl=self.article(n))
        self.store.mutate("fact001", "The reserve's otter population tripled.", "number")

        self.store.split()
        facts = {f["id"]: f for f in self.store.load()[0]}

        for n in range(6):
            first, second = facts[f"fact{2 * n + 1:03d}"], facts[f"fact{2 * n + 2:03d}"]
            self.assertEqual(first["split"], second["split"])
        self.assertEqual(facts["fact013"]["split"], facts["fact001"]["split"])

    def test_the_split_is_even_within_each_verdict_language_and_topic_group(self):

        # Two of everything, one article each: an even split puts one of
        # each pair on each side.
        n = 0
        for label in ("TRUE", "UNVERIFIED"):
            for language in ("en", "es"):
                for topic in ("nature", "arts"):
                    for _ in range(2):
                        n += 1
                        extra = {} if label == "TRUE" else {"referenceEvidenceLinks": []}
                        self.create(claim=f"Claim {n}", articleUrl=self.article(n), label=label,
                                    language=language, topic=topic, **extra)

        counts = self.store.split()["counts"]

        self.assertEqual((counts["train"]["total"], counts["test"]["total"]), (8, 8))
        for side in app.SPLITS:
            self.assertEqual(counts[side]["byLabel"]["TRUE"], 4)
            self.assertEqual(counts[side]["byLanguage"], {"en": 4, "es": 4})
            self.assertEqual(counts[side]["byGroup"]["environment"], 4)

    def test_the_split_is_frozen_and_new_facts_join_their_articles_side(self):

        for n in range(8):
            self.create(claim=f"Claim {n}", articleUrl=self.article(n))
        first = self.store.split()

        # Relabelling a fact keeps its side; running the split again moves nothing.
        self.store.update("fact001", fact(articleUrl=self.article(0), label="PARTIALLY_TRUE"))
        again = self.store.split()
        self.assertEqual(again["facts"], first["facts"])
        self.assertEqual(again["frozenAt"], first["frozenAt"])

        # A later claim of an article already split goes where its article is.
        later = self.create(claim="A third claim of story 3.", articleUrl=self.article(3))
        self.assertEqual(later["split"], first["facts"]["fact004"])
        self.assertEqual(self.store.split_manifest()["facts"]["fact009"], later["split"])

    def test_before_the_freeze_every_fact_is_held_out(self):

        self.assertEqual(self.create()["split"], "test")
        self.assertEqual(self.store.split_manifest(), {})

    def test_the_review_sample_is_a_fifth_of_the_held_out_half(self):

        for n in range(20):
            self.create(claim=f"Claim {n}", articleUrl=self.article(n))
        manifest = self.store.split()
        facts, _ = self.store.load()

        sample = app.review_sample(facts)

        self.assertEqual(len(sample), 2)  # ceil(10 test facts * 0.2)
        self.assertTrue(all(f["split"] == "test" for f in sample))
        self.assertEqual(sorted(f["id"] for f in sample), manifest["recheck"])

    def test_join_refuses_a_fact_with_no_side(self):

        self.create()
        record = json.loads((self.folder / "fact001.json").read_text(encoding="utf-8"))
        record["split"] = "dev"
        (self.folder / "fact001.json").write_text(json.dumps(record), encoding="utf-8")

        with self.assertRaises(ValueError) as caught:
            self.store.join(Path(self.tmp.name) / "joined.jsonl")

        self.assertIn("split must be one of", str(caught.exception))

    # ------------------------------------------------------------------
    # Join
    # ------------------------------------------------------------------

    def test_join_writes_one_jsonl_line_per_fact_in_number_order(self):

        for i in range(3):
            self.create(claim=f"Claim {i}")
        out = Path(self.tmp.name) / "joined.jsonl"

        summary = self.store.join(out)
        lines = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(summary["total"], 3)
        self.assertEqual([l["id"] for l in lines], ["fact001", "fact002", "fact003"])
        self.assertEqual(tuple(lines[0])[: len(app.XFACT_FIELDS)], app.XFACT_FIELDS)

    def test_join_refuses_a_broken_or_invalid_file(self):

        self.create()
        (self.folder / "fact002.json").write_text("{ not json", encoding="utf-8")
        out = Path(self.tmp.name) / "joined.jsonl"

        with self.assertRaises(ValueError) as caught:
            self.store.join(out)

        self.assertIn("fact002.json", str(caught.exception))
        self.assertFalse(out.exists())

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------

    def test_the_server_saves_and_serves_a_fact(self):

        handler = app.make_handler(self.store)
        handler.log_message = lambda *args: None  # one line per request is noise here
        server = HTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{server.server_address[1]}"

        def send(method, path, body, content_type="application/json"):
            request = urllib.request.Request(base + path, data=json.dumps(body).encode(), method=method, headers={"Content-Type": content_type})
            try:
                with urllib.request.urlopen(request) as response:
                    return response.status, json.loads(response.read())
            except urllib.error.HTTPError as error:
                return error.code, json.loads(error.read())

        try:
            self.assertEqual(send("POST", "/api/facts", fact())[0], 201)
            self.assertEqual(send("POST", "/api/facts", fact(referenceEvidenceLinks=[]))[0], 422)
            # Not JSON: a cross-site form post is refused.
            self.assertEqual(send("POST", "/api/facts", fact(), "text/plain")[0], 415)
            self.assertEqual(send("PUT", "/api/facts/fact001", fact(label="FALSE"))[1]["label"], "FALSE")
            self.assertEqual(send("POST", "/api/facts/fact001/review", {"label": "FALSE"})[1]["review"]["agrees"], True)
            self.assertEqual(send("PUT", "/api/facts/fact404", fact())[0], 404)

            with urllib.request.urlopen(base + "/api/state") as response:
                state = json.loads(response.read())
            with urllib.request.urlopen(base + "/") as response:
                page = response.read().decode("utf-8")

            self.assertEqual(state["summary"]["matrix"]["FALSE"]["environment"], 1)
            self.assertIn("<title>Fact labeller</title>", page)
        finally:
            server.shutdown()
            server.server_close()


def backend_batch(request_id="r1", urls=("https://a.example/1", "https://b.example/2")):
    return {
        "requestId": request_id,
        "articles": [
            {"url": url, "site": url.split("/")[2], "language": "es", "publishedAt": "2026-09-20",
             "topic": "climate", "claims": [{"text": f"Claim {i} of {url}", "selectedBy": "anchor", "figures": []}
                                            for i in range(2)]}
            for url in urls
        ],
        "skipped": [{"url": "https://c.example/broken", "source": "c", "reason": "no text"}],
    }


class FakeBackend:
    """Stands in for app.Backend: answers the two calls the queue makes."""

    base_url = "http://backend.test"

    def __init__(self, down=False):
        self.down = down
        self.sent = []
        self.running = False
        self.batch = None

    def call(self, method, path, body=None):
        if self.down:
            raise app.BackendUnreachable("Could not reach the backend at http://backend.test")
        self.sent.append((method, path, body))
        if method == "POST":
            self.running = True
            self.batch = backend_batch(body["requestId"])
            return 202, {"started": True}
        return 200, {"running": self.running, "batch": self.batch, "error": None}


class QueueTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.store = app.Store(root / "manual")
        self.queue = app.Queue(root / "queue")

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_batch_is_saved_once_per_request_and_numbered_within_a_day(self):

        first = self.queue.save(backend_batch("r1"), "2026-09-29")
        again = self.queue.save(backend_batch("r1"), "2026-09-29")
        second = self.queue.save(backend_batch("r2"), "2026-09-29")

        self.assertEqual((first, again, second), ("2026-09-29.json", "2026-09-29.json", "2026-09-29-2.json"))
        claim = self.queue.load(first)["articles"][0]["claims"][0]
        self.assertEqual((claim["status"], claim["factIds"]), ("pending", []))

    def test_labelling_skipping_and_undoing_are_counted(self):

        name = self.queue.save(backend_batch(), "2026-09-29")

        self.queue.mark(name, 0, 0, "labelled", fact_id="fact007")
        self.queue.mark(name, 0, 1, "skipped", reason="opinion")
        self.queue.mark(name, 1, 0, "skipped", reason="trivial")
        self.queue.mark(name, 1, 0, "pending")

        stats = self.queue.stats()
        self.assertEqual((stats["labelled"], stats["skipped"], stats["pending"]), (1, 1, 2))
        # Labelled over labelled + skipped: pending claims are not judged yet.
        self.assertEqual(stats["precision"], 0.5)
        self.assertEqual(stats["byReason"]["opinion"], 1)

    def test_effort_stats_give_precision_by_language_and_time_per_fact(self):

        from unittest import mock

        spanish = self.queue.save(backend_batch("r1"), "2026-09-29")
        english = backend_batch("r2", urls=("https://d.example/1",))
        english["articles"][0]["language"] = "en"
        english_name = self.queue.save(english, "2026-09-30")

        with mock.patch.object(app, "_now", return_value="2026-10-20T10:10:00"):
            labelled, _ = self.store.create(fact(timing={"openedAt": "2026-10-20T10:00:00Z", "activeSeconds": 240}))
        with mock.patch.object(app, "_now", return_value="2026-10-20T10:30:00"):
            self.store.create(fact(claim="Second.", timing={"openedAt": "2026-10-20T10:10:00Z", "activeSeconds": 480}))
        # Chosen by hand before batches existed: in no batch, never timed.
        self.store.create(fact(claim="By hand."))

        self.queue.mark(spanish, 0, 0, "labelled", fact_id=labelled["id"])
        self.queue.mark(spanish, 0, 1, "skipped", reason="opinion")
        self.queue.mark(spanish, 1, 0, "skipped", reason="fragment")
        self.queue.mark(english_name, 0, 0, "labelled", fact_id="fact002")

        stats = app.effort_stats(self.store, self.queue)

        selection = stats["selection"]
        self.assertEqual((selection["labelled"], selection["skipped"], selection["pending"]), (2, 2, 2))
        self.assertEqual(selection["precision"], 0.5)
        self.assertEqual(selection["byLanguage"]["es"]["precision"], round(1 / 3, 4))
        self.assertEqual(selection["byLanguage"]["en"]["precision"], 1.0)
        self.assertEqual(selection["byReason"]["fragment"], 1)

        self.assertEqual(stats["factsNotFromABatch"], ["fact003"])

        time = stats["timePerFact"]
        self.assertEqual((time["timed"], time["untimed"]), (2, 1))
        self.assertEqual(time["activeSeconds"], {"n": 2, "median": 360.0, "p25": 300.0, "p75": 420.0})
        self.assertEqual(time["wallSeconds"]["median"], 900.0)

    def test_the_stats_command_prints_json(self):

        import contextlib
        import io
        from unittest import mock

        out = io.StringIO()
        with mock.patch.object(app, "Store", return_value=self.store), \
                mock.patch.object(app, "Queue", return_value=self.queue), \
                contextlib.redirect_stdout(out):
            code = app.main(["stats"])

        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out.getvalue())["timePerFact"]["timed"], 0)

    def test_a_skip_needs_a_known_reason_and_a_real_claim(self):

        name = self.queue.save(backend_batch(), "2026-09-29")

        self.assertIsNone(self.queue.mark(name, 0, 0, "skipped", reason="boring")[0])
        self.assertIsNone(self.queue.mark(name, 9, 0, "skipped", reason="opinion")[0])
        self.assertIsNone(self.queue.mark("../../etc/passwd", 0, 0, "skipped", reason="opinion")[0])

    def test_the_request_leaves_out_every_article_already_labelled_or_proposed(self):

        self.store.create(fact(articleUrl="https://labelled.example/x"))
        self.queue.save(backend_batch(), "2026-09-29")

        request = app.batch_request(self.store, self.queue, {"articles": "8", "languages": ["es"]}, "id1", "2026-09-30")

        self.assertEqual(set(request["exclude"]), {
            "https://labelled.example/x", "https://a.example/1", "https://b.example/2", "https://c.example/broken",
        })
        self.assertEqual((request["articles"], request["claimsPerArticle"], request["languages"]), (8, 3, ["es"]))
        self.assertEqual((request["seed"], request["requestId"]), ("2026-09-30", "id1"))

    def test_topics_of_the_groups_the_balance_table_is_short_of_are_preferred(self):

        summary = {"byGroup": {"society": 3, "science": 3, "environment": 0, "culture": 3, "health": 3}}

        self.assertEqual(app.prefer_topics(summary), app.TOPIC_GROUPS["environment"])
        self.assertEqual(app.prefer_topics({"byGroup": {g: 2 for g in app.TOPIC_GROUPS}}), [])

    def test_the_server_fetches_saves_and_marks_a_batch(self):

        backend = FakeBackend()
        handler = app.make_handler(self.store, self.queue, backend)
        handler.log_message = lambda *args: None
        server = HTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{server.server_address[1]}"

        def send(method, path, body=None):
            data = json.dumps(body).encode() if body is not None else None
            request = urllib.request.Request(base + path, data=data, method=method, headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(request) as response:
                    return response.status, json.loads(response.read())
            except urllib.error.HTTPError as error:
                return error.code, json.loads(error.read())

        try:
            self.assertEqual(send("POST", "/api/queue/fetch", {"articles": 5})[0], 202)
            # One at a time: a second ask while the first is out is refused.
            self.assertEqual(send("POST", "/api/queue/fetch", {})[0], 409)

            self.assertEqual(send("GET", "/api/queue/status")[1], {"running": True, "startedAt": None})
            backend.running = False
            saved = send("GET", "/api/queue/status")[1]["saved"]

            state = send("GET", "/api/queue")[1]
            self.assertEqual(state["current"]["file"], saved)

            code, _ = send("POST", "/api/facts", {**fact(), "queueRef": {"name": saved, "article": 1, "claim": 0}})
            self.assertEqual(code, 201)
            self.assertEqual(send("POST", "/api/queue/claim", {"name": saved, "article": 0, "claim": 0,
                                                               "status": "skipped", "reason": "fragment"})[0], 200)

            claims = self.queue.load(saved)["articles"]
            self.assertEqual(claims[1]["claims"][0]["factIds"], ["fact001"])
            self.assertEqual(claims[0]["claims"][0]["skipReason"], "fragment")
        finally:
            server.shutdown()
            server.server_close()

    def test_a_backend_that_is_not_running_is_a_clear_error_not_a_crash(self):

        handler = app.make_handler(self.store, self.queue, FakeBackend(down=True))
        handler.log_message = lambda *args: None
        server = HTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{server.server_address[1]}"

        try:
            request = urllib.request.Request(base + "/api/queue/fetch", data=b"{}", method="POST",
                                             headers={"Content-Type": "application/json"})
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(request)
            self.assertEqual(caught.exception.code, 502)
            self.assertIn("Could not reach the backend", json.loads(caught.exception.read())["errors"][0])
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
