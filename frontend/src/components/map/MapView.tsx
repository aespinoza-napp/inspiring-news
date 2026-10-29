"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ArticlePanel } from "@/components/map/ArticlePanel";
import { MapSearch } from "@/components/map/MapSearch";
import { NewsMap, type NewsMapHandle } from "@/components/map/NewsMap";
import { NO_GROUP, type MapData, type MapEntitiesDocument, type MapLinks } from "@/lib/newsMap";
import styles from "./MapPage.module.css";

export interface MapFilters {
  language: string;
  group: string;
  verdict: string;
}

export const NO_FILTERS: MapFilters = { language: "", group: "", verdict: "" };

const VERDICT_OPTIONS = [
  ["", "Any verdict"],
  ["TRUE", "True"],
  ["PARTIALLY_TRUE", "Partially true"],
  ["UNVERIFIED", "Unverified"],
  ["NOT_CHECKED", "Not checked"],
] as const;

const PAGE = 50;

interface Props {
  data: MapData;
  entities: MapEntitiesDocument["entities"];
  // Articles to show at full strength whatever the filters (a search, a
  // day, a reader's list); the rest are dimmed. Null: the filters alone.
  emphasis?: Set<number> | null;
  // Shown above the toolbar: a page's own controls (search, day).
  header?: React.ReactNode;
  label: string;
}

// Whether article i passes the filters.
function passes(data: MapData, i: number, filters: MapFilters): boolean {
  if (filters.language && data.languages[i] !== filters.language) return false;
  if (filters.group && (data.group[i] === NO_GROUP || data.groups[data.group[i]].key !== filters.group)) return false;
  if (filters.verdict && data.verdicts[i] !== filters.verdict) return false;
  return true;
}

function readUrl(): { filters: MapFilters; selected: string | null; list: boolean } {
  const params = new URLSearchParams(window.location.search);
  return {
    filters: { language: params.get("lang") ?? "", group: params.get("group") ?? "", verdict: params.get("verdict") ?? "" },
    selected: params.get("a"),
    list: params.get("view") === "list",
  };
}

function writeUrl(filters: MapFilters, selected: string | null, list: boolean): void {
  const url = new URL(window.location.href);
  const set = (name: string, value: string | null) => (value ? url.searchParams.set(name, value) : url.searchParams.delete(name));
  set("lang", filters.language);
  set("group", filters.group);
  set("verdict", filters.verdict);
  set("a", selected);
  set("view", list ? "list" : null);
  window.history.replaceState(null, "", url);
}

