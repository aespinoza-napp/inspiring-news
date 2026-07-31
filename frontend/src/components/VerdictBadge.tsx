import { Verdict } from "@/lib/types";

const LABELS: Record<Verdict, string> = {
  TRUE: "True",
  FALSE: "False",
  MISLEADING: "Misleading",
  UNVERIFIED: "Unverified",
};

export function VerdictBadge({ verdict }: { verdict: Verdict | null }) {
  const resolved = verdict ?? "UNVERIFIED";
  const label = verdict ? LABELS[resolved] : "Not checked";

  return (
    <span className={`badge badge-${resolved.toLowerCase()}`}>{label}</span>
  );
}
