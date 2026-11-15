/** Building blocks the client draws in several places: unit tokens, hex grids, charts, item tiles. */
import { componentGlyph, el, portrait, svg } from "./dom.js";
import { hexRows, sparkline } from "./logic.js";

const STAR = "★";
const EMBLEM_PART = "Prospectus";

/** Map every completed item's name to the two components it is made of. */
export function recipesOf(catalog) {
  const recipes = new Map();
  for (const item of (catalog && catalog.items) || []) {
    recipes.set(item.name, item.components);
  }
  return recipes;
}

/** A unit as a token needs it, from the match state or from a line of a round summary. */
export function pieceOf(unit) {
  return {
    name: unit.name || unit.champion,
    cost: unit.cost,
    star: unit.star,
    origin: unit.origin,
    symbol: unit.symbol || null,
    items: (unit.items || []).map((item) => (typeof item === "string" ? item : item.name)),
  };
}

/** The component whose glyph stands for an item: the part that is not the emblem maker. */
function leadPart(parts) {
  return parts.find((part) => part !== EMBLEM_PART) || parts[0];
}

function itemPip(name, recipes) {
  const parts = recipes.get(name);
  return el("span", { class: "item-pip", title: name }, parts ? [componentGlyph(leadPart(parts))] : []);
}

/** A unit standing on the board or the bench: stars, portrait, name plate, ticker and items. */
export function token(unit, recipes) {
  const piece = pieceOf(unit);
  const plate = [el("span", { class: "name", text: piece.name })];
  if (piece.symbol) {
    plate.push(el("span", { class: "tag", text: piece.symbol }));
  }
  const data = { origin: piece.origin, cost: piece.cost, star: piece.star };
  return el("span", { class: "token", data }, [
    el("span", { class: "stars", "aria-hidden": "true", text: STAR.repeat(piece.star) }),
    el("span", { class: "disc" }, [portrait(piece.name)]),
    el("span", { class: "plate" }, plate),
    el(
      "span",
      { class: "token-items" },
      piece.items.map((name) => itemPip(name, recipes)),
    ),
  ]);
}

/** One cell of a hex board: the floor tile and, when a unit stands on it, its token. */
export function hexCell(tag, props, piece) {
  return el(tag, props, [el("span", { class: "tile" }), piece]);
}

/** The rows of a hex board; `cellFor(row, col)` builds each cell. */
export function hexGrid(board, cellFor) {
  return hexRows(board.rows, board.cols).map((line) =>
    el(
      "div",
      { class: `hex-row${line.shifted ? " shifted" : ""}` },
      line.cells.map(({ row, col }) => cellFor(row, col)),
    ),
  );
}

/** The closes of a unit's symbol over the slice as a small chart, with its buy and exit marks. */
export function sparkSvg(line, width, height) {
  const { points, coords } = sparkline(line.closes, width, height);
  const chart = svg("svg", {
    class: "spark",
    viewBox: `0 0 ${width} ${height}`,
    role: "img",
    "aria-label": `${line.symbol} over the slice`,
  });
  const d = points ? `M${points.split(" ").join("L")}` : "";
  chart.append(svg("path", { class: "spark-line", d, pathLength: 1 }));
  for (const [bar, what] of line.marks || []) {
    const point = coords[bar];
    if (point) {
      const title = svg("title");
      title.textContent = `${what} on day ${bar + 1}`;
      chart.append(svg("circle", { class: `mark-${what}`, cx: point[0], cy: point[1], r: 3 }, [title]));
    }
  }
  return chart;
}

/** A component or a completed item as a tile: one glyph, or the glyphs of both parts. */
export function itemTile(parts, props) {
  const glyphs = parts.map((part) => el("span", { class: "half" }, [componentGlyph(part)]));
  const kind = parts.length > 1 ? "item-tile full" : "item-tile";
  return el("button", { type: "button", ...props, class: `${kind}${props.class ? ` ${props.class}` : ""}` }, glyphs);
}
