/**
 * The studio: a small WebGL renderer that turns a figure from models.js into moving pictures.
 *
 * A clip is a short motion: the figure breathes, sways and blinks, runs away from the camera or
 * towards it, or jumps and spins. Each frame of a clip is one pose of the whole figure; the
 * frames are drawn side by side on one canvas, a strip that the style sheet plays back. A frame
 * is drawn in three passes: a soft shadow on the ground, then every part a little larger, inside
 * out and in a dark shade of its own colour, which leaves an outline, then every part lit like a
 * vinyl toy: two soft bands of light, cool shadows, a rim of light and a darker foot. A browser
 * without WebGL gets `null` and the client keeps its flat art.
 */

export const FRAME_WIDTH = 192;
export const FRAME_HEIGHT = 256;
const TUBE = 0.22;
const PITCH_DEGREES = 15;
const OUTLINE = 0.035;
const HALF_WIDTH = 1.34;
const HALF_HEIGHT = (HALF_WIDTH * FRAME_HEIGHT) / FRAME_WIDTH;
const BELOW_GROUND = 0.28;
const STRIDE = 6;
const FULL_TURN = 2 * Math.PI;

/**
 * What a frame shows, in model units as the camera sees them. A frame is taller than a figure:
 * the room above the head is where the figure jumps.
 */
export const FRAME = {
  left: -HALF_WIDTH,
  right: HALF_WIDTH,
  bottom: -BELOW_GROUND,
  top: 2 * HALF_HEIGHT - BELOW_GROUND,
};

/** How many frames each clip of a champion has. All but "spin" loop. */
export const CLIPS = { idle: 8, back: 8, charge: 8, spin: 12 };

/** The clips of the things that stand around the arena: one picture, or one slow turn. */
export const PROP_CLIPS = { still: 1, turn: 12 };

const FRAMES = { ...CLIPS, ...PROP_CLIPS };

/** The frame of the standing clip in which a figure has its eyes shut. */
export const BLINK_FRAME = 5;

/**
 * A run: two hops per loop, leaning forward, squashed on the ground and stretched in the air.
 * The lean turns about the middle of the feet, so the lowest lift keeps the toes above ground.
 */
function runPose(yaw, turn) {
  const hop = Math.abs(Math.sin(turn));
  return { yaw: yaw + 7 * Math.sin(turn), lean: 14, squash: 0.93 + 0.12 * hop, lift: 0.06 + 0.26 * hop };
}

const POSES = {
  // Standing: the figure sways from side to side and breathes.
  idle: (turn) => ({
    yaw: -22 + 15 * Math.sin(turn),
    lean: 0,
    squash: 1 + 0.03 * Math.sin(turn + Math.PI / 2),
    lift: 0,
  }),
  // Running at the enemy, seen from behind.
  back: (turn) => runPose(158, turn),
  // The same run seen from the front: the opposing board.
  charge: (turn) => runPose(22, turn),
  // A win: one full turn during a jump.
  spin: (turn) => ({
    yaw: -22 + (360 * turn) / FULL_TURN,
    lean: 0,
    squash: 1 + 0.08 * Math.sin(turn / 2),
    lift: 0.55 * Math.sin(turn / 2),
  }),
  // A thing in the arena, seen a little from the side.
  still: () => ({ yaw: -28, lean: 0, squash: 1, lift: 0 }),
  // The same thing turning once about itself.
  turn: (turn) => ({ yaw: (360 * turn) / FULL_TURN, lean: 0, squash: 1, lift: 0 }),
};

/** How many frames a clip has; throws a RangeError for a name that is not a clip. */
export function framesOf(clip) {
  if (!Object.prototype.hasOwnProperty.call(FRAMES, clip)) {
    throw new RangeError(`there is no clip called "${clip}"`);
  }
  return FRAMES[clip];
}

/**
 * The pose of the whole figure in one frame of a clip: `yaw` turns it about the vertical axis
 * and `lean` tilts it forward about the ground, both in degrees; `squash` scales its height and
 * keeps its volume; `lift` is its height above the ground in model units; `blink` says whether
 * its eyes are shut.
 */
