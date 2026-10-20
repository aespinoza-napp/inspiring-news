import Link from "next/link";
import { VerdictLine } from "@/components/reader/ReaderVerdict";
import { ReaderCard as Card } from "@/lib/reader";
import { ReaderLang, dateIn, languageNameIn, readerText, topicName, withLang } from "@/lib/readerText";

/** One published article in the feed. The whole card is the link. */
export function ReaderCard({ article, lang }: { article: Card; lang: ReaderLang }) {
  const t = readerText(lang);
  const published = dateIn(t, article.publishedAt);

  return (
    <article className="card reader-card">
      <p className="reader-byline">
        <span className="reader-source-name">{article.source.name}</span>
        {published ? (
          <time dateTime={article.publishedAt ?? undefined}>{published}</time>
        ) : (
          <span>{t.checkedOn(dateIn(t, article.checkedAt) ?? "–")}</span>
        )}
        <span>{languageNameIn(t, article.language)}</span>
        {article.topic && <span className="reader-topic">{topicName(t, article.topic)}</span>}
      </p>

      {/* The headline is the publisher's, in the article's own language. */}
      <h2 className="reader-card-headline" lang={article.language ?? undefined}>
        <Link href={withLang(`/reader/${article.id}`, lang)}>{article.headline}</Link>
      </h2>

      {!article.titleExtracted && <UntitledNote lang={lang} />}

      {article.excerpt && (
        <p className="reader-excerpt" lang={article.language ?? undefined}>
          {article.excerpt}
        </p>
      )}

      <VerdictLine summary={article.verdict} lang={lang} />
    </article>
  );
}

/**
 * Extraction found no title, so the headline is a stand-in (the link's
 * slug, the lead's first sentence or the domain). Said, so a stand-in is
 * never passed off as the publisher's headline.
 */
export function UntitledNote({ lang }: { lang: ReaderLang }) {
  return <p className="reader-untitled">{readerText(lang).untitled}</p>;
}
