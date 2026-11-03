"""
One article's journey through every stage, in one answer: which rounds
listed it and who chose it, which jobs analysed it, what each run wrote to
the lake and with which code and models, whether it reached the reader,
and which drafts and stories were written from it.

Each stage already keeps its own record - rounds in `lake/stats/selection/`,
jobs in the journal, writes in the lake's manifest, drafts in their store -
but they were only ever read one stage at a time, so following one article
meant knowing which id to paste into which page. They share one key: the
article's host and path (`reader_id`), the same comparison ingestion, the
job store and the reader use to decide two URLs are one article. That is
the key here too.

Cheap on purpose: the lake's runs are found from the manifest (one line per
write, with its `source_url`), and only the matched records are opened -
never a scan of the processed layer, which carries every embedding.
"""

from __future__ import annotations

import re
from logging import getLogger

from src.models.storage.lineage import DataLayer
from src.services.reader.views import reader_id

logger = getLogger(__name__)

_JOB_ID = re.compile(r"[0-9a-f]{32}")
_SHORT_ID = re.compile(r"[0-9a-f]{16}")

# How many rounds are read back, newest first. A round is one small JSON
# file; the selection step makes a few a day.
ROUNDS_SEARCHED = 200

# Jobs from the journal, newest first, per article. An article analysed more
# often than this is shown with its latest runs.
MAX_JOBS = 50


class NotTraceable(ValueError):
    """`q` names nothing this service can follow back to one article."""


def resolve(q: str, *, jobs, drafts, reader) -> dict:
    """
    What the person pasted, turned into the article's key. Anything a page
    shows can be pasted: the URL, a job id (Live), a draft or story id
    (Drafts, a published story) or a reader id (/reader/<id>).
    """

    q = (q or "").strip()

    if q.startswith(("http://", "https://")):
        return {"key": reader_id(q), "url": q, "from": "url"}

    if _JOB_ID.fullmatch(q):
        job = jobs.get(q)
        if job is None:
            raise NotTraceable("No job with this id, in memory or in the journal.")
        if job.kind != "article":
            raise NotTraceable("This job checked a single claim, not an article: it has no journey to follow.")
        return {"key": reader_id(job.url), "url": job.url, "from": "job"}

    if _SHORT_ID.fullmatch(q):

        draft = drafts.get(q) if drafts is not None else None
        if draft is not None:
            return {"key": draft.source_article_id, "url": None, "from": "draft"}

        # A reader id is already the key; whether anything is stored under
        # it is for the trace to say.
        return {"key": q, "url": None, "from": "reader"}

    raise NotTraceable("Paste an article URL, a job id (32 hex characters) or a draft, story or reader id (16).")


def trace(q: str, *, lake, jobs, rounds, drafts, reader) -> dict:

    target = resolve(q, jobs=jobs, drafts=drafts, reader=reader)
    key = target["key"]

    runs, url, title = _runs(lake, key)

    url = target["url"] or url

    found_jobs = _jobs(jobs, key)

    if url is None and found_jobs:
        url = found_jobs[0]["url"]

    discovery = _discovery(rounds, key)

    if url is None and discovery:
        url = discovery[0]["url"]

    if title is None and discovery:
        title = discovery[0].get("title")

    published = _reader(reader, key)

    return {
        "key": key,
        "resolvedFrom": target["from"],
        "url": url,
        "title": (published or {}).get("title") or title,
        "discovery": discovery,
        "jobs": found_jobs,
        "runs": runs,
        "reader": published,
        "drafts": _drafts(drafts, key),
    }


# ----------------------------------------------------------------------
# Stages
# ----------------------------------------------------------------------


def _same(url: str | None, key: str) -> bool:

    if not url or not isinstance(url, str):
        return False

    try:
        return reader_id(url) == key
    except Exception:
        return False


def _discovery(rounds, key: str) -> list[dict]:
    """Every round that listed the article, newest first: its place, the AI's view, who sent it on."""

    if rounds is None:
        return []

    found = []

    for round_ in rounds.list(ROUNDS_SEARCHED):

        candidates = [*(round_.get("candidates") or []), *(round_.get("reserve") or [])]

        listed = len(round_.get("candidates") or [])

        for position, candidate in enumerate(candidates):

            if not _same(candidate.get("url"), key):
                continue

            ai = round_.get("aiSelection") or {}
            picks = {pick.get("url"): pick for pick in ai.get("picks") or []}
            scored = {item.get("url"): item for item in ai.get("scored") or []}
            ai_row = picks.get(candidate["url"]) or scored.get(candidate["url"])

            queued = round_.get("queued") or {}
            job = next(
                (entry for entry in queued.get("jobs") or [] if entry.get("url") == candidate["url"]),
                None,
            )

            found.append({
                "roundId": round_.get("id"),
                "startedAt": round_.get("startedAt"),
                "edition": round_.get("edition") or "positive",
                "lens": round_.get("lens"),
                "groups": round_.get("groups"),
                "url": candidate.get("url"),
                "title": candidate.get("title"),
                "source": candidate.get("sourceName") or candidate.get("source"),
                "place": position + 1,
                "shown": position < listed,
                "rank": candidate.get("rank"),
                "sameStoryAs": candidate.get("sameStoryAs"),
                "ai": {
                    "picked": candidate["url"] in picks,
                    "score": ai_row.get("score"),
                    "reason": ai_row.get("reason"),
                    "model": ai.get("model"),
                } if ai_row else None,
                "queued": job is not None,
                "queuedAt": queued.get("at") if job is not None else None,
                "selectedBy": queued.get("selectedBy") if job is not None else None,
                "jobId": (job or {}).get("jobId"),
                "queueError": (job or {}).get("error"),
            })

            break

    return found