export function poseOf(clip, frame) {
  const pose = POSES[clip]((FULL_TURN * frame) / framesOf(clip));
  return { ...pose, blink: clip === "idle" && frame === BLINK_FRAME };
}

const VERTEX_SHADER = `
attribute vec3 aPosition;
attribute vec3 aNormal;
uniform mat3 uTurn;
uniform vec3 uSize;
uniform vec3 uAt;
uniform mat3 uView;
uniform vec3 uSquash;
uniform vec3 uLift;
uniform mediump float uGrow;
uniform vec3 uFrame;
varying vec3 vNormal;
varying vec3 vLocal;
varying float vHeight;
void main() {
  vec3 normal = normalize(uTurn * (aNormal / uSize));
  vec3 world = uTurn * (aPosition * uSize) + uAt + normal * uGrow;
  vec3 seen = uView * (world * uSquash) + uLift;
  vNormal = uView * normal;
  vLocal = aPosition;
  vHeight = world.y;
  gl_Position = vec4(seen.x * uFrame.x, seen.y * uFrame.y + uFrame.z, -seen.z * 0.1, 1.0);
}`;

/* uShadow > 0 draws the shadow on the ground, uGrow > 0 the outline, otherwise the lit part;
   uGlow fades the light out, for eyes, lamps and anything else that shines by itself. */
const FRAGMENT_SHADER = `
precision mediump float;
uniform vec3 uColour;
uniform float uGrow;
uniform float uGlow;
uniform float uShadow;
varying vec3 vNormal;
varying vec3 vLocal;
varying float vHeight;
void main() {
  if (uShadow > 0.0) {
    float fade = 1.0 - smoothstep(0.25, 1.0, length(vLocal.xz));
    gl_FragColor = vec4(0.0, 0.0, 0.0, uShadow * fade);
    return;
  }
  if (uGrow > 0.0) {
    gl_FragColor = vec4(uColour * vec3(0.24, 0.22, 0.32) + vec3(0.02, 0.025, 0.06), 1.0);
    return;
  }
  vec3 normal = normalize(vNormal);
  vec3 key = normalize(vec3(-0.5, 0.75, 0.65));
  float wrap = dot(normal, key) * 0.5 + 0.5;
  float band = 0.64 * smoothstep(0.34, 0.5, wrap) + 0.36 * smoothstep(0.7, 0.86, wrap);
  vec3 dark = uColour * vec3(0.5, 0.5, 0.68) + vec3(0.0, 0.005, 0.03);
  vec3 bright = min(uColour * 1.1 + 0.03, 1.0);
  vec3 colour = mix(dark, bright, band);
  colour *= mix(0.72, 1.0, smoothstep(-0.05, 0.8, vHeight));
  float edge = pow(1.0 - clamp(normal.z, 0.0, 1.0), 2.5);
  float rim = edge * smoothstep(-0.35, 0.5, normal.y + 0.5 * normal.x);
  colour += vec3(0.5, 0.68, 1.0) * rim * 0.42;
  float shine = smoothstep(0.94, 0.985, dot(normal, normalize(key + vec3(0.0, 0.0, 1.0))));
  colour += shine * 0.14;
  gl_FragColor = vec4(mix(colour, min(uColour * 1.12, 1.0), uGlow), 1.0);
}`;

/* Meshes: vertices are x, y, z, then the normal; triangles turn counter-clockwise from outside. */

/**
 * How finely a round part is drawn, from the largest parts down to the smallest. The software
 * renderers that stand in for a graphics card pay for every triangle, and a part a few pixels
 * across looks the same with a quarter of them.
 */
export const DETAILS = [
  { segments: 20, rings: 12 },
  { segments: 14, rings: 8 },
  { segments: 10, rings: 6 },
];
const FINE = DETAILS[0];

