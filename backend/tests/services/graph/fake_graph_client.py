from src.database.neo4j_client import GraphUnavailable, ReadResult


class RecordingGraphClient:
    """
    Stands in for GraphClient: records every write transaction as the
    list of (query, params) it was given, and answers reads from a queue.
    Its signatures are held to GraphClient's by
    test_graph_writer.py::test_the_fake_client_matches_the_real_one.
    """

    def __init__(self, reads: list[ReadResult] | None = None, down: bool = False):
        self.writes: list[list[tuple[str, dict]]] = []
        self.reads_made: list[dict] = []
        self._reads = list(reads or [])
        self.down = down

    def write(self, statements: list[tuple[str, dict]]) -> None:
        if self.down:
            raise GraphUnavailable("Neo4j is down (fake)")
        self.writes.append(list(statements))

    def read(
        self,
        query: str,
        params: dict | None = None,
        timeout: float | None = None,
        max_rows: int | None = None,
    ) -> ReadResult:
        if self.down:
            raise GraphUnavailable("Neo4j is down (fake)")
        self.reads_made.append(
            {"query": query, "params": params, "timeout": timeout, "max_rows": max_rows}
        )
        return self._reads.pop(0) if self._reads else ReadResult([], [], False, [])

    def verify_connection(self):
        if self.down:
            raise GraphUnavailable("Neo4j is down (fake)")

    def close(self):
        pass

    # ------------------------------------------------------------------

    def statements(self) -> list[tuple[str, dict]]:
        return [statement for tx in self.writes for statement in tx]

    def params_of(self, query: str) -> list[dict]:
        return [params for q, params in self.statements() if q == query]
