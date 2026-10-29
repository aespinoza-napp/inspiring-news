// The universe in three.js: every published story a star, the five
// sections and 23 topics as the newsroom map lays them out (x and y on
// the disc), each story's depth (z) from a third direction of its meaning,
// so a topic is a cloud and the whole a galaxy. One draw call for every
// star; bloom for the glow; nothing moves a star's place but the view.
//
// Motion: the galaxy turns slowly, stars twinkle and drift a little, and
// a change of view (a section, Today, For you, a search) eases each star
// towards its new brightness and height rather than switching it. All of
// it stops for a reader who asked the system for reduced motion.

import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";

import { NO_GROUP, type Universe } from "./data";

// One map unit in world units, and the depth stretched so the galaxy has
// some thickness without losing its disc.
const R = 10;
const DEPTH_SCALE = 1.6;

// Each section's colour: neon versions of the newsroom's series 1-5, so a
// section is the same hue on both sites.
export const GROUP_COLORS = ["#3d9bff", "#ff7a45", "#22e0a0", "#ffc21a", "#ff6fb5"];
const NO_GROUP_COLOR = "#8a90a6";

const POINT_VERTEX = /* glsl */ `
attribute vec3 color;
attribute float size;
attribute float phase;
attribute float emphasis;
attribute float lift;
uniform float uTime;
uniform float uMotion;
uniform float uPixelRatio;
uniform float uSizeScale;
varying vec3 vColor;
varying float vAlpha;
void main() {
  vec3 p = position;
  p.y += lift;
  p += uMotion * 0.035 * vec3(sin(uTime * 0.31 + phase * 6.3), sin(uTime * 0.23 + phase * 9.1), cos(uTime * 0.27 + phase * 4.7));
  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  gl_Position = projectionMatrix * mv;
  float twinkle = 1.0 + uMotion * 0.28 * sin(uTime * 1.9 + phase * 40.0);
  gl_PointSize = min(size * (0.45 + 0.9 * emphasis) * twinkle * uPixelRatio * uSizeScale / -mv.z, 48.0 * uPixelRatio);
  // Above 1, a story in focus: brighter, so bloom makes it glow.
  vColor = color * (1.0 + 0.7 * max(emphasis - 1.0, 0.0));
  vAlpha = mix(0.07, 1.0, min(emphasis, 1.0));
}`;

const POINT_FRAGMENT = /* glsl */ `
varying vec3 vColor;
varying float vAlpha;
void main() {
  float d = length(gl_PointCoord - 0.5);
  if (d > 0.5) discard;
  float halo = smoothstep(0.5, 0.0, d);
  float core = smoothstep(0.18, 0.0, d);
  gl_FragColor = vec4(vColor * (0.55 + 1.6 * core), halo * vAlpha);
}`;

// A link from the selected story: light flowing along a raised arc.
const LINK_VERTEX = /* glsl */ `
attribute float along;
varying float vAlong;
void main() {
  vAlong = along;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}`;

const LINK_FRAGMENT = /* glsl */ `
uniform float uTime;
uniform vec3 uColor;
uniform float uMotion;
varying float vAlong;
void main() {
  float pulse = pow(fract(vAlong * 2.5 - uTime * 0.45 * uMotion), 6.0);
  gl_FragColor = vec4(uColor, 0.25 + 0.75 * pulse);
}`;

// The kinds of name drawn above the galaxy, from GLiNER's types, each a
// colour none of the five sections uses, and a diamond, not a star.
export const KINDS = [
  { key: "place", label: "Places", one: "Place", color: "#5ef2ff", types: ["city", "country", "location"] },
  { key: "company", label: "Companies", one: "Company", color: "#b28cff", types: ["company", "organization"] },
  { key: "person", label: "People", one: "Person", color: "#d6d0ff", types: ["person"] },
  { key: "brand", label: "Brands", one: "Brand", color: "#c8ff5e", types: ["product"] },
] as const;

export type KindKey = (typeof KINDS)[number]["key"];

