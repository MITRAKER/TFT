/**
 * The fight scene: both boards trade the round's slice in front of the player.
 *
 * The scene has three beats, driven by `data-phase` on the floor so that the style sheet owns
 * the motion: "trading" (every unit's chart is drawn), "resolved" (every unit shows what the
 * trade did to its size) and the banner with the result. A click or a key skips to the end.
 */
import { clear, el } from "./dom.js";
import { bannerOf, mirrorCell, resultLabel, resultTone } from "./logic.js";
import { hexCell, hexGrid, sparkSvg, token } from "./pieces.js";

export const TRADE_MS = 1500;
export const RESULT_MS = 1000;
export const BANNER_MS = 1400;
const TRACE_WIDTH = 64;
const TRACE_HEIGHT = 26;

function fighter(line, recipes) {
  const node = token(line, recipes);
  node.dataset.result = resultTone(line);
  node.append(
    el("span", { class: "trace" }, [sparkSvg(line, TRACE_WIDTH, TRACE_HEIGHT)]),
    el("span", { class: "verdict", text: resultLabel(line) }),
  );
  return node;
}

function lineAt(lines, row, col) {
  return lines.find((line) => line.cell[0] === row && line.cell[1] === col) || null;
}

/** Draw `lines` on a board; the opposing board is turned around to face the player. */
function fillBoard(node, board, lines, recipes, mirrored) {
  const cellFor = (row, col) => {
    const [unitRow, unitCol] = mirrored ? mirrorCell(board, row, col) : [row, col];
    const line = lineAt(lines, unitRow, unitCol);
    const piece = line ? fighter(line, recipes) : null;
    return hexCell("span", { class: `hex${line ? " occupied" : ""}` }, piece);
  };
  clear(node).append(...hexGrid(board, cellFor));
}

function showBanner(node, summary) {
  const banner = bannerOf(summary);
  const lines = [el("strong", { class: "banner-word", text: banner.word })];
  const versus = summary.opponent ? `against ${summary.opponent}` : "";
  const detail = [versus, banner.scores, banner.cost].filter(Boolean).join("  ·  ");
  if (detail) {
    lines.push(el("span", { class: "banner-detail", text: detail }));
  }
  clear(node).append(...lines);
  node.dataset.tone = banner.tone;
  node.hidden = false;
}

/**
 * Play the fight on `stage` ({ root, floor, mine, enemy, banner }) and call `done` exactly once,
 * at the end or when the player skips. Returns the function that skips.
 */
export function playFight(stage, summary, board, recipes, done) {
  const timers = [];
  let over = false;
  const finish = () => {
    if (over) {
      return;
    }
    over = true;
    timers.forEach((timer) => window.clearTimeout(timer));
    stage.root.removeEventListener("click", finish);
    stage.root.hidden = true;
    delete stage.floor.dataset.phase;
    stage.banner.hidden = true;
    done();
  };
  const after = (delay, step) => timers.push(window.setTimeout(step, delay));

  fillBoard(stage.mine, board, summary.units, recipes, false);
  fillBoard(stage.enemy, board, summary.opponent_units, recipes, true);
  stage.banner.hidden = true;
  stage.floor.dataset.phase = "trading";
  stage.root.hidden = false;
  stage.root.addEventListener("click", finish);
  after(TRADE_MS, () => {
    stage.floor.dataset.phase = "resolved";
  });
  after(TRADE_MS + RESULT_MS, () => showBanner(stage.banner, summary));
  after(TRADE_MS + RESULT_MS + BANNER_MS, finish);
  return finish;
}
