"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { FlowSteps } from "@/components/FlowSteps";
import { safeHref } from "@/lib/links";
import {
  Candidate,
  CandidateRound,
  CandidateRoundSummary,
  IngestSource,
  IngestSourcesResponse,
  ScoredCandidate,
  TopicGroup,
} from "@/lib/types";

const PER_SOURCE_OPTIONS = [1, 2, 3, 5, 10];

// The mission screen's reasons (backend src/services/selection/mission_screen.py OFF_MISSION).
const OFF_MISSION: Record<string, string> = {
  politics: "politics",
  labour: "strike or protest",
  crime: "crime",
  disaster: "accident or disaster",
  conflict: "war or conflict",
  celebrity: "celebrity",
  sport: "sport",
  markets: "markets or personal finance",
  service: "service page",
  obituary: "death or obituary",
};

// While the AI selection runs, the round is re-read this often. On the
// production CPU model a selection is minutes; on a GPU, seconds.
const POLL_MS = 2000;

function errorOf(data: unknown, status: number): string {
  const body = data as { error?: string; detail?: unknown } | null;
  if (body?.error) return body.error;
  if (typeof body?.detail === "string") return body.detail;
  if (Array.isArray(body?.detail)) {
    return body.detail.map((item: { msg?: string }) => item?.msg ?? "").filter(Boolean).join("; ");
  }
  return `Request failed (${status})`;
}

async function call<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { cache: "no-store", ...init });
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new Error(errorOf(data, response.status));
  return data as T;
}

