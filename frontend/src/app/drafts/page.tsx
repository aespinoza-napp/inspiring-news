"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { NewDraftForm } from "@/components/drafts/NewDraftForm";
import { DraftSummary, LANGUAGES, draftsApi } from "@/lib/drafts";

/**
 * The newsroom's articles in progress, and where a new one starts
 * (docs/decisions/writing.md). Behind the site password, unlike /reader:
 * a draft is unpublished work.
 */
export default function DraftsPage() {
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

  return (
    <>
      <h1>Drafts</h1>
      <p className="subtitle">
        Articles written from an analysed article and the news related to it, then reviewed, rewritten if they fall
        short, and published.
      </p>

      <NewDraftForm />

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
