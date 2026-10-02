import Link from "next/link";
import { VerdictLine } from "@/components/reader/ReaderVerdict";
import { ReaderCard as Card, languageName, readableDate } from "@/lib/reader";

/** One published article in the feed. The whole card is the link. */
export function ReaderCard({ article }: { article: Card }) {
  const published = readableDate(article.publishedAt);

  return (
    <article className="card reader-card">
      <p className="reader-byline">
        <span className="reader-source-name">{article.source.name}</span>
        {published ? (
          <time dateTime={article.publishedAt ?? undefined}>{published}</time>
        ) : (
          <span>checked {readableDate(article.checkedAt) ?? "–"}</span>
        )}
        <span>{languageName(article.language)}</span>
        {article.topic && <span className="reader-topic">{article.topic}</span>}
      </p>

      <h2 className="reader-card-headline">
        <Link href={`/reader/${article.id}`}>{article.headline}</Link>
      </h2>

      {!article.titleExtracted && <UntitledNote />}

      {article.excerpt && <p className="reader-excerpt">{article.excerpt}</p>}

      <VerdictLine summary={article.verdict} />
    </article>
  );
}

/**
 * Extraction found no title, so the headline is a stand-in (the link's
 * slug, the lead's first sentence or the domain). Said, so a stand-in is
 * never passed off as the publisher's headline.
 */
export function UntitledNote() {
  return <p className="reader-untitled">No headline was extracted; this one is taken from the link or the text.</p>;
}
