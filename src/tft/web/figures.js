/**
 * The champions' 3D figures, drawn once into sprite sheets and reused wherever a unit appears.
 *
 * Drawing takes a moment, so it happens in two passes after the page is up. The first draws the
 * standing clip of every figure, which is all the page needs to show its units; the second draws
 * the things that stand around the arena and then the clips of the fight, in the background,
 * one figure at a time. Until a figure is ready, and in a browser that cannot draw in 3D at
 * all, callers get `null` and show the flat portrait.
 */
import { MODELS, partsOf, propPartsOf } from "./models.js";
import { CLIPS, openStudio, renderClip } from "./studio.js";

export const IDLE_SECONDS = 1.6;
const FIRST = "idle";
const LATER = Object.keys(CLIPS).filter((clip) => clip !== FIRST);
const PHASES = 16;

/**
 * The things around the arena: the clip each is drawn in, how large, whether it stands on the
 * ground, and the custom property of the page that carries its picture to the style sheet.
 */
export const PROP_SHEETS = [
  { name: "Bull Statue", clip: "still", scale: 2, shadow: true, variable: "--prop-bull" },
  { name: "Bear Statue", clip: "still", scale: 2, shadow: true, variable: "--prop-bear" },
  { name: "Pylon", clip: "still", scale: 1, shadow: true, variable: "--prop-pylon" },
  { name: "Coin", clip: "turn", scale: 1, shadow: false, variable: "--prop-coin" },
  { name: "Bell", clip: "still", scale: 2, shadow: false, variable: "--prop-bell" },
];

/** For every figure that is drawn, the address of each ready clip as a CSS `url(...)`. */
const sheets = new Map();
/** The pictures of the later clips, kept so that the browser has them loaded when a fight starts. */
const loaded = [];
let later = Promise.resolve(0);

const pause = () => new Promise((resolve) => window.setTimeout(resolve, 0));

/** Load a picture ahead of its first use; resolves to whether the browser could read it. */
function preload(address) {
  return new Promise((resolve) => {
    const picture = new Image();
    picture.onload = () => {
      loaded.push(picture);
      resolve(true);
    };
    picture.onerror = () => resolve(false);
    picture.src = address;
  });
}

/**
 * Draw one clip of a figure and note where its sheet is. Resolves to `false` when the sheet
 * could not be made, which ends the drawing: a lost graphics context draws empty pictures.
 */
async function drawClip(studio, name, parts, clip) {
  if (studio.gl.isContextLost()) {
    return false;
  }
  const canvas = renderClip(studio, parts, clip);
  const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
  if (!blob || studio.gl.isContextLost()) {
    return false;
  }
  const address = URL.createObjectURL(blob);
  if (clip !== FIRST && !(await preload(address))) {
    return false;
  }
  sheets.set(name, { ...sheets.get(name), [clip]: `url("${address}")` });
  return true;
}

/** Draw the things around the arena and hand their pictures to the style sheet. */
async function drawProps(studio) {
  for (const prop of PROP_SHEETS) {
    if (studio.gl.isContextLost()) {
      return;
    }
    const canvas = renderClip(studio, propPartsOf(prop.name), prop.clip, prop);
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
    if (blob) {
      document.documentElement.style.setProperty(prop.variable, `url("${URL.createObjectURL(blob)}")`);
    }
  }
}

/** Draw the clips of the fight for every figure, then close the studio. */
async function drawLater(studio, figures) {
  let complete = 0;
  let working = true;
  for (const [name, parts] of figures) {
    for (const clip of LATER) {
      working = working && (await drawClip(studio, name, parts, clip));
    }
    if (!working) {
      break;
    }
    complete += 1;
    await pause();
  }
  const lose = studio.gl.getExtension("WEBGL_lose_context");
  if (lose) {
    lose.loseContext();
  }
  return complete;
}

/**
 * Draw the standing clip of every figure and resolve to how many figures are ready: none when
 * this browser cannot draw in 3D. The other clips are drawn afterwards, see `laterClips`.
 */
export async function prepareFigures() {
  const studio = openStudio();
  if (!studio) {
    return 0;
  }
  const figures = [];
  for (const name of Object.keys(MODELS)) {
    const parts = partsOf(name);
    if (await drawClip(studio, name, parts, FIRST)) {
      figures.push([name, parts]);
    }
  }
  later = drawProps(studio).then(() => drawLater(studio, figures));
  return figures.length;
}

/** Resolves, once the clips of the fight are drawn, to how many figures have every clip. */
export function laterClips() {
  return later;
}

/**
 * Where in its standing loop a figure is at `seconds` on the page's clock, as a negative delay.
 *
 * The name and the salt spread the figures in time so a board does not move like one body; the
 * clock makes a figure that is drawn again, as after every action, carry on where it was.
 */
export function phaseOf(name, salt, seconds) {
  let sum = salt * 7;
  for (const letter of name) {
    sum += letter.charCodeAt(0);
  }
  const offset = ((sum % PHASES) / PHASES) * IDLE_SECONDS;
  return -((seconds + offset) % IDLE_SECONDS);
}

/** Point a figure at the clips that are drawn; `has-clips` says it has every one of them. */
function dress(figure, clips) {
  for (const [clip, address] of Object.entries(clips)) {
    figure.style.setProperty(`--${clip}`, address);
  }
  figure.classList.toggle(
    "has-clips",
    Object.keys(CLIPS).every((clip) => clips[clip]),
  );
}

/**
 * Give the figures that are already on the page the clips drawn since they were made. They are
 * changed where they stand: nothing is drawn again, so no unit loses its place or its motion.
 */
export function upgradeFigures(root) {
  for (const figure of root.querySelectorAll(".figure:not(.has-clips)")) {
    const clips = sheets.get(figure.dataset.name);
    if (clips) {
      dress(figure, clips);
    }
  }
}

/** The figure of a champion, standing on its base, or `null` when it has not been drawn. */
export function figureOf(name, salt = 0) {
  const clips = sheets.get(name);
  if (!clips) {
    return null;
  }
  const figure = document.createElement("span");
  figure.className = "figure";
  figure.dataset.name = name;
  dress(figure, clips);
  const phase = phaseOf(name, salt, performance.now() / 1000);
  figure.style.setProperty("--phase", `${phase.toFixed(2)}s`);
  const stand = document.createElement("span");
  stand.className = "stand";
  stand.append(figure);
  return stand;
}
