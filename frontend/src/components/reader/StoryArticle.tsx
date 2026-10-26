import Link from "next/link";
import { ArticleBody } from "@/components/drafts/ArticleBody";
import { VerdictBadge } from "@/components/VerdictBadge";
import { safeHref } from "@/lib/links";
import { percent } from "@/lib/reader";
import { ReaderLang, ReaderText, dateIn, languageNameIn, readerText, topicName, withLang } from "@/lib/readerText";
import { PublishedStory, StoryFactCheck, StorySource, verdictOf } from "@/lib/stories";
import { TikTokVideo } from "./TikTokVideo";
import styles from "./StoryArticle.module.css";

const READER_ID = /^[0-9a-f]{16}$/;

/**
 * A published article, as anyone reads it on /reader/stories/<id>. No
 * hooks and no handlers, so it renders on the server: the page's text is
 * in its HTML. Nothing here acts on the draft - no operator control
 * belongs on a /reader page, which Caddy serves without the password.
 */
export function StoryArticle({ story, lang }: { story: PublishedStory; lang: ReaderLang }) {
  const t = readerText(lang);
  const published = dateIn(t, story.publishedAt);

  return (
    <article className={styles.article}>
      <header>
        <p className="reader-byline">
          <span className="reader-source-name">{t.ourNewsroom}</span>
          <time dateTime={story.publishedAt}>{published}</time>
          <span>{languageNameIn(t, story.language)}</span>
          {story.metadata.topic && <span className="reader-topic">{topicName(t, story.metadata.topic)}</span>}
        </p>

        <h1 className={`reader-headline ${styles.headline}`} lang={story.language}>{story.content.title}</h1>
        {story.content.subtitle && (
          <p className={styles.subtitle} lang={story.language}>
            {story.content.subtitle}
          </p>
        )}
      </header>

      {/* Before the text, not after it: a reader should know what wrote
          it before reading it (docs/decisions/writing.md, "Publishing"). */}
      <aside className={styles.disclosure} aria-label={t.howWritten}>
        <p>{t.disclosure(story.disclosure.aiWritten, story.disclosure.humanEdited, story.disclosure.models)}</p>
        {READER_ID.test(story.sourceArticleId) && (
          <p>
            {t.startsFrom.before}
            <Link href={withLang(`/reader/${story.sourceArticleId}`, lang)}>{t.startsFrom.link}</Link>
            {t.startsFrom.after}
          </p>
        )}
        {story.trend && <p>{t.trendFound(story.trend.name, story.trend.signalName)}</p>}
      </aside>

      <div className={styles.body} lang={story.language}>
        <ArticleBody body={story.content.body} />
      </div>

      {story.trend?.video && <TikTokVideo video={story.trend.video} text={t.video} />}

      {story.sources.length > 0 && <Sources sources={story.sources} t={t} />}

      {story.factChecks.length > 0 && (
        <FactChecks checks={story.factChecks} sources={story.sources} t={t} lang={lang} />
      )}

      {story.metadata.tags.length > 0 && (
        <div className={`chip-row ${styles.tags}`} aria-label={t.tags} lang={story.language}>
          {story.metadata.tags.map((tag) => (
            <span key={tag} className="chip">
              {tag}
            </span>
          ))}
        </div>
      )}

      <footer className={styles.footer}>
        {t.publishedOn(published ?? "")}{" "}
        <Link href={withLang("/reader", lang)}>{t.moreNews}</Link>
      </footer>
    </article>
  );
}

/** Numbered as the body cites them: the n-th is `#source-n`, the target of `[n]`. */
function Sources({ sources, t }: { sources: StorySource[]; t: ReaderText }) {
  return (
    <section className="reader-section" aria-labelledby="story-sources-title">
      <h2 id="story-sources-title" className="section-label">
        {t.sourcesTitle}
      </h2>
      <ol className={styles.sources}>
        {sources.map((source, index) => {
          const href = safeHref(source.url);
          const date = dateIn(t, source.publishedAt);
          const title = source.title || source.domain || source.url;

          return (
            <li key={index} id={`source-${index + 1}`} className={styles.source}>
              {href ? (
                <a href={href} target="_blank" rel="noopener noreferrer">
                  {title}
                </a>
              ) : (
                <span>{title}</span>
              )}
              <span className={styles.sourceMeta}>
                {[source.domain, date, t.origin[source.origin] ?? null].filter(Boolean).join(" · ")}
              </span>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

/**
 * The checks of the analysed article this one rests on. Each points to
 * the sources its verdict used: by number when the article cites the same
 * page, as a link otherwise.
 */
function FactChecks({
  checks,
  sources,
  t,
  lang,
}: {
  checks: StoryFactCheck[];
  sources: StorySource[];
  t: ReaderText;
  lang: ReaderLang;
}) {
  const numberOf = new Map(sources.map((source, index) => [source.url, index + 1]));

  return (
    <section className="reader-section" aria-labelledby="story-checks-title">
      <h2 id="story-checks-title" className="section-label">
        {t.checkedTitle}
      </h2>
      <p className="reader-fine">{t.checkedIntro}</p>
      <ul className={styles.checks}>
        {checks.map((check, index) => (
          <li key={index} className={styles.check}>
            <div className={styles.checkHead}>
              <VerdictBadge verdict={verdictOf(check.verdict)} lang={lang} guide />
              {check.confidence !== null && (
                <span className={styles.confidence}>{t.confidence(percent(check.confidence))}</span>
              )}
            </div>
            <p className={styles.claim}>{check.claim}</p>
            {check.sourceUrls.length > 0 && (
              <p className={styles.checkSources}>
                {t.restsOn}
                {check.sourceUrls.map((url, item) => {
                  const number = numberOf.get(url);
                  const href = safeHref(url);

                  return (
                    <span key={item}>
                      {item > 0 && ", "}
                      {number ? (
                        <a href={`#source-${number}`}>[{number}]</a>
                      ) : href ? (
                        <a href={href} target="_blank" rel="noopener noreferrer">
                          {hostOf(url)}
                        </a>
                      ) : (
                        hostOf(url)
                      )}
                    </span>
                  );
                })}
              </p>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

function hostOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}
