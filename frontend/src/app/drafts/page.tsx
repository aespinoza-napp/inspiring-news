"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { FlowSteps } from "@/components/FlowSteps";
import { NewDraftForm } from "@/components/drafts/NewDraftForm";
import { DraftSummary, LANGUAGES, draftsApi } from "@/lib/drafts";

const READER_ID = /^[0-9a-f]{16}$/;

/**
 * The newsroom's articles in progress, and where a new one starts
 * (docs/decisions/writing.md). Behind the site password, unlike /reader:
 * a draft is unpublished work.
 *
 * `?url=` or `?article=` names the analysed article to start from: the
 * Analyze page links here with the URL once an article has passed, and a
 * draft's page with the reader id, to start again from the same article.
 */
export default function DraftsPage({ searchParams }: { searchParams: { url?: string; article?: string } }) {
  const [drafts, setDrafts] = useState<DraftSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    draftsApi<DraftSummary[]>("")
      .then((rows) => {
        if (!cancelled) setDrafts(rows);
      })
      .catch((exc) => {
        if (!cancelled) setError(exc instanceof Error ? exc.message : String(exc));
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const initialUrl = typeof searchParams.url === "string" ? searchParams.url : null;
  const initialArticleId =
    typeof searchParams.article === "string" && READER_ID.test(searchParams.article) ? searchParams.article : null;

  return (
    <>
      <FlowSteps current="write" />

      <h1>Drafts</h1>
      <p className="subtitle">
        Articles written from an analysed article and the news related to it, then reviewed, rewritten if they fall
        short, and published.
      </p>

      <NewDraftForm initialUrl={initialUrl} initialArticleId={initialArticleId} />

      {error && (
        <div className="error-banner" role="alert">
          {error}
        </div>
      )}

      {drafts && drafts.length === 0 && <p className="subtitle">No drafts yet.</p>}

      {drafts && drafts.length > 0 && (
        <ul className="drafts-list">
          {drafts.map((draft) => (
            <li key={draft.id}>
              <Link href={`/drafts/${draft.id}`}>{draft.title || "Untitled"}</Link>{" "}
              <span className="subtitle">
                {LANGUAGES.find((entry) => entry.code === draft.language)?.label ?? draft.language} · {draft.status}
                {draft.busy ? ` · ${draft.busy}` : ""} · {new Date(draft.updatedAt).toLocaleString()}
              </span>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
