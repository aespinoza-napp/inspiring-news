"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { useEdition } from "@/lib/edition";
import { ArticleDraft, DraftLanguage, LANGUAGES, draftsApi } from "@/lib/drafts";
import { ReaderCard, ReaderFeed, readableDate } from "@/lib/reader";
import styles from "./NewDraftForm.module.css";

// The longest indications the backend accepts (draft_routes.py,
// MAX_INSTRUCTIONS_CHARS). A page of them is plenty.
const MAX_INSTRUCTIONS = 4000;

// The reader's own page size ceiling (GET /reader/articles, limit <= 50):
// the newest published articles, which is where a new draft usually starts.
const RECENT = 50;

const BY_URL = "__url__";

/**
 * Starts a draft from an analysed article: which article, the language
 * and the editor's indications (docs/decisions/writing.md, "Writing").
 *
 * Only an article the reader publishes can be written from, so the
 * choices are the reader's own feed - newest first - with a URL field
 * for anything older. `initialUrl` / `initialArticleId` come from the
 * page's query string: `?url=` from Analyze and Live once an article has
 * passed (they hold its URL, not its reader id), and `?from=<reader id>`
 * from a draft whose writing failed.
 *
 * The backend answers at once with the draft still being written; the
 * draft's own page shows it fill in.
 */
