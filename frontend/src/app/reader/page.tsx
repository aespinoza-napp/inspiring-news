"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ReaderCard } from "@/components/reader/ReaderCard";
import { ReaderFeed, languageName, plural } from "@/lib/reader";

const PAGE_SIZE = 20;

interface FeedQuery {
  topic: string | null;
  language: string | null;
  /** 0-based; 1-based in the URL. */
  page: number;
}

const EMPTY_QUERY: FeedQuery = { topic: null, language: null, page: 0 };

/**
 * The filters live in the URL (?topic=Climate&language=es&page=2), so a
 * filtered feed can be linked to and Back from an article returns to it.
 * Read once on arrival, written on every change - in the handler, not in
 * an effect, for the Strict Mode reason given in app/graph/page.tsx.
 */
function readQuery(): FeedQuery {
  const search = new URLSearchParams(window.location.search);
  const page = Number.parseInt(search.get("page") ?? "1", 10);

  return {
    topic: search.get("topic") || null,
    language: search.get("language") || null,
    page: Number.isFinite(page) && page > 1 ? page - 1 : 0,
  };
}

function writeQuery(query: FeedQuery) {
  const url = new URL(window.location.href);
  url.search = "";
  if (query.topic) url.searchParams.set("topic", query.topic);
  if (query.language) url.searchParams.set("language", query.language);
  if (query.page > 0) url.searchParams.set("page", String(query.page + 1));
  window.history.replaceState(null, "", url);
}

function errorMessage(data: unknown, status: number): string {
  const body = (data ?? {}) as { detail?: unknown; error?: unknown };
  if (typeof body.detail === "string") return body.detail;
  if (typeof body.error === "string") return body.error;
  return `Loading the feed failed (${status}).`;
}

