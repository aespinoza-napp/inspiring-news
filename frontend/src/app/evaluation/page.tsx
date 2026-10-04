"use client";

import { useCallback, useEffect, useState } from "react";
import { DailyBars } from "@/components/DailyBars";
import { BalanceMatrix } from "@/components/evaluation/BalanceMatrix";
import { BarItem, BarList } from "@/components/evaluation/BarList";
import { FactExplorer } from "@/components/evaluation/FactExplorer";
import { RunsPanel } from "@/components/evaluation/RunsPanel";
import { SelectionChart } from "@/components/evaluation/SelectionChart";
import {
  EvaluationSummary,
  LABEL_NAMES,
  SKIP_REASON_NAMES,
  TIER_NAMES,
  percent,
} from "@/lib/evaluation";

const LANGUAGE_NAMES: Record<string, string> = {
  en: "English",
  es: "Spanish",
};

const CLAIM_TYPE_NAMES: Record<string, string> = {
  factual: "Factual",
  numerical: "Numerical",
  interpretive: "Interpretive",
};

const ANNOTATOR_NAMES: Record<string, string> = {
  human: "The annotator",
  ai: "AI, not yet checked",
};

/** Counts as bar rows, in the backend's declared order, with each one's share. */
function bars(counts: Record<string, number>, names: Record<string, string>): BarItem[] {
  const total = Object.values(counts).reduce((sum, n) => sum + n, 0);
  return Object.entries(counts).map(([key, value]) => ({
    key,
    label: names[key] ?? key,
    value,
    note: total ? percent(value / total) : undefined,
  }));
}

