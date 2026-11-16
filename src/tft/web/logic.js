/**
 * Pure helpers for the browser client: no DOM, no network, so they run under Node's test runner.
 *
 * A selection is `null` or one of
 *   { type: "unit", index, where: "board" | "bench", cell: [row, col] | null }
 *   { type: "component", index }
 *   { type: "item", index }
 * A target is one of
 *   { type: "cell", row, col, unit: index | null }
 *   { type: "bench", unit: index | null }
 *   { type: "component", index }
 *   { type: "item", index }
 */

export const INTEREST_STEP = 10;
export const INTEREST_CAP = 5;

/** Clamp `value / max` to a whole percentage between 0 and 100. */
export function percent(value, max) {
  if (!(max > 0)) {
    return 0;
  }
  return Math.max(0, Math.min(100, Math.round((value / max) * 100)));
}

/** The tone of a health bar: "high" above 60 percent, "mid" above 30, otherwise "low". */
export function healthTone(health, max) {
  const share = percent(health, max);
  if (share > 60) {
    return "high";
  }
  return share > 30 ? "mid" : "low";
}

/** How many interest pips `gold` lights, out of INTEREST_CAP. */
export function interestPips(gold) {
  return Math.max(0, Math.min(INTEREST_CAP, Math.floor(gold / INTEREST_STEP)));
}

/** "+1.2%" / "-0.4%" / "0.0%". */
export function signed(value, digits = 1) {
  const fixed = Number(value).toFixed(digits);
  const zero = Number(fixed) === 0;
  return `${value > 0 && !zero ? "+" : ""}${zero ? fixed.replace("-", "") : fixed}%`;
}

/** "W3" for three wins in a row, "L2" for two losses, "-" for none. */
export function streakText(streak) {
  if (streak > 0) {
    return `W${streak}`;
  }
  return streak < 0 ? `L${-streak}` : "-";
}

/** "Breakout Bull" becomes "BB"; a single word keeps its first two letters. */
export function initials(name) {
  const words = String(name).split(/\s+/).filter(Boolean);
  if (words.length === 0) {
    return "";
  }
  if (words.length === 1) {
    return words[0].slice(0, 2).toUpperCase();
  }
  return (words[0][0] + words[1][0]).toUpperCase();
}

/** "1st", "2nd", "3rd", "4th", ... */
export function ordinal(place) {
  const tens = place % 100;
  if (tens >= 11 && tens <= 13) {
    return `${place}th`;
  }
  const suffix = { 1: "st", 2: "nd", 3: "rd" }[place % 10] || "th";
  return `${place}${suffix}`;
}

/** The board as rows of cells, front row first; odd rows are drawn shifted. */
export function hexRows(rows, cols) {
  const grid = [];
  for (let row = 0; row < rows; row += 1) {
    const cells = [];
    for (let col = 0; col < cols; col += 1) {
      cells.push({ row, col });
    }
    grid.push({ row, shifted: row % 2 === 1, cells });
  }
  return grid;
}

/** The unit standing on a cell, or null. */
export function unitAt(units, row, col) {
  return units.find((unit) => unit.cell && unit.cell[0] === row && unit.cell[1] === col) || null;
}

/** Whether another unit stands in front of `[row, col]` in the same column. */
export function isCovered(units, row, col) {
  return units.some((unit) => unit.cell && unit.cell[1] === col && unit.cell[0] < row);
}

/** What standing on a row does, as text: "size 110%, exposed: drawdowns weigh 50% more". */
export function cellEffect(board, units, row, col) {
  const parts = [`size ${board.row_size[row]}%`];
  const shield = board.row_shield[row];
  if (shield) {
    parts.push(`forgives ${shield}% of drawdowns`);
  }
  if (row >= Math.floor(board.rows / 2)) {
    parts.push(
      isCovered(units, row, col)
        ? `covered: forgives ${board.cover}% of drawdowns`
        : `exposed: drawdowns weigh ${board.exposed}% more`,
    );
  }
  return parts.join(", ");
}

/** Shop odds as "1: 45%  2: 33%  3: 20%  4: 2%  5: 0%". */
export function oddsText(odds) {
  return odds.map((chance, index) => `${index + 1}: ${chance}%`).join("  ");
}

/** Points of an SVG polyline for `closes`, fitted into a width x height box with padding. */
export function sparkline(closes, width, height, pad = 3) {
  if (!closes || closes.length === 0) {
    return { points: "", coords: [] };
  }
  const low = Math.min(...closes);
  const high = Math.max(...closes);
  const span = high - low || 1;
  const step = closes.length > 1 ? (width - 2 * pad) / (closes.length - 1) : 0;
  const coords = closes.map((close, index) => [
    Number((pad + index * step).toFixed(2)),
    Number((height - pad - ((close - low) / span) * (height - 2 * pad)).toFixed(2)),
  ]);
  return { points: coords.map(([x, y]) => `${x},${y}`).join(" "), coords };
}

/** The headline of a round summary. */
export function headline(summary) {
  if (summary.outcome === "none") {
    return "No fight this round";
  }
  const versus = summary.opponent ? ` against ${summary.opponent}` : "";
  if (summary.outcome === "won") {
    return `You won${versus}`;
  }
  if (summary.outcome === "draw") {
    return `Draw${versus}`;
  }
  const cost = summary.damage ? ` (-${summary.damage} health)` : "";
  return `You lost${versus}${cost}`;
}

/** One fight of a round report as a sentence. */
export function fightText(fight) {
  if (fight.draw) {
    return `${fight.home} and ${fight.away} drew`;
  }
  return `${fight.winner} beat ${fight.loser} with ${fight.survivors} unit(s) left`;
}