/** Which of DETAILS a part of these half-sizes is drawn with. */
export function detailOf(size) {
  const largest = Math.max(...size);
  if (largest >= 0.3) {
    return 0;
  }
  return largest >= 0.12 ? 1 : 2;
}

function ringPoint(index, segments) {
  const angle = (FULL_TURN * index) / segments;
  return [Math.cos(angle), Math.sin(angle)];
}

/** A unit ball: scaled, it is an ellipsoid. */
export function ballMesh({ segments, rings } = FINE) {
  const vertices = [];
  const indices = [];
  for (let ring = 0; ring <= rings; ring += 1) {
    const polar = (Math.PI * ring) / rings;
    for (let segment = 0; segment <= segments; segment += 1) {
      const [cos, sin] = ringPoint(segment, segments);
      const point = [Math.sin(polar) * cos, Math.cos(polar), Math.sin(polar) * sin];
      vertices.push(...point, ...point);
    }
  }
  for (let ring = 0; ring < rings; ring += 1) {
    for (let segment = 0; segment < segments; segment += 1) {
      const a = ring * (segments + 1) + segment;
      const b = a + segments + 1;
      indices.push(a, a + 1, b, a + 1, b + 1, b);
    }
  }
  return { vertices, indices };
}

/** A disc of radius 1 at height `y` facing `up` (1) or down (-1), added to a mesh. */
function addCap(mesh, y, up, segments) {
  const centre = mesh.vertices.length / STRIDE;
  mesh.vertices.push(0, y, 0, 0, up, 0);
  for (let segment = 0; segment <= segments; segment += 1) {
    const [cos, sin] = ringPoint(segment, segments);
    mesh.vertices.push(cos, y, sin, 0, up, 0);
  }
  for (let segment = 0; segment < segments; segment += 1) {
    const rim = centre + 1 + segment;
    mesh.indices.push(centre, up > 0 ? rim + 1 : rim, up > 0 ? rim : rim + 1);
  }
}

/** The side of a cylinder or a cone: `top` is the radius at y = 1, `lean` tilts the normals. */
function sideMesh(top, lean, segments) {
  const mesh = { vertices: [], indices: [] };
  const length = Math.hypot(1, lean);
  for (let segment = 0; segment <= segments; segment += 1) {
    const [cos, sin] = ringPoint(segment, segments);
    const normal = [cos / length, lean / length, sin / length];
    mesh.vertices.push(cos, -1, sin, ...normal, cos * top, 1, sin * top, ...normal);
  }
  for (let segment = 0; segment < segments; segment += 1) {
    const a = segment * 2;
    mesh.indices.push(a, a + 1, a + 2, a + 2, a + 1, a + 3);
  }
  return mesh;
}

/** A cylinder of radius 1 from y = -1 to y = 1, closed at both ends. */
export function cylinderMesh({ segments } = FINE) {
  const mesh = sideMesh(1, 0, segments);
  addCap(mesh, 1, 1, segments);
  addCap(mesh, -1, -1, segments);
  return mesh;
}

/** A cone with its base of radius 1 at y = -1 and its tip at y = 1. */
export function coneMesh({ segments } = FINE) {
  const mesh = sideMesh(0, 0.5, segments);
  addCap(mesh, -1, -1, segments);
  return mesh;
}

