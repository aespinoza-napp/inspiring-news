"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { LanguageSwitch } from "@/components/reader/LanguageSwitch";
import { UntitledNote } from "@/components/reader/ReaderCard";
import { ReaderClaim } from "@/components/reader/ReaderClaim";
import { VerdictPanel } from "@/components/reader/ReaderVerdict";
import { safeHref } from "@/lib/graphStyle";
import { ReaderArticle } from "@/lib/reader";
import { ReaderLang, ReaderText, dateIn, languageNameIn, readerText, topicName, withLang } from "@/lib/readerText";
import { useReaderLang } from "@/lib/useReaderLang";

type Load =
  | { state: "loading" }
  | { state: "missing" }
  | { state: "error"; message: string | null; status?: number }
  | { state: "ready"; article: ReaderArticle };

export default function ReaderArticlePage({ params }: { params: { id: string } }) {
  const [load, setLoad] = useState<Load>({ state: "loading" });
  // Unless the reader chose one, the page speaks the article's language.
  const [lang, setLang] = useReaderLang(load.state === "ready" ? load.article.language : null);
  const t = readerText(lang);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const response = await fetch(`/api/reader/articles/${encodeURIComponent(params.id)}`, {
          cache: "no-store",
        });
        const data = await response.json();
        if (cancelled) return;

        // 422 is a malformed id: as far as a reader is concerned, the
        // same "no such article" as an unknown one.
        if (response.status === 404 || response.status === 422) {
          setLoad({ state: "missing" });
        } else if (!response.ok) {
          // The backend's own words when it gave some; else ours, worded
          // at render time in the page's language.
          setLoad({
            state: "error",
            message: typeof data.detail === "string" ? data.detail : data.error ?? null,
            status: response.status,
          });
        } else {
          setLoad({ state: "ready", article: data as ReaderArticle });
        }
      } catch (exc) {
        if (!cancelled) setLoad({ state: "error", message: exc instanceof Error ? exc.message : String(exc) });
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [params.id]);

  return (
    <>
      <div className="reader-top">
        <p className="reader-back">
          <Link href={withLang("/reader", lang)}>{t.backToFeed}</Link>
        </p>
        <LanguageSwitch lang={lang} onSelect={setLang} />
      </div>

      {load.state === "loading" && (
        <p className="reader-loading">
          <span className="spinner" aria-hidden="true" /> {t.loadingArticle}
        </p>
      )}

      {load.state === "error" && (
        <div className="error-banner">{load.message ?? t.articleFailed(load.status ?? 0)}</div>
      )}

      {load.state === "missing" && (
        <div className="card reader-empty">
          <h1>{t.missingTitle}</h1>
          <p>{t.missingText}</p>
        </div>
      )}

      {load.state === "ready" && <Article article={load.article} lang={lang} />}
    </>
  );
}

function Article({ article, lang }: { article: ReaderArticle; lang: ReaderLang }) {
  const t = readerText(lang);
  const published = dateIn(t, article.publishedAt);
  const original = safeHref(article.url);
  // The publisher's words keep the article's language whatever the page's.
  const contentLang = article.language ?? undefined;

  return (
    <article className="reader-article">
      <header className="reader-article-head">
        <p className="reader-byline">
          <span className="reader-source-name">{article.source.name}</span>
          {published && <time dateTime={article.publishedAt ?? undefined}>{published}</time>}
          <span>{languageNameIn(t, article.language)}</span>
          {article.topic && <span className="reader-topic">{topicName(t, article.topic)}</span>}
        </p>

        <h1 className="reader-headline" lang={contentLang}>
          {article.headline}
        </h1>
        {!article.titleExtracted && <UntitledNote lang={lang} />}

        {article.author && <p className="reader-author">{t.by(article.author)}</p>}
      </header>

      {article.summary && (
        <section className="reader-lead" aria-label={t.openingLabel}>
          <p lang={contentLang}>{article.summary}</p>
          {original && (
            <p className="reader-fine">
              {t.openingOnly}{" "}
              <a href={original} target="_blank" rel="noopener noreferrer">
                {t.readWhole(article.source.domain)}
              </a>
            </p>
          )}
        </section>
      )}

      <VerdictPanel summary={article.verdict} lang={lang} />

      <section className="reader-section" aria-labelledby="reader-claims-title">
        <h2 id="reader-claims-title" className="section-label">
          {t.claimsTitle}
        </h2>

        {!article.claimsAvailable ? (
          <p className="claims-note">{t.claimsUnavailable}</p>
        ) : article.claims.length === 0 ? (
          <p className="claims-note">{t.noClaims}</p>
        ) : (
          <>
            <p className="reader-guide-link">
              <Link href={withLang("/reader/guide", lang)}>{t.guidePage.title}</Link>
            </p>
            <ReadingGuide t={t} />
            <ol className="reader-claims">
              {article.claims.map((claim, index) => (
                <ReaderClaim
                  key={claim.index}
                  claim={claim}
                  number={index + 1}
                  lang={lang}
                  contentLang={article.language}
                />
              ))}
            </ol>
          </>
        )}
      </section>

      {article.uncheckedTotal > 0 && (
        <details className="reader-section reader-unchecked">
          <summary className="section-label">{t.statementsNotChecked(article.uncheckedTotal)}</summary>
          <p className="reader-fine">{t.notCheckedExplained}</p>
          <ul lang={contentLang}>
            {article.uncheckedClaims.map((text, index) => (
              <li key={index}>{text}</li>
            ))}
          </ul>
          {article.uncheckedTotal > article.uncheckedClaims.length && (
            <p className="reader-fine">{t.andMore(article.uncheckedTotal - article.uncheckedClaims.length)}</p>
          )}
        </details>
      )}

      {(article.topics.length > 0 || article.keywords.length > 0) && (
        <section className="reader-section" aria-label={t.topicsAndKeywords}>
          <div className="chip-row">
            {article.topics.map((topic) =>
              topic.topic ? (
                <span key={topic.topic} className="chip">
                  {topicName(t, topic.topic)}
                </span>
              ) : null
            )}
            {article.keywords.map((keyword) => (
              <span key={keyword} className="chip reader-keyword" lang={contentLang}>
                {keyword}
              </span>
            ))}
          </div>
        </section>
      )}

      <footer className="reader-provenance">
        {t.provenance(dateIn(t, article.checkedAt), article.checkedWith.model, article.checkedWith.pipelineVersion)}
      </footer>
    </article>
  );
}

/** How to read a source's ratings - said once, not under every source. */
function ReadingGuide({ t }: { t: ReaderText }) {
  return (
    <details className="reader-guide">
      <summary>{t.guideTitle}</summary>
      <dl>
        {t.guide.map((entry) => (
          <div key={entry.term}>
            <dt>{entry.term}</dt>
            <dd>{entry.text}</dd>
          </div>
        ))}
      </dl>
    </details>
  );
}
