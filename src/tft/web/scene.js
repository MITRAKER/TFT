/**
 * The fight scene: the two boards fight the round out in front of the player.
 *
 * The engine has already decided the round by trading its slice. battle.js turns that result
 * into a script, and this module plays the script on the floor: the units leave their cells
 * and close with each other, strike or shoot, lose health and fall, and whoever is left
 * standing cheers. Then every unit shows what its own trade did to its size ("resolved"), and
 * a banner gives the result. A click or a key skips to the end.
 *
 * The motion is driven from here, frame by frame, through custom properties on the tokens and
 * small elements for the shots, the hits and the numbers; the style sheet says what they look
 * like.
 */
import { fightersOf, placeAt, planBattle, resultOf } from "./battle.js";
import { clear, el } from "./dom.js";
import { bannerOf, mirrorCell, resultLabel, resultTone } from "./logic.js";
import { hexCell, hexGrid, token } from "./pieces.js";

export const RESULT_MS = 1300;
export const BANNER_MS = 1400;
const LUNGE_SECONDS = 0.24;
const LUNGE = 0.24;
const RECOIL_SECONDS = 0.2;
const RECOIL = 0.1;
const LONGEST_FRAME = 0.1;
const TURN_AT = 0.15;
const MOVING = 0.003;
const NUMBER_SCALE = 100;
const FLASH = [{ filter: "brightness(2.4)" }, { filter: "brightness(1)" }];
const SHAKE = [
  { translate: "0 0" },
  { translate: "5px -3px" },
  { translate: "-4px 3px" },
  { translate: "2px -1px" },
  { translate: "0 0" },
];

/* The pieces on the floor --------------------------------------------------- */

function bar(name) {
  return el("span", { class: name }, [el("span", { class: `${name}-fill` })]);
}

/** A unit as it fights: its token with a health bar, a bar for its signature move and its verdict. */
function fighterToken(line, recipes, side) {
  const node = token(line, recipes);
  node.dataset.result = resultTone(line);
  node.dataset.side = side;
  node.dataset.face = side === "mine" ? "away" : "toward";
  node.append(
    el("span", { class: "bars", "aria-hidden": "true" }, [bar("healthbar"), bar("manabar")]),
    el("span", { class: "verdict", text: resultLabel(line) }),
  );
  return node;
}

/** Draw `lines` on a board and note the token of every fighter; the far board is turned around. */
function fillBoard(node, board, lines, recipes, side, tokens) {
  const placed = new Map();
  (lines || []).forEach((line, index) => {
    if (line.cell) {
      placed.set(`${line.cell[0]},${line.cell[1]}`, { line, id: `${side}-${index}` });
    }
  });
  const cellFor = (row, col) => {
    const [unitRow, unitCol] = side === "mine" ? [row, col] : mirrorCell(board, row, col);
    const entry = placed.get(`${unitRow},${unitCol}`);
    const piece = entry ? fighterToken(entry.line, recipes, side) : null;
    if (entry) {
      tokens.set(entry.id, piece);
    }
    return hexCell("span", { class: `hex${entry ? " occupied" : ""}` }, piece);
  };
  clear(node).append(...hexGrid(board, cellFor));
}