// The map, its filters, the selected article's panel and the list view:
// what /map, /today and /for-you share.
export function MapView({ data, entities, emphasis = null, header, label }: Props) {
  const map = useRef<NewsMapHandle>(null);
  const [filters, setFilters] = useState<MapFilters>(NO_FILTERS);
  const [selected, setSelected] = useState(-1);
  const [list, setList] = useState(false);
  const [page, setPage] = useState(0);
  const [links, setLinks] = useState<MapLinks | null>(null);
  const [linksError, setLinksError] = useState<string | null>(null);
  const [entityFocus, setEntityFocus] = useState<string | null>(null);

  // The URL's state once, on arrival; then the page writes it back.
  useEffect(() => {
    const fromUrl = readUrl();
    setFilters(fromUrl.filters);
    setList(fromUrl.list);
    const index = fromUrl.selected ? data.indexOf.get(fromUrl.selected) : undefined;
    if (index !== undefined) setSelected(index);
  }, [data]);

  useEffect(() => {
    writeUrl(filters, selected >= 0 ? data.ids[selected] : null, list);
  }, [data, filters, selected, list]);

  // The entity a reader clicked: its articles, as far as the map's top
  // five names per article know them.
  const entityArticles = useMemo(() => {
    if (!entityFocus) return null;
    const ref = data.entities.findIndex((row) => row.k === entityFocus);
    if (ref < 0) return new Set<number>();
    const found = new Set<number>();
    data.entitiesOf.forEach((refs, i) => {
      if (refs.includes(ref)) found.add(i);
    });
    return found;
  }, [data, entityFocus]);

  const strong = entityArticles ?? emphasis;

  const visible = useMemo(() => {
    const shown: number[] = [];
    for (let i = 0; i < data.count; i++) {
      if (passes(data, i, filters) && (!strong || strong.has(i))) shown.push(i);
    }
    return shown;
  }, [data, filters, strong]);

  const alpha = useMemo(() => {
    const values = new Float32Array(data.count).fill(0.12);
    visible.forEach((i) => (values[i] = 0.9));
    return values;
  }, [data, visible]);

  // The selected article's links, fetched when it changes.
  useEffect(() => {
    setLinks(null);
    setLinksError(null);
    if (selected < 0) return;

    let cancelled = false;
    fetch(`/api/map/articles/${data.ids[selected]}/links`)
      .then(async (response) => {
        if (!response.ok) throw new Error(response.status === 404 ? "This article is no longer published." : `Its links could not be loaded (${response.status}).`);
        return (await response.json()) as MapLinks;
      })
      .then((value) => !cancelled && setLinks(value))
      .catch((error: Error) => !cancelled && setLinksError(error.message));

    return () => {
      cancelled = true;
    };
  }, [data, selected]);

  const lines = useMemo(() => {
    if (!links) return [];
    const entityPoints = new Map(entities.map((e) => [e.k, e]));
    return [
      ...links.related.map((r) => ({ x: r.x, y: r.y })),
      ...links.entities.flatMap((e) => (entityPoints.has(e.key) ? [entityPoints.get(e.key)!] : [])),
    ];
  }, [links, entities]);

  const selectId = useCallback((id: string) => {
    const index = data.indexOf.get(id);
    if (index === undefined) return;
    setSelected(index);
    map.current?.flyTo(data.positions[index * 2], data.positions[index * 2 + 1], 5);
  }, [data]);

  const focusEntity = useCallback((key: string, x?: number, y?: number) => {
    setEntityFocus((current) => (current === key ? null : key));
    const point = entities.find((e) => e.k === key) ?? (x !== undefined && y !== undefined ? { x, y } : null);
    if (point) map.current?.flyTo(point.x, point.y, 3);
  }, [entities]);

  const focusedName = entityFocus ? data.entities.find((row) => row.k === entityFocus)?.n ?? entities.find((e) => e.k === entityFocus)?.n : null;

  const languages = useMemo(() => Array.from(new Set(data.languages.filter((l): l is string => Boolean(l)))).sort(), [data]);

  const pageItems = visible.slice(page * PAGE, page * PAGE + PAGE);

  return (
    <div className={styles.page}>
      {header}

      <MapSearch
        onArticle={(id) => {
          setList(false);
          selectId(id);
        }}
        onEntity={(key, x, y) => {
          setList(false);
          focusEntity(key, x, y);
        }}
      />

      <div className={styles.toolbar} role="group" aria-label="Filters">
        <label>
          Language
          <select value={filters.language} onChange={(e) => { setFilters({ ...filters, language: e.target.value }); setPage(0); }}>
            <option value="">Any</option>
            {languages.map((language) => (
              <option key={language} value={language}>{language}</option>
            ))}
          </select>
        </label>
        <label>
          Section
          <select value={filters.group} onChange={(e) => { setFilters({ ...filters, group: e.target.value }); setPage(0); }}>
            <option value="">All five</option>
            {data.groups.map((group) => (
              <option key={group.key} value={group.key}>{group.name}</option>
            ))}
          </select>
        </label>
        <label>
          Verdict
          <select value={filters.verdict} onChange={(e) => { setFilters({ ...filters, verdict: e.target.value }); setPage(0); }}>
            {VERDICT_OPTIONS.map(([value, text]) => (
              <option key={value} value={value}>{text}</option>
            ))}
          </select>
        </label>

        {focusedName && (
          <button type="button" className="button-secondary" onClick={() => setEntityFocus(null)}>
            Showing “{focusedName}” · clear
          </button>
        )}

        <span className={styles.muted} aria-live="polite">
          {visible.length} of {data.count} articles
        </span>

        <button type="button" className={`button-secondary ${styles.viewToggle}`} onClick={() => setList(!list)} aria-pressed={list}>
          {list ? "Show the map" : "Show as a list"}
        </button>
      </div>

      {list ? (
        <>
          <ol className={styles.list}>
            {pageItems.map((i) => (
              <li key={data.ids[i]}>
                <Link href={`/reader/${data.ids[i]}`}>{data.titles[i]}</Link>
                <div className={styles.muted}>
                  {data.sources[data.sourceOf[i]]}
                  {data.days[i] ? ` · ${data.days[i]}` : ""}
                  {data.group[i] !== NO_GROUP ? ` · ${data.groups[data.group[i]].name}` : ""}
                  {data.verdicts[i] ? ` · ${data.verdicts[i]!.replace(/_/g, " ").toLowerCase()}` : ""}
                </div>
              </li>
            ))}
          </ol>
          {visible.length > PAGE && (
            <div className={styles.pager}>
              <button type="button" className="button-secondary" disabled={page === 0} onClick={() => setPage(page - 1)}>Previous</button>
              <span className={styles.muted}>{page * PAGE + 1}-{Math.min(visible.length, (page + 1) * PAGE)} of {visible.length}</span>
              <button type="button" className="button-secondary" disabled={(page + 1) * PAGE >= visible.length} onClick={() => setPage(page + 1)}>Next</button>
            </div>
          )}
        </>
      ) : (
        <>
          <div className={selected >= 0 ? `${styles.layout} ${styles.withPanel}` : styles.layout}>
            <NewsMap
              ref={map}
              data={data}
              entities={entities}
              alpha={alpha}
              selected={selected}
              links={lines}
              onSelect={setSelected}
              onEntity={focusEntity}
              label={label}
            />
            {selected >= 0 && (
              <ArticlePanel
                data={data}
                index={selected}
                links={links}
                error={linksError}
                onSelect={selectId}
                onEntity={focusEntity}
                onClose={() => setSelected(-1)}
              />
            )}
          </div>
          <ul className={styles.legend} aria-label="Sections">
            {data.groups.map((group, i) => (
              <li key={group.key}>
                <span className={styles.swatch} style={{ background: `var(--series-${i + 1})` }} aria-hidden="true" />
                {group.name}
              </li>
            ))}
            <li className={styles.muted}>Drag to move, scroll or pinch to zoom, arrows and +/− from the keyboard, 0 for the whole map.</li>
          </ul>
        </>
      )}
    </div>
  );
}
