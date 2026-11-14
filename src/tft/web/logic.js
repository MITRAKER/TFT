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

/** What standing on a row does, as text: "size 120%, exposed: drawdowns weigh 25% more". */
export function cellEffect(board, units, row, col) {
  const parts = [`size ${board.row_size[row]}%`];
  const shield = board.row_shield[row];
  if (shield) {
    parts.push(`absorbs ${shield}% of drawdowns`);
  }
  if (row >= Math.floor(board.rows / 2)) {
    parts.push(
      isCovered(units, row, col)
        ? `covered: absorbs ${board.cover}% more`
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
