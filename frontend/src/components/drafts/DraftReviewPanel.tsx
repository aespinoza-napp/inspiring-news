"use client";

import { Fragment, useMemo, useState } from "react";
import { ArticleBody } from "@/components/drafts/ArticleBody";
import { ScoreBar } from "@/components/ScoreBar";
import { ArticleDraft, DraftContent, DraftStageProps, RevisionReason, draftsApi } from "@/lib/drafts";
import { CorrectionMetric } from "@/lib/types";
import styles from "./DraftReviewPanel.module.css";

/**
 * The corrector's review of the draft and its proposed corrections
 * (docs/decisions/writing.md, "Review"; backend src/api/review_routes.py).
 *
 * Review starts the review in the background and hands the busy draft to
 * the page, which polls until it is done. The review is of one text: an
 * edit, an accepted correction or a rewrite clears it, and the panel says
 * so rather than showing scores for text that is no longer there.
 */

// Title and subtitle first: they are what a reader sees first, and what
// free text on /corrector does not have.
const METRICS: { key: string; label: string; hint?: string }[] = [
  { key: "title", label: "Title" },
  { key: "subtitle", label: "Subtitle" },
  { key: "grammar", label: "Grammar" },
  { key: "factConsistency", label: "Fact consistency", hint: "against the sources and fact-checks" },
  { key: "coverageVerification", label: "Coverage verification", hint: "fit with Inspiring's mission" },
  { key: "seo", label: "SEO" },
  { key: "readability", label: "Readability" },
  { key: "hallucinationIndex", label: "Hallucination index", hint: "higher = better grounded" },
  { key: "style", label: "Writing style" },
];

// The backend's UNAVAILABLE_SUMMARY (src/services/corrector/text_corrector.py)
// begins with this: the model gave no usable score, and the 0 that comes
// with it is not a judgement. Drawn as "not scored", never as a red bar.
const UNAVAILABLE_PREFIX = "Evaluation unavailable";

const CHANGED_BY: Record<RevisionReason, string> = {
  generated: "the text was written again",
  edited: "the text was edited",
  corrected: "a correction was accepted",
  rewritten: "the text was rewritten",
};

type View = "changes" | "side-by-side";

export function DraftReviewPanel({ draft, onChange }: DraftStageProps) {
  const [pending, setPending] = useState<"review" | "accept" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<View>("changes");

  const review = draft.review;
  const busy = draft.busy !== null || pending !== null;

  async function act(action: "review" | "accept-correction") {
    setPending(action === "review" ? "review" : "accept");
    setError(null);

    try {
      onChange(await draftsApi<ArticleDraft>(`${draft.id}/${action}`, { method: "POST" }));
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setPending(null);
    }
  }

  const reviewedBefore = draft.revisions.some((revision) => revision.review !== null);
  const lastRevision = draft.revisions[draft.revisions.length - 1];
  const stale = review === null && reviewedBefore;

  return (
    <section className={`card ${styles.panel}`} aria-labelledby="draft-review-heading">
      <div className={styles.header}>
        <div>
          <h2 id="draft-review-heading">Review</h2>
          <p className={styles.meta}>
            {review
              ? `Reviewed ${new Date(review.reviewedAt).toLocaleString()}${review.model ? ` by ${review.model}` : ""}.`
              : "Grammar, facts against the sources, fit with Inspiring, SEO, readability, grounding and style - and a proposed correction."}
          </p>
        </div>

        <button type="button" className={styles.action} disabled={busy} onClick={() => act("review")}>
          {(pending === "review" || draft.busy === "reviewing") && <span className="spinner" aria-hidden="true" />}
          {draft.busy === "reviewing" ? "Reviewing…" : review ? "Review again" : "Review"}
        </button>
      </div>

      {stale && (
        <p className={styles.stale} role="status">
          The last review is out of date: {lastRevision ? CHANGED_BY[lastRevision.reason] : "the text changed"} after it
          ran. Review the draft again to score the current text.
        </p>
      )}

      {!review && !stale && draft.busy !== "reviewing" && <p className={styles.meta}>Not reviewed yet.</p>}

      {error && (
        <div className="error-banner" role="alert">
          {error}
        </div>
      )}

      {review && <MetricGrid metrics={review.metrics} />}

      {review && (
        <Proposal
          current={draft.content}
          corrected={review.corrected}
          view={view}
          onView={setView}
          published={draft.status === "published"}
          disabled={busy}
          accepting={pending === "accept"}
          onAccept={() => act("accept-correction")}
        />
      )}
    </section>
  );
}

