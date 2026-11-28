/**
 * Original artwork for the client: every picture is drawn here, as flat shapes on a 48 by 48 grid.
 *
 * A picture is a list of shapes, and a shape is the string "<kind>[.<tone>] <numbers or data>":
 *
 *   c cx cy r            circle           e cx cy rx ry        ellipse
 *   r x y w h [radius]   rectangle        l x1 y1 x2 y2        line
 *   g x,y x,y ...        polygon          p <path data>        path
 *
 * Tones pick the colour through CSS: none is the ink, "a" the accent, "h" a hole in the colour
 * of the backdrop, "s" an ink stroke, "t" an accent stroke, "w" a wide ink stroke, "n" a narrow
 * ink stroke and "k" a stroke in the colour of the backdrop.
 */

export const VIEW = 48;

const TONES = {
  "": "ink",
  a: "acc",
  h: "hole",
  s: "line",
  t: "aline",
  w: "wide",
  n: "thin",
  k: "cut",
};

const NUMBERS = {
  c: ["cx", "cy", "r"],
  e: ["cx", "cy", "rx", "ry"],
  r: ["x", "y", "width", "height", "rx"],
  l: ["x1", "y1", "x2", "y2"],
};

const TAGS = { c: "circle", e: "ellipse", r: "rect", l: "line", g: "polygon", p: "path" };

