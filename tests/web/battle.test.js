import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { sequence } from "../../src/tft/web/arena.js";
import {
  BOARD_GAP,
  COLUMN,
  ROW,
  SHIFT,
  STYLES,
  fatesOf,
  fieldOf,
  fightersOf,
  homeOf,
  lengthOf,
  placeAt,
  planBattle,
  resultOf,
} from "../../src/tft/web/battle.js";

const BOARD = { rows: 4, cols: 7 };
const CLOSE = 1e-9;
const ROLES = Object.keys(STYLES);

const line = (champion, role, cell, size, score) => ({ champion, role, cell, size, score });

/** A side of `count` units on cells of their own, from a generator of repeatable numbers. */
function sideOf(next, count) {
  const taken = new Set();
  const lines = [];
  while (lines.length < count) {
    const cell = [Math.floor(next() * BOARD.rows), Math.floor(next() * BOARD.cols)];
    if (!taken.has(String(cell))) {
      taken.add(String(cell));
      const size = 1 + Math.floor(next() * 4);
      const role = ROLES[Math.floor(next() * ROLES.length)];
      lines.push(line(`unit ${lines.length}`, role, cell, size, size * next() * 2));
    }
  }
  return lines;
}

const sideWon = (outcome) => ({ won: "mine", lost: "theirs" })[outcome] || "";

describe("the ground of a fight", () => {
  it("puts my front row next to the other board's front row", () => {
    const mine = homeOf("mine", [0, 3], BOARD);
    const theirs = homeOf("theirs", [0, 3], BOARD);
    assert.ok(Math.abs(mine.y - theirs.y - BOARD_GAP) < CLOSE);
    assert.ok(homeOf("mine", [3, 3], BOARD).y > mine.y, "my back row is further down");
    assert.ok(homeOf("theirs", [3, 3], BOARD).y < theirs.y, "their back row is further up");
  });

  it("turns the other board around and shifts every second row", () => {
    assert.deepEqual(homeOf("theirs", [3, 6], BOARD), { x: 0, y: 0 });
    assert.ok(Math.abs(homeOf("theirs", [0, 0], BOARD).x - (6 * COLUMN + SHIFT)) < CLOSE);
    assert.ok(Math.abs(homeOf("mine", [1, 0], BOARD).x - SHIFT) < CLOSE);
    assert.equal(homeOf("mine", [2, 0], BOARD).x, 0);
    assert.ok(Math.abs(homeOf("mine", [1, 2], BOARD).y - homeOf("mine", [0, 2], BOARD).y - ROW) < CLOSE);
  });

  it("holds every cell of both boards with room to spare", () => {
    const field = fieldOf(BOARD);
    for (const side of ["mine", "theirs"]) {
      for (let row = 0; row < BOARD.rows; row += 1) {
        for (let col = 0; col < BOARD.cols; col += 1) {
          const home = homeOf(side, [row, col], BOARD);
          assert.ok(home.x > field.left && home.x < field.right, `${side} ${row},${col}`);
          assert.ok(home.y > field.top && home.y < field.bottom, `${side} ${row},${col}`);
        }
      }
    }
  });
});

describe("the fighters", () => {
  const summary = {
    units: [line("Barrel Bo", "Swing", [0, 2], 1.4, 2.1), line("Index Drone", "Quant", [3, 3], 1, 0)],
    opponent_units: [line("Pip Squeak", "Scalper", [1, 4], 1, 0.6), { ...line("Ghost", "Whale", null, 1, 1) }],
  };

  it("are my units and then the other board's, each with its own way of fighting", () => {
    const fighters = fightersOf(summary, BOARD, new Map([["Barrel Bo", "Roll Out"]]));
    assert.deepEqual(fighters.map((fighter) => fighter.id), ["mine-0", "mine-1", "theirs-0"]);
    const [bo, drone, pip] = fighters;
    assert.deepEqual([bo.side, bo.name, bo.health, bo.power, bo.ability], ["mine", "Barrel Bo", 1.4, 2.1, "Roll Out"]);
    assert.ok(drone.reach > bo.reach, "a Quant shoots, a Swing strikes");
    assert.ok(pip.period < bo.period, "a Scalper hits more often");
    assert.equal(drone.ability, "");
  });

  it("have some health even when the trade left nothing, and fight by hand when the class is unknown", () => {
    const [odd] = fightersOf({ units: [line("Odd", "Juggler", [0, 0], 0, -3)], opponent_units: [] }, BOARD);
    assert.ok(odd.health > 0);
    assert.equal(odd.power, 0);
    assert.equal(odd.reach, STYLES.Swing.reach);
    assert.deepEqual(fightersOf({ units: [], opponent_units: null }, BOARD), []);
  });

  it("fight in a way for every class of the game", () => {
    assert.deepEqual(Object.keys(STYLES).sort(), [
      "Arbitrageur",
      "Contrarian",
      "Hedger",
      "Momentum",
      "Quant",
      "Scalper",
      "Swing",
      "Whale",
    ]);
    for (const style of Object.values(STYLES)) {
      assert.ok(style.reach > 1 && style.period > 0.3 && style.period < 1.5);
    }
  });
});

