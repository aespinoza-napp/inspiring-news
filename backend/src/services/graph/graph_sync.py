"""
Backfill: bring the graph up to date with what already exists outside it.

    cd backend && uv run python -m src.services.graph.graph_sync

or POST /graph/sync (the "Sync" button on the frontend's /graph page).

Three inputs, in this order:

1. The configured sources (data/sources/*.yaml) - so every one of ours is
   a rated Source node before any article points at it.
2. The hand-labelled facts (data/evaluation/manual/factNNN.json, written
   by labeller/) - article, claim, verdict, topic and reference links,
   tagged method 'manual'.
3. The lake's processed records that carry a fact-check report - every
   analysis run before the graph write existed, and any whose live graph
   write failed. Each is written exactly as AnalysisService would have.

Every write is a MERGE keyed on the schema's keys, and a fact or an
article replaces what it wrote before, so running this twice changes
nothing the second time. A file that fails to parse or write is reported
and skipped; it does not stop the rest.
"""

import json
from logging import getLogger
from pathlib import Path

from src.models.storage.lineage import DataLayer
from src.models.storage.records import ProcessedRecord
from src.repositories.datalake_repository import DataLakeRepository
from src.services.graph.graph_writer import GraphWriter

logger = getLogger(__name__)

# Relative to backend/, like SourceRepository's data/sources: the working
# directory is backend/ both locally and in the Docker image.
MANUAL_FACTS_PATH = Path("data/evaluation/manual")


class GraphSync:

    def __init__(
        self,
        writer: GraphWriter,
        lake: DataLakeRepository | None = None,
        facts_path: Path | None = None,
    ):
        self.writer = writer
        self.lake = lake
        self.facts_path = Path(facts_path) if facts_path else MANUAL_FACTS_PATH

    def run(self) -> dict:

        self.writer.ensure_schema()

        errors: list[dict] = []

        sources = self.writer.write_sources()

        facts = 0

        for path in sorted(self.facts_path.glob("fact*.json")):
            try:
                fact = json.loads(path.read_text(encoding="utf-8"))
                self.writer.write_labelled_fact(fact)
                facts += 1
            except Exception as exc:
                logger.warning("Could not sync %s into the graph", path, exc_info=True)
                errors.append({"item": path.name, "error": str(exc)})

        articles = 0

        for record in self._processed_records(errors):
            try:
                self.writer.write_analysis(
                    record.article,
                    record.fact_check,
                    run_id=record.lineage.run_id,
                )
                articles += 1
            except Exception as exc:
                logger.warning(
                    "Could not sync %s into the graph", record.article.url, exc_info=True
                )
                errors.append({"item": record.article.url, "error": str(exc)})

        return {
            "sources": sources,
            "facts": facts,
            "articles": articles,
            "errors": errors,
        }

    def _processed_records(self, errors: list[dict]) -> list[ProcessedRecord]:

        if self.lake is None:
            return []

        try:
            raw_records = self.lake.list(DataLayer.PROCESSED)
        except Exception as exc:
            errors.append({"item": "lake", "error": str(exc)})
            return []

        latest: dict[str, ProcessedRecord] = {}

        for data in raw_records:

            try:
                record = ProcessedRecord.model_validate(data)
            except Exception as exc:
                errors.append({"item": data.get("record_id", "?"), "error": str(exc)})
                continue

            # Enriched but never verified (a run that died mid-check): no
            # report to take claims and verdicts from.
            if record.fact_check is None:
                continue

            # The newest run per URL, which is what the live write would
            # have left in the graph last.
            url = record.article.url
            current = latest.get(url)

            if current is None or record.fact_check.checked_at > current.fact_check.checked_at:
                latest[url] = record

        return list(latest.values())


if __name__ == "__main__":

    import logging

    logging.basicConfig(level=logging.INFO)

    from src.container import get_datalake_repository, get_graph_writer

    report = GraphSync(get_graph_writer(), lake=get_datalake_repository()).run()

    print(json.dumps(report, indent=2))