// ----------------------------------------------------------------------
// Metrics
// ----------------------------------------------------------------------

function MetricGrid({ metrics }: { metrics: Record<string, CorrectionMetric> }) {
  // Any metric the backend adds later is shown after the known ones,
  // under its own key, rather than dropped.
  const known = new Set(METRICS.map((metric) => metric.key));
  const extra = Object.keys(metrics)
    .filter((key) => !known.has(key))
    .map((key) => ({ key, label: key, hint: undefined }));

  return (
    <div className="metric-grid">
      {METRICS.concat(extra)
        .filter(({ key }) => metrics[key])
        .map(({ key, label, hint }) => {
          const metric = metrics[key];
          const unavailable = metric.summary.startsWith(UNAVAILABLE_PREFIX);

          return (
            <div
              key={key}
              className={`metric-card ${unavailable ? styles.unavailable : scoreTierClass(metric.score)}`}
            >
              <div className="metric-title">
                {label}
                {hint && <span className={styles.hint}> · {hint}</span>}
              </div>
              {unavailable ? (
                <p className={styles.notScored}>Not scored</p>
              ) : (
                <ScoreBar label="Score" value={metric.score} />
              )}
              <p className="metric-summary">{metric.summary}</p>
              {metric.issues.length > 0 && (
                <ul className="metric-issues">
                  {metric.issues.map((issue, index) => (
                    <li key={index}>{issue}</li>
                  ))}
                </ul>
              )}
            </div>
          );
        })}
    </div>
  );
}

// The same tiers as /corrector, so one colour means one thing on both.
function scoreTierClass(score: number): string {
  if (score >= 70) return "metric-card-good";
  if (score >= 40) return "metric-card-warn";
  return "metric-card-bad";
}

// ----------------------------------------------------------------------
// The proposed correction
// ----------------------------------------------------------------------

function Proposal({
  current,
  corrected,
  view,
  onView,
  published,
  disabled,
  accepting,
  onAccept,
}: {
  current: DraftContent;
  corrected: DraftContent | null;
  view: View;
  onView: (view: View) => void;
  published: boolean;
  disabled: boolean;
  accepting: boolean;
  onAccept: () => void;
}) {
  const fields = useMemo(
    () =>
      corrected
        ? (["title", "subtitle", "body"] as const).map((field) => ({
            field,
            pieces: wordDiff(current[field], corrected[field]),
          }))
        : [],
    [current, corrected]
  );

  if (!corrected) {
    return (
      <>
        <h3 className="section-label">Proposed correction</h3>
        <p className={styles.meta}>
          No proposal: the model did not return a usable corrected version, or it broke a rule a correction must keep
          (no new citations, none lost, the same language, about the same length). The metrics above still stand.
        </p>
      </>
    );
  }

  const changes = fields.reduce(
    (count, { pieces }) =>
      count + (pieces ? pieces.filter((piece) => piece.kind !== "same" && piece.text.trim()).length : 1),
    0
  );

  const identical =
    corrected.title === current.title && corrected.subtitle === current.subtitle && corrected.body === current.body;

  return (
    <>
      <div className={styles.proposalHeader}>
        <h3 className="section-label">Proposed correction</h3>

        {!identical && (
          <div className={styles.views} role="group" aria-label="How to compare">
            <button
              type="button"
              className={`${styles.toggle} ${view === "changes" ? styles.toggleActive : ""}`}
              aria-pressed={view === "changes"}
              onClick={() => onView("changes")}
            >
              Changes
            </button>
            <button
              type="button"
              className={`${styles.toggle} ${view === "side-by-side" ? styles.toggleActive : ""}`}
              aria-pressed={view === "side-by-side"}
              onClick={() => onView("side-by-side")}
            >
              Side by side
            </button>
          </div>
        )}
      </div>

      {identical ? (
        <p className={styles.meta}>The corrector proposes no changes.</p>
      ) : view === "changes" ? (
        <div className={styles.changes}>
          <p className={styles.meta}>
            {changes} change{changes === 1 ? "" : "s"}: <del className={styles.removed}>removed</del>{" "}
            <ins className={styles.added}>added</ins>
          </p>
          {fields.map(({ field, pieces }) => (
            <div key={field} className={styles.field}>
              <div className={styles.fieldLabel}>{field}</div>
              {pieces ? (
                <div className={`${styles.diff} ${field === "title" ? styles.diffTitle : ""}`}>
                  {pieces.map((piece, index) =>
                    piece.kind === "same" ? (
                      <Fragment key={index}>{piece.text}</Fragment>
                    ) : piece.kind === "added" ? (
                      <ins key={index} className={styles.added}>
                        {piece.text}
                      </ins>
                    ) : (
                      <del key={index} className={styles.removed}>
                        {piece.text}
                      </del>
                    )
                  )}
                </div>
              ) : (
                <p className={styles.meta}>Too long to compare word by word here; use Side by side.</p>
              )}
            </div>
          ))}
        </div>
      ) : (
        <div className={styles.sideBySide}>
          <Version heading="Current" content={current} />
          <Version heading="Proposed" content={corrected} />
        </div>
      )}

      {!identical && (
        <div className={styles.acceptRow}>
          <button type="button" className={styles.action} disabled={disabled || published} onClick={onAccept}>
            {accepting && <span className="spinner" aria-hidden="true" />}
            Accept correction
          </button>
          <p className={styles.meta}>
            {published
              ? "This draft is published; unpublish it before changing it."
              : "Replaces the title, subtitle and body. The current text stays in the draft's history."}
          </p>
        </div>
      )}
    </>
  );
}

