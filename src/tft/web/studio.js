/**
 * The studio: a small WebGL renderer that turns a figure from models.js into pictures.
 *
 * Each figure is drawn a few times while it sways from side to side; the frames are laid next
 * to one another in a sprite sheet that the style sheet plays back. Every part is drawn twice:
 * once a little larger, inside out and dark, which leaves an outline, then lit in three bands
 * like a vinyl toy. A browser without WebGL gets `null` and the client keeps its flat art.
 */

export const FRAMES = 8;
export const FRAME_SIZE = 192;
const SEGMENTS = 20;
const RINGS = 12;
const TUBE = 0.22;
const SWAY_DEGREES = 15;
const BASE_YAW_DEGREES = -22;
const PITCH_DEGREES = 15;
const OUTLINE = 0.035;
const HALF_WIDTH = 1.34;
const EYE_HEIGHT = 1.06;
const STRIDE = 6;

const VERTEX_SHADER = `
attribute vec3 aPosition;
attribute vec3 aNormal;
uniform mat3 uTurn;
uniform vec3 uSize;
uniform vec3 uAt;
uniform mat3 uView;
uniform mediump float uGrow;
uniform vec3 uFrame;
varying vec3 vNormal;
void main() {
  vec3 normal = normalize(uTurn * (aNormal / uSize));
  vec3 world = uTurn * (aPosition * uSize) + uAt + normal * uGrow;
  vec3 seen = uView * world;
  vNormal = uView * normal;
  gl_Position = vec4(seen.x * uFrame.x, seen.y * uFrame.y + uFrame.z, -seen.z * 0.1, 1.0);
}`;

const FRAGMENT_SHADER = `
precision mediump float;
uniform vec3 uColour;
uniform float uGrow;
varying vec3 vNormal;
void main() {
  if (uGrow > 0.0) {
    gl_FragColor = vec4(0.04, 0.06, 0.12, 1.0);
    return;
  }
  vec3 normal = normalize(vNormal);
  vec3 light = normalize(vec3(-0.5, 0.75, 0.65));
  float lit = dot(normal, light);
  float shade = 0.56 + 0.3 * smoothstep(-0.2, -0.05, lit) + 0.24 * smoothstep(0.3, 0.45, lit);
  float rim = pow(1.0 - clamp(normal.z, 0.0, 1.0), 3.0) * 0.22;
  float shine = smoothstep(0.955, 0.985, dot(normal, normalize(light + vec3(0.0, 0.0, 1.0)))) * 0.3;
  gl_FragColor = vec4(uColour * shade + vec3(0.55, 0.7, 1.0) * rim + shine, 1.0);
}`;

/* Meshes: vertices are x, y, z, then the normal; triangles turn counter-clockwise from outside. */

function ringPoint(index) {
  const angle = (2 * Math.PI * index) / SEGMENTS;
  return [Math.cos(angle), Math.sin(angle)];
}

/** A unit ball: scaled, it is an ellipsoid. */
export function ballMesh() {
  const vertices = [];
  const indices = [];
  for (let ring = 0; ring <= RINGS; ring += 1) {
    const polar = (Math.PI * ring) / RINGS;
    for (let segment = 0; segment <= SEGMENTS; segment += 1) {
      const [cos, sin] = ringPoint(segment);
      const point = [Math.sin(polar) * cos, Math.cos(polar), Math.sin(polar) * sin];
      vertices.push(...point, ...point);
    }
  }
  for (let ring = 0; ring < RINGS; ring += 1) {
    for (let segment = 0; segment < SEGMENTS; segment += 1) {
      const a = ring * (SEGMENTS + 1) + segment;
      const b = a + SEGMENTS + 1;
      indices.push(a, a + 1, b, a + 1, b + 1, b);
    }
  }
  return { vertices, indices };
}

/** A disc of radius 1 at height `y` facing `up` (1) or down (-1), added to a mesh. */
function addCap(mesh, y, up) {
  const centre = mesh.vertices.length / STRIDE;
  mesh.vertices.push(0, y, 0, 0, up, 0);
  for (let segment = 0; segment <= SEGMENTS; segment += 1) {
    const [cos, sin] = ringPoint(segment);
    mesh.vertices.push(cos, y, sin, 0, up, 0);
  }
  for (let segment = 0; segment < SEGMENTS; segment += 1) {
    const rim = centre + 1 + segment;
    mesh.indices.push(centre, up > 0 ? rim + 1 : rim, up > 0 ? rim : rim + 1);
  }
}

/** The side of a cylinder or a cone: `top` is the radius at y = 1, `lean` tilts the normals. */
function sideMesh(top, lean) {
  const mesh = { vertices: [], indices: [] };
  const length = Math.hypot(1, lean);
  for (let segment = 0; segment <= SEGMENTS; segment += 1) {
    const [cos, sin] = ringPoint(segment);
    const normal = [cos / length, lean / length, sin / length];
    mesh.vertices.push(cos, -1, sin, ...normal, cos * top, 1, sin * top, ...normal);
  }
  for (let segment = 0; segment < SEGMENTS; segment += 1) {
    const a = segment * 2;
    mesh.indices.push(a, a + 1, a + 2, a + 2, a + 1, a + 3);
  }
  return mesh;
}

