// The news map's points on the GPU, through regl: one draw call for
// every article whatever the count, a second only for the selected
// article's lines. Chosen over sigma.js by the 29 Oct spike: as fast on
// the integrated GPU and 16x faster without one, where sigma could not
// draw 50k points at all (docs/decisions/news-map.md, "The renderer").
// No React here, so the benchmark page measures exactly what the map runs.

import createREGL from "regl";
import type { Regl, DrawCommand, Buffer } from "regl";

import type { MapData } from "@/lib/newsMap";

export interface Camera {
  // The map point at the canvas centre, and how many CSS pixels one map
  // unit spans.
  x: number;
  y: number;
  k: number;
}

const POINT_VERTEX = `
precision mediump float;
attribute vec2 position;
attribute vec3 color;
attribute float alpha;
uniform vec2 centre;
uniform float scale;
uniform vec2 viewport;
uniform float pointSize;
varying vec3 vColor;
varying float vAlpha;
void main() {
  vec2 p = (position - centre) * scale;
  gl_Position = vec4(p.x * 2.0 / viewport.x, p.y * 2.0 / viewport.y, 0.0, 1.0);
  gl_PointSize = pointSize * (alpha < 0.5 ? 0.75 : 1.0);
  vColor = color;
  vAlpha = alpha;
}`;

const POINT_FRAGMENT = `
precision mediump float;
varying vec3 vColor;
varying float vAlpha;
void main() {
  vec2 c = gl_PointCoord * 2.0 - 1.0;
  float r = dot(c, c);
  if (r > 1.0) discard;
  gl_FragColor = vec4(vColor, vAlpha * (1.0 - smoothstep(0.6, 1.0, r)));
}`;

const LINE_VERTEX = `
precision mediump float;
attribute vec2 position;
uniform vec2 centre;
uniform float scale;
uniform vec2 viewport;
void main() {
  vec2 p = (position - centre) * scale;
  gl_Position = vec4(p.x * 2.0 / viewport.x, p.y * 2.0 / viewport.y, 0.0, 1.0);
}`;

const LINE_FRAGMENT = `
precision mediump float;
uniform vec4 color;
void main() { gl_FragColor = color; }`;

interface Uniforms {
  centre: [number, number];
  scale: number;
  viewport: [number, number];
  pointSize: number;
}

// How big a point is drawn, in CSS pixels, at a zoom: small enough at the
// whole disc that 10k points read as a cloud, larger as you zoom in.
export function pointSize(k: number, base: number): number {
  return Math.max(2, Math.min(12, 2.5 + Math.log2(Math.max(k / base, 1)) * 2));
}

export class MapRenderer {
  private readonly regl: Regl;
  private readonly drawPoints: DrawCommand;
  private readonly drawLines: DrawCommand;
  private readonly positionBuffer: Buffer;
  private readonly colorBuffer: Buffer;
  private readonly alphaBuffer: Buffer;
  private readonly lineBuffer: Buffer;
  private count = 0;
  private lineCount = 0;
  private lineColor: [number, number, number, number] = [0.4, 0.4, 0.4, 0.8];
  private background: [number, number, number, number] = [0, 0, 0, 0];

  // The zoom at which the whole disc fits: point sizes grow from it.
  baseScale = 1;