export function NewDraftForm({
  initialUrl,
  initialArticleId,
}: {
  initialUrl?: string | null;
  initialArticleId?: string | null;
}) {
  const router = useRouter();

  const [articles, setArticles] = useState<ReaderCard[] | null>(null);
  const [feedError, setFeedError] = useState<string | null>(null);

  const [choice, setChoice] = useState<string>(initialUrl ? BY_URL : initialArticleId ?? "");
  const [url, setUrl] = useState(initialUrl ?? "");
  const [language, setLanguage] = useState<DraftLanguage>("ca");
  const [instructions, setInstructions] = useState("");

  // The header's edition: the articles offered are its own, and the
  // draft is written in its voice (backend article_writer.newsroom).
  const { edition, ready: editionReady } = useEdition();

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // The headline of a `?from=` article older than the feed's first page.
  const [fromHeadline, setFromHeadline] = useState<string | null>(null);

  useEffect(() => {
    if (!editionReady) return;

    let cancelled = false;

    fetch(`/api/reader/articles?limit=${RECENT}&edition=${edition}`, { cache: "no-store" })
      .then(async (response) => {
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data?.detail ?? data?.error ?? `Request failed (${response.status}).`);
        return data as ReaderFeed;
      })
      .then((feed) => {
        if (cancelled) return;
        setArticles(feed.items);
        // Nothing chosen yet - or an article of the other edition's, from
        // before the switch moved: the newest published article, or the
        // URL field when there is none to choose.
        setChoice((current) => {
          const stale =
            current &&
            current !== BY_URL &&
            current !== initialArticleId &&
            !feed.items.some((item) => item.id === current);
          return (stale ? "" : current) || feed.items[0]?.id || BY_URL;
        });
      })
      .catch((exc) => {
        if (cancelled) return;
        setFeedError(exc instanceof Error ? exc.message : String(exc));
        setChoice((current) => current || BY_URL);
      });

    return () => {
      cancelled = true;
    };
  }, [edition, editionReady, initialArticleId]);

  const fromListed = !!initialArticleId && !!articles?.some((article) => article.id === initialArticleId);

  useEffect(() => {
    if (!initialArticleId || !articles || fromListed) return;

    let cancelled = false;

    fetch(`/api/reader/articles/${initialArticleId}`, { cache: "no-store" })
      .then((response) => (response.ok ? response.json() : null))
      .then((article: ReaderCard | null) => {
        if (!cancelled && article?.headline) setFromHeadline(article.headline);
      })
      .catch(() => undefined);

    return () => {
      cancelled = true;
    };
  }, [initialArticleId, articles, fromListed]);

  const byUrl = choice === BY_URL;
  const chosen = articles?.find((article) => article.id === choice) ?? null;
  const ready = byUrl ? url.trim().length > 0 : choice.length > 0;

  async function submit(event: FormEvent) {
    event.preventDefault();

    if (!ready || submitting) return;

    setSubmitting(true);
    setError(null);

    try {
      const draft = await draftsApi<ArticleDraft>("", {
        method: "POST",
        body: {
          ...(byUrl ? { articleUrl: url.trim() } : { articleId: choice }),
          language,
          instructions,
          edition,
        },
      });

      router.push(`/drafts/${draft.id}`);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
      setSubmitting(false);
    }
  }

  return (
    <form className="card" onSubmit={submit}>
      <h2>Write a new article</h2>
      <p className={`subtitle ${styles.note}`}>
        From an article the newsroom analysed and published: news on the same story from other outlets is found, and the
        article is written from those sources and the fact-checks, citing each. On a CPU this takes minutes.
      </p>

      <label className="field-label" htmlFor="draft-article">
        Analysed article
      </label>
      <select
        id="draft-article"
        className={styles.select}
        value={choice}
        onChange={(event) => setChoice(event.target.value)}
        disabled={submitting}
      >
        {!articles && !feedError && <option value="">Loading the published articles…</option>}
        {initialArticleId && !fromListed && (
          <option value={initialArticleId}>{fromHeadline ?? `The article you came from (${initialArticleId})`}</option>
        )}
        {articles?.map((article) => (
          <option key={article.id} value={article.id}>
            {article.headline} — {article.source.name}
            {article.publishedAt ? ` · ${readableDate(article.publishedAt)}` : ""}
          </option>
        ))}
        <option value={BY_URL}>Another published article, by its URL…</option>
      </select>

      {feedError && (
        <p className="claims-note">Could not list the published articles ({feedError}). Give the article&apos;s URL.</p>
      )}

      {articles && articles.length === 0 && (
        <p className="claims-note">
          Nothing is published yet: an article must be analysed and pass before it can be written from.
        </p>
      )}

      {chosen && (
        <p className={styles.chosen}>
          {[chosen.topic, chosen.language?.toUpperCase(), `${chosen.verdict.claimsChecked} claims checked`]
            .filter(Boolean)
            .join(" · ")}
        </p>
      )}

      {byUrl && (
        <input
          type="text"
          aria-label="Article URL"
          placeholder="https://www.example.com/news/the-analysed-article"
          value={url}
          onChange={(event) => setUrl(event.target.value)}
          disabled={submitting}
        />
      )}

      <span className="field-label" id="draft-language">
        Language
      </span>
      <div className={styles.languages} role="radiogroup" aria-labelledby="draft-language">
        {LANGUAGES.map((entry) => (
          <label key={entry.code} className="checkbox-label">
            <input
              type="radio"
              name="draft-language"
              value={entry.code}
              checked={language === entry.code}
              onChange={() => setLanguage(entry.code)}
              disabled={submitting}
            />
            {entry.label}
          </label>
        ))}
      </div>

      <label className="field-label" htmlFor="draft-instructions">
        Indications for the writer
      </label>
      <textarea
        id="draft-instructions"
        value={instructions}
        maxLength={MAX_INSTRUCTIONS}
        onChange={(event) => setInstructions(event.target.value)}
        placeholder={
          "Angle, length, audience, register. E.g.: 500 words for young readers; lead with what the volunteers did, " +
          "and end with what comes next."
        }
        disabled={submitting}
      />

      <div className="form-row">
        <button type="submit" disabled={!ready || submitting}>
          {submitting && <span className="spinner" aria-hidden="true" />}
          {submitting ? "Starting…" : "Write the article"}
        </button>
        <span className={`subtitle ${styles.hint}`}>
          Only the sources and the fact-checks are used; claims not verified are not stated as fact.
        </span>
      </div>

      {error && (
        <div className="error-banner" role="alert">
          {error}
        </div>
      )}
    </form>
  );
}
