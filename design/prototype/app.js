import { CLOSED_TOTAL, DEMANDS, PEOPLE, SECTORS, STATUSES } from "./data.js";
import { closeDrawer, openDrawer, selectedId, setOnChange } from "./drawer.js";
import { markSvg, renderPanel } from "./panel.js";
import { AGE_COLOR, ageFill, avatar, el, icon, idleLevel, idleText, sectorTag, voiceSentence } from "./ui.js";

const state = { sector: "", person: "" };
const URGENCY_RANK = { critica: 3, alta: 2, normal: 1 };

const visible = () =>
  DEMANDS.filter((d) => (!state.sector || d.sector === state.sector) && (!state.person || d.assignee === state.person));

const sorted = (list) =>
  [...list].sort((a, b) => URGENCY_RANK[b.urgency] - URGENCY_RANK[a.urgency] || b.idle - a.idle);

function stepsRow(d) {
  if (!d.steps.length) return el("span", { class: "steps-text", text: "Sem etapas" });
  const done = d.steps.filter((s) => s.done).length;
  return el("span", { style: { display: "inline-flex", alignItems: "center", flex: "1" } },
    el("span", { class: "steps", "aria-hidden": "true" }, d.steps.slice(0, 8).map((s) => el("i", { class: s.done ? "on" : "" }))),
    el("span", { class: "steps-text num", text: `${done} de ${d.steps.length}` }));
}

function card(d, index) {
  const level = idleLevel(d.idle);
  const closed = d.status === "concluido";
  const flagged = !closed && d.urgency !== "normal";
  return el("button", {
    type: "button", class: "card", "aria-selected": String(selectedId() === d.id),
    "aria-label": `${d.title}. ${d.who}. ${idleText(d)}.`,
    onclick: (e) => openDrawer(d, e.currentTarget),
  },
    el("span", { class: "gauge", "aria-hidden": "true" },
      el("span", {
        class: "gauge-fill",
        style: { "--age": `${closed ? 100 : ageFill(d.idle)}%`, "--age-color": closed ? "var(--age-0)" : AGE_COLOR[level], "--i": String(index) },
      })),
    el("span", { class: "card-title", text: d.title }),
    el("span", { class: "card-who", text: d.who }),
    el("span", { class: "card-meta" },
      el("span", { style: { display: "inline-flex", gap: "12px", alignItems: "center" } },
        sectorTag(d.sector),
        d.restricted ? el("span", { title: "Acesso restrito" }, icon("lock", 13)) : null,
        flagged ? el("span", { class: "urgency", "data-level": d.urgency, text: d.urgency === "critica" ? "Crítica" : "Alta" }) : null),
      el("span", { class: "idle num", "data-level": closed ? "0" : String(level), text: idleText(d).replace("Parada ", "") })),
    el("span", { class: "card-foot" }, stepsRow(d), avatar(d.assignee)));
}

function lane(status, list) {
  const open = status.id !== "concluido";
  const oldest = open && list.length ? Math.max(...list.map((d) => d.idle)) : 0;
  const total = open ? list.length : CLOSED_TOTAL;
  return el("section", { class: `lane${open ? "" : " lane-done"}`, "aria-label": status.name },
    el("div", { class: "lane-head" },
      el("h2", { class: "lane-name", text: status.name }),
      el("span", { class: "lane-count num", text: String(total) })),
    el("div", { class: "lane-heat", style: { "--heat": AGE_COLOR[idleLevel(oldest)], "--heat-fill": open ? `${ageFill(oldest)}%` : "0%" } }),
    list.length
      ? el("div", { class: "cards" }, sorted(list).map(card))
      : el("p", { class: "empty-lane", text: "Nada por aqui. Quando uma demanda mudar de situação, ela aparece nesta coluna." }));
}

function filters() {
  const pick = (key) => (e) => { state[key] = e.target.value; renderBoard(); };
  const sector = el("select", { class: "select", "aria-label": "Filtrar por setor", onchange: pick("sector") },
    el("option", { value: "", text: "Todos os setores" }),
    Object.entries(SECTORS).map(([k, s]) => el("option", { value: k, selected: state.sector === k, text: s.name })));
  const who = el("select", { class: "select", "aria-label": "Filtrar por pessoa", onchange: pick("person") },
    el("option", { value: "", text: "Todas as pessoas" }),
    PEOPLE.map((p) => el("option", { value: p.id, selected: state.person === p.id, text: p.name })));
  return [sector, who, el("button", { class: "btn btn-primary", type: "button", text: "Nova demanda" })];
}

export function renderBoard() {
  const list = visible();
  document.getElementById("board-host").replaceChildren(
    el("div", { class: "view-head" },
      el("div", {}, el("p", { class: "view-title", text: "Quadro" }), el("p", { class: "voice", text: voiceSentence(list) })),
      el("div", { class: "toolbar" }, filters())),
    el("div", { class: "board" }, STATUSES.map((s) => lane(s, list.filter((d) => d.status === s.id)))));
}

function navigate() {
  const asked = location.hash.replace("#/", "") || "login";
  const view = ["login", "quadro", "painel"].includes(asked) ? asked : "quadro";
  document.getElementById("login").dataset.active = String(view === "login");
  document.getElementById("app").dataset.active = String(view !== "login");
  document.getElementById("board-host").hidden = view !== "quadro";
  document.getElementById("panel-host").hidden = view !== "painel";
  document.querySelectorAll("a.rail-link").forEach((a) => {
    if (a.getAttribute("href") === `#/${view}`) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  });
  if (view === "quadro") renderBoard();
  if (view === "painel") renderPanel();
  closeDrawer();
}

function chrome() {
  document.getElementById("rail").append(
    el("span", { class: "mark" }, markSvg()),
    el("a", { class: "rail-link", href: "#/quadro", title: "Quadro", "aria-label": "Quadro" }, icon("board")),
    el("a", { class: "rail-link", href: "#/painel", title: "Painel do sócio", "aria-label": "Painel do sócio" }, icon("chart")),
    el("span", { class: "rail-link", title: "Contatos (em breve)", style: { opacity: "0.5" } }, icon("people")),
    el("span", { class: "rail-spacer" }),
    el("a", { class: "me", href: "#/login", title: "Carlos Mendes, sair", "aria-label": "Carlos Mendes, sair", text: "CM" }));
  const bars = document.getElementById("bars");
  const heights = [34, 62, 24, 80, 46, 92, 30, 70, 54, 100, 38, 66, 28, 84, 48, 58];
  heights.forEach((h, n) => {
    const level = h > 75 ? 2 : h > 45 ? 1 : 0;
    bars.append(el("i", { style: { "--h": `${h}%`, "--c": AGE_COLOR[level], "--n": String(n) } }));
  });
}

export function boot() {
  chrome();
  setOnChange(() => {
    if (location.hash === "#/painel") renderPanel();
    else if (location.hash !== "#/login" && location.hash !== "") renderBoard();
  });
  document.getElementById("login-form").addEventListener("submit", (e) => { e.preventDefault(); location.hash = "#/quadro"; });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeDrawer(); });
  window.addEventListener("hashchange", navigate);
  navigate();
}
