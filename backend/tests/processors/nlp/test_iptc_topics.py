"""
The MN-DS (IPTC) topic classifier as the backend reads it (2026-11-17): a weight
file scored with numpy, and the enrichment ordering the 23 topics by its group.
"""

from types import SimpleNamespace

import numpy as np

from src.config.thresholds import PipelineThresholds
from src.models.nlp.topic_prediction import TopicPrediction
from src.processors.nlp.iptc_topics import GROUP_OF_IPTC, IptcTopicClassifier, lead
from src.workflows.enrichment import NewsEnrichmentPipeline


def weights(tmp_path, classes):
    path = tmp_path / "iptc.npz"
    coef = np.eye(len(classes), 4, dtype=np.float32)
    np.savez_compressed(path, coef=coef, intercept=np.zeros(len(classes), dtype=np.float32), classes=np.asarray(classes))
    return path


def test_the_most_probable_category_comes_first_with_its_group(tmp_path):

    classifier = IptcTopicClassifier(weights(tmp_path, ["environment", "politics", "health", "sport"]))

    ranked = classifier.predict([0.1, 0.2, 3.0, 0.0])

    assert ranked[0].category == "health" and ranked[0].group == "health"
    assert abs(sum(topic.probability for topic in ranked) - 1.0) < 1e-6
    assert [t.group for t in ranked if t.category == "politics"] == [None]


def test_the_lead_is_the_title_and_the_first_eighty_words():

    text = lead("A title", " ".join(f"w{i}" for i in range(200)))

    assert text.startswith("A title. w0") and text.endswith("w79")


def test_the_table_maps_onto_the_five_groups_only():

    assert set(GROUP_OF_IPTC.values()) == {"society", "science", "environment", "culture", "health"}


def pipeline_with(classifier):

    pipeline = NewsEnrichmentPipeline.__new__(NewsEnrichmentPipeline)
    pipeline.iptc = classifier
    pipeline.embedding = SimpleNamespace(service=SimpleNamespace(encode=lambda text: [0.0, 0.0, 3.0, 0.0]))
    return pipeline


TOPICS = [
    TopicPrediction(topic="Arts", confidence=0.6, probability=0.05),
    TopicPrediction(topic="Medicine", confidence=0.5, probability=0.05),
]


def test_under_iptc_the_topics_of_its_group_come_first(tmp_path):

    pipeline = pipeline_with(IptcTopicClassifier(weights(tmp_path, ["environment", "politics", "health", "sport"])))
    article = SimpleNamespace(title="T", content="Body.")

    topics, iptc = pipeline._iptc_group(article, list(TOPICS), PipelineThresholds(topic_group_classifier="iptc"))

    assert iptc["category"] == "health" and iptc["group"] == "health"
    from src.workflows.enrichment import GROUP_OF_NAME
    assert GROUP_OF_NAME[topics[0].topic] == "health"


def test_by_default_nothing_changes(tmp_path):

    pipeline = pipeline_with(IptcTopicClassifier(weights(tmp_path, ["environment", "politics", "health", "sport"])))

    topics, iptc = pipeline._iptc_group(SimpleNamespace(title="T", content="B"), list(TOPICS), PipelineThresholds(topic_group_classifier="embedding"))

    assert topics == TOPICS and iptc is None


def test_off_the_mission_keeps_the_topics_and_records_the_category(tmp_path):

    pipeline = pipeline_with(IptcTopicClassifier(weights(tmp_path, ["environment", "politics", "sport", "health"])))

    # The stub's vector puts its weight on the third class: sport.
    topics, iptc = pipeline._iptc_group(SimpleNamespace(title="T", content="B"), list(TOPICS), PipelineThresholds(topic_group_classifier="iptc"))

    assert iptc == {"category": "sport", "probability": iptc["probability"], "group": None}
    assert topics == TOPICS