// How visible the threads are when no name is in focus.
const EDGE_OPACITY = 0.07;

export function kindOf(type: string): KindKey | null {
  return KINDS.find((kind) => (kind.types as readonly string[]).includes(type))?.key ?? null;
}

// A name in the network: where it floats (map units; z its height above
// the disc), and which stories name it.
export interface NetworkNode {
  key: string;
  name: string;
  kind: KindKey;
  x: number;
  y: number;
  z: number;
  stories: number[];
}

export interface SceneEvents {
  hover(index: number, screen: { x: number; y: number } | null): void;
  select(index: number): void;
  hoverNode(node: number, screen: { x: number; y: number } | null): void;
  selectNode(node: number): void;
}

const NODE_VERTEX = /* glsl */ `
attribute vec3 color;
attribute float size;
uniform float uPixelRatio;
uniform float uTime;
uniform float uMotion;
varying vec3 vColor;
void main() {
  vec4 mv = modelViewMatrix * vec4(position + uMotion * vec3(0.0, 0.06 * sin(uTime * 0.6 + position.x), 0.0), 1.0);
  gl_Position = projectionMatrix * mv;
  gl_PointSize = min(size * uPixelRatio * 26.0 / -mv.z, 64.0 * uPixelRatio);
  vColor = color;
}`;

// A diamond with a bright rim: a name, not a story.
const NODE_FRAGMENT = /* glsl */ `
varying vec3 vColor;
void main() {
  vec2 c = abs(gl_PointCoord - 0.5);
  float d = c.x + c.y;
  if (d > 0.5) discard;
  float rim = smoothstep(0.32, 0.5, d);
  gl_FragColor = vec4(vColor * (0.5 + 1.4 * rim), 0.35 + 0.65 * rim);
}`;

// A thread from a name down to a story: bright at the name, fading towards the galaxy.
const EDGE_VERTEX = /* glsl */ `
attribute vec3 color;
attribute float strength;
varying vec3 vColor;
varying float vStrength;
void main() {
  vColor = color;
  vStrength = strength;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}`;

const EDGE_FRAGMENT = /* glsl */ `
uniform float uOpacity;
varying vec3 vColor;
varying float vStrength;
void main() {
  gl_FragColor = vec4(vColor, uOpacity * vStrength);
}`;

