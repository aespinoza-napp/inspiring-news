"use client";

import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState } from "react";

import { MapRenderer, type Camera } from "@/lib/mapRenderer";
import { groupColors, parseColor, type MapData } from "@/lib/newsMap";
import { SpatialGrid } from "@/lib/spatialGrid";
import styles from "./NewsMap.module.css";

export interface MapEntityPoint {
  k: string;
  n: string;
  t: string;
  c: number;
  x: number;
  y: number;
}

export interface NewsMapHandle {
  flyTo(x: number, y: number, zoom: number): void;
  fitAll(): void;
}

interface Props {
  data: MapData;
  entities: MapEntityPoint[];
  // Per article, 0..1; what a filter or a search leaves out is dimmed.
  alpha: Float32Array;
  selected: number;
  // The selected article's links, as map points to draw lines to.
  links: { x: number; y: number }[];
  // The reader's own connections, as segments in map units: dashed.
  personal?: Float32Array;
  onSelect(index: number): void;
  onEntity?(key: string): void;
  label: string;
}

// The disc and the ring beyond it (no-topic articles at 1.08) fit when
// the shorter side spans this many map units.
const FIT = 2.4;

// A topic's label shows once the closest two anchors (0.287 apart) are
// this many pixels apart: before that they overlap.
const TOPIC_LABEL_PIXELS = 110;

// Entities appear past this much zoom, the most named first, at most this many.
const ENTITY_ZOOM = 3;
const MAX_ENTITY_LABELS = 30;

const HOVER_PIXELS = 8;

// Read by scripts/bench_news_map.py (N8's budget): a mark when the first
// frame with stories is drawn, and each hover pick's milliseconds, kept
// only when the measuring page has set window.__newsMapPerf.
declare global {
  interface Window {
    __newsMapPerf?: { picks: number[] };
  }
}
const FIRST_FRAME = "news-map:first-frame";
const CLICK_SLOP = 4;

function baseScale(width: number, height: number): number {
  return Math.min(width, height) / FIT;
}

