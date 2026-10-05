"""
The labelled sets the harness runs over, loaded into one row shape.

Two formats, one loader, because they are one format on purpose: the
labeller writes every custom fact with x-fact's ten keys first, in
x-fact's order (`labeller/test_app.py` pins it), and adds its own after
them. What tells them apart is the custom set's own `id`; x-fact has no
id, so one is derived here.

Three inputs are accepted:

- a JSONL file (`xfact_en_es_pilot.jsonl`, or the joined
  `custom_en_es.jsonl` once it exists);
- a directory of one-fact JSON files (`data/evaluation/manual/`), so the
  custom set can be run before it is joined - the harness should not
  have to wait for the last day of labelling to be exercised on it.

Nothing here is written. The dataset's sha256 is part of a run's key,
so editing a label after a run starts a new run rather than mixing two
versions of the gold set in one results file.

docs/decisions/evaluation.md §Record format, §Run layout.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from src.config.topics import GROUP_OF as _GROUP_OF, TOPIC_GROUPS as _TOPIC_GROUPS
from src.models.fact_checker.fact_check import Verdict

XFACT = "xfact"
CUSTOM = "custom"

# The five groups, as the labeller balances them. The backend's copy
# lives in src/config/topics.py (ingestion selects sources by them too);
# tests/evaluation/test_harness_dataset.py holds it equal to
# labeller/app.py's, which imports nothing from backend/.
TOPIC_GROUPS = _TOPIC_GROUPS

GROUP_OF = _GROUP_OF

_VERDICTS = {verdict.value for verdict in Verdict}


class DatasetError(ValueError):
    """The dataset cannot be scored as it stands; the message says where."""


@dataclass(frozen=True)
class DatasetRow:
    """
    One labelled claim. Field names are Python's; the record writes them
    back under the dataset's own keys (`claimDate`, `labelRaw`...).
    """

    id: str

    # Which set the row belongs to, `custom` or `xfact` - not the file
    # name. It decides what the harness passes the pipeline (a context
    # for custom rows, none for x-fact) and which leak can happen (a
    # verdict leak is an x-fact property: its `site` published the
    # verdict).
    dataset: str

    language: str

    site: str | None

    claim: str

    # None for x-fact's "none". Rule 3 (no evidence newer than the claim)
    # cannot be checked without it.
    claim_date: str | None

    label: str

    label_raw: str | None

    reference_links: tuple[str, ...]

    # Custom set only.
    article_url: str | None = None

    topic: str | None = None

    claim_type: str | None = None

    source_tier: str | None = None

    @property
    def topic_group(self) -> str | None:

        return GROUP_OF.get(self.topic) if self.topic else None


@dataclass(frozen=True)
class Dataset:

    path: Path

    # The file's stem, or the directory's name. Names the run and report
    # directories, so two datasets cannot share them.
    stem: str

    sha256: str

    rows: tuple[DatasetRow, ...]

    @property
    def kinds(self) -> list[str]:

        return sorted({row.dataset for row in self.rows})


def xfact_id(language: str, site: str, claim: str) -> str:
    """
    x-fact has no id. Its rows are told apart by what they say and who
    checked them: the first 12 hex digits of sha1 over language, site and
    claim, one per line. Unique over all 64 pilot rows; the loader
    refuses a duplicate rather than let two claims share a record.
    """

    digest = hashlib.sha1(
        "\n".join([language, site, claim]).encode("utf-8")
    ).hexdigest()

    return f"xf-{digest[:12]}"


def load_dataset(path: str | Path) -> Dataset:

    path = Path(path)

    if path.is_dir():
        raw_rows, sha256 = _read_directory(path)
        stem = path.name
    elif path.is_file():
        raw_rows, sha256 = _read_jsonl(path)
        stem = path.stem
    else:
        raise DatasetError(f"{path}: no such file or directory")

    rows = tuple(parse_row(raw, where) for where, raw in raw_rows)

    _refuse_duplicates(rows)

    if not rows:
        raise DatasetError(f"{path}: no rows")

    return Dataset(path=path, stem=stem, sha256=sha256, rows=rows)


def _read_jsonl(path: Path) -> tuple[list[tuple[str, dict]], str]:

    data = path.read_bytes()

    rows = []

    for number, line in enumerate(data.decode("utf-8").splitlines(), start=1):

        if not line.strip():
            continue

        try:
            rows.append((f"{path.name}:{number}", json.loads(line)))
        except json.JSONDecodeError as exc:
            raise DatasetError(f"{path.name}:{number}: not JSON ({exc})") from exc

    return rows, hashlib.sha256(lf(data)).hexdigest()


def lf(data: bytes) -> bytes:
    """
    The bytes a hash is taken over: CRLF read as LF. Git for Windows
    checks text out as CRLF (core.autocrlf=true here), so the same
    committed set hashed differently on Windows than on Linux or the VM -
    a different run key, and two runs of one set refused as two sets.
    """

    return data.replace(b"\r\n", b"\n")


def _read_directory(path: Path) -> tuple[list[tuple[str, dict]], str]:
    """
    Every `*.json` in the directory, by name. The hash covers names and
    bytes, so adding, removing or editing a fact all change it.
    """

    digest = hashlib.sha256()

    rows = []

    for file in sorted(path.glob("*.json")):

        data = file.read_bytes()

        digest.update(file.name.encode("utf-8") + b"\0" + lf(data) + b"\0")

        try:
            rows.append((file.name, json.loads(data.decode("utf-8"))))
        except json.JSONDecodeError as exc:
            raise DatasetError(f"{file.name}: not JSON ({exc})") from exc

    return rows, digest.hexdigest()


def parse_row(raw: dict, where: str = "row") -> DatasetRow:
    """One row of either format; `where` names it in an error."""

    if not isinstance(raw, dict):
        raise DatasetError(f"{where}: a row must be a JSON object")

    for key in ("language", "claim", "label"):
        if not raw.get(key):
            raise DatasetError(f"{where}: missing `{key}`")

    label = str(raw["label"]).upper()

    if label not in _VERDICTS:
        raise DatasetError(
            f"{where}: label {raw['label']!r} is not a Verdict ({sorted(_VERDICTS)})"
        )

    language = str(raw["language"]).lower()
    site = raw.get("site") or None
    claim = str(raw["claim"])

    links = raw.get("referenceEvidenceLinks") or []

    if not isinstance(links, list):
        raise DatasetError(f"{where}: referenceEvidenceLinks must be a list")

    is_custom = bool(raw.get("id"))

    return DatasetRow(
        id=str(raw["id"]) if is_custom else xfact_id(language, site or "", claim),
        dataset=CUSTOM if is_custom else XFACT,
        language=language,
        site=site,
        claim=claim,
        claim_date=_claim_date(raw.get("claimDate")),
        label=label,
        label_raw=raw.get("labelRaw"),
        reference_links=tuple(str(link) for link in links if link),
        article_url=raw.get("articleUrl") or None,
        topic=raw.get("topic") or None,
        claim_type=raw.get("claimType") or None,
        source_tier=raw.get("sourceTier") or None,
    )


def _claim_date(value) -> str | None:
    """x-fact writes "none" for a claim with no date; the record says null."""

    if value is None:
        return None

    text = str(value).strip()

    if not text or text.lower() == "none":
        return None

    return text


def _refuse_duplicates(rows: tuple[DatasetRow, ...]) -> None:

    seen: dict[str, int] = {}

    duplicates = []

    for row in rows:
        seen[row.id] = seen.get(row.id, 0) + 1
        if seen[row.id] == 2:
            duplicates.append(row.id)

    if duplicates:
        raise DatasetError(
            "duplicate ids - two rows would share one record: "
            + ", ".join(sorted(duplicates))
        )