def _jobs(jobs, key: str) -> list[dict]:

    if jobs is None:
        return []

    return [
        {
            "jobId": job.job_id,
            "url": job.url,
            "status": job.status,
            "createdAt": job.created_at,
            "updatedAt": job.updated_at,
            "error": job.error,
            "eventCount": len(job.events),
        }
        for job in jobs.find(lambda url, kind: kind == "article" and _same(url, key), MAX_JOBS)
    ]


def _runs(lake, key: str) -> tuple[list[dict], str | None, str | None]:
    """
    Each analysis run the lake holds for the article, newest first: the
    record it wrote per layer, from which parent, when, and with what code,
    models and overrides - then what it decided.
    """

    if lake is None:
        return [], None, None

    try:
        entries = [entry for entry in lake.manifest() if _same(entry.get("source_url"), key)]
    except Exception:
        logger.warning("Could not read the lake's manifest for a trace", exc_info=True)
        return [], None, None

    by_run: dict[str, dict] = {}

    for entry in entries:

        run_id = entry.get("run_id") or "?"

        run = by_run.setdefault(run_id, {
            "runId": run_id,
            "articleId": entry.get("article_id"),
            "url": entry.get("source_url"),
            "contentHash": entry.get("content_hash"),
            "codeRevision": entry.get("code_revision"),
            "startedAt": entry.get("at"),
            "layers": {},
            "writes": [],
        })

        run["writes"].append({
            "at": entry.get("at"),
            "layer": entry.get("layer"),
            "recordId": entry.get("record_id"),
            "parentLayer": entry.get("parent_layer"),
            "parentRecordId": entry.get("parent_record_id"),
        })

        # The last write per layer is the record as it stands: processed is
        # written twice in a run that reached verification, same id.
        run["layers"][entry.get("layer")] = entry.get("record_id")

    url = None
    title = None

    runs = sorted(by_run.values(), key=lambda run: str(run["startedAt"] or ""), reverse=True)

    for run in runs:

        raw = _get(lake, DataLayer.RAW, run["layers"].get("raw"))
        served = _get(lake, DataLayer.EXPLOITATION, run["layers"].get("exploitation"))

        lineage = (served or raw or {}).get("lineage") or {}

        run["pipelineVersion"] = lineage.get("pipeline_version")
        run["components"] = lineage.get("components") or {}
        run["thresholdOverrides"] = lineage.get("threshold_overrides") or {}
        # Every value the run used; empty on records from before 2026-11-03.
        run["thresholds"] = lineage.get("thresholds") or {}

        article = (raw or {}).get("article") or {}

        run["fetch"] = {
            "extractor": raw.get("extractor"),
            "fetchedAt": raw.get("fetched_at"),
            "contentLength": raw.get("content_length"),
            "title": article.get("title"),
            "language": article.get("language"),
        } if raw else None

        run["outcome"] = {
            "publishable": served.get("publishable"),
            "validationPassed": served.get("validation_passed"),
            "rejectionReasons": served.get("rejection_reasons") or [],
            "isDuplicate": served.get("is_duplicate"),
            "verdict": served.get("verdict"),
            "verdictConfidence": served.get("verdict_confidence"),
            "claimsTotal": served.get("claims_total"),
            "claimsChecked": served.get("claims_checked"),
            "primaryTopic": served.get("primary_topic"),
            "impactScore": served.get("impact_score"),
            "citedEvidence": len(served.get("cited_evidence_urls") or []),
        } if served else None

        # A run that stopped before verification wrote no exploitation
        # record: it is the stage that tells "rejected" from "cut off".
        run["reached"] = (
            "exploitation" if served else
            "processed" if run["layers"].get("processed") else
            "raw" if raw else
            "nothing readable"
        )

        url = url or run["url"]
        title = title or (served or {}).get("title") or article.get("title")

    return runs, url, title


def _get(lake, layer: DataLayer, record_id: str | None) -> dict | None:

    if not record_id:
        return None

    try:
        return lake.get(layer, record_id)
    except Exception:
        return None


def _reader(reader, key: str) -> dict | None:
    """The reader's own view, said briefly: published or not, under which verdict."""

    if reader is None:
        return None

    try:
        view = reader.article(key)
    except Exception:
        logger.warning("Could not read the reader index for a trace", exc_info=True)
        return None

    if view is None:
        return {"published": False, "id": key}

    return {
        "published": True,
        "id": key,
        "title": view.get("headline"),
        "verdict": view.get("verdict"),
        "checkedAt": view.get("checkedAt"),
    }


def _drafts(drafts, key: str) -> list[dict]:

    if drafts is None:
        return []

    return [
        {
            "id": draft.id,
            "title": draft.content.title,
            "status": draft.status,
            "busy": draft.busy,
            "edition": draft.edition,
            "language": draft.language,
            "createdAt": draft.created_at,
            "updatedAt": draft.updated_at,
            "revisions": len(draft.revisions),
            "published": [record.model_dump(mode="json") for record in draft.published],
            # The story's id is the draft's (services/publishing/story.py).
            "storyId": draft.id if draft.status == "published" else None,
        }
        for draft in drafts.list()
        if draft.source_article_id == key
    ]
