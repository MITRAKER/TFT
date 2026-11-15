import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { CHAMPIONS, COMPONENTS, ICONS, TRAITS, VIEW, parseShape, shapesOf } from "../../src/tft/web/art.js";

const TABLES = { CHAMPIONS, TRAITS, COMPONENTS, ICONS };
const TONES = ["ink", "acc", "hole", "line", "aline", "wide", "thin", "cut"];
const PAIR = /^-?\d+(\.\d+)?,-?\d+(\.\d+)?$/;

function checkShape(label, shape) {
  assert.ok(TONES.includes(shape.tone), `${label}: tone ${shape.tone}`);
  if (shape.tag === "path") {
    assert.match(shape.attrs.d, /^M[\d\s.,A-Za-z-]+$/, `${label}: path`);
    return;
  }
  if (shape.tag === "polygon") {
    const pairs = shape.attrs.points.split(" ");
    assert.ok(pairs.length >= 3 && pairs.every((pair) => PAIR.test(pair)), `${label}: polygon`);
    return;
  }
  const values = Object.values(shape.attrs);
  assert.ok(values.length >= 3, `${label}: ${shape.tag} needs its numbers`);
  assert.ok(values.every((value) => value >= -VIEW && value <= 2 * VIEW), `${label}: off the grid`);
}

describe("the art tables", () => {
  it("hold a picture for every champion, trait and component", () => {
    assert.equal(Object.keys(CHAMPIONS).length, 25);
    assert.equal(Object.keys(TRAITS).length, 14);
    assert.equal(Object.keys(COMPONENTS).length, 8);
    for (const name of ["coin", "heart", "fight", "market", "carousel", "augment", "reroll", "xp", "flame"]) {
      assert.ok(name in ICONS, `missing icon ${name}`);
    }
  });

  it("hold only shapes that can be drawn", () => {
    for (const [title, table] of Object.entries(TABLES)) {
      for (const name of Object.keys(table)) {
        const shapes = shapesOf(table, name);
        assert.ok(shapes.length > 0, `${title}.${name} is empty`);
        shapes.forEach((shape) => checkShape(`${title}.${name}`, shape));
      }
    }
  });
});

describe("parseShape", () => {
  it("reads every kind of shape", () => {
    assert.deepEqual(parseShape("c 24 20 8"), { tag: "circle", tone: "ink", attrs: { cx: 24, cy: 20, r: 8 } });
    assert.deepEqual(parseShape("e.a 24 26 9 10"), {
      tag: "ellipse",
      tone: "acc",
      attrs: { cx: 24, cy: 26, rx: 9, ry: 10 },
    });
    assert.deepEqual(parseShape("r.h 4 5 6 7"), {
      tag: "rect",
      tone: "hole",
      attrs: { x: 4, y: 5, width: 6, height: 7 },
    });
    assert.deepEqual(parseShape("r 4 5 6 7 2").attrs.rx, 2);
    assert.deepEqual(parseShape("l.s 1 2 3 4"), {
      tag: "line",
      tone: "line",
      attrs: { x1: 1, y1: 2, x2: 3, y2: 4 },
    });
    assert.deepEqual(parseShape("g.t 1,2 3,4 5,6"), {
      tag: "polygon",
      tone: "aline",
      attrs: { points: "1,2 3,4 5,6" },
    });
    assert.deepEqual(parseShape("  p.w M1 2L3 4  "), { tag: "path", tone: "wide", attrs: { d: "M1 2L3 4" } });
    assert.equal(parseShape("l.n 1 2 3 4").tone, "thin");
    assert.equal(parseShape("p.k M1 2").tone, "cut");
  });

  it("refuses what it cannot read", () => {
    for (const bad of ["", "x 1 2 3", "c.z 1 2 3", "c", "c 1 2 3 4", "c 1 two 3", "r 1 2 3 4 5 6"]) {
      assert.throws(() => parseShape(bad), RangeError, bad);
    }
  });

  it("knows which names have a picture", () => {
    assert.equal(shapesOf(CHAMPIONS, "Nobody"), null);
    assert.equal(shapesOf(CHAMPIONS, "toString"), null);
    assert.equal(shapesOf(ICONS, "coin").length, ICONS.coin.length);
  });
});
