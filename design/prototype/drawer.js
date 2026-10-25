import { PEOPLE, SECTORS, STATUSES, URGENCIES } from "./data.js";
import { avatar, el, icon, idleText, person, sectorTag } from "./ui.js";

const root = () => document.getElementById("drawer");
let current = null;
let onChange = () => {};
let opener = null;

export function setOnChange(fn) {
  onChange = fn;
}

export function closeDrawer() {
  root().dataset.open = "false";
  current = null;
  onChange();
  if (opener) opener.focus();
}

export function openDrawer(demand, trigger) {
  current = demand;
  opener = trigger || null;
  paint();
  root().dataset.open = "true";
  root().querySelector(".icon-btn").focus({ preventScroll: true });
  onChange();
}

export const selectedId = () => (current ? current.id : null);

function select(options, value, label, onPick) {
  const node = el("select", { class: "select", "aria-label": label, onchange: (e) => onPick(e.target.value) },
    options.map(([v, text]) => el("option", { value: v, selected: v === value, text })));
  return node;
}

function property(label, control) {
  return [el("dt", { text: label }), el("dd", {}, control)];
}

function paint() {
  const d = current;
  const host = root();
  host.replaceChildren(
    el("div", { class: "drawer-head" },
      el("div", { class: "drawer-top" },
        el("span", { class: "sector-line" }, sectorTag(d.sector), d.restricted ? el("span", { class: "sr-only", text: "acesso restrito" }) : null),
        el("button", { class: "icon-btn", "aria-label": "Fechar detalhe", onclick: closeDrawer }, icon("close"))),
      el("h2", { class: "drawer-title", id: "drawer-title", text: d.title }),
      el("p", { class: "drawer-sub", text: `${d.who} (final ${d.phone}). ${idleText(d)}.` })),
    el("div", { class: "drawer-body" },
      el("dl", { class: "props" },
        property("Situação", segmented(d)),
        property("Responsável", select([["", "Sem responsável"], ...PEOPLE.map((p) => [p.id, p.name])], d.assignee || "", "Responsável",
          (v) => { d.assignee = v || null; paint(); onChange(); })),
        property("Setor", select(Object.entries(SECTORS).map(([k, s]) => [k, s.name]), d.sector, "Setor",
          (v) => { d.sector = v; paint(); onChange(); })),
        property("Urgência", select(Object.entries(URGENCIES), d.urgency, "Urgência",
          (v) => { d.urgency = v; paint(); onChange(); }))),
      conversation(d),
      steps(d)));
}

function segmented(d) {
  return el("div", { class: "segmented", role: "group", "aria-label": "Situação da demanda" },
    STATUSES.map((s) => el("button", {
      type: "button", "aria-pressed": String(d.status === s.id), text: { novo: "Nova", em_andamento: "Em andamento", aguardando: "Aguardando", concluido: "Concluída" }[s.id],
      onclick: () => {
        d.status = s.id;
        if (s.id === "concluido") { d.idle = 0; d.closedAgo = 0; } else { d.idle = 0; }
        paint(); onChange();
      },
    })));
}

function conversation(d) {
  const msgs = d.msgs.length ? d.msgs : [{ out: false, t: d.title, at: "ter 09:00" }];
  return el("section", {},
    el("h3", { class: "section-title" }, "Conversa", el("span", { text: String(msgs.length) })),
    el("div", { class: "thread" },
      msgs.map((m) => el("div", { class: `msg${m.out ? " out" : ""}` }, m.t, el("time", { text: m.at })))));
}

function steps(d) {
  const done = d.steps.filter((s) => s.done).length;
  const pct = d.steps.length ? Math.round((100 * done) / d.steps.length) : 0;
  return el("section", {},
    el("h3", { class: "section-title" }, "Etapas", el("span", { text: d.steps.length ? `${done} de ${d.steps.length}` : "nenhuma ainda" })),
    d.steps.length ? el("div", { class: "progress", role: "progressbar", "aria-valuenow": pct, "aria-valuemin": 0, "aria-valuemax": 100 }, el("i", { style: { width: `${pct}%` } })) : null,
    el("ul", { class: "checklist" },
      d.steps.map((s) => el("li", {},
        el("button", {
          type: "button", class: "check", role: "checkbox", "aria-checked": String(s.done),
          onclick: () => { s.done = !s.done; d.idle = 0; paint(); onChange(); },
        }, el("span", { class: "box" }, icon("check", 13)), el("span", { class: "check-text", text: s.t }))))),
    );
}
