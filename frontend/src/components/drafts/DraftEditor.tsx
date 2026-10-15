"use client";

import { ArticleBody } from "@/components/drafts/ArticleBody";
import { DraftStageProps } from "@/lib/drafts";

/**
 * The article as written: title, subtitle, body with its citations, the
 * sources and fact-checks behind it, its metadata, and a person's edit.
 * Filled in by the writer stage (docs/decisions/writing.md, "Writing").
 */
export function DraftEditor({ draft }: DraftStageProps) {
  return (
    <article>
      <h1>{draft.content.title}</h1>
      {draft.content.subtitle && <p className="subtitle">{draft.content.subtitle}</p>}
      <ArticleBody body={draft.content.body} />
    </article>
  );
}
