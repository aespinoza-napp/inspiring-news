// The universe's interface: the heads-up display around the scene
// (search, modes, the legend, the story panel, the list, For you and the
// account), wired to the backend's /map and /account routes.

import { account, api, madridToday, NO_GROUP, photoUrl, type Interest, type Links, type Photo, type SearchResult, type Universe } from "./data";
import { GROUP_COLORS, KINDS, kindOf, UniverseScene, type KindKey, type NetworkNode } from "./scene";

// Not "today": at the 30-60 stories a day the newsroom publishes, one day
// is too few stars to read as a picture (the author, 29 Oct).
type Mode = "universe" | "week" | "foryou";

const WEEK_DAYS = 7;

// The names drawn above the galaxy: in two stories at least (or in any,
// when the reader asks for every name), the most named first, at most this
// many, and the biggest labelled in space - few or many, as the reader
// chooses (17 Nov: "I want to see more entities"). All of them are one
// Points and one LineSegments, so two thousand cost what three hundred do.
const MAX_NODES = 2000;
const LABELS_FEW = 14;
const LABELS_MANY = 60;

// A name whose stories are this much about one topic floats over it;
// below, over the centre. And how far names of one topic scatter (map
// units: under the 0.287 between two topics' anchors).
const BROAD_SHARE = 0.2;
const NAME_SCATTER = 0.11;

// Three numbers in [0, 1) from a name's key: the same scatter on every
// visit, for every reader (FNV-1a, then two more mixes).
function scatter(key: string): [number, number, number] {
  let h = 2166136261;
  for (let i = 0; i < key.length; i++) {
    h ^= key.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  const next = () => {
    h ^= h >>> 15;
    h = Math.imul(h, 2246822519);
    h ^= h >>> 13;
    return (h >>> 0) / 4294967296;
  };
  return [next(), next(), next()];
}

// Photos floating over the stories (20 Nov: "the photography is so
// important in the news"): always the selected story's and its connected
// ones'; the stories in view nearest the camera, a few from afar and more
// near the island; and every story in focus when the focus is this small
// (a name's stories, For you).
const FAR_PHOTOS = 8;
const NEAR_PHOTOS = 18;
const NEAR_VIEW = 12;
const ALL_PHOTOS_UNDER = 24;

const READER_BASE = import.meta.env.PUBLIC_READER_BASE ?? "";
const LOCAL_INTERESTS = "inspiring-news:interests";
const MIN_CHOICES = 3;

const $ = <T extends HTMLElement = HTMLElement>(selector: string) => document.querySelector(selector) as T;

function escape(text: string): string {
  return text.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);
}

