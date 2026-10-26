"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { DraftEditor } from "@/components/drafts/DraftEditor";
import { DraftReviewPanel } from "@/components/drafts/DraftReviewPanel";
import { DraftTrendPanel } from "@/components/drafts/DraftTrendPanel";
import { PublishPanel } from "@/components/drafts/PublishPanel";
import { RewritePanel } from "@/components/drafts/RewritePanel";
import { ArticleDraft, BUSY_LABEL, LANGUAGES, draftsApi } from "@/lib/drafts";

const POLL_MS = 2000;

/**
 * One draft's workspace: the article, its review, rewriting, publishing. Each stage
 * is its own component and gets the same two props - the draft, and
 * `onChange` to hand back the draft its own API call returned. A step
 * that starts background work returns the draft `busy`; the page polls
 * until it is not, so no component polls on its own.
 */
export default function DraftPage({ params }: { params: { id: string } }) {
  const [draft, setDraft] = useState<ArticleDraft | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const next = await draftsApi<ArticleDraft>(params.id);
      setDraft(next);
      setError(null);
      return next;
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
      return null;
    }
  }, [params.id]);

  const busy = draft?.busy ?? null;

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    async function tick() {
      const next = await load();
      // Rescheduled only behind `cancelled` (frontend/CLAUDE.md, the
      // useAnalysisJob incident).
      if (!cancelled && next?.busy) {
        timer = setTimeout(tick, POLL_MS);
      }
    }

    tick();

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [load, busy]);

  if (!draft) {
    return (
      <>
        <p className="reader-back">
          <Link href="/drafts">← Drafts</Link>
        </p>
        {error ? (
          <div className="error-banner" role="alert">
            {error}
          </div>
        ) : (
          <p className="subtitle">Loading…</p>
        )}
      </>
    );
  }

  const language = LANGUAGES.find((entry) => entry.code === draft.language)?.label ?? draft.language;

  return (
    <>
      <p className="reader-back">
        <Link href="/drafts">← Drafts</Link>
      </p>

      <p className="subtitle">
        {language} · {draft.status}
        {draft.model ? ` · written by ${draft.model}` : ""}
      </p>

      {draft.busy && (
        <p className="subtitle" role="status">
          <span className="spinner" aria-hidden="true" /> {BUSY_LABEL[draft.busy]}
        </p>
      )}

      {(draft.error || error) && (
        <div className="error-banner" role="alert">
          {draft.error ?? error}
        </div>
      )}

      <DraftTrendPanel draft={draft} onChange={setDraft} />

      <DraftEditor draft={draft} onChange={setDraft} />

      <DraftReviewPanel draft={draft} onChange={setDraft} />

      <RewritePanel draft={draft} onChange={setDraft} />

      <PublishPanel draft={draft} onChange={setDraft} />
    </>
  );
}
