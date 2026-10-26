import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { Appointment } from "../../api/types";
import { useCurrentUser } from "../../components/AppShell";
import { useAppointments, usePatchAppointment } from "../../hooks/queries";
import { addDays, dayKey, rangeLabel, type CalendarView } from "../../lib/calendar";
import { saveErrorMessage } from "../../lib/errors";
import { EventPanel } from "./EventPanel";
import { ListView } from "./ListView";
import { MonthView } from "./MonthView";
import { parseDate, visibleRange, voice } from "./range";
import { WeekView } from "./WeekView";

const VIEWS: { id: CalendarView; label: string }[] = [
  { id: "week", label: "Semana" },
  { id: "month", label: "Mês" },
  { id: "list", label: "Lista" },
];

export function AgendaPage() {
  const me = useCurrentUser();
  const [params, setParams] = useSearchParams();
  const asked = params.get("visao");
  const view: CalendarView = VIEWS.find((v) => v.id === asked)?.id ?? "week";
  const cursor = parseDate(params.get("data"));
  const range = visibleRange(view, cursor);
  const list = useAppointments({ since: range.since.toISOString(), until: range.until.toISOString() });
  const patch = usePatchAppointment();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const canEdit = me.role !== "colaborador";

  function update(changes: Record<string, string | null>) {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(changes)) {
      if (value === null) next.delete(key);
      else next.set(key, value);
    }
    setParams(next);
  }
  function step(direction: 1 | -1) {
    const moved =
      view === "month" ? new Date(cursor.getFullYear(), cursor.getMonth() + direction, 1) : addDays(cursor, 7 * direction);
    update({ data: dayKey(moved) });
  }
  function changeView(next: CalendarView) {
    setSelectedId(null);
    update({ visao: next === "week" ? null : next });
  }

  if (list.isPending) {
    return (
      <p role="status" className="loading">
        Carregando a agenda…
      </p>
    );
  }
  if (!list.data) {
    return (
      <div role="alert" className="loading">
        <p>Não foi possível carregar a agenda.</p>
        <button className="btn" type="button" onClick={() => void list.refetch()}>
          Tentar de novo
        </button>
      </div>
    );
  }

  const items = list.data.filter((item) => item.status !== "cancelled");
  const selected = items.find((item) => item.id === selectedId) ?? null;
  const panelOpen = view !== "month" && selected !== null;
  const pick = (item: Appointment) => setSelectedId(item.id);
  const unit = view === "month" ? "Mês" : "Semana";

  return (
    <>
      <div className="view-head">
        <div>
          <h1 className="view-title">Agenda</h1>
          <p className="voice">{voice(items)}</p>
        </div>
      </div>
      <div className="cal-bar">
        <div className="cal-nav">
          {view === "list" ? null : (
            <>
              <button type="button" className="btn" aria-label={unit + " anterior"} onClick={() => step(-1)}>
                ‹
              </button>
              <button type="button" className="btn" aria-label={unit + " seguinte"} onClick={() => step(1)}>
                ›
              </button>
              <button type="button" className="btn" onClick={() => update({ data: null })}>
                Hoje
              </button>
              <h2 className="cal-range">{rangeLabel(view, cursor)}</h2>
            </>
          )}
        </div>
        <div className="seg" role="group" aria-label="Visão">
          {VIEWS.map((v) => (
            <button key={v.id} type="button" className="seg-btn" aria-pressed={v.id === view} onClick={() => changeView(v.id)}>
              {v.label}
            </button>
          ))}
        </div>
      </div>
      {patch.isError ? (
        <p role="alert" className="form-error board-alert">
          {saveErrorMessage(patch.error)}
        </p>
      ) : null}
      <div className="cal-layout" data-panel={panelOpen ? "open" : "closed"}>
        <div className="cal-main">
          {view === "week" ? (
            <>
              {items.length === 0 ? <p className="hint">Semana sem compromissos.</p> : null}
              <WeekView cursor={cursor} items={items} selectedId={selectedId} onSelect={pick} />
            </>
          ) : null}
          {view === "month" ? (
            <MonthView
              cursor={cursor}
              items={items}
              onPickDay={(date) => {
                setSelectedId(null);
                update({ visao: null, data: dayKey(date) });
              }}
            />
          ) : null}
          {view === "list" ? <ListView items={items} selectedId={selectedId} onSelect={pick} /> : null}
        </div>
        {panelOpen && selected ? (
          <EventPanel
            item={selected}
            canEdit={canEdit}
            busy={patch.isPending}
            onStatus={(status) => patch.mutate({ id: selected.id, status })}
            onOpenCase={() => update({ demanda: selected.demand_id })}
            onClose={() => setSelectedId(null)}
          />
        ) : null}
      </div>
    </>
  );
}