// A story's WordPress labels, beside ours: its categories and tags as the
// site has them, the topics of ours they point to, and, when our classifier
// gave it no topic, that its place comes from them.
function wordpressLabels(wp: NonNullable<Links["wordpress"]>): string {
  const chip = (text: string, extra = "") => `<span class="chip static${extra}">${escape(text)}</span>`;
  return `
    <p class="hud-label">On the WordPress site</p>
    <div class="chips">${wp.categories.map((c) => chip(c, " category")).join("")}${wp.tags.map((t) => chip(`#${t}`)).join("")}</div>
    ${wp.topics.length ? `<p class="muted small">Its labels point to ${wp.topics.map((t) => escape(t.name)).join(", ")}.</p>` : ""}
    ${wp.topicFrom === "WordPress" ? `<p class="muted small">Placed by these labels: our classifier gave it no topic.</p>` : ""}`;
}

// A story's thumbnail in a list: decorative, its title follows it.
function thumb(src: string | null | undefined): string {
  return src ? `<img class="thumb" src="${escape(src)}" alt="" loading="lazy" decoding="async" />` : `<span class="thumb none" aria-hidden="true"></span>`;
}

function verdictText(verdict: string | null): string {
  return verdict ? verdict.replace(/_/g, " ").toLowerCase() : "not checked";
}

// Browser storage can be missing or refuse: the app works without it.
function readLocal(): Interest[] {
  try {
    const parsed = JSON.parse(window.localStorage.getItem(LOCAL_INTERESTS) ?? "[]");
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function writeLocal(items: Interest[]): void {
  try {
    window.localStorage.setItem(LOCAL_INTERESTS, JSON.stringify(items));
  } catch {
    // Kept for this visit only.
  }
}

interface State {
  data: Universe | null;
  mode: Mode;
  section: number | null;
  strong: Set<number> | null;
  selected: number;
  // The selected story's connected ones, for their photos in space.
  related: number[];
  user: { username: string } | null;
  csrf: string | null;
  interests: Interest[];
}

export function start(): void {
  const state: State = { data: null, mode: "universe", section: null, strong: null, selected: -1, related: [], user: null, csrf: null, interests: [] };

  let scene: UniverseScene;
  try {
    scene = new UniverseScene($("#space"), {
      hover: (index, screen) => showTooltip(index, screen),
      select: (index) => select(index),
      hoverNode: (node, screen) => showNodeTooltip(node, screen),
      selectNode: (node) => selectNode(node),
    });
  } catch (error) {
    $("#loading").innerHTML = `<p>This browser could not start WebGL, so the universe cannot be drawn. <a href="${READER_BASE}/reader">Read the stories</a> instead.</p>`;
    return;
  }

  // ---- labels in space --------------------------------------------------

  const labels: { element: HTMLElement; x: number; y: number; z: number; kind: "group" | "topic"; group: number }[] = [];

  function makeLabels(data: Universe): void {
    const host = $("#labels");
    data.groups.forEach((group, i) => {
      const element = document.createElement("div");
      element.className = "space-label group";
      element.style.setProperty("--tint", GROUP_COLORS[i]);
      element.textContent = group.name;
      host.appendChild(element);
      labels.push({ element, x: Math.cos(group.angle) * 1.18, y: Math.sin(group.angle) * 1.18, z: 0.05, kind: "group", group: i });
    });
    for (const topic of data.topics) {
      const element = document.createElement("div");
      element.className = "space-label topic";
      element.textContent = topic.name;
      host.appendChild(element);
      labels.push({ element, x: topic.x, y: topic.y, z: 0.16, kind: "topic", group: data.groups.findIndex((g) => g.key === topic.group) });
    }
  }

  // ---- the network of names ---------------------------------------------

  let allNodes: NetworkNode[] = [];
  let nodes: NetworkNode[] = [];
  const kindsOn = new Set<KindKey>(KINDS.map((k) => k.key));
  let networkOn = true;
  let nodeLabels: { element: HTMLElement; node: number }[] = [];
  let minStories = 2;
  let labelledNodes = LABELS_FEW;

  function buildNetwork(data: Universe): void {
    const stories = new Map<number, number[]>();
    data.entitiesOf.forEach((refs, i) => refs.forEach((ref) => (stories.get(ref) ?? stories.set(ref, []).get(ref)!).push(i)));

    // A name floats over the topic its stories are about: above its main
    // topic's cluster, pulled towards its second as far as that one's share
    // allows, at a height that grows with its stories, scattered a little
    // (fixed by its key) so names of one topic do not sit on each other.
    // A name no topic dominates floats over the centre, higher: it
    // connects everywhere. Not a ring round the rim, which said nothing
    // about what a name is related to (the author, 29 Oct); and not the
    // mean of its stories' places, which put every broad name at the
    // centre, one on another.
    const anchors = data.topics.map((topic) => ({ x: topic.x, y: topic.y }));
    allNodes = [];
    stories.forEach((named, ref) => {
      const entity = data.entities[ref];
      const kind = entity ? kindOf(entity.t) : null;
      if (!kind || named.length < minStories) return;

      const byTopic = new Map<number, number>();
      for (const i of named) {
        const main = data.topicsOf[i]?.[0];
        if (main !== undefined) byTopic.set(main, (byTopic.get(main) ?? 0) + 1);
      }
      const ranked = Array.from(byTopic.entries()).sort((a, b) => b[1] - a[1]);
      const [r1, r2, r3] = scatter(entity.k);
      const lift = 1.1 + 0.45 * Math.log2(named.length) + 0.5 * r3;
      let x: number;
      let y: number;
      let z = lift;

      if (ranked.length && ranked[0][1] / named.length >= BROAD_SHARE) {
        const first = anchors[ranked[0][0]];
        x = first.x;
        y = first.y;
        if (ranked[1]) {
          const second = anchors[ranked[1][0]];
          const pull = 0.5 * (ranked[1][1] / (ranked[0][1] + ranked[1][1]));
          x += (second.x - first.x) * pull;
          y += (second.y - first.y) * pull;
        }
        const angle = r1 * Math.PI * 2;
        x += Math.cos(angle) * NAME_SCATTER * Math.sqrt(r2);
        y += Math.sin(angle) * NAME_SCATTER * Math.sqrt(r2);
      } else {
        const angle = r1 * Math.PI * 2;
        x = Math.cos(angle) * (0.12 + 0.2 * r2);
        y = Math.sin(angle) * (0.12 + 0.2 * r2);
        z = lift + 1.2;
      }

      allNodes.push({ key: entity.k, name: entity.n, kind, x, y, z, stories: named });
    });
    allNodes.sort((a, b) => b.stories.length - a.stories.length);
    allNodes = allNodes.slice(0, MAX_NODES);
    makeConnectionsLegend();
    applyNetwork();
  }

  function applyNetwork(): void {
    nodes = allNodes.filter((n) => kindsOn.has(n.kind));
    scene.setNetwork(nodes);
    scene.setNetworkVisible(networkOn);
    const host = $("#labels");
    nodeLabels.forEach((l) => l.element.remove());
    nodeLabels = nodes.slice(0, labelledNodes).map((node, i) => {
      const element = document.createElement("div");
      element.className = "space-label node";
      element.style.setProperty("--tint", KINDS.find((k) => k.key === node.kind)!.color);
      element.textContent = node.name;
      // A label is easier to hit than a diamond.
      element.addEventListener("click", () => selectNode(i));
      host.appendChild(element);
      return { element, node: i };
    });
  }

  function makeConnectionsLegend(): void {
    const list = $("#kinds");
    list.innerHTML = "";
    for (const kind of KINDS) {
      const count = allNodes.filter((n) => n.kind === kind.key).length;
      const item = document.createElement("li");
      item.innerHTML = `<button type="button" aria-pressed="true"><span class="diamond" style="--tint:${kind.color}"></span>${kind.label}<span class="count">${count}</span></button>`;
      item.querySelector("button")!.addEventListener("click", (event) => {
        const button = event.currentTarget as HTMLButtonElement;
        if (kindsOn.has(kind.key)) kindsOn.delete(kind.key);
        else kindsOn.add(kind.key);
        button.setAttribute("aria-pressed", String(kindsOn.has(kind.key)));
        applyNetwork();
      });
      list.appendChild(item);
    }
  }

  // How many names, and how many labelled: two small switches under the kinds.
  function pressOnly(selector: string, pressed: HTMLElement): void {
    document.querySelectorAll<HTMLButtonElement>(selector).forEach((b) => b.setAttribute("aria-pressed", String(b === pressed)));
  }
  document.querySelectorAll<HTMLButtonElement>("[data-min-stories]").forEach((button) =>
    button.addEventListener("click", () => {
      minStories = Number(button.dataset.minStories);
      pressOnly("[data-min-stories]", button);
      if (state.data) buildNetwork(state.data);
    }),
  );
  document.querySelectorAll<HTMLButtonElement>("[data-labels]").forEach((button) =>
    button.addEventListener("click", () => {
      labelledNodes = button.dataset.labels === "many" ? LABELS_MANY : LABELS_FEW;
      pressOnly("[data-labels]", button);
      applyNetwork();
    }),
  );

  const networkButton = $("#network-button");
  networkButton.addEventListener("click", () => {
    networkOn = !networkOn;
    networkButton.setAttribute("aria-pressed", String(networkOn));
    networkButton.textContent = networkOn ? "on" : "off";
    scene.setNetworkVisible(networkOn);
  });

  function showNodeTooltip(node: number, screen: { x: number; y: number } | null): void {
    const tip = $("#tooltip");
    const n = nodes[node];
    if (node < 0 || !screen || !n) {
      tip.hidden = true;
      return;
    }
    const kind = KINDS.find((k) => k.key === n.kind)!;
    tip.innerHTML = `<strong>${escape(n.name)}</strong><span>${kind.one} · named in ${n.stories.length} stories</span>`;
    tip.style.left = `${Math.min(screen.x + 16, window.innerWidth - 320)}px`;
    tip.style.top = `${screen.y + 16}px`;
    tip.hidden = false;
  }

  function selectNode(node: number): void {
    const data = state.data;
    const n = nodes[node];
    if (!data || !n) return;
    state.selected = -1;
    state.related = [];
    scene.mark(-1);
    scene.setLinks(-1, []);
    state.strong = new Set(n.stories);
    state.section = null;
    refresh();
    status(state.strong, `named ${n.name}`);
    scene.highlightNode(node);
    scene.flyToNode(node);

    const kind = KINDS.find((k) => k.key === n.kind)!;
    const newest = [...n.stories].sort((a, b) => (data.days[b] ?? "").localeCompare(data.days[a] ?? "")).slice(0, 40);
    const panel = $("#panel");
    panel.hidden = false;
    panel.innerHTML = `
      <button type="button" class="close" aria-label="Close">×</button>
      <p class="hud-label" style="color:${kind.color}">${kind.one}</p>
      <h2>${escape(n.name)}</h2>
      <p class="muted">Named in ${n.stories.length} stories${n.stories.length > newest.length ? `; the ${newest.length} newest` : ""}:</p>
      <ol class="related with-thumbs">${newest.map((i) => `<li>${thumb(data.thumbs[i])}<div><button type="button" class="link" data-story="${data.ids[i]}">${escape(data.titles[i])}</button><span class="muted"> · ${escape(data.sources[data.sourceOf[i]])}${data.days[i] ? ` · ${data.days[i]}` : ""}</span></div></li>`).join("")}</ol>`;
    panel.querySelector(".close")!.addEventListener("click", () => {
      panel.hidden = true;
      scene.highlightNode(-1);
      state.strong = null;
      refresh();
    });
    panel.querySelectorAll<HTMLButtonElement>("[data-story]").forEach((b) => b.addEventListener("click", () => void select(data.indexOf.get(b.dataset.story!)!)));
  }

  // ---- photos in space ----------------------------------------------------

  type PhotoKind = "selected" | "related" | "near";
  const photoLayer = $("#photos");
  const floating = new Map<number, { element: HTMLButtonElement; kind: PhotoKind }>();
  let photosOn = true;
  let photoFrame = 0;

  function inFocus(i: number): boolean {
    return (!state.strong || state.strong.has(i)) && (state.section === null || state.data!.group[i] === state.section);
  }

  // Which stories show their photo now, and how.
  function wantedPhotos(): Map<number, PhotoKind> {
    const data = state.data;
    const wanted = new Map<number, PhotoKind>();
    if (!data || !photosOn) return wanted;

    if (state.selected >= 0 && data.images[state.selected]) wanted.set(state.selected, "selected");
    for (const i of state.related) if (data.thumbs[i] && !wanted.has(i)) wanted.set(i, "related");

    const focus = state.strong && state.section === null ? state.strong : null;
    if (focus && focus.size <= ALL_PHOTOS_UNDER) {
      for (const i of focus) if (data.thumbs[i] && !wanted.has(i)) wanted.set(i, "near");
      return wanted;
    }

    const seen: { i: number; d: number }[] = [];
    for (let i = 0; i < data.count; i++) {
      if (!data.thumbs[i] || wanted.has(i) || !inFocus(i)) continue;
      const p = scene.projectStory(i);
      if (p && !underHud(p.x, p.y - 40)) seen.push({ i, d: p.distance });
    }
    seen.sort((a, b) => a.d - b.d);
    for (const { i } of seen.slice(0, scene.viewDistance < NEAR_VIEW ? NEAR_PHOTOS : FAR_PHOTOS)) wanted.set(i, "near");
    return wanted;
  }

  // The panels over the scene, measured with each choice of photos: a photo
  // whose story is under one is not drawn through the glass.
  let hud: DOMRect[] = [];
  function measureHud(): void {
    hud = [".top", ".legend", "#panel", ".status"]
      .map((selector) => document.querySelector<HTMLElement>(selector))
      .filter((element): element is HTMLElement => Boolean(element) && !element!.hidden)
      .map((element) => element.getBoundingClientRect());
  }
  function underHud(x: number, y: number): boolean {
    if (x < 0 || y < 0 || x > window.innerWidth || y > window.innerHeight) return true;
    return hud.some((r) => x > r.left - 24 && x < r.right + 24 && y > r.top - 24 && y < r.bottom + 24);
  }

  function syncPhotos(): void {
    const data = state.data;
    if (!data) return;
    measureHud();
    const wanted = wantedPhotos();
    for (const [i, shown] of floating) {
      if (wanted.get(i) !== shown.kind) {
        shown.element.remove();
        floating.delete(i);
      }
    }
    for (const [i, kind] of wanted) {
      if (floating.has(i)) continue;
      const element = document.createElement("button");
      element.type = "button";
      element.className = `space-photo ${kind}`;
      element.tabIndex = -1;
      element.title = data.titles[i];
      const src = kind === "selected" ? data.images[i] : data.thumbs[i];
      element.innerHTML = `<img src="${escape(src!)}" alt="" decoding="async" />`;
      if (kind !== "selected" && data.group[i] !== NO_GROUP) element.style.setProperty("--tint", GROUP_COLORS[data.group[i]]);
      element.addEventListener("click", () => (i === state.selected ? openPhoto(data.images[i]!, data.titles[i], null) : void select(i)));
      element.addEventListener("pointerenter", () => {
        const box = element.getBoundingClientRect();
        showTooltip(i, { x: box.right - 8, y: box.top });
      });
      element.addEventListener("pointerleave", () => showTooltip(-1, null));
      photoLayer.appendChild(element);
      floating.set(i, { element, kind });
    }
  }

  function placePhotos(): void {
    for (const [i, shown] of floating) {
      const p = scene.projectStory(i);
      const emphasis = scene.emphasisOf(i);
      if (!p || emphasis < 0.2 || underHud(p.x, p.y - 40)) {
        shown.element.style.opacity = "0";
        continue;
      }
      // Nearer is larger and on top; the selected one stays readable at any distance.
      const scale = shown.kind === "selected" ? 1 : Math.max(0.55, Math.min(1.35, 7 / p.distance));
      shown.element.style.opacity = "1";
      shown.element.style.zIndex = String(shown.kind === "selected" ? 9999 : Math.round(5000 - p.distance * 100));
      shown.element.style.transform = `translate(${p.x}px, ${p.y}px) translate(-50%, calc(-100% - 10px)) scale(${scale.toFixed(3)})`;
    }
  }

  const photosButton = $("#photos-button");
  function setPhotos(on: boolean): void {
    photosOn = on;
    photosButton.setAttribute("aria-pressed", String(on));
    photosButton.textContent = on ? "on" : "off";
    syncPhotos();
  }
  photosButton.addEventListener("click", () => setPhotos(!photosOn));

  // ---- a photo, large ------------------------------------------------------

  function openPhoto(src: string, alt: string, caption: string | null): void {
    const image = $<HTMLImageElement>("#photo-large");
    image.src = src;
    image.alt = alt;
    $("#photo-caption").textContent = caption ?? "";
    $("#photo-caption").hidden = !caption;
    open("#photo-overlay");
  }

  scene.onFrame = () => {
    // Which photos float is decided every few frames (a pass over every
    // story when near); where they are, every frame, as the island turns.
    if (photoFrame++ % 12 === 0) syncPhotos();
    placePhotos();
    for (const label of nodeLabels) {
      const p = networkOn ? scene.projectNode(label.node) : null;
      label.element.style.opacity = p ? "1" : "0";
      if (p) label.element.style.transform = `translate(${p.x}px, ${p.y}px) translate(-50%, -140%)`;
    }
    for (const label of labels) {
      const p = scene.project(label.x, label.y, label.z);
      // Topics only when the camera is near enough for them to be apart,
      // and with a section in focus, only that section's names.
      const inFocus = state.section === null || label.group === state.section;
      const visible = p !== null && inFocus && (label.kind === "group" || p.distance < 11);
      label.element.style.opacity = visible ? (label.kind === "topic" ? String(Math.min(1, (11 - p!.distance) / 3)) : "1") : "0";
      if (p) label.element.style.transform = `translate(${p.x}px, ${p.y}px) translate(-50%, -50%)`;
    }
  };

  // ---- loading ------------------------------------------------------------

  api
    .universe()
    .then((data) => {
      state.data = data;
      scene.setData(data);
      makeLabels(data);
      makeLegend(data);
      buildNetwork(data);
      // A map with no photos (the lake's, the synthetic preview) has no switch for them.
      if (!data.images.some(Boolean)) photosButton.closest("p")!.hidden = true;
      $("#loading").classList.add("gone");
      setTimeout(() => $("#loading").remove(), 1200);
      const shared = new URLSearchParams(window.location.search);
      const mode = shared.get("mode") as Mode | null;
      if (mode === "week" || mode === "foryou") setMode(mode);
      else refresh();
      const story = shared.get("story");
      if (story && data.indexOf.has(story)) select(data.indexOf.get(story)!);
    })
    .catch((error: Error) => {
      $("#loading").innerHTML = `<p>The universe could not be loaded: ${escape(error.message)}</p>`;
    });

  void loadAccount();

  // ---- what is shown ------------------------------------------------------

  function refresh(): void {
    const data = state.data;
    if (!data) return;
    let strong = state.strong;
    if (state.section !== null) {
      const inSection = new Set<number>();
      for (let i = 0; i < data.count; i++) if (data.group[i] === state.section && (!strong || strong.has(i))) inSection.add(i);
      strong = inSection;
    }
    scene.focus(strong);
    status(strong);
  }

  function status(strong: Set<number> | null, note = ""): void {
    const data = state.data!;
    const shown = strong ? strong.size : data.count;
    const mode = { universe: "", week: "the last week", foryou: "for you" }[state.mode];
    const where = state.section !== null ? data.groups[state.section].name : mode || note ? "" : "the whole universe";
    const parts = [`${shown.toLocaleString()} of ${data.count.toLocaleString()} stories`, mode, where, note].filter(Boolean);
    $("#status").textContent = parts.join(" · ");
  }

  async function setMode(mode: Mode): Promise<void> {
    const data = state.data;
    if (!data) return;
    state.mode = mode;
    document.querySelectorAll<HTMLButtonElement>(".modes button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.mode === mode)));
    const url = new URL(window.location.href);
    if (mode === "universe") url.searchParams.delete("mode");
    else url.searchParams.set("mode", mode);
    window.history.replaceState(null, "", url);

    if (mode === "universe") {
      state.strong = null;
      refresh();
      return;
    }

    if (mode === "week") {
      // The seven days to today, Madrid's; with nothing in them, the
      // seven days to the newest story, and the status says so.
      const days = Array.from(new Set(data.days.filter((d): d is string => Boolean(d)))).sort().reverse();
      const today = madridToday();
      const recent = (end: string) => {
        const start = new Date(`${end}T12:00:00Z`);
        start.setUTCDate(start.getUTCDate() - (WEEK_DAYS - 1));
        return start.toISOString().slice(0, 10);
      };
      let end = today;
      if (!days.some((d) => d <= end && d >= recent(end))) end = days[0] ?? today;
      const start = recent(end);
      state.strong = new Set<number>();
      for (let i = 0; i < data.count; i++) {
        const day = data.days[i];
        if (day && day >= start && day <= end) state.strong.add(i);
      }
      refresh();
      status(state.strong, end === today ? `${start} to today` : `nothing this week: ${start} to ${end}`);
      return;
    }

    // For you: at least three interests first.
    if (state.interests.length < MIN_CHOICES) {
      openChooser();
      return;
    }
    try {
      const answer = await api.forYou({ interests: state.interests.map(({ kind, key }) => ({ kind, key })), limit: 40 });
      state.strong = new Set(answer.items.map((item) => data.indexOf.get(item.id)).filter((i): i is number => i !== undefined));
      refresh();
      showForYou(answer.items);
    } catch (error) {
      status(null, (error as Error).message);
    }
  }

  document.querySelectorAll<HTMLButtonElement>(".modes button").forEach((button) =>
    button.addEventListener("click", () => void setMode(button.dataset.mode as Mode)),
  );

  // ---- legend -------------------------------------------------------------

  function makeLegend(data: Universe): void {
    const list = $("#legend");
    data.groups.forEach((group, i) => {
      const item = document.createElement("li");
      item.innerHTML = `<button type="button" aria-pressed="false"><span class="dot" style="--tint:${GROUP_COLORS[i]}"></span>${escape(group.name)}<span class="count"></span></button>`;
      let n = 0;
      for (let s = 0; s < data.count; s++) if (data.group[s] === i) n++;
      item.querySelector(".count")!.textContent = n.toLocaleString();
      item.querySelector("button")!.addEventListener("click", () => {
        state.section = state.section === i ? null : i;
        list.querySelectorAll("button").forEach((b, j) => b.setAttribute("aria-pressed", String(state.section === j)));
        refresh();
        if (state.section === null) scene.home();
        else scene.flyTo(Math.cos(group.angle) * 0.74, Math.sin(group.angle) * 0.74, 0, 7);
      });
      list.appendChild(item);
    });
  }

  $("#home-button").addEventListener("click", () => scene.home());
  const motionButton = $("#motion-button");
  motionButton.setAttribute("aria-pressed", String(scene.moving));
  motionButton.addEventListener("click", () => {
    scene.setMotion(!scene.moving);
    motionButton.setAttribute("aria-pressed", String(scene.moving));
  });
  $("#list-button").addEventListener("click", openList);

  // ---- the selected story -------------------------------------------------

  function showTooltip(index: number, screen: { x: number; y: number } | null): void {
    const tip = $("#tooltip");
    const data = state.data;
    if (index < 0 || !screen || !data) {
      tip.hidden = true;
      return;
    }
    const photo = data.images[index] ?? data.thumbs[index];
    tip.classList.toggle("with-photo", Boolean(photo));
    tip.innerHTML = `${photo ? `<img src="${escape(photo)}" alt="" decoding="async" />` : ""}<strong>${escape(data.titles[index])}</strong><span>${escape(data.sources[data.sourceOf[index]])}${data.days[index] ? ` · ${data.days[index]}` : ""} · ${verdictText(data.verdicts[index])}</span>`;
    tip.style.left = `${Math.min(screen.x + 16, window.innerWidth - 320)}px`;
    tip.style.top = `${screen.y + 16}px`;
    tip.hidden = false;
  }

  async function select(index: number): Promise<void> {
    const data = state.data;
    const panel = $("#panel");
    state.selected = index;
    state.related = [];
    scene.mark(index);
    const url = new URL(window.location.href);

    if (index < 0 || !data) {
      panel.hidden = true;
      scene.setLinks(-1, []);
      url.searchParams.delete("story");
      window.history.replaceState(null, "", url);
      return;
    }

    url.searchParams.set("story", data.ids[index]);
    window.history.replaceState(null, "", url);
    scene.flyTo(data.positions[index * 3], data.positions[index * 3 + 1], data.positions[index * 3 + 2], 3.2);

    panel.hidden = false;
    const hero = data.images[index];
    panel.innerHTML = `
      <button type="button" class="close" aria-label="Close">×</button>
      ${hero ? `<figure class="photo-hero"><button type="button" class="photo-open" aria-label="Open the photo"><img id="panel-photo" src="${escape(hero)}" alt="" decoding="async" /></button><figcaption id="panel-photo-caption" hidden></figcaption></figure>` : ""}
      <p class="hud-label" style="color:${data.group[index] === NO_GROUP ? "#8a90a6" : GROUP_COLORS[data.group[index]]}">${data.group[index] === NO_GROUP ? "Not placed" : escape(data.groups[data.group[index]].name)}</p>
      <h2>${escape(data.titles[index])}</h2>
      <p class="muted">${escape(data.sources[data.sourceOf[index]])}${data.days[index] ? ` · ${data.days[index]}` : ""}</p>
      <p><span class="verdict v-${(data.verdicts[index] ?? "none").toLowerCase()}">${verdictText(data.verdicts[index])}</span></p>
      <p><a class="primary-link" href="${READER_BASE}/reader/${data.ids[index]}">Read the story and its checks →</a></p>
      <div id="panel-links"><p class="muted">Tracing its connections…</p></div>`;
    panel.querySelector(".close")!.addEventListener("click", () => void select(-1));
    let main: Photo | null = hero ? { src: hero, thumb: data.thumbs[index], full: null, alt: null, caption: null, featured: true } : null;
    panel.querySelector(".photo-open")?.addEventListener("click", () => {
      // main's addresses are resolved already (photoUrl), once.
      if (main) openPhoto(main.full ?? main.src, main.alt ?? data.titles[index], main.caption);
    });
    syncPhotos();

    let links: Links;
    try {
      links = await api.links(data.ids[index]);
    } catch (error) {
      $("#panel-links").innerHTML = `<p class="error">Its connections could not be loaded (${escape((error as Error).message)}).</p>`;
      return;
    }
    if (state.selected !== index) return;

    // The photos, as served: the main one's alt and caption, and the rest of the post's.
    const photos = (links.photos ?? [])
      .map((photo) => ({ ...photo, src: photoUrl(photo.src)!, thumb: photoUrl(photo.thumb), full: photoUrl(photo.full) }))
      .filter((photo) => photo.src);
    if (main && photos[0]) {
      main = photos[0];
      $<HTMLImageElement>("#panel-photo").alt = main.alt ?? "";
      const caption = $("#panel-photo-caption");
      caption.textContent = main.caption ?? "";
      caption.hidden = !main.caption;
    }
    state.related = links.related.map((r) => data.indexOf.get(r.id)).filter((j): j is number => j !== undefined);
    syncPhotos();

    scene.setLinks(
      index,
      links.related.map((r) => {
        const j = data.indexOf.get(r.id);
        return j !== undefined ? { x: data.positions[j * 3], y: data.positions[j * 3 + 1], z: data.positions[j * 3 + 2] } : { x: r.x, y: r.y };
      }),
    );

    const followed = (kind: string, key: string) => state.interests.some((i) => i.kind === kind && i.key === key);
    const gallery = photos.slice(main ? 1 : 0);
    $("#panel-links").innerHTML = `
      ${gallery.length ? `<p class="hud-label">Its photos</p><div class="gallery">${gallery.map((photo, g) => `<button type="button" class="gallery-photo" data-photo="${g}" aria-label="${escape(photo.alt ?? photo.caption ?? "A photo of the story")}"><img src="${escape(photo.thumb ?? photo.src)}" alt="" loading="lazy" decoding="async" /></button>`).join("")}</div>` : ""}
      <p class="hud-label">Topics</p>
      <div class="chips">${links.topics.map((t) => `<button type="button" class="chip" data-follow="topic" data-key="${escape(t.key)}" data-label="${escape(t.name)}" aria-pressed="${followed("topic", t.key)}">${followed("topic", t.key) ? "✓ " : "+ "}${escape(t.name)}</button>`).join("")}</div>
      ${links.entities.length ? `<p class="hud-label">Names</p><div class="chips">${links.entities.map((e) => `<button type="button" class="chip" data-entity="${escape(e.key)}">${escape(e.name)}${e.articles > 1 ? ` · ${e.articles}` : ""}</button>`).join("")}</div>` : ""}
      ${links.wordpress ? wordpressLabels(links.wordpress) : ""}
      <p class="hud-label">Connected</p>
      ${links.related.length ? `<ol class="related with-thumbs">${links.related.map((r) => `<li>${thumb(photoUrl(r.thumb))}<div><button type="button" class="link" data-story="${r.id}">${escape(r.title)}</button><span class="muted"> ${escape(r.via.slice(0, 2).map((v) => (v.kind === "entity" ? `both name ${v.via}` : v.kind === "topic" ? `both about ${v.via}` : v.kind === "claim" ? "the same claim" : "a shared source")).join("; "))}</span></div></li>`).join("")}</ol>` : `<p class="muted">Nothing else published shares a claim, a source, a name or a topic with it yet.</p>`}`;

    $("#panel-links").querySelectorAll<HTMLButtonElement>("[data-photo]").forEach((b) =>
      b.addEventListener("click", () => {
        const photo = gallery[Number(b.dataset.photo)];
        openPhoto(photo.full ?? photo.src, photo.alt ?? data.titles[index], photo.caption);
      }),
    );

    $("#panel-links").querySelectorAll<HTMLButtonElement>("[data-story]").forEach((b) =>
      b.addEventListener("click", () => {
        const j = data.indexOf.get(b.dataset.story!);
        if (j !== undefined) void select(j);
      }),
    );
    $("#panel-links").querySelectorAll<HTMLButtonElement>("[data-entity]").forEach((b) => b.addEventListener("click", () => focusEntity(b.dataset.entity!)));
    $("#panel-links").querySelectorAll<HTMLButtonElement>("[data-follow]").forEach((b) =>
      b.addEventListener("click", async () => {
        const item: Interest = { kind: b.dataset.follow as Interest["kind"], key: b.dataset.key!, label: b.dataset.label! };
        await toggleInterest(item);
        void select(index);
      }),
    );
  }

  function focusEntity(key: string): void {
    const data = state.data!;
    const ref = data.entities.findIndex((e) => e.k === key);
    const strong = new Set<number>();
    data.entitiesOf.forEach((refs, i) => refs.includes(ref) && strong.add(i));
    state.strong = strong;
    state.section = null;
    refresh();
    const name = data.entities[ref]?.n ?? key.split(":").slice(1).join(":");
    status(strong, `the stories naming ${name}`);
  }

  // ---- search -------------------------------------------------------------

  const input = $<HTMLInputElement>("#search-input");
  const results = $<HTMLUListElement>("#search-results");
  let active = -1;
  let found: SearchResult[] = [];
  let typing = 0;

  function showResults(items: SearchResult[], note: string): void {
    found = items;
    active = -1;
    results.innerHTML =
      items.map((r, i) => `<li role="option" id="result-${i}" data-i="${i}"><span class="kind">${r.kind === "entity" ? "Name" : "Story"}</span>${escape(r.kind === "entity" ? `${r.name} · ${r.articles}` : r.title ?? "")}<span class="muted"> · ${escape(r.reason)}</span></li>`).join("") +
      `<li class="note" aria-disabled="true">${items.length ? note : "Nothing published matches."}</li>`;
    results.hidden = false;
    input.setAttribute("aria-expanded", "true");
    results.querySelectorAll<HTMLLIElement>("[data-i]").forEach((li) => {
      li.addEventListener("mousedown", (e) => e.preventDefault());
      li.addEventListener("click", () => choose(found[Number(li.dataset.i)]));
    });
  }

  function choose(result: SearchResult): void {
    results.hidden = true;
    input.setAttribute("aria-expanded", "false");
    const data = state.data!;
    if (result.kind === "article" && result.id && data.indexOf.has(result.id)) void select(data.indexOf.get(result.id)!);
    if (result.kind === "entity" && result.key) {
      focusEntity(result.key);
      scene.flyTo(result.x, result.y, 0, 6);
    }
  }

  input.addEventListener("input", () => {
    window.clearTimeout(typing);
    if (!input.value.trim()) {
      results.hidden = true;
      return;
    }
    // Names and words only while typing: no embedding per keystroke.
    typing = window.setTimeout(() => {
      api.search(input.value, false).then((a) => showResults(a.results, "Press Enter to search by meaning too.")).catch(() => undefined);
    }, 160);
  });

  input.addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      active = Math.max(-1, Math.min(found.length - 1, active + (event.key === "ArrowDown" ? 1 : -1)));
      results.querySelectorAll("[data-i]").forEach((li, i) => li.classList.toggle("active", i === active));
      input.setAttribute("aria-activedescendant", active >= 0 ? `result-${active}` : "");
    } else if (event.key === "Enter") {
      event.preventDefault();
      if (active >= 0) choose(found[active]);
      else api.search(input.value, true).then((a) => showResults(a.results, a.semantic === "used" ? "By name, word and meaning." : "By name and word.")).catch((e: Error) => showResults([], e.message));
    } else if (event.key === "Escape") {
      results.hidden = true;
      input.blur();
    }
  });
  input.addEventListener("blur", () => setTimeout(() => (results.hidden = true), 150));

  // ---- the list -------------------------------------------------------------

  function openList(): void {
    const data = state.data;
    if (!data) return;
    const shown: number[] = [];
    for (let i = 0; i < data.count && shown.length < 300; i++) {
      if ((!state.strong || state.strong.has(i)) && (state.section === null || data.group[i] === state.section)) shown.push(i);
    }
    $("#list").innerHTML = shown
      .map((i) => `<li>${thumb(data.thumbs[i])}<div><a href="${READER_BASE}/reader/${data.ids[i]}">${escape(data.titles[i])}</a><span class="muted"> · ${escape(data.sources[data.sourceOf[i]])}${data.days[i] ? ` · ${data.days[i]}` : ""} · ${data.group[i] === NO_GROUP ? "" : escape(data.groups[data.group[i]].name)}</span></div></li>`)
      .join("");
    open("#list-overlay");
  }

  function showForYou(items: { id: string; title: string; reasons: string[] }[]): void {
    const panel = $("#panel");
    panel.hidden = false;
    panel.innerHTML = `
      <button type="button" class="close" aria-label="Close">×</button>
      <p class="hud-label">For you</p>
      <h2>Your stories</h2>
      <p class="muted">Following ${escape(state.interests.map((i) => i.label).join(", "))}. <button type="button" class="link" id="change-interests">Change</button></p>
      <ol class="related with-thumbs">${items.map((item) => `<li>${thumb(state.data!.thumbs[state.data!.indexOf.get(item.id) ?? -1])}<div><button type="button" class="link" data-story="${item.id}">${escape(item.title)}</button><span class="muted"> because ${escape(item.reasons.join("; ") || "it is new")}</span></div></li>`).join("")}</ol>`;
    panel.querySelector(".close")!.addEventListener("click", () => (panel.hidden = true));
    $("#change-interests").addEventListener("click", openChooser);
    panel.querySelectorAll<HTMLButtonElement>("[data-story]").forEach((b) => b.addEventListener("click", () => void select(state.data!.indexOf.get(b.dataset.story!)!)));
  }

  // ---- For you's chooser ---------------------------------------------------

  function openChooser(): void {
    const data = state.data!;
    const chosen = [...state.interests];
    const host = $("#chooser");
    const has = (kind: string, key: string) => chosen.some((i) => i.kind === kind && i.key === key);
    const draw = () => {
      host.innerHTML = data.groups
        .map(
          (g, gi) => `<fieldset><legend><button type="button" class="chip section" style="--tint:${GROUP_COLORS[gi]}" data-kind="group" data-key="${g.key}" data-label="${escape(g.name)}" aria-pressed="${has("group", g.key)}">${has("group", g.key) ? "✓ " : ""}${escape(g.name)}, all of it</button></legend>
          <div class="chips">${data.topics.filter((t) => t.group === g.key).map((t) => `<button type="button" class="chip" data-kind="topic" data-key="${t.key}" data-label="${escape(t.name)}" aria-pressed="${has("topic", t.key)}">${has("topic", t.key) ? "✓ " : ""}${escape(t.name)}</button>`).join("")}</div></fieldset>`,
        )
        .join("");
      host.querySelectorAll<HTMLButtonElement>("[data-kind]").forEach((b) =>
        b.addEventListener("click", () => {
          const item: Interest = { kind: b.dataset.kind as Interest["kind"], key: b.dataset.key!, label: b.dataset.label! };
          const at = chosen.findIndex((i) => i.kind === item.kind && i.key === item.key);
          if (at >= 0) chosen.splice(at, 1);
          else chosen.push(item);
          draw();
        }),
      );
      const done = $<HTMLButtonElement>("#chooser-done");
      done.disabled = chosen.length < MIN_CHOICES;
      done.textContent = chosen.length < MIN_CHOICES ? `Choose ${MIN_CHOICES - chosen.length} more` : `Show my stories (${chosen.length})`;
      done.onclick = async () => {
        await saveInterests(chosen);
        close("#chooser-overlay");
        void setMode("foryou");
      };
    };
    draw();
    open("#chooser-overlay");
  }

  async function saveInterests(items: Interest[]): Promise<void> {
    state.interests = items;
    if (state.user) {
      const answer = await account<{ items: Interest[] }>("interests/set", { items: items.map(({ kind, key }) => ({ kind, key })) }, state.csrf).catch(() => null);
      if (answer) state.interests = answer.items;
    } else {
      writeLocal(items);
    }
  }

  async function toggleInterest(item: Interest): Promise<void> {
    const at = state.interests.findIndex((i) => i.kind === item.kind && i.key === item.key);
    await saveInterests(at >= 0 ? state.interests.filter((_, j) => j !== at) : [...state.interests, item]);
  }

  // ---- the account --------------------------------------------------------

  async function loadAccount(): Promise<void> {
    try {
      const me = await account<{ user: { username: string }; csrf: string }>("me");
      state.user = me?.user ?? null;
      state.csrf = me?.csrf ?? null;
      const interests = state.user ? await account<{ items: Interest[] }>("interests") : null;
      state.interests = interests?.items ?? [];
    } catch {
      state.user = null;
      state.interests = readLocal();
    }
    $("#account-button").textContent = state.user ? `◉ ${state.user.username}` : "Sign in";
  }

  $("#account-button").addEventListener("click", () => {
    drawAccount();
    open("#account-overlay");
  });

  function drawAccount(): void {
    const host = $("#account");
    if (state.user) {
      host.innerHTML = `<p>Signed in as <strong>${escape(state.user.username)}</strong>.</p>
        <p class="muted">You follow ${state.interests.length ? escape(state.interests.map((i) => i.label).join(", ")) : "nothing yet"}.</p>
        <button type="button" id="sign-out" class="primary">Sign out</button>`;
      $("#sign-out").addEventListener("click", async () => {
        await account("logout", {}, state.csrf).catch(() => null);
        await loadAccount();
        drawAccount();
      });
      return;
    }
    host.innerHTML = `<form id="sign-in" class="form">
        <label>Username <input name="username" autocomplete="username" required minlength="3" maxlength="32" /></label>
        <label>Password <input name="password" type="password" autocomplete="current-password" required minlength="10" maxlength="128" /></label>
        <p id="account-error" class="error" hidden></p>
        <div class="row"><button type="submit" class="primary" data-action="login">Sign in</button><button type="submit" class="ghost" data-action="register">Create an account</button></div>
        <p class="muted">An account keeps what you follow. Your password is kept as an argon2id hash, never itself; one cookie, the session; no tracking.</p>
      </form>`;
    const form = $<HTMLFormElement>("#sign-in");
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const action = ((event as SubmitEvent).submitter as HTMLButtonElement | null)?.dataset.action ?? "login";
      const fields = new FormData(form);
      try {
        await account(action, { username: fields.get("username"), password: fields.get("password") });
        const local = readLocal();
        await loadAccount();
        if (local.length && !state.interests.length) await saveInterests(local);
        close("#account-overlay");
      } catch (error) {
        const message = $("#account-error");
        message.textContent = (error as Error).message;
        message.hidden = false;
      }
    });
  }

  // ---- overlays and keys -----------------------------------------------------

  function open(selector: string): void {
    const overlay = $(selector);
    overlay.hidden = false;
    overlay.querySelector<HTMLElement>("button, a, input")?.focus();
  }

  function close(selector: string): void {
    $(selector).hidden = true;
  }

  document.querySelectorAll<HTMLElement>(".overlay").forEach((overlay) => {
    overlay.addEventListener("click", (event) => {
      if (event.target === overlay || (event.target as HTMLElement).closest("[data-close]")) overlay.hidden = true;
    });
  });

  document.addEventListener("keydown", (event) => {
    const typingIn = (event.target as HTMLElement).closest("input, textarea");
    if (event.key === "Escape") {
      document.querySelectorAll<HTMLElement>(".overlay").forEach((o) => (o.hidden = true));
      if (!typingIn) void select(-1);
      return;
    }
    if (typingIn) return;
    if (event.key === "/") {
      event.preventDefault();
      input.focus();
    } else if (event.key === "h") scene.home();
    else if (event.key === "m") motionButton.click();
    else if (event.key === "l") openList();
    else if (event.key === "p") setPhotos(!photosOn);
  });
}
