/**
 * The browser client: draws the match the server describes and sends the player's actions.
 * All game logic lives on the server; the pure helpers live in logic.js.
 */
import {
  cellEffect,
  fightText,
  headline,
  hexRows,
  initials,
  interestPips,
  isCovered,
  nextStep,
  oddsText,
  ordinal,
  percent,
  signed,
  sparkline,
  streakText,
  unitAt,
} from "./logic.js";

const SVG_NS = "http://www.w3.org/2000/svg";
const AUTO_DELAY_MS = 1200;
const TOAST_MS = 3200;
const SPARK_WIDTH = 120;
const SPARK_HEIGHT = 32;
const HINT =
  "Click a unit, then a cell to place it. Click two components to craft an item, " +
  "then the item and a unit to equip it.";

const view = { match: null, catalog: null, selection: null, auto: false, busy: false, timer: null };

const $ = (id) => document.getElementById(id);

/** Create an element; `props` sets class, text, data, listeners (onclick...) and attributes. */
function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (value === null || value === undefined || value === false) {
      continue;
    }
    if (key === "class") {
      node.className = value;
    } else if (key === "text") {
      node.textContent = value;
    } else if (key === "data") {
      Object.assign(node.dataset, value);
    } else if (key.startsWith("on")) {
      node.addEventListener(key.slice(2), value);
    } else {
      node.setAttribute(key, value === true ? "" : String(value));
    }
  }
  for (const child of [].concat(children)) {
    if (child) {
      node.append(child);
    }
  }
  return node;
}

function clear(node) {
  node.replaceChildren();
  return node;
}

function button(text, onclick, extra = {}) {
  return el("button", { type: "button", text, onclick, ...extra });
}

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
  let data = null;
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

/* Units -------------------------------------------------------------------- */

function unitTile(unit) {
  const meta = [el("span", { class: "stars", text: "★".repeat(unit.star) })];
  if (unit.symbol) {
    meta.push(document.createTextNode(` ${unit.symbol}`));
  }
  return el("span", { class: "unit" }, [
    el("span", { class: "unit-initials", text: initials(unit.name) }),
    el("span", { class: "unit-name", text: unit.name }),
    el("span", { class: "unit-meta" }, meta),
    el(
      "span",
      { class: "unit-items" },
      unit.items.map(() => el("span", { class: "item-dot" })),
    ),
  ]);
}

function isSelectedUnit(unit) {
  const selection = view.selection;
  return Boolean(unit && selection && selection.type === "unit" && selection.index === unit.index);
}

function miniBoard(units, board) {
  const node = el("div", { class: "board mini" });
  for (const line of hexRows(board.rows, board.cols)) {
    const rowNode = el("div", { class: `hex-row${line.shifted ? " shifted" : ""}` });
    for (const { row, col } of line.cells) {
      const unit = unitAt(units, row, col);
      const cell = el("span", { class: `hex${unit ? " occupied" : ""}` });
      if (unit) {
        cell.dataset.origin = unit.origin;
        cell.dataset.cost = unit.cost;
        cell.title = `${unit.name} ${"★".repeat(unit.star)}`;
        cell.append(unitTile(unit));
      }
      rowNode.append(cell);
    }
    node.append(rowNode);
  }
  return node;
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

async function loadLobby() {
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

/* The match ---------------------------------------------------------------- */

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

function renderHud(seat) {
  $("hp-fill").style.setProperty("--amount", `${percent(seat.health, seat.max_health)}%`);
  $("hp-text").textContent = String(seat.health);
  $("gold").textContent = String(seat.gold);
  const lit = interestPips(seat.gold);
  const pips = [0, 1, 2, 3, 4].map((pip) => el("span", { class: `pip${pip < lit ? " lit" : ""}` }));
  clear($("interest")).append(...pips);
  const income = seat.income;
  $("income").textContent = `+${income.total} next round`;
  $("income").title =
    `${income.base} base, ${income.interest} interest, ${income.streak} streak bonus`;
  $("level").textContent = String(seat.level);
  const xpShare = seat.xp_needed ? percent(seat.xp, seat.xp_needed) : 100;
  $("xp-fill").style.setProperty("--amount", `${xpShare}%`);
  $("xp-text").textContent = seat.xp_needed ? `${seat.xp}/${seat.xp_needed} xp` : "max level";
  $("streak").textContent = streakText(seat.streak);
}

function renderRivals(state) {
  const node = clear($("rivals"));
  for (const rival of state.others) {
    const fill = el("span", { class: "fill hp" });
    fill.style.setProperty("--amount", `${percent(rival.health, rival.max_health)}%`);
    node.append(
      el(
        "button",
        {
          type: "button",
          class: `rival${rival.alive ? "" : " out"}`,
          "aria-label": `Scout ${rival.name}: ${rival.health} health, level ${rival.level}`,
          onclick: () => showScout(rival),
        },
        [
          el("span", { class: "rival-top" }, [
            el("strong", { text: rival.name }),
            el("span", { class: "muted", text: `Lv ${rival.level}` }),
          ]),
          el("span", { class: "bar" }, [fill]),
        ],
      ),
    );
  }
}

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
  const node = el("button", {
    type: "button",
    class: classes.join(" "),
    "aria-label": label,
    title: label,
    data: { row, col },
    onclick: () => clickTarget({ type: "cell", row, col, unit: unit ? unit.index : null }),
  });
  if (unit) {
    node.dataset.origin = unit.origin;
    node.dataset.cost = unit.cost;
    node.append(unitTile(unit));
  }
  return node;
}

function renderBoard(state) {
  const { seat, board } = state;
  const node = clear($("board"));
  const placing = Boolean(view.selection && view.selection.type === "unit");
  node.classList.toggle("targeting", placing);
  for (const line of hexRows(board.rows, board.cols)) {
    const rowNode = el("div", { class: `hex-row${line.shifted ? " shifted" : ""}` });
    for (const { row, col } of line.cells) {
      rowNode.append(cellButton(state, row, col));
    }
    node.append(rowNode);
  }
  $("board-count").textContent = `${seat.board.length}/${seat.board_limit}`;
  $("board-legend").textContent =
    `Front row on top. Position size by row: ${board.row_size.join(" / ")}%. ` +
    "A back unit needs a unit in front of it in its column.";
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
    const slotNode = el("button", {
      type: "button",
      class: classes.join(" "),
      "aria-label": label,
      title: label,
      onclick: () => clickTarget({ type: "bench", unit: unit ? unit.index : null }),
    });
    if (unit) {
      slotNode.dataset.origin = unit.origin;
      slotNode.dataset.cost = unit.cost;
      slotNode.append(unitTile(unit));
    }
    node.append(slotNode);
  }
}

