"use client";

// The renderer benchmark (docs/goals.md, N2 and N8): the same synthetic
// points drawn by regl (lib/mapRenderer.ts, what the map runs) or by
// sigma.js, along the same scripted pan and zoom, each frame drawn
// synchronously and waited for (gl.finish), so the numbers are the GPU's
// work and not the display's refresh rate. Read by
// scripts/bench_map_renderers.py from #bench-result. Synthetic data
// only: nothing here calls the backend.

import { useEffect, useRef, useState } from "react";
import Graph from "graphology";
import Sigma from "sigma";

import { MapRenderer, type Camera } from "@/lib/mapRenderer";
import { synthetic, type MapGroup, type MapTopic } from "@/lib/newsMap";
import { SpatialGrid } from "@/lib/spatialGrid";

const WIDTH = 1280;
const HEIGHT = 800;

// The backend's frame, approximately: five sectors, 23 anchors on two
// rings. The cost of drawing does not depend on where the anchors are.
function benchFrame(): { layout: number; groups: MapGroup[]; topics: MapTopic[] } {
  const sizes = [4, 4, 5, 5, 5];
  const groups: MapGroup[] = [];
  const topics: MapTopic[] = [];
  const slot = (2 * Math.PI) / (23 + 0.6 * 5);
  let cursor = 0;
  let index = 0;

  sizes.forEach((size, g) => {
    const start = cursor;
    for (let t = 0; t < size; t++, index++) {
      const angle = Math.PI / 2 - (cursor + 0.5) * slot;
      const radius = index % 2 === 0 ? 0.88 : 0.6;
      topics.push({ key: `t${index}`, name: `Topic ${index}`, group: `g${g}`, x: radius * Math.cos(angle), y: radius * Math.sin(angle) });
      cursor += 1;
    }
    groups.push({ key: `g${g}`, name: `Group ${g}`, angle: Math.PI / 2 - ((start + cursor) / 2) * slot, span: size * slot });
    cursor += 0.6;
  });

  return { layout: 1, groups, topics };
}

// Between frames, so the page still answers the driver (DevTools) while
// a slow renderer works through the path; each frame is timed on its own.
function breathe(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

function percentile(values: number[], p: number): number {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.min(sorted.length - 1, Math.floor((p / 100) * sorted.length))];
}

function summary(values: number[]) {
  return {
    median: Number(percentile(values, 50).toFixed(3)),
    p95: Number(percentile(values, 95).toFixed(3)),
    max: Number(Math.max(...values).toFixed(3)),
  };
}

// Zoom from the whole disc to 8x and back while circling the centre.
function cameraAt(step: number, frames: number, base: number): Camera {
  const t = step / frames;
  const zoom = 1 + 7 * Math.sin(Math.PI * t);
  return { x: 0.3 * Math.cos(2 * Math.PI * t), y: 0.3 * Math.sin(2 * Math.PI * t), k: base * zoom };
}

// How many pixels of a frame are drawn, read back from the canvas: proof
// the points were drawn at all, since a frame drawn wrongly times fast.
function litPixels(gl: WebGLRenderingContext | WebGL2RenderingContext): number {
  const width = gl.drawingBufferWidth;
  const height = gl.drawingBufferHeight;
  const pixels = new Uint8Array(width * height * 4);
  gl.readPixels(0, 0, width, height, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
  let lit = 0;
  for (let i = 3; i < pixels.length; i += 4) if (pixels[i] > 0) lit++;
  return lit;
}

// Waits for the GPU for certain: a readPixels cannot return before the
// frame it reads is done, where gl.finish may (ANGLE).
function sync(gl: WebGLRenderingContext | WebGL2RenderingContext): void {
  gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array(4));
}

function rendererName(gl: WebGLRenderingContext | WebGL2RenderingContext | null): string {
  if (!gl) return "none";
  const info = gl.getExtension("WEBGL_debug_renderer_info");
  return String(info ? gl.getParameter(info.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER));
}

