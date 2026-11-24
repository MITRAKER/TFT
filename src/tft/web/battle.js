/**
 * The battle: a fight between two boards as a timed script that the scene plays back.
 *
 * The engine decides who wins by trading the round's slice; nothing here changes that. This
 * module turns the decided result into the fight an auto-battler shows: the units leave their
 * cells, close with the nearest enemy, strike or shoot, lose health and fall, until the side
 * that lost has nobody left and the winner keeps as many units as the engine says survived.
 * The weakest trades fall first, so the fight tells the same story as the scores. It is pure:
 * the same boards and the same result give the same script, so it is tested without a browser.
 *
 * Places are in widths of a cell and times in seconds. The far board is the other player's,
 * drawn turned around: its front row is the one next to the player's front row.
 */
import { mirrorCell } from "./logic.js";

/** From one cell to the next in a row, from one row to the next, and how far an odd row is shifted. */
export const COLUMN = 1.05;
export const ROW = 0.916;
export const SHIFT = COLUMN / 2;
/** From the front row of one board to the front row of the other. */
export const BOARD_GAP = 1.4947;

const STEP = 1 / 30;
const TRACK_STEPS = 3;
const MELEE = 1.12;
const RANGED = 3.4;
const SPEED = 2.5;
const SHOT_SPEED = 9;
const SWING = 0.12;
const PERSONAL_SPACE = 0.62;
const MARGIN = 0.6;
const SHORTEST = 4;
const LONGEST = 7.5;
const CHEER = 0.9;
const FIRST_FALL = 0.3;
const LAST_WINNER_FALL = 0.85;
const HEAVY_SHARE = 0.3;

/**
 * How each class fights: how far it reaches and how long it takes between two blows. The
 * classes that stand in front by default fight hand to hand; the others shoot.
 */
export const STYLES = {
  Whale: { reach: MELEE, period: 1.1 },
  Swing: { reach: MELEE, period: 0.9 },
  Scalper: { reach: MELEE, period: 0.5 },
  Hedger: { reach: MELEE, period: 0.95 },
  Momentum: { reach: RANGED, period: 0.8 },
  Contrarian: { reach: RANGED, period: 0.85 },
  Arbitrageur: { reach: RANGED, period: 0.7 },
  Quant: { reach: RANGED, period: 0.75 },
};
const BRAWLER = { reach: MELEE, period: 0.9 };

const clamp = (value, low, high) => Math.min(Math.max(value, low), high);

/** Where a unit stands before the fight: `side` is "mine" or "theirs", `cell` its own cell. */
export function homeOf(side, cell, board) {
  const [row, col] = side === "mine" ? cell : mirrorCell(board, cell[0], cell[1]);
  const across = col * COLUMN + (row % 2 === 1 ? SHIFT : 0);
  const down = side === "mine" ? (board.rows - 1) * ROW + BOARD_GAP + row * ROW : row * ROW;
  return { x: across, y: down };
}

/** The corners of the ground the fight may use: both boards and a margin around them. */
export function fieldOf(board) {
  return {
    left: -MARGIN,
    right: (board.cols - 1) * COLUMN + SHIFT + MARGIN,
    top: -MARGIN,
    bottom: 2 * (board.rows - 1) * ROW + BOARD_GAP + MARGIN,
  };
}

function fighterOf(side, index, line, board, abilities) {
  const style = Object.prototype.hasOwnProperty.call(STYLES, line.role) ? STYLES[line.role] : BRAWLER;
  return {
    id: `${side}-${index}`,
    side,
    name: line.champion,
    home: homeOf(side, line.cell, board),
    health: Math.max(Number(line.size) || 0, 0.01),
    power: Math.max(Number(line.score) || 0, 0),
    reach: style.reach,
    period: style.period,
    ability: abilities.get(line.champion) || "",
  };
}

/**
 * Everybody who fights, from a round summary: my units, then the other board's. `abilities`
 * maps a champion's name to the name of its signature move. A line without a cell is left out.
 */
