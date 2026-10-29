// What the universe reads from the backend (src/api/map_routes.py,
// src/api/account_routes.py), decoded once into typed arrays. Copied
// from the newsroom frontend's lib/newsMap.ts rather than shared: two
// separate apps, and this one adds the depth (layout version 2).

export interface Group {
  key: string;
  name: string;
  angle: number;
  span: number;
}

export interface Topic {
  key: string;
  name: string;
  group: string;
  x: number;
  y: number;
}

export interface MapDocument {
  layout: number;
  groups: Group[];
  topics: Topic[];
  count: number;
  sources: string[];
  entities: { k: string; n: string; t: string }[];
  articles: {
    id: string[];
    title: string[];
    lang: (string | null)[];
    day: (string | null)[];
    src: number[];
    g: number[];
    t: number[][];
    e: number[][];
    v: (string | null)[];
    x: number[];
    y: number[];
    z?: number[];
    approx: (string | null)[];
  };
}

export interface Universe {
  groups: Group[];
  topics: Topic[];
  count: number;
  // x, y, z per story in map units: x and y on the disc, z its depth.
  positions: Float32Array;
  group: Uint8Array;
  ids: string[];
  titles: string[];
  languages: (string | null)[];
  days: (string | null)[];
  sources: string[];
  sourceOf: Uint16Array;
  topicsOf: number[][];
  entitiesOf: number[][];
  entities: { k: string; n: string; t: string }[];
  verdicts: (string | null)[];
  indexOf: Map<string, number>;
}

export const NO_GROUP = 255;

export function decode(document: MapDocument): Universe {
  const a = document.articles;
  const count = a.id.length;
  const positions = new Float32Array(count * 3);
  const group = new Uint8Array(count);
  const sourceOf = new Uint16Array(count);
  const indexOf = new Map<string, number>();

  for (let i = 0; i < count; i++) {
    positions[i * 3] = a.x[i];
    positions[i * 3 + 1] = a.y[i];
    positions[i * 3 + 2] = a.z ? a.z[i] : 0;
    group[i] = a.g[i] < 0 ? NO_GROUP : a.g[i];
    sourceOf[i] = a.src[i];
    indexOf.set(a.id[i], i);
  }

  return {
    groups: document.groups,
    topics: document.topics,
    count,
    positions,
    group,
    ids: a.id,
    titles: a.title,
    languages: a.lang,
    days: a.day,
    sources: document.sources,
    sourceOf,
    topicsOf: a.t,
    entitiesOf: a.e,
    entities: document.entities,
    verdicts: a.v,
    indexOf,
  };
}

export interface Links {
  id: string;
  title: string;
  topics: { key: string; name: string; confidence: number }[];
  entities: { key: string; name: string; type: string; articles: number }[];
  related: { id: string; title: string; x: number; y: number; score: number; via: { kind: string; via: string; weight: number }[] }[];
}

export interface SearchResult {
  kind: "article" | "entity";
  id?: string;
  key?: string;
  title?: string;
  name?: string;
  articles?: number;
  x: number;
  y: number;
  reason: string;
}

export interface ForYouItem {
  id: string;
  title: string;
  source: string;
  day: string | null;
  score: number;
  parts: Record<string, number>;
  mainPart: string;
  reasons: string[];
}

export interface Interest {
  kind: "group" | "topic" | "entity";
  key: string;
  label: string;
}

// Today in Madrid, YYYY-MM-DD: the backend dates every story by Madrid's day.
export function madridToday(): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Madrid", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
}

async function json<T>(response: Response): Promise<T> {
  if (response.status === 429) throw new Error(`Too many requests from here; try again in ${response.headers.get("retry-after") ?? "a moment"} s.`);
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(typeof body?.detail === "string" ? body.detail : `The request failed (${response.status}).`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  universe: () => fetch("/api/map/articles", { cache: "no-cache" }).then((r) => json<MapDocument>(r)).then(decode),
  links: (id: string) => fetch(`/api/map/articles/${id}/links`).then((r) => json<Links>(r)),
  search: (q: string, semantic: boolean) =>
    fetch(`/api/map/search?q=${encodeURIComponent(q)}&semantic=${semantic}`).then((r) => json<{ results: SearchResult[]; semantic: string }>(r)),
  forYou: (body: unknown) =>
    fetch("/api/map/for-you", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }).then((r) =>
      json<{ items: ForYouItem[]; weights: Record<string, number>; coldStart: boolean }>(r),
    ),
};

// Reader accounts: same origin, so the session cookie goes with every call.
const OURS = { "X-Requested-With": "inspiring-news" };

export async function account<T>(path: string, body?: unknown, csrf?: string | null): Promise<T | null> {
  const response = await fetch(`/api/account/${path}`, {
    method: body === undefined ? "GET" : "POST",
    cache: "no-store",
    headers: { ...OURS, ...(body !== undefined ? { "Content-Type": "application/json" } : {}), ...(csrf ? { "X-CSRF-Token": csrf } : {}) },
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  });
  if (response.status === 204) return null;
  return json<T>(response);
}