function renderShop(state) {
  const { seat, costs } = state;
  const node = clear($("shop"));
  seat.shop.forEach((offer, slot) => {
    if (!offer) {
      node.append(
        el("button", { type: "button", class: "card empty", disabled: true, "aria-label": "Sold" }),
      );
      return;
    }
    node.append(
      el(
        "button",
        {
          type: "button",
          class: `card${offer.affordable ? "" : " poor"}`,
          data: { origin: offer.origin, cost: offer.cost },
          "aria-label": `Buy ${offer.name} for ${offer.cost} gold`,
          onclick: () => act("buy", [slot]),
        },
        [
          el("span", { class: "card-name", text: offer.name }),
          el("span", { class: "card-sub", text: `${offer.origin}, ${offer.role}` }),
          el("span", { class: "card-cost", text: `${offer.cost} gold` }),
        ],
      ),
    );
  });
  $("btn-xp").textContent = `Buy XP (${costs.xp} gold)`;
  $("btn-reroll").textContent = `Reroll (${costs.reroll} gold)`;
  $("odds").textContent = `Shop odds by cost: ${oddsText(seat.odds)}`;
}

function renderTraits(seat) {
  const list = clear($("traits"));
  if (seat.traits.length === 0) {
    list.append(el("li", { class: "muted", text: "Field units that share a market or a style." }));
  }
  const progress = (trait) => {
    const next = trait.breakpoints.find((needed) => needed > trait.count);
    return next ? `${trait.name} ${trait.count}/${next}` : `${trait.name} ${trait.count}`;
  };
  for (const trait of seat.traits.filter((one) => one.tier > 0)) {
    list.append(
      el("li", { class: "trait active", title: trait.summary }, [
        el("span", { text: progress(trait) }),
        el("span", { class: "pos", text: `+${trait.bonus}%` }),
      ]),
    );
  }
  const waiting = seat.traits.filter((one) => one.tier === 0).map(progress);
  if (waiting.length > 0) {
    list.append(el("li", { class: "muted trait-rest", text: `Not active yet: ${waiting.join(", ")}` }));
  }
}

function isSelected(type, index) {
  const selection = view.selection;
  return Boolean(selection && selection.type === type && selection.index === index);
}

