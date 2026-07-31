import { Verdict } from "@/lib/types";

const LABELS: Record<Verdict, string> = {
  TRUE: "True",
  FALSE: "False",
  MISLEADING: "Misleading",
  UNVERIFIED: "Unverified",
};

export function VerdictBadge({ verdict }: { verdict: Verdict | null }) {
  if (!verdict) {
    // Distinct from an actual "UNVERIFIED" fact-check outcome: this claim
    // was never run through fact-checking at all (article failed
    // validation), so it gets a visually different, outlined treatment
    // rather than the solid gray "checked but unverified" badge.
    return <span className="badge badge-not-checked">Not checked</span>;
  }

  return (
    <span className={`badge badge-${verdict.toLowerCase()}`}>
      {LABELS[verdict]}
    </span>
  );
}
