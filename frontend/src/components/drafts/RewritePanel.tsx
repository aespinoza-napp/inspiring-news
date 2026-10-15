"use client";

import { useEffect, useMemo, useState } from "react";
import {
  ArticleDraft,
  DraftContent,
  DraftReview,
  DraftStageProps,
  MetricStanding,
  REVIEW_METRICS,
  RevisionReason,
  RewriteRequest,
  RewriteTargetsInfo,
  draftsApi,
  metricStanding,
} from "@/lib/drafts";
import styles from "./RewritePanel.module.css";

/**
 * The rewrite stage (docs/decisions/writing.md, "Rewriting"; backend
 * src/api/rewrite_routes.py). Each review metric against its target - the
 * metrics expected - and, when the review falls short, a rewrite guided by
 * what fell short: the same sources and fact-checks, reviewed again at
 * once. Then the history, from which any earlier text (and its review)
 * can be restored, since a rewrite that scores worse is kept too.
 *
 * Rewrite and Restore hand the page the draft their call returned; a
 * rewrite comes back busy and the page polls it. Nothing here runs while
 * the draft is busy or published.
 */

const REASON_LABEL: Record<RevisionReason, string> = {
  generated: "Written",
  edited: "Edited by a person",
  corrected: "Correction accepted",
  rewritten: "Rewritten",
  restored: "Restored",
};

const STANDING_LABEL: Record<MetricStanding, string> = {
  met: "Meets target",
  below: "Below target",
  unscored: "Not scored",
};

// Beside each revision in the history: the two metrics about truth, held
// to the strictest targets, and grammar, what a reader sees first.
const HEADLINE: { key: string; label: string }[] = [
  { key: "factConsistency", label: "Facts" },
  { key: "hallucinationIndex", label: "Grounding" },
  { key: "grammar", label: "Grammar" },
];

// Issues listed per metric under "What will be addressed" before "+N more".
const ISSUES_SHOWN = 3;

type Pending = "rewrite" | number | null;

function sameText(a: DraftContent, b: DraftContent): boolean {
  return a.title === b.title && a.subtitle === b.subtitle && a.body === b.body;
}

function scoreText(score: number): string {
  return Number.isInteger(score) ? String(score) : score.toFixed(1);
}

