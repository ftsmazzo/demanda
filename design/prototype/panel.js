import { DEMANDS, PEOPLE } from "./data.js";
import { openDrawer } from "./drawer.js";
import { AGE_COLOR, avatar, el, idleLevel, spanText } from "./ui.js";

export function markSvg(size = 30) {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", "0 0 30 30");
  svg.setAttribute("width", size);
  svg.setAttribute("height", size);
  svg.setAttribute("aria-hidden", "true");
  const bar = (y, h, fill) => {
    const r = document.createElementNS(ns, "rect");
    for (const [k, v] of Object.entries({ x: 10, y, width: 10, height: h, rx: 3, fill })) r.setAttribute(k, v);
    return r;
  };
  svg.append(bar(3, 24, "var(--rule-strong)"), bar(13, 14, "var(--azinhavre)"));
  return svg;
}

const PALETTE = { novo: "var(--ink-3)", em_andamento: "var(--azinhavre)", aguardando: "var(--age-1)" };

function stuckRow(d) {
  const days = d.idle >= 24;
  return el("button", {
    type: "button", class: "stuck-row", style: { "--age-color": AGE_COLOR[idleLevel(d.idle)] },
    onclick: (e) => openDrawer(d, e.currentTarget),
  },
    el("span", { class: "stuck-age num" }, String(days ? Math.floor(d.idle / 24) : Math.floor(d.idle)), el("small", { text: days ? (Math.floor(d.idle / 24) === 1 ? "dia" : "dias") : "h" })),
    el("span", {}, el("span", { class: "stuck-title", text: d.title }), el("br"), el("span", { class: "stuck-who", text: d.who })),
    avatar(d.assignee));
}

function loadRow(p, items) {
  const segment = (status) => el("i", {
    style: { width: `${(100 * items.filter((d) => d.status === status).length) / 5}%`, background: PALETTE[status] },
  });
  return el("div", { class: "load" },
    el("span", { text: p.name.split(" ")[0] }),
    el("span", { class: "load-bar", role: "img", "aria-label": `${items.length} demandas abertas` }, Object.keys(PALETTE).map(segment)),
    el("span", { class: "num", style: { color: "var(--ink-2)", fontWeight: "600" }, text: String(items.length) }));
}

export function renderPanel() {
  const open = DEMANDS.filter((d) => d.status !== "concluido");
  const stuck = [...open].sort((a, b) => b.idle - a.idle).slice(0, 6);
  const rows = PEOPLE.map((p) => ({ p, items: open.filter((d) => d.assignee === p.id) }))
    .filter((r) => r.items.length)
    .sort((a, b) => b.items.length - a.items.length);
  const legend = [["Novas", PALETTE.novo], ["Em andamento", PALETTE.em_andamento], ["Aguardando", PALETTE.aguardando]];
  document.getElementById("panel-host").replaceChildren(
    el("div", { class: "view-head" },
      el("div", {},
        el("p", { class: "view-title", text: "Painel do sócio" }),
        el("p", { class: "voice", text: `A demanda mais esquecida está parada há ${spanText(stuck[0].idle)}: ${stuck[0].title}.` }))),
    el("div", { class: "panel-grid" },
      el("section", {}, el("h2", { class: "section-title", style: { marginTop: "0" }, text: "Paradas há mais tempo" }), stuck.map(stuckRow)),
      el("section", {},
        el("h2", { class: "section-title", style: { marginTop: "0" }, text: "Carga da equipe" }),
        rows.map(({ p, items }) => loadRow(p, items)),
        el("div", { class: "legend" }, legend.map(([t, c]) => el("span", { style: { "--c": c }, text: t }))))));
}
