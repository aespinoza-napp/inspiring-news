"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { FlowSteps } from "@/components/FlowSteps";
import { editionOf, toneLabel, useEdition } from "@/lib/edition";
import { safeHref } from "@/lib/links";
import {
  Candidate,
  CandidateRank,
  CandidateRound,
  CandidateRoundSummary,
  IngestSource,
  IngestSourcesResponse,
  RoundTrend,
  ScoredCandidate,
  TopicGroup,
  TrendCard,
  TrendSignal,
} from "@/lib/types";

const PER_SOURCE_OPTIONS = [1, 2, 3, 5, 10];

// Where "Articles per source" starts, always: one, the person's choice
// (2026-10-30). A reopened round still shows the count it was made with.
const DEFAULT_PER_SOURCE = 1;

// The trending lens's defaults when the backend does not say (one older
// than 2026-10-26): src/services/trends/trending.py.
const FALLBACK_PER_TREND = 2;
const FALLBACK_MAX_PER_TREND = 5;

// Where the positive-impact-or-topic control starts when the backend does
// not say (one older than 2026-10-13): its default then.
const FALLBACK_TOPIC_EMPHASIS = 0.6;

// The control's step: finer than this is noise on what a round shows
// (docs/experiments.md, "emphasis: positive impact or the topic").
const EMPHASIS_STEP = 0.05;

// The mission screen's reasons (backend src/services/selection/mission_screen.py
// OFF_MISSION, and FORMATS for what is not an article at all).
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
  podcast: "a podcast, not an article",
  roundup: "a roundup of several stories",
  quiz: "a quiz",
  gallery: "a photo gallery",
  advisory: "a media advisory",
  promotion: "a promotion",
  shopping: "shopping",
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

function percent(value: number | undefined): string {
  return value === undefined ? "–" : `${Math.round(value * 100)}%`;
}

// A candidate's score and what it is made of (backend
// src/services/selection/ranking.py): the story's own title and summary,
// how well it fits the topics picked (weighed against the first by the
// round's topic emphasis), how much of its source's news the screen kept
// this round, and the source's reliability rating.
function RankLine({ rank, place, tone }: { rank: CandidateRank; place: number | undefined; tone: string }) {
  return (
    <div className="candidate-rank">
      <span
        className="rank-score"
        title="Ranking score, 0-100: the story itself, how well it fits the topics picked, its source's record this round and the source's reliability rating"
      >
        {place !== undefined && `#${place} · `}
        {Math.round(rank.score * 100)}
      </span>
      <span className="stats-muted">
        <span title={`How much nearer its title and summary come to ${tone} than to anything off-mission`}>
          story {rank.news === null ? "not read" : Math.round(rank.news * 100)}
        </span>
        {rank.topic !== undefined && rank.topic !== null && (
          <>
            {" · "}
            <span title="How well its title and summary fit the topics picked, rather than another group's">
              topic {Math.round(rank.topic * 100)}
            </span>
          </>
        )}
        {" · "}
        <span title="The share of this source's newest articles the mission screen kept this round, smoothed">
          source {Math.round(rank.record * 100)}% on-mission
        </span>
        {rank.virality !== undefined ? (
          <>
            {" · "}
            <span title="How much its trend is spreading among its signal's trends this round: 100 for the signal's top trend">
              trend {rank.virality === null ? "typed by you" : `spreading ${Math.round(rank.virality * 100)}`}
            </span>
          </>
        ) : (
          rank.reliability !== undefined && (
            <>
              {" · "}
              <span title="The source's configured reliability rating, the one its pages get as evidence">
                rated {rank.reliability.toFixed(2)}
              </span>
            </>
          )
        )}
      </span>
    </div>
  );
}

function searches(traffic: number | null): string {
  return traffic === null ? "" : ` · ${traffic.toLocaleString()}+ searches`;
}

