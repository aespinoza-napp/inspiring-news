import { ClaimStep, ClaimTrace, JobTrace, TraceRejected, TraceSource } from "@/lib/liveTrace";
import { QueryKind } from "@/lib/types";
import { VerdictBadge } from "@/components/VerdictBadge";

const STEP_LABELS: Record<ClaimStep, string> = {
  searching: "Searching the web…",
  found: "Sources found",
  scraping: "Reading the top sources…",
  ranking: "Rating the sources…",
  judging: "Asking the model to judge the claim…",
  done: "Checked",
};

const percent = (value: number | null) =>
  value === null ? "–" : `${Math.round(value * 100)}%`;

/**
 * What a run is doing to its claims right now: for each one, what was
 * searched, which sources came back, how each was rated and what the
 * model concluded. Everything it draws was already sent by the backend as
 * a phase event, so it fills in while the run is still going.
 */
export function LiveTrace({ trace }: { trace: JobTrace }) {
  return (
    <div className="trace">
      {trace.skippedReason && (
        <p className="trace-note">
          Fact-check skipped — {trace.skippedReason.split(",").join(", ")}.
          {trace.validation?.impactScore != null &&
            ` Impact score ${percent(trace.validation.impactScore)}.`}
        </p>
      )}

      {trace.claimsSelected !== null && trace.claims.length === 0 && !trace.skippedReason && (
        <p className="trace-note">
          {trace.claimsSelected === 0
            ? "No claim was selected for verification."
            : `${trace.claimsSelected} claim(s) selected — starting the first…`}
        </p>
      )}

      {trace.claims.map((claim) => (
        <ClaimTraceCard key={claim.claim} claim={claim} />
      ))}
    </div>
  );
}

function ClaimTraceCard({ claim }: { claim: ClaimTrace }) {
  const done = claim.step === "done";
  const stillLooking = claim.step === "searching" || claim.step === "found" || claim.step === "scraping";

  return (
    <section className="trace-claim">
      <header className="trace-claim-head">
        <p className="trace-claim-text">{claim.claim}</p>

        {done ? (
          <span className="trace-claim-verdict">
            <VerdictBadge verdict={claim.verdict} />
            {claim.confidence !== null && (
              <span className="trace-muted">{percent(claim.confidence)} confidence</span>
            )}
          </span>
        ) : (
          <span className="trace-step" role="status">
            <span className="spinner" aria-hidden="true" />
            {STEP_LABELS[claim.step]}
          </span>
        )}
      </header>

      {claim.queries.length > 0 && (
        <div className="trace-block">
          <h4 className="trace-label">Searched on SearXNG</h4>
          <ul className="trace-queries">
            {claim.queries.map((query, index) => (
              <li key={query}>
                <code>{query}</code>
                {/* The anchor query alone retrieves the claim's subject;
                    the proposition query is what asks about the assertion
                    itself. Which is which is the difference between a
                    real source and a page that merely shares a name. */}
                {claim.queryKinds[index] && (
                  <span className="trace-tag">{QUERY_KIND_LABELS[claim.queryKinds[index]]}</span>
                )}
              </li>
            ))}
          </ul>
          {claim.webCount !== null && (
            <p className="trace-muted">
              {claim.webCount} web result{claim.webCount === 1 ? "" : "s"}
              {claim.internalCount
                ? ` · ${claim.internalCount} from previously analysed articles`
                : ""}
            </p>
          )}
        </div>
      )}

      {claim.found.length > 0 && (
        <details className="trace-block" open={stillLooking}>
          <summary className="trace-label">
            Sources found ({claim.found.length})
          </summary>
          <ul className="trace-sources">
            {claim.found.map((source, index) => (
              <FoundRow key={`${source.url}-${index}`} source={source} />
            ))}
          </ul>
        </details>
      )}

      {claim.ranked.length > 0 && (
        <div className="trace-block">
          <h4 className="trace-label">
            {done ? "Sources used" : "Sources rated"} ({claim.ranked.length})
          </h4>
          <ul className="trace-sources">
            {claim.ranked.map((source, index) => (
              <RatedRow key={`${source.url}-${index}`} source={source} />
            ))}
          </ul>
        </div>
      )}

      {claim.cut.length + claim.rejected.length > 0 && (
        <details className="trace-block">
          <summary className="trace-label">
            Found but not used ({claim.cut.length + claim.rejected.length})
          </summary>
          <ul className="trace-rejected">
            {[...claim.rejected, ...claim.cut].map((item, index) => (
              <RejectedRow key={`${item.url}-${index}`} item={item} />
            ))}
          </ul>
        </details>
      )}

      {done && (
        <div className="trace-block">
          {claim.explanation && <p className="trace-explanation">{claim.explanation}</p>}

          {claim.independentDomains !== null && (
            <p className="trace-muted">
              Backed by {claim.independentDomains} independent domain
              {claim.independentDomains === 1 ? "" : "s"}
            </p>
          )}

          {claim.agreements.length > 0 && (
            <Comparison title="Sources agree" items={claim.agreements} />
          )}
          {claim.discrepancies.length > 0 && (
            <Comparison title="Sources disagree" items={claim.discrepancies} />
          )}
        </div>
      )}
    </section>
  );
}