/** The portrait of every champion, by name. */
export const CHAMPIONS = {
  "Pip Squeak": [
    "c 13 15 8",
    "c 35 15 8",
    "c.a 13 15 4",
    "c.a 35 15 4",
    "e 24 28 13 12",
    "c.h 19 26 1.8",
    "c.h 29 26 1.8",
    "c.a 24 33 2.2",
  ],
  "Index Drone": [
    "l.w 12 14 36 34",
    "l.w 36 14 12 34",
    "e.a 11 13 8 3",
    "e.a 37 13 8 3",
    "e.a 11 35 8 3",
    "e.a 37 35 8 3",
    "r 17 17 14 14 4",
    "c.h 24 24 3.6",
    "c.a 24 24 1.8",
  ],
  "Hodl Hamster": [
    "c 13 13 5",
    "c 35 13 5",
    "e 24 27 15 14",
    "c.a 14 31 5",
    "c.a 34 31 5",
    "c.h 19 23 1.8",
    "c.h 29 23 1.8",
    "c.h 24 28 1.5",
    "r.h 22.5 31 3 4 1",
  ],
  "Barrel Bo": [
    "r 12 7 24 34 6",
    "r.a 12 13.5 24 3.5",
    "r.a 12 31 24 3.5",
    "p.h M24 18c2.6 3.2 4 5.2 4 7a4 4 0 0 1-8 0c0-1.8 1.4-3.8 4-7z",
  ],
  "Coupon Clerk": [
    "r 6 13 36 22 4",
    "c.h 6 24 4",
    "c.h 42 24 4",
    "c.a 18 20 3",
    "c.a 30 28 3",
    "l.t 31 17 17 31",
  ],
  "Candle Reader": [
    "l.s 12 8 12 40",
    "l.s 24 4 24 36",
    "l.s 36 12 36 44",
    "r 8 16 8 16 1.5",
    "r.a 20 9 8 18 1.5",
    "r 32 20 8 16 1.5",
  ],
  "Gap Gazelle": [
    "p.s M20 20C18 12 14 8 15 2",
    "p.s M28 20C30 12 34 8 33 2",
    "g 14,20 6,15 12,26",
    "g 34,20 42,15 36,26",
    "g 24,45 14,24 18,17 30,17 34,24",
    "c.h 19 26 1.6",
    "c.h 29 26 1.6",
    "e.a 24 41 3 2.2",
  ],
  "Mean Reverend": [
    "p M3 41C13 41 15 14 24 14C33 14 35 41 45 41Z",
    "r.h 23.2 18 1.6 23",
    "e.t 24 8 8 3",
  ],
  "Spread Spider": [
    "p.s M19 22L9 15L4 20",
    "p.s M18 26L7 24L3 30",
    "p.s M18 30L8 33L5 40",
    "p.s M20 34L13 40L12 46",
    "p.s M29 22L39 15L44 20",
    "p.s M30 26L41 24L45 30",
    "p.s M30 30L40 33L43 40",
    "p.s M28 34L35 40L36 46",
    "e 24 30 7 8.5",
    "c 24 18 5",
    "g.a 24,25 27,30 24,35 21,30",
  ],
  "Gold Bug": [
    "p.s M21 9C19 5 16 4 14 5",
    "p.s M27 9C29 5 32 4 34 5",
    "l.s 14 20 6 16",
    "l.s 13 28 4 28",
    "l.s 14 36 6 41",
    "l.s 34 20 42 16",
    "l.s 35 28 44 28",
    "l.s 34 36 42 41",
    "c 24 12 5.5",
    "e 24 29 11 14",
    "r.h 23.2 17 1.6 26",
    "c.a 18.5 25 2.5",
    "c.a 29.5 25 2.5",
    "c.a 18.5 34 2.5",
    "c.a 29.5 34 2.5",
  ],
  "Stable Coin": [
    "c 24 24 18",
    "c.h 24 24 14",
    "c 24 24 12.5",
    "r.a 16.5 19 15 3.6 1.8",
    "r.a 16.5 25.4 15 3.6 1.8",
  ],
  "Yield Yeti": [
    "g 24,5 28,9 33,7 35,12 40,13 39,18 43,22 40,26 43,31 38,33 38,39 33,38 30,43 26,40 22,43 19,39 14,40 13,35 8,34 10,29 5,26 9,22 6,17 11,15 11,10 16,10 19,6 22,9",
    "e.a 24 26 9 10",
    "c.h 20 23 1.8",
    "c.h 28 23 1.8",
    "r.h 20 30 8 2.4 1.2",
  ],
  "Breakout Bull": [
    "p.w M13 17C5 15 4 8 7 4",
    "p.w M35 17C43 15 44 8 41 4",
    "p M12 15H36L33 34C31 41 17 41 15 34Z",
    "e.a 24 34 8 5.5",
    "c.h 21 34 1.5",
    "c.h 27 34 1.5",
    "c.h 18 23 1.7",
    "c.h 30 23 1.7",
  ],
  "Bear Baron": [
    "c 11 18 6",
    "c 37 18 6",
    "c 24 30 15",
    "g.a 14,12 14,4 19,8 24,2 29,8 34,4 34,12",
    "e.a 24 36 7 5",
    "e.h 24 34 2.6 1.8",
    "c.h 18 27 1.8",
    "c.h 30 27 1.8",
  ],
  "Vol Vampire": [
    "p M24 15L21 8L20 16C13 9 5 11 1 19C7 18 10 21 12 26C15 22 19 23 21 28L24 37L27 28C29 23 33 22 36 26C38 21 41 18 47 19C43 11 35 9 28 16L27 8Z",
    "c.a 21.5 20 1.5",
    "c.a 26.5 20 1.5",
    "g.a 22,24.5 23,28 24,24.5",
    "g.a 24,24.5 25,28 26,24.5",
  ],
  "Carry Caravan": [
    "r 7 22 26 9 4",
    "c 14 20 6",
    "c 26 20 6",
    "p.w M33 26L37 12",
    "r 34 7 10 6 3",
    "r 9 29 4 12 1",
    "r 27 29 4 12 1",
    "r.a 16 20 8 7 1.5",
    "c.h 40 9.5 1",
  ],
  "Miner Mole": [
    "l.w 13 43 31 15",
    "p.w M12 14C22 6 36 8 43 20",
    "g.a 33,34 39,31 44,36 41,43 34,42",
  ],
  "Crude Colossus": [
    "l.s 24 12 12 42",
    "l.s 24 12 36 42",
    "l.s 19.5 23 28.5 23",
    "l.s 16 32 32 32",
    "l.s 19.5 23 32 32",
    "l.s 28.5 23 16 32",
    "r 8 40 32 4 2",
    "p.a M24 2c2.4 3 3.6 4.8 3.6 6.4a3.6 3.6 0 0 1-7.2 0c0-1.6 1.2-3.4 3.6-6.4z",
  ],
  "Market Maker": [
    "r 22.5 10 3 30 1",
    "r 14 39 20 4 2",
    "r 6 12 36 3 1.5",
    "l.n 9 14 4 27",
    "l.n 9 14 14 27",
    "l.n 39 14 34 27",
    "l.n 39 14 44 27",
    "p M2 27H16C16 32 12 34 9 34C6 34 2 32 2 27Z",
    "p M32 27H46C46 32 42 34 39 34C36 34 32 32 32 27Z",
    "c.a 24 11 3.5",
  ],
  "Fed Whisperer": [
    "g 10,13 9,3 18,8",
    "g 38,13 39,3 30,8",
    "p M24 6C13 6 9 14 9 25C9 36 15 43 24 43C33 43 39 36 39 25C39 14 35 6 24 6Z",
    "c.a 17.5 21 6",
    "c.a 30.5 21 6",
    "c.h 17.5 21 2.4",
    "c.h 30.5 21 2.4",
    "g.h 21,27 27,27 24,32",
  ],
  "Flash Crash": [
    "g 29,2 10,27 21,27 17,46 38,19 27,19",
    "c.a 9 10 2.5",
    "c.a 40 38 2.5",
    "c.a 41 8 1.6",
  ],
  "Whale Watcher": [
    "p M24 46C21 36 21 30 23 24C17 25 8 22 3 11C11 14 19 14 24 21C29 14 37 14 45 11C40 22 31 25 25 24C27 30 27 36 24 46Z",
    "p.t M4 42C8 38 12 38 16 42",
    "p.t M32 42C36 38 40 38 44 42",
  ],
  "Black Swan": [
    "p M10 34C10 27 17 24 26 25C33 26 40 30 43 26C43 36 36 42 25 42C16 42 10 39 10 34Z",
    "p.w M17 31C8 26 8 14 16 10C19 8.5 22 9.5 23 12",
    "c 22 11.5 4",
    "g.a 25,10 31,12.5 25,14",
    "c.h 21.5 10.8 0.9",
  ],
  "Central Banker": [
    "g 24,4 43,17 5,17",
    "r 8 20 5 16 1",
    "r 17 20 5 16 1",
    "r 26 20 5 16 1",
    "r 35 20 5 16 1",
    "r 5 38 38 5 1.5",
    "c.a 24 12 3",
  ],
  "Algo Overlord": [
    "l.s 24 10 24 4",
    "c.a 24 4 2.5",
    "r 9 10 30 28 7",
    "r 5 20 4 9 2",
    "r 39 20 4 9 2",
    "r 19 38 10 5 1",
    "r.a 13 18 22 7 3.5",
    "c.h 19 21.5 1.8",
    "c.h 29 21.5 1.8",
    "r.h 17 30 2.2 4 1",
    "r.h 21 30 2.2 4 1",
    "r.h 25 30 2.2 4 1",
    "r.h 29 30 2.2 4 1",
  ],
};