describe("the fates", () => {
  const mine = [line("a", "Swing", [0, 1], 2, 3), line("b", "Quant", [3, 1], 2, 1), line("c", "Whale", [0, 4], 2, 0)];
  const theirs = [line("x", "Swing", [0, 2], 2, 1), line("y", "Hedger", [2, 2], 2, 2)];
  const fighters = fightersOf({ units: mine, opponent_units: theirs }, BOARD);
  const fatesFor = (result) => fatesOf(fighters, BOARD, result, 6);

  it("bring down the whole side that lost, the last unit at the end", () => {
    const fates = fatesFor({ outcome: "won", survivors: 2, margin: 0.5 });
    const falls = ["theirs-0", "theirs-1"].map((id) => fates.get(id).falls);
    assert.ok(falls.every((time) => time > 0 && time <= 6));
    assert.equal(Math.max(...falls), 6);
    assert.ok(Math.min(...falls) >= 6 * 0.3);
  });

  it("keep as many of the winner as survived, the ones with the best trades", () => {
    const fates = fatesFor({ outcome: "won", survivors: 2, margin: 0.5 });
    assert.equal(fates.get("mine-0").falls, null);
    assert.equal(fates.get("mine-1").falls, null);
    assert.ok(fates.get("mine-2").falls < 6, "the unit whose trade left nothing falls before the end");
    assert.ok(Math.abs(fates.get("mine-0").left - 0.6) < CLOSE);
    assert.equal(fates.get("mine-2").left, 0);
  });

  it("keep at least one and at most all of the winner", () => {
    const standing = (survivors) =>
      [...fatesFor({ outcome: "lost", survivors, margin: 1 })].filter(([id, fate]) => id.startsWith("theirs") && !fate.falls).length;
    assert.equal(standing(0), 1);
    assert.equal(standing(2), 2);
    assert.equal(standing(9), 2);
    assert.equal(standing(undefined), 1);
  });

  it("leave a narrow winner nearly spent and a clear one nearly whole", () => {
    const left = (margin) => fatesFor({ outcome: "won", survivors: 1, margin }).get("mine-0").left;
    assert.ok(left(0) < 0.25 && left(0) > 0.1);
    assert.equal(left(1), 1);
    assert.ok(left(0.5) > left(0.1));
  });

  it("bring down both sides in a draw, the last two at the same moment", () => {
    const fates = fatesFor({ outcome: "draw", survivors: 1, margin: 0 });
    assert.ok([...fates.values()].every((fate) => fate.falls !== null && fate.left === 0));
    const last = (side) => Math.max(...fighters.filter((f) => f.side === side).map((f) => fates.get(f.id).falls));
    assert.equal(last("mine"), 6);
    assert.equal(last("theirs"), 6);
  });

  it("send the front and the weak first", () => {
    const fates = fatesFor({ outcome: "lost", survivors: 1, margin: 0.5 });
    // c stands in front with a trade that left nothing; b stands at the back.
    assert.ok(fates.get("mine-2").falls < fates.get("mine-0").falls);
    assert.ok(fates.get("mine-0").falls < fates.get("mine-1").falls);
  });
});

