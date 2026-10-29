// The universe's interface: the heads-up display around the scene
// (search, modes, the legend, the story panel, the list, For you and the
// account), wired to the backend's /map and /account routes.

import { account, api, madridToday, NO_GROUP, type Interest, type Links, type SearchResult, type Universe } from "./data";
import { GROUP_COLORS, KINDS, kindOf, UniverseScene, type KindKey, type NetworkNode } from "./scene";

// Not "today": at the 30-60 stories a day the newsroom publishes, one day
// is too few stars to read as a picture (the author, 29 Oct).
type Mode = "universe" | "week" | "foryou";

const WEEK_DAYS = 7;

// The names drawn above the galaxy: in two stories at least, the most
// named first, at most this many, and the biggest labelled in space.
const MAX_NODES = 300;
const LABELLED_NODES = 14;

// The crown: its rings' radius (map units, just inside the disc's rim),
// the lowest ring's height and the step between rings (world units).
const CROWN_RADIUS = 0.82;
const CROWN_HEIGHT = 2.6;
const CROWN_STEP = 0.9;

const READER_BASE = import.meta.env.PUBLIC_READER_BASE ?? "";
const LOCAL_INTERESTS = "inspiring-news:interests";
const MIN_CHOICES = 3;

const $ = <T extends HTMLElement = HTMLElement>(selector: string) => document.querySelector(selector) as T;

function escape(text: string): string {
  return text.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);
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
  user: { username: string } | null;
  csrf: string | null;
  interests: Interest[];
}

