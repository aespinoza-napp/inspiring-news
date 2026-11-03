"use client";

import Link from "next/link";
import { Fragment, useCallback, useEffect, useState } from "react";
import { VerdictBadge } from "@/components/VerdictBadge";
import { safeHref } from "@/lib/links";
import { ArticleTrace, LakeIntegrity, TraceDiscovery, TraceDraft, TraceJob, TraceRun, short, traceHref, when } from "@/lib/trace";
import { AnalysisJob } from "@/lib/types";
import styles from "./trace.module.css";

/**
 * One article's journey through the newsroom, end to end: which rounds
 * listed it and who chose it, which jobs analysed it, what every run
 * wrote to the lake (and from which parent, with which code and models),
 * whether the reader publishes it, which drafts and stories came from it.
 *
 * Every other page shows one stage. This one answers "where has this
 * article been, and why is it where it is" - and links each stage to the
 * page that shows it in full. Any id a page shows can be pasted: the URL,
 * a job id, a draft or story id, a reader id (backend src/services/trace.py).
 */
export default function TracePage() {
  const [input, setInput] = useState("");
  const [trace, setTrace] = useState<ArticleTrace | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async (q: string) => {
    const query = q.trim();
    if (!query) return;

    // Written to the URL so the trace can be reloaded, bookmarked and
    // linked to from every other page (lib/trace.ts traceHref).
    const url = new URL(window.location.href);
    url.searchParams.set("q", query);
    window.history.replaceState(null, "", url.toString());

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`/api/trace?q=${encodeURIComponent(query)}`, { cache: "no-store" });
      const data = await response.json();

      if (!response.ok) {
        setTrace(null);
        setError(data?.detail ?? data?.error ?? `Request failed (${response.status})`);
        return;
      }

      setTrace(data as ArticleTrace);
    } catch (err) {
      setTrace(null);
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const q = new URLSearchParams(window.location.search).get("q");
    if (q) {
      setInput(q);
      void load(q);
    }
  }, [load]);

  return (
    <>
      <h1>Trace</h1>
      <p className="subtitle">
        Follow one article through every stage: discovered, chosen, analysed,
        stored layer by layer, published, written about. Paste its URL - or any
        id another page shows you: a job id from Live, a draft or story id, a
        reader id.
      </p>

      <form
        className={styles.search}
        onSubmit={(event) => {
          event.preventDefault();
          void load(input);
        }}
      >
        <label className="field-label" htmlFor="trace-q">
          Article URL or id
        </label>
        <div className={styles.searchRow}>
          <input
            id="trace-q"
            type="text"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="https://… or a job / draft / reader id"
            autoComplete="off"
          />
          <button type="submit" disabled={loading || !input.trim()}>
            {loading ? "Tracing…" : "Trace"}
          </button>
        </div>
      </form>

      {error && <div className="error-banner">{error}</div>}

      {!trace && !loading && (
        <>
          <RecentArticles
            onPick={(url) => {
              setInput(url);
              void load(url);
            }}
          />
          <LakeCheck />
        </>
      )}

      {trace && <Journey trace={trace} onRefresh={() => load(input)} />}
    </>
  );
}

// ----------------------------------------------------------------------
// The journey
// ----------------------------------------------------------------------

type StageState = "done" | "partial" | "none";

interface Stage {
  anchor: string;
  label: string;
  state: StageState;
  note: string;
}

