import { ClaimTiming, JobTiming } from "@/lib/liveTrace";
import { QueryKind } from "@/lib/types";

// What each of a claim's queries is asking. Short enough to sit in a
// chip, because the useful thing is telling them apart at a glance.
export const QUERY_KIND_LABELS: Record<QueryKind, string> = {
  anchor: "who & what",
  proposition: "what it claims",
  refutation: "counter-evidence",
};

// How a query was answered (backend: SearxngClient.last_route). A search
// that took 0.0 s was answered from memory; the seconds alone cannot say.
const VIA_LABELS: Record<string, string> = {
  searxng: "SearXNG",
  duckduckgo: "DuckDuckGo (fallback)",
  cache: "from memory",
  shared: "shared with another claim",
  failed: "failed",
};

const PAGE_OUTCOMES: Record<string, string> = {
  page: "read",
  snippet: "snippet only",
  cached: "already read",
  late: "too slow - snippet used",
};

export const seconds = (value: number | null): string =>
  value === null ? "–" : value < 10 ? `${value.toFixed(1)} s` : `${Math.round(value)} s`;

interface Segment {
  id: string;
  label: string;
  seconds: number;
}

/**
 * One bar for a whole: each segment as wide as its share of the time.
 * Colour tells the segments apart; the legend under it says which is
 * which, with the seconds, so nothing depends on telling hues apart.
 */
function StackedBar({ segments, label }: { segments: Segment[]; label: string }) {
  const whole = segments.reduce((sum, segment) => sum + segment.seconds, 0);

  if (whole <= 0) return null;

  return (
    <div className="timing">
      <div className="timing-bar" role="img" aria-label={label}>
        {segments.map((segment) =>
          segment.seconds > 0 ? (
            <span
              key={segment.id}
              className={`timing-seg timing-seg-${segment.id}`}
              style={{ width: `${(segment.seconds / whole) * 100}%` }}
              title={`${segment.label}: ${seconds(segment.seconds)}`}
            />
          ) : null,
        )}
      </div>
      <ul className="timing-legend">
        {segments.map((segment) => (
          <li key={segment.id}>
            <span className={`timing-key timing-seg-${segment.id}`} aria-hidden="true" />
            {segment.label} <strong>{seconds(segment.seconds)}</strong>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** An article's stages, fetch to store, and its total. */
export function ArticleTiming({ timing }: { timing: JobTiming }) {
  if (!timing.stages.length) return null;

  return (
    <div className="trace-block">
      <h4 className="trace-label">
        Time {timing.running ? "so far" : "taken"}: {seconds(timing.total)}
      </h4>
      <StackedBar
        label={`Time per stage, ${seconds(timing.total)} in all`}
        segments={timing.stages.map((stage) => ({
          id: stage.id,
          label: stage.label,
          seconds: stage.seconds,
        }))}
      />
    </div>
  );
}

/**
 * Where one claim's seconds went: the search (and each query in it), the
 * pages, the ranking, the wait for the model and the model itself. Shown
 * once the claim is checked; a run from before the backend measured the
 * stages shows its total only.
 */
export function ClaimTimingPanel({ timing }: { timing: ClaimTiming }) {
  if (timing.total === null) return null;

  const parts: Segment[] = [
    { id: "search", label: "Search", seconds: timing.search ?? 0 },
    { id: "fetch", label: "Pages", seconds: timing.fetch ?? 0 },
    { id: "ranking", label: "Ranking", seconds: timing.ranking ?? 0 },
    { id: "wait", label: "Waiting for the model", seconds: timing.llmWait ?? 0 },
    { id: "llm", label: "The model", seconds: timing.llm ?? 0 },
  ];

  const measured = parts.reduce((sum, part) => sum + part.seconds, 0);

  // Embedding the claim, the pre-rank, the stored-article search and the
  // hand-offs between stages: what no named part covers.
  const rest = Math.max(0, timing.total - measured);

  const segments = measured > 0
    ? [...parts.filter((part) => part.seconds > 0), { id: "other", label: "Other", seconds: rest }]
    : [];

  return (
    <details className="trace-block timing-claim">
      <summary className="trace-label">
        Time: {seconds(timing.total)}
        {timing.deadline !== null && (
          <span className={`trace-tag${timing.deadlineExceeded ? " trace-tag-warn" : ""}`}>
            {timing.deadlineExceeded ? "past" : "within"} its {seconds(timing.deadline)} limit
          </span>
        )}
      </summary>

      {segments.length > 0 && (
        <StackedBar label={`Time per step, ${seconds(timing.total)} in all`} segments={segments} />
      )}

      {timing.queries.length > 0 && (
        <table className="timing-table">
          <caption className="trace-muted">Each search, at the same time as the others</caption>
          <thead>
            <tr>
              <th scope="col">Query</th>
              <th scope="col">Results</th>
              <th scope="col">Answered by</th>
              <th scope="col" className="timing-num">Time</th>
            </tr>
          </thead>
          <tbody>
            {timing.queries.map((query, index) => (
              <tr key={`${query.query}-${index}`}>
                <td>
                  {query.kind && <span className="trace-tag">{QUERY_KIND_LABELS[query.kind]}</span>}{" "}
                  <code>{query.query}</code>
                </td>
                <td>{query.results ?? (query.error ? "failed" : "–")}</td>
                <td>{query.via ? VIA_LABELS[query.via] ?? query.via : "–"}</td>
                <td className="timing-num">{seconds(query.seconds)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {timing.pages.length > 0 && (
        <table className="timing-table">
          <caption className="trace-muted">
            Each page, fetched at the same time
            {timing.fetchWait !== null && ` (waited at most ${seconds(timing.fetchWait)})`}
          </caption>
          <thead>
            <tr>
              <th scope="col">Page</th>
              <th scope="col">Outcome</th>
              <th scope="col" className="timing-num">Time</th>
            </tr>
          </thead>
          <tbody>
            {timing.pages.map((page, index) => (
              <tr key={`${page.url}-${index}`}>
                <td className="timing-url">{hostOf(page.url)}</td>
                <td>{page.outcome ? PAGE_OUTCOMES[page.outcome] ?? page.outcome : "–"}</td>
                <td className="timing-num">{seconds(page.seconds)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {timing.model && (
        <p className="trace-muted">
          {timing.model}
          {timing.promptTokens !== null && ` read ${timing.promptTokens} tokens`}
          {timing.completionTokens !== null && ` and wrote ${timing.completionTokens}`}
          {timing.llm !== null && ` in ${seconds(timing.llm)}`}
          {timing.llmWait !== null && timing.llmWait >= 0.5 &&
            `, after waiting ${seconds(timing.llmWait)} for another claim's call`}
          .
        </p>
      )}
    </details>
  );
}

function hostOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}
