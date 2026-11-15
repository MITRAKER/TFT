/**
 * The browser client: draws the match the server describes and sends the player's actions.
 * All game logic lives on the server. The pure helpers are in logic.js, the pictures in art.js,
 * the shared pieces in pieces.js and the fight scene in scene.js.
 */
import { $, button, clear, decorate, el, icon, portrait, traitGlyph } from "./dom.js";
import {
  cellEffect,
  fightText,
  headline,
  interestPips,
  isCovered,
  nextStep,
  oddsText,
  ordinal,
  percent,
  resultLabel,
  resultTone,
  roundKind,
  signed,
  standings,
  streakText,
  traitSteps,
  unitAt,
} from "./logic.js";
import { hexCell, hexGrid, itemTile, recipesOf, sparkSvg, token } from "./pieces.js";
import { playFight } from "./scene.js";

const AUTO_DELAY_MS = 1200;
const TOAST_MS = 3200;
const SPARK_WIDTH = 120;
const SPARK_HEIGHT = 32;
const STAR = "★";
const HINT =
  "Click a unit, then a cell to place it. Click two components to craft an item, " +
  "then the item and a unit to equip it.";
const ROUND_NAMES = {
  fight: "player fight",
  market: "against the Market",
  carousel: "carousel, then a player fight",
};

const view = {
  match: null,
  catalog: null,
  recipes: new Map(),
  selection: null,
  auto: false,
  busy: false,
  timer: null,
  skipScene: null,
};

/** A refusal by the rules or the server, with a message for the player. */
class Refused extends Error {}

async function request(method, path, body) {
  const options = { method, headers: {} };
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  let response;
  try {
    response = await fetch(path, options);
  } catch {
    throw new Refused("Cannot reach the server.");
  }
  let data;
  try {
    data = await response.json();
  } catch {
    data = null;
  }
  if (!data || data.ok !== true) {
    throw new Refused((data && data.error) || `The server answered ${response.status}.`);
  }
  return data;
}

function matchPath(id, suffix = "") {
  return `/api/matches/${encodeURIComponent(id)}${suffix}`;
}

function toast(message, isError = false) {
  const node = $("toast");
  node.textContent = message;
  node.className = `toast show${isError ? " error" : ""}`;
  window.clearTimeout(view.timer);
  view.timer = window.setTimeout(() => {
    node.className = "toast";
  }, TOAST_MS);
}

/** Run an async step, one at a time, and show refusals as a toast. */
async function guarded(step) {
  if (view.busy) {
    return;
  }
  view.busy = true;
  try {
    await step();
  } catch (error) {
    if (!(error instanceof Refused)) {
      throw error;
    }
    toast(error.message, true);
  } finally {
    view.busy = false;
  }
}

function show(screen) {
  for (const name of ["lobby", "game", "spectate"]) {
    $(name).hidden = name !== screen;
  }
  if (screen !== "spectate") {
    view.auto = false;
  }
  $("toast").className = "toast";
}

/* Dialogs ------------------------------------------------------------------ */

function openDialog(title, body, actions, tone = "") {
  const heading = $("dialog-title");
  heading.textContent = title;
  heading.className = tone;
  clear($("dialog-body")).append(...body);
  clear($("dialog-actions")).append(...actions);
  $("overlay").hidden = false;
  if (actions.length > 0) {
    actions[actions.length - 1].focus();
  }
}

function closeDialog() {
  $("overlay").hidden = true;
}

/* Small pieces ------------------------------------------------------------- */

function fromCatalog(kind, name) {
  const entries = (view.catalog && view.catalog[kind]) || [];
  return entries.find((entry) => entry.name === name) || null;
}

function glyphSlot(glyph, extra = "") {
  return el("span", { class: `glyph-slot${extra ? ` ${extra}` : ""}` }, [glyph]);
}

function coins(amount) {
  return el("span", { class: "coins" }, [
    glyphSlot(icon("coin"), "gold"),
    document.createTextNode(String(amount)),
  ]);
}

function traitChip(name) {
  return el("span", { class: "trait-chip" }, [glyphSlot(traitGlyph(name)), document.createTextNode(name)]);
}

function healthBar(seat) {
  const fill = el("span", { class: "fill hp" });
  fill.style.setProperty("--amount", `${percent(seat.health, seat.max_health)}%`);
  return el("span", { class: "bar" }, [fill]);
}

function tone(value) {
  if (value > 0) {
    return "pos";
  }
  return value < 0 ? "neg" : "";
}