// What a trending round's candidate explains: the trend's name, where it
// was read, how far it is spreading, and the video a person gave with it.
function TrendLine({ trend }: { trend: TrendCard }) {
  const href = trend.link ? safeHref(trend.link) : null;
  return (
    <div className="candidate-trend">
      <span className="trend-badge">Trending</span>{" "}
      {href ? (
        <a href={href} target="_blank" rel="noopener noreferrer" title="The trend itself">
          {trend.name}
        </a>
      ) : (
        trend.name
      )}
      <span className="stats-muted">
        {" "}
        · {trend.seed ? "typed by you" : trend.signalName}
        {searches(trend.traffic)}
        {trend.startedAt && ` · since ${when(trend.startedAt)}`}
        {trend.positive && " · chosen as good news there"}
        {trend.video && " · its TikTok video goes with the story"}
      </span>
    </div>
  );
}

function sameEmphasis(a: number, b: number): boolean {
  return Math.abs(a - b) < 1e-6;
}

// The emphasis a round was asked for, so reopening it puts the control
// back where it was: what it asked, else what it applied, else the default.
function emphasisOf(round: CandidateRound, fallback: number): number {
  const emphasis = round.ranking?.topicEmphasis;
  return emphasis?.asked ?? emphasis?.applied ?? emphasis?.default ?? fallback;
}

