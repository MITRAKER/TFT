import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { CHAMPIONS } from "../../src/tft/web/art.js";
import {
  KINDS,
  MODELS,
  PROPS,
  eyeParts,
  parsePart,
  partsFrom,
  partsOf,
  propPartsOf,
  rgb,
} from "../../src/tft/web/models.js";

/** The kinds a part can have once eyes are taken apart: the ones the studio has a mesh for. */
const SOLIDS = Object.values(KINDS).filter((kind) => kind !== "eye");

describe("the 3D figures", () => {
  it("exist for every champion that has a portrait", () => {
    assert.deepEqual(Object.keys(MODELS).sort(), Object.keys(CHAMPIONS).sort());
  });

  /** Check that every part is one the studio can draw. */
  function checkParts(name, parts) {
    for (const part of parts) {
      assert.ok(SOLIDS.includes(part.kind), `${name}: kind ${part.kind}`);
      assert.equal("mirrored" in part, false);
      assert.ok(part.size.every((value) => value > 0 && value <= 1), `${name}: size ${part.size}`);
      assert.ok(part.colour.every((value) => value >= 0 && value <= 1), `${name}: colour`);
      assert.ok(part.at.concat(part.turn).every(Number.isFinite), `${name}: place`);
      assert.ok(part.glow >= 0 && part.glow <= 1, `${name}: glow ${part.glow}`);
      assert.equal(typeof part.bare, "boolean");
      assert.ok(["", "open", "shut"].includes(part.when), `${name}: when ${part.when}`);
    }
  }

  it("are built from parts that can be drawn", () => {
    for (const name of Object.keys(MODELS)) {
      const parts = partsOf(name);
      assert.ok(parts.length >= 6, `${name} has too few parts`);
      assert.ok(parts.length <= 40, `${name} has ${parts.length} parts, which is slow to draw`);
      checkParts(name, parts);
    }
  });

  it("come with the things that stand around the arena", () => {
    assert.deepEqual(Object.keys(PROPS).sort(), ["Bear Statue", "Bell", "Bull Statue", "Coin", "Pylon"]);
    for (const name of Object.keys(PROPS)) {
      const parts = propPartsOf(name);
      assert.ok(parts.length >= 6, `${name} has too few parts`);
      checkParts(name, parts);
      assert.ok(parts.every((part) => part.when === ""), `${name} does not blink`);
    }
    assert.equal(propPartsOf("Pip Squeak"), null);
    assert.equal(propPartsOf("constructor"), null);
  });

  it("stand on the ground, fit their frame and face the camera", () => {
    for (const name of Object.keys(MODELS)) {
      const parts = partsOf(name);
      const lowest = Math.min(...parts.map((part) => part.at[1] - Math.max(...part.size)));
      const highest = Math.max(...parts.map((part) => part.at[1] + part.size[1]));
      const widest = Math.max(...parts.map((part) => Math.abs(part.at[0]) + part.size[0]));
      assert.ok(lowest > -0.75, `${name} sinks into the ground: ${lowest}`);
      assert.ok(highest > 1.1 && highest < 2.45, `${name} is ${highest} tall`);
      assert.ok(widest < 1.3, `${name} is ${widest} wide`);
    }
  });

  it("mirror the parts written with a capital letter", () => {
    const parts = partsOf("Pip Squeak");
    const ears = parts.filter((part) => part.at[1] === 1.66 && part.size[0] === 0.27);
    assert.equal(ears.length, 2);
    assert.deepEqual(ears.map((ear) => ear.at[0]).sort(), [-0.42, 0.42]);
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

describe("the eyes", () => {
  const eyesOf = (name) => partsOf(name).filter((part) => part.when !== "");

  it("are open in every frame but the blink, where a lid takes their place", () => {
    const eyes = eyesOf("Pip Squeak");
    const open = eyes.filter((part) => part.when === "open");
    const shut = eyes.filter((part) => part.when === "shut");
    // Two eyes: a white, a dark iris and a point of light each, and one lid each.
    assert.equal(open.length, 6);
    assert.equal(shut.length, 2);
    assert.ok(eyes.every((part) => part.kind === "ball"));
    assert.deepEqual(shut.map((lid) => Math.sign(lid.at[0])).sort(), [-1, 1]);
  });

  it("show a pupil in an iris that is not dark", () => {
    const dark = eyeParts(partsFromEye("e 0 1 0 | .1 .1 .05 | #141824"));
    const bright = eyeParts(partsFromEye("e 0 1 0 | .1 .1 .05 | #e09a1b"));
    assert.equal(dark.length, 4);
    assert.equal(bright.length, 5);
    assert.equal(eyesOf("Fed Whisperer").filter((part) => part.when === "open").length, 8);
  });

  it("look towards each other, with the light on the same side in both", () => {
    const [right, left] = ["e .2 1 0 | .1 .1 .05 | #141824", "e -.2 1 0 | .1 .1 .05 | #141824"].map((spec) =>
      eyeParts(partsFromEye(spec)),
    );
    const iris = (eye) => eye[1].at[0] - eye[0].at[0];
    assert.ok(iris(right) < 0 && iris(left) > 0, "each iris sits towards the nose");
    const light = (eye) => eye.find((part) => part.glow === 1).at[0] - eye[0].at[0];
    assert.ok(light(right) < 0 && light(left) < 0, "both points of light sit on the same side");
    const single = eyeParts(partsFromEye("e 0 1 0 | .1 .1 .05 | #141824"));
    assert.equal(single[1].at[0], 0);
  });

  it("stand out from the white they sit on, and turn with the eye", () => {
    const [white, iris, light] = eyeParts(partsFromEye("e 0 1 0 | .1 .1 .05 | #141824"));
    assert.ok(iris.at[2] + iris.size[2] > white.at[2] + white.size[2]);
    assert.ok(light.at[2] + light.size[2] > iris.at[2] + iris.size[2]);
    assert.equal(white.bare, false);
    assert.equal(iris.bare, true);
    // Turned a quarter about y, the eye looks along x: its iris is beside it, not in front.
    const turned = eyeParts(partsFromEye("e 0 1 0 | .1 .1 .05 | #141824 | 0 90 0"));
    assert.ok(turned[1].at[0] > 0.02);
    assert.ok(Math.abs(turned[1].at[2]) < 1e-9);
  });

  /** The eye a part string stands for, before it is taken apart. */
  function partsFromEye(spec) {
    const { mirrored, ...eye } = parsePart(spec);
    assert.equal(mirrored, false);
    return eye;
  }
});

describe("partsFrom", () => {
  it("makes mirror images and marks what shines", () => {
    const parts = partsFrom(["S .3 1 0 | .1 .1 .1 | #ffffff!", "b 0 1 0 | .2 .2 .2 | #336699"]);
    assert.equal(parts.length, 3);
    assert.deepEqual(parts.map((part) => part.glow), [1, 1, 0]);
    assert.deepEqual(parts.map((part) => part.at[0]), [0.3, -0.3, 0]);
    assert.ok(parts.every((part) => part.bare === false && part.when === ""));
  });

  it("refuses a list with a part it cannot read", () => {
    assert.throws(() => partsFrom(["s 0 1 0 | .1 .1 .1 | #ffffff", "nonsense"]), RangeError);
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
      glow: 0,
    });
    const lamp = parsePart("s 0 .55 0 | .1 .1 .1 | #ff8000!");
    assert.equal(lamp.glow, 1);
    assert.deepEqual(lamp.colour, [1, 128 / 255, 0]);
    assert.equal(parsePart("E .2 1 .4 | .1 .1 .05 | #141824").kind, "eye");
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
      "s 0 0 0 | 1 1 1 | #000000!!",
      "s 0 0 0 | 1 1 1 | !#000000",
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