/** The glyph of every trait, classes and origins alike, by name. */
export const TRAITS = {
  Scalper: ["g 28,4 12,26 22,26 19,44 36,20 26,20"],
  Swing: ["p.w M5 24C11 6 19 6 24 24C29 42 37 42 43 24"],
  Momentum: ["p.w M6 38L18 26L26 32L38 16", "g 45,7 43,23 29,9"],
  Contrarian: ["p.w M14 40V20C14 10 34 10 34 20V28", "g 25,27 43,27 34,40"],
  Hedger: ["p M24 4L41 10V22C41 33 34 41 24 45C14 41 7 33 7 22V10Z", "p.k M16 23L22 29L33 17"],
  Arbitrageur: ["p.w M8 17H34", "g 33,8 45,17 33,26", "p.w M40 31H14", "g 15,22 3,31 15,40"],
  Quant: [
    "l.s 12 34 24 14",
    "l.s 24 14 37 30",
    "l.s 12 34 37 30",
    "c 12 34 5.5",
    "c 24 14 5.5",
    "c 37 30 5.5",
    "c.a 24 14 2.5",
  ],
  Whale: [
    "p M24 40C22 32 22 28 23.5 23C18 24 10 21 6 12C13 14.5 20 14.5 24 20.5C28 14.5 35 14.5 42 12C38 21 30 24 24.5 23C26 28 26 32 24 40Z",
  ],
  Equities: ["r 7 28 8 14 1.5", "r 20 18 8 24 1.5", "r 33 8 8 34 1.5"],
  Tech: [
    "l.s 18 6 18 12",
    "l.s 24 6 24 12",
    "l.s 30 6 30 12",
    "l.s 18 36 18 42",
    "l.s 24 36 24 42",
    "l.s 30 36 30 42",
    "l.s 6 18 12 18",
    "l.s 6 24 12 24",
    "l.s 6 30 12 30",
    "l.s 36 18 42 18",
    "l.s 36 24 42 24",
    "l.s 36 30 42 30",
    "r 12 12 24 24 4",
    "r.h 18 18 12 12 2",
  ],
  Crypto: [
    "g 24,3 42,13.5 42,34.5 24,45 6,34.5 6,13.5",
    "g.h 24,12 34,18 34,30 24,36 14,30 14,18",
    "c 24 24 4.5",
  ],
  Commodities: [
    "p M24 4C31 14 37 22 37 30A13 13 0 0 1 11 30C11 22 17 14 24 4Z",
    "p.k M17 30A7 7 0 0 0 24 37",
  ],
  Bonds: [
    "r 8 6 32 36 3",
    "r.h 14 13 20 2.6 1.3",
    "r.h 14 19 20 2.6 1.3",
    "r.h 14 25 12 2.6 1.3",
    "c.a 31 33 5",
  ],
  Forex: [
    "p.w M9 21A15.5 15.5 0 0 1 37 17",
    "g 41,6 43,22 28,18",
    "p.w M39 27A15.5 15.5 0 0 1 11 31",
    "g 7,42 5,26 20,30",
  ],
};

