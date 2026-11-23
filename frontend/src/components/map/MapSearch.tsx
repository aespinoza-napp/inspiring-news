"use client";

import { useEffect, useId, useRef, useState } from "react";

import styles from "./MapPage.module.css";

// GET /map/search (backend/src/services/news_map/search.py).
export interface SearchResult {
  kind: "article" | "entity";
  id?: string;
  key?: string;
  title?: string;
  name?: string;
  type?: string;
  articles?: number;
  x: number;
  y: number;
  reason: string;
}

interface Answer {
  query: string;
  results: SearchResult[];
  semantic: "used" | "skipped" | "unavailable";
}

interface Props {
  onArticle(id: string): void;
  onEntity(key: string, x: number, y: number): void;
}

const SUGGEST_AFTER_MS = 150;

async function ask(query: string, semantic: boolean): Promise<Answer> {
  const response = await fetch(`/api/map/search?q=${encodeURIComponent(query)}&semantic=${semantic}`);
  if (response.status === 429) {
    const wait = response.headers.get("retry-after");
    throw new Error(`Too many searches from here; try again${wait ? ` in ${wait} s` : " shortly"}.`);
  }
  if (!response.ok) throw new Error(`The search failed (${response.status}).`);
  return response.json();
}

function label(result: SearchResult): string {
  return result.kind === "entity" ? `${result.name} · ${result.articles} ${result.articles === 1 ? "story" : "stories"}` : result.title ?? "";
}

// Names and words as you type (no embedding per keystroke: the backend's
// `semantic=false`); Enter searches by meaning too. The query is kept in
// the URL (?q=), so a search can be shared.
export function MapSearch({ onArticle, onEntity }: Props) {
  const id = useId();
  const [query, setQuery] = useState("");
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const [error, setError] = useState<string | null>(null);
  const [full, setFull] = useState(false);
  const typed = useRef(false);

  // A shared search: run it once on arrival.
  useEffect(() => {
    const q = new URLSearchParams(window.location.search).get("q");
    if (q) {
      setQuery(q);
      submit(q);
    }
    // Once, on arrival: `submit` is recreated each render.
  }, []);

  useEffect(() => {
    if (!typed.current) return;
    if (!query.trim()) {
      setAnswer(null);
      return;
    }

    let cancelled = false;
    const timer = setTimeout(() => {
      ask(query, false)
        .then((value) => {
          if (cancelled) return;
          setAnswer(value);
          setFull(false);
          setError(null);
          setOpen(true);
          setActive(-1);
        })
        .catch((e: Error) => !cancelled && setError(e.message));
    }, SUGGEST_AFTER_MS);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [query]);

  function submit(q: string) {
    if (!q.trim()) return;
    ask(q, true)
      .then((value) => {
        setAnswer(value);
        setFull(true);
        setError(null);
        setOpen(true);
        setActive(-1);
        const url = new URL(window.location.href);
        url.searchParams.set("q", q);
        window.history.replaceState(null, "", url);
      })
      .catch((e: Error) => setError(e.message));
  }

  function choose(result: SearchResult) {
    setOpen(false);
    if (result.kind === "article" && result.id) onArticle(result.id);
    if (result.kind === "entity" && result.key) onEntity(result.key, result.x, result.y);
  }

  const results = answer?.results ?? [];

  const onKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setOpen(true);
      setActive((i) => Math.min(results.length - 1, i + 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((i) => Math.max(-1, i - 1));
    } else if (event.key === "Enter") {
      event.preventDefault();
      if (active >= 0 && results[active]) choose(results[active]);
      else submit(query);
    } else if (event.key === "Escape") {
      setOpen(false);
    }
  };

  return (
    <div className={styles.search}>
      <label htmlFor={`${id}-input`} className={styles.searchLabel}>
        Search stories and names
      </label>
      <input
        id={`${id}-input`}
        type="search"
        role="combobox"
        aria-expanded={open && results.length > 0}
        aria-controls={`${id}-results`}
        aria-activedescendant={active >= 0 ? `${id}-result-${active}` : undefined}
        autoComplete="off"
        maxLength={200}
        placeholder="A name, a place, a topic…"
        value={query}
        onChange={(e) => {
          typed.current = true;
          setQuery(e.target.value);
        }}
        onKeyDown={onKeyDown}
        onFocus={() => results.length && setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        className={styles.searchInput}
      />

      {error && <p className="error-banner">{error}</p>}

      {open && answer && (
        <div className={styles.searchResults}>
          {results.length === 0 ? (
            <p className={styles.muted}>Nothing published matches “{answer.query}”.{full ? "" : " Press Enter to search by meaning too."}</p>
          ) : (
            <ul id={`${id}-results`} role="listbox" aria-label="Results">
              {results.map((result, i) => (
                <li
                  key={`${result.kind}:${result.id ?? result.key}`}
                  id={`${id}-result-${i}`}
                  role="option"
                  aria-selected={i === active}
                  className={i === active ? styles.activeResult : undefined}
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => choose(result)}
                >
                  <span className={styles.resultKind}>{result.kind === "entity" ? "Name" : "Story"}</span>
                  {label(result)}
                  <span className={styles.muted}> · {result.reason}</span>
                </li>
              ))}
            </ul>
          )}
          <p className={styles.muted}>
            {answer.semantic === "used" && "Searched by name, by word and by meaning."}
            {answer.semantic === "skipped" && "By name and word. Press Enter to search by meaning too."}
            {answer.semantic === "unavailable" && "By name and word only: searching by meaning is unavailable right now."}
          </p>
        </div>
      )}
    </div>
  );
}
