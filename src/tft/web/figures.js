/**
 * The champions' 3D figures, drawn once into sprite sheets and reused wherever a unit appears.
 *
 * Drawing takes a moment, so it happens one figure at a time after the page is up; until a
 * figure is ready, and in a browser that cannot draw in 3D at all, callers get `null` and show
 * the flat portrait instead.
 */
import { MODELS, partsOf } from "./models.js";
import { openStudio, renderSheet } from "./studio.js";

const SWAY_SECONDS = 1.6;
const sheets = new Map();

function sheetUrl(canvas) {
  return new Promise((resolve) => {
    canvas.toBlob((blob) => resolve(blob ? URL.createObjectURL(blob) : null), "image/png");
  });
}

/**
 * Draw every figure, yielding to the page between two of them. Resolves to how many figures
 * are ready: none when this browser cannot draw in 3D.
 */
export async function prepareFigures() {
  const studio = openStudio();
  if (!studio) {
    return 0;
  }
  for (const name of Object.keys(MODELS)) {
    const url = await sheetUrl(renderSheet(studio, partsOf(name)));
    if (url) {
      sheets.set(name, url);
    }
    await new Promise((resolve) => window.setTimeout(resolve, 0));
  }
  const lose = studio.gl.getExtension("WEBGL_lose_context");
  if (lose) {
    lose.loseContext();
  }
  return sheets.size;
}

/** Spread the sway of the figures in time so a board does not move like one body. */
function phaseOf(name, salt) {
  let sum = salt * 7;
  for (const letter of name) {
    sum += letter.charCodeAt(0);
  }
  return -((sum % 16) / 16) * SWAY_SECONDS;
}

/** The figure of a champion, standing on its base, or `null` when it has not been drawn. */
export function figureOf(name, salt = 0) {
  const url = sheets.get(name);
  if (!url) {
    return null;
  }
  const figure = document.createElement("span");
  figure.className = "figure";
  figure.style.backgroundImage = `url(${url})`;
  figure.style.animationDelay = `${phaseOf(name, salt).toFixed(2)}s`;
  const stand = document.createElement("span");
  stand.className = "stand";
  stand.append(figure);
  return stand;
}
