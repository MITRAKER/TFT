import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { CHAMPIONS } from "../../src/tft/web/art.js";
import { KINDS, MODELS, parsePart, partsOf, rgb } from "../../src/tft/web/models.js";

describe("the 3D figures", () => {
  it("exist for every champion that has a portrait", () => {
    assert.deepEqual(Object.keys(MODELS).sort(), Object.keys(CHAMPIONS).sort());
  });

  it("are built from parts that can be drawn", () => {
    const kinds = Object.values(KINDS);
    for (const name of Object.keys(MODELS)) {
      const parts = partsOf(name);
      assert.ok(parts.length >= 6, `${name} has too few parts`);
      for (const part of parts) {
        assert.ok(kinds.includes(part.kind), `${name}: kind ${part.kind}`);
        assert.equal(part.mirrored, false);
        assert.ok(part.size.every((value) => value > 0 && value <= 1), `${name}: size ${part.size}`);
        assert.ok(part.colour.every((value) => value >= 0 && value <= 1), `${name}: colour`);
      }
    }
  });

  it("stand on the ground, fit their frame and face the camera", () => {
    for (const name of Object.keys(MODELS)) {
      const parts = partsOf(name);
      const lowest = Math.min(...parts.map((part) => part.at[1] - Math.max(...part.size)));
      const highest = Math.max(...parts.map((part) => part.at[1] + part.size[1]));
      const widest = Math.max(...parts.map((part) => Math.abs(part.at[0]) + part.size[0]));
      assert.ok(lowest > -0.75, `${name} sinks into the ground: ${lowest}`);
      assert.ok(highest > 1.3 && highest < 2.45, `${name} is ${highest} tall`);
      assert.ok(widest < 1.3, `${name} is ${widest} wide`);
    }
  });

  it("mirror the parts written with a capital letter", () => {
    const parts = partsOf("Pip Squeak");
    const ears = parts.filter((part) => part.at[1] === 1.62 && part.size[0] === 0.26);
    assert.equal(ears.length, 2);
    assert.deepEqual(ears.map((ear) => ear.at[0]).sort(), [-0.38, 0.38]);
    const legs = partsOf("Spread Spider").filter((part) => part.turn[2] !== 0 && part.kind === "ball");
    const left = legs.filter((leg) => leg.at[0] < 0);
    const right = legs.filter((leg) => leg.at[0] > 0);
    assert.equal(left.length, right.length);
    assert.deepEqual(
      left.map((leg) => leg.turn[2]).sort(),
      right.map((leg) => -leg.turn[2]).sort(),
    );
    assert.equal(partsOf("Nobody"), null);
    assert.equal(partsOf("constructor"), null);
  });
});

describe("parsePart", () => {
  it("reads a part", () => {
    assert.deepEqual(parsePart("s 0 .55 0 | .42 .5 .38 | #ff8000"), {
      kind: "ball",
      mirrored: false,
      at: [0, 0.55, 0],
      size: [0.42, 0.5, 0.38],
      colour: [1, 128 / 255, 0],
      turn: [0, 0, 0],
    });
    const cone = parsePart("K .14 2 -.04 | .06 .36 .06 | #3b2f2a | -10 0 -8");
    assert.equal(cone.kind, "cone");
    assert.equal(cone.mirrored, true);
    assert.deepEqual(cone.turn, [-10, 0, -8]);
    assert.deepEqual(["c", "b", "t"].map((kind) => parsePart(`${kind} 0 0 0 | 1 1 1 | #000000`).kind), [
      "cylinder",
      "box",
      "ring",
    ]);
  });

  it("refuses what it cannot read", () => {
    const bad = [
      "",
      "x 0 0 0 | 1 1 1 | #000000",
      "s 0 0 | 1 1 1 | #000000",
      "s 0 0 0 | 1 1 | #000000",
      "s 0 0 0 | 1 1 1 | red",
      "s 0 0 0 | 1 1 1 | #000000 | 1 2",
      "s 0 0 0 | 1 1 1 | #000000 | 1 2 3 | 4",
      "s 0 zero 0 | 1 1 1 | #000000",
    ];
    for (const spec of bad) {
      assert.throws(() => parsePart(spec), RangeError, spec);
    }
  });

  it("turns a colour into numbers", () => {
    assert.deepEqual(rgb("#ffffff"), [1, 1, 1]);
    assert.deepEqual(rgb("#000000"), [0, 0, 0]);
    assert.deepEqual(rgb("#336699"), [0.2, 0.4, 0.6]);
  });
});