function stages(trace: ArticleTrace): Stage[] {
  const queued = trace.discovery.some((round) => round.queued);
  const finished = trace.jobs.filter((job) => job.status === "done").length;
  const served = trace.runs.find((run) => run.outcome);
  const stories = trace.drafts.filter((draft) => draft.storyId);

  return [
    {
      anchor: "discovered",
      label: "Discovered",
      state: trace.discovery.length ? (queued ? "done" : "partial") : "none",
      note: trace.discovery.length
        ? `${trace.discovery.length} round${plural(trace.discovery.length)}${queued ? ", sent on" : ", not chosen"}`
        : "pasted in, not from a round",
    },
    {
      anchor: "analysed",
      label: "Analysed",
      state: trace.jobs.length ? (finished ? "done" : "partial") : trace.runs.length ? "done" : "none",
      note: trace.jobs.length
        ? `${trace.jobs.length} job${plural(trace.jobs.length)}, ${finished} finished`
        : trace.runs.length
        ? "no job on record, runs in the lake"
        : "never analysed",
    },
    {
      anchor: "stored",
      label: "Stored",
      state: served ? "done" : trace.runs.length ? "partial" : "none",
      note: trace.runs.length
        ? `${trace.runs.length} run${plural(trace.runs.length)}, latest reached ${trace.runs[0].reached}`
        : "nothing in the lake",
    },
    {
      anchor: "published",
      label: "Published",
      state: trace.reader?.published ? "done" : served ? "partial" : "none",
      note: trace.reader?.published
        ? "on the reader"
        : served
        ? served.outcome?.publishable
          ? "publishable, not indexed yet"
          : "withheld"
        : "–",
    },
    {
      anchor: "written",
      label: "Written",
      state: stories.length ? "done" : trace.drafts.length ? "partial" : "none",
      note: trace.drafts.length
        ? `${trace.drafts.length} draft${plural(trace.drafts.length)}, ${stories.length} published`
        : "no draft",
    },
  ];
}

function Journey({ trace, onRefresh }: { trace: ArticleTrace; onRefresh: () => void }) {
  const steps = stages(trace);
  const url = trace.url;

  return (
    <>
      <article className={`card ${styles.head}`}>
        <div>
          <h2 className={styles.title}>{trace.title ?? url ?? trace.key}</h2>
          {url && (
            <a className="card-url" href={safeHref(url)} target="_blank" rel="noopener noreferrer">
              {url}
            </a>
          )}
          <p className={styles.keyLine}>
            Article key <code title="sha256 of host + path, the id every stage shares">{trace.key}</code>
            {trace.resolvedFrom !== "url" && <> · found from a {trace.resolvedFrom} id</>}
          </p>
        </div>
        <button type="button" className={styles.refresh} onClick={onRefresh}>
          Refresh
        </button>
      </article>

      <ol className={styles.journey} aria-label="Where this article has been">
        {steps.map((step) => (
          <li key={step.anchor} className={`${styles.step} ${styles[step.state]}`}>
            <a href={`#${step.anchor}`}>
              <span className={styles.dot} aria-hidden="true" />
              <span className={styles.stepLabel}>{step.label}</span>
              <span className={styles.stepNote}>{step.note}</span>
            </a>
          </li>
        ))}
      </ol>

      <Actions trace={trace} />

      <Section id="discovered" title="Discovered" empty={trace.discovery.length === 0}
        emptyText="No Discover round listed this article: it was pasted into Analyze, or the round is older than the last 200.">
        {trace.discovery.map((round) => (
          <RoundRow key={round.roundId} round={round} />
        ))}
      </Section>

      <Section id="analysed" title="Analysed" empty={trace.jobs.length === 0}
        emptyText={trace.runs.length ? "The lake holds runs, but no job record: the journal was cleared, or it ran through POST /analyze." : "No analysis job on record."}>
        {trace.jobs.map((job) => (
          <JobRow key={job.jobId} job={job} />
        ))}
      </Section>

      <Section id="stored" title="Stored, run by run" empty={trace.runs.length === 0}
        emptyText="Nothing in the lake for this article.">
        <p className={styles.hint}>
          Each run writes raw → processed → exploitation, each record naming its
          parent. Newest first.
        </p>
        {trace.runs.map((run, index) => (
          <RunCard key={run.runId} run={run} latest={index === 0} />
        ))}
      </Section>

      <Section id="published" title="Published" empty={!trace.reader}
        emptyText="The reader index could not be read.">
        {trace.reader?.published ? (
          <div className={styles.row}>
            {trace.reader.verdict && <VerdictBadge verdict={trace.reader.verdict.display === "NOT_CHECKED" ? null : trace.reader.verdict.display} />}
            <span>On the public reader{trace.reader.checkedAt ? `, checked ${when(trace.reader.checkedAt)}` : ""}.</span>
            <Link href={`/reader/${trace.reader.id}`}>Open on Reader →</Link>
          </div>
        ) : (
          <p className="trace-muted">
            Not on the reader. {publishedWhyNot(trace.runs[0])}
          </p>
        )}
      </Section>

      <Section id="written" title="Written from it" empty={trace.drafts.length === 0}
        emptyText={trace.reader?.published ? "No draft yet." : "No draft: only a published article can be written from."}>
        {trace.drafts.map((draft) => (
          <DraftRow key={draft.id} draft={draft} />
        ))}
      </Section>
    </>
  );
}

