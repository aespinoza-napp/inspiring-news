import { VerdictBadge } from "@/components/VerdictBadge";
import { ReaderVerdictSummary, badgeVerdict, notJudgedReasons, percent, tally } from "@/lib/reader";
import { ReaderLang, readerText } from "@/lib/readerText";

/**
 * The verdict as a feed card shows it: the badge, then how the judged
 * claims came out, then - apart, never folded into the tally - how many
 * we failed to check. "Unverified" next to "2 true · 1 not checked" says
 * what the badge alone hides: the article verdict is worst-claim-wins.
 */
export function VerdictLine({ summary, lang }: { summary: ReaderVerdictSummary; lang: ReaderLang }) {
  const t = readerText(lang);
  const judged = tally(summary, t);
  const reasons = notJudgedReasons(summary, t);

  return (
    <div className="reader-verdict-line">
      <VerdictBadge verdict={badgeVerdict(summary)} lang={lang} guide />
      {judged && <span>{judged}</span>}
      {/* Nothing judged: the badge already says "Not checked", so say why. */}
      {summary.display === "NOT_CHECKED" && reasons && <span>{capitalise(reasons)}</span>}
      {summary.display !== "NOT_CHECKED" && summary.notJudged > 0 && (
        <span className="reader-not-judged" title={reasons}>
          {t.notCheckedCount(summary.notJudged)}
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
export function VerdictPanel({ summary, lang }: { summary: ReaderVerdictSummary; lang: ReaderLang }) {
  const t = readerText(lang);
  const notChecked = summary.display === "NOT_CHECKED";
  const judged = tally(summary, t);
  const reasons = notJudgedReasons(summary, t);

  // The article is UNVERIFIED only because of claims we failed to check:
  // no judged claim is UNVERIFIED, so the failures decided it.
  const unverifiedByFailure =
    !notChecked &&
    summary.overall === "UNVERIFIED" &&
    !summary.counts.UNVERIFIED &&
    summary.notJudged > 0;

  const parts = [judged, summary.notJudged > 0 ? t.couldNotBeChecked(summary.notJudged) : ""].filter(Boolean);

  return (
    <section className="card reader-verdict-panel" aria-labelledby="reader-verdict-title">
      <div className="reader-verdict-head">
        <span className="reader-verdict-badge">
          <VerdictBadge verdict={badgeVerdict(summary)} lang={lang} guide />
        </span>
        {!notChecked && summary.confidence !== null && (
          <span className="reader-confidence">{t.confidence(percent(summary.confidence))}</span>
        )}
      </div>

      <h2 id="reader-verdict-title" className="reader-verdict-title">
        {notChecked ? t.noneCouldBeChecked : t.claimsSelected(summary.claimsChecked, summary.claimsTotal, parts)}
      </h2>

      <ul className="reader-verdict-notes">
        {notChecked && (
          <li>
            {reasons ? `${capitalise(reasons)}. ` : ""}
            {t.ourFailureArticle}
          </li>
        )}

        {!notChecked && summary.notJudged > 0 && (
          <li className="reader-note-warn">
            {t.notCountedAsVerdict(summary.notJudged, reasons)}
            {unverifiedByFailure && t.unverifiedByFailure(summary.notJudged)}
          </li>
        )}

        {!notChecked && <li>{t.weakestClaim}</li>}

        {summary.belowAnchorFloor && <li className="reader-note-warn">{t.belowAnchorFloor}</li>}
      </ul>
    </section>
  );
}

function capitalise(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}
