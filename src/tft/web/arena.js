/**
 * The arena: what stands around the boards. A night skyline of candlestick towers, beams of
 * light, drifting sparks, a raised platform, the bull and the bear, pylons with turning coins
 * and the opening bell. All of it is decoration: nothing here takes a click or says anything
 * about the match, and assistive technology is told to skip it.
 */
import { el, svg } from "./dom.js";

const SKY_WIDTH = 1000;
const SKY_HEIGHT = 100;
const ROWS = [
  { layer: "far", count: 54, seed: 11, low: 18, high: 62 },
  { layer: "near", count: 26, seed: 29, low: 26, high: 88 },
];
const FLOOR_BAND = 7;
const BEAMS = 4;
const MOTES = 16;
const PYLONS = ["far-left", "far-right", "near-left", "near-right"];

/**
 * A generator of repeatable numbers from 0 up to 1, so that the arena looks the same on every
 * visit: the classic linear congruential sequence.
 */
export function sequence(seed) {
  let state = seed >>> 0;
  return () => {
    state = (Math.imul(state, 1664525) + 1013904223) >>> 0;
    return state / 4294967296;
  };
}

/**
 * One row of the skyline as candles in a picture `SKY_WIDTH` wide and `SKY_HEIGHT` high:
 * `{ x, width, height, wick, up }`. The towers fill the width without touching; `up` says
 * whether the candle closed above its open, which colours it.
 */
export function towers({ count, seed, low, high }) {
  const next = sequence(seed);
  const pitch = SKY_WIDTH / count;
  const row = [];
  for (let index = 0; index < count; index += 1) {
    const width = pitch * (0.46 + 0.3 * next());
    const height = low + (high - low) * next() ** 1.6;
    row.push({
      x: index * pitch + (pitch - width) * next(),
      width,
      height,
      wick: 3 + 9 * next(),
      up: next() < 0.58,
    });
  }
  return row;
}

function towerShapes(tower, banded) {
  const top = SKY_HEIGHT - tower.height;
  const tone = tower.up ? "up" : "down";
  const middle = tower.x + tower.width / 2;
  const shapes = [
    svg("rect", { class: `wick ${tone}`, x: middle - 0.6, y: top - tower.wick, width: 1.2, height: tower.wick }),
    svg("rect", { class: `tower ${tone}`, x: tower.x, y: top, width: tower.width, height: tower.height }),
    svg("rect", { class: `cap ${tone}`, x: tower.x, y: top, width: tower.width, height: 1.6 }),
  ];
  for (let level = top + FLOOR_BAND; banded && level < SKY_HEIGHT - 2; level += FLOOR_BAND) {
    shapes.push(svg("rect", { class: "storey", x: tower.x, y: level, width: tower.width, height: 1.1 }));
  }
  return shapes;
}

function skyline(row) {
  const picture = svg("svg", {
    class: `skyline ${row.layer}`,
    viewBox: `0 0 ${SKY_WIDTH} ${SKY_HEIGHT}`,
    preserveAspectRatio: "none",
  });
  picture.append(...towers(row).flatMap((tower) => towerShapes(tower, row.layer === "near")));
  return picture;
}

/** A span whose custom properties place and time it; the style sheet does the rest. */
function placed(name, properties) {
  const node = el("span", { class: name });
  for (const [key, value] of Object.entries(properties)) {
    node.style.setProperty(`--${key}`, value);
  }
  return node;
}

function backdrop() {
  const next = sequence(71);
  const beams = Array.from({ length: BEAMS }, (_, index) =>
    placed("beam", {
      at: `${(12 + (76 * index) / (BEAMS - 1)).toFixed(1)}%`,
      lean: `${(-16 + (32 * index) / (BEAMS - 1)).toFixed(1)}deg`,
      time: `${(9 + 5 * next()).toFixed(1)}s`,
    }),
  );
  return el("div", { class: "backdrop", "aria-hidden": "true" }, [
    el("span", { class: "night" }),
    ...ROWS.map(skyline),
    el("span", { class: "haze" }),
    ...beams,
    el("span", { class: "prop bell" }),
  ]);
}

function stage() {
  const pylons = PYLONS.map((corner) =>
    el("span", { class: `prop pylon ${corner}` }, [el("span", { class: "prop coin" })]),
  );
  return [
    el("div", { class: "ground", "aria-hidden": "true" }),
    el("div", { class: "slab", "aria-hidden": "true" }, [el("span", { class: "slab-front" })]),
    el("div", { class: "props", "aria-hidden": "true" }, [
      el("span", { class: "prop statue bull" }),
      el("span", { class: "prop statue bear" }),
      ...pylons,
    ]),
  ];
}

function foreground() {
  const next = sequence(5);
  const motes = Array.from({ length: MOTES }, () =>
    placed("mote", {
      at: `${(100 * next()).toFixed(1)}%`,
      size: `${(2 + 3 * next()).toFixed(1)}px`,
      time: `${(9 + 10 * next()).toFixed(1)}s`,
      wait: `${(-18 * next()).toFixed(1)}s`,
      sway: `${(-30 + 60 * next()).toFixed(0)}px`,
    }),
  );
  return el("div", { class: "foreground", "aria-hidden": "true" }, motes);
}

/**
 * Build the arena around the boards of a floor: the backdrop behind them, the platform and the
 * props in their plane, and the sparks in front. Safe to call once for each floor.
 */
export function dressFloor(floor) {
  const boards = floor.querySelector(".boards");
  if (!boards || floor.querySelector(".backdrop")) {
    return;
  }
  floor.prepend(backdrop());
  boards.prepend(...stage());
  floor.append(foreground());
}
