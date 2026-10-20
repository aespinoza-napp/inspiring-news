import Link from "next/link";
import { ReaderLang, readerText, withLang } from "@/lib/readerText";
import { Verdict } from "@/lib/types";

/**
 * A verdict as a coloured badge. `lang` is the reader's page language;
 * the operator pages leave it out and read English. The names come from
 * lib/readerText.ts, so the reader and the newsroom never name a verdict
 * two ways.
 *
 * `guide` makes the badge a link to what it means on /reader/guide, in
 * the same language - every badge a reader sees, so a verdict is never a
 * bare word (roadmap, Phase 6). The operator pages do not pass it.
 */
export function VerdictBadge({
  verdict,
  lang = "en",
  guide = false,
}: {
  verdict: Verdict | null;
  lang?: ReaderLang;
  guide?: boolean;
}) {
  const t = readerText(lang);

  // Distinct from an actual "UNVERIFIED" fact-check outcome: this claim
  // was never run through fact-checking at all (article failed
  // validation), so it gets a visually different, outlined treatment
  // rather than the solid gray "checked but unverified" badge.
  const label = verdict ? t.verdict[verdict] : t.notChecked;
  const badge = (
    <span className={verdict ? `badge badge-${verdict.toLowerCase()}` : "badge badge-not-checked"}>{label}</span>
  );

  if (!guide) return badge;

  const anchor = verdict ? verdict.toLowerCase() : "not-checked";

  return (
    <Link
      href={`${withLang("/reader/guide", lang)}#${anchor}`}
      className="badge-link"
      aria-label={t.badgeHelp(label)}
      title={t.badgeHelp(label)}
    >
      {badge}
    </Link>
  );
}
