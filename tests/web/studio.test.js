import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { KINDS } from "../../src/tft/web/models.js";
import { FRAMES, MESHES, swayOf, turnMatrix, viewMatrix } from "../../src/tft/web/studio.js";

const STRIDE = 6;
const CLOSE = 1e-9;

function vertex(mesh, index) {
  const at = index * STRIDE;
  return { point: mesh.vertices.slice(at, at + 3), normal: mesh.vertices.slice(at + 3, at + 6) };
}

const minus = (a, b) => a.map((value, axis) => value - b[axis]);
const dot = (a, b) => a.reduce((sum, value, axis) => sum + value * b[axis], 0);
const cross = (a, b) => [
  a[1] * b[2] - a[2] * b[1],
  a[2] * b[0] - a[0] * b[2],
  a[0] * b[1] - a[1] * b[0],
];

/** Apply a 3 by 3 matrix in column order to a vector. */
function apply(matrix, vector) {
  return [0, 1, 2].map((row) => dot([matrix[row], matrix[3 + row], matrix[6 + row]], vector));
}

describe("the meshes", () => {
  it("cover every kind of part", () => {
    assert.deepEqual(Object.keys(MESHES).sort(), Object.values(KINDS).sort());
  });

  for (const [kind, build] of Object.entries(MESHES)) {
    it(`${kind}: fits the unit box, has unit normals and valid triangles`, () => {
      const mesh = build();
      const count = mesh.vertices.length / STRIDE;
      assert.equal(mesh.vertices.length % STRIDE, 0);
      assert.equal(mesh.indices.length % 3, 0);
      assert.ok(count < 65536);
      assert.ok(mesh.indices.every((index) => Number.isInteger(index) && index >= 0 && index < count));
      for (let index = 0; index < count; index += 1) {
        const { point, normal } = vertex(mesh, index);
        assert.ok(point.every((value) => Math.abs(value) <= 1 + CLOSE), `${kind}: point ${point}`);
        assert.ok(Math.abs(Math.hypot(...normal) - 1) < 1e-6, `${kind}: normal ${normal}`);
      }
    });

    it(`${kind}: triangles turn counter-clockwise seen from outside`, () => {
      const mesh = build();
      let checked = 0;
      for (let at = 0; at < mesh.indices.length; at += 3) {
        const [a, b, c] = [0, 1, 2].map((corner) => vertex(mesh, mesh.indices[at + corner]));
        const facing = cross(minus(b.point, a.point), minus(c.point, a.point));
        if (Math.hypot(...facing) > 1e-6) {
          const outward = a.normal.map((value, axis) => value + b.normal[axis] + c.normal[axis]);
          assert.ok(dot(facing, outward) > 0, `${kind}: triangle ${at / 3} faces inward`);
          checked += 1;
        }
      }
      assert.ok(checked >= 12, `${kind}: only ${checked} triangles checked`);
    });
  }
});

describe("the rotations", () => {
  it("leave a part alone when it is not turned", () => {
    assert.deepEqual(turnMatrix([0, 0, 0]), [1, 0, 0, 0, 1, 0, 0, 0, 1]);
  });

  it("turn about x, then y, then z", () => {
    const close = (actual, expected) =>
      actual.forEach((value, axis) => assert.ok(Math.abs(value - expected[axis]) < 1e-9, `${actual}`));
    close(apply(turnMatrix([90, 0, 0]), [0, 1, 0]), [0, 0, 1]);
    close(apply(turnMatrix([0, 90, 0]), [0, 0, 1]), [1, 0, 0]);
    close(apply(turnMatrix([0, 0, 90]), [1, 0, 0]), [0, 1, 0]);
    close(apply(turnMatrix([90, 0, 90]), [0, 1, 0]), [0, 0, 1]);
    close(apply(turnMatrix([90, 90, 0]), [0, 1, 0]), [1, 0, 0]);
  });

  it("keep lengths and right angles", () => {
    for (const matrix of [turnMatrix([20, -35, 110]), viewMatrix(-22), viewMatrix(40)]) {
      const columns = [0, 3, 6].map((start) => matrix.slice(start, start + 3));
      for (const column of columns) {
        assert.ok(Math.abs(Math.hypot(...column) - 1) < 1e-9);
      }
      assert.ok(Math.abs(dot(columns[0], columns[1])) < 1e-9);
      assert.ok(Math.abs(dot(columns[1], columns[2])) < 1e-9);
      assert.ok(Math.abs(dot(cross(columns[0], columns[1]), columns[2]) - 1) < 1e-9);
    }
  });

  it("look down on the figure from the front", () => {
    const top = apply(viewMatrix(0), [0, 2, 0]);
    assert.ok(top[2] > 0 && top[1] > 1.8);
  });

  it("sway back to where they started", () => {
    const turns = Array.from({ length: FRAMES }, (_, frame) => swayOf(frame));
    assert.ok(Math.abs(swayOf(0) - swayOf(FRAMES)) < 1e-9);
    assert.ok(Math.max(...turns) - Math.min(...turns) > 20);
    assert.ok(Math.abs(turns[1] - turns[0]) < 15);
    assert.ok(Math.abs(turns[FRAMES - 1] - turns[0]) < 15);
  });
});
