import type { Metadata } from "next";
import Link from "next/link";
import { headers } from "next/headers";
import { LanguageSwitch } from "@/components/reader/LanguageSwitch";
import { VerdictBadge } from "@/components/VerdictBadge";
import { VERDICT_ORDER } from "@/lib/reader";
import { pickLang, preferredLang, readerText, withLang } from "@/lib/readerText";

// Per request: its language comes from the request (?lang=, else
// Accept-Language), so there is nothing to prerender.
export const dynamic = "force-dynamic";

interface Props {
  searchParams: { lang?: string | string[] };
}

function pageLang(searchParams: Props["searchParams"]) {
  const chosen = Array.isArray(searchParams.lang) ? searchParams.lang[0] : searchParams.lang;
  return pickLang(chosen, preferredLang(headers().get("accept-language")));
}

export function generateMetadata({ searchParams }: Props): Metadata {
  return { title: readerText(pageLang(searchParams)).guidePage.title };
}

/**
 * What each verdict means here, why "Not checked" is not UNVERIFIED, how
 * an article's verdict follows from its claims and what a confidence is
 * and is not (roadmap, Phase 6). Every badge on the reader's pages links
 * to its own section (`VerdictBadge`'s `guide`), by the anchors below.
 *
 * Rendered on the server like the story page: a reader without
 * JavaScript, or a search engine, gets the whole text. No accuracy
 * figure yet, on purpose: the set it would come from is still mostly the
 * AI pass's labels (docs/roadmap.md, Thesis priorities P0.2).
 */
export default function GuidePage({ searchParams }: Props) {
  const lang = pageLang(searchParams);
  const t = readerText(lang);
  const g = t.guidePage;

  return (
    <div lang={lang} className="reader-guide-page">
      <div className="reader-top">
        <p className="reader-back">
          <Link href={withLang("/reader", lang)}>{t.backToFeed}</Link>
        </p>
        <LanguageSwitch lang={lang} hrefFor={(code) => withLang("/reader/guide", code)} />
      </div>

      <h1>{g.title}</h1>
      <p className="subtitle">{g.intro}</p>

      <section className="reader-section" aria-labelledby="guide-verdicts">
        <h2 id="guide-verdicts">{g.verdictsTitle}</h2>
        <dl className="reader-guide-verdicts">
          {/* Best first for reading, unlike the feed's worst-first tally. */}
          {[...VERDICT_ORDER].reverse().map((verdict) => (
            <div key={verdict} id={verdict.toLowerCase()} className="reader-guide-verdict">
              <dt>
                <VerdictBadge verdict={verdict} lang={lang} />
              </dt>
              <dd>{g.verdicts[verdict]}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="reader-section" id="not-checked" aria-labelledby="guide-not-checked">
        <h2 id="guide-not-checked">{g.notCheckedTitle}</h2>
        <p>
          <VerdictBadge verdict={null} lang={lang} /> {g.notChecked}
        </p>
      </section>

      <section className="reader-section" id="article" aria-labelledby="guide-article">
        <h2 id="guide-article">{g.articleTitle}</h2>
        <p>{g.article}</p>
      </section>

      <section className="reader-section" id="confidence" aria-labelledby="guide-confidence">
        <h2 id="guide-confidence">{g.confidenceTitle}</h2>
        <ul>
          {g.confidence.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      </section>

      <section className="reader-section" id="sources" aria-labelledby="guide-sources">
        <h2 id="guide-sources">{g.sourcesTitle}</h2>
        <p>{g.sources}</p>
      </section>

      <section className="reader-section" id="accuracy" aria-labelledby="guide-accuracy">
        <h2 id="guide-accuracy">{g.accuracyTitle}</h2>
        <p>{g.accuracy}</p>
      </section>
    </div>
  );
}