  constructor(private readonly canvas: HTMLCanvasElement) {
    this.regl = createREGL({
      canvas,
      attributes: { antialias: true, alpha: true, premultipliedAlpha: false },
      // Drawn on demand, never on a loop: a still map costs nothing.
      optionalExtensions: [],
    });

    this.positionBuffer = this.regl.buffer({ usage: "static", type: "float", length: 0 });
    this.colorBuffer = this.regl.buffer({ usage: "static", type: "float", length: 0 });
    this.alphaBuffer = this.regl.buffer({ usage: "dynamic", type: "float", length: 0 });
    this.lineBuffer = this.regl.buffer({ usage: "dynamic", type: "float", length: 0 });

    const blend = {
      enable: true,
      func: { srcRGB: "src alpha", srcAlpha: 1, dstRGB: "one minus src alpha", dstAlpha: 1 },
    } as const;

    this.drawPoints = this.regl({
      vert: POINT_VERTEX,
      frag: POINT_FRAGMENT,
      attributes: {
        position: this.positionBuffer,
        color: this.colorBuffer,
        alpha: this.alphaBuffer,
      },
      uniforms: {
        centre: this.regl.prop<Uniforms, "centre">("centre"),
        scale: this.regl.prop<Uniforms, "scale">("scale"),
        viewport: this.regl.prop<Uniforms, "viewport">("viewport"),
        pointSize: this.regl.prop<Uniforms, "pointSize">("pointSize"),
      },
      blend,
      depth: { enable: false },
      primitive: "points",
      count: () => this.count,
    });

    this.drawLines = this.regl({
      vert: LINE_VERTEX,
      frag: LINE_FRAGMENT,
      attributes: { position: this.lineBuffer },
      uniforms: {
        centre: this.regl.prop<Uniforms, "centre">("centre"),
        scale: this.regl.prop<Uniforms, "scale">("scale"),
        viewport: this.regl.prop<Uniforms, "viewport">("viewport"),
        color: () => this.lineColor,
      },
      blend,
      depth: { enable: false },
      primitive: "lines",
      count: () => this.lineCount,
    });
  }

  setData(data: MapData, colors: [number, number, number][]): void {
    const rgb = new Float32Array(data.count * 3);

    for (let i = 0; i < data.count; i++) {
      const color = colors[Math.min(data.group[i], colors.length - 1)];
      rgb[i * 3] = color[0];
      rgb[i * 3 + 1] = color[1];
      rgb[i * 3 + 2] = color[2];
    }

    this.positionBuffer({ data: data.positions, usage: "static" });
    this.colorBuffer({ data: rgb, usage: "static" });
    this.alphaBuffer({ data: new Float32Array(data.count).fill(0.9), usage: "dynamic" });
    this.count = data.count;
  }

  // Per point, 0..1: dims what a filter or a search leaves out.
  setAlpha(alpha: Float32Array): void {
    this.alphaBuffer({ data: alpha, usage: "dynamic" });
  }

  // Segments as x0, y0, x1, y1, ...: the selected article's links.
  setLines(segments: Float32Array, color?: [number, number, number, number]): void {
    this.lineBuffer({ data: segments, usage: "dynamic" });
    this.lineCount = segments.length / 2;
    if (color) this.lineColor = color;
  }

  setBackground(color: [number, number, number, number]): void {
    this.background = color;
  }

  // Draws one frame; returns its milliseconds, the GPU's included when
  // `measure` asks for gl.finish (the benchmark), else only the CPU's.
  draw(camera: Camera, measure = false): number {
    const started = performance.now();
    const ratio = window.devicePixelRatio || 1;
    const width = this.canvas.clientWidth;
    const height = this.canvas.clientHeight;

    if (this.canvas.width !== Math.round(width * ratio) || this.canvas.height !== Math.round(height * ratio)) {
      this.canvas.width = Math.round(width * ratio);
      this.canvas.height = Math.round(height * ratio);
    }

    this.regl.poll();
    this.regl.clear({ color: this.background, depth: 1 });

    const uniforms: Uniforms = {
      centre: [camera.x, camera.y],
      scale: camera.k * ratio,
      viewport: [this.canvas.width, this.canvas.height],
      pointSize: pointSize(camera.k, this.baseScale) * ratio,
    };

    if (this.lineCount > 0) this.drawLines(uniforms);
    if (this.count > 0) this.drawPoints(uniforms);

    if (measure) this.regl._gl.finish();

    return performance.now() - started;
  }

  destroy(): void {
    this.regl.destroy();
  }
}