function moveChip(origin, move) {
  return el("span", { class: "move", data: { origin } }, [
    glyphSlot(traitGlyph(origin)),
    document.createTextNode(`${origin} `),
    el("span", { class: tone(move), text: signed(move) }),
  ]);
}

function isSelectedUnit(unit) {
  const selection = view.selection;
  return Boolean(unit && selection && selection.type === "unit" && selection.index === unit.index);
}

function isSelected(type, index) {
  const selection = view.selection;
  return Boolean(selection && selection.type === type && selection.index === index);
}

function miniBoard(units, board) {
  const cellFor = (row, col) => {
    const unit = unitAt(units, row, col);
    const props = { class: `hex${unit ? " occupied" : ""}` };
    if (unit) {
      props.title = `${unit.name} ${STAR.repeat(unit.star)}`;
    }
    return hexCell("span", props, unit ? token(unit, view.recipes) : null);
  };
  return el("div", { class: "board mini" }, hexGrid(board, cellFor));
}

function traitText(traits) {
  const active = traits.filter((trait) => trait.tier > 0);
  if (active.length === 0) {
    return "No active traits";
  }
  return active.map((trait) => `${trait.name} ${trait.count}`).join(", ");
}

/* Lobby -------------------------------------------------------------------- */

function setRoundInfo(text) {
  $("round-info").textContent = text;
}

function matchLabel(card) {
  const alive = card.seats.filter((seat) => seat.alive).length;
  let status = `after ${card.rounds_played} round(s)`;
  if (card.finished) {
    status = "finished";
  } else if (card.round) {
    status = `round ${card.round}`;
  }
  const kind = card.has_seat ? "Your match" : "Bot match";
  return `${kind}, ${card.mode} mode, ${status}, ${alive} of ${card.seats.length} alive`;
}

function renderMatchList(matches) {
  const list = clear($("match-list"));
  $("match-empty").hidden = matches.length > 0;
  for (const card of matches) {
    const actions = [];
    if (card.has_seat && !card.finished) {
      actions.push(button("Resume", () => guarded(() => openMatch(card.id, false))));
    }
    actions.push(button("Spectate", () => guarded(() => openMatch(card.id, true))));
    actions.push(button("Delete", () => guarded(() => removeMatch(card.id)), { class: "danger" }));
    list.append(
      el("li", { class: "match-row" }, [
        el("span", { text: matchLabel(card) }),
        el("span", { class: "row" }, actions),
      ]),
    );
  }
}

function renderShowcase() {
  const champions = (view.catalog && view.catalog.champions) || [];
  const units = champions.map((champion) =>
    el(
      "span",
      {
        class: "show-unit",
        title: `${champion.name}: ${champion.cost}-cost ${champion.origin} ${champion.role}`,
      },
      [token({ ...champion, star: 1, items: [] }, view.recipes)],
    ),
  );
  clear($("showcase")).append(...units);
}

function endScene() {
  if (view.skipScene) {
    view.skipScene();
  }
}

async function loadLobby() {
  endScene();
  show("lobby");
  setRoundInfo("");
  closeDialog();
  const data = await request("GET", "/api/matches");
  renderMatchList(data.matches);
}

async function openMatch(id, spectate) {
  const data = await request("GET", matchPath(id, spectate ? "/spectate" : ""));
  setMatch(data.state);
}

async function removeMatch(id) {
  await request("DELETE", matchPath(id));
  await loadLobby();
}

async function createMatch(spectate) {
  const body = {
    bots: Number($("opt-bots").value),
    market: $("opt-market").checked,
    spectate,
  };
  const seed = $("opt-seed").value.trim();
  if (seed !== "") {
    body.seed = Number(seed);
  }
  const data = await request("POST", "/api/matches", body);
  setMatch(data.state);
}

function setMatch(state) {
  view.match = state;
  view.selection = null;
  closeDialog();
  if (state.spectator) {
    renderSpectate();
    return;
  }
  renderGame();
  if (state.phase === "finished") {
    showFinished();
  } else {
    offerAugment();
  }
}

/* The match: top of the table ----------------------------------------------- */

function roundText(state) {
  const arena = state.mode === "market" ? `market pack ${state.pack}` : "power mode";
  if (!state.round) {
    return state.phase === "finished" ? `Match over, ${arena}` : arena;
  }
  const round = state.round;
  const parts = [`Round ${round.label}`, round.pve ? "against the Market" : "player fight"];
  if (round.carousel) {
    parts.push("carousel");
  }
  if (round.augment) {
    parts.push("augment");
  }
  parts.push(arena);
  return parts.join(", ");
}