/** What a unit's trade multiplied its size by: 1 keeps it, 0 is a wipe-out. */
export function factorOf(line) {
  return line.size > 0 ? line.score / line.size : 0;
}

/** How a unit's round went: "out" (wiped out), "up", "down" or "flat". */
export function resultTone(line) {
  if (!(line.size > 0)) {
    return "flat";
  }
  if (line.score <= 0) {
    return "out";
  }
  const change = Math.round((factorOf(line) - 1) * 100);
  if (change === 0) {
    return "flat";
  }
  return change > 0 ? "up" : "down";
}

/** The label a unit's result gets in the fight: "+38%", "-26%", "0%" or "wiped out". */
export function resultLabel(line) {
  const tone = resultTone(line);
  if (tone === "out") {
    return "wiped out";
  }
  const change = Math.round((factorOf(line) - 1) * 100);
  return `${change > 0 ? "+" : ""}${change}%`;
}

/** Where a cell of the opposing board is drawn: turned around to face the player. */
export function mirrorCell(board, row, col) {
  return [board.rows - 1 - row, board.cols - 1 - col];
}

/**
 * A unit's place in the rhythm of a fight, from 0 up to 1, by its cell: neighbours get
 * different beats, so a board does not strike as one body.
 */
export function beatOf(cell) {
  const [row, col] = cell || [0, 0];
  return ((row * 3 + col * 5) % 8) / 8;
}

/**
 * Where the player's action has just put a unit, for the drop-in: `{ row, col }` after fielding
 * or moving one, `{ slot }` when a purchase or benching added one to the bench, otherwise `null`.
 * `before` and `after` are the player's seat around the action.
 */
export function arrivalOf(action, before, after) {
  if (action.kind === "field" || action.kind === "move") {
    const [, row, col] = action.args;
    return unitAt(after.board, row, col) ? { row, col } : null;
  }
  const added = after.bench.length === before.bench.length + 1;
  if ((action.kind === "buy" || action.kind === "bench") && added) {
    return { slot: after.bench.length - 1 };
  }
  return null;
}

/** Every seat for the scoreboard: the living by health, then the eliminated; `me` marks the player. */
export function standings(seat, others) {
  const seats = others.map((other) => ({ ...other, me: false }));
  if (seat) {
    seats.push({ ...seat, me: true });
  }
  return seats.sort(
    (a, b) => Number(b.alive) - Number(a.alive) || b.health - a.health || a.name.localeCompare(b.name),
  );
}

/** The kind of a round for its icon: "carousel", "market" (against the Market) or "fight". */
export function roundKind(round) {
  if (round.carousel) {
    return "carousel";
  }
  return round.pve ? "market" : "fight";
}

/** A trait's breakpoints with whether the count reaches each: [{ needed: 2, reached: true }, ...]. */
export function traitSteps(trait) {
  return trait.breakpoints.map((needed) => ({ needed, reached: trait.count >= needed }));
}

/** The banner of the fight scene: its word and its tone. */
export function bannerOf(summary) {
  const words = { won: "Victory", lost: "Defeat", draw: "Draw" };
  const word = words[summary.outcome] || "No fight";
  const scores =
    summary.outcome in words
      ? `${summary.score.toFixed(1)} to ${summary.opponent_score.toFixed(1)}`
      : "";
  const cost = summary.outcome === "lost" && summary.damage ? `-${summary.damage} health` : "";
  return { word, tone: summary.outcome, scores, cost };
}

const SELECT = (selection) => ({ kind: "select", selection });
const ACT = (kind, args) => ({ kind: "action", action: { kind, args } });
const CLEAR = { kind: "clear" };
const NONE = { kind: "none" };

function selectTarget(target) {
  if (target.type === "component" || target.type === "item") {
    return SELECT({ type: target.type, index: target.index });
  }
  if (target.unit === null || target.unit === undefined) {
    return NONE;
  }
  const where = target.type === "cell" ? "board" : "bench";
  const cell = target.type === "cell" ? [target.row, target.col] : null;
  return SELECT({ type: "unit", index: target.unit, where, cell });
}

function fromUnit(selection, target) {
  if (target.type === "component" || target.type === "item") {
    return selectTarget(target);
  }
  if (target.unit === selection.index) {
    return CLEAR;
  }
  if (target.type === "cell") {
    const kind = selection.where === "bench" ? "field" : "move";
    return ACT(kind, [selection.index, target.row, target.col]);
  }
  if (selection.where === "bench") {
    return target.unit === null ? CLEAR : selectTarget(target);
  }
  if (target.unit === null) {
    return ACT("bench", [selection.index]);
  }
  return ACT("field", [target.unit, selection.cell[0], selection.cell[1]]);
}

function fromItem(selection, target) {
  if (target.type === "item") {
    return target.index === selection.index ? CLEAR : selectTarget(target);
  }
  if (target.type === "component") {
    return selectTarget(target);
  }
  if (target.unit === null) {
    return CLEAR;
  }
  return ACT("equip", [target.unit, selection.index]);
}

function fromComponent(selection, target) {
  if (target.type === "component") {
    return target.index === selection.index ? CLEAR : ACT("craft", [selection.index, target.index]);
  }
  if (target.type === "item" || target.unit !== null) {
    return selectTarget(target);
  }
  return CLEAR;
}

/**
 * Decide what a click means given what is selected.
 *
 * Returns `{kind: "action", action}` to send to the server, `{kind: "select", selection}`,
 * `{kind: "clear"}` to drop the selection, or `{kind: "none"}`.
 */
export function nextStep(selection, target) {
  if (!selection) {
    return selectTarget(target);
  }
  if (selection.type === "unit") {
    return fromUnit(selection, target);
  }
  return selection.type === "item" ? fromItem(selection, target) : fromComponent(selection, target);
}
