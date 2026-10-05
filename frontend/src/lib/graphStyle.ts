import { GraphNode } from "@/lib/types";
import { safeHref as linkHref } from "@/lib/links";

/**
 * How each node label is drawn on the /graph page, in the schema view and
 * the result canvas alike, so one colour always means one kind of thing.
 * The base labels are backend/src/services/graph/schema.py's NODE_KEYS.
 */

export const BASE_LABELS = [
  "Article",
  "Claim",
  "Verdict",
  "Evidence",
  "Source",
  "Entity",
  "Topic",
] as const;

export type BaseLabel = (typeof BASE_LABELS)[number];

// Fixed slots of the categorical palette (globals.css --series-*), never
// reassigned by index. Verdict nodes take the verdict colours instead.
export const LABEL_COLOR: Record<string, string> = {
  Article: "var(--series-1)",
  Entity: "var(--series-2)",
  Topic: "var(--series-3)",
  Verdict: "var(--series-4)",
  Evidence: "var(--series-5)",
  Source: "var(--series-6)",
  Claim: "var(--series-7)",
};

const VERDICT_COLOR: Record<string, string> = {
  TRUE: "var(--true)",
  PARTIALLY_TRUE: "var(--partially-true)",
  FALSE: "var(--false)",
  MISLEADING: "var(--misleading)",
  UNVERIFIED: "var(--unverified)",
};

export const LABEL_RADIUS: Record<string, number> = {
  Article: 13,
  Claim: 10,
  Verdict: 12,
  Source: 10,
  Evidence: 8,
  Entity: 8,
  Topic: 9,
};

export function primaryLabel(labels: string[]): string {
  for (const label of BASE_LABELS) {
    if (labels.includes(label)) return label;
  }
  return labels[0] ?? "?";
}

/** The entity's type label (:Person, :Country...) if it has one. */
export function secondaryLabels(labels: string[]): string[] {
  const primary = primaryLabel(labels);
  return labels.filter((label) => label !== primary);
}

export function verdictColor(verdict: string | null | undefined): string {
  return (verdict && VERDICT_COLOR[verdict]) || "var(--unverified)";
}

export function nodeColor(node: GraphNode): string {
  const label = primaryLabel(node.labels);
  if (label === "Verdict") return verdictColor(String(node.properties.name ?? ""));
  return LABEL_COLOR[label] ?? "var(--muted)";
}

function shortUrl(url: string): string {
  return url.replace(/^https?:\/\/(www\.)?/, "").replace(/\/$/, "");
}

/** The one line a node is known by. */
export function nodeCaption(node: GraphNode): string {
  const p = node.properties;
  const str = (value: unknown) => (typeof value === "string" && value ? value : null);

  switch (primaryLabel(node.labels)) {
    case "Article":
      return str(p.title) ?? shortUrl(String(p.url ?? ""));
    case "Evidence":
      return str(p.title) ?? shortUrl(String(p.url ?? ""));
    case "Claim":
      return String(p.text ?? p.id ?? "");
    case "Source":
      return str(p.name) ?? String(p.domain ?? "");
    default:
      return String(p.name ?? p.key ?? p.url ?? node.id);
  }
}

export function truncate(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

/** Only http(s) values become links: evidence URLs come from web search (lib/links.ts). */
export function safeHref(value: unknown): string | null {
  return linkHref(value) ?? null;
}
