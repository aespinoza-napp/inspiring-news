import logging
from typing import Any, NamedTuple

from neo4j import READ_ACCESS, GraphDatabase, unit_of_work
from neo4j.exceptions import AuthError, ServiceUnavailable, SessionExpired

# The driver logs every server notification at WARNING on this logger,
# whatever the driver config says - a console query naming a property
# nobody has written yet put a full diagnostic record in the backend log.
# The notices go back to the caller instead (ReadResult.notices).
logging.getLogger("neo4j.notifications").setLevel(logging.ERROR)


class GraphUnavailable(Exception):
    """Neo4j could not be reached, or refused our credentials."""


class ReadResult(NamedTuple):

    columns: list[str]

    rows: list[dict[str, Any]]

    truncated: bool

    # What the server said about the query - an unknown label or property,
    # a deprecated form. Returned rather than logged: to the person who
    # typed the query in the console it is the most useful line on the
    # page; in the backend's log it was noise on every read.
    notices: list[str]


class GraphClient:
    """
    The one place this process talks Bolt. Everything above it passes
    Cypher and parameters; nothing above it imports `neo4j`.

    Timeouts are short on purpose. The graph write is a side effect of an
    analysis (see AnalysisService._store_graph), and the driver's defaults
    - a 30s connection timeout, then 30s of transaction retries - meant a
    stopped Neo4j container added a minute to every run before its
    `graph_failed` event.
    """

    CONNECTION_TIMEOUT_SECONDS = 3.0

    MAX_RETRY_SECONDS = 2.0

    def __init__(self, uri: str, user: str, password: str, driver=None):

        # Constructing the driver does not connect: the first session
        # does. So building a GraphClient with Neo4j down is fine, and the
        # container can build one lazily like everything else.
        self.driver = driver or GraphDatabase.driver(
            uri,
            auth=(user, password),
            connection_timeout=self.CONNECTION_TIMEOUT_SECONDS,
            connection_acquisition_timeout=self.CONNECTION_TIMEOUT_SECONDS,
            max_transaction_retry_time=self.MAX_RETRY_SECONDS,
            warn_notification_severity="OFF",
        )

    def close(self):
        self.driver.close()

    def verify_connection(self):
        try:
            return self.driver.verify_connectivity()
        except (ServiceUnavailable, SessionExpired, AuthError) as exc:
            raise GraphUnavailable(str(exc)) from exc

    def write(self, statements: list[tuple[str, dict]]) -> None:
        """
        Every statement in one transaction: an article lands in the graph
        whole or not at all. A half-written article - its claims without
        their verdicts - reads as "checked, no verdict", which is a
        different and wrong answer.
        """

        def work(tx):
            for query, params in statements:
                tx.run(query, params).consume()

        try:
            with self.driver.session() as session:
                session.execute_write(work)
        except (ServiceUnavailable, SessionExpired, AuthError) as exc:
            raise GraphUnavailable(str(exc)) from exc

    def read(
        self,
        query: str,
        params: dict | None = None,
        timeout: float | None = None,
        max_rows: int | None = None,
    ) -> ReadResult:
        """
        Runs in a READ transaction, which the
        server enforces: a CREATE, MERGE or SET sent here is refused by
        Neo4j itself, not by a keyword filter we could get wrong. That is
        what makes POST /graph/query safe to expose to the query console.
        """

        @unit_of_work(timeout=timeout)
        def work(tx):
            result = tx.run(query, params or {})
            columns = list(result.keys())
            rows = []
            truncated = False

            for record in result:
                if max_rows is not None and len(rows) >= max_rows:
                    truncated = True
                    break
                rows.append(dict(record.items()))

            summary = result.consume()

            notices = [
                status.status_description
                for status in summary.gql_status_objects
                if status.is_notification
            ]

            return ReadResult(columns, rows, truncated, notices)

        try:
            with self.driver.session(default_access_mode=READ_ACCESS) as session:
                return session.execute_read(work)
        except (ServiceUnavailable, SessionExpired, AuthError) as exc:
            raise GraphUnavailable(str(exc)) from exc