describe("a battle plan", () => {
  /** Check everything a plan promises; returns the plan. */
  function checkPlan(mine, theirs, result) {
    const fighters = fightersOf({ units: mine, opponent_units: theirs }, BOARD);
    const plan = planBattle(fighters, BOARD, result);
    const sides = new Map(plan.fighters.map((fighter) => [fighter.id, fighter.side]));
    const fell = new Map(plan.events.filter((event) => event.kind === "fall").map((event) => [event.unit, event.t]));
    const winner = sideWon(result.outcome);
    for (const fighter of plan.fighters) {
      assert.equal(fell.has(fighter.id), fighter.falls !== null, `${fighter.id}: the script and the fate agree`);
      assert.ok(fighter.side === winner || fell.has(fighter.id), `${fighter.id} lost and still stands`);
      assert.ok(fighter.falls === null || Math.abs(fell.get(fighter.id) - fighter.falls) < CLOSE);
    }
    const health = new Map(plan.fighters.map((fighter) => [fighter.id, fighter.health]));
    let before = 0;
    for (const event of plan.events) {
      assert.ok(event.t >= before - CLOSE, "what happens is in order");
      before = event.t;
      checkEvent(event, { sides, fell, health });
    }
    checkTracks(plan);
    assert.ok(plan.length >= 4 && plan.length <= 7.5 && plan.total > plan.length);
    return plan;
  }

  function checkEvent(event, { sides, fell, health }) {
    if (event.kind === "attack") {
      assert.notEqual(sides.get(event.from), sides.get(event.to), "nobody hits a friend");
      assert.ok(!fell.has(event.from) || event.t <= fell.get(event.from) + CLOSE, "the fallen do not hit");
      assert.ok(!fell.has(event.to) || event.t <= fell.get(event.to) + CLOSE, "nobody starts a blow at the fallen");
      assert.ok(event.lands >= event.t - CLOSE && event.lands - event.t < 0.5);
      assert.ok(["strike", "shot"].includes(event.style));
    } else if (event.kind === "hit") {
      assert.ok(event.health >= -CLOSE && event.health <= health.get(event.to) + CLOSE, "health only goes down");
      assert.ok(event.loss >= -CLOSE);
      health.set(event.to, event.health);
    } else if (event.kind === "fall") {
      assert.ok(health.get(event.unit) < CLOSE, "a unit falls when its health is gone");
    } else {
      assert.ok(["cast", "cheer"].includes(event.kind), event.kind);
    }
  }

  function checkTracks(plan) {
    for (const fighter of plan.fighters) {
      const track = plan.tracks.get(fighter.id);
      assert.deepEqual(track[0], { t: 0, x: fighter.home.x, y: fighter.home.y });
      for (let index = 1; index < track.length; index += 1) {
        const [from, to] = [track[index - 1], track[index]];
        assert.ok(to.x >= plan.field.left - CLOSE && to.x <= plan.field.right + CLOSE);
        assert.ok(to.y >= plan.field.top - CLOSE && to.y <= plan.field.bottom + CLOSE);
        const speed = Math.hypot(to.x - from.x, to.y - from.y) / (to.t - from.t);
        assert.ok(speed < 5.5, `${fighter.id} moves ${speed.toFixed(1)} cells a second`);
      }
      assert.ok(fighter.falls === null || track[track.length - 1].t <= fighter.falls + CLOSE);
    }
  }

  it("ends as the engine decided, whatever the boards", () => {
    const next = sequence(2026);
    for (let run = 0; run < 250; run += 1) {
      const mine = sideOf(next, Math.floor(next() * 10));
      const theirs = sideOf(next, Math.floor(next() * 10));
      const outcome = ["won", "lost", "draw"][Math.floor(next() * 3)];
      const winners = { won: mine, lost: theirs, draw: [] }[outcome];
      const survivors = 1 + Math.floor(next() * Math.max(winners.length, 1));
      const plan = checkPlan(mine, theirs, { outcome, survivors, margin: next() });
      const standing = plan.fighters.filter((fighter) => fighter.falls === null);
      assert.equal(standing.length, Math.min(survivors, winners.length), `run ${run}: ${outcome}`);
      assert.ok(standing.every((fighter) => fighter.side === sideWon(outcome)));
    }
  });

  it("is the same every time for the same boards and result", () => {
    const next = sequence(7);
    const mine = sideOf(next, 5);
    const theirs = sideOf(next, 6);
    const result = { outcome: "won", survivors: 2, margin: 0.3 };
    const plan = () => planBattle(fightersOf({ units: mine, opponent_units: theirs }, BOARD), BOARD, result);
    const [first, second] = [plan(), plan()];
    assert.deepEqual(first.events, second.events);
    assert.deepEqual([...first.tracks], [...second.tracks]);
  });

  it("lets every unit use its signature move once while it stands, and the winners cheer", () => {
    const next = sequence(11);
    const plan = checkPlan(sideOf(next, 4), sideOf(next, 4), { outcome: "lost", survivors: 2, margin: 0.4 });
    const casts = plan.events.filter((event) => event.kind === "cast");
    assert.equal(new Set(casts.map((event) => event.unit)).size, casts.length, "nobody casts twice");
    assert.ok(casts.length >= 6, `only ${casts.length} of 8 units cast`);
    const cheer = plan.events[plan.events.length - 1];
    assert.deepEqual([cheer.kind, cheer.side], ["cheer", "theirs"]);
    assert.ok(cheer.t > plan.length && cheer.t < plan.total);
  });

  it("makes the two sides meet: units leave their cells and blows are struck by hand and thrown", () => {
    const mine = [line("a", "Swing", [0, 3], 2, 3), line("b", "Quant", [3, 3], 2, 2)];
    const theirs = [line("x", "Whale", [0, 3], 2, 1), line("y", "Momentum", [3, 3], 2, 1)];
    const plan = checkPlan(mine, theirs, { outcome: "won", survivors: 2, margin: 0.6 });
    const styles = new Set(plan.events.filter((event) => event.kind === "attack").map((event) => event.style));
    assert.deepEqual([...styles].sort(), ["shot", "strike"]);
    const walked = (id) => {
      const track = plan.tracks.get(id);
      return Math.hypot(track[track.length - 1].x - track[0].x, track[track.length - 1].y - track[0].y);
    };
    assert.ok(walked("mine-0") > 0.3, "the one who fights by hand walks up to the enemy");
    const hits = plan.events.filter((event) => event.kind === "hit");
    assert.ok(hits.length >= 8);
    assert.ok(hits.some((hit) => hit.heavy));
  });

  it("is short and quiet when one side has nobody", () => {
    const plan = checkPlan([line("a", "Swing", [0, 3], 2, 3)], [], { outcome: "won", survivors: 1, margin: 1 });
    assert.deepEqual(plan.events.map((event) => event.kind), ["cheer"]);
    assert.equal(plan.fighters[0].falls, null);
    const empty = planBattle([], BOARD, { outcome: "draw", survivors: 1, margin: 0 });
    assert.deepEqual([empty.events, empty.fighters], [[], []]);
  });
});

