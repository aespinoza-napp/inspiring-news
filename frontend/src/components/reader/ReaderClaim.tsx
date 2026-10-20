import { Rating } from "@/components/LiveTrace";
import { VerdictBadge } from "@/components/VerdictBadge";
import { safeHref } from "@/lib/graphStyle";
import { NOT_JUDGED, ReaderClaim as Claim, ReaderSource, percent } from "@/lib/reader";
import { ReaderLang, ReaderText, dateIn, readerText } from "@/lib/readerText";

/**
 * What each way a check can end means, said to a reader (readerText's
 * `outcome`). The three failures say plainly that nothing was judged: in
 * the record they are UNVERIFIED like a real one, and drawn as one they
 * would present our outage as a finding about the claim. `no_answer` and
 * `llm_unreachable` read alike because the record cannot tell them apart:
 * the pipeline wrote the same explanation for both before
 * `llm_unreachable` existed.
 */
function outcomeText(t: ReaderText, outcome: Claim["outcome"]): string {
  return outcome === "judged" ? "" : t.outcome[outcome];
}

/**
 * One checked claim: its verdict, how the check ended, and the sources it
 * rests on. The claim, the model's explanation and the sources' own words
 * stay in the language they were written in (`lang` on each).
 */
export function ReaderClaim({
  claim,
  number,
  lang,
  contentLang,
}: {
  claim: Claim;
  number: number;
  lang: ReaderLang;
  contentLang: string | null;
}) {
  const t = readerText(lang);
  const failed = NOT_JUDGED.includes(claim.outcome);
  const cited = claim.sources.filter((source) => source.cited).length;
  const outcome = outcomeText(t, claim.outcome);

  return (
    <li
      className={`reader-claim ${
        failed ? "claim-verdict-none reader-claim-failed" : `claim-verdict-${claim.verdict.toLowerCase()}`
      }`}
    >
      <div className="reader-claim-head">
        <p className="reader-claim-text">
          <span className="reader-claim-number">{number}.</span>{" "}
          <span lang={contentLang ?? undefined}>{claim.text}</span>
        </p>
        <span className="reader-claim-verdict">
          <VerdictBadge verdict={failed ? null : claim.verdict} lang={lang} guide />
          {/* Only a judgement has a confidence; a forced UNVERIFIED's is 0 and says nothing. */}
          {claim.outcome === "judged" && claim.confidence !== null && (
            <span>{t.confident(percent(claim.confidence))}</span>
          )}
        </span>
      </div>

      {outcome && <p className={`reader-outcome${failed ? " reader-outcome-failed" : ""}`}>{outcome}</p>}

      {/* The model's own reasoning - only where the model actually judged.
          Not marked with a language: the verifier's prompt is English but
          does not say which language to answer in, and it answers in either. */}
      {(claim.outcome === "judged" || claim.outcome === "ungrounded") && claim.explanation && (
        <p className="reader-explanation">{claim.explanation}</p>
      )}

      {claim.modelVerdict && !failed && (
        <p className="reader-fine">
          {t.modelAnswered} <strong>{t.verdict[claim.modelVerdict]}</strong>
          {/* The reason is the pipeline's own note, in English: shown as written. */}
          {overrideReason(claim.note) ? (
            <>
              {t.changedBecause}
              <span lang="en">{overrideReason(claim.note)}</span>.
            </>
          ) : (
            "."
          )}
        </p>
      )}

      {claim.searchUnavailable && claim.outcome === "judged" && (
        <p className="reader-fine reader-note-warn">{t.searchFailedNote}</p>
      )}

      {/* Stances are the model's reading of each source: where it never
          weighed them, there is no agreement to report. */}
      {!failed && (claim.agreements.length > 0 || claim.discrepancies.length > 0) && (
        <div className="comparison-block">
          {claim.agreements.length > 0 && (
            <Comparison title={t.sourcesAgree} items={claim.agreements} kind="agreements" />
          )}
          {claim.discrepancies.length > 0 && (
            <Comparison title={t.sourcesDiffer} items={claim.discrepancies} kind="discrepancies" />
          )}
        </div>
      )}

      {claim.sources.length > 0 && (
        <div className="trace-block">
          <p className="trace-label">
            {t.sourcesLine(claim.sources.length, failed ? null : cited)}
            {claim.independentDomains > 0 && t.independentSites(claim.independentDomains)}
          </p>
          <ul className="trace-sources">
            {claim.sources.map((source, index) => (
              <SourceRow key={`${source.url}-${index}`} source={source} judged={!failed} t={t} />
            ))}
          </ul>
        </div>
      )}

      {claim.notUsedTotal > 0 && (
        <details className="trace-block reader-not-used">
          <summary className="trace-label">{t.setAside(claim.notUsedTotal)}</summary>
          <ul className="trace-rejected">
            {claim.notUsed.map((item, index) => (
              <li key={`${item.url}-${index}`} className="trace-source">
                <SourceLink url={item.url} title={item.title} />
                <span className="trace-muted" lang="en">
                  {item.reason}
                </span>
              </li>
            ))}
          </ul>
          {claim.notUsedTotal > claim.notUsed.length && (
            <p className="reader-fine">{t.andMore(claim.notUsedTotal - claim.notUsed.length)}</p>
          )}
        </details>
      )}
    </li>
  );
}

