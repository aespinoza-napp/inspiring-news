"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { ArticleBody } from "@/components/drafts/ArticleBody";
import { VerdictBadge } from "@/components/VerdictBadge";
import { ArticleDraft, DraftContent, DraftStageProps, SourceOrigin, draftsApi } from "@/lib/drafts";
import { safeHref } from "@/lib/links";
import { percent, readableDate } from "@/lib/reader";
import { Verdict } from "@/lib/types";

const ORIGIN_LABEL: Record<SourceOrigin, string> = {
  analysed: "Analysed article",
  related: "Related news",
  evidence: "Fact-check evidence",
};

const VERDICTS = new Set<string>(["TRUE", "PARTIALLY_TRUE", "FALSE", "MISLEADING", "UNVERIFIED"]);

const REASON_LABEL: Record<string, string> = {
  generated: "Written",
  edited: "Edited by a person",
  corrected: "Corrections accepted",
  rewritten: "Rewritten",
};

/**
 * The article as written: title, subtitle, body with its citations, the
 * sources and fact-checks behind it, its metadata, and a person's edit
 * (docs/decisions/writing.md, "Writing").
 *
 * The sources are saved before the model writes, so while the draft is
 * `generating` they show here already, and the body fills in when the
 * model answers. Each source's list item is `#source-n`, where the
 * body's `[n]` links (ArticleBody).
 */