function Comparison({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="trace-comparison">
      <h4 className="trace-label">{title}</h4>
      <ul>
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

function SourceTitle({ source }: { source: TraceSource }) {
  return (
    <span className="trace-source-title">
      <strong>{source.domain || hostOf(source.url)}</strong>
      <a href={safeHref(source.url)} target="_blank" rel="noopener noreferrer">
        {source.title || source.url}
      </a>
    </span>
  );
}

function FoundRow({ source }: { source: TraceSource }) {
  return (
    <li className="trace-source">
      <SourceTitle source={source} />
      <span className="trace-source-meta">
        {source.origin === "internal" && <span className="trace-tag">stored article</span>}
        {source.engines.map((engine) => (
          <span key={engine} className="trace-tag">
            {engine}
          </span>
        ))}
        {source.foundBy.map((kind) => (
          <span key={kind} className="trace-tag">
            {QUERY_KIND_LABELS[kind]}
          </span>
        ))}
        {source.quickScore !== null && (
          <span className="trace-muted">match {percent(source.quickScore)}</span>
        )}
        {source.scraped === true && <span className="trace-tag trace-tag-ok">read</span>}
        {source.scraped === false && (
          <span className="trace-tag trace-tag-warn">could not read</span>
        )}
      </span>
    </li>
  );
}

// What each of a claim's queries is asking. Short enough to sit in a
// chip, because the useful thing is telling them apart at a glance.
const QUERY_KIND_LABELS: Record<QueryKind, string> = {
  anchor: "who & what",
  proposition: "what it claims",
  refutation: "counter-evidence",
};


function RatedRow({ source }: { source: TraceSource }) {
  const reliability = source.reliabilityKnown
    ? percent(source.reliabilityScore)
    : "unrated";

  return (
    <li className="trace-source trace-source-rated">
      <SourceTitle source={source} />

      <span className="trace-source-meta">
        {source.cited === true && <span className="trace-tag trace-tag-ok">cited</span>}
        {source.stance && (
          <span className={`stance-chip stance-${source.stance}`}>{source.stance}</span>
        )}
        {source.origin === "internal" && <span className="trace-tag">stored article</span>}
      </span>

      <div className="trace-ratings">
        <Rating label="Relevance" value={source.relevanceScore} strong />
        <Rating label="Wording match" value={source.semanticScore} />
        {/* What "wording match" cannot see: whether the claim's own
            terms are on the page at all. A page titled "What does ACME
            mean?" matches a claim mentioning ACME almost perfectly by
            embedding and contains none of what the claim asserts. */}
        <Rating label="Claim terms" value={source.lexicalScore} />
        <Rating label="Recency" value={source.recencyScore} />
        <Rating
          label="Source reliability"
          value={source.reliabilityKnown ? source.reliabilityScore : null}
          note={reliability}
        />
      </div>

      {source.pertinenceScore !== null && (
        <p className="trace-muted trace-fine">
          Addresses the claim: {percent(source.pertinenceScore)}. Below the
          run&apos;s floor a source is cut before the model sees it, however
          reliable or recent it is.
        </p>
      )}

      {!source.reliabilityKnown && (
        <p className="trace-muted trace-fine">
          Nobody has rated this domain; ranking assumed {percent(source.reliabilityScore)}.
        </p>
      )}

      {source.quote && <blockquote className="source-quote">{source.quote}</blockquote>}
    </li>
  );
}

function Rating({
  label,
  value,
  note,
  strong = false,
}: {
  label: string;
  value: number | null;
  note?: string;
  strong?: boolean;
}) {
  return (
    <div className="trace-rating">
      <span className="trace-rating-label">{label}</span>
      <span
        className="trace-rating-track"
        role="progressbar"
        aria-label={label}
        aria-valuenow={value === null ? undefined : Math.round(value * 100)}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        {value !== null && (
          <span
            className={`trace-rating-fill${strong ? " is-strong" : ""}`}
            style={{ width: `${Math.max(0, Math.min(value, 1)) * 100}%` }}
          />
        )}
      </span>
      <span className="trace-rating-value">{note ?? percent(value)}</span>
    </div>
  );
}

function RejectedRow({ item }: { item: TraceRejected }) {
  return (
    <li className="trace-source">
      <a href={safeHref(item.url)} target="_blank" rel="noopener noreferrer">
        {item.title || item.url}
      </a>
      <span className="trace-muted">{item.reason}</span>
    </li>
  );
}

/**
 * Source URLs come from web search results, which this app does not
 * control. Only http(s) may become a link: anything else (a `javascript:`
 * URL in a hostile result) is shown as text, not made clickable.
 */
function safeHref(url: string): string | undefined {
  return /^https?:\/\//i.test(url) ? url : undefined;
}

function hostOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}