function Actions({ trace }: { trace: ArticleTrace }) {
  const url = trace.url;
  const published = !!trace.reader?.published;

  return (
    <nav className={styles.actions} aria-label="Go on from here">
      {url && <Link href={`/?url=${encodeURIComponent(url)}`}>Analyse again</Link>}
      {url && <Link href={`/enrich?url=${encodeURIComponent(url)}`}>Enrichment only</Link>}
      {url && <Link href={`/graph?tab=related&article=${encodeURIComponent(url)}`}>Related in the graph</Link>}
      {published && <Link href={`/drafts?from=${trace.key}`}>Write an article from it</Link>}
      {published && <Link href={`/reader/${trace.key}`}>Reader page</Link>}
    </nav>
  );
}

function Section({
  id,
  title,
  empty,
  emptyText,
  children,
}: {
  id: string;
  title: string;
  empty: boolean;
  emptyText: string;
  children: React.ReactNode;
}) {
  return (
    <section id={id} className={styles.section}>
      <h3 className="section-label">{title}</h3>
      {empty ? <p className="trace-muted">{emptyText}</p> : children}
    </section>
  );
}

function RoundRow({ round }: { round: TraceDiscovery }) {
  const score = round.rank?.score;

  return (
    <div className={`card ${styles.item}`}>
      <div className={styles.row}>
        <strong>Round {when(round.startedAt)}</strong>
        <span className="chip">{round.edition}</span>
        {round.groups?.map((group) => (
          <span key={group} className="chip">
            {group}
          </span>
        ))}
        {round.lens && <span className="chip">lens: {round.lens}</span>}
      </div>
      <p className={styles.detail}>
        Ranked <strong>#{round.place}</strong>
        {typeof score === "number" && <> (score {score.toFixed(2)})</>}
        {!round.shown && " - in the reserve, never shown"}
        {round.source && <> · {round.source}</>}
        {round.sameStoryAs && <> · same story as another outlet&apos;s</>}
      </p>
      {round.ai && (
        <p className={styles.detail}>
          AI {round.ai.picked ? "picked it" : "did not pick it"}
          {round.ai.score !== null && <> at {round.ai.score}</>}
          {round.ai.reason && <>: “{round.ai.reason}”</>}
        </p>
      )}
      <p className={styles.detail}>
        {round.queued ? (
          <>
            Sent to analysis {when(round.queuedAt)} by <strong>{chooser(round.selectedBy)}</strong>
            {round.queueError && <> - failed to queue: {round.queueError}</>}
          </>
        ) : (
          "Not sent to analysis from this round."
        )}
      </p>
      <div className={styles.links}>
        <Link href={`/discover?round=${round.roundId}`}>Open the round →</Link>
        {round.jobId && <Link href={`/live?job=${round.jobId}`}>Its job on Live →</Link>}
      </div>
    </div>
  );
}

