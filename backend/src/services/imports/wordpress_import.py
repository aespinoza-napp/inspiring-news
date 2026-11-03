"""
A WordPress export brought into the lake and the graph as it is: every post
enriched, every post through admission - recorded, deciding nothing - and
none fact-checked. The point is a fixed set to compare on: everyone works on
the same articles, word for word, and a verified run later on the same file
is judged against the same text (`verify=True`, the same code path).

    POST /imports/wordpress?statuses=publish   (the export's bytes)
    GET  /imports/wordpress                    (progress, then each post's result)
    GET  /imports/wordpress/snapshot           (the posts as read, one JSON a line)

`scripts/import_wordpress.py` sends a file and follows it.

What an unverified import leaves behind, per post:

- the lake's three layers, with every threshold in the lineage and the
  file, the post id and its status in the raw record's metadata; its
  exploitation record is **never publishable**, so nothing
  imported shows up on the reader as an article this newsroom checked;
- the graph's Article node with `fact_checked: false`,
  `fact_check_skipped: "import"`, no verdict, and `admitted`, `topic_ok`,
  `positive_ok`, `duplicate`, `impact_score` and `skipped_reason` saying
  whether it would have passed the filters - a rejected post is in the
  graph too, with `admitted: false`;
- **nothing in the vector store**, which is the corpus the fact-checker
  searches: remembered now, a post would be found as evidence for itself
  when it is verified later. So a duplicate *within* the file is told by
  the snapshot (`duplicate_of`, same text or title), not by admission.

Runs inside the backend process, not beside it: the vector store is an
on-disk Qdrant that the running app holds locked.
"""

from __future__ import annotations

import json
import threading
import time
from collections import Counter
from datetime import datetime, timezone
from logging import getLogger
from pathlib import Path
from uuid import uuid4

from src.config.thresholds import PipelineThresholds
from src.models.core.news import News
from src.services.imports.wordpress import Export, Post, parse

logger = getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def source_id(export: Export) -> str:
    """What each imported article says it came from: the file, by its site."""

    host = export.base_url.split("://")[-1].strip("/") or "unknown"

    return f"wordpress:{host}"


def to_news(post: Post, source: str) -> News:

    return News(
        source_id=source,
        url=post.url,
        title=post.title or None,
        author=post.author,
        published_at=datetime.fromisoformat(post.published_at) if post.published_at else None,
        language=post.language,
        content=post.text,
        metadata={
            "imported_from": source,
            "wp_id": post.wp_id,
            "status": post.status,
            "categories": post.categories,
            "tags": post.tags,
            "sources": post.sources,
            "content_hash": post.content_hash,
        },
    )


def outcome(post: Post, result: dict) -> dict:
    """One post's line: what admission said, what was stored, what the graph got."""

    if "error" in result:
        return {"wpId": post.wp_id, "url": post.url, "title": post.title, "error": result["error"]}

    validity = result.get("validity") or {}
    storage = result.get("storage") or {}
    fact_check = result.get("factCheck") or {}

    return {
        "wpId": post.wp_id,
        "url": post.url,
        "title": post.title,
        "status": post.status,
        "publishedAt": post.published_at,
        "categories": post.categories,
        "contentHash": post.content_hash,
        "duplicateInFile": post.duplicate_of,
        "passedFilters": bool(validity.get("isValid")),
        "rejectedFor": validity.get("reasons") or [],
        "topicOk": validity.get("hasTopic"),
        "duplicate": validity.get("isDuplicate"),
        "impactScore": validity.get("impactScore"),
        "topics": [topic.get("topic") for topic in (result.get("topics") or [])][:3],
        "claims": fact_check.get("claimsTotal", 0),
        "factChecked": fact_check.get("claimsChecked", 0) > 0,
        "runId": storage.get("runId"),
        "stored": bool(storage.get("persisted")),
    }


