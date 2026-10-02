import { QUERY_KIND_LABELS, Rating } from "@/components/LiveTrace";
import { VerdictBadge } from "@/components/VerdictBadge";
import { safeHref } from "@/lib/graphStyle";
import {
  ClaimOutcome,
  NOT_JUDGED,
  ReaderClaim as Claim,
  ReaderSource,
  VERDICT_WORDS,
  percent,
  plural,
  readableDate,
} from "@/lib/reader";
import { EvidenceStance } from "@/lib/types";

/**
 * What each way a check can end means, said to a reader. The three
 * failures say plainly that nothing was judged: in the record they are
 * UNVERIFIED like a real one, and drawn as one they would present our
 * outage as a finding about the claim.
 */
const OUTCOME_TEXT: Record<ClaimOutcome, string> = {
  judged: "",
  ungrounded:
    "The model gave an answer but could not point to a source that bears it out, so the claim stands as unverified.",
  no_evidence:
    "Searched for, and nothing that addresses this claim came back. Unverified here means looked for and not found.",
  search_unavailable:
    "Not checked: the web search failed, so nothing was looked at. This is not a verdict on the claim.",
  llm_unreachable:
    "Not checked: the model could not be reached. The sources found are listed below, but nobody weighed them.",
  // The record cannot tell these two apart: the pipeline wrote the same
  // explanation for both before `llm_unreachable` existed.
  no_answer:
    "Not checked: the model was unavailable or gave no usable answer. The sources found are listed below, but nobody weighed them.",
};

const STANCE_TEXT: Record<EvidenceStance, string> = {
  supports: "supports the claim",
  contradicts: "contradicts the claim",
  unrelated: "judged unrelated",
};

/** One checked claim: its verdict, how the check ended, and the sources it rests on. */
export function ReaderClaim({ claim, number }: { claim: Claim; number: number }) {
  const failed = NOT_JUDGED.includes(claim.outcome);
  const cited = claim.sources.filter((source) => source.cited).length;

  return (
    <li
      className={`reader-claim ${
        failed ? "claim-verdict-none reader-claim-failed" : `claim-verdict-${claim.verdict.toLowerCase()}`
      }`}
    >
      <div className="reader-claim-head">
        <p className="reader-claim-text">
          <span className="reader-claim-number">{number}.</span> {claim.text}
        </p>
        <span className="reader-claim-verdict">
          <VerdictBadge verdict={failed ? null : claim.verdict} />
          {/* Only a judgement has a confidence; a forced UNVERIFIED's is 0 and says nothing. */}
          {claim.outcome === "judged" && claim.confidence !== null && (
            <span>{percent(claim.confidence)} confident</span>
          )}
        </span>
      </div>

      {OUTCOME_TEXT[claim.outcome] && (
        <p className={`reader-outcome${failed ? " reader-outcome-failed" : ""}`}>
          {OUTCOME_TEXT[claim.outcome]}
        </p>
      )}

      {/* The model's own reasoning - only where the model actually judged. */}
      {(claim.outcome === "judged" || claim.outcome === "ungrounded") && claim.explanation && (
        <p className="reader-explanation">{claim.explanation}</p>
      )}

      {claim.modelVerdict && !failed && (
        <p className="reader-fine">
          The model itself answered <strong>{VERDICT_WORDS[claim.modelVerdict]}</strong>
          {overrideReason(claim.note) ? `; it was changed because ${overrideReason(claim.note)}.` : "."}
        </p>
      )}

      {claim.searchUnavailable && claim.outcome === "judged" && (
        <p className="reader-fine reader-note-warn">
          The web search failed for this claim; the verdict rests only on articles this site had
          already checked.
        </p>
      )}

      {/* Stances are the model's reading of each source: where it never
          weighed them, there is no agreement to report. */}
      {!failed && (claim.agreements.length > 0 || claim.discrepancies.length > 0) && (
        <div className="comparison-block">
          {claim.agreements.length > 0 && (
            <Comparison title="Where the sources agree" items={claim.agreements} kind="agreements" />
          )}
          {claim.discrepancies.length > 0 && (
            <Comparison title="Where they differ" items={claim.discrepancies} kind="discrepancies" />
          )}
        </div>
      )}

      {claim.sources.length > 0 && (
        <div className="trace-block">
          <p className="trace-label">
            {plural(claim.sources.length, "source")}
            {failed ? " found" : ` weighed, ${cited} cited by the model`}
            {claim.independentDomains > 0 &&
              ` · ${plural(claim.independentDomains, "independent site")}`}
          </p>
          <ul className="trace-sources">
            {claim.sources.map((source, index) => (
              <SourceRow key={`${source.url}-${index}`} source={source} judged={!failed} />
            ))}
          </ul>
        </div>
      )}

      {claim.notUsedTotal > 0 && (
        <details className="trace-block reader-not-used">
          <summary className="trace-label">
            {plural(claim.notUsedTotal, "more page")} found and set aside
          </summary>
          <ul className="trace-rejected">
            {claim.notUsed.map((item, index) => (
              <li key={`${item.url}-${index}`} className="trace-source">
                <SourceLink url={item.url} title={item.title} />
                <span className="trace-muted">{item.reason}</span>
              </li>
            ))}
          </ul>
          {claim.notUsedTotal > claim.notUsed.length && (
            <p className="reader-fine">and {claim.notUsedTotal - claim.notUsed.length} more.</p>
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
function SourceRow({ source, judged }: { source: ReaderSource; judged: boolean }) {
  const published = readableDate(source.publishedAt);

  return (
    <li className="trace-source trace-source-rated reader-source">
      <span className="trace-source-title">
        <strong>{source.domain}</strong>
        <SourceLink url={source.url} title={source.title} />
      </span>

      <span className="trace-source-meta">
        {judged &&
          (source.cited ? (
            <span className="trace-tag trace-tag-ok">cited by the model</span>
          ) : (
            <span className="trace-tag">not cited</span>
          ))}
        {judged && source.stance && (
          <span className={`stance-chip stance-${source.stance}`}>{STANCE_TEXT[source.stance]}</span>
        )}
        {source.origin === "internal" && <span className="trace-tag">an article checked here before</span>}
        {published && <span className="trace-muted">{published}</span>}
      </span>

      {source.quote ? (
        <blockquote className="source-quote">{source.quote}</blockquote>
      ) : (
        source.snippet && <p className="reader-snippet">{source.snippet}</p>
      )}

      <div className="trace-ratings" aria-label="Why this source was trusted">
        <Rating
          label="Site reliability"
          value={source.reliabilityKnown ? source.scores.reliability : null}
          note={source.reliabilityKnown ? percent(source.scores.reliability) : "unrated"}
        />
        <Rating label="Addresses the claim" value={source.scores.pertinence} />
        <Rating label="Relevance" value={source.scores.relevance} strong />
        <Rating label="Wording match" value={source.scores.semantic} />
        <Rating label="Claim terms" value={source.scores.lexical} />
        <Rating label="Recency" value={source.scores.recency} />
      </div>

      <p className="trace-muted trace-fine reader-source-why">
        {source.reliabilityKnown
          ? `A site with a reliability rating of ${percent(source.scores.reliability)}.`
          : `Nobody has rated this site; ranking assumed ${percent(source.scores.reliability)}.`}
        {source.foundBy.length > 0 &&
          ` Found by the search for ${source.foundBy.map((kind) => QUERY_KIND_LABELS[kind] ?? kind).join(" and ")}.`}
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
