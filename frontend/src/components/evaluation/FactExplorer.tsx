"use client";

import { useMemo, useState } from "react";
import { VerdictBadge } from "@/components/VerdictBadge";
import {
  EvaluationFact,
  GROUP_NAMES,
  LABEL_NAMES,
  TIER_NAMES,
  isVerdict,
} from "@/lib/evaluation";
import { safeHref } from "@/lib/graphStyle";

// The labeller writes this prefix into the note of a fact an AI
// assistant labelled; the backend reports it as annotator "ai". Hidden
// from the note itself because the tag beside the fact already says it.
const AI_PREFIX = /^\[AI label:[^\]]*\]\s*/;

function host(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

function matches(fact: EvaluationFact, query: string): boolean {
  if (!query) return true;
  const haystack = [fact.claim, fact.site, fact.claimant, fact.note, fact.topic, fact.id]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return haystack.includes(query.toLowerCase());
}

/**
 * Every labelled fact, filterable. Filters sit in one row above the
 * list and every one of them narrows the same list, so the count says
 * exactly what is on screen.
 */
export function FactExplorer({
  facts,
  labels,
  groups,
}: {
  facts: EvaluationFact[];
  labels: string[];
  groups: string[];
}) {
  const [label, setLabel] = useState("all");
  const [group, setGroup] = useState("all");
  const [language, setLanguage] = useState("all");
  const [annotator, setAnnotator] = useState("all");
  const [query, setQuery] = useState("");

  const languages = useMemo(
    () => Array.from(new Set(facts.map((f) => f.language).filter(Boolean))) as string[],
    [facts]
  );

  // Newest first: the facts just labelled are the ones being checked.
  const shown = useMemo(
    () =>
      facts
        .filter(
          (fact) =>
            (label === "all" || fact.label === label) &&
            (group === "all" || fact.group === group) &&
            (language === "all" || fact.language === language) &&
            (annotator === "all" || fact.annotator === annotator) &&
            matches(fact, query.trim())
        )
        .slice()
        .reverse(),
    [facts, label, group, language, annotator, query]
  );

  return (
    <div className="eval-facts">
      <div className="eval-filters" role="group" aria-label="Filter the facts">
        <label>
          <span className="field-label">Verdict</span>
          <select value={label} onChange={(e) => setLabel(e.target.value)}>
            <option value="all">All</option>
            {labels.map((l) => (
              <option key={l} value={l}>
                {LABEL_NAMES[l] ?? l}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className="field-label">Group</span>
          <select value={group} onChange={(e) => setGroup(e.target.value)}>
            <option value="all">All</option>
            {groups.map((g) => (
              <option key={g} value={g}>
                {GROUP_NAMES[g] ?? g}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className="field-label">Language</span>
          <select value={language} onChange={(e) => setLanguage(e.target.value)}>
            <option value="all">All</option>
            {languages.map((l) => (
              <option key={l} value={l}>
                {l}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className="field-label">Labelled by</span>
          <select value={annotator} onChange={(e) => setAnnotator(e.target.value)}>
            <option value="all">Anyone</option>
            <option value="human">The annotator</option>
            <option value="ai">AI, unchecked</option>
          </select>
        </label>
        <label className="eval-filter-search">
          <span className="field-label">Search</span>
          <input
            type="search"
            value={query}
            placeholder="Claim, outlet, note…"
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
      </div>

      <p className="eval-count" aria-live="polite">
        Showing {shown.length} of {facts.length}
      </p>

      <ul className="eval-fact-list">
        {shown.map((fact) => {
          const article = safeHref(fact.articleUrl);
          const note = fact.note?.replace(AI_PREFIX, "") ?? null;
          return (
            <li key={fact.id} className="eval-fact">
              <div className="eval-fact-head">
                <span className="eval-fact-id">{fact.id}</span>
                {isVerdict(fact.label) ? (
                  <VerdictBadge verdict={fact.label} />
                ) : (
                  <span className="badge badge-not-checked">{fact.label ?? "No label"}</span>
                )}
                {fact.annotator === "ai" && (
                  <span className="eval-tag eval-tag-ai" title="Labelled by an AI assistant; not yet checked by the annotator">
                    AI · unchecked
                  </span>
                )}
                {fact.reviewed && <span className="eval-tag">Re-labelled</span>}
                {fact.onlyOwnSource && <span className="eval-tag">Own source only</span>}
              </div>

              <p className="eval-fact-claim" lang={fact.language ?? undefined}>
                {fact.claim}
              </p>

              <p className="eval-fact-meta">
                {[
                  fact.claimant,
                  article ? null : fact.site,
                  fact.claimDate,
                  fact.topic && `${fact.topic}${fact.group ? ` (${GROUP_NAMES[fact.group] ?? fact.group})` : ""}`,
                  fact.claimType,
                  fact.sourceTier && (TIER_NAMES[fact.sourceTier] ?? fact.sourceTier),
                  fact.language,
                ]
                  .filter(Boolean)
                  .join(" · ")}
                {article && (
                  <>
                    {" · "}
                    <a href={article} target="_blank" rel="noreferrer">
                      {fact.site ?? host(article)}
                    </a>
                  </>
                )}
              </p>

              {(note || fact.evidenceLinks.length > 0) && (
                <details className="eval-fact-detail">
                  <summary>
                    {fact.evidenceLinks.length} evidence link{fact.evidenceLinks.length === 1 ? "" : "s"}
                    {fact.evidenceDate ? ` · newest ${fact.evidenceDate}` : ""}
                    {note ? " · note" : ""}
                  </summary>
                  {note && <p className="eval-fact-note">{note}</p>}
                  {fact.evidenceLinks.length > 0 && (
                    <ul className="eval-links">
                      {fact.evidenceLinks.map((link) => {
                        const href = safeHref(link);
                        return (
                          <li key={link}>
                            {href ? (
                              <a href={href} target="_blank" rel="noreferrer">
                                {host(href)}
                              </a>
                            ) : (
                              link
                            )}
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </details>
              )}
            </li>
          );
        })}
      </ul>

      {shown.length === 0 && <p className="claims-note">No fact matches these filters.</p>}
    </div>
  );
}
