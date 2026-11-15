import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  bannerOf,
  cellEffect,
  factorOf,
  fightText,
  headline,
  healthTone,
  hexRows,
  initials,
  interestPips,
  isCovered,
  mirrorCell,
  nextStep,
  oddsText,
  ordinal,
  percent,
  resultLabel,
  resultTone,
  roundKind,
  signed,
  sparkline,
  standings,
  streakText,
  traitSteps,
  unitAt,
} from "../../src/tft/web/logic.js";

const BOARD = { rows: 4, cols: 7, row_size: [90, 95, 100, 110], row_shield: [40, 20, 0, 0], cover: 25, exposed: 50 };
const UNITS = [
  { index: 0, name: "Coupon Clerk", cell: [0, 3] },
  { index: 1, name: "Breakout Bull", cell: [3, 3] },
  { index: 2, name: "Pip Squeak", cell: [3, 0] },
  { index: 3, name: "Index Drone", cell: null },
];

describe("formatting", () => {
  it("clamps percentages", () => {
    assert.equal(percent(50, 100), 50);
    assert.equal(percent(150, 100), 100);
    assert.equal(percent(-5, 100), 0);
    assert.equal(percent(1, 3), 33);
    assert.equal(percent(5, 0), 0);
    assert.equal(percent(5, undefined), 0);
  });

  it("counts interest pips", () => {
    assert.deepEqual([0, 9, 10, 49, 50, 500, -3].map(interestPips), [0, 0, 1, 4, 5, 5, 0]);
  });

  it("signs percentages", () => {
    assert.equal(signed(1.24), "+1.2%");
    assert.equal(signed(-0.44), "-0.4%");
    assert.equal(signed(0), "0.0%");
    assert.equal(signed(-0.04), "0.0%");
    assert.equal(signed(0.04), "0.0%");
    assert.equal(signed(3.14159, 2), "+3.14%");
  });

  it("names streaks, initials and places", () => {
    assert.deepEqual([3, -2, 0].map(streakText), ["W3", "L2", "-"]);
    assert.equal(initials("Breakout Bull"), "BB");
    assert.equal(initials("Whale"), "WH");
    assert.equal(initials("  mean   reverend extra "), "MR");
    assert.equal(initials(""), "");
    assert.deepEqual([1, 2, 3, 4, 11, 12, 13, 21, 22, 23, 101, 111].map(ordinal), [
      "1st",
      "2nd",
      "3rd",
      "4th",
      "11th",
      "12th",
      "13th",
      "21st",
      "22nd",
      "23rd",
      "101st",
      "111th",
    ]);
  });

  it("lists shop odds by cost", () => {
    assert.equal(oddsText([45, 33, 20, 2, 0]), "1: 45%  2: 33%  3: 20%  4: 2%  5: 0%");
  });

  it("writes headlines and fights", () => {
    assert.equal(headline({ outcome: "none" }), "No fight this round");
    assert.equal(headline({ outcome: "won", opponent: "ana" }), "You won against ana");
    assert.equal(headline({ outcome: "draw", opponent: "bo" }), "Draw against bo");
    assert.equal(headline({ outcome: "lost", opponent: "cy", damage: 6 }), "You lost against cy (-6 health)");
    assert.equal(headline({ outcome: "lost", opponent: null, damage: 0 }), "You lost");
    assert.equal(fightText({ draw: true, home: "ana", away: "bo" }), "ana and bo drew");
    assert.equal(
      fightText({ draw: false, winner: "ana", loser: "bo", survivors: 2 }),
      "ana beat bo with 2 unit(s) left",
    );
  });
});