/** The two bars over the floor that say how much health each side has left. */
function teamBars(node, summary) {
  const team = (side, name) =>
    el("span", { class: `team ${side}` }, [
      el("span", { class: "team-name", text: name }),
      el("span", { class: "team-bar" }, [el("span", { class: "team-fill" })]),
    ]);
  clear(node).append(team("mine", "You"), el("span", { class: "versus", text: "vs" }), team("theirs", summary.opponent || "Nobody"));
  return { mine: node.querySelector(".mine .team-fill"), theirs: node.querySelector(".theirs .team-fill") };
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

/* The fight ------------------------------------------------------------------ */

/** Everything the playback keeps about one fighter. */
function actorOf(fighter, node, track) {
  return {
    ...fighter,
    node,
    figure: node.querySelector(".figure, .disc"),
    healthFill: node.querySelector(".healthbar-fill"),
    manaFill: node.querySelector(".manabar-fill"),
    track,
    shown: fighter.health,
    place: { ...fighter.home },
    aim: null,
    lunge: null,
    recoil: null,
    down: false,
    cast: false,
  };
}

/** A small thing on the floor: a shot, the flash of a hit, a number. `kind` is its class. */
function effect(battle, kind, place, text = "") {
  const node = el("span", { class: `fx-item ${kind}`, text });
  node.style.setProperty("--fx", place.x.toFixed(3));
  node.style.setProperty("--fy", place.y.toFixed(3));
  battle.fx.append(node);
  return node;
}

/** Show something for a moment: it is taken away when its animation ends. */
function flashEffect(battle, kind, place, text = "") {
  const node = effect(battle, kind, place, text);
  node.addEventListener("animationend", () => node.remove(), { once: true });
  return node;
}

function showTeams(battle) {
  for (const side of ["mine", "theirs"]) {
    const team = battle.actors.filter((actor) => actor.side === side);
    const whole = team.reduce((sum, actor) => sum + actor.health, 0);
    const left = team.reduce((sum, actor) => sum + actor.shown, 0);
    battle.teams[side].style.setProperty("--share", whole > 0 ? (left / whole).toFixed(3) : "0");
  }
}

function onCast(battle, event) {
  const actor = battle.byId.get(event.unit);
  actor.cast = true;
  actor.manaFill.style.setProperty("--share", "0");
  flashEffect(battle, "ring", actor.place).dataset.side = actor.side;
  if (event.name) {
    flashEffect(battle, "callout", actor.place, event.name).dataset.side = actor.side;
  }
}

function onAttack(battle, event) {
  const actor = battle.byId.get(event.from);
  const target = battle.byId.get(event.to);
  actor.aim = target;
  actor.lunge = { starts: event.t, style: event.style };
  if (event.style === "shot") {
    const node = effect(battle, event.heavy ? "shot heavy" : "shot", actor.place);
    node.dataset.side = actor.side;
    battle.shots.push({ node, from: { ...actor.place }, target, starts: event.t, lands: event.lands });
  }
}

function onHit(battle, event) {
  const target = battle.byId.get(event.to);
  const attacker = battle.byId.get(event.from);
  target.shown = event.health;
  target.healthFill.style.setProperty("--share", (event.health / target.health).toFixed(3));
  if (target.figure && target.figure.animate) {
    target.figure.animate(FLASH, { duration: 220 });
  }
  if (attacker) {
    target.recoil = { starts: event.t, from: { ...attacker.place } };
  }
  flashEffect(battle, event.heavy ? "impact heavy" : "impact", target.place);
  if (event.style === "strike") {
    flashEffect(battle, "slash", target.place).dataset.turn = attacker && attacker.place.x > target.place.x ? "left" : "right";
  }
  const lost = Math.round(event.loss * NUMBER_SCALE);
  if (lost > 0) {
    const number = flashEffect(battle, event.heavy ? "damage heavy" : "damage", target.place, `-${lost}`);
    number.dataset.side = target.side;
  }
  showTeams(battle);
}

function onFall(battle, event) {
  const actor = battle.byId.get(event.unit);
  actor.down = true;
  actor.node.dataset.down = "true";
  flashEffect(battle, "ring fallen", actor.place);
  // The floor shakes a little when a unit goes down.
  if (battle.ground.animate) {
    battle.ground.animate(SHAKE, { duration: 220 });
  }
}

function onCheer(battle) {
  for (const actor of battle.actors) {
    if (!actor.down) {
      actor.node.dataset.cheer = "true";
      actor.node.dataset.face = "toward";
    }
  }
}

const HANDLERS = { cast: onCast, attack: onAttack, hit: onHit, fall: onFall, cheer: onCheer };

/** How far a blow or a hit has moved a unit off its place at `clock`: a short push and back. */
function nudge(actor, clock) {
  let x = 0;
  let y = 0;
  const pushes = [
    [actor.lunge, actor.aim && actor.aim.place, LUNGE_SECONDS, actor.lunge && actor.lunge.style === "shot" ? -0.3 * LUNGE : LUNGE],
    [actor.recoil, actor.recoil && actor.recoil.from, RECOIL_SECONDS, -RECOIL],
  ];
  for (const [push, towards, seconds, reach] of pushes) {
    const progress = push ? (clock - push.starts) / seconds : 2;
    if (towards && progress >= 0 && progress <= 1) {
      const far = Math.hypot(towards.x - actor.place.x, towards.y - actor.place.y) || 1;
      const swing = Math.sin(Math.PI * progress) * reach;
      x += ((towards.x - actor.place.x) / far) * swing;
      y += ((towards.y - actor.place.y) / far) * swing;
    }
  }
  return { x, y };
}

function setData(node, key, value) {
  if (node.dataset[key] !== value) {
    node.dataset[key] = value;
  }
}

/** Put a fighter where the script has it now, facing whom it fights. */
function moveActor(actor, clock) {
  const spot = placeAt(actor.track, clock);
  const moved = Math.hypot(spot.x - actor.place.x, spot.y - actor.place.y) > MOVING;
  actor.place = spot;
  if (actor.down) {
    return;
  }
  const push = nudge(actor, clock);
  actor.node.style.setProperty("--mx", (spot.x + push.x - actor.home.x).toFixed(3));
  actor.node.style.setProperty("--my", (spot.y + push.y - actor.home.y).toFixed(3));
  setData(actor.node, "move", moved ? "run" : "stand");
  if (actor.aim && !actor.node.dataset.cheer) {
    setData(actor.node, "face", actor.aim.place.y < spot.y ? "away" : "toward");
    setData(actor.node, "turn", actor.aim.place.x < spot.x - TURN_AT ? "left" : "right");
  }
  if (!actor.cast) {
    actor.manaFill.style.setProperty("--share", Math.min(clock / actor.casts, 1).toFixed(3));
  }
}

/** Fly the shots towards their targets, wherever those have gone, and remove the ones that landed. */
function moveShots(battle, clock) {
  battle.shots = battle.shots.filter((shot) => {
    const progress = (clock - shot.starts) / Math.max(shot.lands - shot.starts, 0.01);
    if (progress >= 1) {
      shot.node.remove();
      return false;
    }
    const share = Math.max(progress, 0);
    shot.node.style.setProperty("--fx", (shot.from.x + (shot.target.place.x - shot.from.x) * share).toFixed(3));
    shot.node.style.setProperty("--fy", (shot.from.y + (shot.target.place.y - shot.from.y) * share).toFixed(3));
    return true;
  });
}

/**
 * Play a battle plan on the floor and call `done` when the cheering is over. Returns the
 * function that stops it. The clock only runs while frames are drawn, so a hidden tab pauses
 * the fight instead of skipping it.
 */
function playBattle(battle, plan, done) {
  let last = performance.now();
  let clock = 0;
  let next = 0;
  let frame = 0;
  const tick = (now) => {
    clock += Math.min((now - last) / 1000, LONGEST_FRAME);
    last = now;
    while (next < plan.events.length && plan.events[next].t <= clock) {
      HANDLERS[plan.events[next].kind](battle, plan.events[next]);
      next += 1;
    }
    battle.actors.forEach((actor) => moveActor(actor, clock));
    moveShots(battle, clock);
    if (clock >= plan.total) {
      done();
      return;
    }
    frame = window.requestAnimationFrame(tick);
  };
  frame = window.requestAnimationFrame(tick);
  return () => window.cancelAnimationFrame(frame);
}

/** Set the stage for a fight: both boards, the team bars, and the playback's notes. */
function setUp(stage, summary, board, recipes, context) {
  const tokens = new Map();
  fillBoard(stage.mine, board, summary.units, recipes, "mine", tokens);
  fillBoard(stage.enemy, board, summary.opponent_units, recipes, "theirs", tokens);
  const result = resultOf(summary, context.fights, context.seat);
  const plan = planBattle(fightersOf(summary, board, context.abilities), board, result);
  const actors = plan.fighters.map((fighter) => actorOf(fighter, tokens.get(fighter.id), plan.tracks.get(fighter.id)));
  const battle = {
    actors,
    byId: new Map(actors.map((actor) => [actor.id, actor])),
    fx: clear(stage.fx),
    ground: stage.fx.parentNode,
    teams: teamBars(stage.score, summary),
    shots: [],
  };
  actors.forEach((actor) => {
    actor.healthFill.style.setProperty("--share", "1");
    actor.manaFill.style.setProperty("--share", "0");
  });
  showTeams(battle);
  return { battle, plan };
}

/**
 * Play the fight on `stage` ({ root, floor, mine, enemy, fx, score, banner }) and call `done`
 * exactly once, at the end or when the player skips. `context` is what the scene needs beside
 * the summary: `{ fights, seat, abilities }`, the round's fights, the player's seat name and
 * the signature move of every champion. Returns the function that skips.
 */
export function playFight(stage, summary, board, recipes, context, done) {
  const timers = [];
  let stopBattle = () => {};
  let over = false;
  const finish = () => {
    if (over) {
      return;
    }
    over = true;
    stopBattle();
    timers.forEach((timer) => window.clearTimeout(timer));
    stage.root.removeEventListener("click", finish);
    stage.root.hidden = true;
    delete stage.floor.dataset.phase;
    stage.banner.hidden = true;
    clear(stage.fx);
    done();
  };
  const after = (delay, step) => timers.push(window.setTimeout(step, delay));

  const { battle, plan } = setUp(stage, summary, board, recipes, context);
  stage.banner.hidden = true;
  stage.floor.dataset.phase = "battle";
  stage.root.hidden = false;
  stage.root.addEventListener("click", finish);
  stopBattle = playBattle(battle, plan, () => {
    stage.floor.dataset.phase = "resolved";
    after(RESULT_MS, () => showBanner(stage.banner, summary));
    after(RESULT_MS + BANNER_MS, finish);
  });
  return finish;
}
