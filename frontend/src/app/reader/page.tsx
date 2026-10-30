"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { LanguageSwitch } from "@/components/reader/LanguageSwitch";
import { ReaderCard } from "@/components/reader/ReaderCard";
import { StoryList } from "@/components/reader/StoryList";
import { Edition, useEdition } from "@/lib/edition";
import { ReaderFeed } from "@/lib/reader";
import { ReaderText, languageNameIn, readerText, topicName, withLang } from "@/lib/readerText";
import { useReaderLang } from "@/lib/useReaderLang";

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
 * `language` filters the articles; `lang` (useReaderLang) is the page's
 * own language, kept beside them.
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
  const lang = url.searchParams.get("lang");
  url.search = "";
  if (lang) url.searchParams.set("lang", lang);
  if (query.topic) url.searchParams.set("topic", query.topic);
  if (query.language) url.searchParams.set("language", query.language);
  if (query.page > 0) url.searchParams.set("page", String(query.page + 1));
  window.history.replaceState(null, "", url);
}

function errorMessage(data: unknown, status: number, t: ReaderText): string {
  const body = (data ?? {}) as { detail?: unknown; error?: unknown };
  if (typeof body.detail === "string") return body.detail;
  if (typeof body.error === "string") return body.error;
  return t.feedFailed(status);
}

export default function ReaderPage() {
  const [lang, setLang] = useReaderLang();
  const t = readerText(lang);
  const [query, setQuery] = useState<FeedQuery | null>(null);
  const [feed, setFeed] = useState<ReaderFeed | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // The header's edition: each edition's readers see only its articles
  // (backend reader index, `edition`). A topic of the other edition's is
  // dropped when the switch moves - it would match nothing.
  const { edition, ready } = useEdition();
  const lastEdition = useRef<Edition | null>(null);

  useEffect(() => {
    setQuery(readQuery());
  }, []);

  useEffect(() => {
    if (!ready) return;
    if (lastEdition.current && lastEdition.current !== edition) {
      setQuery((current) => {
        if (!current) return current;
        const next = { ...current, topic: null, page: 0 };
        writeQuery(next);
        return next;
      });
    }
    lastEdition.current = edition;
  }, [edition, ready]);

  useEffect(() => {
    if (!query || !ready) return;

    let cancelled = false;

    const search = new URLSearchParams({
      offset: String(query.page * PAGE_SIZE),
      limit: String(PAGE_SIZE),
    });
    if (query.topic) search.set("topic", query.topic);
    if (query.language) search.set("language", query.language);
    search.set("edition", edition);

    setLoading(true);

    (async () => {
      try {
        const response = await fetch(`/api/reader/articles?${search}`, { cache: "no-store" });
        const data = await response.json();
        if (!response.ok) throw new Error(errorMessage(data, response.status, readerText(lang)));
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
    // Not on `lang`: it only words an error, and a new language is no
    // reason to fetch the feed again.
  }, [query, edition, ready]);

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
      <LanguageSwitch lang={lang} onSelect={setLang} />

      <h1>{t.feedTitle}</h1>
      <p className="subtitle">{t.feedSubtitle}</p>
      <p className="reader-guide-link">
        <Link href={withLang("/reader/guide", lang)}>{t.guidePage.title}</Link>
      </p>

      {/* The articles the newsroom wrote from these (docs/decisions/
          writing.md, "Publishing"). Shown only once one is published, and
          outside the filters below, which are the checked articles'. */}
      <StoryList lang={lang} />

      {error && <div className="error-banner">{error}</div>}

      {!feed && loading && !error && (
        <p className="reader-loading">
          <span className="spinner" aria-hidden="true" /> {t.loadingFeed}
        </p>
      )}

      {feed && query && feed.lake.publishable > 0 && (
        <Filters feed={feed} query={query} onChange={update} t={t} />
      )}

      {feed && query && (
        <div className="reader-feed" aria-busy={loading}>
          {feed.items.length === 0 ? (
            <EmptyFeed
              t={t}
              feed={feed}
              filtered={filtered}
              onClear={() => update(EMPTY_QUERY)}
              onFirstPage={() => goToPage(0)}
            />
          ) : (
            <>
              <p className="reader-count">
                {t.articles(feed.total)}
                {filtered ? t.match : ""}
                {feed.total > feed.limit &&
                  t.shown(feed.offset + 1, Math.min(feed.offset + feed.items.length, feed.total))}
              </p>

              {feed.items.map((article) => (
                <ReaderCard key={article.id} article={article} lang={lang} />
              ))}

              {feed.total > feed.limit && (
                <nav className="reader-pager" aria-label={t.pages}>
                  <button
                    type="button"
                    className="reader-pager-button"
                    disabled={query.page === 0 || loading}
                    onClick={() => goToPage(query.page - 1)}
                  >
                    {t.newer}
                  </button>
                  <span className="reader-pager-status">
                    {t.pageOf(query.page + 1, Math.ceil(feed.total / feed.limit))}
                  </span>
                  <button
                    type="button"
                    className="reader-pager-button"
                    disabled={feed.offset + feed.items.length >= feed.total || loading}
                    onClick={() => goToPage(query.page + 1)}
                  >
                    {t.older}
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
  t,
}: {
  feed: ReaderFeed;
  query: FeedQuery;
  onChange: (next: FeedQuery) => void;
  t: ReaderText;
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
        label={t.filterTopic}
        all={t.all}
        options={topics}
        selected={query.topic}
        describe={(value) => topicName(t, value)}
        onSelect={(topic) => onChange({ ...query, topic, page: 0 })}
      />
      {languages.length > 1 || query.language ? (
        <FilterRow
          label={t.filterLanguage}
          all={t.all}
          options={languages}
          selected={query.language}
          describe={(value) => languageNameIn(t, value)}
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
  all,
  options,
  selected,
  describe,
  onSelect,
}: {
  label: string;
  all: string;
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
          {all}
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
  t,
  feed,
  filtered,
  onClear,
  onFirstPage,
}: {
  t: ReaderText;
  feed: ReaderFeed;
  filtered: boolean;
  onClear: () => void;
  onFirstPage: () => void;
}) {
  if (feed.lake.analysed === 0) {
    const words = t.emptyNothingAnalysed;
    return (
      <div className="card reader-empty">
        <h2>{t.emptyNothingAnalysedTitle}</h2>
        <p>
          {words.before}
          <Link href="/">{words.analyzer}</Link>
          {words.middle}
          <Link href="/scraper">{words.scraper}</Link>
          {words.after}
        </p>
      </div>
    );
  }

  if (feed.lake.publishable === 0) {
    return (
      <div className="card reader-empty">
        <h2>{t.emptyNothingPublishedTitle}</h2>
        <p>
          {t.emptyNothingPublished(feed.lake.analysed)}
          <Link href="/scraper">{t.emptyNothingPublishedLink}</Link>
          {t.emptyNothingPublishedAfter}
        </p>
      </div>
    );
  }

  if (feed.total > 0) {
    return (
      <div className="card reader-empty">
        <h2>{t.emptyPastEndTitle}</h2>
        <p>{t.emptyPastEnd(feed.total)}</p>
        <button type="button" className="reader-pager-button" onClick={onFirstPage}>
          {t.firstPage}
        </button>
      </div>
    );
  }

  return (
    <div className="card reader-empty">
      <h2>{t.emptyNoMatchTitle}</h2>
      <p>{t.emptyNoMatch(feed.lake.publishable, filtered)}</p>
      {filtered && (
        <button type="button" className="reader-pager-button" onClick={onClear}>
          {t.clearFilters}
        </button>
      )}
    </div>
  );
}