/** The icon of every item component, by name. */
export const COMPONENTS = {
  "Stop Order": ["g 17,5 31,5 43,17 43,31 31,43 17,43 5,31 5,17", "r.h 13 21 22 6 2"],
  "Limit Order": ["c 24 24 19", "c.h 24 24 13.5", "c 24 24 8.5", "c.a 24 24 3.5"],
  "Volume Filter": ["g 5,8 43,8 28,26 28,40 20,44 20,26"],
  "Volatility Gauge": [
    "p M5 32A19 19 0 0 1 43 32Z",
    "l.k 24 31 34 17",
    "c.a 24 31 3.5",
    "r 5 35 38 4 2",
  ],
  "Hedge Ticket": ["l.s 24 3 24 7", "p M3 24A21 21 0 0 1 45 24Z", "p.s M24 24V38C24 43 17 43 17 38"],
  "Cash Buffer": ["r 4 12 40 24 4", "c.h 24 24 7", "c 24 24 4", "c.h 10 18 2", "c.h 38 30 2"],
  "Margin Note": ["g 24,4 40,20 31,20 31,28 17,28 17,20 8,20", "r 17 32 14 4 1", "r 17 39 14 4 1"],
  Prospectus: [
    "p M12 4H30L38 12V44H12Z",
    "g.h 30,4 30,12 38,12",
    "g.a 24,19 26.6,25.2 33.3,25.6 28.1,29.9 29.9,36.4 24,32.8 18.1,36.4 19.9,29.9 14.7,25.6 21.4,25.2",
  ],
};

/** Interface icons, by name. */
export const ICONS = {
  coin: ["c 24 24 20", "c.h 24 24 15.5", "c 24 24 13.5", "g.h 24,15 31,24 24,33 17,24"],
  heart: ["p M24 42C10 32 4 25 4 16A10 10 0 0 1 24 12A10 10 0 0 1 44 16C44 25 38 32 24 42Z"],
  fight: [
    "l.w 8 8 32 32",
    "l.w 40 8 16 32",
    "l.s 25 39 39 25",
    "l.s 23 39 9 25",
    "c 39 39 3.5",
    "c 9 39 3.5",
  ],
  market: [
    "l.s 12 8 12 40",
    "l.s 24 4 24 36",
    "l.s 36 12 36 44",
    "r 8 16 8 16 1.5",
    "r 20 9 8 18 1.5",
    "r 32 20 8 16 1.5",
  ],
  carousel: ["c.s 24 24 15", "c 24 9 5", "c 39 24 5", "c 24 39 5", "c 9 24 5"],
  augment: ["g 24,4 41,14 41,34 24,44 7,34 7,14", "g.h 24,13 33,18.5 33,29.5 24,35 15,29.5 15,18.5"],
  reroll: [
    "p.w M9 21A15.5 15.5 0 0 1 37 17",
    "g 41,6 43,22 28,18",
    "p.w M39 27A15.5 15.5 0 0 1 11 31",
    "g 7,42 5,26 20,30",
  ],
  xp: ["p.w M10 26L24 12L38 26", "p.w M10 39L24 25L38 39"],
  star: ["g 24,3 30.2,17.5 46,19 34,29.5 37.6,45 24,36.8 10.4,45 14,29.5 2,19 17.8,17.5"],
  flame: ["p M24 3C27 12 36 16 36 28A12 12 0 0 1 12 28C12 22 15 19 17 15C18 19 20 21 22 21C21 14 22 8 24 3Z"],
  shield: ["p M24 4L41 10V22C41 33 34 41 24 45C14 41 7 33 7 22V10Z"],
};

/**
 * Split one shape string into `{ tag, tone, attrs }`.
 *
 * Throws a RangeError for a shape it cannot read, so a typo in the art never reaches the screen.
 */
export function parseShape(spec) {
  const [head, ...rest] = String(spec).trim().split(/\s+/);
  const [kind, tone = ""] = head.split(".");
  const tag = TAGS[kind];
  if (!tag || !(tone in TONES) || rest.length === 0) {
    throw new RangeError(`cannot read the shape "${spec}"`);
  }
  if (kind === "p") {
    return { tag, tone: TONES[tone], attrs: { d: rest.join(" ") } };
  }
  if (kind === "g") {
    return { tag, tone: TONES[tone], attrs: { points: rest.join(" ") } };
  }
  const names = NUMBERS[kind];
  const values = rest.map(Number);
  if (values.length > names.length || values.some((value) => !Number.isFinite(value))) {
    throw new RangeError(`cannot read the shape "${spec}"`);
  }
  const attrs = {};
  values.forEach((value, index) => {
    attrs[names[index]] = value;
  });
  return { tag, tone: TONES[tone], attrs };
}

/** The shapes of a picture: `table` is one of the tables above; unknown names give `null`. */
export function shapesOf(table, name) {
  return Object.prototype.hasOwnProperty.call(table, name) ? table[name].map(parseShape) : null;
}