function easeInOut(t: number): number {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

export class UniverseScene {
  readonly renderer: THREE.WebGLRenderer;
  readonly camera: THREE.PerspectiveCamera;
  readonly controls: OrbitControls;
  private readonly scene = new THREE.Scene();
  private readonly composer: EffectComposer;
  private readonly bloom: UnrealBloomPass;
  private readonly clock = new THREE.Clock();
  private readonly raycaster = new THREE.Raycaster();
  private readonly pointer = new THREE.Vector2();
  private points: THREE.Points | null = null;
  private material: THREE.ShaderMaterial | null = null;
  private links: THREE.LineSegments | null = null;
  private linkMaterial: THREE.ShaderMaterial | null = null;
  private marker: THREE.Mesh;
  private data: Universe | null = null;

  // The network of names: their diamonds, every thread, and the bright
  // threads of the name in focus.
  private nodes: NetworkNode[] = [];
  private nodePoints: THREE.Points | null = null;
  private edges: THREE.LineSegments | null = null;
  private highlight: THREE.LineSegments | null = null;
  private nodeMaterial: THREE.ShaderMaterial | null = null;
  private edgeMaterial: THREE.ShaderMaterial | null = null;
  private hoverNode = -1;

  // Per star, what it shows now and what it is easing towards.
  private emphasis = new Float32Array(0);
  private emphasisTarget = new Float32Array(0);
  private lift = new Float32Array(0);
  private liftTarget = new Float32Array(0);
  private easing = false;

  private flight: { from: THREE.Vector3; to: THREE.Vector3; fromTarget: THREE.Vector3; toTarget: THREE.Vector3; start: number; duration: number } | null = null;
  private hoverIndex = -1;
  private pointerDirty = false;
  private motion: boolean;
  private frame = 0;

  constructor(private readonly host: HTMLElement, private readonly events: SceneEvents) {
    this.motion = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    this.renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.setSize(host.clientWidth, host.clientHeight);
    host.appendChild(this.renderer.domElement);

    this.scene.background = new THREE.Color("#04050d");
    this.scene.fog = new THREE.FogExp2("#04050d", 0.018);

    this.camera = new THREE.PerspectiveCamera(55, host.clientWidth / host.clientHeight, 0.05, 400);
    this.camera.position.copy(this.homePosition());

    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.06;
    this.controls.minDistance = 1.2;
    this.controls.maxDistance = 60;
    this.controls.autoRotate = this.motion;
    this.controls.autoRotateSpeed = 0.35;
    // A reader who takes the controls stops the slow turn until they let go for a while.
    let resume = 0;
    this.controls.addEventListener("start", () => {
      this.controls.autoRotate = false;
      window.clearTimeout(resume);
    });
    this.controls.addEventListener("end", () => {
      resume = window.setTimeout(() => (this.controls.autoRotate = this.motion), 8000);
    });

    this.composer = new EffectComposer(this.renderer);
    this.composer.addPass(new RenderPass(this.scene, this.camera));
    this.bloom = new UnrealBloomPass(new THREE.Vector2(host.clientWidth, host.clientHeight), 0.95, 0.55, 0.08);
    this.composer.addPass(this.bloom);
    this.composer.addPass(new OutputPass());

    this.addStarfield();

    // The selected story's ring: dimmer than white, so bloom does not blow
    // it out, and kept the same size on screen whatever the distance.
    this.marker = new THREE.Mesh(
      new THREE.RingGeometry(0.85, 1, 64),
      new THREE.MeshBasicMaterial({ color: "#9fc8ff", transparent: true, opacity: 0.55, side: THREE.DoubleSide, depthWrite: false }),
    );
    this.marker.visible = false;
    this.scene.add(this.marker);

    const resize = new ResizeObserver(() => this.resize());
    resize.observe(host);

    this.renderer.domElement.addEventListener("pointermove", (event) => {
      const box = this.renderer.domElement.getBoundingClientRect();
      this.pointer.set(((event.clientX - box.left) / box.width) * 2 - 1, -((event.clientY - box.top) / box.height) * 2 + 1);
      this.pointerDirty = true;
    });
    this.renderer.domElement.addEventListener("pointerleave", () => {
      this.hoverIndex = -1;
      this.hoverNode = -1;
      this.events.hover(-1, null);
      this.events.hoverNode(-1, null);
    });

    let down = { x: 0, y: 0 };
    this.renderer.domElement.addEventListener("pointerdown", (event) => (down = { x: event.clientX, y: event.clientY }));
    this.renderer.domElement.addEventListener("pointerup", (event) => {
      if (Math.hypot(event.clientX - down.x, event.clientY - down.y) < 5) {
        const under = this.pick();
        if (under.node >= 0) this.events.selectNode(under.node);
        else this.events.select(under.story);
      }
    });

    this.renderer.setAnimationLoop(() => this.tick());
  }

  // ---- the world ---------------------------------------------------------

  // A map point (x, y on the disc, z its depth) in world space: the disc
  // lies flat, depth is up.
  world(x: number, y: number, z = 0): THREE.Vector3 {
    return new THREE.Vector3(x * R, z * R * DEPTH_SCALE, -y * R);
  }

  private addStarfield(): void {
    const count = 2500;
    const positions = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      const r = 60 + Math.random() * 140;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      positions.set([r * Math.sin(phi) * Math.cos(theta), r * Math.cos(phi), r * Math.sin(phi) * Math.sin(theta)], i * 3);
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    const stars = new THREE.Points(geometry, new THREE.PointsMaterial({ color: "#7d86b8", size: 0.35, sizeAttenuation: true, transparent: true, opacity: 0.55, fog: false }));
    this.scene.add(stars);
  }

  // The holographic guides: the two rings the topics sit on, and a faint
  // line between each pair of sections.
  private addGuides(data: Universe): void {
    const guides = new THREE.Group();
    const ring = (radius: number, opacity: number) => {
      const points = Array.from({ length: 160 }, (_, i) => {
        const a = (i / 160) * Math.PI * 2;
        return this.world(Math.cos(a) * radius, Math.sin(a) * radius);
      });
      const line = new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(points), new THREE.LineBasicMaterial({ color: "#3a4a8a", transparent: true, opacity }));
      guides.add(line);
    };
    ring(0.6, 0.35);
    ring(0.88, 0.35);
    ring(1.08, 0.15);

    // Midway between one section's end and the next one's start: sections
    // run clockwise, so a section ends at angle - span / 2.
    data.groups.forEach((group, i) => {
      const next = data.groups[(i + 1) % data.groups.length];
      let start = next.angle + next.span / 2;
      const end = group.angle - group.span / 2;
      if (start > end) start -= Math.PI * 2;
      const edge = (start + end) / 2;
      const line = new THREE.Line(
        new THREE.BufferGeometry().setFromPoints([this.world(Math.cos(edge) * 0.3, Math.sin(edge) * 0.3), this.world(Math.cos(edge) * 1.05, Math.sin(edge) * 1.05)]),
        new THREE.LineBasicMaterial({ color: "#2a3570", transparent: true, opacity: 0.4 }),
      );
      guides.add(line);
    });

    this.scene.add(guides);
  }

  setData(data: Universe): void {
    this.data = data;
    this.addGuides(data);

    const n = data.count;
    const positions = new Float32Array(n * 3);
    const colors = new Float32Array(n * 3);
    const sizes = new Float32Array(n);
    const phases = new Float32Array(n);
    const palette = [...GROUP_COLORS, NO_GROUP_COLOR].map((c) => new THREE.Color(c));

    for (let i = 0; i < n; i++) {
      const p = this.world(data.positions[i * 3], data.positions[i * 3 + 1], data.positions[i * 3 + 2]);
      positions.set([p.x, p.y, p.z], i * 3);
      const color = palette[data.group[i] === NO_GROUP ? palette.length - 1 : Math.min(data.group[i], palette.length - 2)];
      colors.set([color.r, color.g, color.b], i * 3);
      // A stable spread of sizes and phases from the story's id, so a
      // star twinkles the same way on every visit.
      const h = parseInt(data.ids[i].slice(-6), 16) || i * 2654435761;
      phases[i] = (h % 1000) / 1000;
      sizes[i] = 2.4 + ((h >> 10) % 100) / 60;
    }

    this.emphasis = new Float32Array(n).fill(0);
    this.emphasisTarget = new Float32Array(n).fill(1);
    this.lift = new Float32Array(n).fill(-0.6);
    this.liftTarget = new Float32Array(n).fill(0);
    this.easing = true;

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    geometry.setAttribute("size", new THREE.BufferAttribute(sizes, 1));
    geometry.setAttribute("phase", new THREE.BufferAttribute(phases, 1));
    geometry.setAttribute("emphasis", new THREE.BufferAttribute(this.emphasis, 1).setUsage(THREE.DynamicDrawUsage));
    geometry.setAttribute("lift", new THREE.BufferAttribute(this.lift, 1).setUsage(THREE.DynamicDrawUsage));

    this.material = new THREE.ShaderMaterial({
      vertexShader: POINT_VERTEX,
      fragmentShader: POINT_FRAGMENT,
      uniforms: {
        uTime: { value: 0 },
        uMotion: { value: this.motion ? 1 : 0 },
        uPixelRatio: { value: this.renderer.getPixelRatio() },
        uSizeScale: { value: 9 },
      },
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });

    this.points = new THREE.Points(geometry, this.material);
    this.scene.add(this.points);
  }

  // ---- what is shown -------------------------------------------------------

  // Per story how bright it should be; the ones in focus rise a little
  // and the rest sink, all eased (setData's arrays). Stories in focus glow
  // more the fewer they are: 180 of today's stories among 5,000 were faint
  // at the brightness the whole universe has.
  focus(strong: Set<number> | null, lift = 0.35): void {
    if (!this.data) return;
    const glow = strong ? 1.5 + 1.0 * (1 - Math.min(1, strong.size / 2000)) : 1;
    for (let i = 0; i < this.data.count; i++) {
      const on = !strong || strong.has(i);
      this.emphasisTarget[i] = on ? glow : 0.06;
      this.liftTarget[i] = strong ? (on ? lift : -0.25) : 0;
    }
    this.easing = true;
    if (!this.motion) this.settle();
  }

  private settle(): void {
    this.emphasis.set(this.emphasisTarget);
    this.lift.set(this.liftTarget);
    this.markDirty();
    this.easing = false;
  }

  private markDirty(): void {
    if (!this.points) return;
    (this.points.geometry.getAttribute("emphasis") as THREE.BufferAttribute).needsUpdate = true;
    (this.points.geometry.getAttribute("lift") as THREE.BufferAttribute).needsUpdate = true;
  }

  position(index: number): THREE.Vector3 {
    const d = this.data!;
    const p = this.world(d.positions[index * 3], d.positions[index * 3 + 1], d.positions[index * 3 + 2]);
    p.y += this.lift[index] ?? 0;
    return p;
  }

  // Raised arcs of flowing light from one story to others (map points).
  setLinks(from: number, to: { x: number; y: number; z?: number }[], color = "#9fd4ff"): void {
    if (this.links) {
      this.scene.remove(this.links);
      this.links.geometry.dispose();
      this.links = null;
    }
    if (from < 0 || to.length === 0) return;

    const start = this.position(from);
    const segments = 24;
    const positions: number[] = [];
    const along: number[] = [];

    for (const target of to) {
      const end = this.world(target.x, target.y, target.z ?? 0);
      const middle = start.clone().lerp(end, 0.5);
      middle.y += start.distanceTo(end) * 0.35 + 0.3;
      const curve = new THREE.QuadraticBezierCurve3(start, middle, end);
      const points = curve.getPoints(segments);
      for (let s = 0; s < segments; s++) {
        positions.push(...points[s].toArray(), ...points[s + 1].toArray());
        along.push(s / segments, (s + 1) / segments);
      }
    }

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
    geometry.setAttribute("along", new THREE.Float32BufferAttribute(along, 1));
    this.linkMaterial ??= new THREE.ShaderMaterial({
      vertexShader: LINK_VERTEX,
      fragmentShader: LINK_FRAGMENT,
      uniforms: { uTime: { value: 0 }, uColor: { value: new THREE.Color(color) }, uMotion: { value: this.motion ? 1 : 0 } },
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
    this.links = new THREE.LineSegments(geometry, this.linkMaterial);
    this.scene.add(this.links);
  }

  mark(index: number): void {
    this.marker.visible = index >= 0;
    if (index >= 0) this.marker.position.copy(this.position(index));
  }

  // Flies the camera to look at a map point from `distance` away.
  flyTo(x: number, y: number, z = 0, distance = 4): void {
    const target = this.world(x, y, z);
    const direction = this.camera.position.clone().sub(this.controls.target).normalize();
    if (direction.y < 0.35) direction.y = 0.35;
    direction.normalize();
    this.flight = {
      from: this.camera.position.clone(),
      to: target.clone().add(direction.multiplyScalar(distance)),
      fromTarget: this.controls.target.clone(),
      toTarget: target,
      start: performance.now(),
      duration: this.motion ? 1400 : 0,
    };
  }

  // Far enough for the whole galaxy to fit the screen: a tall, narrow
  // screen (a phone) needs the camera further back than a wide one.
  private homePosition(): THREE.Vector3 {
    const aspect = this.host.clientWidth / Math.max(1, this.host.clientHeight);
    return new THREE.Vector3(0, 13, 17).multiplyScalar(Math.max(1, 1.15 / aspect));
  }

  home(): void {
    this.flight = {
      from: this.camera.position.clone(),
      to: this.homePosition(),
      fromTarget: this.controls.target.clone(),
      toTarget: new THREE.Vector3(0, 0, 0),
      start: performance.now(),
      duration: this.motion ? 1600 : 0,
    };
  }

  setMotion(on: boolean): void {
    this.motion = on;
    this.controls.autoRotate = on;
    if (this.material) this.material.uniforms.uMotion.value = on ? 1 : 0;
    if (this.nodeMaterial) this.nodeMaterial.uniforms.uMotion.value = on ? 1 : 0;
    if (this.linkMaterial) this.linkMaterial.uniforms.uMotion.value = on ? 1 : 0;
  }

  get moving(): boolean {
    return this.motion;
  }

  // Where a map point is on screen (CSS pixels), or null behind the camera.
  project(x: number, y: number, z = 0): { x: number; y: number; distance: number } | null {
    const p = this.world(x, y, z);
    const distance = p.distanceTo(this.camera.position);
    p.project(this.camera);
    if (p.z > 1) return null;
    return {
      x: (p.x * 0.5 + 0.5) * this.host.clientWidth,
      y: (-p.y * 0.5 + 0.5) * this.host.clientHeight,
      distance,
    };
  }

  // ---- each frame ------------------------------------------------------------

  // What is under the pointer: a name (it floats nearer) or a story.
  private pick(): { story: number; node: number } {
    this.raycaster.setFromCamera(this.pointer, this.camera);
    const reach = 0.012 * this.camera.position.distanceTo(this.controls.target) + 0.02;
    if (this.nodePoints?.visible) {
      this.raycaster.params.Points = { threshold: reach * 2.2 };
      const node = this.raycaster.intersectObject(this.nodePoints)[0];
      if (node?.index !== undefined) return { story: -1, node: node.index };
    }
    if (!this.points) return { story: -1, node: -1 };
    this.raycaster.params.Points = { threshold: reach };
    const hits = this.raycaster.intersectObject(this.points);
    const hit = hits.find((h) => h.index !== undefined && this.emphasisTarget[h.index] > 0.5);
    return { story: hit?.index ?? -1, node: -1 };
  }

  // ---- the network of names ---------------------------------------------------

  setNetwork(nodes: NetworkNode[]): void {
    for (const object of [this.nodePoints, this.edges, this.highlight]) {
      if (object) {
        this.scene.remove(object);
        object.geometry.dispose();
      }
    }
    this.nodePoints = this.edges = this.highlight = null;
    this.nodes = nodes;
    if (!this.data || nodes.length === 0) return;

    const colors = Object.fromEntries(KINDS.map((k) => [k.key, new THREE.Color(k.color)]));
    const positions = new Float32Array(nodes.length * 3);
    const nodeColors = new Float32Array(nodes.length * 3);
    const sizes = new Float32Array(nodes.length);
    const edgePositions: number[] = [];
    const edgeColors: number[] = [];
    const strength: number[] = [];

    nodes.forEach((node, n) => {
      const at = this.world(node.x, node.y, 0);
      at.y = node.z;
      positions.set([at.x, at.y, at.z], n * 3);
      const color = colors[node.kind];
      nodeColors.set([color.r, color.g, color.b], n * 3);
      sizes[n] = 0.7 + Math.sqrt(node.stories.length) * 0.12;
      // A thread's light divided across its name's stories: on 29 Oct,
      // 7,500 threads at one brightness added up to a white ball.
      const share = Math.min(1, 2.5 / Math.sqrt(node.stories.length));
      for (const story of node.stories) {
        const s = this.world(this.data!.positions[story * 3], this.data!.positions[story * 3 + 1], this.data!.positions[story * 3 + 2]);
        edgePositions.push(at.x, at.y, at.z, s.x, s.y, s.z);
        edgeColors.push(color.r, color.g, color.b, color.r, color.g, color.b);
        strength.push(share, share * 0.12);
      }
    });

    const nodeGeometry = new THREE.BufferGeometry();
    nodeGeometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    nodeGeometry.setAttribute("color", new THREE.BufferAttribute(nodeColors, 3));
    nodeGeometry.setAttribute("size", new THREE.BufferAttribute(sizes, 1));
    this.nodeMaterial ??= new THREE.ShaderMaterial({
      vertexShader: NODE_VERTEX,
      fragmentShader: NODE_FRAGMENT,
      uniforms: { uPixelRatio: { value: this.renderer.getPixelRatio() }, uTime: { value: 0 }, uMotion: { value: this.motion ? 1 : 0 } },
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
    this.nodePoints = new THREE.Points(nodeGeometry, this.nodeMaterial);
    this.scene.add(this.nodePoints);

    const edgeGeometry = new THREE.BufferGeometry();
    edgeGeometry.setAttribute("position", new THREE.Float32BufferAttribute(edgePositions, 3));
    edgeGeometry.setAttribute("color", new THREE.Float32BufferAttribute(edgeColors, 3));
    edgeGeometry.setAttribute("strength", new THREE.Float32BufferAttribute(strength, 1));
    // Normal blending, faint: added together, thousands of threads summed
    // to white and bloom spread it over the galaxy (29 Oct). Blended, an
    // overlap stays its kind's colour. The name in focus is drawn bright,
    // added (highlightNode).
    this.edgeMaterial ??= new THREE.ShaderMaterial({
      vertexShader: EDGE_VERTEX,
      fragmentShader: EDGE_FRAGMENT,
      uniforms: { uOpacity: { value: EDGE_OPACITY } },
      transparent: true,
      depthWrite: false,
      blending: THREE.NormalBlending,
    });
    this.edges = new THREE.LineSegments(edgeGeometry, this.edgeMaterial);
    this.scene.add(this.edges);
  }

  // The threads of one name, bright; -1 for none. The rest dim meanwhile.
  highlightNode(node: number): void {
    if (this.highlight) {
      this.scene.remove(this.highlight);
      this.highlight.geometry.dispose();
      this.highlight = null;
    }
    if (this.edgeMaterial) this.edgeMaterial.uniforms.uOpacity.value = node >= 0 ? EDGE_OPACITY / 3 : EDGE_OPACITY;
    if (node < 0 || !this.data || !this.nodes[node]) return;

    const n = this.nodes[node];
    const at = this.world(n.x, n.y, 0);
    at.y = n.z;
    const color = new THREE.Color(KINDS.find((k) => k.key === n.kind)!.color);
    const positions: number[] = [];
    const colors: number[] = [];
    const strength: number[] = [];
    for (const story of n.stories) {
      const s = this.position(story);
      positions.push(at.x, at.y, at.z, s.x, s.y, s.z);
      colors.push(color.r, color.g, color.b, color.r, color.g, color.b);
      // Brightest where it reaches a story, fading towards the name: the
      // reader looks for the stories, and hundreds of threads meeting at
      // full light burned the name white (29 Oct).
      strength.push(0.15, 1);
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
    geometry.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
    geometry.setAttribute("strength", new THREE.Float32BufferAttribute(strength, 1));
    const material = new THREE.ShaderMaterial({
      vertexShader: EDGE_VERTEX,
      fragmentShader: EDGE_FRAGMENT,
      // Bright, but divided like the faint threads and blended, not added:
      // Barcelona's 744 added at full brightness blew the view out, and
      // even divided they burned white where they meet (29 Oct).
      uniforms: { uOpacity: { value: Math.min(0.8, 8 / Math.sqrt(n.stories.length)) } },
      transparent: true,
      depthWrite: false,
      blending: THREE.NormalBlending,
    });
    this.highlight = new THREE.LineSegments(geometry, material);
    this.scene.add(this.highlight);
  }

  setNetworkVisible(visible: boolean): void {
    if (this.nodePoints) this.nodePoints.visible = visible;
    if (this.edges) this.edges.visible = visible;
    if (this.highlight) this.highlight.visible = visible;
  }

  // Where a name floats, on screen.
  projectNode(node: number): { x: number; y: number; distance: number } | null {
    const n = this.nodes[node];
    if (!n) return null;
    const p = this.world(n.x, n.y, 0);
    p.y = n.z;
    const distance = p.distanceTo(this.camera.position);
    p.project(this.camera);
    if (p.z > 1) return null;
    return { x: (p.x * 0.5 + 0.5) * this.host.clientWidth, y: (-p.y * 0.5 + 0.5) * this.host.clientHeight, distance };
  }

  flyToNode(node: number): void {
    const n = this.nodes[node];
    if (!n) return;
    const target = this.world(n.x, n.y, 0);
    target.y = n.z * 0.6;
    const direction = this.camera.position.clone().sub(this.controls.target).normalize();
    this.flight = {
      from: this.camera.position.clone(),
      to: target.clone().add(direction.multiplyScalar(11)),
      fromTarget: this.controls.target.clone(),
      toTarget: target,
      start: performance.now(),
      duration: this.motion ? 1400 : 0,
    };
  }

  private resize(): void {
    const width = this.host.clientWidth;
    const height = this.host.clientHeight;
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(width, height);
    this.composer.setSize(width, height);
  }

  onFrame: (() => void) | null = null;

  private tick(): void {
    const dt = Math.min(0.05, this.clock.getDelta());
    const time = this.clock.elapsedTime;

    if (this.flight) {
      const t = this.flight.duration ? Math.min(1, (performance.now() - this.flight.start) / this.flight.duration) : 1;
      const e = easeInOut(t);
      this.camera.position.lerpVectors(this.flight.from, this.flight.to, e);
      this.controls.target.lerpVectors(this.flight.fromTarget, this.flight.toTarget, e);
      if (t >= 1) this.flight = null;
    }

    if (this.easing && this.points) {
      const k = Math.min(1, dt * 3.2);
      let still = true;
      for (let i = 0; i < this.emphasis.length; i++) {
        const de = this.emphasisTarget[i] - this.emphasis[i];
        const dl = this.liftTarget[i] - this.lift[i];
        if (Math.abs(de) > 0.002 || Math.abs(dl) > 0.002) {
          this.emphasis[i] += de * k;
          this.lift[i] += dl * k;
          still = false;
        }
      }
      this.markDirty();
      if (still) this.easing = false;
    }

    if (this.material) this.material.uniforms.uTime.value = time;
    if (this.nodeMaterial) this.nodeMaterial.uniforms.uTime.value = time;
    if (this.linkMaterial) this.linkMaterial.uniforms.uTime.value = time;
    if (this.marker.visible) {
      this.marker.lookAt(this.camera.position);
      const onScreen = this.marker.position.distanceTo(this.camera.position) * 0.022;
      this.marker.scale.setScalar(onScreen * (1 + (this.motion ? 0.12 * Math.sin(time * 3) : 0)));
    }

    // Hover, at most every other frame: the raycast is a pass over every star.
    if (this.pointerDirty && this.frame++ % 2 === 0) {
      this.pointerDirty = false;
      const under = this.pick();
      const box = this.renderer.domElement.getBoundingClientRect();
      const screen = { x: ((this.pointer.x + 1) / 2) * box.width, y: ((1 - this.pointer.y) / 2) * box.height };
      if (under.node !== this.hoverNode) {
        this.hoverNode = under.node;
        this.events.hoverNode(under.node, under.node >= 0 ? screen : null);
      }
      if (under.story !== this.hoverIndex) {
        this.hoverIndex = under.story;
        this.events.hover(under.story, under.story >= 0 ? screen : null);
      }
    }

    this.controls.update(dt);
    this.composer.render();
    this.onFrame?.();
  }
}
