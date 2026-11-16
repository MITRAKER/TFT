import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { KINDS, MODELS, PROPS, partsOf, propPartsOf } from "../../src/tft/web/models.js";
import {
  BLINK_FRAME,
  CLIPS,
  DETAILS,
  FRAME,
  FRAME_HEIGHT,
  FRAME_WIDTH,
  MESHES,
  PROP_CLIPS,
  detailOf,
  footprintOf,
  framesOf,
  poseOf,
  poseUniforms,
  shadowOf,
  showsIn,
  turnMatrix,
  viewMatrix,
} from "../../src/tft/web/studio.js";

const STRIDE = 6;
const CLOSE = 1e-9;
// The dark shell around every part, drawn a little larger than the part itself.
const OUTLINE = 0.035;
const LOOPS = ["idle", "back", "charge"];

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

const radians = (degrees) => (degrees * Math.PI) / 180;

/** Where the camera sees a point of the model in a pose, as the shader works it out. */
function seenPoint(pose, point) {
  const { squash, view, lift } = poseUniforms(pose);
  const seen = apply(view, point.map((value, axis) => value * squash[axis]));
  return seen.map((value, axis) => value + lift[axis]);
}

describe("the meshes", () => {
  it("cover every kind of part; an eye is drawn as balls", () => {
    const solids = Object.values(KINDS).filter((kind) => kind !== "eye");
    assert.deepEqual(Object.keys(MESHES).sort(), solids.sort());
  });

  it("come finer for large parts than for small ones", () => {
    assert.equal(detailOf([0.5, 0.6, 0.4]), 0);
    assert.equal(detailOf([0.3, 0.05, 0.05]), 0);
    assert.equal(detailOf([0.2, 0.29, 0.1]), 1);
    assert.equal(detailOf([0.12, 0.02, 0.02]), 1);
    assert.equal(detailOf([0.06, 0.07, 0.05]), 2);
    for (let level = 1; level < DETAILS.length; level += 1) {
      assert.ok(DETAILS[level].segments < DETAILS[level - 1].segments);
      assert.ok(MESHES.ball(DETAILS[level]).indices.length < MESHES.ball(DETAILS[level - 1]).indices.length);
    }
    assert.deepEqual(MESHES.ball(), MESHES.ball(DETAILS[0]));
  });

  for (const [kind, build] of Object.entries(MESHES)) {
    for (const [level, detail] of DETAILS.entries()) {
      it(`${kind}, detail ${level}: fits the unit box, has unit normals and valid triangles`, () => {
        const mesh = build(detail);
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

      it(`${kind}, detail ${level}: triangles turn counter-clockwise seen from outside`, () => {
        const mesh = build(detail);
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
    for (const matrix of [turnMatrix([20, -35, 110]), viewMatrix(-22), viewMatrix(40), viewMatrix(158, 14)]) {
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

  it("lean a figure towards where it faces", () => {
    const upright = apply(viewMatrix(0), [0, 2, 0]);
    const leaning = apply(viewMatrix(0, 14), [0, 2, 0]);
    assert.ok(leaning[2] > upright[2], "the head comes towards the camera it faces");
    const away = apply(viewMatrix(180, 14), [0, 2, 0]);
    assert.ok(away[2] < upright[2], "turned around, the head goes away from the camera");
  });
});

describe("the clips", () => {
  const posesOf = (clip) => Array.from({ length: CLIPS[clip] }, (_, frame) => poseOf(clip, frame));

  it("are the standing loop, the two runs and the jump", () => {
    assert.deepEqual(CLIPS, { idle: 8, back: 8, charge: 8, spin: 12 });
    assert.throws(() => poseOf("moonwalk", 0), RangeError);
    assert.throws(() => poseOf("constructor", 0), RangeError);
    assert.throws(() => framesOf("moonwalk"), RangeError);
    assert.equal(framesOf("spin"), 12);
  });

  it("blink once in the standing loop and nowhere else", () => {
    assert.ok(BLINK_FRAME > 0 && BLINK_FRAME < CLIPS.idle);
    for (const clip of Object.keys(CLIPS)) {
      const shut = posesOf(clip).filter((pose) => pose.blink);
      assert.equal(shut.length, clip === "idle" ? 1 : 0, clip);
    }
    assert.equal(poseOf("idle", BLINK_FRAME).blink, true);
  });

  it("show an eye open or shut, and everything else always", () => {
    const awake = { blink: false };
    const blinking = { blink: true };
    assert.equal(showsIn({ when: "" }, awake), true);
    assert.equal(showsIn({ when: "" }, blinking), true);
    assert.equal(showsIn({ when: "open" }, awake), true);
    assert.equal(showsIn({ when: "open" }, blinking), false);
    assert.equal(showsIn({ when: "shut" }, awake), false);
    assert.equal(showsIn({ when: "shut" }, blinking), true);
  });

  it("show the things of the arena in one picture, or in one turn", () => {
    assert.deepEqual(PROP_CLIPS, { still: 1, turn: 12 });
    assert.equal(framesOf("still"), 1);
    const turn = Array.from({ length: PROP_CLIPS.turn }, (_, frame) => poseOf("turn", frame));
    assert.ok(Math.abs(poseOf("turn", PROP_CLIPS.turn).yaw - turn[0].yaw - 360) < CLOSE);
    for (const pose of [poseOf("still", 0), ...turn]) {
      assert.deepEqual([pose.lean, pose.squash, pose.lift, pose.blink], [0, 1, 0, false]);
    }
  });

  it("loop back to where they started", () => {
    for (const clip of LOOPS) {
      const first = poseOf(clip, 0);
      const again = poseOf(clip, CLIPS[clip]);
      for (const key of ["yaw", "lean", "squash", "lift"]) {
        assert.ok(Math.abs(first[key] - again[key]) < CLOSE, `${clip}: ${key}`);
      }
    }
  });

  it("move a little from one frame to the next", () => {
    for (const clip of Object.keys(CLIPS)) {
      const poses = posesOf(clip);
      poses.forEach((pose, frame) => {
        const next = poseOf(clip, frame + 1);
        assert.ok(Math.abs(next.yaw - pose.yaw) <= 30 + CLOSE, `${clip}: frame ${frame} turns too far`);
        assert.ok(Math.abs(next.lift - pose.lift) < 0.3, `${clip}: frame ${frame} jumps too far`);
      });
    }
  });

  it("never sink into the ground, flatten or stretch a figure too far", () => {
    for (const clip of Object.keys(CLIPS)) {
      for (const pose of posesOf(clip)) {
        assert.ok(pose.lift >= 0, `${clip}: lift ${pose.lift}`);
        assert.ok(pose.squash > 0.85 && pose.squash < 1.15, `${clip}: squash ${pose.squash}`);
      }
    }
  });

  it("stand and sway while idle", () => {
    const poses = posesOf("idle");
    const turns = poses.map((pose) => pose.yaw);
    assert.ok(Math.max(...turns) - Math.min(...turns) > 20);
    assert.ok(poses.every((pose) => pose.lift === 0 && pose.lean === 0));
    assert.ok(poses.every((pose) => Math.cos(radians(pose.yaw)) > 0), "faces the camera");
    const breaths = poses.map((pose) => pose.squash);
    assert.ok(Math.max(...breaths) > 1.02 && Math.min(...breaths) < 0.98);
  });

  it("run away from the camera in back and towards it in charge", () => {
    const back = posesOf("back");
    const charge = posesOf("charge");
    assert.ok(back.every((pose) => Math.cos(radians(pose.yaw)) < 0));
    assert.ok(charge.every((pose) => Math.cos(radians(pose.yaw)) > 0));
    back.forEach((pose, frame) => {
      assert.ok(pose.lean > 0, "leans forward");
      assert.equal(pose.lean, charge[frame].lean);
      assert.equal(pose.lift, charge[frame].lift);
      assert.equal(pose.squash, charge[frame].squash);
    });
    // Two hops in a loop: the lift peaks twice and the figure lands in between.
    const lifts = back.map((pose) => pose.lift);
    const peak = Math.max(...lifts);
    assert.equal(lifts.filter((lift) => lift === peak).length, 2);
    assert.ok(peak - Math.min(...lifts) > 0.15);
    assert.equal(lifts[0], Math.min(...lifts));
    assert.ok(Math.abs(lifts[CLIPS.back / 2] - lifts[0]) < CLOSE);
  });

  it("turn exactly once during the jump of spin", () => {
    const poses = posesOf("spin");
    const idle = poseOf("idle", 0);
    assert.ok(Math.abs(poses[0].yaw - idle.yaw) < CLOSE, "starts where idle stands");
    assert.ok(Math.abs(poseOf("spin", CLIPS.spin).yaw - poses[0].yaw - 360) < CLOSE);
    poses.forEach((pose, frame) => {
      assert.ok(Math.abs(pose.yaw - poses[0].yaw - (360 * frame) / CLIPS.spin) < CLOSE);
    });
    assert.equal(poses[0].lift, 0);
    assert.ok(Math.abs(poseOf("spin", CLIPS.spin).lift) < CLOSE, "lands at the end");
    assert.ok(Math.max(...poses.map((pose) => pose.lift)) > 0.4);
    assert.equal(poses[CLIPS.spin / 2].lift, Math.max(...poses.map((pose) => pose.lift)));
  });
});

describe("a pose", () => {
  it("keeps the volume of a figure when it squashes", () => {
    for (const squash of [0.93, 1, 1.08]) {
      const [x, y, z] = poseUniforms({ yaw: 0, lean: 0, squash, lift: 0 }).squash;
      assert.equal(y, squash);
      assert.equal(x, z);
      assert.ok(Math.abs(x * y * z - 1) < CLOSE);
    }
  });

  it("leaves the middle of the feet on the ground and lifts straight up", () => {
    const standing = { yaw: 37, lean: 14, squash: 0.95, lift: 0 };
    assert.ok(seenPoint(standing, [0, 0, 0]).every((value) => Math.abs(value) < CLOSE));
    const lifted = seenPoint({ ...standing, lift: 0.5 }, [0, 0, 0]);
    assert.ok(Math.abs(lifted[0]) < CLOSE);
    assert.ok(lifted[1] > 0.45 && lifted[1] < 0.5);
  });

  it("turns the face away at half a turn", () => {
    const front = seenPoint({ yaw: 0, lean: 0, squash: 1, lift: 0 }, [0, 1, 0.5]);
    const behind = seenPoint({ yaw: 180, lean: 0, squash: 1, lift: 0 }, [0, 1, 0.5]);
    assert.ok(front[2] > behind[2]);
    assert.ok(Math.abs(front[0]) < CLOSE && Math.abs(behind[0]) < CLOSE);
  });
});

describe("the frame", () => {
  it("is taller than wide, with the ground near its bottom", () => {
    assert.equal(FRAME_WIDTH % 4, 0);
    assert.equal(FRAME_HEIGHT * 3, FRAME_WIDTH * 4);
    const width = FRAME.right - FRAME.left;
    const height = FRAME.top - FRAME.bottom;
    assert.ok(Math.abs(height / width - FRAME_HEIGHT / FRAME_WIDTH) < CLOSE);
    assert.equal(FRAME.left, -FRAME.right);
    assert.ok(FRAME.bottom < 0 && FRAME.bottom > -0.5);
  });

  /** Every point of a figure as it is drawn: the vertices of its parts, on their dark shells. */
  function shellOf(parts) {
    const points = [];
    for (const part of parts) {
      const mesh = MESHES[part.kind](DETAILS[detailOf(part.size)]);
      const turn = turnMatrix(part.turn);
      for (let index = 0; index < mesh.vertices.length / STRIDE; index += 1) {
        const { point, normal } = vertex(mesh, index);
        const turned = apply(turn, point.map((value, axis) => value * part.size[axis]));
        const out = apply(turn, normal.map((value, axis) => value / part.size[axis]));
        const length = Math.hypot(...out);
        points.push(turned.map((value, axis) => value + part.at[axis] + (out[axis] / length) * OUTLINE));
      }
    }
    return points;
  }

  /** Where a pose puts the first point that leaves the frame, as text; `null` when all stay in. */
  function strayIn(points, pose) {
    for (const point of points) {
      const [x, y] = seenPoint(pose, point);
      if (x <= FRAME.left || x >= FRAME.right || y <= FRAME.bottom || y >= FRAME.top) {
        return `${x.toFixed(3)}, ${y.toFixed(3)}`;
      }
    }
    return null;
  }

  it("holds every figure in every pose of every clip", () => {
    for (const name of Object.keys(MODELS)) {
      const points = shellOf(partsOf(name));
      for (const [clip, frames] of Object.entries(CLIPS)) {
        for (let frame = 0; frame < frames; frame += 1) {
          assert.equal(strayIn(points, poseOf(clip, frame)), null, `${name}, frame ${frame} of ${clip}`);
        }
      }
    }
  });

  it("holds everything that stands around the arena", () => {
    for (const name of Object.keys(PROPS)) {
      const points = shellOf(propPartsOf(name));
      for (const [clip, frames] of Object.entries(PROP_CLIPS)) {
        for (let frame = 0; frame < frames; frame += 1) {
          assert.equal(strayIn(points, poseOf(clip, frame)), null, `${name}, frame ${frame} of ${clip}`);
        }
      }
    }
  });

  it("is left by a figure that is lifted too high", () => {
    const points = shellOf(partsOf("Candle Reader"));
    assert.equal(strayIn(points, { yaw: 0, lean: 0, squash: 1, lift: 0.8 }), null);
    assert.notEqual(strayIn(points, { yaw: 0, lean: 0, squash: 1, lift: 1.2 }), null);
  });
});

describe("the shadow", () => {
  it("is as wide as what a figure has near the ground", () => {
    const post = [{ at: [0, 1, 0], size: [0.1, 1, 0.1] }];
    const table = [{ at: [0, 0.4, 0], size: [0.9, 0.05, 0.5] }];
    const [postWide, postDeep] = footprintOf(post);
    const [tableWide, tableDeep] = footprintOf(table);
    assert.ok(tableWide > postWide && tableDeep > postDeep);
    assert.ok(tableWide > tableDeep, "wider than deep, like the table");
    assert.ok(postWide > 0.2, "even a post throws a shadow");
  });

  it("counts a part high up for less than the same part at the feet", () => {
    const low = footprintOf([{ at: [0.6, 0.3, 0], size: [0.2, 0.2, 0.2] }]);
    const high = footprintOf([{ at: [0.6, 1.9, 0], size: [0.2, 0.2, 0.2] }]);
    assert.ok(high[0] < low[0]);
  });

  it("stays inside the frame for every figure and every prop", () => {
    const all = [
      ...Object.keys(MODELS).map((name) => partsOf(name)),
      ...Object.keys(PROPS).map((name) => propPartsOf(name)),
    ];
    for (const parts of all) {
      const [wide, deep] = footprintOf(parts);
      assert.ok(wide < FRAME.right && deep < FRAME.right);
    }
  });

  it("shrinks and pales as the figure rises, and lies flat on the ground", () => {
    const parts = partsOf("Bear Baron");
    const standing = shadowOf(parts, 0);
    const jumping = shadowOf(parts, 0.55);
    assert.ok(jumping.size[0] < standing.size[0] && jumping.size[2] < standing.size[2]);
    assert.ok(jumping.darkness < standing.darkness && jumping.darkness > 0);
    assert.ok(standing.size[1] < 0.01 && standing.at[1] < 0.05);
    assert.deepEqual(shadowOf(parts, -1), standing);
    assert.deepEqual(shadowOf(parts, 5).size, shadowOf(parts, 0.6).size);
  });
});