function JobRow({ job }: { job: TraceJob }) {
  return (
    <div className={`card ${styles.item} ${styles.row}`}>
      <span className={`live-status live-status-${job.status}`}>{job.status}</span>
      <span>
        {when(job.createdAt)} → {when(job.updatedAt)}
      </span>
      <code title={job.jobId}>{short(job.jobId)}</code>
      <span className="trace-muted">{job.eventCount} events</span>
      {job.error && <span className={styles.bad}>{job.error}</span>}
      <Link className={styles.push} href={`/live?job=${job.jobId}`}>
        Every search and source →
      </Link>
    </div>
  );
}

const LAYERS = ["raw", "processed", "exploitation"] as const;

const LAYER_TEXT: Record<(typeof LAYERS)[number], string> = {
  raw: "what was fetched",
  processed: "enriched + fact-check report",
  exploitation: "what the reader serves",
};

function RunCard({ run, latest }: { run: TraceRun; latest: boolean }) {
  const [open, setOpen] = useState(latest);
  const outcome = run.outcome;
  const models = Object.entries(run.components ?? {});
  const overrides = Object.entries(run.thresholdOverrides ?? {});
  const thresholds = Object.entries(run.thresholds ?? {});

  return (
    <article className={`card ${styles.item}`}>
      <header className={styles.row}>
        <strong>Run {when(run.startedAt)}</strong>
        {latest && <span className="chip">latest</span>}
        {outcome ? (
          <>
            <VerdictBadge verdict={outcome.claimsChecked > 0 ? outcome.verdict : null} />
            <span className={outcome.publishable ? styles.good : styles.bad}>
              {outcome.publishable ? "publishable" : "withheld"}
            </span>
          </>
        ) : (
          <span className="trace-muted">stopped after {run.reached}</span>
        )}
        <button type="button" className={`live-toggle ${styles.push}`} aria-expanded={open} onClick={() => setOpen((value) => !value)}>
          {open ? "Hide lineage" : "Show lineage"}
        </button>
      </header>

      {outcome && (
        <p className={styles.detail}>
          {outcome.validationPassed ? "Admitted" : "Rejected at admission"}
          {outcome.rejectionReasons.length > 0 && <>: {outcome.rejectionReasons.join("; ")}</>}
          {" · "}
          {outcome.claimsChecked}/{outcome.claimsTotal} claims checked · {outcome.citedEvidence} sources cited
          {outcome.primaryTopic && <> · {outcome.primaryTopic}</>}
          {" · "}impact {outcome.impactScore.toFixed(2)}
          {outcome.isDuplicate && " · duplicate"}
        </p>
      )}

      {open && (
        <>
          <ol className={styles.chain} aria-label="Lineage, raw to served">
            {LAYERS.map((layer) => {
              const id = run.layers[layer];
              return (
                <li key={layer} className={id ? styles.linkDone : styles.linkMissing}>
                  <span className={styles.layerName}>{layer}</span>
                  <span className={styles.layerText}>{LAYER_TEXT[layer]}</span>
                  <code title={id ?? "not written"}>{id ? short(id) : "not written"}</code>
                </li>
              );
            })}
          </ol>

          <dl className={styles.facts}>
            <dt>Run</dt>
            <dd><code>{run.runId}</code></dd>
            <dt>Code</dt>
            <dd>
              {run.codeRevision ? <code>{short(run.codeRevision, 10)}</code> : "unknown revision"}
              {run.pipelineVersion && <> · pipeline v{run.pipelineVersion}</>}
            </dd>
            {run.fetch && (
              <>
                <dt>Fetch</dt>
                <dd>
                  {run.fetch.extractor ?? "?"} · {run.fetch.contentLength ?? 0} characters
                  {run.fetch.language && <> · {run.fetch.language}</>} · {when(run.fetch.fetchedAt)}
                </dd>
              </>
            )}
            <dt>Body hash</dt>
            <dd><code title={run.contentHash ?? ""}>{short(run.contentHash, 12)}</code></dd>
            <dt>Models</dt>
            <dd>
              {models.length ? (
                <span className={styles.chips}>
                  {models.map(([role, model]) => (
                    <span key={role} className="chip" title={role}>
                      {role.replace(/_/g, " ")}: {model}
                    </span>
                  ))}
                </span>
              ) : (
                "not recorded"
              )}
            </dd>
            <dt>Overrides</dt>
            <dd>
              {overrides.length ? (
                <span className={styles.chips}>
                  {overrides.map(([name, value]) => (
                    <span key={name} className="chip">
                      {name} = {JSON.stringify(value)}
                    </span>
                  ))}
                </span>
              ) : (
                "none: the profile's defaults"
              )}
            </dd>
          </dl>

          {thresholds.length > 0 && (
            <details className={styles.writes}>
              <summary>All {thresholds.length} thresholds this run used</summary>
              <dl className={styles.facts}>
                {thresholds.map(([name, value]) => (
                  <Fragment key={name}>
                    <dt>{name}</dt>
                    <dd><code>{JSON.stringify(value)}</code></dd>
                  </Fragment>
                ))}
              </dl>
            </details>
          )}

          <details className={styles.writes}>
            <summary>{run.writes.length} write{plural(run.writes.length)} in the manifest</summary>
            <ol>
              {run.writes.map((write, index) => (
                <li key={`${write.recordId}-${index}`}>
                  <span>{when(write.at)}</span> <strong>{write.layer}</strong> <code>{short(write.recordId)}</code>
                  {write.parentLayer && (
                    <span className="trace-muted">
                      {" "}← {write.parentLayer} <code>{short(write.parentRecordId)}</code>
                    </span>
                  )}
                </li>
              ))}
            </ol>
          </details>
        </>
      )}
    </article>
  );
}