export function RewritePanel({ draft, onChange }: DraftStageProps) {
  const [info, setInfo] = useState<RewriteTargetsInfo | null>(null);
  const [infoError, setInfoError] = useState<string | null>(null);
  const [overrides, setOverrides] = useState<Record<string, number>>({});
  const [instructions, setInstructions] = useState("");
  const [rounds, setRounds] = useState<number | null>(null);
  const [pending, setPending] = useState<Pending>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const response = await fetch("/api/writing/targets", { cache: "no-store" });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(
            typeof data?.detail === "string" ? data.detail : data?.error ?? `Loading the targets failed (${response.status}).`
          );
        }
        if (!cancelled) setInfo(data as RewriteTargetsInfo);
      } catch (exc) {
        if (!cancelled) setInfoError(exc instanceof Error ? exc.message : String(exc));
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  const targets = useMemo<Record<string, number> | null>(
    () => (info ? { ...info.targets, ...overrides } : null),
    [info, overrides]
  );

  const review = draft.review;
  const published = draft.status === "published";
  const rewriting = draft.busy === "rewriting";
  const blocked = draft.busy !== null || pending !== null || published;

  const rows = REVIEW_METRICS.map(({ key, label }) => {
    const metric = review?.metrics[key] ?? null;
    const target = targets?.[key];
    const standing = metric && target !== undefined ? metricStanding(metric, target, info?.unscoredSummary) : null;
    return { key, label, metric, target, standing };
  });

  const below = rows.filter((row) => row.standing === "below");
  const unscored = rows.filter((row) => row.standing === "unscored");
  const unmet = below.length > 0;

  const maxRounds = info?.rounds.max ?? 1;
  const chosenRounds = rounds ?? info?.rounds.default ?? 1;
  const maxChars = info?.maxInstructionsChars ?? 2000;

  function setTarget(key: string, raw: string) {
    if (!info) return;
    const value = Number(raw);
    if (raw.trim() === "" || !Number.isFinite(value)) return;
    const clamped = Math.max(0, Math.min(100, value));
    setOverrides((current) => {
      const next = { ...current };
      if (clamped === info.targets[key]) delete next[key];
      else next[key] = clamped;
      return next;
    });
  }

  async function startRewrite() {
    setPending("rewrite");
    setError(null);

    const body: RewriteRequest = {};
    if (Object.keys(overrides).length > 0) body.targets = overrides;
    if (instructions.trim()) body.instructions = instructions.trim();
    if (info && chosenRounds !== info.rounds.default) body.maxRounds = chosenRounds;

    try {
      onChange(await draftsApi<ArticleDraft>(`${draft.id}/rewrite`, { method: "POST", body }));
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setPending(null);
    }
  }

  async function restore(index: number) {
    if (
      draft.status === "approved" &&
      !window.confirm("Restoring changes the text, so the draft goes back to draft and must be approved again. Restore it?")
    ) {
      return;
    }

    setPending(index);
    setError(null);

    try {
      onChange(await draftsApi<ArticleDraft>(`${draft.id}/restore`, { method: "POST", body: { revision: index } }));
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setPending(null);
    }
  }

  const buttonLabel = rewriting ? "Rewriting…" : !review ? "Review first" : unmet ? `Rewrite (${below.length} below target)` : "Rewrite";

  return (
    <section className={`card ${styles.panel}`} aria-labelledby="rewrite-heading">
      <h2 id="rewrite-heading">Rewrite</h2>
      <p className={styles.meta}>
        Each metric of the review against the score expected of it. When the review falls short, the article can be
        rewritten from the same sources and fact-checks, guided by what fell short, and the new text is reviewed at
        once.
      </p>

      {infoError && (
        <p className={styles.note} role="status">
          The targets could not be loaded ({infoError}), so no metric is judged here. A rewrite still uses the
          backend&apos;s default targets.
        </p>
      )}

      {/* ---------------- the metrics against their targets ---------------- */}

      <div className={styles.targetsHeader}>
        <h3 className="section-label">Targets</h3>
        {Object.keys(overrides).length > 0 && (
          <button type="button" className="button-link" onClick={() => setOverrides({})} disabled={blocked}>
            Reset to the defaults
          </button>
        )}
      </div>

      {!review && (
        <p className={styles.meta}>
          {draft.revisions.some((revision) => revision.review !== null)
            ? "The current text has no review: it changed after the last one. Review it to see how it measures up."
            : "Not reviewed yet: review the draft to see how it measures up."}
        </p>
      )}

      <ul className={styles.metrics}>
        {rows.map(({ key, label, metric, target, standing }) => (
          <li key={key} className={`${styles.metric} ${standing ? styles[standing] : ""}`}>
            <span className={styles.metricLabel}>{label}</span>

            <span className={styles.track} aria-hidden="true">
              {metric && standing !== "unscored" && (
                <span className={styles.fill} style={{ width: `${Math.max(0, Math.min(metric.score, 100))}%` }} />
              )}
              {target !== undefined && <span className={styles.tick} style={{ left: `${target}%` }} />}
            </span>

            <span className={styles.numbers}>
              {metric ? (standing === "unscored" ? "–" : scoreText(metric.score)) : "–"}
              <span className={styles.muted}> / </span>
              {info ? (
                <input
                  type="number"
                  className={styles.targetInput}
                  min={0}
                  max={100}
                  step={5}
                  value={target ?? ""}
                  disabled={blocked}
                  aria-label={`Target for ${label}`}
                  onChange={(event) => setTarget(key, event.target.value)}
                />
              ) : (
                "–"
              )}
            </span>

            <span className={`${styles.standing} ${standing ? styles[`standing-${standing}`] : ""}`}>
              {standing ? STANDING_LABEL[standing] : review ? "–" : "Not reviewed"}
            </span>
          </li>
        ))}
      </ul>

      {unscored.length > 0 && (
        <p className={styles.note}>
          <strong>Not scored:</strong> {unscored.map((row) => row.label).join(", ")}. The reviewer gave no usable score,
          so {unscored.length === 1 ? "it counts" : "they count"} neither for nor against the targets. Review again to
          score {unscored.length === 1 ? "it" : "them"}.
        </p>
      )}

      {Object.keys(overrides).length > 0 && (
        <p className={styles.meta}>
          Changed targets apply to this page and to the next rewrite; they are not saved with the draft.
        </p>
      )}

      {/* ---------------- what a rewrite would address ---------------- */}

      {review && (
        <>
          <h3 className="section-label">What will be addressed</h3>
          {below.length > 0 ? (
            <ul className={styles.addressed}>
              {below.map(({ key, label, metric, target }) => (
                <li key={key}>
                  <strong>{label}</strong>{" "}
                  <span className={styles.muted}>
                    {scoreText(metric!.score)} against {scoreText(target!)}
                  </span>
                  {metric!.summary && <span className={styles.summary}> - {metric!.summary}</span>}
                  {metric!.issues.length > 0 && (
                    <ul>
                      {metric!.issues.slice(0, ISSUES_SHOWN).map((issue, index) => (
                        <li key={index}>{issue}</li>
                      ))}
                      {metric!.issues.length > ISSUES_SHOWN && (
                        <li className={styles.muted}>and {metric!.issues.length - ISSUES_SHOWN} more</li>
                      )}
                    </ul>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <p className={styles.meta}>
              {targets
                ? "Every scored metric meets its target. A rewrite now would follow your instructions below and the review's remaining notes."
                : "The targets are not loaded, so nothing is judged below target here."}
            </p>
          )}
        </>
      )}

      {/* ---------------- the request ---------------- */}

      <label className="field-label" htmlFor="rewrite-instructions">
        Instructions for this rewrite (optional)
      </label>
      <textarea
        id="rewrite-instructions"
        className={styles.instructions}
        value={instructions}
        maxLength={maxChars}
        disabled={blocked}
        placeholder="e.g. Shorter sentences; lead with what changed for the fishermen."
        onChange={(event) => setInstructions(event.target.value)}
      />
      <p className={styles.meta}>
        {instructions.length.toLocaleString()} / {maxChars.toLocaleString()} characters. Added to the draft&apos;s own
        indications, which still apply. The rewrite may add no facts and keeps every citation on its statement.
      </p>

      {maxRounds > 1 && (
        <div className={styles.rounds}>
          <label htmlFor="rewrite-rounds">Rounds</label>
          <select
            id="rewrite-rounds"
            value={chosenRounds}
            disabled={blocked}
            onChange={(event) => setRounds(Number(event.target.value))}
          >
            {Array.from({ length: maxRounds }, (_, index) => index + 1).map((count) => (
              <option key={count} value={count}>
                {count}
              </option>
            ))}
          </select>
          <span className={styles.meta}>
            Each round is a rewrite and a review - minutes of the model each. A further round runs only while a scored
            metric is still below its target.
          </span>
        </div>
      )}

      {draft.status === "approved" && review && (
        <p className={styles.note}>Rewriting changes the text, so the draft goes back to draft and must be approved again.</p>
      )}

      <div className={styles.actionRow}>
        <button
          type="button"
          className={unmet ? styles.emphasised : "button-secondary"}
          disabled={!review || blocked}
          onClick={startRewrite}
        >
          {(pending === "rewrite" || rewriting) && <span className="spinner" aria-hidden="true" />}
          {buttonLabel}
        </button>
        <p className={styles.meta}>
          {published
            ? "This draft is published; unpublish it before changing it."
            : rewriting
              ? "Rewriting, then reviewing the new text…"
              : !review
                ? "A rewrite is guided by the review of the current text: review the draft first."
                : unmet
                  ? "If the new text scores worse, restore the earlier one from the history below."
                  : "Every scored metric meets its target; rewrite only if you want another version."}
        </p>
      </div>

      {error && (
        <div className="error-banner" role="alert">
          {error}
        </div>
      )}

      {/* ---------------- the history ---------------- */}

      {draft.revisions.length > 0 && (
        <History
          draft={draft}
          targets={targets}
          unscoredSummary={info?.unscoredSummary}
          blocked={blocked}
          pending={pending}
          onRestore={restore}
        />
      )}
    </section>
  );
}

// ----------------------------------------------------------------------
// The history, newest first, each revision with its own review
// ----------------------------------------------------------------------

function History({
  draft,
  targets,
  unscoredSummary,
  blocked,
  pending,
  onRestore,
}: {
  draft: ArticleDraft;
  targets: Record<string, number> | null;
  unscoredSummary: string | undefined;
  blocked: boolean;
  pending: Pending;
  onRestore: (index: number) => void;
}) {
  const last = draft.revisions.length - 1;

  const entries = draft.revisions.map((revision, index) => {
    // The current text's review is the draft's; an earlier text's is the
    // one it kept when it was replaced.
    const review = index === last ? draft.review : revision.review;

    // A restored revision is a copy of an earlier text: say which.
    let from: number | null = null;
    if (revision.reason === "restored") {
      for (let earlier = index - 1; earlier >= 0; earlier--) {
        if (sameText(draft.revisions[earlier].content, revision.content)) {
          from = earlier;
          break;
        }
      }
    }

    return { revision, index, review, from };
  });

  return (
    <>
      <h3 className="section-label">History ({draft.revisions.length})</h3>
      <ol className={styles.history}>
        {entries.reverse().map(({ revision, index, review, from }) => {
          const current = index === last;
          const asCurrent = sameText(revision.content, draft.content);

          return (
            <li key={`${revision.at}-${index}`} className={`${styles.revision} ${current ? styles.currentRevision : ""}`}>
              <div className={styles.revisionText}>
                <div className={styles.revisionHead}>
                  <span className={styles.revisionNumber}>#{index + 1}</span>
                  <span className={styles.reason}>{REASON_LABEL[revision.reason] ?? revision.reason}</span>
                  {from !== null && <span className={styles.muted}>from #{from + 1}</span>}
                  {revision.model && (
                    <span className={styles.muted}>
                      {revision.reason === "restored" ? `text by ${revision.model}` : `by ${revision.model}`}
                    </span>
                  )}
                  <time className={styles.muted} dateTime={revision.at}>
                    {new Date(revision.at).toLocaleString()}
                  </time>
                  {current && <span className={styles.currentTag}>Current</span>}
                </div>
                <p className={styles.revisionTitle}>{revision.content.title}</p>
                <RevisionScores review={review} targets={targets} unscoredSummary={unscoredSummary} />
              </div>

              {!current && (
                <button
                  type="button"
                  className={`button-secondary ${styles.restore}`}
                  disabled={blocked || asCurrent}
                  title={asCurrent ? "This is the current text." : undefined}
                  onClick={() => onRestore(index)}
                >
                  {pending === index && <span className="spinner" aria-hidden="true" />}
                  Restore
                </button>
              )}
            </li>
          );
        })}
      </ol>
      <p className={styles.meta}>
        Restore puts that text back, with its review, as a new revision: nothing in the history is lost.
      </p>
    </>
  );
}

function RevisionScores({
  review,
  targets,
  unscoredSummary,
}: {
  review: DraftReview | null;
  targets: Record<string, number> | null;
  unscoredSummary: string | undefined;
}) {
  if (!review) return <p className={styles.revisionScores}>Not reviewed</p>;

  const judged = targets
    ? REVIEW_METRICS.filter(({ key }) => review.metrics[key] && targets[key] !== undefined).map(({ key }) =>
        metricStanding(review.metrics[key], targets[key], unscoredSummary)
      )
    : [];

  const scored = judged.filter((standing) => standing !== "unscored").length;
  const met = judged.filter((standing) => standing === "met").length;

  return (
    <p className={styles.revisionScores}>
      {targets && (
        <span>
          {met} of {scored} scored target{scored === 1 ? "" : "s"} met
        </span>
      )}
      {HEADLINE.filter(({ key }) => review.metrics[key]).map(({ key, label }) => {
        const metric = review.metrics[key];
        const standing = targets ? metricStanding(metric, targets[key], unscoredSummary) : null;
        return (
          <span key={key} className={`${styles.chip} ${standing ? styles[`standing-${standing}`] : ""}`}>
            {label} {standing === "unscored" ? "not scored" : scoreText(metric.score)}
          </span>
        );
      })}
    </p>
  );
}
