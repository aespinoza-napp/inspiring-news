"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { UntitledNote } from "@/components/reader/ReaderCard";
import { ReaderClaim } from "@/components/reader/ReaderClaim";
import { VerdictPanel } from "@/components/reader/ReaderVerdict";
import { safeHref } from "@/lib/graphStyle";
import { ReaderArticle, languageName, plural, readableDate } from "@/lib/reader";

type Load =
  | { state: "loading" }
  | { state: "missing" }
  | { state: "error"; message: string }
  | { state: "ready"; article: ReaderArticle };

export default function ReaderArticlePage({ params }: { params: { id: string } }) {
  const [load, setLoad] = useState<Load>({ state: "loading" });

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
          setLoad({
            state: "error",
            message:
              typeof data.detail === "string"
                ? data.detail
                : data.error ?? `Loading the article failed (${response.status}).`,
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
      <p className="reader-back">
        <Link href="/reader">← Checked articles</Link>
      </p>

      {load.state === "loading" && (
        <p className="reader-loading">
          <span className="spinner" aria-hidden="true" /> Loading the article…
        </p>
      )}

      {load.state === "error" && <div className="error-banner">{load.message}</div>}

      {load.state === "missing" && (
        <div className="card reader-empty">
          <h1>No published article here</h1>
          <p>
            Either nothing was published under this link, or the article has been withdrawn:
            when an article is checked again its newest check decides, and one judged false or
            misleading leaves the reader.
          </p>
        </div>
      )}

      {load.state === "ready" && <Article article={load.article} />}
    </>
  );
}

function Article({ article }: { article: ReaderArticle }) {
  const published = readableDate(article.publishedAt);
  const original = safeHref(article.url);

  return (
    <article className="reader-article">
      <header className="reader-article-head">
        <p className="reader-byline">
          <span className="reader-source-name">{article.source.name}</span>
          {published && <time dateTime={article.publishedAt ?? undefined}>{published}</time>}
          <span>{languageName(article.language)}</span>
          {article.topic && <span className="reader-topic">{article.topic}</span>}
        </p>

        <h1 className="reader-headline">{article.headline}</h1>
        {!article.titleExtracted && <UntitledNote />}

        {article.author && <p className="reader-author">By {article.author}</p>}
      </header>

      {article.summary && (
        <section className="reader-lead" aria-label="Opening of the article">
          <p>{article.summary}</p>
          {original && (
            <p className="reader-fine">
              Only the opening is shown here.{" "}
              <a href={original} target="_blank" rel="noopener noreferrer">
                Read the whole article on {article.source.domain}
              </a>
            </p>
          )}
        </section>
      )}

      <VerdictPanel summary={article.verdict} />

      <section className="reader-section" aria-labelledby="reader-claims-title">
        <h2 id="reader-claims-title" className="section-label">
          The claims, one by one
        </h2>

        {!article.claimsAvailable ? (
          <p className="claims-note">
            The record holding this article&apos;s claims and their sources could not be read, so
            only the overall verdict is known.
          </p>
        ) : article.claims.length === 0 ? (
          <p className="claims-note">No claim of this article was checked.</p>
        ) : (
          <>
            <ReadingGuide />
            <ol className="reader-claims">
              {article.claims.map((claim, index) => (
                <ReaderClaim key={claim.index} claim={claim} number={index + 1} />
              ))}
            </ol>
          </>
        )}
      </section>

      {article.uncheckedTotal > 0 && (
        <details className="reader-section reader-unchecked">
          <summary className="section-label">
            {plural(article.uncheckedTotal, "statement")} not checked
          </summary>
          <p className="reader-fine">
            Only the statements an article&apos;s credibility rests on are checked. These were
            left out; they are listed, not judged.
          </p>
          <ul>
            {article.uncheckedClaims.map((text, index) => (
              <li key={index}>{text}</li>
            ))}
          </ul>
          {article.uncheckedTotal > article.uncheckedClaims.length && (
            <p className="reader-fine">
              and {article.uncheckedTotal - article.uncheckedClaims.length} more.
            </p>
          )}
        </details>
      )}

      {(article.topics.length > 0 || article.keywords.length > 0) && (
        <section className="reader-section" aria-label="Topics and keywords">
          <div className="chip-row">
            {article.topics.map((topic) =>
              topic.topic ? (
                <span key={topic.topic} className="chip">
                  {topic.topic}
                </span>
              ) : null
            )}
            {article.keywords.map((keyword) => (
              <span key={keyword} className="chip reader-keyword">
                {keyword}
              </span>
            ))}
          </div>
        </section>
      )}

      <footer className="reader-provenance">
        Checked {readableDate(article.checkedAt) ?? "on an unknown date"}
        {article.checkedWith.model && <> with {article.checkedWith.model}</>}
        {article.checkedWith.pipelineVersion && <>, pipeline {article.checkedWith.pipelineVersion}</>}.
      </footer>
    </article>
  );
}

/** How to read a source's ratings - said once, not under every source. */
function ReadingGuide() {
  return (
    <details className="reader-guide">
      <summary>How to read the sources</summary>
      <dl>
        <div>
          <dt>Site reliability</dt>
          <dd>
            Our rating of the site. Most sites have none; those are marked unrated and ranked with
            a neutral default, not with a rating.
          </dd>
        </div>
        <div>
          <dt>Addresses the claim</dt>
          <dd>
            Whether the page is about this claim at all. Below a floor it is cut before the model
            sees it, however reliable the site.
          </dd>
        </div>
        <div>
          <dt>Relevance</dt>
          <dd>
            What put the source in front of the model: wording match, the claim&apos;s own terms on
            the page, how recent it is, and the site&apos;s reliability, combined.
          </dd>
        </div>
        <div>
          <dt>Cited by the model</dt>
          <dd>
            The verdict rests on the cited sources. A verdict the model could not back with one is
            not kept.
          </dd>
        </div>
      </dl>
    </details>
  );
}