/** A cylinder of radius 1 from y = -1 to y = 1, closed at both ends. */
export function cylinderMesh() {
  const mesh = sideMesh(1, 0);
  addCap(mesh, 1, 1);
  addCap(mesh, -1, -1);
  return mesh;
}

/** A cone with its base of radius 1 at y = -1 and its tip at y = 1. */
export function coneMesh() {
  const mesh = sideMesh(0, 0.5);
  addCap(mesh, -1, -1);
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
export function ringMesh() {
  const mesh = { vertices: [], indices: [] };
  const radius = 1 - TUBE;
  for (let around = 0; around <= SEGMENTS; around += 1) {
    const [cos, sin] = ringPoint(around);
    for (let tube = 0; tube <= RINGS; tube += 1) {
      const angle = (2 * Math.PI * tube) / RINGS;
      const out = Math.cos(angle);
      const up = Math.sin(angle);
      const reach = radius + TUBE * out;
      mesh.vertices.push(reach * cos, TUBE * up, reach * sin, out * cos, up, out * sin);
    }
  }
  for (let around = 0; around < SEGMENTS; around += 1) {
    for (let tube = 0; tube < RINGS; tube += 1) {
      const a = around * (RINGS + 1) + tube;
      const c = a + RINGS + 1;
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

/** The camera: the figure turned by `yaw`, seen a little from above. */
export function viewMatrix(yaw) {
  return multiply(aboutX(PITCH_DEGREES), aboutY(yaw));
}

/** How far a frame of the sway is turned, in degrees. */
export function swayOf(frame) {
  return BASE_YAW_DEGREES + SWAY_DEGREES * Math.sin((2 * Math.PI * frame) / FRAMES);
}

/* The renderer. */

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
  canvas.width = FRAME_SIZE;
  canvas.height = FRAME_SIZE;
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
  for (const name of ["uTurn", "uSize", "uAt", "uView", "uGrow", "uFrame", "uColour"]) {
    uniforms[name] = gl.getUniformLocation(program, name);
  }
  gl.uniform3f(uniforms.uFrame, 1 / HALF_WIDTH, 1 / HALF_WIDTH, -EYE_HEIGHT / HALF_WIDTH);
  const meshes = {};
  for (const [kind, build] of Object.entries(MESHES)) {
    meshes[kind] = upload(gl, build());
  }
  return { canvas, gl, uniforms, meshes };
}

function drawPart(studio, part, grow) {
  const { gl, uniforms } = studio;
  const mesh = studio.meshes[part.kind];
  gl.bindBuffer(gl.ARRAY_BUFFER, mesh.vertices);
  gl.vertexAttribPointer(0, 3, gl.FLOAT, false, STRIDE * 4, 0);
  gl.vertexAttribPointer(1, 3, gl.FLOAT, false, STRIDE * 4, 12);
  gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, mesh.indices);
  gl.uniformMatrix3fv(uniforms.uTurn, false, turnMatrix(part.turn));
  gl.uniform3fv(uniforms.uSize, part.size);
  gl.uniform3fv(uniforms.uAt, part.at);
  gl.uniform3fv(uniforms.uColour, part.colour);
  gl.uniform1f(uniforms.uGrow, grow);
  gl.drawElements(gl.TRIANGLES, mesh.count, gl.UNSIGNED_SHORT, 0);
}

/** Draw a figure turned by `yaw` degrees onto the studio's canvas. */
export function drawFigure(studio, parts, yaw) {
  const { gl, uniforms } = studio;
  gl.viewport(0, 0, FRAME_SIZE, FRAME_SIZE);
  gl.clearColor(0, 0, 0, 0);
  gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
  gl.uniformMatrix3fv(uniforms.uView, false, viewMatrix(yaw));
  gl.cullFace(gl.FRONT);
  parts.forEach((part) => drawPart(studio, part, OUTLINE));
  gl.cullFace(gl.BACK);
  parts.forEach((part) => drawPart(studio, part, 0));
}

/** The sprite sheet of a figure as a canvas: FRAMES pictures of the sway, side by side. */
export function renderSheet(studio, parts) {
  const sheet = document.createElement("canvas");
  sheet.width = FRAME_SIZE * FRAMES;
  sheet.height = FRAME_SIZE;
  const pen = sheet.getContext("2d");
  for (let frame = 0; frame < FRAMES; frame += 1) {
    drawFigure(studio, parts, swayOf(frame));
    pen.drawImage(studio.canvas, frame * FRAME_SIZE, 0);
  }
  return sheet;
}