export default function ReaderPage() {
  const [query, setQuery] = useState<FeedQuery | null>(null);
  const [feed, setFeed] = useState<ReaderFeed | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setQuery(readQuery());
  }, []);

  useEffect(() => {
    if (!query) return;

    let cancelled = false;

    const search = new URLSearchParams({
      offset: String(query.page * PAGE_SIZE),
      limit: String(PAGE_SIZE),
    });
    if (query.topic) search.set("topic", query.topic);
    if (query.language) search.set("language", query.language);

    setLoading(true);

    (async () => {
      try {
        const response = await fetch(`/api/reader/articles?${search}`, { cache: "no-store" });
        const data = await response.json();
        if (!response.ok) throw new Error(errorMessage(data, response.status));
        if (cancelled) return;
        setFeed(data as ReaderFeed);
        setError(null);
      } catch (exc) {
        if (cancelled) return;
        setError(exc instanceof Error ? exc.message : String(exc));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [query]);

  function update(next: FeedQuery) {
    setQuery(next);
    writeQuery(next);
  }

  function goToPage(page: number) {
    if (!query) return;
    update({ ...query, page });
    window.scrollTo({ top: 0 });
  }

  const filtered = Boolean(query?.topic || query?.language);

  return (
    <>
      <h1>Checked articles</h1>
      <p className="subtitle">
        Articles that passed every step: on a topic we cover, constructive, not a duplicate, and
        not judged false or misleading. Each says how its claims came out and what the verdict
        rests on.
      </p>

      {error && <div className="error-banner">{error}</div>}

      {!feed && loading && !error && (
        <p className="reader-loading">
          <span className="spinner" aria-hidden="true" /> Loading the feed…
        </p>
      )}

      {feed && query && feed.lake.publishable > 0 && (
        <Filters feed={feed} query={query} onChange={update} />
      )}

      {feed && query && (
        <div className="reader-feed" aria-busy={loading}>
          {feed.items.length === 0 ? (
            <EmptyFeed
              feed={feed}
              filtered={filtered}
              onClear={() => update(EMPTY_QUERY)}
              onFirstPage={() => goToPage(0)}
            />
          ) : (
            <>
              <p className="reader-count">
                {plural(feed.total, "article")}
                {filtered ? " match" : ""}
                {feed.total > feed.limit &&
                  ` · ${feed.offset + 1}–${Math.min(feed.offset + feed.items.length, feed.total)} shown`}
              </p>

              {feed.items.map((article) => (
                <ReaderCard key={article.id} article={article} />
              ))}

              {feed.total > feed.limit && (
                <nav className="reader-pager" aria-label="Pages">
                  <button
                    type="button"
                    className="reader-pager-button"
                    disabled={query.page === 0 || loading}
                    onClick={() => goToPage(query.page - 1)}
                  >
                    ← Newer
                  </button>
                  <span className="reader-pager-status">
                    Page {query.page + 1} of {Math.ceil(feed.total / feed.limit)}
                  </span>
                  <button
                    type="button"
                    className="reader-pager-button"
                    disabled={feed.offset + feed.items.length >= feed.total || loading}
                    onClick={() => goToPage(query.page + 1)}
                  >
                    Older →
                  </button>
                </nav>
              )}
            </>
          )}
        </div>
      )}
    </>
  );
}

function Filters({
  feed,
  query,
  onChange,
}: {
  feed: ReaderFeed;
  query: FeedQuery;
  onChange: (next: FeedQuery) => void;
}) {
  // A selected value stays on screen even where the other filter leaves
  // it no articles, so it can still be seen and switched off.
  const topics = withSelected(feed.topics.map((facet) => ({ value: facet.topic, count: facet.count })), query.topic);
  const languages = withSelected(
    feed.languages.map((facet) => ({ value: facet.language, count: facet.count })),
    query.language
  );

  return (
    <div className="reader-filters">
      <FilterRow
        label="Topic"
        options={topics}
        selected={query.topic}
        describe={(value) => value}
        onSelect={(topic) => onChange({ ...query, topic, page: 0 })}
      />
      {languages.length > 1 || query.language ? (
        <FilterRow
          label="Language"
          options={languages}
          selected={query.language}
          describe={languageName}
          onSelect={(language) => onChange({ ...query, language, page: 0 })}
        />
      ) : null}
    </div>
  );
}

interface FilterOption {
  value: string;
  count: number;
}

function withSelected(options: FilterOption[], selected: string | null): FilterOption[] {
  if (!selected || options.some((option) => option.value.toLowerCase() === selected.toLowerCase())) {
    return options;
  }
  return [...options, { value: selected, count: 0 }];
}

function FilterRow({
  label,
  options,
  selected,
  describe,
  onSelect,
}: {
  label: string;
  options: FilterOption[];
  selected: string | null;
  describe: (value: string) => string;
  onSelect: (value: string | null) => void;
}) {
  const isSelected = (value: string | null) =>
    (value ?? "").toLowerCase() === (selected ?? "").toLowerCase();

  return (
    <div className="reader-filter-row" role="group" aria-label={label}>
      <span className="reader-filter-label">{label}</span>
      <div className="reader-filter-options">
        <button
          type="button"
          className="reader-filter"
          aria-pressed={isSelected(null)}
          onClick={() => onSelect(null)}
        >
          All
        </button>
        {options.map((option) => (
          <button
            key={option.value}
            type="button"
            className="reader-filter"
            aria-pressed={isSelected(option.value)}
            onClick={() => onSelect(isSelected(option.value) ? null : option.value)}
          >
            {describe(option.value)}
            <span className="reader-filter-count">{option.count}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

/**
 * An empty feed says which of its causes it is: they have different
 * fixes. Nothing analysed means run the pipeline; analysed but nothing
 * published means every article was turned away or judged false or
 * misleading; the rest are this page's own filters and paging.
 */
function EmptyFeed({
  feed,
  filtered,
  onClear,
  onFirstPage,
}: {
  feed: ReaderFeed;
  filtered: boolean;
  onClear: () => void;
  onFirstPage: () => void;
}) {
  if (feed.lake.analysed === 0) {
    return (
      <div className="card reader-empty">
        <h2>Nothing has been analysed yet</h2>
        <p>
          The store holds no analysed article, so there is nothing to publish. Analyse one on
          the <Link href="/">Analyzer</Link>, or queue a batch from the ingest panel on{" "}
          <Link href="/scraper">Scraper</Link>; every article that passes appears here.
        </p>
      </div>
    );
  }

  if (feed.lake.publishable === 0) {
    return (
      <div className="card reader-empty">
        <h2>Nothing has been published</h2>
        <p>
          {plural(feed.lake.analysed, "article")} analysed, and none passed. Each was turned away
          before checking (off-topic, not constructive, or a duplicate) or was judged false or
          misleading. <Link href="/scraper">Scraper</Link> shows what became of each one.
        </p>
      </div>
    );
  }

  if (feed.total > 0) {
    return (
      <div className="card reader-empty">
        <h2>This page is past the end</h2>
        <p>There are {plural(feed.total, "article")} on fewer pages than that.</p>
        <button type="button" className="reader-pager-button" onClick={onFirstPage}>
          Go to the first page
        </button>
      </div>
    );
  }

  return (
    <div className="card reader-empty">
      <h2>No published article matches</h2>
      <p>
        {plural(feed.lake.publishable, "article")} published; none matches{" "}
        {filtered ? "these filters" : "this view"}.
      </p>
      {filtered && (
        <button type="button" className="reader-pager-button" onClick={onClear}>
          Clear the filters
        </button>
      )}
    </div>
  );
}