export function DraftEditor({ draft, onChange }: DraftStageProps) {
  const [editing, setEditing] = useState<DraftContent | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const written = draft.revisions.length > 0;
  const generating = draft.busy === "generating";
  const canEdit = written && draft.busy === null && draft.status !== "published";

  async function save(event: FormEvent) {
    event.preventDefault();

    if (!editing || saving) return;

    setSaving(true);
    setError(null);

    try {
      const next = await draftsApi<ArticleDraft>(`${draft.id}/content`, { method: "PUT", body: editing });
      onChange(next);
      setEditing(null);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      {editing ? (
        <form className="card draft-edit" onSubmit={save}>
          <label className="field-label" htmlFor="draft-title">
            Title
          </label>
          <input
            id="draft-title"
            type="text"
            value={editing.title}
            onChange={(event) => setEditing({ ...editing, title: event.target.value })}
            disabled={saving}
          />

          <label className="field-label" htmlFor="draft-subtitle">
            Subtitle
          </label>
          <input
            id="draft-subtitle"
            type="text"
            value={editing.subtitle}
            onChange={(event) => setEditing({ ...editing, subtitle: event.target.value })}
            disabled={saving}
          />

          <label className="field-label" htmlFor="draft-body">
            Body
          </label>
          <textarea
            id="draft-body"
            className="draft-body-input"
            value={editing.body}
            onChange={(event) => setEditing({ ...editing, body: event.target.value })}
            disabled={saving}
          />
          <p className="claims-note">
            Paragraphs separated by a blank line; <code>## </code> and <code>### </code> subheadings; <code>- </code>{" "}
            lists; <code>**bold**</code>. <code>[n]</code> cites source n below. Saving makes a new revision and clears
            the review, which read the old text.
          </p>

          <div className="form-row">
            <button type="submit" disabled={saving || !editing.title.trim()}>
              {saving && <span className="spinner" aria-hidden="true" />}
              Save
            </button>
            <button type="button" className="button-secondary" onClick={() => setEditing(null)} disabled={saving}>
              Cancel
            </button>
          </div>

          {error && (
            <div className="error-banner" role="alert">
              {error}
            </div>
          )}
        </form>
      ) : (
        <article className="card draft-article">
          <h1 className="draft-title">{draft.content.title}</h1>
          {draft.content.subtitle && <p className="draft-subtitle">{draft.content.subtitle}</p>}

          {written ? (
            <ArticleBody body={draft.content.body} />
          ) : generating ? (
            <p className="subtitle">
              {draft.sources.length > 0
                ? `The model is writing from the ${draft.sources.length} sources below.`
                : "Finding news on the same story…"}{" "}
              The title above is the analysed article&apos;s, until the article arrives.
            </p>
          ) : (
            <p className="subtitle">
              No article was written.{" "}
              <Link href={`/drafts?article=${draft.sourceArticleId}`}>Start again from the same article</Link>.
            </p>
          )}

          {canEdit && (
            <div className="form-row">
              <button type="button" className="button-secondary" onClick={() => setEditing({ ...draft.content })}>
                Edit
              </button>
            </div>
          )}

          {written && draft.status === "published" && (
            <p className="claims-note">Published: unpublish it before editing.</p>
          )}
        </article>
      )}

      <DraftSources draft={draft} />

      <DraftFactChecks draft={draft} />

      {written && <DraftMetadataPanel draft={draft} />}

      {written && <DraftHistory draft={draft} />}
    </>
  );
}

function DraftSources({ draft }: { draft: ArticleDraft }) {
  if (draft.sources.length === 0) return null;

  const counts = draft.sources.reduce<Record<string, number>>((tally, source) => {
    tally[source.origin] = (tally[source.origin] ?? 0) + 1;
    return tally;
  }, {});

  return (
    <section className="card">
      <div className="section-label">
        Sources ({draft.sources.length})
        <span className="section-label-note">
          {(["analysed", "related", "evidence"] as SourceOrigin[])
            .filter((origin) => counts[origin])
            .map((origin) => `${counts[origin]} ${ORIGIN_LABEL[origin].toLowerCase()}`)
            .join(" · ")}
        </span>
      </div>

      {!draft.sources.some((source) => source.origin === "related") && (
        <p className="claims-note">
          No related news was found: the article rests on the analysed article and the evidence behind its fact-checks.
        </p>
      )}

      <ol className="draft-sources">
        {draft.sources.map((source, index) => {
          const href = safeHref(source.url);
          const date = readableDate(source.publishedAt);

          return (
            <li key={source.url} id={`source-${index + 1}`} className="draft-source">
              <span className="draft-source-number">[{index + 1}]</span>
              <div className="draft-source-text">
                <div>
                  {href ? (
                    <a href={href} target="_blank" rel="noopener noreferrer">
                      {source.title || source.url}
                    </a>
                  ) : (
                    source.title || source.url
                  )}
                </div>
                <div className="draft-source-meta">
                  <span className={`draft-origin draft-origin-${source.origin}`}>{ORIGIN_LABEL[source.origin]}</span>
                  {source.domain && <span>{source.domain}</span>}
                  {date && <span>{date}</span>}
                  <span>{source.reliabilityKnown ? "rated outlet" : "unrated outlet"}</span>
                </div>
                {source.excerpt && (
                  <details className="draft-source-excerpt">
                    <summary>What the writer saw ({source.excerpt.length.toLocaleString()} characters)</summary>
                    <p>{source.excerpt}</p>
                  </details>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

function DraftFactChecks({ draft }: { draft: ArticleDraft }) {
  if (draft.factChecks.length === 0) return null;

  const position = new Map(draft.sources.map((source, index) => [source.url, index + 1]));

  return (
    <section className="card">
      <div className="section-label">
        Fact-checks of the analysed article ({draft.factChecks.length})
        <span className="section-label-note">a claim not found true is not stated as fact</span>
      </div>

      {draft.factChecks.map((check, index) => {
        const verdict = VERDICTS.has(check.verdict) ? (check.verdict as Verdict) : null;
        const cited = check.sourceUrls.map((url) => position.get(url)).filter((n): n is number => n !== undefined);

        return (
          <div className={`claim claim-verdict-${(verdict ?? "none").toLowerCase()}`} key={`${check.claim}-${index}`}>
            <p className="claim-text">{check.claim}</p>
            <div className="claim-meta">
              <VerdictBadge verdict={verdict} />
              {check.confidence !== null && <span>confidence {percent(check.confidence)}</span>}
              {cited.length > 0 && (
                <span>
                  sources{" "}
                  {cited.map((n) => (
                    <a key={n} href={`#source-${n}`}>
                      [{n}]
                    </a>
                  ))}
                </span>
              )}
            </div>
          </div>
        );
      })}
    </section>
  );
}

function DraftMetadataPanel({ draft }: { draft: ArticleDraft }) {
  const { metadata } = draft;

  return (
    <section className="card">
      <div className="section-label">Metadata</div>
      <dl className="draft-metadata">
        <dt>Slug</dt>
        <dd>
          <code>{metadata.slug || "–"}</code>
        </dd>
        <dt>SEO description</dt>
        <dd>
          {metadata.seoDescription || "–"}
          {metadata.seoDescription && (
            <span className="draft-metadata-note"> ({metadata.seoDescription.length} characters)</span>
          )}
        </dd>
        <dt>Topic</dt>
        <dd>{metadata.topic ?? "–"}</dd>
        <dt>Keywords</dt>
        <dd>
          {metadata.keywords.length ? (
            <span className="chip-row">
              {metadata.keywords.map((keyword) => (
                <span className="chip" key={keyword}>
                  {keyword}
                </span>
              ))}
            </span>
          ) : (
            "–"
          )}
        </dd>
        <dt>Tags</dt>
        <dd>
          {metadata.tags.length ? (
            <span className="chip-row">
              {metadata.tags.map((tag) => (
                <span className="chip" key={tag}>
                  {tag}
                </span>
              ))}
            </span>
          ) : (
            "–"
          )}
        </dd>
      </dl>
    </section>
  );
}

function DraftHistory({ draft }: { draft: ArticleDraft }) {
  return (
    <section className="card">
      <div className="section-label">History ({draft.revisions.length})</div>
      <ol className="draft-history">
        {draft.revisions.map((revision, index) => (
          <li key={`${revision.at}-${index}`}>
            {REASON_LABEL[revision.reason] ?? revision.reason}
            {revision.model ? ` by ${revision.model}` : ""} · {new Date(revision.at).toLocaleString()}
            {index === draft.revisions.length - 1 && <span className="draft-metadata-note"> (current)</span>}
          </li>
        ))}
      </ol>
      {draft.instructions && (
        <p className="claims-note">
          <strong>Indications:</strong> {draft.instructions}
        </p>
      )}
    </section>
  );
}