describe("placeAt", () => {
  const track = [
    { t: 0, x: 0, y: 0 },
    { t: 1, x: 2, y: 0 },
    { t: 2, x: 2, y: 4 },
  ];

  it("is between the points of a track, and stays at its end", () => {
    assert.deepEqual(placeAt(track, 0), { x: 0, y: 0 });
    assert.deepEqual(placeAt(track, 0.5), { x: 1, y: 0 });
    assert.deepEqual(placeAt(track, 1.5), { x: 2, y: 2 });
    assert.deepEqual(placeAt(track, 2), { x: 2, y: 4 });
    assert.deepEqual(placeAt(track, 99), { x: 2, y: 4 });
    assert.deepEqual(placeAt([{ t: 0, x: 3, y: 1 }], 5), { x: 3, y: 1 });
  });
});

describe("resultOf", () => {
  const fights = [
    { home: "ana", away: "bo", winner: "ana", loser: "bo", draw: false, survivors: 4 },
    { home: "di", away: "you", winner: "you", loser: "di", draw: false, survivors: 3 },
  ];

  it("takes the survivors from the seat's own fight and the margin from the scores", () => {
    const result = resultOf({ outcome: "won", score: 8, opponent_score: 6 }, fights, "you");
    assert.deepEqual(result, { outcome: "won", survivors: 3, margin: 0.25 });
    const lost = resultOf({ outcome: "lost", score: 3, opponent_score: 12 }, fights, "you");
    assert.equal(lost.margin, 0.75);
  });

  it("keeps one unit when the fight is not listed or was a draw", () => {
    assert.equal(resultOf({ outcome: "won", score: 2, opponent_score: 1 }, [], "you").survivors, 1);
    assert.equal(resultOf({ outcome: "won", score: 2, opponent_score: 1 }, undefined, "you").survivors, 1);
    const draw = [{ home: "you", away: "di", draw: true, survivors: 0 }];
    assert.deepEqual(resultOf({ outcome: "draw", score: 0, opponent_score: 0 }, draw, "you"), {
      outcome: "draw",
      survivors: 1,
      margin: 0,
    });
  });
});

describe("the length of a fight", () => {
  it("grows with the number of units, within limits", () => {
    assert.equal(lengthOf(0), 4);
    assert.equal(lengthOf(2), 4);
    assert.ok(lengthOf(10) > lengthOf(6));
    assert.equal(lengthOf(40), 7.5);
  });
});