/** A box from -1 to 1 on every axis, with flat faces. */
export function boxMesh() {
  const faces = [
    [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
    [[-1, 0, 0], [0, 0, 1], [0, 1, 0]],
    [[0, 1, 0], [0, 0, 1], [1, 0, 0]],
    [[0, -1, 0], [1, 0, 0], [0, 0, 1]],
    [[0, 0, 1], [1, 0, 0], [0, 1, 0]],
    [[0, 0, -1], [0, 1, 0], [1, 0, 0]],
  ];
  const mesh = { vertices: [], indices: [] };
  faces.forEach(([normal, u, v], face) => {
    for (const [su, sv] of [[-1, -1], [1, -1], [1, 1], [-1, 1]]) {
      const corner = normal.map((value, axis) => value + su * u[axis] + sv * v[axis]);
      mesh.vertices.push(...corner, ...normal);
    }
    const first = face * 4;
    mesh.indices.push(first, first + 1, first + 2, first, first + 2, first + 3);
  });
  return mesh;
}

/** A ring lying flat: its outer edge is at radius 1 and its tube has radius TUBE. */
export function ringMesh({ segments, rings } = FINE) {
  const mesh = { vertices: [], indices: [] };
  const radius = 1 - TUBE;
  for (let around = 0; around <= segments; around += 1) {
    const [cos, sin] = ringPoint(around, segments);
    for (let tube = 0; tube <= rings; tube += 1) {
      const angle = (FULL_TURN * tube) / rings;
      const out = Math.cos(angle);
      const up = Math.sin(angle);
      const reach = radius + TUBE * out;
      mesh.vertices.push(reach * cos, TUBE * up, reach * sin, out * cos, up, out * sin);
    }
  }
  for (let around = 0; around < segments; around += 1) {
    for (let tube = 0; tube < rings; tube += 1) {
      const a = around * (rings + 1) + tube;
      const c = a + rings + 1;
      mesh.indices.push(a, a + 1, c, c, a + 1, c + 1);
    }
  }
  return mesh;
}

export const MESHES = {
  ball: ballMesh,
  cylinder: cylinderMesh,
  cone: coneMesh,
  box: boxMesh,
  ring: ringMesh,
};

/* Rotations: 3 by 3 matrices in column order, as WebGL takes them. */

function multiply(a, b) {
  const out = new Array(9).fill(0);
  for (let column = 0; column < 3; column += 1) {
    for (let row = 0; row < 3; row += 1) {
      for (let k = 0; k < 3; k += 1) {
        out[column * 3 + row] += a[k * 3 + row] * b[column * 3 + k];
      }
    }
  }
  return out;
}

function aboutX(degrees) {
  const angle = (degrees * Math.PI) / 180;
  const [cos, sin] = [Math.cos(angle), Math.sin(angle)];
  return [1, 0, 0, 0, cos, sin, 0, -sin, cos];
}

function aboutY(degrees) {
  const angle = (degrees * Math.PI) / 180;
  const [cos, sin] = [Math.cos(angle), Math.sin(angle)];
  return [cos, 0, -sin, 0, 1, 0, sin, 0, cos];
}

function aboutZ(degrees) {
  const angle = (degrees * Math.PI) / 180;
  const [cos, sin] = [Math.cos(angle), Math.sin(angle)];
  return [cos, sin, 0, -sin, cos, 0, 0, 0, 1];
}

/** The rotation of a part: about x first, then y, then z, in degrees. */
export function turnMatrix([rx, ry, rz]) {
  return multiply(aboutZ(rz), multiply(aboutY(ry), aboutX(rx)));
}

/** The camera: the figure leant forward by `lean`, turned by `yaw` and seen a little from above. */
export function viewMatrix(yaw, lean = 0) {
  return multiply(aboutX(PITCH_DEGREES), multiply(aboutY(yaw), aboutX(lean)));
}

/**
 * A pose as the shader takes it: the scale along each axis, the rotation that follows it and
 * the lift as the camera sees it. The lights ignore the squash.
 */
export function poseUniforms(pose) {
  const wide = 1 / Math.sqrt(pose.squash);
  const pitch = (PITCH_DEGREES * Math.PI) / 180;
  return {
    squash: [wide, pose.squash, wide],
    view: viewMatrix(pose.yaw, pose.lean),
    lift: [0, pose.lift * Math.cos(pitch), pose.lift * Math.sin(pitch)],
  };
}

/* The renderer. */

const UNIFORMS = [
  "uTurn",
  "uSize",
  "uAt",
  "uView",
  "uSquash",
  "uLift",
  "uGrow",
  "uGlow",
  "uShadow",
  "uFrame",
  "uColour",
];
const NO_TURN = [0, 0, 0];
const SHADOW_DARKNESS = 0.42;
const SHADOW_REACH = 0.85;
const SHADOW_HEIGHT = 0.7;

function compile(gl, type, source) {
  const shader = gl.createShader(type);
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  return gl.getShaderParameter(shader, gl.COMPILE_STATUS) ? shader : null;
}

function link(gl) {
  const vertex = compile(gl, gl.VERTEX_SHADER, VERTEX_SHADER);
  const fragment = compile(gl, gl.FRAGMENT_SHADER, FRAGMENT_SHADER);
  if (!vertex || !fragment) {
    return null;
  }
  const program = gl.createProgram();
  gl.attachShader(program, vertex);
  gl.attachShader(program, fragment);
  gl.bindAttribLocation(program, 0, "aPosition");
  gl.bindAttribLocation(program, 1, "aNormal");
  gl.linkProgram(program);
  return gl.getProgramParameter(program, gl.LINK_STATUS) ? program : null;
}

function upload(gl, mesh) {
  const vertices = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, vertices);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(mesh.vertices), gl.STATIC_DRAW);
  const indices = gl.createBuffer();
  gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, indices);
  gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, new Uint16Array(mesh.indices), gl.STATIC_DRAW);
  return { vertices, indices, count: mesh.indices.length };
}