export const NewsMap = forwardRef<NewsMapHandle, Props>(function NewsMap(
  { data, entities, alpha, selected, links, personal, onSelect, onEntity, label },
  ref,
) {
  const frame = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const renderer = useRef<MapRenderer | null>(null);
  const camera = useRef<Camera>({ x: 0, y: 0, k: 1 });
  const scheduled = useRef(0);
  const labels = useRef<Map<string, HTMLElement>>(new Map());
  const marker = useRef<HTMLDivElement>(null);
  const grid = useRef<SpatialGrid | null>(null);
  const alphaRef = useRef(alpha);
  alphaRef.current = alpha;

  const [failed, setFailed] = useState<string | null>(null);
  const [hover, setHover] = useState<{ index: number; x: number; y: number } | null>(null);
  const [dragging, setDragging] = useState(false);

  // ---- drawing ---------------------------------------------------------

  const toScreen = useCallback((x: number, y: number) => {
    const element = frame.current!;
    const c = camera.current;
    return {
      x: element.clientWidth / 2 + (x - c.x) * c.k,
      y: element.clientHeight / 2 - (y - c.y) * c.k,
    };
  }, []);

  const toMap = useCallback((sx: number, sy: number) => {
    const element = frame.current!;
    const c = camera.current;
    return {
      x: c.x + (sx - element.clientWidth / 2) / c.k,
      y: c.y - (sy - element.clientHeight / 2) / c.k,
    };
  }, []);

  const placeLabels = useCallback(() => {
    const element = frame.current;
    if (!element) return;

    const width = element.clientWidth;
    const height = element.clientHeight;
    const c = camera.current;
    const base = baseScale(width, height);
    const showTopics = c.k * 0.287 >= TOPIC_LABEL_PIXELS;
    const showEntities = c.k >= base * ENTITY_ZOOM;
    let entitiesShown = 0;

    labels.current.forEach((node, key) => {
      // "group:", "topic:" or "entity:", then the key (an entity's has colons of its own).
      const kind = key.slice(0, key.indexOf(":"));
      const x = Number(node.dataset.x);
      const y = Number(node.dataset.y);
      const p = toScreen(x, y);
      const inside = p.x > -100 && p.x < width + 100 && p.y > -40 && p.y < height + 40;

      let visible = inside;
      if (kind === "topic") visible = inside && showTopics;
      if (kind === "entity") {
        visible = inside && showEntities && entitiesShown < MAX_ENTITY_LABELS;
        if (visible) entitiesShown++;
      }

      node.classList.toggle(styles.hidden, !visible);
      if (visible) node.style.transform = `translate(${p.x}px, ${p.y}px) translate(-50%, -50%)`;
    });

    if (marker.current) {
      if (selected >= 0) {
        const p = toScreen(data.positions[selected * 2], data.positions[selected * 2 + 1]);
        marker.current.style.transform = `translate(${p.x}px, ${p.y}px)`;
        marker.current.classList.remove(styles.hidden);
      } else {
        marker.current.classList.add(styles.hidden);
      }
    }
  }, [data, selected, toScreen]);

  const firstFrame = useRef(false);

  const draw = useCallback(() => {
    scheduled.current = 0;
    if (!renderer.current) return;
    renderer.current.draw(camera.current);
    placeLabels();
    if (!firstFrame.current && data.count > 0) {
      firstFrame.current = true;
      performance.mark(FIRST_FRAME);
    }
  }, [placeLabels, data]);

  const schedule = useCallback(() => {
    if (!scheduled.current) scheduled.current = requestAnimationFrame(draw);
  }, [draw]);

  // ---- set-up ----------------------------------------------------------

  useEffect(() => {
    if (!canvas.current || !frame.current) return;

    try {
      renderer.current = new MapRenderer(canvas.current);
    } catch (error) {
      setFailed(String(error));
      return;
    }

    const element = frame.current;
    const base = baseScale(element.clientWidth, element.clientHeight);
    camera.current = { x: 0, y: 0, k: base };
    renderer.current.baseScale = base;

    // Resizing changes the fit and the canvas; the camera's centre stays.
    const observer = new ResizeObserver(() => {
      if (!renderer.current || !frame.current) return;
      renderer.current.baseScale = baseScale(frame.current.clientWidth, frame.current.clientHeight);
      schedule();
    });
    observer.observe(element);

    return () => {
      observer.disconnect();
      if (scheduled.current) cancelAnimationFrame(scheduled.current);
      renderer.current?.destroy();
      renderer.current = null;
    };
    // The renderer lives as long as the component; the data is set below.
  }, []);

  // The data, recoloured when the colour scheme changes.
  useEffect(() => {
    if (!renderer.current || !frame.current) return;

    const colour = () => {
      renderer.current?.setData(data, groupColors(frame.current!, data.groups.length));
      renderer.current?.setAlpha(alphaRef.current);
      schedule();
    };

    colour();
    grid.current = new SpatialGrid(data.positions, 0.02);

    const scheme = window.matchMedia("(prefers-color-scheme: dark)");
    scheme.addEventListener("change", colour);
    return () => scheme.removeEventListener("change", colour);
  }, [data, schedule]);

  useEffect(() => {
    renderer.current?.setAlpha(alpha);
    schedule();
  }, [alpha, schedule]);

  useEffect(() => {
    if (!renderer.current) return;
    const segments = new Float32Array(links.length * 4);
    if (selected >= 0) {
      links.forEach((link, i) => {
        segments[i * 4] = data.positions[selected * 2];
        segments[i * 4 + 1] = data.positions[selected * 2 + 1];
        segments[i * 4 + 2] = link.x;
        segments[i * 4 + 3] = link.y;
      });
    }
    const [r, g, b] = parseColor(getComputedStyle(frame.current!).getPropertyValue("--muted")) ?? [0.42, 0.42, 0.42];
    renderer.current.setLines(selected >= 0 ? segments : new Float32Array(0), [r, g, b, 0.7]);
    schedule();
  }, [data, links, selected, schedule]);

  useEffect(() => {
    if (!renderer.current) return;
    const accent = parseColor(getComputedStyle(frame.current!).getPropertyValue("--accent")) ?? [0.15, 0.39, 0.92];
    renderer.current.setDashed(personal ?? new Float32Array(0), [accent[0], accent[1], accent[2], 0.9]);
    schedule();
  }, [personal, schedule]);

  // ---- camera ----------------------------------------------------------

  const animateTo = useCallback((target: Camera) => {
    const start = { ...camera.current };
    const began = performance.now();
    const duration = window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 350;

    const step = (now: number) => {
      const t = duration ? Math.min(1, (now - began) / duration) : 1;
      const e = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
      camera.current = {
        x: start.x + (target.x - start.x) * e,
        y: start.y + (target.y - start.y) * e,
        k: start.k * Math.pow(target.k / start.k, e),
      };
      draw();
      if (t < 1) requestAnimationFrame(step);
    };

    requestAnimationFrame(step);
  }, [draw]);

  useImperativeHandle(ref, () => ({
    flyTo(x, y, zoom) {
      const element = frame.current!;
      animateTo({ x, y, k: baseScale(element.clientWidth, element.clientHeight) * zoom });
    },
    fitAll() {
      const element = frame.current!;
      animateTo({ x: 0, y: 0, k: baseScale(element.clientWidth, element.clientHeight) });
    },
  }), [animateTo]);

  const zoomAt = useCallback((sx: number, sy: number, factor: number) => {
    const element = frame.current!;
    const base = baseScale(element.clientWidth, element.clientHeight);
    const before = toMap(sx, sy);
    const k = Math.min(base * 60, Math.max(base * 0.6, camera.current.k * factor));
    camera.current = { ...camera.current, k };
    const after = toMap(sx, sy);
    camera.current = { x: camera.current.x + before.x - after.x, y: camera.current.y + before.y - after.y, k };
    schedule();
  }, [schedule, toMap]);

  // ---- pointer and keyboard ---------------------------------------------

  const pointers = useRef(new Map<number, { x: number; y: number }>());
  const gesture = useRef<{ x: number; y: number; moved: number; distance: number } | null>(null);

  const local = (event: { clientX: number; clientY: number }) => {
    const box = frame.current!.getBoundingClientRect();
    return { x: event.clientX - box.left, y: event.clientY - box.top };
  };

  const pick = useCallback((sx: number, sy: number): number => {
    if (!grid.current) return -1;
    const started = performance.now();
    const p = toMap(sx, sy);
    const visible = alphaRef.current;
    const found = grid.current.nearest(p.x, p.y, HOVER_PIXELS / camera.current.k, (i) => visible[i] > 0.5);
    window.__newsMapPerf?.picks.push(performance.now() - started);
    return found;
  }, [toMap]);

  const onPointerDown = (event: React.PointerEvent) => {
    frame.current!.setPointerCapture(event.pointerId);
    const p = local(event);
    pointers.current.set(event.pointerId, p);
    const all = Array.from(pointers.current.values());
    gesture.current = {
      x: p.x,
      y: p.y,
      moved: 0,
      distance: all.length === 2 ? Math.hypot(all[0].x - all[1].x, all[0].y - all[1].y) : 0,
    };
  };

  const onPointerMove = (event: React.PointerEvent) => {
    const p = local(event);

    if (!pointers.current.has(event.pointerId)) {
      const index = pick(p.x, p.y);
      setHover(index >= 0 ? { index, x: p.x, y: p.y } : null);
      return;
    }

    const previous = pointers.current.get(event.pointerId)!;
    pointers.current.set(event.pointerId, p);
    const all = Array.from(pointers.current.values());

    if (all.length === 2 && gesture.current) {
      const distance = Math.hypot(all[0].x - all[1].x, all[0].y - all[1].y);
      if (gesture.current.distance > 0) {
        zoomAt((all[0].x + all[1].x) / 2, (all[0].y + all[1].y) / 2, distance / gesture.current.distance);
      }
      gesture.current.distance = distance;
      gesture.current.moved += CLICK_SLOP + 1;
      return;
    }

    const dx = p.x - previous.x;
    const dy = p.y - previous.y;
    if (gesture.current) gesture.current.moved += Math.abs(dx) + Math.abs(dy);
    if (gesture.current && gesture.current.moved > CLICK_SLOP) setDragging(true);

    camera.current = { ...camera.current, x: camera.current.x - dx / camera.current.k, y: camera.current.y + dy / camera.current.k };
    setHover(null);
    schedule();
  };

  const onPointerUp = (event: React.PointerEvent) => {
    const p = local(event);
    const wasClick = gesture.current && gesture.current.moved <= CLICK_SLOP && pointers.current.size === 1;
    pointers.current.delete(event.pointerId);
    if (pointers.current.size === 0) {
      setDragging(false);
      gesture.current = null;
    }
    if (wasClick) onSelect(pick(p.x, p.y));
  };

  useEffect(() => {
    const element = frame.current;
    if (!element) return;

    // Not React's onWheel: it is passive, and the page must not scroll
    // while the map zooms.
    const wheel = (event: WheelEvent) => {
      event.preventDefault();
      const p = local(event);
      zoomAt(p.x, p.y, Math.exp(-event.deltaY * (event.deltaMode === 1 ? 0.05 : 0.0015)));
    };

    element.addEventListener("wheel", wheel, { passive: false });
    return () => element.removeEventListener("wheel", wheel);
  }, [zoomAt]);

  const onKeyDown = (event: React.KeyboardEvent) => {
    const element = frame.current!;
    const step = 60 / camera.current.k;
    const centre = { x: element.clientWidth / 2, y: element.clientHeight / 2 };

    const moves: Record<string, () => void> = {
      ArrowLeft: () => { camera.current = { ...camera.current, x: camera.current.x - step }; schedule(); },
      ArrowRight: () => { camera.current = { ...camera.current, x: camera.current.x + step }; schedule(); },
      ArrowUp: () => { camera.current = { ...camera.current, y: camera.current.y + step }; schedule(); },
      ArrowDown: () => { camera.current = { ...camera.current, y: camera.current.y - step }; schedule(); },
      "+": () => zoomAt(centre.x, centre.y, 1.25),
      "=": () => zoomAt(centre.x, centre.y, 1.25),
      "-": () => zoomAt(centre.x, centre.y, 0.8),
      "0": () => animateTo({ x: 0, y: 0, k: baseScale(element.clientWidth, element.clientHeight) }),
      Escape: () => onSelect(-1),
    };

    const move = moves[event.key];
    if (move) {
      event.preventDefault();
      move();
    }
  };

  // ---- labels ----------------------------------------------------------

  const register = (key: string) => (node: HTMLElement | null) => {
    if (node) labels.current.set(key, node);
    else labels.current.delete(key);
  };

  useEffect(() => {
    schedule();
  }, [entities, selected, schedule]);

  const hovered = hover && hover.index >= 0 ? hover : null;

  return (
    <div
      ref={frame}
      className={dragging ? `${styles.frame} ${styles.dragging}` : styles.frame}
      tabIndex={0}
      role="application"
      aria-label={label}
      aria-roledescription="map"
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={onPointerUp}
      onPointerLeave={() => setHover(null)}
      onKeyDown={onKeyDown}
    >
      <canvas ref={canvas} className={styles.canvas} aria-hidden="true" />

      <div className={styles.overlay}>
        {data.groups.map((group) => {
          const radius = 1.0;
          return (
            <button
              type="button"
              key={group.key}
              ref={register(`group:${group.key}`)}
              className={styles.groupLabel}
              data-x={radius * Math.cos(group.angle)}
              data-y={radius * Math.sin(group.angle)}
              onPointerDown={(e) => e.stopPropagation()}
              onClick={() => {
                const element = frame.current!;
                animateTo({ x: 0.72 * Math.cos(group.angle), y: 0.72 * Math.sin(group.angle), k: baseScale(element.clientWidth, element.clientHeight) * 2.2 });
              }}
            >
              {group.name}
            </button>
          );
        })}

        {data.topics.map((topic) => (
          <button
            type="button"
            key={topic.key}
            ref={register(`topic:${topic.key}`)}
            className={`${styles.topicLabel} ${styles.hidden}`}
            data-x={topic.x}
            data-y={topic.y + 0.1}
            onPointerDown={(e) => e.stopPropagation()}
            onClick={() => {
              const element = frame.current!;
              animateTo({ x: topic.x, y: topic.y, k: baseScale(element.clientWidth, element.clientHeight) * 6 });
            }}
          >
            {topic.name}
          </button>
        ))}

        {entities.map((entity) => (
          <button
            type="button"
            key={entity.k}
            ref={register(`entity:${entity.k}`)}
            className={`${styles.entityLabel} ${styles.hidden}`}
            data-x={entity.x}
            data-y={entity.y}
            title={`${entity.n}: ${entity.c} articles`}
            onPointerDown={(e) => e.stopPropagation()}
            onClick={() => onEntity?.(entity.k)}
          >
            {entity.n} · {entity.c}
          </button>
        ))}

        <div ref={marker} className={`${styles.marker} ${styles.hidden}`} />

        {hovered && (
          <div
            className={styles.hoverCard}
            style={{
              left: Math.min(hovered.x + 14, (frame.current?.clientWidth ?? 0) - 300),
              top: hovered.y + 14,
            }}
          >
            <strong>{data.titles[hovered.index]}</strong>
            {data.sources[data.sourceOf[hovered.index]]}
            {data.days[hovered.index] ? ` · ${data.days[hovered.index]}` : ""}
            {data.verdicts[hovered.index] ? ` · ${data.verdicts[hovered.index]!.replace(/_/g, " ").toLowerCase()}` : ""}
          </div>
        )}
      </div>

      <div className={styles.controls} onPointerDown={(e) => e.stopPropagation()}>
        <button type="button" aria-label="Zoom in" onClick={() => zoomAt(frame.current!.clientWidth / 2, frame.current!.clientHeight / 2, 1.5)}>+</button>
        <button type="button" aria-label="Zoom out" onClick={() => zoomAt(frame.current!.clientWidth / 2, frame.current!.clientHeight / 2, 1 / 1.5)}>−</button>
        <button type="button" aria-label="Show the whole map" onClick={() => animateTo({ x: 0, y: 0, k: baseScale(frame.current!.clientWidth, frame.current!.clientHeight) })}>⌂</button>
      </div>

      {failed && (
        <div className={styles.unavailable}>
          This browser could not start WebGL, so the map cannot be drawn. The list view has every article.
        </div>
      )}
    </div>
  );
});
