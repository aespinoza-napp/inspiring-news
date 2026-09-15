/**
 * Fixed-order categorical palette (8 slots), reused everywhere a set of
 * things shown together needs an identity color - topic bars, the
 * quality radar's axes. One shared list so the same slot always means
 * the same hue across every chart on the page, rather than each
 * component picking its own order.
 *
 * Assigned by position (this component's Nth item gets slot N), not by
 * name - there's no stable identity across different articles' topics
 * to color-match against, so position within one render is what's
 * being distinguished, not the topic itself across renders.
 */
export const SERIES_COLORS = [
  "var(--series-1)",
  "var(--series-2)",
  "var(--series-3)",
  "var(--series-4)",
  "var(--series-5)",
  "var(--series-6)",
  "var(--series-7)",
  "var(--series-8)",
] as const;

export function seriesColor(index: number): string {
  return SERIES_COLORS[index % SERIES_COLORS.length];
}
