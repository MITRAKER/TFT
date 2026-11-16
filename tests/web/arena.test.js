import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { sequence, towers } from "../../src/tft/web/arena.js";

describe("the sequence", () => {
  it("gives the same numbers for the same seed, all from 0 up to 1", () => {
    const first = sequence(7);
    const second = sequence(7);
    const values = Array.from({ length: 200 }, () => first());
    assert.deepEqual(values, Array.from({ length: 200 }, () => second()));
    assert.ok(values.every((value) => value >= 0 && value < 1));
    assert.ok(new Set(values).size > 190, "the numbers do not repeat soon");
  });

  it("gives other numbers for another seed", () => {
    assert.notEqual(sequence(1)(), sequence(2)());
  });
});

describe("the skyline", () => {
  const row = { count: 26, seed: 29, low: 26, high: 88 };

  it("is the same on every visit", () => {
    assert.deepEqual(towers(row), towers(row));
    assert.notDeepEqual(towers(row), towers({ ...row, seed: 30 }));
  });

  it("fills the width with towers that do not touch", () => {
    const skyline = towers(row);
    assert.equal(skyline.length, row.count);
    skyline.forEach((tower, index) => {
      assert.ok(tower.x >= 0 && tower.x + tower.width <= 1000, `tower ${index} leaves the picture`);
      assert.ok(tower.width > 0);
      if (index > 0) {
        const before = skyline[index - 1];
        assert.ok(tower.x >= before.x + before.width, `tower ${index} touches the one before`);
      }
    });
  });

  it("keeps every tower and its wick inside the picture", () => {
    for (const tower of towers(row)) {
      assert.ok(tower.height >= row.low && tower.height <= row.high);
      assert.ok(tower.wick > 0 && tower.height + tower.wick <= 100);
    }
  });

  it("mixes candles that closed up with candles that closed down", () => {
    const up = towers(row).filter((tower) => tower.up).length;
    assert.ok(up > 0 && up < row.count);
  });
});