function renderStage(state) {
  const list = clear($("stage"));
  for (const round of state.stage) {
    const kind = roundKind(round);
    const marks = [el("span", { class: "round-icon" }, [icon(kind)])];
    if (round.augment) {
      marks.push(el("span", { class: "round-gem" }, [icon("augment")]));
    }
    marks.push(el("span", { class: "round-label", text: round.label }));
    const title = `Round ${round.label}: ${ROUND_NAMES[kind]}${round.augment ? ", augment" : ""}`;
    const current = round.state === "current" ? "step" : null;
    list.append(el("li", { class: `round ${round.state} ${kind}`, title, "aria-current": current }, marks));
  }
  $("phase").textContent =
    state.phase === "finished" ? "The match is over" : "Planning: buy, place, then fight";
}

function renderTape(state) {
  const node = clear($("tape"));
  const summary = state.last && state.last.summary;
  const moves = summary ? summary.origin_moves : [];
  if (moves.length === 0) {
    const text =
      state.mode === "market"
        ? "Every fight is decided on a slice of real market history."
        : "Power mode: the stronger board wins.";
    node.append(el("span", { class: "muted", text }));
    return;
  }
  node.append(el("span", { class: "tape-label", text: "Last slice" }));
  node.append(...moves.map(([origin, move]) => moveChip(origin, move)));
}

function actionLabel(node, glyph, text, cost) {
  clear(node).append(glyphSlot(icon(glyph)), el("span", { class: "action-text", text }), coins(cost));
}

function renderHud(state) {
  const { seat, costs } = state;
  $("hp-fill").style.setProperty("--amount", `${percent(seat.health, seat.max_health)}%`);
  $("hp-text").textContent = String(seat.health);
  $("gold").textContent = String(seat.gold);
  const lit = interestPips(seat.gold);
  const pips = [0, 1, 2, 3, 4].map((pip) => el("span", { class: `pip${pip < lit ? " lit" : ""}` }));
  clear($("interest")).append(...pips);
  const income = seat.income;
  $("income").textContent = `+${income.total} next round`;
  $("income").title = `${income.base} base, ${income.interest} interest, ${income.streak} streak bonus`;
  $("level").textContent = String(seat.level);
  const xpShare = seat.xp_needed ? percent(seat.xp, seat.xp_needed) : 100;
  $("xp-fill").style.setProperty("--amount", `${xpShare}%`);
  $("xp-text").textContent = seat.xp_needed ? `${seat.xp}/${seat.xp_needed} xp` : "max level";
  $("streak").textContent = streakText(seat.streak);
  actionLabel($("btn-xp"), "xp", "Buy XP", costs.xp);
  actionLabel($("btn-reroll"), "reroll", "Reroll", costs.reroll);
  $("odds").textContent = `Shop odds by cost: ${oddsText(seat.odds)}`;
}

function seatRow(seat) {
  const body = [
    el("span", { class: "avatar", text: seat.name.slice(0, 1).toUpperCase() }),
    el("span", { class: "rival-main" }, [
      el("span", { class: "rival-top" }, [
        el("strong", { text: seat.me ? "You" : seat.name }),
        el("span", { class: "muted", text: `Lv ${seat.level}` }),
      ]),
      healthBar(seat),
    ]),
    el("strong", { class: "rival-hp", text: String(seat.health) }),
  ];
  const classes = `rival${seat.alive ? "" : " out"}${seat.me ? " me" : ""}`;
  if (seat.me) {
    return el("div", { class: classes }, body);
  }
  const label = `Scout ${seat.name}: ${seat.health} health, level ${seat.level}`;
  return el("button", { type: "button", class: classes, "aria-label": label, onclick: () => showScout(seat) }, body);
}

function renderRivals(state) {
  clear($("rivals")).append(...standings(state.seat, state.others).map(seatRow));
}

/* The match: board, bench and shop ------------------------------------------ */

