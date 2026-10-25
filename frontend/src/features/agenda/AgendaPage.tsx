import type { CSSProperties } from "react";
import { useSearchParams } from "react-router-dom";
import type { Appointment, AppointmentStatus } from "../../api/types";
import { useCurrentUser } from "../../components/AppShell";
import { useAppointments, usePatchAppointment } from "../../hooks/queries";
import { groupByDay, timeLabel } from "../../lib/agenda";
import { saveErrorMessage } from "../../lib/errors";
import { SECTOR_COLOR, SECTOR_LABEL } from "../../lib/sectors";

const STATE_LABEL: Record<AppointmentStatus, string> = {
  proposed: "Proposto",
  confirmed: "Confirmado",
  cancelled: "Cancelado",
};

function voice(list: Appointment[]): string {
  const proposed = list.filter((item) => item.status === "proposed").length;
  if (proposed) {
    return `${proposed} ${proposed === 1 ? "compromisso espera" : "compromissos esperam"} a sua confirmação.`;
  }
  return list.length ? "Tudo confirmado por aqui." : "Nenhum compromisso à vista.";
}

export function AgendaPage() {
  const me = useCurrentUser();
  const [params, setParams] = useSearchParams();
  const list = useAppointments();
  const patch = usePatchAppointment();
  const canEdit = me.role !== "colaborador";

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

  function openDemand(item: Appointment) {
    const next = new URLSearchParams(params);
    next.set("demanda", item.demand_id);
    setParams(next);
  }

  const groups = groupByDay(list.data);

  return (
    <>
      <div className="view-head">
        <div>
          <h1 className="view-title">Agenda</h1>
          <p className="voice">{voice(list.data)}</p>
        </div>
      </div>
      {patch.isError ? (
        <p role="alert" className="form-error board-alert">
          {saveErrorMessage(patch.error)}
        </p>
      ) : null}
      {groups.length === 0 ? (
        <p className="hint">
          Nenhum compromisso à vista. Quando alguém marcar algo pelo WhatsApp, aparece aqui para você confirmar.
        </p>
      ) : (
        groups.map((group) => (
          <section key={group.key} className="agenda-day" aria-label={group.label}>
            <h2 className="section-title">{group.label}</h2>
            <ul className="agenda-list">
              {group.items.map((item) => (
                <li key={item.id} className="agenda-row" data-status={item.status}>
                  <span className="agenda-time num">{timeLabel(item)}</span>
                  <div className="agenda-main">
                    <button type="button" className="agenda-title" onClick={() => openDemand(item)}>
                      {item.title}
                    </button>
                    <span className="agenda-meta">
                      {item.contact ? <span>{item.contact.name ?? "Contato sem nome"}</span> : null}
                      <span className="sector" style={{ "--dot": SECTOR_COLOR[item.sector] } as CSSProperties}>
                        {SECTOR_LABEL[item.sector]}
                      </span>
                    </span>
                  </div>
                  <span className="agenda-state">{STATE_LABEL[item.status]}</span>
                  {canEdit ? (
                    <span className="agenda-actions">
                      {item.status === "proposed" ? (
                        <button
                          type="button"
                          className="btn btn-primary"
                          disabled={patch.isPending}
                          onClick={() => patch.mutate({ id: item.id, status: "confirmed" })}
                        >
                          Confirmar
                        </button>
                      ) : null}
                      <button
                        type="button"
                        className="btn"
                        disabled={patch.isPending}
                        onClick={() => patch.mutate({ id: item.id, status: "cancelled" })}
                      >
                        Cancelar
                      </button>
                    </span>
                  ) : null}
                </li>
              ))}
            </ul>
          </section>
        ))
      )}
    </>
  );
}