// How much fitting the topics picked weighs against positive impact in the
// order (backend src/services/selection/ranking.py, the topic emphasis): 0
// all positive impact, 1 all topic. It splits the story's share of each
// score; the source's record and rating keep theirs. Without a topic there
// is nothing to weigh, and the control says so rather than pretending.
function EmphasisControl({
  value,
  defaultValue,
  hasTopic,
  disabled,
  onChange,
  tone,
}: {
  value: number;
  defaultValue: number;
  hasTopic: boolean;
  disabled: boolean;
  onChange: (value: number) => void;
  /** What the story is read for in this edition: "positive impact" or "devastation". */
  tone: string;
}) {
  const topic = Math.round(value * 100);
  const atDefault = sameEmphasis(value, defaultValue);

  return (
    <div className="emphasis-control">
      <label className="emphasis-label" htmlFor="topic-emphasis">
        What comes first
      </label>
      <div className="emphasis-slider">
        <span className="emphasis-end">{tone[0].toUpperCase() + tone.slice(1)}</span>
        <input
          id="topic-emphasis"
          type="range"
          min={0}
          max={1}
          step={EMPHASIS_STEP}
          value={value}
          disabled={disabled || !hasTopic}
          onChange={(event) => onChange(Number(event.target.value))}
          aria-valuetext={`${topic}% topic relevance, ${100 - topic}% ${tone}`}
        />
        <span className="emphasis-end">Topic relevance</span>
      </div>
      <p className="claims-note">
        {hasTopic ? (
          <>
            {topic}% topic relevance, {100 - topic}% {tone}
            {atDefault ? " (the default)" : ""}: of what each story counts for, how much is how
            squarely it fits these topics and how much {tone} it reads as. Its source&apos;s record
            and rating count the same either way, and stories nearer another topic are listed after
            the rest at any setting.
            {!atDefault && (
              <>
                {" "}
                <button
                  type="button"
                  className="button-link emphasis-reset"
                  onClick={() => onChange(defaultValue)}
                  disabled={disabled}
                >
                  Back to the default ({Math.round(defaultValue * 100)}%)
                </button>
              </>
            )}
          </>
        ) : (
          `Pick a topic to weigh it against ${tone}: with no topic picked there is no topic relevance to order by.`
        )}
      </p>
    </div>
  );
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
  // The header's edition (lib/edition.tsx): which groups, sources and
  // signals are offered, and the edition a round is made - and its picks
  // analysed - in.
  const { edition, setEdition, ready } = useEdition();
  const devastating = edition === "devastating";
  const tone = toneLabel(edition).toLowerCase();

  const [catalogue, setCatalogue] = useState<IngestSourcesResponse | null>(null);
  const [groups, setGroups] = useState<string[]>([]);
  const [excluded, setExcluded] = useState<Set<string>>(new Set());
  const [perSource, setPerSource] = useState(DEFAULT_PER_SOURCE);
  const [emphasis, setEmphasis] = useState(FALLBACK_TOPIC_EMPHASIS);

  // The trending lens (docs/decisions/trends.md): what is spreading right
  // now instead of a group's sources. Groups then only order what fits them.
  const [trending, setTrending] = useState(false);
  const [signalsOff, setSignalsOff] = useState<Set<string>>(new Set());
  const [seed, setSeed] = useState("");
  const [searchTrends, setSearchTrends] = useState(false);
  const [perTrend, setPerTrend] = useState(FALLBACK_PER_TREND);

  const [round, setRound] = useState<CandidateRound | null>(null);
  const [chosen, setChosen] = useState<Set<string>>(new Set());
  const [recent, setRecent] = useState<CandidateRoundSummary[]>([]);

  const [busy, setBusy] = useState<
    "discovering" | "refreshing" | "more" | "starting-ai" | "queueing" | null
  >(null);
  const [error, setError] = useState<string | null>(null);

  const maxGroups = catalogue?.maxGroups ?? 3;
  const maxSelected = catalogue?.maxSelected ?? 20;
  const listed = catalogue?.listed ?? 20;
  const maxListed = catalogue?.maxListed ?? 40;
  const defaultEmphasis = catalogue?.topicEmphasis ?? FALLBACK_TOPIC_EMPHASIS;
  const signals: TrendSignal[] = catalogue?.signals ?? [];
  const signalsOn = signals.filter((signal) => !signalsOff.has(signal.id));
  const maxPerTrend = catalogue?.trending?.maxPerTrend ?? FALLBACK_MAX_PER_TREND;

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

  // Mirrors of the open round and the catalogue for the effects below,
  // which must not re-run each time either changes.
  const roundRef = useRef<CandidateRound | null>(null);
  roundRef.current = round;
  const catalogueRef = useRef<IngestSourcesResponse | null>(null);
  catalogueRef.current = catalogue;
  const urlRoundRead = useRef(false);

  // The groups, sources and signals of the edition - again whenever the
  // header's switch changes it. A group or a round of the other edition
  // is let go: its picks would be judged by the wrong gate.
  useEffect(() => {
    if (!ready) return;

    let cancelled = false;

    (async () => {
      try {
        const data = await call<IngestSourcesResponse>(`/api/ingest/sources?edition=${edition}`);
        if (cancelled) return;
        setCatalogue(data);
        setGroups((current) => current.filter((id) => data.groups.some((group) => group.id === id)));
        setSignalsOff(new Set());

        const open = roundRef.current;
        if (open && editionOf(open) !== edition) {
          setRound(null);
          setChosen(new Set());
          writeRoundToUrl(null);
        }

        if (!roundRef.current || editionOf(roundRef.current) !== edition) {
          setPerSource(DEFAULT_PER_SOURCE);
          setEmphasis(data.topicEmphasis ?? FALLBACK_TOPIC_EMPHASIS);
          setPerTrend(data.trending?.perTrend ?? FALLBACK_PER_TREND);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load the sources.");
      }
    })();

    loadRecent();

    return () => {
      cancelled = true;
    };
  }, [ready, edition, loadRecent]);

  // A round named in the URL, once: it opens in its own edition, which
  // becomes the page's.
  useEffect(() => {
    if (!ready || urlRoundRead.current) return;
    urlRoundRead.current = true;

    const id = roundFromUrl();
    if (!id) return;

    (async () => {
      try {
        const saved = await call<CandidateRound>(`/api/ingest/rounds/${id}`);
        roundRef.current = saved;
        setEdition(editionOf(saved));
        setRound(saved);
        setGroups(saved.groups);
        setPerSource(saved.perSource);
        setEmphasis(emphasisOf(saved, catalogueRef.current?.topicEmphasis ?? FALLBACK_TOPIC_EMPHASIS));
        restoreTrending(saved, catalogueRef.current?.signals ?? []);
        setChosen(new Set(saved.queued?.urls ?? []));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not reopen that round.");
      }
    })();
    // restoreTrending only sets state; it is the same function in effect.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, setEdition]);

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

  // The round comes best first (its ranking); once the AI has scored,
  // best AI score first, ties left in the ranking's order.
  const candidates: Candidate[] = useMemo(() => {
    const list = [...(round?.candidates ?? [])];
    if (scores.size === 0) return list;
    return list.sort((a, b) => (scores.get(b.url)?.score ?? -1) - (scores.get(a.url)?.score ?? -1));
  }, [round, scores]);

  // Each candidate's place in the ranking, which an AI sort does not change.
  const places = useMemo(() => {
    const byUrl = new Map<string, number>();
    (round?.candidates ?? []).forEach((candidate, index) => byUrl.set(candidate.url, index + 1));
    return byUrl;
  }, [round]);

  // A story's other outlets, shown or not: the url its repeats point to ->
  // their sources' names.
  const alsoIn = useMemo(() => {
    const byLead = new Map<string, string[]>();
    for (const candidate of [...(round?.candidates ?? []), ...(round?.reserve ?? [])]) {
      if (!candidate.sameStoryAs) continue;
      byLead.set(candidate.sameStoryAs, [...(byLead.get(candidate.sameStoryAs) ?? []), candidate.sourceName]);
    }
    return byLead;
  }, [round]);

  const queued = round?.queued ?? null;
  const locked = queued !== null;

  // How many more the round can show: what is ranked below, up to maxListed in all.
  const more = round
    ? Math.max(0, Math.min(round.reserve?.length ?? 0, maxListed - round.candidates.length))
    : 0;

  const unscored =
    round?.aiSelection?.status === "done"
      ? (round.candidates ?? []).filter((candidate) => !scores.has(candidate.url)).length
      : 0;

  // A reopened round puts the lens back as it was read.
  function restoreTrending(saved: CandidateRound, known: TrendSignal[]) {
    const isTrending = saved.lens === "trending";
    setTrending(isTrending);
    if (!isTrending) return;
    const read = new Set(saved.signals ?? []);
    setSignalsOff(new Set(known.filter((signal) => !read.has(signal.id)).map((signal) => signal.id)));
    setSeed(saved.seed ?? "");
    setSearchTrends(Boolean(saved.search));
    setPerTrend(saved.perTrend ?? FALLBACK_PER_TREND);
  }

  function toggleTrending() {
    if (round) {
      if (
        chosen.size > 0 &&
        !window.confirm(
          `Search ${trending ? "the topics' sources" : "what is trending"} instead? The ${chosen.size} you ticked will be cleared; this round stays under Recent rounds.`
        )
      ) {
        return;
      }
      startOver();
    }
    setTrending((current) => !current);
  }

  function toggleSignal(id: string) {
    setSignalsOff((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleGroup(id: string) {
    // Other topics are another search. With a round on screen the only way
    // to read the feeds again was Refresh, which repeats the round's own
    // topics: on 2026-10-09 Environment was picked over a Culture round and
    // Refresh brought Culture three times. The round stays under Recent.
    if (round) {
      if (
        chosen.size > 0 &&
        !window.confirm(
          `Search other topics? The ${chosen.size} you ticked will be cleared; this round stays under Recent rounds.`
        )
      ) {
        return;
      }
      startOver();
    }
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

  async function discover(again?: { groups: string[]; sources: string[]; perSource: number }) {
    setBusy(again ? "refreshing" : "discovering");
    setError(null);
    try {
      // Left at the default, none is sent: the round then records that
      // the default was used, whatever it is that day. Refresh takes the
      // control as it stands, so moving it and refreshing re-ranks.
      const topicEmphasis = sameEmphasis(emphasis, defaultEmphasis) ? null : emphasis;
      const created = await post<CandidateRound>(
        "/api/ingest/rounds",
        trending
          ? {
              trending: true,
              groups: again?.groups ?? groups,
              signals: signalsOn.map((signal) => signal.id),
              seed: seed.trim() || null,
              search: searchTrends,
              perSource: again?.perSource ?? perTrend,
              listed,
              topicEmphasis,
              edition,
            }
          : {
              groups: again?.groups ?? groups,
              sources: again?.sources ?? included.map((source) => source.id),
              perSource: again?.perSource ?? perSource,
              listed,
              topicEmphasis,
              edition,
            }
      );
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

  // The same topics, sources and articles per source, read again - from
  // the list itself. It used to take "New round" at the list's end, then
  // "Find articles" back up in step 2.
  async function refresh() {
    if (!round) return;
    if (
      chosen.size > 0 &&
      !window.confirm(
        `Read the sources again? The ${chosen.size} you ticked will be cleared; this round stays under Recent rounds.`
      )
    ) {
      return;
    }
    await discover({
      groups: round.groups,
      sources: round.sources.map((row) => row.source),
      perSource: round.perSource,
    });
  }

  // The next of the ranking into view, up to maxListed: only when asked.
  async function showMore() {
    if (!round) return;
    setBusy("more");
    setError(null);
    try {
      setRound(await post<CandidateRound>(`/api/ingest/rounds/${round.id}/more`, {}));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not show more.");
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
      roundRef.current = saved;
      setEdition(editionOf(saved));
      setRound(saved);
      setGroups(saved.groups);
      setPerSource(saved.perSource);
      setEmphasis(emphasisOf(saved, defaultEmphasis));
      restoreTrending(saved, signals);
      setChosen(
        new Set(saved.queued?.urls ?? (saved.aiSelection?.picks ?? []).map((pick) => pick.url))
      );
      writeRoundToUrl(saved.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not reopen that round.");
    }
  }

  const groupName = (id: string) => catalogue?.groups.find((group) => group.id === id)?.name ?? id;

  // How the open round was ordered, and whether the control has moved
  // since: then Refresh is what re-ranks.
  const roundEmphasis = round?.ranking?.topicEmphasis ?? null;
  // null: a round from before the control, or one with no topic to weigh.
  const roundOrderedAt = roundEmphasis?.applied ?? null;
  const emphasisMoved = roundOrderedAt !== null && !sameEmphasis(emphasis, roundOrderedAt);

  return (
    <>
      <FlowSteps current="discover" />

      <h1>Discover{devastating ? " · Devastating" : ""}</h1>
      {devastating && (
        <p className="edition-note">
          The Devastating edition: the news that is really bad for humanity - terrorism, mass
          killings, war, hate, suicide and overdose crises, disasters, abuse of power. Every
          general outlet is read and its stories screened for harm instead of hope; the
          good-news outlets are not read. What you analyse is still fact-checked.
        </p>
      )}
      <p className="subtitle">
        Pick up to {maxGroups} topics: only the sources that cover them are
        read, and only for those topics. Or pick Trending: what is spreading
        right now, and the articles that explain it. The articles found come
        best first, by how squarely they fit those topics and how{" "}
        {devastating ? "devastating" : "positive"} they read - you say which counts more - and by their source; the{" "}
        {listed} best shown, up to {maxListed} if you ask for more. Choose up
        to {maxSelected} of them, yourself or from the AI&apos;s proposal, and
        send them to analysis.
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
          {signals.length > 0 && (
            <button
              type="button"
              className={trending ? "topic-group topic-trending is-on" : "topic-group topic-trending"}
              aria-pressed={trending}
              disabled={locked || busy !== null}
              onClick={toggleTrending}
              title="What is spreading right now, and the articles that explain it"
            >
              <span className="topic-group-name">Trending</span>
              <span className="topic-group-meta">{signals.length} signals</span>
            </button>
          )}
        </div>
        <p className="claims-note">
          {trending
            ? groups.length === 0
              ? `Trending: what is spreading right now. Pick up to ${maxGroups} topics as well to list what fits them first.`
              : `Trending, with what fits ${groups.length === 1 ? "this topic" : "these topics"} first · topics: ` +
                (catalogue?.groups ?? [])
                  .filter((group) => groups.includes(group.id))
                  .flatMap((group) => group.topics.map((topic) => topic.name))
                  .join(", ")
            : groups.length === 0
              ? `Choose 1 to ${maxGroups}.`
              : `${groups.length} of ${maxGroups} · topics: ` +
                (catalogue?.groups ?? [])
                  .filter((group) => groups.includes(group.id))
                  .flatMap((group) => group.topics.map((topic) => topic.name))
                  .join(", ")}
        </p>

        {catalogue && (
          <EmphasisControl
            tone={tone}
            value={emphasis}
            defaultValue={defaultEmphasis}
            hasTopic={groups.length > 0}
            disabled={locked || busy !== null}
            onChange={setEmphasis}
          />
        )}
        {emphasisMoved && roundOrderedAt !== null && !locked && (
          <p className="claims-note emphasis-moved">
            The list below is ordered at {Math.round(roundOrderedAt * 100)}% topic relevance.{" "}
            <strong>Refresh</strong> reads the same sources again and orders a new round at{" "}
            {Math.round(emphasis * 100)}%.
          </p>
        )}
      </section>

      {/* ---------------- 2 · What is trending ---------------- */}

      {trending && !round && (
        <section className="card discover-step">
          <div className="section-label">2 · What is trending</div>
          <p className="claims-note">
            Public feeds of what people are searching for, voting up and sharing, read with no
            key. TikTok itself is not read: its listing needs a signed-in session and its terms
            forbid scraping. If you saw a trend there, type it below.
          </p>
          <div className="ingest-sources">
            {signals.map((signal) => (
              <label className="checkbox-label" key={signal.id}>
                <input
                  type="checkbox"
                  checked={!signalsOff.has(signal.id)}
                  onChange={() => toggleSignal(signal.id)}
                />
                {signal.name}
                <span className="stats-muted">
                  {" "}
                  {signal.language}
                  {signal.positive && " · good news by choice"}
                </span>
              </label>
            ))}
          </div>
          <label className="trend-seed" htmlFor="trend-seed">
            A trend you saw
            <input
              id="trend-seed"
              type="text"
              value={seed}
              maxLength={300}
              placeholder="#FarmearAura, a few words, a TikTok link or a news link"
              onChange={(event) => setSeed(event.target.value)}
            />
          </label>
          <p className="claims-note">
            A hashtag or words are looked up in the news. A TikTok link is kept as the trend&apos;s
            video, which a published story shows through TikTok&apos;s own player, only when a reader
            clicks; the video page itself is never fetched.
          </p>
          <div className="ingest-controls">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={searchTrends}
                onChange={(event) => setSearchTrends(event.target.checked)}
              />
              Also look each trend up in the news
              <span className="stats-muted"> (slower: one search a trend)</span>
            </label>
            <label className="ingest-per-source">
              Articles per trend
              <select value={perTrend} onChange={(event) => setPerTrend(Number(event.target.value))}>
                {Array.from({ length: maxPerTrend }, (_, index) => index + 1).map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              onClick={() => discover()}
              disabled={busy !== null || (signalsOn.length === 0 && !seed.trim())}
            >
              {busy === "discovering" && <span className="spinner" aria-hidden="true" />}
              {busy === "discovering"
                ? "Reading what is trending…"
                : seed.trim() && signalsOn.length === 0
                  ? "Look your trend up"
                  : `Find what is trending in ${signalsOn.length} ${signalsOn.length === 1 ? "signal" : "signals"}`}
            </button>
          </div>
          <p className="claims-note">
            Every trend&apos;s articles go through the same screen as any round: most of what is
            trending is television, sport, celebrity and accidents, and is left out. Popularity
            ranks what you see; it never decides what is true.
          </p>
        </section>
      )}

      {/* ---------------- 2 · Sources ---------------- */}

      {!trending && groups.length > 0 && !round && (
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
            <button type="button" onClick={() => discover()} disabled={busy !== null || included.length === 0}>
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
            {round.lens === "trending"
              ? `${round.totals.candidates} new articles behind ${round.totals.trends ?? 0} trends from ${round.totals.sources} ${round.totals.sources === 1 ? "signal" : "signals"}` +
                (round.groups.length ? `, ${round.groups.map(groupName).join(", ")} first` : "") +
                ((round.totals.notArticles ?? 0) > 0
                  ? ` · ${round.totals.notArticles} links that were not articles, or sport, crime or betting pages`
                  : "")
              : `${round.totals.candidates} new articles from ${round.totals.sources} sources in ${round.groups.map(groupName).join(", ")}`}
            {round.ranking &&
              (round.candidates.length < round.totals.candidates
                ? ` · the best ${round.candidates.length} shown`
                : " · all shown")}{" "}
            · {round.totals.alreadyStored} already analysed · {round.totals.deferred} more left for another round
            {(round.totals.stale ?? 0) > 0 &&
              (round.lens === "trending"
                ? ` · ${round.totals.stale} from trends or articles too old to be trending`
                : ` · ${round.totals.stale} older than a month`)}
            {(round.totals.sameStory ?? 0) > 0 &&
              ` · ${round.totals.sameStory} repeat a story another outlet tells, ranked last`}
            {round.totals.failed > 0 &&
              ` · ${round.totals.failed} ${round.totals.failed === 1 ? "source" : "sources"} found nothing`}{" "}
            <span className="stats-muted">({when(round.startedAt)})</span>
          </p>

          {round.ranking && round.candidates.length > 0 && (
            <p className="claims-note">
              Best first, by the story and its source:
              {(round.ranking.weights.topic ?? 0) > 0 &&
                ` how well it fits ${round.groups.map(groupName).join(", ")} (${percent(round.ranking.weights.topic)}),`}{" "}
              how near its title and summary come to {tone} rather than to anything
              off-mission ({percent(round.ranking.weights.news)}),{" "}
              {round.lens === "trending" ? (
                <>
                  how much of its signal&apos;s trends were on-mission this round (
                  {percent(round.ranking.weights.record)}), and how far its trend is spreading among
                  its signal&apos;s ({percent(round.ranking.weights.virality)}). Popularity orders the
                  list; it never enters a verdict.
                </>
              ) : (
                <>
                  how much of its source&apos;s news was on-mission this round (
                  {percent(round.ranking.weights.record)}), and the source&apos;s reliability rating (
                  {percent(round.ranking.weights.reliability)}).
                </>
              )}
              {roundEmphasis &&
                (roundEmphasis.applied !== null
                  ? ` Ordered at ${Math.round(roundEmphasis.applied * 100)}% topic relevance` +
                    (roundEmphasis.asked === null ? " (the default)." : ", as asked.")
                  : " No topic to weigh this round - nothing could be read for it - so its own reading and its source decide, whatever the topic setting.")}
            </p>
          )}

          {round.lens === "trending" && (round.trends ?? []).length > 0 && (
            <details className="claims-note">
              <summary>
                {round.trends?.length} trends read
                {round.seed ? `, with the one you typed (${round.seed})` : ""}: what became of each
              </summary>
              <ul className="screened-list">
                {(round.trends ?? []).map((trend: RoundTrend) => {
                  const href = trend.link ? safeHref(trend.link) : null;
                  return (
                    <li key={`${trend.signal}-${trend.id}`}>
                      {href ? (
                        <a href={href} target="_blank" rel="noopener noreferrer">
                          {trend.name}
                        </a>
                      ) : (
                        trend.name
                      )}{" "}
                      <span className="stats-muted">
                        · {trend.seed ? "typed by you" : trend.signalName}
                        {searches(trend.traffic)}
                        {` · ${trend.articles} ${trend.articles === 1 ? "article" : "articles"}`}
                        {trend.candidates > 0 && `, ${trend.candidates} offered`}
                        {trend.screened > 0 && `, ${trend.screened} left out as off-mission`}
                        {trend.stale && " · too old to be trending"}
                        {trend.notes.map((note) => ` · ${note}`)}
                      </span>
                    </li>
                  );
                })}
              </ul>
            </details>
          )}

          {round.screen?.status === "unavailable" && (
            <p className="claims-note">
              The mission screen could not run ({round.screen.error}), so nothing was left out
              for being off-mission: elections, crime or celebrity pieces may be in this list, and
              its order comes from the sources alone.
            </p>
          )}

          {round.screened && round.screened.length > 0 && (
            <details className="claims-note">
              <summary>
                {round.screened.length} left out as off-mission (elections, strikes, crime,
                accidents, markets, obituaries…) or as not an article (podcasts, roundups,
                galleries…) before choosing
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
                        {item.trend && ` · trending: ${item.trend}`}
                      </span>
                    </li>
                  );
                })}
              </ul>
            </details>
          )}

          {/* Every action on the list in one bar that stays in view while
              it scrolls: Refresh, the AI, the count and Analyse used to be
              split between its top and its end. */}
          {!locked && (
            <div className="discover-toolbar">
              <button
                type="button"
                className="button-secondary"
                onClick={refresh}
                disabled={busy !== null || aiStatus === "running"}
                title={`Read the same sources again, for ${round.groups.map(groupName).join(", ")}, ordered at ${Math.round(emphasis * 100)}% topic relevance. To search other topics, pick them above.`}
              >
                {busy === "refreshing" && <span className="spinner" aria-hidden="true" />}
                {busy === "refreshing" ? "Reading the feeds…" : "Refresh"}
              </button>
              {round.candidates.length > 0 && (
                <>
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
                  <button
                    type="button"
                    className="discover-analyse"
                    onClick={analyse}
                    disabled={busy !== null || chosen.size === 0}
                  >
                    {busy === "queueing" && <span className="spinner" aria-hidden="true" />}
                    {`Analyse ${chosen.size} ${chosen.size === 1 ? "article" : "articles"}`}
                  </button>
                </>
              )}
            </div>
          )}

          {round.aiSelection?.status === "done" && (
            <p className="claims-note">
              The AI proposed {round.aiSelection.picks?.length ?? 0} of{" "}
              {round.candidates.length - unscored}, scoring each from its title and summary
              against the publication&apos;s idea of {tone} ({round.aiSelection.model},{" "}
              {round.aiSelection.calls} {round.aiSelection.calls === 1 ? "call" : "calls"},{" "}
              {Math.round((round.aiSelection.elapsedMs ?? 0) / 1000)} s). Its picks are ticked;
              change them freely.
              {(round.aiSelection.notes ?? []).map((note) => ` ${note}`)}
              {unscored > 0 &&
                ` The ${unscored} shown since have no AI score: ask the AI again to include them.`}
            </p>
          )}

          {round.aiSelection?.status === "failed" && (
            <div className="error-banner" role="alert">
              The AI selection failed: {round.aiSelection.error}
            </div>
          )}

          {round.candidates.length === 0 ? (
            <p className="claims-note">
              {round.lens === "trending"
                ? "Nothing that is trending passed the screen, or everything was already analysed. Open the trends read above to see why, look a trend up yourself, or try later."
                : "Nothing new in these sources for these topics. Try another topic, more articles per source, or later."}
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
                        {alsoIn.has(candidate.url) && (
                          <span title={`Also in: ${alsoIn.get(candidate.url)?.join(", ")}`}>
                            {` · the same story in ${alsoIn.get(candidate.url)?.length} more ${
                              alsoIn.get(candidate.url)?.length === 1 ? "source" : "sources"
                            }, ranked after the rest`}
                          </span>
                        )}
                        {candidate.sameStoryAs &&
                          ` · the same story as ${
                            places.has(candidate.sameStoryAs) ? `#${places.get(candidate.sameStoryAs)}` : "one ranked above"
                          }`}
                        {candidate.otherGroup && (
                          <span title="Its nearest topic belongs to another group: listed after the candidates that fit the groups picked.">
                            {` · fits ${candidate.otherGroup} better, ranked after the rest`}
                          </span>
                        )}
                      </div>
                      {candidate.trend && <TrendLine trend={candidate.trend} />}
                      {candidate.summary && <p className="candidate-summary">{candidate.summary}</p>}
                      {candidate.rank && <RankLine rank={candidate.rank} place={places.get(candidate.url)} tone={tone} />}
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
                New round: other topics or sources
              </button>
              {more > 0 && (
                <button
                  type="button"
                  className="button-secondary"
                  onClick={showMore}
                  disabled={busy !== null || aiStatus === "running"}
                  title={`Up to ${maxListed} in all; ranked below the ones shown`}
                >
                  {busy === "more" && <span className="spinner" aria-hidden="true" />}
                  {`Show ${more} more`}
                </button>
              )}
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
                {recent.filter((summary) => editionOf(summary) === edition).map((summary) => (
                  <tr key={summary.id}>
                    <td>{when(summary.startedAt)}</td>
                    <td>
                      {summary.lens === "trending" &&
                        `Trending${(summary.groups ?? []).length ? " · " : ""}`}
                      {(summary.groups ?? []).map(groupName).join(", ")}
                      {typeof summary.topicEmphasis === "number" && (
                        <span className="stats-muted" title="How much topic relevance weighed against positive impact in its order">
                          {` · ${Math.round(summary.topicEmphasis * 100)}% topic`}
                        </span>
                      )}
                    </td>
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