function renderInventory(seat) {
  const components = clear($("components"));
  seat.components.forEach((name, index) => {
    components.append(
      button(name, () => clickTarget({ type: "component", index }), {
        class: `pill${isSelected("component", index) ? " selected" : ""}`,
        "aria-label": `Component ${name}`,
      }),
    );
  });
  const items = clear($("items"));
  seat.items.forEach((item, index) => {
    items.append(
      button(item.name, () => clickTarget({ type: "item", index }), {
        class: `pill item${isSelected("item", index) ? " selected" : ""}`,
        title: item.effect,
        "aria-label": `Item ${item.name}: ${item.effect}`,
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
    list.append(el("li", { class: "trait", text: `${augment.name}: ${augment.text}` }));
  }
  if (seat.offer.length + seat.augments.length === 0) {
    list.append(el("li", { class: "muted", text: "Augments are offered at rounds 2-1, 3-2 and 4-2." }));
  }
}

function fromCatalog(kind, name) {
  const entries = (view.catalog && view.catalog[kind]) || [];
  return entries.find((entry) => entry.name === name) || null;
}

function unitDetail(state, unit) {
  const champion = fromCatalog("champions", unit.name);
  const strategy = (view.catalog && view.catalog.strategies[unit.role]) || "";
  const lines = [
    el("strong", { text: `${unit.name} ${"★".repeat(unit.star)}` }),
    el("span", { class: "muted", text: `${unit.cost}-cost, ${unit.origin}, ${unit.role}` }),
    el("span", { text: strategy }),
  ];
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
  renderHud(state.seat);
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

function sparkSvg(line) {
  const { points, coords } = sparkline(line.closes, SPARK_WIDTH, SPARK_HEIGHT);
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("class", "spark");
  svg.setAttribute("viewBox", `0 0 ${SPARK_WIDTH} ${SPARK_HEIGHT}`);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", `${line.symbol} over the slice`);
  const path = document.createElementNS(SVG_NS, "polyline");
  path.setAttribute("class", "spark-line");
  path.setAttribute("points", points);
  svg.append(path);
  for (const [bar, what] of line.marks) {
    const point = coords[bar];
    if (!point) {
      continue;
    }
    const dot = document.createElementNS(SVG_NS, "circle");
    dot.setAttribute("class", `mark-${what}`);
    dot.setAttribute("cx", String(point[0]));
    dot.setAttribute("cy", String(point[1]));
    dot.setAttribute("r", "3");
    const title = document.createElementNS(SVG_NS, "title");
    title.textContent = `${what} on day ${bar + 1}`;
    dot.append(title);
    svg.append(dot);
  }
  return svg;
}

function tone(value) {
  if (value > 0) {
    return "pos";
  }
  return value < 0 ? "neg" : "";
}

function tradesTable(units) {
  const head = ["Unit", "Ticker", "Slice", "P&L", "Drawdown", "Trades", "Score"];
  const rows = units.map((line) =>
    el("tr", {}, [
      el("td", { text: line.unit }),
      el("td", { text: line.symbol }),
      el("td", {}, [sparkSvg(line)]),
      el("td", { class: tone(line.pnl), text: signed(line.pnl) }),
      el("td", { text: `${line.drawdown.toFixed(1)}%` }),
      el("td", { text: String(line.trades) }),
      el("td", { class: tone(line.score), text: line.score.toFixed(1) }),
    ]),
  );
  return el("div", { class: "table-wrap" }, [
    el("table", { class: "trades" }, [
      el("thead", {}, [el("tr", {}, head.map((text) => el("th", { scope: "col", text })))]),
      el("tbody", {}, rows),
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

function resultBody(summary, report) {
  const where = summary.slice_label ? `, market slice ${summary.slice_label}` : "";
  const body = [el("p", { class: "muted", text: `Round ${summary.round_label}${where}` })];
  if (summary.origin_moves.length > 0) {
    const chips = summary.origin_moves.map(([origin, move]) =>
      el("span", { class: "move", data: { origin } }, [
        document.createTextNode(`${origin} `),
        el("span", { class: tone(move), text: signed(move) }),
      ]),
    );
    body.push(el("div", { class: "moves" }, chips));
  }
  if (summary.units.length > 0) {
    body.push(tradesTable(summary.units));
    const scores = `${summary.score.toFixed(1)} against ${summary.opponent_score.toFixed(1)}`;
    body.push(el("p", { class: "muted", text: `Board score ${scores}` }));
  }
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

function fight() {
  return guarded(async () => {
    const data = await request("POST", matchPath(view.match.id, "/ready"));
    view.match = data.state;
    view.selection = null;
    renderGame();
    showResult();
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
  const fill = el("span", { class: "fill hp" });
  fill.style.setProperty("--amount", `${percent(seat.health, seat.max_health)}%`);
  const facts = `${seat.health} health, level ${seat.level}, ${seat.gold} gold, ${streakText(seat.streak)}`;
  return el("div", { class: `panel seat-card${seat.alive ? "" : " out"}` }, [
    el("div", { class: "section-head" }, [
      el("strong", { text: seat.name }),
      el("span", { class: "muted", text: facts }),
    ]),
    el("span", { class: "bar" }, [fill]),
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

function onKey(event) {
  if (event.key === "Escape") {
    if (!$("overlay").hidden) {
      closeDialog();
    } else if (view.selection) {
      view.selection = null;
      renderGame();
    }
    return;
  }
  const typing = ["INPUT", "TEXTAREA", "SELECT"].includes(event.target.tagName);
  if (typing || $("game").hidden || !$("overlay").hidden || event.ctrlKey || event.metaKey) {
    return;
  }
  const key = event.key.toLowerCase();
  if (key === "d") {
    act("reroll");
  } else if (key === "f") {
    act("xp");
  } else if (key === "e" && view.selection && view.selection.type === "unit") {
    act("sell", [view.selection.index]);
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
  await guarded(async () => {
    view.catalog = await request("GET", "/api/catalog");
    document.title = view.catalog.name;
    $("brand").textContent = view.catalog.name;
    await loadLobby();
  });
}

start();