function DraftRow({ draft }: { draft: TraceDraft }) {
  return (
    <div className={`card ${styles.item}`}>
      <div className={styles.row}>
        <strong>{draft.title || "Untitled draft"}</strong>
        <span className="chip">{draft.status}</span>
        {draft.busy && <span className="chip">{draft.busy}…</span>}
        <span className="chip">{draft.language}</span>
        <span className="trace-muted">
          {draft.revisions} revision{plural(draft.revisions)} · updated {when(draft.updatedAt)}
        </span>
      </div>
      <div className={styles.links}>
        <Link href={`/drafts/${draft.id}`}>Open the draft →</Link>
        {draft.storyId && <Link href={`/reader/stories/${draft.storyId}`}>The published story →</Link>}
        {draft.published
          .filter((record) => record.channel !== "web" && record.url)
          .map((record) => (
            <a key={`${record.channel}-${record.at}`} href={safeHref(record.url!)} target="_blank" rel="noopener noreferrer">
              On {record.channel} →
            </a>
          ))}
      </div>
    </div>
  );
}

// ----------------------------------------------------------------------
// The whole lake: does its lineage hold together?
// ----------------------------------------------------------------------

/**
 * Asked for, never on load: it opens every record in the lake
 * (backend src/services/lake_integrity.py).
 */
