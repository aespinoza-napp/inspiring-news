import { VerdictBadge } from "@/components/VerdictBadge";
import {
  ReaderVerdictSummary,
  badgeVerdict,
  notJudgedReasons,
  percent,
  plural,
  tally,
} from "@/lib/reader";

/**
 * The verdict as a feed card shows it: the badge, then how the judged
 * claims came out, then - apart, never folded into the tally - how many
 * we failed to check. "Unverified" next to "2 true · 1 not checked" says
 * what the badge alone hides: the article verdict is worst-claim-wins.
 */
export function VerdictLine({ summary }: { summary: ReaderVerdictSummary }) {
  const judged = tally(summary);

  return (
    <div className="reader-verdict-line">
      <VerdictBadge verdict={badgeVerdict(summary)} />
      {judged && <span>{judged}</span>}
      {/* Nothing judged: the badge already says "Not checked", so say why. */}
      {summary.display === "NOT_CHECKED" && notJudgedReasons(summary) && (
        <span>{capitalise(notJudgedReasons(summary))}</span>
      )}
      {summary.display !== "NOT_CHECKED" && summary.notJudged > 0 && (
        <span className="reader-not-judged" title={notJudgedReasons(summary)}>
          {summary.notJudged} not checked
        </span>
      )}
    </div>
  );
}

/**
 * The article page's verdict panel: what the badge means, sentence by
 * sentence. Each sentence exists because the badge alone misleads in
 * one specific case - an outage read as a finding, one unverified claim
 * outweighing several true ones, a verdict resting on fewer claims than
 * usual.
 */
export function VerdictPanel({ summary }: { summary: ReaderVerdictSummary }) {
  const notChecked = summary.display === "NOT_CHECKED";
  const judged = tally(summary);
  const reasons = notJudgedReasons(summary);

  // The article is UNVERIFIED only because of claims we failed to check:
  // no judged claim is UNVERIFIED, so the failures decided it.
  const unverifiedByFailure =
    !notChecked &&
    summary.overall === "UNVERIFIED" &&
    !summary.counts.UNVERIFIED &&
    summary.notJudged > 0;

  return (
    <section className="card reader-verdict-panel" aria-labelledby="reader-verdict-title">
      <div className="reader-verdict-head">
        <span className="reader-verdict-badge">
          <VerdictBadge verdict={badgeVerdict(summary)} />
        </span>
        {!notChecked && summary.confidence !== null && (
          <span className="reader-confidence">
            confidence {percent(summary.confidence)}
          </span>
        )}
      </div>

      <h2 id="reader-verdict-title" className="reader-verdict-title">
        {notChecked
          ? "None of this article's claims could be checked."
          : `${plural(summary.claimsChecked, "claim")} selected${
              summary.claimsTotal > summary.claimsChecked
                ? ` from ${plural(summary.claimsTotal, "statement")}`
                : ""
            }: ${[judged, summary.notJudged > 0 && `${summary.notJudged} could not be checked`]
              .filter(Boolean)
              .join(", ")}.`}
      </h2>

      <ul className="reader-verdict-notes">
        {notChecked && (
          <li>
            {reasons ? `${capitalise(reasons)}. ` : ""}
            That is a failure on our side, not a finding about the article.
          </li>
        )}

        {!notChecked && summary.notJudged > 0 && (
          <li className="reader-note-warn">
            {summary.notJudged === 1 ? "The one" : `The ${summary.notJudged}`} that could not be
            checked {reasons ? `(${reasons}) ` : ""}
            {summary.notJudged === 1 ? "is" : "are"} not counted as a verdict: that is a failure on
            our side, not a finding about the claim.
            {unverifiedByFailure &&
              " The article reads Unverified because of them alone: no claim that was checked came out unverified."}
          </li>
        )}

        {!notChecked && (
          <li>
            The article takes its weakest claim&apos;s verdict, so one unverified claim outweighs
            any number of true ones. Confidence is the average across its claims.
          </li>
        )}

        {summary.belowAnchorFloor && (
          <li className="reader-note-warn">
            Fewer central claims than usual were found in this article, so the verdict rests on
            less than usual.
          </li>
        )}
      </ul>
    </section>
  );
}

function capitalise(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}
