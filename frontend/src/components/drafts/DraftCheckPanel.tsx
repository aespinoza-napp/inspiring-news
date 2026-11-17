"use client";

import { useState } from "react";
import { ArticleDraft, DraftStageProps, draftsApi } from "@/lib/drafts";
import styles from "./DraftCheckPanel.module.css";

/**
 * The draft's own fact-check (backend src/services/writer/draft_fact_check.py,
 * 2026-11-17): each cited sentence held to the excerpts of the sources it
 * cites, by MiniCheck. The second check of the pipeline - the first was the
 * analysed article's - and it comes before the review and the approval,
 * which the backend refuses for a text never checked. An unsupported
 * sentence is listed, not removed: the person decides, as with the review.
 */
export function DraftCheckPanel({ draft, onChange }: DraftStageProps) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const check = draft.check ?? null;
  const busy = draft.busy !== null || pending;
  const unsupported = check ? check.sentences.filter((sentence) => !sentence.supported) : [];

  async function run() {
    setPending(true);
    setError(null);
    try {
      onChange(await draftsApi<ArticleDraft>(`${draft.id}/check`, { method: "POST" }));
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setPending(false);
    }
  }

  return (
    <section className={`card ${styles.panel}`} aria-labelledby="draft-check-title">
      <div className={styles.header}>
        <div>
          <h2 id="draft-check-title">Fact-check of the draft</h2>
          <p className={styles.meta}>
            Every sentence that cites a source, held to what that source says. It runs after writing and
            before every review; approval waits for it.
          </p>
        </div>
        {draft.status !== "published" && (
          <button type="button" className={styles.action} onClick={run} disabled={busy}>
            {check ? "Check again" : "Check the draft"}
          </button>
        )}
      </div>

      {error && <p className="error-banner">{error}</p>}

      {!check && <p className={styles.note}>This text has not been checked yet.</p>}

      {check?.error && <p className={styles.warn}>{check.error}</p>}

      {check && !check.error && (
        <>
          <p className={styles.summary}>
            <b>{check.sentences.length - unsupported.length}</b> of <b>{check.sentences.length}</b> cited sentences
            supported by their sources
            {check.uncited.length > 0 && <>; {check.uncited.length} cite nothing</>}.
            <span className={styles.meta}> {check.model ?? "MiniCheck"}, threshold {check.threshold}.</span>
          </p>

          {unsupported.length > 0 && (
            <>
              <h3 className={styles.subhead}>Not supported by what they cite</h3>
              <ul className={styles.list}>
                {unsupported.map((sentence, index) => (
                  <li key={index}>
                    <span>{sentence.text}</span>
                    <span className={styles.score}>
                      cites [{sentence.sources.join("], [")}] · support {Math.round(sentence.support * 100)}%
                      {sentence.translated ? " · read in English" : ""}
                    </span>
                  </li>
                ))}
              </ul>
            </>
          )}

          {check.uncited.length > 0 && (
            <>
              <h3 className={styles.subhead}>Citing nothing</h3>
              <ul className={styles.list}>
                {check.uncited.map((sentence, index) => (
                  <li key={index}>{sentence}</li>
                ))}
              </ul>
            </>
          )}
        </>
      )}
    </section>
  );
}