/** Open the studio, or return `null` when this browser cannot draw in 3D. */
export function openStudio() {
  const canvas = document.createElement("canvas");
  canvas.width = FRAME_WIDTH * CLIPS.idle;
  canvas.height = FRAME_HEIGHT;
  const gl = canvas.getContext("webgl", { antialias: true, preserveDrawingBuffer: true });
  const program = gl ? link(gl) : null;
  if (!program) {
    return null;
  }
  gl.useProgram(program);
  gl.enable(gl.DEPTH_TEST);
  gl.enable(gl.CULL_FACE);
  gl.enableVertexAttribArray(0);
  gl.enableVertexAttribArray(1);
  const uniforms = {};
  for (const name of UNIFORMS) {
    uniforms[name] = gl.getUniformLocation(program, name);
  }
  // The canvas keeps its colours multiplied by their opacity, and so does the shadow.
  gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
  gl.uniform3f(uniforms.uFrame, 1 / HALF_WIDTH, 1 / HALF_HEIGHT, (BELOW_GROUND - HALF_HEIGHT) / HALF_HEIGHT);
  const meshes = {};
  for (const [kind, build] of Object.entries(MESHES)) {
    meshes[kind] = DETAILS.map((detail) => upload(gl, build(detail)));
  }
  return { canvas, gl, uniforms, meshes };
}

function drawPart(studio, part, grow) {
  const { gl, uniforms } = studio;
  const mesh = studio.meshes[part.kind][detailOf(part.size)];
  gl.bindBuffer(gl.ARRAY_BUFFER, mesh.vertices);
  gl.vertexAttribPointer(0, 3, gl.FLOAT, false, STRIDE * 4, 0);
  gl.vertexAttribPointer(1, 3, gl.FLOAT, false, STRIDE * 4, 12);
  gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, mesh.indices);
  gl.uniformMatrix3fv(uniforms.uTurn, false, turnMatrix(part.turn));
  gl.uniform3fv(uniforms.uSize, part.size);
  gl.uniform3fv(uniforms.uAt, part.at);
  gl.uniform3fv(uniforms.uColour, part.colour);
  gl.uniform1f(uniforms.uGrow, grow);
  gl.uniform1f(uniforms.uGlow, part.glow || 0);
  gl.drawElements(gl.TRIANGLES, mesh.count, gl.UNSIGNED_SHORT, 0);
}

/**
 * How far a figure reaches over the ground to its side and to its front, for its shadow. Parts
 * high above the ground count for less: a hat throws less shadow at the feet than a belly.
 */