async function benchRegl(container: HTMLDivElement, count: number, frames: number) {
  const data = synthetic(benchFrame(), count);
  const canvas = document.createElement("canvas");
  canvas.style.width = `${WIDTH}px`;
  canvas.style.height = `${HEIGHT}px`;
  container.appendChild(canvas);

  const started = performance.now();
  const renderer = new MapRenderer(canvas);
  const colors: [number, number, number][] = [[0.16, 0.47, 0.84], [0.92, 0.41, 0.2], [0.11, 0.69, 0.48], [0.93, 0.63, 0], [0.91, 0.48, 0.64], [0.5, 0.5, 0.5]];
  renderer.setData(data, colors);
  const base = Math.min(WIDTH, HEIGHT) / 2.3;
  renderer.baseScale = base;
  const gl = canvas.getContext("webgl2") ?? canvas.getContext("webgl");
  renderer.draw({ x: 0, y: 0, k: base }, true);
  if (gl) sync(gl);
  const firstFrame = performance.now() - started;
  const lit = gl ? litPixels(gl) : 0;

  const times: number[] = [];
  for (let step = 0; step < frames; step++) {
    const t0 = performance.now();
    renderer.draw(cameraAt(step, frames, base), true);
    if (gl) sync(gl);
    times.push(performance.now() - t0);
    await breathe();
  }

  // The read-back's own cost, on frames with nothing to draw: what every
  // frame time above includes beyond the drawing.
  const empty: number[] = [];
  renderer.setData(synthetic(benchFrame(), 0), colors);
  for (let step = 0; step < 60; step++) {
    const t0 = performance.now();
    renderer.draw(cameraAt(step, 60, base), true);
    if (gl) sync(gl);
    empty.push(performance.now() - t0);
    await breathe();
  }

  const gridStarted = performance.now();
  const grid = new SpatialGrid(data.positions, 0.01);
  const gridBuild = performance.now() - gridStarted;

  const picks: number[] = [];
  for (let i = 0; i < 500; i++) {
    const x = Math.cos(i) * 0.7;
    const y = Math.sin(i * 1.3) * 0.7;
    const t0 = performance.now();
    grid.nearest(x, y, 8 / base);
    picks.push(performance.now() - t0);
  }

  const result = { gpu: rendererName(gl), litPixels: lit, firstFrameMs: Number(firstFrame.toFixed(1)), frameMs: summary(times), emptyFrameMs: summary(empty), gridBuildMs: Number(gridBuild.toFixed(2)), pickMs: summary(picks) };
  renderer.destroy();
  return result;
}

async function benchSigma(container: HTMLDivElement, count: number, frames: number) {
  const data = synthetic(benchFrame(), count);
  const host = document.createElement("div");
  host.style.width = `${WIDTH}px`;
  host.style.height = `${HEIGHT}px`;
  host.style.position = "relative";
  container.appendChild(host);

  const palette = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#888888"];

  const started = performance.now();
  const graph = new Graph();
  for (let i = 0; i < data.count; i++) {
    graph.addNode(data.ids[i], { x: data.positions[i * 2], y: data.positions[i * 2 + 1], size: 2, color: palette[Math.min(data.group[i], 5)] });
  }
  const sigma = new Sigma(graph, host, { renderLabels: false, renderEdgeLabels: false, enableEdgeEvents: false });
  const render = () => (sigma as unknown as { render(): void }).render();
  const canvases = Object.values(sigma.getCanvases());
  const contexts = canvases
    .map((canvas) => canvas.getContext("webgl2") ?? canvas.getContext("webgl"))
    .filter((gl): gl is WebGL2RenderingContext | WebGLRenderingContext => gl !== null);
  const finish = () => contexts.forEach((gl) => sync(gl));

  render();
  finish();
  const firstFrame = performance.now() - started;
  const lit = contexts.reduce((sum, gl) => sum + litPixels(gl), 0);

  const camera = sigma.getCamera();
  const times: number[] = [];
  for (let step = 0; step < frames; step++) {
    const t = step / frames;
    camera.setState({ x: 0.5 + 0.15 * Math.cos(2 * Math.PI * t), y: 0.5 + 0.15 * Math.sin(2 * Math.PI * t), ratio: 1 / (1 + 7 * Math.sin(Math.PI * t)) });
    const t0 = performance.now();
    render();
    finish();
    times.push(performance.now() - t0);
    await breathe();
  }

  const result = { gpu: rendererName(contexts[0] ?? null), litPixels: lit, firstFrameMs: Number(firstFrame.toFixed(1)), frameMs: summary(times) };
  sigma.kill();
  return result;
}

export default function MapBench() {
  const container = useRef<HTMLDivElement>(null);
  const [result, setResult] = useState<string>("running");

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const renderer = params.get("renderer") === "sigma" ? "sigma" : "regl";
    const count = Math.min(200_000, Math.max(1, Number(params.get("n") ?? 10_000)));
    const frames = Math.min(2000, Math.max(10, Number(params.get("frames") ?? 180)));

    // A frame later, so the page itself has painted before timing starts.
    const handle = requestAnimationFrame(async () => {
      try {
        const measured = renderer === "sigma" ? await benchSigma(container.current!, count, frames) : await benchRegl(container.current!, count, frames);
        setResult(JSON.stringify({ renderer, count, frames, ...measured }));
      } catch (error) {
        setResult(JSON.stringify({ renderer, count, error: String(error) }));
      }
    });

    return () => cancelAnimationFrame(handle);
  }, []);

  return (
    <main>
      <h1>Map renderer benchmark</h1>
      <p className="claims-note">Synthetic points only. Parameters: ?renderer=regl|sigma&amp;n=10000&amp;frames=180.</p>
      <pre id="bench-result">{result}</pre>
      <div ref={container} />
    </main>
  );
}