class WordPressImport:

    def __init__(self, analysis_service, directory: Path):
        self.analysis_service = analysis_service
        self.directory = Path(directory)

        self._lock = threading.Lock()
        self._state: dict = {"running": False, "importId": None}

    # ------------------------------------------------------------------
    # Background run, polled: a post is a few seconds of enrichment
    # ------------------------------------------------------------------

    def state(self, with_results: bool = True) -> dict:

        with self._lock:
            state = dict(self._state)

        if not with_results:
            state.pop("results", None)

        return state

    def snapshot_path(self) -> Path | None:

        with self._lock:
            import_id = self._state.get("importId")

        return self.directory / import_id / "snapshot.jsonl" if import_id else None

    def start(
        self,
        data: bytes,
        statuses: tuple[str, ...] = ("publish",),
        verify: bool = False,
        limit: int | None = None,
    ) -> dict:
        """
        Read the export now, so a bad file is refused at once; run it in the
        background. Raises NotAnExport for a file this cannot read, and
        RuntimeError while another import runs.
        """

        export = parse(data, statuses)
        posts = export.posts[:limit] if limit else export.posts

        with self._lock:

            if self._state.get("running"):
                raise RuntimeError("An import is already running.")

            import_id = uuid4().hex[:12]
            folder = self.directory / import_id
            folder.mkdir(parents=True, exist_ok=True)

            # The snapshot first: it is the "same data" everything after this
            # is compared on, and it holds whether or not the run finishes.
            with (folder / "snapshot.jsonl").open("w", encoding="utf-8") as handle:
                for post in posts:
                    handle.write(json.dumps(post.row(), ensure_ascii=False) + "\n")

            self._state = {
                "running": True,
                "importId": import_id,
                "site": export.site,
                "sourceId": source_id(export),
                "statuses": list(statuses),
                "verify": verify,
                "postsInFile": export.items,
                "total": len(posts),
                "done": 0,
                "startedAt": _now(),
                "finishedAt": None,
                "error": None,
                "summary": None,
                "results": [],
            }

        threading.Thread(
            target=self._run,
            args=(export, posts, verify, folder),
            name="wordpress-import",
            daemon=True,
        ).start()

        return self.state(with_results=False)

    def _run(self, export: Export, posts: list[Post], verify: bool, folder: Path) -> None:

        source = source_id(export)
        thresholds = PipelineThresholds()

        try:
            with (folder / "results.jsonl").open("w", encoding="utf-8") as handle:

                for post in posts:

                    started = time.perf_counter()

                    try:
                        result = self.analysis_service.analyze_news(
                            to_news(post, source),
                            thresholds=thresholds,
                            verify=verify,
                            # Only a verified run may join the corpus a later
                            # check searches; an unverified one never does.
                            remember=verify,
                            extractor="wordpress_export",
                        )
                    except Exception as exc:
                        logger.warning("Import of %s failed", post.url, exc_info=True)
                        result = {"url": post.url, "error": str(exc)}

                    line = {**outcome(post, result), "seconds": round(time.perf_counter() - started, 2)}

                    handle.write(json.dumps(line, ensure_ascii=False) + "\n")
                    handle.flush()

                    with self._lock:
                        self._state["results"].append(line)
                        self._state["done"] += 1

        except Exception as exc:
            logger.exception("WordPress import failed")
            with self._lock:
                self._state["error"] = str(exc)

        finally:
            with self._lock:
                self._state["summary"] = summarise(self._state["results"])
                self._state["finishedAt"] = _now()
                self._state["running"] = False
                summary = dict(self._state)
                summary.pop("results")

            try:
                (folder / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
            except OSError:
                logger.warning("Could not write the import summary", exc_info=True)


def summarise(results: list[dict]) -> dict:

    ok = [line for line in results if "error" not in line]
    reasons = Counter(reason for line in ok for reason in line.get("rejectedFor") or [])

    return {
        "imported": len(ok),
        "failed": len(results) - len(ok),
        "passedFilters": sum(1 for line in ok if line.get("passedFilters")),
        "rejected": sum(1 for line in ok if not line.get("passedFilters")),
        "rejectedFor": dict(reasons.most_common()),
        "duplicatesInFile": sum(1 for line in ok if line.get("duplicateInFile")),
        "claims": sum(line.get("claims") or 0 for line in ok),
        "stored": sum(1 for line in ok if line.get("stored")),
    }