export function start(): void {
  const state: State = { data: null, mode: "universe", section: null, strong: null, selected: -1, user: null, csrf: null, interests: [] };

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

  function buildNetwork(data: Universe): void {
    const stories = new Map<number, number[]>();
    data.entitiesOf.forEach((refs, i) => refs.forEach((ref) => (stories.get(ref) ?? stories.set(ref, []).get(ref)!).push(i)));

    // Names form a crown of rings above the galaxy, one ring per kind.
    // Not each name at the mean of its stories: a name in every section
    // (Barcelona, a big company) has its mean at the centre, and on
    // 29 Oct every hub piled up there, labels on labels. A name sits over
    // the side its stories lean towards, spaced evenly round its ring so
    // none overlap, and its threads fall to its stories.
    const leaning: { node: NetworkNode; angle: number }[] = [];
    stories.forEach((named, ref) => {
      const entity = data.entities[ref];
      const kind = entity ? kindOf(entity.t) : null;
      if (!kind || named.length < 2) return;
      let x = 0;
      let y = 0;
      for (const i of named) {
        x += data.positions[i * 3];
        y += data.positions[i * 3 + 1];
      }
      leaning.push({ node: { key: entity.k, name: entity.n, kind, x: 0, y: 0, z: 0, stories: named }, angle: Math.atan2(y, x) });
    });
    leaning.sort((a, b) => b.node.stories.length - a.node.stories.length);
    const kept = leaning.slice(0, MAX_NODES);

    allNodes = [];
    KINDS.forEach((kind, k) => {
      const ring = kept.filter((l) => l.node.kind === kind.key).sort((a, b) => a.angle - b.angle);
      const height = CROWN_HEIGHT + k * CROWN_STEP;
      ring.forEach((l, i) => {
        const angle = (ring[0]?.angle ?? 0) + (i * Math.PI * 2) / ring.length;
        allNodes.push({ ...l.node, x: Math.cos(angle) * CROWN_RADIUS, y: Math.sin(angle) * CROWN_RADIUS, z: height });
      });
    });
    allNodes.sort((a, b) => b.stories.length - a.stories.length);
    makeConnectionsLegend();
    applyNetwork();
  }

  function applyNetwork(): void {
    nodes = allNodes.filter((n) => kindsOn.has(n.kind));
    scene.setNetwork(nodes);
    scene.setNetworkVisible(networkOn);
    const host = $("#labels");
    nodeLabels.forEach((l) => l.element.remove());
    nodeLabels = nodes.slice(0, LABELLED_NODES).map((node, i) => {
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
      <ol class="related">${newest.map((i) => `<li><button type="button" class="link" data-story="${data.ids[i]}">${escape(data.titles[i])}</button><span class="muted"> · ${escape(data.sources[data.sourceOf[i]])}${data.days[i] ? ` · ${data.days[i]}` : ""}</span></li>`).join("")}</ol>`;
    panel.querySelector(".close")!.addEventListener("click", () => {
      panel.hidden = true;
      scene.highlightNode(-1);
      state.strong = null;
      refresh();
    });
    panel.querySelectorAll<HTMLButtonElement>("[data-story]").forEach((b) => b.addEventListener("click", () => void select(data.indexOf.get(b.dataset.story!)!)));
  }

  scene.onFrame = () => {
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
    tip.innerHTML = `<strong>${escape(data.titles[index])}</strong><span>${escape(data.sources[data.sourceOf[index]])}${data.days[index] ? ` · ${data.days[index]}` : ""} · ${verdictText(data.verdicts[index])}</span>`;
    tip.style.left = `${Math.min(screen.x + 16, window.innerWidth - 320)}px`;
    tip.style.top = `${screen.y + 16}px`;
    tip.hidden = false;
  }

  async function select(index: number): Promise<void> {
    const data = state.data;
    const panel = $("#panel");
    state.selected = index;
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
    panel.innerHTML = `
      <button type="button" class="close" aria-label="Close">×</button>
      <p class="hud-label" style="color:${data.group[index] === NO_GROUP ? "#8a90a6" : GROUP_COLORS[data.group[index]]}">${data.group[index] === NO_GROUP ? "Not placed" : escape(data.groups[data.group[index]].name)}</p>
      <h2>${escape(data.titles[index])}</h2>
      <p class="muted">${escape(data.sources[data.sourceOf[index]])}${data.days[index] ? ` · ${data.days[index]}` : ""}</p>
      <p><span class="verdict v-${(data.verdicts[index] ?? "none").toLowerCase()}">${verdictText(data.verdicts[index])}</span></p>
      <p><a class="primary-link" href="${READER_BASE}/reader/${data.ids[index]}">Read the story and its checks →</a></p>
      <div id="panel-links"><p class="muted">Tracing its connections…</p></div>`;
    panel.querySelector(".close")!.addEventListener("click", () => void select(-1));

    let links: Links;
    try {
      links = await api.links(data.ids[index]);
    } catch (error) {
      $("#panel-links").innerHTML = `<p class="error">Its connections could not be loaded (${escape((error as Error).message)}).</p>`;
      return;
    }
    if (state.selected !== index) return;

    scene.setLinks(
      index,
      links.related.map((r) => {
        const j = data.indexOf.get(r.id);
        return j !== undefined ? { x: data.positions[j * 3], y: data.positions[j * 3 + 1], z: data.positions[j * 3 + 2] } : { x: r.x, y: r.y };
      }),
    );

    const followed = (kind: string, key: string) => state.interests.some((i) => i.kind === kind && i.key === key);
    $("#panel-links").innerHTML = `
      <p class="hud-label">Topics</p>
      <div class="chips">${links.topics.map((t) => `<button type="button" class="chip" data-follow="topic" data-key="${escape(t.key)}" data-label="${escape(t.name)}" aria-pressed="${followed("topic", t.key)}">${followed("topic", t.key) ? "✓ " : "+ "}${escape(t.name)}</button>`).join("")}</div>
      ${links.entities.length ? `<p class="hud-label">Names</p><div class="chips">${links.entities.map((e) => `<button type="button" class="chip" data-entity="${escape(e.key)}">${escape(e.name)}${e.articles > 1 ? ` · ${e.articles}` : ""}</button>`).join("")}</div>` : ""}
      <p class="hud-label">Connected</p>
      ${links.related.length ? `<ol class="related">${links.related.map((r) => `<li><button type="button" class="link" data-story="${r.id}">${escape(r.title)}</button><span class="muted"> ${escape(r.via.slice(0, 2).map((v) => (v.kind === "entity" ? `both name ${v.via}` : v.kind === "topic" ? `both about ${v.via}` : v.kind === "claim" ? "the same claim" : "a shared source")).join("; "))}</span></li>`).join("")}</ol>` : `<p class="muted">Nothing else published shares a claim, a source, a name or a topic with it yet.</p>`}`;

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
      .map((i) => `<li><a href="${READER_BASE}/reader/${data.ids[i]}">${escape(data.titles[i])}</a><span class="muted"> · ${escape(data.sources[data.sourceOf[i]])}${data.days[i] ? ` · ${data.days[i]}` : ""} · ${data.group[i] === NO_GROUP ? "" : escape(data.groups[data.group[i]].name)}</span></li>`)
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
      <ol class="related">${items.map((item) => `<li><button type="button" class="link" data-story="${item.id}">${escape(item.title)}</button><span class="muted"> because ${escape(item.reasons.join("; ") || "it is new")}</span></li>`).join("")}</ol>`;
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
  });
}
