import { PEOPLE, SECTORS } from "./data.js";

export function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (value === undefined || value === null || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else if (key === "style") Object.entries(value).forEach(([k, v]) => node.style.setProperty(k, v));
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child.nodeType ? child : document.createTextNode(child));
  }
  return node;
}

const SVG = {
  board: "M4 5h4.5v14H4zM9.75 5h4.5v9h-4.5zM15.5 5H20v11.5h-4.5z",
  chart: "M5 19V11M10 19V5M15 19v-6M20 19V8",
  people: "M8.5 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM3 19c0-3 2.5-5 5.5-5s5.5 2 5.5 5M16.5 6.5a2.6 2.6 0 0 1 0 5M17.5 14.3c1.9.5 3.5 2 3.5 4.7",
  plus: "M12 5v14M5 12h14",
  close: "M6 6l12 12M18 6 6 18",
  check: "M5 12.5l4.5 4.5L19 7.5",
  lock: "M7 11V8a5 5 0 0 1 10 0v3M6 11h12v9H6z",
};

export function icon(name, size = 21) {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("width", size);
  svg.setAttribute("height", size);
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", "1.7");
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("stroke-linejoin", "round");
  svg.setAttribute("aria-hidden", "true");
  const path = document.createElementNS(ns, "path");
  path.setAttribute("d", SVG[name]);
  svg.append(path);
  return svg;
}

export const person = (id) => PEOPLE.find((p) => p.id === id) || null;

export function idleLevel(hours) {
  if (hours >= 72) return 2;
  if (hours >= 24) return 1;
  return 0;
}

export function idleText(demand) {
  if (demand.status === "concluido") return `Concluída há ${spanText(demand.closedAgo || 0)}`;
  if (demand.idle < 1) return "Movimentada agora";
  return `Parada há ${spanText(demand.idle)}`;
}

export function spanText(hours) {
  if (hours >= 48) return `${Math.floor(hours / 24)} dias`;
  if (hours >= 24) return "1 dia";
  return `${Math.max(1, Math.floor(hours))} h`;
}

export function ageFill(hours) {
  return Math.min(100, Math.max(12, 12 + (hours / 72) * 88));
}

export const AGE_COLOR = ["var(--age-0)", "var(--age-1)", "var(--age-2)"];

export function sectorTag(id) {
  const sector = SECTORS[id];
  return el("span", { class: "sector", style: { "--dot": sector.color }, text: sector.name });
}

export function avatar(id) {
  const p = person(id);
  if (!p) return el("span", { class: "avatar empty", title: "Sem responsável", "aria-label": "Sem responsável", text: "?" });
  return el("span", { class: "avatar", title: p.name, "aria-label": p.name, text: p.initials });
}

export function voiceSentence(demands) {
  const open = demands.filter((d) => d.status !== "concluido");
  const critical = open.filter((d) => d.urgency === "critica").length;
  const stuck = open.filter((d) => d.idle >= 24).length;
  const stuckText = stuck === 1 ? "1 está parada" : `${stuck} estão paradas`;
  if (critical && stuck) {
    const crit = critical === 1 ? "1 demanda crítica pede" : `${critical} demandas críticas pedem`;
    return `Hoje, ${crit} a sua atenção e ${stuckText} há mais de um dia.`;
  }
  if (critical) return `Hoje, ${critical === 1 ? "1 demanda crítica pede" : `${critical} demandas críticas pedem`} a sua atenção.`;
  if (stuck) return `${stuck === 1 ? "Uma demanda está parada" : `${stuck} demandas estão paradas`} há mais de um dia.`;
  return "Tudo em movimento hoje.";
}