describe("the board", () => {
  it("lays out rows with every other row shifted", () => {
    const rows = hexRows(4, 7);
    assert.equal(rows.length, 4);
    assert.deepEqual(rows.map((row) => row.shifted), [false, true, false, true]);
    assert.equal(rows[2].cells.length, 7);
    assert.deepEqual(rows[2].cells[5], { row: 2, col: 5 });
    assert.deepEqual(hexRows(0, 7), []);
  });

  it("finds units and cover", () => {
    assert.equal(unitAt(UNITS, 3, 3).name, "Breakout Bull");
    assert.equal(unitAt(UNITS, 1, 1), null);
    assert.equal(isCovered(UNITS, 3, 3), true);
    assert.equal(isCovered(UNITS, 3, 0), false);
    assert.equal(isCovered(UNITS, 0, 3), false);
  });

  it("describes what a cell does", () => {
    assert.equal(cellEffect(BOARD, UNITS, 0, 3), "size 90%, forgives 40% of drawdowns");
    assert.equal(cellEffect(BOARD, UNITS, 1, 1), "size 95%, forgives 20% of drawdowns");
    assert.equal(cellEffect(BOARD, UNITS, 3, 3), "size 110%, covered: forgives 25% of drawdowns");
    assert.equal(cellEffect(BOARD, UNITS, 3, 0), "size 110%, exposed: drawdowns weigh 50% more");
    assert.equal(cellEffect(BOARD, UNITS, 2, 6), "size 100%, exposed: drawdowns weigh 50% more");
  });

  it("turns the opposing board around", () => {
    assert.deepEqual(mirrorCell(BOARD, 0, 0), [3, 6]);
    assert.deepEqual(mirrorCell(BOARD, 3, 6), [0, 0]);
    assert.deepEqual(mirrorCell(BOARD, 1, 3), [2, 3]);
  });
});

describe("the fight scene", () => {
  const line = (size, score) => ({ size, score });

  it("measures what a trade did to a unit's size", () => {
    assert.equal(factorOf(line(2, 3)), 1.5);
    assert.equal(factorOf(line(2, 0)), 0);
    assert.equal(factorOf(line(0, 0)), 0);
  });

  it("names the result of a unit", () => {
    assert.deepEqual(
      [line(2, 2.76), line(2, 1.48), line(2, 2.004), line(2, 0), line(0, 0)].map(resultTone),
      ["up", "down", "flat", "out", "flat"],
    );
    assert.deepEqual(
      [line(2, 2.76), line(2, 1.48), line(2, 2.004), line(2, 0), line(1, 2)].map(resultLabel),
      ["+38%", "-26%", "0%", "wiped out", "+100%"],
    );
  });

  it("writes the banner", () => {
    const base = { opponent: "ana", score: 12.34, opponent_score: 9.1, damage: 7 };
    assert.deepEqual(bannerOf({ ...base, outcome: "won" }), {
      word: "Victory",
      tone: "won",
      scores: "12.3 to 9.1",
      cost: "",
    });
    assert.deepEqual(bannerOf({ ...base, outcome: "lost" }), {
      word: "Defeat",
      tone: "lost",
      scores: "12.3 to 9.1",
      cost: "-7 health",
    });
    assert.equal(bannerOf({ ...base, outcome: "lost", damage: 0 }).cost, "");
    assert.equal(bannerOf({ ...base, outcome: "draw" }).word, "Draw");
    assert.deepEqual(bannerOf({ ...base, outcome: "none" }), {
      word: "No fight",
      tone: "none",
      scores: "",
      cost: "",
    });
  });
});

describe("the table", () => {
  it("orders the scoreboard", () => {
    const you = { name: "you", health: 70, alive: true };
    const others = [
      { name: "bo", health: 90, alive: true },
      { name: "ana", health: 90, alive: true },
      { name: "cy", health: 0, alive: false },
    ];
    const rows = standings(you, others);
    assert.deepEqual(rows.map((row) => row.name), ["ana", "bo", "you", "cy"]);
    assert.deepEqual(rows.map((row) => row.me), [false, false, true, false]);
    assert.deepEqual(standings(null, others).map((row) => row.name), ["ana", "bo", "cy"]);
    assert.equal(others[0].me, undefined);
  });

  it("names the kind of a round", () => {
    assert.equal(roundKind({ pve: false, carousel: false }), "fight");
    assert.equal(roundKind({ pve: true, carousel: false }), "market");
    assert.equal(roundKind({ pve: false, carousel: true }), "carousel");
    assert.equal(roundKind({ pve: true, carousel: true }), "carousel");
  });

  it("marks the breakpoints a trait has reached", () => {
    assert.deepEqual(traitSteps({ breakpoints: [2, 4, 6], count: 4 }), [
      { needed: 2, reached: true },
      { needed: 4, reached: true },
      { needed: 6, reached: false },
    ]);
    assert.deepEqual(traitSteps({ breakpoints: [1], count: 0 }), [{ needed: 1, reached: false }]);
  });

  it("tones a health bar", () => {
    assert.deepEqual(
      [100, 61, 60, 31, 30, 0].map((health) => healthTone(health, 100)),
      ["high", "high", "mid", "mid", "low", "low"],
    );
    assert.equal(healthTone(5, 0), "low");
  });
});

