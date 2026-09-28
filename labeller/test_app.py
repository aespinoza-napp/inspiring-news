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


if __name__ == "__main__":
    unittest.main()