function post<T>(url: string, body: unknown): Promise<T> {
  return call<T>(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

function when(value: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

// The round id lives in the URL, so a reload - or coming back from Live -
// returns to the same candidates and the same AI proposal.
function roundFromUrl(): string | null {
  if (typeof window === "undefined") return null;
  const id = new URLSearchParams(window.location.search).get("round");
  return id && /^[0-9a-f]{16}$/.test(id) ? id : null;
}

function writeRoundToUrl(id: string | null) {
  const url = new URL(window.location.href);
  if (id) url.searchParams.set("round", id);
  else url.searchParams.delete("round");
  window.history.replaceState(null, "", url.toString());
}

export default function DiscoverPage() {
  const [catalogue, setCatalogue] = useState<IngestSourcesResponse | null>(null);
  const [groups, setGroups] = useState<string[]>([]);
  const [excluded, setExcluded] = useState<Set<string>>(new Set());
  const [perSource, setPerSource] = useState(3);

  const [round, setRound] = useState<CandidateRound | null>(null);
  const [chosen, setChosen] = useState<Set<string>>(new Set());
  const [recent, setRecent] = useState<CandidateRoundSummary[]>([]);

  const [busy, setBusy] = useState<"discovering" | "starting-ai" | "queueing" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const maxGroups = catalogue?.maxGroups ?? 3;
  const maxSelected = catalogue?.maxSelected ?? 20;

  const loadRecent = useCallback(async () => {
    try {
      const data = await call<{ rounds: CandidateRoundSummary[] }>("/api/ingest/rounds?limit=8");
      setRecent(data.rounds);
    } catch {
      // The list is a convenience; the page works without it.
    }
  }, []);

  // ------------------------------------------------------------------
  // Load the groups and sources, and a round named in the URL
  // ------------------------------------------------------------------

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const data = await call<IngestSourcesResponse>("/api/ingest/sources");
        if (cancelled) return;
        setCatalogue(data);

        const id = roundFromUrl();
        if (id) {
          const saved = await call<CandidateRound>(`/api/ingest/rounds/${id}`);
          if (cancelled) return;
          setRound(saved);
          setGroups(saved.groups);
          setPerSource(saved.perSource);
          setChosen(new Set(saved.queued?.urls ?? []));
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load the sources.");
      }
    })();

    loadRecent();

    return () => {
      cancelled = true;
    };
  }, [loadRecent]);

  // ------------------------------------------------------------------
  // Poll the round while its AI selection runs
  // ------------------------------------------------------------------

  const aiStatus = round?.aiSelection?.status ?? null;
  const roundId = round?.id ?? null;

  useEffect(() => {
    if (!roundId || aiStatus !== "running") return;

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    async function poll() {
      try {
        const latest = await call<CandidateRound>(`/api/ingest/rounds/${roundId}`);
        if (cancelled) return;
        setRound(latest);

        if (latest.aiSelection?.status === "done") {
          // The proposal arrives ticked; the editor can still change it.
          setChosen(new Set((latest.aiSelection.picks ?? []).map((pick) => pick.url)));
          loadRecent();
          return;
        }

        if (latest.aiSelection?.status !== "running") return;
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Lost track of the AI selection.");
      }

      // Rescheduled only while still mounted (the rule useAnalysisJob
      // keeps: a cleanup racing a poll in flight must not leave a timer).
      if (!cancelled) timer = setTimeout(poll, POLL_MS);
    }

    timer = setTimeout(poll, POLL_MS);

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [roundId, aiStatus, loadRecent]);

  // ------------------------------------------------------------------

  const sources: IngestSource[] = useMemo(
    () =>
      (catalogue?.sources ?? []).filter((source) =>
        source.groups.some((group) => groups.includes(group))
      ),
    [catalogue, groups]
  );

  const included = sources.filter((source) => !excluded.has(source.id));

  const scores = useMemo(() => {
    const byUrl = new Map<string, ScoredCandidate>();
    for (const item of round?.aiSelection?.scored ?? []) byUrl.set(item.url, item);
    return byUrl;
  }, [round]);

  const picks = useMemo(
    () => new Set((round?.aiSelection?.picks ?? []).map((pick) => pick.url)),
    [round]
  );

  // Best AI score first once there are scores; the feed's order before.
  const candidates: Candidate[] = useMemo(() => {
    const list = [...(round?.candidates ?? [])];
    if (scores.size === 0) return list;
    return list.sort((a, b) => (scores.get(b.url)?.score ?? -1) - (scores.get(a.url)?.score ?? -1));
  }, [round, scores]);

  const queued = round?.queued ?? null;
  const locked = queued !== null;

  function toggleGroup(id: string) {
    setGroups((current) =>
      current.includes(id)
        ? current.filter((group) => group !== id)
        : current.length < maxGroups
          ? [...current, id]
          : current
    );
  }

  function toggleSource(id: string) {
    setExcluded((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleCandidate(url: string) {
    if (locked) return;
    setChosen((current) => {
      const next = new Set(current);
      if (next.has(url)) next.delete(url);
      else if (next.size < maxSelected) next.add(url);
      return next;
    });
  }

  async function discover() {
    setBusy("discovering");
    setError(null);
    try {
      const created = await post<CandidateRound>("/api/ingest/rounds", {
        groups,
        sources: included.map((source) => source.id),
        perSource,
      });
      setRound(created);
      setChosen(new Set());
      writeRoundToUrl(created.id);
      loadRecent();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Discovery failed.");
    } finally {
      setBusy(null);
    }
  }

  async function askAI() {
    if (!round) return;
    setBusy("starting-ai");
    setError(null);
    try {
      const state = await post<CandidateRound["aiSelection"]>(
        `/api/ingest/rounds/${round.id}/ai-selection`,
        { limit: maxSelected }
      );
      setRound({ ...round, aiSelection: state });
    } catch (err) {
      setError(err instanceof Error ? err.message : "The AI selection could not start.");
    } finally {
      setBusy(null);
    }
  }

  async function analyse() {
    if (!round) return;
    setBusy("queueing");
    setError(null);
    try {
      // In the candidates' order on screen, so the jobs start in it too.
      const urls = candidates.map((candidate) => candidate.url).filter((url) => chosen.has(url));
      const result = await post<CandidateRound["queued"]>(`/api/ingest/rounds/${round.id}/queue`, { urls });
      setRound({ ...round, queued: result });
      loadRecent();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send the selection to analysis.");
    } finally {
      setBusy(null);
    }
  }

  function startOver() {
    setRound(null);
    setChosen(new Set());
    writeRoundToUrl(null);
  }

  async function reopen(id: string) {
    setError(null);
    try {
      const saved = await call<CandidateRound>(`/api/ingest/rounds/${id}`);
      setRound(saved);
      setGroups(saved.groups);
      setPerSource(saved.perSource);
      setChosen(
        new Set(saved.queued?.urls ?? (saved.aiSelection?.picks ?? []).map((pick) => pick.url))
      );
      writeRoundToUrl(saved.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not reopen that round.");
    }
  }

  const groupName = (id: string) => catalogue?.groups.find((group) => group.id === id)?.name ?? id;

  return (
    <>
      <FlowSteps current="discover" />

      <h1>Discover</h1>
      <p className="subtitle">
        Pick up to {maxGroups} topics: only the sources that cover them are
        read, and only for those topics. Then choose up to {maxSelected} of
        the articles found - yourself, or let the AI propose a selection
        you can change - and send them to analysis.
      </p>

      {error && (
        <div className="error-banner" role="alert">
          {error}
        </div>
      )}

      {/* ---------------- 1 · Topics ---------------- */}

      <section className="card discover-step">
        <div className="section-label">1 · Topics</div>
        {!catalogue && !error && <p className="claims-note">Loading the topics…</p>}
        <div className="topic-groups" role="group" aria-label="Topic groups">
          {(catalogue?.groups ?? []).map((group: TopicGroup) => {
            const on = groups.includes(group.id);
            const full = !on && groups.length >= maxGroups;
            return (
              <button
                type="button"
                key={group.id}
                className={on ? "topic-group is-on" : "topic-group"}
                aria-pressed={on}
                disabled={full || locked || busy !== null}
                onClick={() => toggleGroup(group.id)}
                title={group.topics.map((topic) => topic.name).join(", ")}
              >
                <span className="topic-group-name">{group.name}</span>
                <span className="topic-group-meta">{group.sources} sources</span>
              </button>
            );
          })}
        </div>
        <p className="claims-note">
          {groups.length === 0
            ? `Choose 1 to ${maxGroups}.`
            : `${groups.length} of ${maxGroups} · topics: ` +
              (catalogue?.groups ?? [])
                .filter((group) => groups.includes(group.id))
                .flatMap((group) => group.topics.map((topic) => topic.name))
                .join(", ")}
        </p>
      </section>

      {/* ---------------- 2 · Sources ---------------- */}

      {groups.length > 0 && !round && (
        <section className="card discover-step">
          <div className="section-label">2 · Sources</div>
          <p className="claims-note">
            The sources whose configuration names one of these topics. Untick
            any you do not want read this time. Off-topic sections (sport,
            celebrities, horoscopes, lotteries) are never read.
          </p>
          <div className="ingest-sources">
            {sources.map((source) => (
              <label className="checkbox-label" key={source.id}>
                <input
                  type="checkbox"
                  checked={!excluded.has(source.id)}
                  onChange={() => toggleSource(source.id)}
                />
                {source.name}
                <span className="stats-muted"> {source.language}</span>
              </label>
            ))}
          </div>
          <div className="ingest-controls">
            <label className="ingest-per-source">
              Articles per source
              <select value={perSource} onChange={(event) => setPerSource(Number(event.target.value))}>
                {PER_SOURCE_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </label>
            <button type="button" onClick={discover} disabled={busy !== null || included.length === 0}>
              {busy === "discovering" && <span className="spinner" aria-hidden="true" />}
              {busy === "discovering"
                ? "Reading the feeds…"
                : `Find articles in ${included.length} ${included.length === 1 ? "source" : "sources"}`}
            </button>
          </div>
          <p className="claims-note">
            Reads only feeds and section pages: nothing is fetched or
            analysed until you send a selection.
          </p>
        </section>
      )}

      {/* ---------------- 3 · Choose ---------------- */}

      {round && (
        <section className="card discover-step">
          <div className="section-label">3 · Choose up to {maxSelected}</div>
          <p className="claims-note">
            {round.totals.candidates} new articles from {round.totals.sources} sources in{" "}
            {round.groups.map(groupName).join(", ")} · {round.totals.alreadyStored} already analysed ·{" "}
            {round.totals.deferred} more left for another round
            {(round.totals.stale ?? 0) > 0 && ` · ${round.totals.stale} older than a month`}
            {round.totals.failed > 0 && ` · ${round.totals.failed} sources found nothing`}{" "}
            <span className="stats-muted">({when(round.startedAt)})</span>
          </p>

          {round.screen?.status === "unavailable" && (
            <p className="claims-note">
              The mission screen could not run ({round.screen.error}), so nothing was left out
              for being off-mission: elections, crime or celebrity pieces may be in this list.
            </p>
          )}

          {round.screened && round.screened.length > 0 && (
            <details className="claims-note">
              <summary>
                {round.screened.length} left out as off-mission (elections, strikes, crime,
                accidents, markets, obituaries…) before choosing
              </summary>
              <ul className="screened-list">
                {round.screened.map((item) => {
                  const href = safeHref(item.url);
                  return (
                    <li key={item.url}>
                      {href ? (
                        <a href={href} target="_blank" rel="noopener noreferrer">
                          {item.title ?? item.url}
                        </a>
                      ) : (
                        item.title ?? item.url
                      )}{" "}
                      <span className="stats-muted">
                        · {item.sourceName} · {OFF_MISSION[item.offMission] ?? item.offMission}
                      </span>
                    </li>
                  );
                })}
              </ul>
            </details>
          )}

          {!locked && round.candidates.length > 0 && (
            <div className="discover-toolbar">
              <button
                type="button"
                className="button-secondary"
                onClick={askAI}
                disabled={busy !== null || aiStatus === "running"}
              >
                {(busy === "starting-ai" || aiStatus === "running") && (
                  <span className="spinner" aria-hidden="true" />
                )}
                {aiStatus === "running"
                  ? "The AI is reading the list…"
                  : aiStatus === "done"
                    ? "Ask the AI again"
                    : "Let the AI choose"}
              </button>
              <span className="discover-count" aria-live="polite">
                {chosen.size} / {maxSelected} chosen
              </span>
              {chosen.size > 0 && (
                <button type="button" className="button-link" onClick={() => setChosen(new Set())}>
                  Clear
                </button>
              )}
            </div>
          )}

          {round.aiSelection?.status === "done" && (
            <p className="claims-note">
              The AI proposed {round.aiSelection.picks?.length ?? 0} of{" "}
              {round.candidates.length}, scoring each from its title and summary
              against the publication&apos;s idea of positive impact ({round.aiSelection.model},{" "}
              {round.aiSelection.calls} {round.aiSelection.calls === 1 ? "call" : "calls"},{" "}
              {Math.round((round.aiSelection.elapsedMs ?? 0) / 1000)} s). Its picks are ticked;
              change them freely.
              {(round.aiSelection.notes ?? []).map((note) => ` ${note}`)}
            </p>
          )}

          {round.aiSelection?.status === "failed" && (
            <div className="error-banner" role="alert">
              The AI selection failed: {round.aiSelection.error}
            </div>
          )}

          {round.candidates.length === 0 ? (
            <p className="claims-note">
              Nothing new in these sources for these topics. Try another
              topic, more articles per source, or later.
            </p>
          ) : (
            <ul className="candidate-list">
              {candidates.map((candidate) => {
                const scored = scores.get(candidate.url);
                const on = chosen.has(candidate.url);
                const href = safeHref(candidate.url);
                const full = !on && chosen.size >= maxSelected;
                return (
                  <li key={candidate.url} className={on ? "candidate is-chosen" : "candidate"}>
                    <label className="candidate-check">
                      <input
                        type="checkbox"
                        checked={on}
                        disabled={locked || full}
                        onChange={() => toggleCandidate(candidate.url)}
                        aria-label={`Choose: ${candidate.title ?? candidate.url}`}
                      />
                    </label>
                    <div className="candidate-body">
                      <div className="candidate-title">
                        {href ? (
                          <a href={href} target="_blank" rel="noopener noreferrer">
                            {candidate.title ?? candidate.url}
                          </a>
                        ) : (
                          candidate.title ?? candidate.url
                        )}
                        {candidate.titleFrom === "url" && (
                          <span className="stats-muted" title="The feed gave no title; this one is made from the link.">
                            {" "}
                            (from the link)
                          </span>
                        )}
                      </div>
                      <div className="candidate-meta">
                        {candidate.sourceName} · {candidate.language}
                        {candidate.publishedAt && ` · ${when(candidate.publishedAt)}`}
                      </div>
                      {candidate.summary && <p className="candidate-summary">{candidate.summary}</p>}
                      {scored && (
                        <div className="candidate-ai">
                          <span
                            className={picks.has(candidate.url) ? "ai-score is-pick" : "ai-score"}
                            title="The AI's positive-impact score, 0-10"
                          >
                            {scored.score === null ? "not scored" : `AI ${scored.score}/10`}
                          </span>
                          {scored.reason && <span className="candidate-reason">{scored.reason}</span>}
                        </div>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}

          {!locked && (
            <div className="ingest-controls">
              <button type="button" className="button-link" onClick={startOver} disabled={busy !== null}>
                New round
              </button>
              <button type="button" onClick={analyse} disabled={busy !== null || chosen.size === 0}>
                {busy === "queueing" && <span className="spinner" aria-hidden="true" />}
                {`Analyse ${chosen.size} ${chosen.size === 1 ? "article" : "articles"}`}
              </button>
            </div>
          )}
        </section>
      )}

      {/* ---------------- 4 · Analyse ---------------- */}

      {queued && (
        <section className="card discover-step">
          <div className="section-label">4 · Sent to analysis</div>
          <p className="claims-note">
            {queued.jobs.filter((job) => job.jobId).length} of {queued.urls.length} queued{" "}
            <span className="stats-muted">({when(queued.at)})</span>. Chosen{" "}
            {queued.selectedBy === "user"
              ? "by you"
              : queued.selectedBy === "ai"
                ? "by the AI, unchanged"
                : `by the AI and you: ${queued.aiKept} of its ${queued.aiProposed} kept, ${queued.userAdded} added`}
            . Each one is scraped, enriched, admitted or rejected, and its claims checked.
          </p>
          <div className="discover-next">
            <Link href="/live">Follow them on Live →</Link>
            <Link href="/reader">The published ones on Reader →</Link>
            <button type="button" className="button-link" onClick={startOver}>
              Start a new round
            </button>
          </div>
          {queued.jobs.some((job) => job.error) && (
            <div className="error-banner" role="alert">
              {queued.jobs.filter((job) => job.error).length} could not be queued:{" "}
              {queued.jobs.find((job) => job.error)?.error}
            </div>
          )}
        </section>
      )}

      {/* ---------------- Recent rounds ---------------- */}

      {recent.length > 0 && (
        <>
          <h2>Recent rounds</h2>
          <div className="stats-table-wrap">
            <table className="stats-table">
              <thead>
                <tr>
                  <th>When</th>
                  <th>Topics</th>
                  <th className="stats-number">Candidates</th>
                  <th>AI</th>
                  <th className="stats-number">Analysed</th>
                  <th>Chosen by</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {recent.map((summary) => (
                  <tr key={summary.id}>
                    <td>{when(summary.startedAt)}</td>
                    <td>{(summary.groups ?? []).map(groupName).join(", ")}</td>
                    <td className="stats-number">{summary.totals?.candidates ?? "–"}</td>
                    <td>
                      {summary.aiStatus === "done"
                        ? `${summary.aiPicks} proposed`
                        : summary.aiStatus ?? <span className="stats-muted">–</span>}
                    </td>
                    <td className="stats-number">{summary.queued || <span className="stats-muted">–</span>}</td>
                    <td>{summary.selectedBy ?? <span className="stats-muted">–</span>}</td>
                    <td>
                      {summary.id === round?.id ? (
                        <span className="stats-muted">open</span>
                      ) : (
                        <button type="button" className="button-link" onClick={() => reopen(summary.id)}>
                          Reopen
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  );
}