function cellButton(state, row, col) {
  const { seat, board } = state;
  const unit = unitAt(seat.board, row, col);
  const effect = cellEffect(board, seat.board, row, col);
  const who = unit ? `${unit.name}, ${unit.star} star` : "Empty cell";
  const label = `${who}, row ${row}, column ${col}: ${effect}`;
  const classes = ["hex"];
  if (unit) {
    classes.push("occupied");
    const backHalf = row >= Math.floor(board.rows / 2);
    if (backHalf && !isCovered(seat.board, row, col)) {
      classes.push("exposed");
    }
  }
  if (isSelectedUnit(unit)) {
    classes.push("selected");
  }
  const props = {
    type: "button",
    class: classes.join(" "),
    "aria-label": label,
    title: label,
    data: { row, col },
    onclick: () => clickTarget({ type: "cell", row, col, unit: unit ? unit.index : null }),
  };
  return hexCell("button", props, unit ? token(unit, view.recipes) : null);
}

function renderBoard(state) {
  const { seat, board } = state;
  const node = clear($("board"));
  node.classList.toggle("targeting", Boolean(view.selection && view.selection.type === "unit"));
  node.append(...hexGrid(board, (row, col) => cellButton(state, row, col)));
  $("board-count").textContent = `${seat.board.length}/${seat.board_limit}`;
  $("board-legend").textContent =
    `Front row at the top. Size by row: ${board.row_size.join(" / ")}%. ` +
    `A back unit with nobody in front of it pays ${board.exposed}% more for drawdowns.`;
}

function renderBench(state) {
  const node = clear($("bench"));
  for (let slot = 0; slot < state.bench_size; slot += 1) {
    const unit = state.seat.bench[slot] || null;
    const classes = ["slot"];
    if (unit) {
      classes.push("occupied");
    }
    if (isSelectedUnit(unit)) {
      classes.push("selected");
    }
    const label = unit ? `${unit.name}, ${unit.star} star, on the bench` : "Empty bench slot";
    node.append(
      el(
        "button",
        {
          type: "button",
          class: classes.join(" "),
          "aria-label": label,
          title: label,
          onclick: () => clickTarget({ type: "bench", unit: unit ? unit.index : null }),
        },
        unit ? [token(unit, view.recipes)] : [],
      ),
    );
  }
}

function shopCard(offer, slot) {
  if (!offer) {
    return el("button", { type: "button", class: "card empty", disabled: true, "aria-label": "Sold" });
  }
  return el(
    "button",
    {
      type: "button",
      class: `card${offer.affordable ? "" : " poor"}`,
      data: { origin: offer.origin, cost: offer.cost },
      "aria-label": `Buy ${offer.name} for ${offer.cost} gold`,
      onclick: () => act("buy", [slot]),
    },
    [
      el("span", { class: "card-art" }, [portrait(offer.name)]),
      el("span", { class: "card-traits" }, [traitChip(offer.origin), traitChip(offer.role)]),
      el("span", { class: "card-foot" }, [
        el("span", { class: "card-name", text: offer.name }),
        el("span", { class: "card-cost" }, [coins(offer.cost)]),
      ]),
    ],
  );
}

function renderShop(state) {
  clear($("shop")).append(...state.seat.shop.map(shopCard));
}

/* The match: rails ---------------------------------------------------------- */

function traitRow(trait) {
  const steps = traitSteps(trait).map((step) =>
    el("span", { class: `step${step.reached ? " reached" : ""}`, text: String(step.needed) }),
  );
  const parts = [
    el("span", { class: "trait-badge" }, [traitGlyph(trait.name)]),
    el("span", { class: "trait-count", text: String(trait.count) }),
    el("span", { class: "trait-main" }, [
      el("span", { class: "trait-name", text: trait.name }),
      el("span", { class: "trait-steps" }, steps),
    ]),
  ];
  if (trait.tier > 0) {
    parts.push(el("span", { class: "pos trait-bonus", text: `+${trait.bonus}%` }));
  }
  const classes = `trait${trait.tier > 0 ? " active" : ""}`;
  return el("li", { class: classes, title: trait.summary, data: { tier: trait.tier } }, parts);
}

function renderTraits(seat) {
  const list = clear($("traits"));
  if (seat.traits.length === 0) {
    list.append(el("li", { class: "muted", text: "Field units that share a market or a style." }));
    return;
  }
  list.append(...seat.traits.map(traitRow));
}