function Version({ heading, content }: { heading: string; content: DraftContent }) {
  return (
    <div className={styles.version}>
      <div className={styles.fieldLabel}>{heading}</div>
      <h4 className={styles.versionTitle}>{content.title}</h4>
      {content.subtitle && <p className={styles.versionSubtitle}>{content.subtitle}</p>}
      <ArticleBody body={content.body} />
    </div>
  );
}

// ----------------------------------------------------------------------
// A word-level diff, no dependency
// ----------------------------------------------------------------------

type Piece = { kind: "same" | "added" | "removed"; text: string };

// A body of ~2,000 words against its correction: the LCS table is
// words x words cells. Past this the comparison falls back to side by
// side rather than freeze the tab.
const MAX_DIFF_CELLS = 6_000_000;

/** Words and the whitespace between them, so the diff keeps line breaks. */
function tokens(text: string): string[] {
  return text.match(/\s+|[^\s]+/g) ?? [];
}

/**
 * Longest common subsequence over tokens, walked from the start. Returns
 * null when the texts are too long to compare here.
 */
function wordDiff(before: string, after: string): Piece[] | null {
  const a = tokens(before);
  const b = tokens(after);
  const n = a.length;
  const m = b.length;

  if ((n + 1) * (m + 1) > MAX_DIFF_CELLS) return null;

  const width = m + 1;
  // table[i * width + j]: the LCS length of a[i..] and b[j..].
  const table = new Uint32Array((n + 1) * width);

  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      table[i * width + j] =
        a[i] === b[j]
          ? table[(i + 1) * width + j + 1] + 1
          : Math.max(table[(i + 1) * width + j], table[i * width + j + 1]);
    }
  }

  const pieces: Piece[] = [];

  function push(kind: Piece["kind"], text: string) {
    const last = pieces[pieces.length - 1];
    if (last && last.kind === kind) last.text += text;
    else pieces.push({ kind, text });
  }

  let i = 0;
  let j = 0;

  while (i < n && j < m) {
    if (a[i] === b[j]) {
      push("same", a[i]);
      i++;
      j++;
    } else if (table[(i + 1) * width + j] >= table[i * width + j + 1]) {
      push("removed", a[i]);
      i++;
    } else {
      push("added", b[j]);
      j++;
    }
  }

  while (i < n) push("removed", a[i++]);
  while (j < m) push("added", b[j++]);

  return pieces;
}
