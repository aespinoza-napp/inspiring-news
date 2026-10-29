// The news map's data (docs/decisions/news-map.md): the backend's
// GET /map/articles, decoded once into typed arrays the renderer hands
// to the GPU as they are. Shapes mirror backend/src/services/news_map/.

export interface MapGroup {
  key: string;
  name: string;
  // The sector's centre and width, in radians; 0 is east, counter-clockwise.
  angle: number;
  span: number;
}

export interface MapTopic {
  key: string;
  name: string;
  group: string;
  x: number;
  y: number;
}

export interface MapEntityRow {
  k: string;
  n: string;
  t: string;
}

// As the backend sends them: one list per field, the same index across.
export interface MapArticleColumns {
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
  approx: (string | null)[];
}

export interface MapDocument {
  layout: number;
  groups: MapGroup[];
  topics: MapTopic[];
  day: string | null;
  count: number;
  sources: string[];
  entities: MapEntityRow[];
  articles: MapArticleColumns;
}

// What the renderer and the pages use: positions and groups as typed
// arrays, everything else by index.
export interface MapData {
  layout: number;
  groups: MapGroup[];
  topics: MapTopic[];
  count: number;
  // x0, y0, x1, y1, ... in map units (the disc has radius 1).
  positions: Float32Array;
  // Index into `groups`, or 255 for an article no topic placed.
  group: Uint8Array;
  ids: string[];
  titles: string[];
  languages: (string | null)[];
  days: (string | null)[];
  sources: string[];
  sourceOf: Uint16Array;
  topicsOf: number[][];
  entitiesOf: number[][];
  entities: MapEntityRow[];
  verdicts: (string | null)[];
  approximate: (string | null)[];
  indexOf: Map<string, number>;
}

export const NO_GROUP = 255;

export function decode(document: MapDocument): MapData {
  const columns = document.articles;
  const count = columns.id.length;

  const positions = new Float32Array(count * 2);
  const group = new Uint8Array(count);
  const sourceOf = new Uint16Array(count);
  const indexOf = new Map<string, number>();

  for (let i = 0; i < count; i++) {
    positions[i * 2] = columns.x[i];
    positions[i * 2 + 1] = columns.y[i];
    group[i] = columns.g[i] < 0 ? NO_GROUP : columns.g[i];
    sourceOf[i] = columns.src[i];
    indexOf.set(columns.id[i], i);
  }

  return {
    layout: document.layout,
    groups: document.groups,
    topics: document.topics,
    count,
    positions,
    group,
    ids: columns.id,
    titles: columns.title,
    languages: columns.lang,
    days: columns.day,
    sources: document.sources,
    sourceOf,
    topicsOf: columns.t,
    entitiesOf: columns.e,
    entities: document.entities,
    verdicts: columns.v,
    approximate: columns.approx,
    indexOf,
  };
}

// Each group's colour: the site's validated categorical series
// (globals.css, --series-1..5), read at run time so dark mode applies to
// the canvas too. An article no topic placed is drawn in --muted.
export function groupColors(element: Element, groups: number): [number, number, number][] {
  const style = getComputedStyle(element);
  const colors: [number, number, number][] = [];

  for (let i = 0; i < groups; i++) {
    colors.push(parseColor(style.getPropertyValue(`--series-${i + 1}`)) ?? [0.4, 0.4, 0.4]);
  }

  colors.push(parseColor(style.getPropertyValue("--muted")) ?? [0.5, 0.5, 0.5]);

  return colors;
}

// "#2a78d6" or "rgb(42, 120, 214)" to [0..1] channels.
export function parseColor(value: string): [number, number, number] | null {
  const text = value.trim();

  const hex = /^#([0-9a-f]{6})$/i.exec(text);
  if (hex) {
    const n = parseInt(hex[1], 16);
    return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
  }

  const rgb = /^rgba?\(\s*(\d+)[,\s]+(\d+)[,\s]+(\d+)/i.exec(text);
  if (rgb) {
    return [Number(rgb[1]) / 255, Number(rgb[2]) / 255, Number(rgb[3]) / 255];
  }

  return null;
}

// A deterministic stand-in for the backend's map, for the renderer
// benchmark (app/map/bench) and N8's budget: `count` articles spread
// over the real frame's topics, so it draws like the real one.
export function synthetic(frame: Pick<MapDocument, "groups" | "topics" | "layout">, count: number, seed = 1): MapData {
  let state = seed >>> 0 || 1;
  const random = () => {
    // xorshift32: the same points on every run and every machine.
    state ^= state << 13;
    state ^= state >>> 17;
    state ^= state << 5;
    return (state >>> 0) / 4294967296;
  };

  const positions = new Float32Array(count * 2);
  const group = new Uint8Array(count);
  const ids: string[] = [];
  const titles: string[] = [];
  const topicsOf: number[][] = [];
  const groupIndex = new Map(frame.groups.map((g, i) => [g.key, i]));

  for (let i = 0; i < count; i++) {
    const t = Math.floor(random() * frame.topics.length);
    const topic = frame.topics[t];
    const angle = random() * Math.PI * 2;
    const distance = Math.sqrt(random()) * 0.075;
    positions[i * 2] = topic.x + Math.cos(angle) * distance;
    positions[i * 2 + 1] = topic.y + Math.sin(angle) * distance;
    group[i] = groupIndex.get(topic.group) ?? NO_GROUP;
    ids.push(i.toString(16).padStart(16, "0"));
    titles.push(`Synthetic story ${i} about ${topic.name}`);
    topicsOf.push([t]);
  }

  return {
    layout: frame.layout,
    groups: frame.groups,
    topics: frame.topics,
    count,
    positions,
    group,
    ids,
    titles,
    languages: ids.map((_, i) => (i % 2 ? "en" : "es")),
    days: ids.map(() => null),
    sources: ["Synthetic"],
    sourceOf: new Uint16Array(count),
    topicsOf,
    entitiesOf: ids.map(() => []),
    entities: [],
    verdicts: ids.map(() => "TRUE"),
    approximate: ids.map(() => null),
    indexOf: new Map(ids.map((id, i) => [id, i])),
  };
}

// GET /map/articles/{id}/links (backend/src/services/news_map/index.py, links).
export interface MapLinkReason {
  kind: "claim" | "evidence" | "entity" | "topic";
  via: string;
  weight: number;
}

export interface MapRelated {
  id: string;
  title: string;
  x: number;
  y: number;
  score: number;
  via: MapLinkReason[];
}

export interface MapLinks {
  id: string;
  title: string;
  x: number;
  y: number;
  topics: { key: string; name: string; confidence: number }[];
  entities: { key: string; name: string; type: string; articles: number }[];
  related: MapRelated[];
}

// GET /map/entities.
export interface MapEntitiesDocument {
  layout: number;
  count: number;
  entities: { k: string; n: string; t: string; c: number; x: number; y: number }[];
}

// What a related article's reason reads as.
export function reasonText(reason: MapLinkReason): string {
  switch (reason.kind) {
    case "claim":
      return `the same claim: "${reason.via.length > 120 ? `${reason.via.slice(0, 117)}...` : reason.via}"`;
    case "evidence":
      return "a source both were checked against";
    case "entity":
      return `both name ${reason.via}`;
    case "topic":
      return `both are about ${reason.via}`;
  }
}