export function fightersOf(summary, board, abilities = new Map()) {
  const side = (name, lines) =>
    (lines || [])
      .map((line, index) => (line.cell ? fighterOf(name, index, line, board, abilities) : null))
      .filter(Boolean);
  return side("mine", summary.units).concat(side("theirs", summary.opponent_units));
}

/** How long the fighting lasts: longer with more units, within limits. */
export function lengthOf(count) {
  return clamp(3 + 0.3 * count, SHORTEST, LONGEST);
}

/** The side that the result says won, or "" for a draw. */
function winnerOf(outcome) {
  if (outcome === "won") {
    return "mine";
  }
  return outcome === "lost" ? "theirs" : "";
}

/**
 * The order in which a side falls: the units next to the enemy and the units whose trade made
 * least of them go first. `centre` is the line between the two boards.
 */
function fallOrder(units, centre) {
  const strongest = Math.max(...units.map((unit) => unit.power), 1e-9);
  const key = (unit) => Math.abs(unit.home.y - centre) / ROW + (1.5 * unit.power) / strongest;
  return [...units].sort((a, b) => key(a) - key(b) || a.id.localeCompare(b.id));
}

/**
 * When every unit falls, if it does, and how much of its health a survivor keeps.
 *
 * The side that lost falls to the last unit, at the end of the fight. The winner keeps
 * `survivors` units, the ones with the best trades, and loses the others before the end; a
 * narrow win leaves the survivors nearly spent. In a draw both sides fall, the last two at
 * the same moment.
 */
export function fatesOf(fighters, board, result, length) {
  const fates = new Map();
  const winner = winnerOf(result.outcome);
  const centre = (board.rows - 1) * ROW + BOARD_GAP / 2;
  const kept = clamp(0.2 + 0.8 * (Number(result.margin) || 0), 0.15, 1);
  for (const side of ["mine", "theirs"]) {
    const units = fighters.filter((fighter) => fighter.side === side);
    const stays = side === winner ? clamp(Math.round(Number(result.survivors) || 1), 1, units.length) : 0;
    const strongest = [...units].sort((a, b) => b.power - a.power || a.id.localeCompare(b.id));
    const standing = new Set(strongest.slice(0, stays).map((unit) => unit.id));
    const falling = fallOrder(
      units.filter((unit) => !standing.has(unit.id)),
      centre,
    );
    const last = side === winner ? LAST_WINNER_FALL : 1;
    falling.forEach((unit, index) => {
      // The last one falls exactly at `last`, not a rounding error before it.
      const part = (index + 1) / falling.length;
      const share = part === 1 ? last : FIRST_FALL + (last - FIRST_FALL) * part;
      fates.set(unit.id, { falls: length * share, left: 0 });
    });
    standing.forEach((id) => fates.set(id, { falls: null, left: kept }));
  }
  return fates;
}

/** The health a unit should show at a time: it runs down evenly to what its fate leaves. */
function levelOf(unit, time, length) {
  const end = unit.falls === null ? length : unit.falls;
  return unit.health * (1 - (1 - unit.left) * clamp(time / end, 0, 1));
}

const distance = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);

/** The nearest unit of `others` to `unit`, or null; ties go to the lower id. */
function nearest(unit, others) {
  let best = null;
  let closest = Infinity;
  for (const other of others) {
    const far = distance(unit, other);
    if (far < closest - 1e-9 || (Math.abs(far - closest) <= 1e-9 && best && other.id < best.id)) {
      best = other;
      closest = far;
    }
  }
  return best;
}

/** Move a unit towards its target until the target is within reach. */
function approach(unit, target) {
  const far = distance(unit, target);
  const wanted = unit.reach * (unit.reach > MELEE ? 0.95 : 0.88);
  if (far <= wanted) {
    return;
  }
  const stride = Math.min(SPEED * STEP, far - wanted);
  unit.x += ((target.x - unit.x) / far) * stride;
  unit.y += ((target.y - unit.y) / far) * stride;
}