function renderInventory(seat) {
  const components = clear($("components"));
  seat.components.forEach((name, index) => {
    const entry = fromCatalog("components", name);
    components.append(
      itemTile([name], {
        class: isSelected("component", index) ? "selected" : "",
        title: `${name}: ${entry ? entry.effect : ""}`,
        "aria-label": `Component ${name}`,
        onclick: () => clickTarget({ type: "component", index }),
      }),
    );
  });
  const items = clear($("items"));
  seat.items.forEach((item, index) => {
    items.append(
      itemTile(item.components, {
        class: isSelected("item", index) ? "selected" : "",
        title: `${item.name}: ${item.effect}`,
        "aria-label": `Item ${item.name}: ${item.effect}`,
        onclick: () => clickTarget({ type: "item", index }),
      }),
    );
  });
  $("items-empty").hidden = seat.components.length + seat.items.length > 0;
}

function renderAugments(seat) {
  const list = clear($("augments"));
  if (seat.offer.length > 0) {
    list.append(el("li", {}, [button("Choose your augment", offerAugment, { class: "primary" })]));
  }
  for (const augment of seat.augments) {
    list.append(
      el("li", { class: "augment", data: { tier: augment.tier }, title: augment.text }, [
        glyphSlot(icon("augment")),
        el("span", {}, [el("strong", { text: augment.name }), el("span", { class: "muted", text: ` ${augment.text}` })]),
      ]),
    );
  }
  if (seat.offer.length + seat.augments.length === 0) {
    list.append(el("li", { class: "muted", text: "Augments are offered at rounds 2-1, 3-2 and 4-2." }));
  }
}

function unitDetail(state, unit) {
  const champion = fromCatalog("champions", unit.name);
  const strategy = (view.catalog && view.catalog.strategies[unit.role]) || "";
  const head = el("span", { class: "detail-head", data: { origin: unit.origin, cost: unit.cost } }, [
    el("span", { class: "disc" }, [portrait(unit.name)]),
    el("span", { class: "detail-title" }, [
      el("strong", { text: `${unit.name} ${STAR.repeat(unit.star)}` }),
      el("span", { class: "detail-traits" }, [traitChip(unit.origin), traitChip(unit.role), coins(unit.cost)]),
    ]),
  ]);
  const lines = [head, el("span", { text: strategy })];
  if (champion) {
    lines.push(el("span", { class: "muted", text: `${champion.ability}: ${champion.text}` }));
  }
  if (unit.cell) {
    const effect = cellEffect(state.board, state.seat.board, unit.cell[0], unit.cell[1]);
    const ticker = unit.symbol ? `Trades ${unit.symbol}. ` : "";
    lines.push(el("span", { text: `${ticker}This cell: ${effect}.` }));
  }
  for (const item of unit.items) {
    lines.push(el("span", { class: "muted", text: `${item.name}: ${item.effect}` }));
  }
  const actions = [button(`Sell (+${unit.sell} gold)`, () => act("sell", [unit.index]))];
  if (unit.cell) {
    actions.push(button("Bench", () => act("bench", [unit.index])));
  }
  lines.push(el("span", { class: "row" }, actions));
  return lines;
}

function renderDetail(state) {
  const node = clear($("detail"));
  const selection = view.selection;
  if (!selection) {
    node.append(el("span", { class: "muted", text: HINT }));
    return;
  }
  if (selection.type === "unit") {
    const units = [...state.seat.board, ...state.seat.bench];
    const unit = units.find((candidate) => candidate.index === selection.index);
    if (unit) {
      node.append(...unitDetail(state, unit));
    }
    return;
  }
  if (selection.type === "component") {
    const name = state.seat.components[selection.index];
    const entry = fromCatalog("components", name);
    node.append(
      el("strong", { text: name }),
      el("span", { text: entry ? entry.effect : "" }),
      el("span", { class: "muted", text: "Click another component to craft an item." }),
    );
    return;
  }
  const item = state.seat.items[selection.index];
  node.append(
    el("strong", { text: item.name }),
    el("span", { text: item.effect }),
    el("span", { class: "muted", text: "Click a unit to equip it." }),
  );
}

function renderGame() {
  const state = view.match;
  show("game");
  setRoundInfo(roundText(state));
  renderStage(state);
  renderTape(state);
  renderHud(state);
  renderRivals(state);
  renderBoard(state);
  renderBench(state);
  renderShop(state);
  renderTraits(state.seat);
  renderInventory(state.seat);
  renderAugments(state.seat);
  renderDetail(state);
}

function act(kind, args = []) {
  if (view.skipScene) {
    return Promise.resolve();
  }
  return guarded(async () => {
    try {
      const data = await request("POST", matchPath(view.match.id, "/actions"), { kind, args });
      view.match = data.state;
      toast(data.message);
    } finally {
      view.selection = null;
      renderGame();
    }
  });
}