export function footprintOf(parts) {
  let wide = 0.3;
  let deep = 0.3;
  for (const part of parts) {
    const near = 1 / (1 + Math.max(part.at[1] - SHADOW_HEIGHT, 0));
    wide = Math.max(wide, (Math.abs(part.at[0]) + 0.7 * part.size[0]) * near);
    deep = Math.max(deep, (Math.abs(part.at[2]) + 0.7 * part.size[2]) * near);
  }
  return [Math.min(wide, 1) * SHADOW_REACH, Math.min(deep, 1) * SHADOW_REACH];
}

/** The shadow under a figure as a part: a flat disc that shrinks and pales as the figure rises. */
export function shadowOf(parts, lift) {
  const [wide, deep] = footprintOf(parts);
  const height = Math.min(Math.max(lift, 0) / 0.6, 1);
  const reach = 1 - 0.3 * height;
  return {
    kind: "ball",
    at: [0, 0.01, 0],
    size: [wide * reach, 0.002, deep * reach],
    colour: NO_TURN,
    turn: NO_TURN,
    darkness: SHADOW_DARKNESS * (1 - 0.5 * height),
  };
}

/** Draw the shadow of a figure: it lies on the ground whatever the figure does above it. */
function drawShadow(studio, parts, pose) {
  const { gl, uniforms } = studio;
  const shadow = shadowOf(parts, pose.lift);
  const flat = poseUniforms({ yaw: pose.yaw, lean: 0, squash: 1, lift: 0 });
  gl.uniform3fv(uniforms.uSquash, flat.squash);
  gl.uniformMatrix3fv(uniforms.uView, false, flat.view);
  gl.uniform3fv(uniforms.uLift, flat.lift);
  gl.uniform1f(uniforms.uShadow, shadow.darkness);
  gl.enable(gl.BLEND);
  gl.depthMask(false);
  gl.cullFace(gl.BACK);
  drawPart(studio, shadow, 0);
  gl.depthMask(true);
  gl.disable(gl.BLEND);
  gl.uniform1f(uniforms.uShadow, 0);
}

/** Whether a part shows in a pose: an eye is open or shut, everything else always shows. */
export function showsIn(part, pose) {
  return !part.when || part.when === (pose.blink ? "shut" : "open");
}

/** Draw a figure in a pose into the part of the canvas that the viewport covers. */
function drawPose(studio, parts, pose, shadow) {
  const { gl, uniforms } = studio;
  const shown = parts.filter((part) => showsIn(part, pose));
  if (shadow) {
    drawShadow(studio, shown, pose);
  }
  const { squash, view, lift } = poseUniforms(pose);
  gl.uniform3fv(uniforms.uSquash, squash);
  gl.uniformMatrix3fv(uniforms.uView, false, view);
  gl.uniform3fv(uniforms.uLift, lift);
  gl.cullFace(gl.FRONT);
  shown.filter((part) => !part.bare).forEach((part) => drawPart(studio, part, OUTLINE));
  gl.cullFace(gl.BACK);
  shown.forEach((part) => drawPart(studio, part, 0));
}

/**
 * Draw every frame of a clip side by side on the studio's canvas and return that canvas.
 *
 * One canvas holds the whole strip, so the picture is read back from the graphics card once
 * for a clip and not once for a frame, which is what takes the time on a software renderer.
 * `scale` draws every frame that many times larger, for things that are shown large; without
 * `shadow` the thing throws none, as something that hangs in the air.
 */
export function renderClip(studio, parts, clip, { scale = 1, shadow = true } = {}) {
  const { canvas, gl } = studio;
  const frames = framesOf(clip);
  const width = FRAME_WIDTH * scale;
  const height = FRAME_HEIGHT * scale;
  if (canvas.width !== frames * width || canvas.height !== height) {
    canvas.width = frames * width;
    canvas.height = height;
  }
  gl.clearColor(0, 0, 0, 0);
  gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
  for (let frame = 0; frame < frames; frame += 1) {
    gl.viewport(frame * width, 0, width, height);
    drawPose(studio, parts, poseOf(clip, frame), shadow);
  }
  return canvas;
}