/**
 * One source and why it was trusted: whether the model relied on it,
 * what it says, the passage it was judged on, and the ratings that put
 * it in front of the model - reliability (ours, or the default an
 * unrated site gets), how well it addresses the claim, and the ranking
 * factors behind its relevance.
 */
function SourceRow({ source, judged, t }: { source: ReaderSource; judged: boolean; t: ReaderText }) {
  const published = dateIn(t, source.publishedAt);

  return (
    <li className="trace-source trace-source-rated reader-source">
      <span className="trace-source-title">
        <strong>{source.domain}</strong>
        <SourceLink url={source.url} title={source.title} />
      </span>

      <span className="trace-source-meta">
        {judged &&
          (source.cited ? (
            <span className="trace-tag trace-tag-ok">{t.citedByModel}</span>
          ) : (
            <span className="trace-tag">{t.notCited}</span>
          ))}
        {judged && source.stance && (
          <span className={`stance-chip stance-${source.stance}`}>{t.stance[source.stance]}</span>
        )}
        {source.origin === "internal" && <span className="trace-tag">{t.checkedHereBefore}</span>}
        {published && <span className="trace-muted">{published}</span>}
      </span>

      {source.quote ? (
        <blockquote className="source-quote">{source.quote}</blockquote>
      ) : (
        source.snippet && <p className="reader-snippet">{source.snippet}</p>
      )}

      <div className="trace-ratings" aria-label={t.whyTrusted}>
        <Rating
          label={t.rating.reliability}
          value={source.reliabilityKnown ? source.scores.reliability : null}
          note={source.reliabilityKnown ? percent(source.scores.reliability) : t.unrated}
        />
        <Rating label={t.rating.pertinence} value={source.scores.pertinence} />
        <Rating label={t.rating.relevance} value={source.scores.relevance} strong />
        <Rating label={t.rating.semantic} value={source.scores.semantic} />
        <Rating label={t.rating.lexical} value={source.scores.lexical} />
        <Rating label={t.rating.recency} value={source.scores.recency} />
      </div>

      <p className="trace-muted trace-fine reader-source-why">
        {source.reliabilityKnown
          ? t.ratedSite(percent(source.scores.reliability))
          : t.unratedSite(percent(source.scores.reliability))}
        {source.foundBy.length > 0 &&
          t.foundBySearch(source.foundBy.map((kind) => t.queryKind[kind] ?? kind).join(t.and))}
      </p>
    </li>
  );
}

/**
 * The why of a guardrail override, out of the operator's note
 * ("LLM verdict TRUE recalibrated to PARTIALLY_TRUE: a cited source
 * contradicts part of it." - FactChecker._trace). Null for any other
 * note: an unrecognised one is not shown to a reader at all.
 */
function overrideReason(note: string | null): string | null {
  const match = note?.match(/recalibrated to [A-Z_]+: (.+?)\.?$/);
  return match ? match[1] : null;
}

/** Source URLs came from web search: only http(s) becomes a link. */
function SourceLink({ url, title }: { url: string; title: string }) {
  const href = safeHref(url);

  return href ? (
    <a href={href} target="_blank" rel="noopener noreferrer">
      {title || url}
    </a>
  ) : (
    <span>{title || url}</span>
  );
}

function Comparison({
  title,
  items,
  kind,
}: {
  title: string;
  items: string[];
  kind: "agreements" | "discrepancies";
}) {
  return (
    <div className={`comparison-${kind}`}>
      <p className="comparison-group-title">{title}</p>
      <ul className="comparison-list">
        {items.map((item, index) => (
          <li key={index}>{item}</li>
        ))}
      </ul>
    </div>
  );
}