function LakeCheck() {
  const [result, setResult] = useState<LakeIntegrity | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  async function run() {
    setRunning(true);
    setError(null);

    try {
      const response = await fetch("/api/lake/integrity", { cache: "no-store" });
      const data = await response.json();

      if (!response.ok) {
        setError(data?.detail ?? data?.error ?? `Request failed (${response.status})`);
        return;
      }

      setResult(data as LakeIntegrity);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setRunning(false);
    }
  }

  return (
    <section className={styles.section}>
      <h3 className="section-label">The whole lake</h3>
      <p className={styles.hint}>
        Checks every stored record: each parent exists, each body hashes to what its lineage states, and each
        served verdict is its report&apos;s. Changes nothing.
      </p>

      <button type="button" className={`live-toggle ${styles.checkButton}`} disabled={running} onClick={run}>
        {running ? "Checking…" : "Check the lake's integrity"}
      </button>

      {error && <div className="error-banner">{error}</div>}

      {result && (
        <div className={`card ${styles.item}`}>
          <p className={result.ok ? styles.good : styles.bad}>
            {result.ok ? "Holds together" : `${result.errors} error${plural(result.errors)} found`}
            {result.warnings > 0 && `, ${result.warnings} warning${plural(result.warnings)}`}
          </p>
          <p className={styles.detail}>
            {result.runs} run{plural(result.runs)}, {result.runsComplete} through every layer ·{" "}
            {Object.entries(result.records)
              .map(([layer, count]) => `${count} ${layer}`)
              .join(", ")}{" "}
            · {result.manifestEntries} manifest entries
          </p>
          {result.byKind.length > 0 && (
            <ul className={styles.recent}>
              {result.byKind.map((kind) => (
                <li key={kind.kind} className={styles.detail}>
                  <span className={kind.severity === "error" ? styles.bad : "trace-muted"}>{kind.severity}</span>{" "}
                  <code>{kind.kind}</code> × {kind.count}
                </li>
              ))}
            </ul>
          )}
          {result.issues
            .filter((issue) => issue.severity === "error")
            .map((issue, index) => (
              <p key={`${issue.recordId}-${index}`} className={styles.detail}>
                <strong>{issue.kind}</strong>: {issue.detail}
                {issue.url && (
                  <>
                    {" "}
                    <Link href={traceHref(issue.url)}>Trace it →</Link>
                  </>
                )}
              </p>
            ))}
        </div>
      )}
    </section>
  );
}

// ----------------------------------------------------------------------
// Before anything is asked: the articles run recently
// ----------------------------------------------------------------------

function RecentArticles({ onPick }: { onPick: (url: string) => void }) {
  const [jobs, setJobs] = useState<AnalysisJob[] | null>(null);

  useEffect(() => {
    let cancelled = false;

    fetch("/api/jobs", { cache: "no-store" })
      .then((response) => (response.ok ? response.json() : { jobs: [] }))
      .then((data) => {
        if (!cancelled) setJobs((data?.jobs ?? []).filter((job: AnalysisJob) => job.kind !== "claim"));
      })
      .catch(() => {
        if (!cancelled) setJobs([]);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  if (!jobs || jobs.length === 0) return null;

  const seen = new Set<string>();
  const unique = jobs.filter((job) => (seen.has(job.url) ? false : (seen.add(job.url), true)));

  return (
    <section className={styles.section}>
      <h3 className="section-label">Analysed recently</h3>
      <ul className={styles.recent}>
        {unique.slice(0, 12).map((job) => (
          <li key={job.jobId}>
            <button type="button" onClick={() => onPick(job.url)}>
              <span className={`live-status live-status-${job.status}`}>{job.status}</span>
              <span className={styles.recentUrl}>{job.url}</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

// ----------------------------------------------------------------------

function plural(count: number): string {
  return count === 1 ? "" : "s";
}

function chooser(selectedBy: TraceDiscovery["selectedBy"]): string {
  if (selectedBy === "ai") return "the AI, unchanged";
  if (selectedBy === "ai+user") return "the AI, edited by a person";
  if (selectedBy === "user") return "a person";
  return "someone";
}

function publishedWhyNot(run: TraceRun | undefined): string {
  if (!run) return "It was never stored.";
  if (!run.outcome) return `Its latest run stopped after the ${run.reached} layer.`;
  if (!run.outcome.validationPassed) return "Its latest run was rejected at admission.";
  if (!run.outcome.publishable) return `Its latest verdict, ${run.outcome.verdict}, withholds it.`;
  return "Its latest run is publishable; the reader index may not have caught up yet.";
}