function and(names: string[]): string {
  return names.length <= 1
    ? names.join("")
    : `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
}

export default function EvaluationPage() {
  const [summary, setSummary] = useState<EvaluationSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch("/api/evaluation", { cache: "no-store" });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail ?? data.error ?? `Request failed (${response.status})`);
      }
      setSummary(data as EvaluationSummary);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const totals = summary?.totals;
  const selection = summary?.selection;

  // The classes the gold labels do not contain yet. Said in words above
  // the matrix, because it changes what the metrics can mean: macro-F1
  // is averaged over the classes present, so an empty one is not scored.
  const emptyLabels = summary
    ? summary.labels.filter((label) => (totals?.byLabel[label] ?? 0) === 0)
    : [];

  const judged = selection ? selection.labelled + selection.skipped : 0;
  const aiFacts = totals?.byAnnotator.ai ?? 0;

  return (
    <>
      <h1>Evaluation</h1>
      <p className="subtitle">
        What the hand-labelled validation set holds, how often the pipeline&apos;s claim selector
        proposes a claim worth checking, and how each model run scored against the labels. Read
        from <code>backend/data/evaluation/</code> on every refresh.
      </p>

      <div className="eval-toolbar">
        <button type="button" className="eval-refresh" onClick={load} disabled={loading}>
          {loading && <span className="spinner" aria-hidden="true" />}
          {loading ? "Loading…" : "Refresh"}
        </button>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {summary && !summary.found && (
        <div className="eval-empty">
          <p>
            The backend found no <code>data/evaluation/manual/</code> or{" "}
            <code>data/evaluation/queue/</code> folder. Label a fact with{" "}
            <code>python labeller/app.py</code> and refresh.
          </p>
        </div>
      )}

      {summary && totals && selection && summary.found && (
        <>
          <div className="stats-totals">
            <div className="stats-total">
              <div className="stats-total-value">
                {totals.total}
                <span className="eval-total-of"> / {totals.target}</span>
              </div>
              <div className="stats-total-label">Facts labelled</div>
            </div>
            <div className="stats-total">
              <div className={`stats-total-value${aiFacts > 0 ? " stats-warn" : ""}`}>{aiFacts}</div>
              <div className="stats-total-label">Labelled by AI, not yet checked</div>
            </div>
            <div className="stats-total">
              <div className="stats-total-value">{percent(selection.precision)}</div>
              <div className="stats-total-label">
                Selector precision · {selection.labelled} of {judged} claims
              </div>
            </div>
            <div className="stats-total">
              <div className="stats-total-value">{summary.runs.length}</div>
              <div className="stats-total-label">Model runs</div>
            </div>
          </div>

          <div
            className="eval-progress"
            role="img"
            aria-label={`${totals.total} of ${totals.target} facts labelled; ${totals.minimum} is the floor the paper reports on`}
          >
            <div className="eval-progress-track">
              <span
                className="eval-progress-fill"
                style={{ width: `${Math.min(totals.total / totals.target, 1) * 100}%` }}
              />
              <span
                className="eval-progress-mark"
                style={{ left: `${(totals.minimum / totals.target) * 100}%` }}
              />
            </div>
            <div className="eval-progress-scale" aria-hidden="true">
              <span>0</span>
              <span style={{ left: `${(totals.minimum / totals.target) * 100}%` }}>
                {totals.minimum} · floor
              </span>
              <span>{totals.target} · target</span>
            </div>
          </div>

          {(summary.brokenFacts.length > 0 || selection.broken.length > 0) && (
            <div className="error-banner">
              Some files could not be read and are left out:{" "}
              {[...summary.brokenFacts, ...selection.broken]
                .map((b) => `${b.file} (${b.error})`)
                .join("; ")}
            </div>
          )}

          <section className="stats-section">
            <h2>Is the set balanced?</h2>
            <p className="eval-lead">
              The labeller steers toward {totals.perCell} facts in every verdict and topic-group
              cell. A cell still short at {totals.target} is reported short, not padded.
            </p>
            {emptyLabels.length > 0 && (
              <p className="eval-callout">
                No {and(emptyLabels.map((l) => LABEL_NAMES[l] ?? l))} fact yet. Macro-F1 is
                averaged over the classes the gold labels contain, so{" "}
                {emptyLabels.length === 1 ? "this class is" : "these classes are"} not scored
                until one is labelled.
              </p>
            )}
            <BalanceMatrix
              labels={summary.labels}
              groups={Object.keys(summary.groups)}
              matrix={totals.matrix}
              perCell={totals.perCell}
              byLabel={totals.byLabel}
              byGroup={totals.byGroup}
            />
          </section>

          <section className="stats-section">
            <h2>What it is made of</h2>
            <div className="eval-grid">
              <div>
                <p className="section-label">Language</p>
                <BarList items={bars(totals.byLanguage, LANGUAGE_NAMES)} label="Facts per language" unit={["fact", "facts"]} />
              </div>
              <div>
                <p className="section-label">Claim type</p>
                <BarList items={bars(totals.byClaimType, CLAIM_TYPE_NAMES)} label="Facts per claim type" unit={["fact", "facts"]} />
              </div>
              <div>
                <p className="section-label">Evidence tier</p>
                <BarList items={bars(totals.bySourceTier, TIER_NAMES)} label="Facts per source tier" unit={["fact", "facts"]} />
              </div>
              <div>
                <p className="section-label">Labelled by</p>
                <BarList items={bars(totals.byAnnotator, ANNOTATOR_NAMES)} label="Facts per annotator" unit={["fact", "facts"]} />
              </div>
            </div>

            {totals.perDay.length > 0 && (
              <>
                <p className="section-label">Facts labelled per day</p>
                <DailyBars points={totals.perDay} unit={["fact", "facts"]} label="Facts labelled per day" />
              </>
            )}
          </section>

          <section className="stats-section">
            <h2>Does the claim selector pick claims worth checking?</h2>
            <p className="eval-lead">
              Each daily batch proposes the claims the pipeline itself would check. A labelled
              claim was worth checking; a skipped one was not, and the reason says why. Labelled
              over judged is the selector&apos;s precision: a result for the paper, not just
              progress.
            </p>

            {selection.batches.length === 0 ? (
              <p className="claims-note">No daily batch yet. The labeller&apos;s Today tab builds one.</p>
            ) : (
              <>
                <SelectionChart batches={selection.batches} />

                <div className="eval-grid">
                  <div>
                    <p className="section-label">Why claims were skipped</p>
                    <BarList
                      items={bars(selection.byReason, SKIP_REASON_NAMES)}
                      label="Skipped claims per reason"
                      unit={["claim", "claims"]}
                    />
                  </div>
                  <div>
                    <p className="section-label">Precision per language</p>
                    <BarList
                      items={Object.entries(selection.byLanguage).map(([language, counts]) => ({
                        key: language,
                        label: LANGUAGE_NAMES[language] ?? language,
                        value: counts.labelled,
                        note: `of ${counts.labelled + counts.skipped} · ${percent(counts.precision)}`,
                      }))}
                      label="Labelled claims per language, of those judged"
                      unit={["claim", "claims"]}
                    />
                  </div>
                </div>
              </>
            )}
          </section>

          <section className="stats-section">
            <h2>How the models scored</h2>
            <p className="eval-lead">
              The evaluation harness&apos;s reports, newest first. Claims whose search or model
              failed are reported apart by the harness, not counted as wrong answers.
            </p>
            <RunsPanel runs={summary.runs} />
          </section>

          <section className="stats-section">
            <h2>Every fact</h2>
            <FactExplorer facts={summary.facts} labels={summary.labels} groups={Object.keys(summary.groups)} />
          </section>
        </>
      )}
    </>
  );
}