/** Push apart the units that stand on each other's feet, and keep everybody on the field. */
function spread(units, field) {
  for (let first = 0; first < units.length; first += 1) {
    for (let second = first + 1; second < units.length; second += 1) {
      const a = units[first];
      const b = units[second];
      const far = distance(a, b);
      if (far < PERSONAL_SPACE) {
        // Two units on the same spot are parted along a line that depends on who they are.
        const angle = far > 1e-6 ? Math.atan2(b.y - a.y, b.x - a.x) : first + second;
        const push = Math.min((PERSONAL_SPACE - far) / 2, SPEED * STEP);
        a.x -= Math.cos(angle) * push;
        a.y -= Math.sin(angle) * push;
        b.x += Math.cos(angle) * push;
        b.y += Math.sin(angle) * push;
      }
    }
  }
  for (const unit of units) {
    unit.x = clamp(unit.x, field.left, field.right);
    unit.y = clamp(unit.y, field.top, field.bottom);
  }
}

/**
 * One blow: when it starts, when it lands, and whether it is thrown or struck. Returns the
 * blow as it will land.
 */
function blow(state, unit, target, starts, lands) {
  const style = unit.reach > MELEE || distance(unit, target) > MELEE * 1.2 ? "shot" : "strike";
  const heavy = unit.charged;
  state.events.push({ t: starts, kind: "attack", from: unit.id, to: target.id, style, lands, heavy });
  unit.charged = false;
  unit.wait = unit.period;
  return { t: lands, from: unit, to: target, style, heavy };
}

/** What a unit does in one step: find a target, close in, and hit when it can. */
function act(state, unit, time) {
  const foes = state.alive.filter((other) => other.side !== unit.side);
  if (!unit.target || unit.target.down) {
    unit.target = nearest(unit, foes);
  }
  unit.wait -= STEP;
  if (!unit.target) {
    return;
  }
  if (!unit.cast && time >= unit.casts) {
    unit.cast = true;
    unit.charged = true;
    state.events.push({ t: time, kind: "cast", unit: unit.id, name: unit.ability });
  }
  if (distance(unit, unit.target) > unit.reach) {
    approach(unit, unit.target);
  } else if (unit.wait <= 0) {
    const flight = unit.reach > MELEE ? distance(unit, unit.target) / SHOT_SPEED : SWING;
    state.landing.push(blow(state, unit, unit.target, time, time + flight));
  }
}

/** Let the blows that have arrived land: the target's health drops to where it should be. */
function land(state, time) {
  const still = [];
  for (const hit of state.landing) {
    if (hit.t > time) {
      still.push(hit);
    } else if (!hit.to.down) {
      const level = levelOf(hit.to, hit.t, state.length);
      const loss = Math.max(hit.to.shown - level, 0);
      hit.to.shown = level;
      state.events.push({
        t: hit.t,
        kind: "hit",
        to: hit.to.id,
        from: hit.from.id,
        style: hit.style,
        health: level,
        loss,
        heavy: hit.heavy || loss > HEAVY_SHARE * hit.to.health,
      });
    }
  }
  state.landing = still;
}

/** Bring down the units whose time has come, each by a last blow from the enemy nearest to it. */
function fell(state, time) {
  const due = state.alive.filter((unit) => unit.falls !== null && unit.falls <= time);
  for (const unit of due) {
    const foes = state.alive.filter((other) => other.side !== unit.side);
    const killer = nearest(unit, foes.filter((foe) => foe.target === unit)) || nearest(unit, foes);
    let style = "strike";
    if (killer) {
      const lead = killer.reach > MELEE ? Math.min(distance(killer, unit) / SHOT_SPEED, 0.35) : SWING;
      ({ style } = blow(state, killer, unit, unit.falls - lead, unit.falls));
    }
    state.events.push({
      t: unit.falls,
      kind: "hit",
      to: unit.id,
      from: killer ? killer.id : "",
      style,
      health: 0,
      loss: unit.shown,
      heavy: true,
    });
    state.events.push({ t: unit.falls, kind: "fall", unit: unit.id });
    unit.shown = 0;
  }
  for (const unit of due) {
    unit.down = true;
  }
  state.alive = state.alive.filter((unit) => !unit.down);
}

