"""A query asked before is answered from the file; a new one is searched and kept."""

from src.evaluation.search_cache import CachedSearxngClient


class Counting(CachedSearxngClient):

    def __init__(self, path, answers):
        super().__init__(path, base_url="http://searxng.invalid")
        self.answers = answers
        self.sent = []

    def _fetch(self, query, language):
        self.sent.append(query)
        return self.answers.get(query, [])


def test_an_answer_is_kept_and_read_back_by_the_next_run(tmp_path):

    path = tmp_path / "searches.jsonl"
    hits = [{"url": "https://a.example", "title": "A"}]

    first = Counting(path, {"Boracay photos taken": hits})
    assert first.search("Boracay photos taken") == hits
    assert first.sent == ["Boracay photos taken"]

    second = Counting(path, {"Boracay photos taken": [{"url": "https://other.example"}]})
    assert second.search("Boracay photos taken") == hits
    assert second.sent == [] and second.last_route() == "recorded"


def test_an_empty_answer_is_not_kept(tmp_path):

    path = tmp_path / "searches.jsonl"

    Counting(path, {}).search("nothing here")

    assert not path.exists() or path.read_text() == ""