function clickTarget(target) {
  if (view.busy || view.skipScene) {
    return Promise.resolve();
  }
  const step = nextStep(view.selection, target);
  if (step.kind === "action") {
    return act(step.action.kind, step.action.args);
  }
  if (step.kind === "select") {
    view.selection = step.selection;
  } else if (step.kind === "clear") {
    view.selection = null;
  } else {
    return Promise.resolve();
  }
  renderGame();
  return Promise.resolve();
}

/* Round results ------------------------------------------------------------ */

function tradeRow(line, withChart) {
  const result = resultTone(line);
  const resultClass = { up: "pos", down: "neg", out: "neg" }[result] || "";
  const cells = [el("td", { text: line.unit }), el("td", { class: "ticker", text: line.symbol })];
  if (withChart) {
    cells.push(el("td", {}, [sparkSvg(line, SPARK_WIDTH, SPARK_HEIGHT)]));
  }
  cells.push(
    el("td", { class: tone(line.pnl), text: signed(line.pnl) }),
    el("td", { text: `${line.drawdown.toFixed(1)}%` }),
    el("td", { text: String(line.trades) }),
    el("td", { text: line.size.toFixed(2) }),
    el("td", { class: resultClass, text: resultLabel(line) }),
    el("td", { class: "score", text: line.score.toFixed(2) }),
  );
  return el("tr", {}, cells);
}

function tradesTable(units, kind) {
  const withChart = kind === "trades";
  const head = ["Unit", "Ticker", "P&L", "Drawdown", "Trades", "Size", "Result", "Score"];
  if (withChart) {
    head.splice(2, 0, "Slice");
  }
  return el("div", { class: "table-wrap" }, [
    el("table", { class: `ledger ${kind}` }, [
      el("thead", {}, [el("tr", {}, head.map((text) => el("th", { scope: "col", text })))]),
      el(
        "tbody",
        {},
        units.map((line) => tradeRow(line, withChart)),
      ),
    ]),
  ]);
}

function fightsList(report) {
  const items = report.fights.map((fight) => el("li", { text: fightText(fight) }));
  if (report.eliminated.length > 0) {
    items.push(el("li", { class: "neg", text: `Eliminated: ${report.eliminated.join(", ")}` }));
  }
  return el("ul", { class: "fights" }, items);
}

function boardsOf(summary) {
  const parts = [];
  if (summary.units.length > 0) {
    parts.push(tradesTable(summary.units, "trades"));
  }
  if (summary.units.length + summary.opponent_units.length > 0) {
    const scores = `${summary.score.toFixed(2)} against ${summary.opponent_score.toFixed(2)}`;
    const how =
      "A unit's score is its size after the trade: a good trade grows it, a bad one shrinks it.";
    parts.push(el("p", { class: "muted", text: `Board score ${scores}. ${how}` }));
  }
  if (summary.opponent_units.length > 0) {
    const label = `${summary.opponent || "The other board"}: ${summary.opponent_units.length} unit(s)`;
    parts.push(
      el("details", { class: "other-board" }, [
        el("summary", { text: label }),
        tradesTable(summary.opponent_units, "theirs"),
      ]),
    );
  }
  return parts;
}

function resultBody(summary, report) {
  const where = summary.slice_label ? `, market slice ${summary.slice_label}` : "";
  const body = [el("p", { class: "muted", text: `Round ${summary.round_label}${where}` })];
  if (summary.origin_moves.length > 0) {
    const chips = summary.origin_moves.map(([origin, move]) => moveChip(origin, move));
    body.push(el("div", { class: "moves" }, chips));
  }
  body.push(...boardsOf(summary));
  body.push(el("h2", { text: "What this round teaches" }));
  if (summary.lessons.length === 0) {
    body.push(el("p", { class: "muted", text: "Nothing stood out this round. Keep going." }));
  } else {
    const lessons = summary.lessons.map((text) => el("p", { class: "lesson", text }));
    body.push(el("div", { class: "lessons" }, lessons));
  }
  body.push(el("h2", { text: "All fights" }), fightsList(report));
  return body;
}

function showResult() {
  const state = view.match;
  const { summary, report } = state.last;
  if (!summary || !report) {
    return;
  }
  const finished = state.phase === "finished";
  const next = finished
    ? button("Final placements", showFinished, { class: "primary" })
    : button("Next round", () => {
        closeDialog();
        offerAugment();
      }, { class: "primary" });
  openDialog(headline(summary), resultBody(summary, report), [next], summary.outcome);
}

