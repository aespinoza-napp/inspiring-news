"""
Does the lake hold together? Every record claims a lineage - which run,
which article, which parent, which bytes - and the reader, the graph sync,
the writer and Trace all believe it. Nothing ever checked it.

This walks the lake and reports, without changing anything:

Errors, a record that cannot be believed:
- a record whose file name is not its own id, or that sits in another
  layer's folder, or whose id is not the one its run and article derive;
- a record pointing at a parent that does not exist, or that belongs to
  another run or article;
- a body whose hash is not the one its lineage states;
- a served record that says something else than the report it was derived
  from (verdict, confidence), or that is publishable when the rule says it
  is not, since those decide what the public reads.

Warnings, a gap in the record rather than a falsehood:
- a record the manifest never logged, or a write it logged whose record is
  gone (a record is overwritten by a re-run; it should not vanish);
- a run that stopped before the served layer without saying why is normal
  for a rejected or failed run, so it is counted, not flagged;
- no code revision on the lineage, so "which code produced this" has no
  answer for that record.

`python -m src.services.lake_integrity` prints it and exits 1 on any error.
Reads through the repository's public methods, so another backend is checked
the same way; opens every record, so it is for a person or a nightly check,
never for a request's hot path.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from dataclasses import dataclass, field

from src.models.fact_checker.fact_check import Verdict
from src.models.storage.lineage import DataLayer, build_record_id
from src.repositories.datalake_repository import content_hash

# What blocks publication (DataLakeRepository._is_publishable).
_WITHHELD = {Verdict.FALSE.value, Verdict.MISLEADING.value}

_PARENT_LAYER = {
    DataLayer.PROCESSED.value: DataLayer.RAW,
    DataLayer.EXPLOITATION.value: DataLayer.PROCESSED,
}

# Float noise between two serialisations of one figure.
_TOLERANCE = 1e-6


@dataclass
class Issue:

    severity: str  # "error" | "warning"

    kind: str

    layer: str | None

    record_id: str | None

    detail: str

    url: str | None = None

    def view(self) -> dict:

        return {
            "severity": self.severity,
            "kind": self.kind,
            "layer": self.layer,
            "recordId": self.record_id,
            "url": self.url,
            "detail": self.detail,
        }


@dataclass
class Report:

    records: Counter = field(default_factory=Counter)

    runs: int = 0

    runs_complete: int = 0

    manifest_entries: int = 0

    issues: list[Issue] = field(default_factory=list)

    def add(self, severity: str, kind: str, record: dict | None, detail: str, layer: str | None = None) -> None:

        lineage = (record or {}).get("lineage") or {}

        self.issues.append(Issue(
            severity=severity,
            kind=kind,
            layer=layer or lineage.get("layer"),
            record_id=(record or {}).get("record_id"),
            url=lineage.get("source_url"),
            detail=detail,
        ))

    @property
    def errors(self) -> list[Issue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    def view(self, limit: int = 200) -> dict:

        counts = Counter((issue.severity, issue.kind) for issue in self.issues)

        return {
            "ok": not self.errors,
            "records": dict(self.records),
            "runs": self.runs,
            "runsComplete": self.runs_complete,
            "manifestEntries": self.manifest_entries,
            "errors": len(self.errors),
            "warnings": len(self.issues) - len(self.errors),
            "byKind": [
                {"severity": severity, "kind": kind, "count": count}
                for (severity, kind), count in sorted(counts.items())
            ],
            # Errors first: a long list of warnings must not hide one.
            "issues": [
                issue.view()
                for issue in sorted(self.issues, key=lambda issue: issue.severity != "error")[:limit]
            ],
        }


def verify(lake) -> Report:

    report = Report()

    records = {layer.value: {record["record_id"]: record for record in lake.list(layer) if record.get("record_id")} for layer in DataLayer}

    for layer, found in records.items():
        report.records[layer] = len(found)

    manifest = lake.manifest()
    report.manifest_entries = len(manifest)

    logged = {(entry.get("layer"), entry.get("record_id")) for entry in manifest}

    for layer, found in records.items():
        for record in found.values():
            _check_record(report, layer, record, records, logged)

    for layer, record_id in sorted(logged, key=str):
        if layer in records and record_id not in records[layer]:
            report.add("warning", "logged_record_missing", None, f"The manifest logged {record_id} in {layer}, and it is gone.", layer=layer)

    _check_runs(report, records)

    return report


def _check_record(report: Report, layer: str, record: dict, records: dict, logged: set) -> None:

    lineage = record.get("lineage") or {}
    record_id = record["record_id"]

    if not lineage:
        report.add("error", "no_lineage", record, "The record carries no lineage.", layer=layer)
        return

    if lineage.get("layer") != layer:
        report.add("error", "wrong_layer", record, f"In {layer}, but its lineage says {lineage.get('layer')}.", layer=layer)

    expected = build_record_id(DataLayer(layer), lineage.get("article_id") or "", lineage.get("run_id") or "")

    if record_id != expected:
        report.add("error", "wrong_id", record, f"Its id is not the one its run and article derive ({expected}).", layer=layer)

    if (layer, record_id) not in logged:
        report.add("warning", "not_in_manifest", record, "The manifest never logged this record.", layer=layer)

    if not lineage.get("code_revision"):
        report.add("warning", "no_code_revision", record, "Which code produced this cannot be told.", layer=layer)

    _check_parent(report, layer, record, lineage, records)
    _check_body(report, layer, record, lineage)

    if layer == DataLayer.EXPLOITATION.value:
        _check_served(report, record, lineage, records)


def _check_parent(report: Report, layer: str, record: dict, lineage: dict, records: dict) -> None:

    parent_layer = _PARENT_LAYER.get(layer)

    if parent_layer is None:
        return

    parent_id = lineage.get("parent_record_id")

    if not parent_id:
        # Allowed by design: a parent write can fail and the next layer
        # still be written, "which simply loses its parent link".
        report.add("warning", "no_parent", record, f"No link to its {parent_layer.value} record.", layer=layer)
        return

    parent = records[parent_layer.value].get(parent_id)

    if parent is None:
        report.add("error", "parent_missing", record, f"Its parent {parent_id} is not in {parent_layer.value}.", layer=layer)
        return

    theirs = parent.get("lineage") or {}

    for name in ("run_id", "article_id"):
        if theirs.get(name) != lineage.get(name):
            report.add("error", "parent_mismatch", record, f"Its parent has another {name}.", layer=layer)

    if theirs.get("content_hash") != lineage.get("content_hash"):
        report.add("error", "hash_differs_from_parent", record, "Its body hash is not its parent's: the text changed between layers.", layer=layer)


def _check_body(report: Report, layer: str, record: dict, lineage: dict) -> None:

    article = record.get("article")

    # The served layer holds a summary, not the body: nothing to hash.
    if not isinstance(article, dict):
        return

    body = article.get("content") if layer == DataLayer.RAW.value else article.get("body")

    if body is None:
        return

    if content_hash(body) != lineage.get("content_hash"):
        report.add("error", "body_hash_mismatch", record, "The stored text does not hash to what its lineage states.", layer=layer)


def _check_served(report: Report, record: dict, lineage: dict, records: dict) -> None:

    parent = records[DataLayer.PROCESSED.value].get(lineage.get("parent_record_id"))

    fact_check = (parent or {}).get("fact_check") or {}

    served_verdict = record.get("verdict")

    if fact_check:

        if fact_check.get("overall_verdict") != served_verdict:
            report.add("error", "verdict_differs_from_report", record, f"Serves {served_verdict}; its report says {fact_check.get('overall_verdict')}.")

        confidence = fact_check.get("overall_confidence")

        if isinstance(confidence, (int, float)) and abs(confidence - (record.get("verdict_confidence") or 0.0)) > _TOLERANCE:
            report.add("error", "confidence_differs_from_report", record, "Its confidence is not its report's.")

    if record.get("publishable"):

        if not record.get("validation_passed"):
            report.add("error", "publishable_unvalidated", record, "Publishable, though it did not pass admission.")

        if served_verdict in _WITHHELD:
            report.add("error", "publishable_with_blocking_verdict", record, f"Publishable with the verdict {served_verdict}.")


def _check_runs(report: Report, records: dict) -> None:

    runs: dict[str, set[str]] = {}

    for layer, found in records.items():
        for record in found.values():
            run_id = (record.get("lineage") or {}).get("run_id")
            if run_id:
                runs.setdefault(run_id, set()).add(layer)

    report.runs = len(runs)
    report.runs_complete = sum(1 for layers in runs.values() if len(layers) == len(DataLayer))


def main() -> int:

    from src.container import get_datalake_repository

    report = verify(get_datalake_repository())

    print(json.dumps(report.view(), indent=2, ensure_ascii=False))

    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main())