function startOf(fighters, fates, length) {
  return fighters.map((fighter, index) => {
    const fate = fates.get(fighter.id);
    const lifetime = fate.falls === null ? length : fate.falls;
    return {
      ...fighter,
      ...fate,
      x: fighter.home.x,
      y: fighter.home.y,
      shown: fighter.health,
      target: null,
      down: false,
      // The first blows and the signature moves are spread out, so a board is not one body.
      wait: 0.15 + ((index * 7) % 5) * 0.09,
      casts: lifetime * (0.3 + ((index * 5) % 7) * 0.05),
      cast: false,
      charged: false,
      track: [{ t: 0, x: fighter.home.x, y: fighter.home.y }],
    };
  });
}

/**
 * The script of a fight. `result` is `{ outcome, survivors, margin }`: "won", "lost" or
 * "draw" as the player sees it, how many units the winner keeps, and how clear the win was
 * from 0 to 1.
 *
 * Returns `{ length, total, field, fighters, tracks, events }`: how long the fighting lasts
 * and the scene with the cheering, the ground, every fighter with when it `falls` (or null)
 * and the share of health it has `left`, where each fighter is over time, and what happens,
 * in order: "cast" (a signature move), "attack" (a blow leaves, as a "strike" or a "shot"),
 * "hit" (it lands, with the health the target has left), "fall" and, at the end, "cheer".
 */
export function planBattle(fighters, board, result) {
  const length = lengthOf(fighters.length);
  const fates = fatesOf(fighters, board, result, length);
  const units = startOf(fighters, fates, length);
  const field = fieldOf(board);
  const state = { length, events: [], landing: [], alive: [...units] };
  const steps = Math.round(length / STEP);
  for (let step = 1; step <= steps; step += 1) {
    const time = step === steps ? length : step * STEP;
    // Those whose time has come fall first: a unit does nothing in the step in which it falls.
    fell(state, time);
    state.alive.forEach((unit) => act(state, unit, time));
    spread(state.alive, field);
    land(state, time);
    if (step % TRACK_STEPS === 0 || step === steps) {
      state.alive.forEach((unit) => unit.track.push({ t: time, x: unit.x, y: unit.y }));
    }
  }
  const winner = winnerOf(result.outcome);
  if (state.alive.length > 0) {
    state.events.push({ t: length + 0.15, kind: "cheer", side: winner });
  }
  state.events.sort((a, b) => a.t - b.t);
  return {
    length,
    total: length + CHEER,
    field,
    fighters: units.map(({ id, side, name, home, health, reach, falls, left, casts, ability }) => ({
      id,
      side,
      name,
      home,
      health,
      reach,
      falls,
      left,
      casts,
      ability,
    })),
    tracks: new Map(units.map((unit) => [unit.id, unit.track])),
    events: state.events,
  };
}

/** Where a fighter is at a time, between the points of its track; it stays where the track ends. */
export function placeAt(track, time) {
  let before = track[0];
  for (const point of track) {
    if (point.t > time) {
      const span = point.t - before.t;
      const share = span > 0 ? (time - before.t) / span : 1;
      return { x: before.x + (point.x - before.x) * share, y: before.y + (point.y - before.y) * share };
    }
    before = point;
  }
  return { x: before.x, y: before.y };
}

/**
 * What a round summary and the round's fights say about the seat's own fight:
 * `{ outcome, survivors, margin }` for `planBattle`. Without a matching fight the winner
 * keeps one unit.
 */
export function resultOf(summary, fights, seat) {
  const fight = (fights || []).find((entry) => entry.home === seat || entry.away === seat) || null;
  const high = Math.max(summary.score || 0, summary.opponent_score || 0);
  const low = Math.min(summary.score || 0, summary.opponent_score || 0);
  return {
    outcome: summary.outcome,
    survivors: fight && !fight.draw ? fight.survivors : 1,
    margin: high > 0 ? (high - low) / high : 0,
  };
}