function wantsMotion() {
  return !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function afterFight() {
  view.skipScene = null;
  renderGame();
  showResult();
}

/** Show the round that was just fought: the scene when there is something to see, then the result. */
function showFight(state) {
  const summary = state.last.summary;
  const fighters = summary ? summary.units.length + summary.opponent_units.length : 0;
  if (fighters === 0 || !wantsMotion()) {
    afterFight();
    return;
  }
  const stage = {
    root: $("theatre"),
    floor: $("scene-floor"),
    mine: $("scene-mine"),
    enemy: $("scene-enemy"),
    banner: $("banner"),
  };
  const versus = summary.opponent ? `You against ${summary.opponent}` : "Your board";
  const where = summary.slice_label ? `, trading ${summary.slice_label}` : "";
  $("scene-caption").textContent = `Round ${summary.round_label}: ${versus}${where}`;
  view.skipScene = playFight(stage, summary, state.board, view.recipes, afterFight);
}

function fight() {
  if (view.skipScene) {
    return Promise.resolve();
  }
  return guarded(async () => {
    const data = await request("POST", matchPath(view.match.id, "/ready"));
    view.match = data.state;
    view.selection = null;
    showFight(data.state);
  });
}

function preview() {
  return guarded(async () => {
    const data = await request("GET", matchPath(view.match.id, "/preview"));
    const rows = data.odds.map((entry) =>
      el("li", { class: "place" }, [
        el("span", { text: entry.name }),
        el("strong", { text: `${Math.round(entry.probability * 100)}%` }),
      ]),
    );
    const note =
      "Share of replayed market slices on which your board beats each board as it stands. " +
      "A simulation of the past, never a promise.";
    openDialog(
      "Odds on replayed market slices",
      [el("p", { class: "muted", text: note }), el("ul", { class: "places" }, rows)],
      [button("Close", closeDialog)],
    );
  });
}

function offerAugment() {
  const state = view.match;
  if (!state.seat || state.seat.offer.length === 0 || state.phase === "finished") {
    return;
  }
  const cards = state.seat.offer.map((augment, index) =>
    el(
      "button",
      {
        type: "button",
        class: "offer",
        data: { tier: augment.tier },
        onclick: () => {
          closeDialog();
          act("augment", [index]);
        },
      },
      [
        glyphSlot(icon("augment"), "offer-gem"),
        el("strong", { text: augment.name }),
        el("span", { class: "muted", text: augment.tier }),
        el("span", { text: augment.text }),
      ],
    ),
  );
  openDialog(
    "Choose an augment",
    [el("div", { class: "offers" }, cards)],
    [button("Decide later", closeDialog)],
  );
}

function showScout(rival) {
  const state = view.match;
  const status = rival.alive ? `${rival.health} health` : "eliminated";
  openDialog(
    `${rival.name}: ${status}, level ${rival.level}, ${rival.gold} gold`,
    [miniBoard(rival.board, state.board), el("p", { class: "muted", text: traitText(rival.traits) })],
    [button("Close", closeDialog)],
  );
}

async function downloadReplay() {
  const data = await request("GET", matchPath(view.match.id, "/replay"));
  const blob = new Blob([JSON.stringify(data.replay, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = el("a", { href: url, download: `tft-replay-seed-${data.replay.seed}.json` });
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function showFinished() {
  const state = view.match;
  const everyone = state.seat ? [state.seat, ...state.others] : state.others;
  const rows = state.placements.map((name, index) => {
    const seat = everyone.find((candidate) => candidate.name === name);
    const mine = Boolean(state.seat && state.seat.name === name);
    return el("li", { class: `place${mine ? " me" : ""}` }, [
      el("span", { text: `${ordinal(index + 1)}  ${name}` }),
      el("span", { class: "muted", text: seat ? `${seat.health} health, level ${seat.level}` : "" }),
    ]);
  });
  const place = state.seat ? state.placements.indexOf(state.seat.name) + 1 : 0;
  const title = place > 0 ? `Match over: you placed ${ordinal(place)}` : "Match over";
  const actions = [];
  if (state.has_seat && !state.spectator) {
    actions.push(button("Download replay", () => guarded(downloadReplay)));
  }
  actions.push(button("Back to the lobby", () => guarded(loadLobby), { class: "primary" }));
  openDialog(title, [el("ol", { class: "places" }, rows)], actions);
}

/* Spectating --------------------------------------------------------------- */

function seatCard(seat, board) {
  const facts = `${seat.health} health, level ${seat.level}, ${seat.gold} gold, ${streakText(seat.streak)}`;
  return el("div", { class: `panel seat-card${seat.alive ? "" : " out"}` }, [
    el("div", { class: "section-head" }, [
      el("strong", { text: seat.name }),
      el("span", { class: "muted", text: facts }),
    ]),
    healthBar(seat),
    miniBoard(seat.board, board),
    el("p", { class: "muted", text: traitText(seat.traits) }),
  ]);
}

function renderSpectate() {
  const state = view.match;
  show("spectate");
  setRoundInfo(roundText(state));
  const finished = state.phase === "finished";
  $("spectate-title").textContent = finished
    ? `Match over: ${state.placements[0]} won`
    : `Spectating, ${state.rounds_played} round(s) played`;
  const steppable = !state.has_seat && !finished;
  $("btn-step").hidden = !steppable;
  $("btn-auto").hidden = !steppable;
  $("btn-auto").setAttribute("aria-pressed", String(view.auto));
  clear($("seats")).append(...state.others.map((seat) => seatCard(seat, state.board)));
  const fights = clear($("spectate-fights"));
  const report = state.last.report;
  if (report) {
    fights.append(el("li", { class: "muted", text: `Round ${report.round}` }), fightsList(report));
  } else {
    fights.append(el("li", { class: "muted", text: "No round played yet." }));
  }
}

async function stepOnce() {
  const data = await request("POST", matchPath(view.match.id, "/step"));
  view.match = data.state;
  renderSpectate();
}

function autoLoop() {
  if (!view.auto || !view.match || view.match.phase === "finished") {
    view.auto = false;
    $("btn-auto").setAttribute("aria-pressed", "false");
    return;
  }
  guarded(stepOnce).then(() => window.setTimeout(autoLoop, AUTO_DELAY_MS));
}

function toggleAuto() {
  view.auto = !view.auto;
  $("btn-auto").setAttribute("aria-pressed", String(view.auto));
  if (view.auto) {
    autoLoop();
  }
}

/* Wiring ------------------------------------------------------------------- */

function onEscape() {
  if (!$("overlay").hidden) {
    closeDialog();
  } else if (view.selection) {
    view.selection = null;
    renderGame();
  }
}

/** D rerolls, F buys experience, E sells the selected unit: the genre's usual keys. */
function onShortcut(key) {
  if (key === "d") {
    act("reroll");
  } else if (key === "f") {
    act("xp");
  } else if (key === "e" && view.selection && view.selection.type === "unit") {
    act("sell", [view.selection.index]);
  }
}

function onKey(event) {
  if (view.skipScene) {
    if (["Escape", "Enter", " "].includes(event.key)) {
      event.preventDefault();
      endScene();
    }
    return;
  }
  if (event.key === "Escape") {
    onEscape();
    return;
  }
  const typing = ["INPUT", "TEXTAREA", "SELECT"].includes(event.target.tagName);
  const inGame = !$("game").hidden && $("overlay").hidden;
  if (inGame && !typing && !event.ctrlKey && !event.metaKey) {
    onShortcut(event.key.toLowerCase());
  }
}

function wire() {
  $("new-match").addEventListener("submit", (event) => {
    event.preventDefault();
    guarded(() => createMatch(false));
  });
  $("btn-watch").addEventListener("click", () => guarded(() => createMatch(true)));
  $("opt-bots").addEventListener("input", () => {
    $("opt-bots-out").textContent = $("opt-bots").value;
  });
  $("nav-lobby").addEventListener("click", () => guarded(loadLobby));
  $("btn-xp").addEventListener("click", () => act("xp"));
  $("btn-reroll").addEventListener("click", () => act("reroll"));
  $("btn-fight").addEventListener("click", fight);
  $("btn-preview").addEventListener("click", preview);
  $("btn-step").addEventListener("click", () => guarded(stepOnce));
  $("btn-auto").addEventListener("click", toggleAuto);
  $("btn-refresh").addEventListener("click", () => guarded(() => openMatch(view.match.id, true)));
  document.addEventListener("keydown", onKey);
}

async function start() {
  wire();
  decorate(document);
  await guarded(async () => {
    view.catalog = await request("GET", "/api/catalog");
    view.recipes = recipesOf(view.catalog);
    document.title = view.catalog.name;
    $("brand").textContent = view.catalog.name;
    renderShowcase();
    await loadLobby();
  });
}

start();