describe("sparkline", () => {
  it("fits closes into the box", () => {
    const { points, coords } = sparkline([100, 110, 90], 120, 32, 2);
    assert.equal(coords.length, 3);
    assert.deepEqual(coords[0], [2, 16]);
    assert.deepEqual(coords[1], [60, 2]);
    assert.deepEqual(coords[2], [118, 30]);
    assert.equal(points, "2,16 60,2 118,30");
  });

  it("handles flat, single and empty series", () => {
    assert.deepEqual(sparkline([5, 5], 100, 20, 0).coords, [
      [0, 20],
      [100, 20],
    ]);
    assert.deepEqual(sparkline([7], 100, 20).coords, [[3, 17]]);
    assert.deepEqual(sparkline([], 100, 20), { points: "", coords: [] });
    assert.deepEqual(sparkline(undefined, 100, 20), { points: "", coords: [] });
  });
});

describe("nextStep", () => {
  const boardUnit = { type: "unit", index: 1, where: "board", cell: [3, 3] };
  const benchUnit = { type: "unit", index: 5, where: "bench", cell: null };
  const item = { type: "item", index: 0 };
  const component = { type: "component", index: 1 };
  const act = (kind, args) => ({ kind: "action", action: { kind, args } });
  const cell = (row, col, unit = null) => ({ type: "cell", row, col, unit });
  const bench = (unit = null) => ({ type: "bench", unit });

  it("selects what is clicked when nothing is selected", () => {
    assert.deepEqual(nextStep(null, cell(3, 3, 1)), { kind: "select", selection: boardUnit });
    assert.deepEqual(nextStep(null, bench(5)), { kind: "select", selection: benchUnit });
    assert.deepEqual(nextStep(null, { type: "item", index: 0 }), { kind: "select", selection: item });
    assert.deepEqual(nextStep(null, { type: "component", index: 1 }), {
      kind: "select",
      selection: component,
    });
    assert.deepEqual(nextStep(null, cell(0, 0)), { kind: "none" });
    assert.deepEqual(nextStep(null, bench()), { kind: "none" });
  });

  it("fields a bench unit onto a cell, even an occupied one", () => {
    assert.deepEqual(nextStep(benchUnit, cell(2, 4)), act("field", [5, 2, 4]));
    assert.deepEqual(nextStep(benchUnit, cell(3, 3, 1)), act("field", [5, 3, 3]));
    assert.deepEqual(nextStep(benchUnit, bench(5)), { kind: "clear" });
    assert.deepEqual(nextStep(benchUnit, bench()), { kind: "clear" });
    assert.equal(nextStep(benchUnit, bench(6)).selection.index, 6);
  });

  it("moves, swaps and benches a board unit", () => {
    assert.deepEqual(nextStep(boardUnit, cell(0, 0)), act("move", [1, 0, 0]));
    assert.deepEqual(nextStep(boardUnit, cell(0, 3, 0)), act("move", [1, 0, 3]));
    assert.deepEqual(nextStep(boardUnit, cell(3, 3, 1)), { kind: "clear" });
    assert.deepEqual(nextStep(boardUnit, bench()), act("bench", [1]));
    assert.deepEqual(nextStep(boardUnit, bench(5)), act("field", [5, 3, 3]));
    assert.deepEqual(nextStep(boardUnit, { type: "item", index: 2 }), {
      kind: "select",
      selection: { type: "item", index: 2 },
    });
  });

  it("equips an item on a unit", () => {
    assert.deepEqual(nextStep(item, cell(3, 3, 1)), act("equip", [1, 0]));
    assert.deepEqual(nextStep(item, bench(5)), act("equip", [5, 0]));
    assert.deepEqual(nextStep(item, cell(0, 0)), { kind: "clear" });
    assert.deepEqual(nextStep(item, { type: "item", index: 0 }), { kind: "clear" });
    assert.equal(nextStep(item, { type: "item", index: 1 }).selection.index, 1);
    assert.equal(nextStep(item, { type: "component", index: 0 }).selection.type, "component");
  });

  it("crafts two components", () => {
    assert.deepEqual(nextStep(component, { type: "component", index: 0 }), act("craft", [1, 0]));
    assert.deepEqual(nextStep(component, { type: "component", index: 1 }), { kind: "clear" });
    assert.deepEqual(nextStep(component, cell(0, 0)), { kind: "clear" });
    assert.equal(nextStep(component, cell(3, 3, 1)).selection.type, "unit");
    assert.equal(nextStep(component, { type: "item", index: 0 }).selection.type, "item");
  });
});
