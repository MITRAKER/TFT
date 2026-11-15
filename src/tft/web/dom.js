/** Small DOM helpers shared by the client's modules: elements, and pictures from art.js. */
import { CHAMPIONS, COMPONENTS, ICONS, TRAITS, VIEW, shapesOf } from "./art.js";
import { initials } from "./logic.js";

const SVG_NS = "http://www.w3.org/2000/svg";

export const $ = (id) => document.getElementById(id);

function setProp(node, key, value) {
  if (key === "class") {
    node.setAttribute("class", value);
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

function build(node, props, children) {
  for (const [key, value] of Object.entries(props)) {
    if (value !== null && value !== undefined && value !== false) {
      setProp(node, key, value);
    }
  }
  for (const child of [].concat(children)) {
    if (child) {
      node.append(child);
    }
  }
  return node;
}

/** Create an element; `props` sets class, text, data, listeners (onclick...) and attributes. */
export function el(tag, props = {}, children = []) {
  return build(document.createElement(tag), props, children);
}

/** Create an SVG element the same way. */
export function svg(tag, props = {}, children = []) {
  return build(document.createElementNS(SVG_NS, tag), props, children);
}

export function clear(node) {
  node.replaceChildren();
  return node;
}

export function button(text, onclick, extra = {}) {
  return el("button", { type: "button", text, onclick, ...extra });
}

function drawing(shapes, extraClass) {
  const nodes = shapes.map((shape) => svg(shape.tag, { class: shape.tone, ...shape.attrs }));
  const classes = extraClass ? `art ${extraClass}` : "art";
  return svg("svg", { class: classes, viewBox: `0 0 ${VIEW} ${VIEW}`, "aria-hidden": "true" }, nodes);
}

function lettering(name) {
  const text = svg("text", { class: "ink letters", x: VIEW / 2, y: VIEW / 2 + 6, "text-anchor": "middle" });
  text.textContent = initials(name);
  return svg("svg", { class: "art", viewBox: `0 0 ${VIEW} ${VIEW}`, "aria-hidden": "true" }, [text]);
}

/** The picture of `name` from one of the art tables; a name without art gets its initials. */
function pictureFrom(table, name, extraClass) {
  const shapes = shapesOf(table, name);
  return shapes ? drawing(shapes, extraClass) : lettering(name);
}

export const portrait = (name) => pictureFrom(CHAMPIONS, name);
export const traitGlyph = (name) => pictureFrom(TRAITS, name, "glyph");
export const componentGlyph = (name) => pictureFrom(COMPONENTS, name, "glyph");
export const icon = (name) => pictureFrom(ICONS, name, "glyph");

/** Fill every `[data-icon]` placeholder under `root` with its interface icon. */
export function decorate(root) {
  for (const node of root.querySelectorAll("[data-icon]")) {
    clear(node).append(icon(node.dataset.icon));
  }
}
