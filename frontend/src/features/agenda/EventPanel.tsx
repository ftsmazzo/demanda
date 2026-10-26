import type { CSSProperties } from "react";
import { Link } from "react-router-dom";
import type { Appointment, AppointmentStatus } from "../../api/types";
import { whenLabel } from "../../lib/agenda";
import { SECTOR_COLOR, SECTOR_LABEL } from "../../lib/sectors";

const STATE_LABEL: Record<AppointmentStatus, string> = {
  proposed: "Proposto",
  confirmed: "Confirmado",
  cancelled: "Cancelado",
};

interface Props {
  item: Appointment;
  canEdit: boolean;
  busy: boolean;
  onStatus: (status: AppointmentStatus) => void;
  onOpenCase: () => void;
  onClose: () => void;
}

export function EventPanel({ item, canEdit, busy, onStatus, onOpenCase, onClose }: Props) {
  return (
    <section className="event-panel" aria-label="Compromisso selecionado" data-status={item.status}>
      <div className="event-panel-head">
        <span className="agenda-state">{STATE_LABEL[item.status]}</span>
        <button type="button" className="btn btn-quiet" onClick={onClose}>
          Fechar
        </button>
      </div>
      <h2 className="event-panel-title">{item.title}</h2>
      <p className="event-panel-when">{whenLabel(item.starts_at, item.all_day)}</p>
      <p className="agenda-meta">
        {item.contact ? <span>{item.contact.name ?? "Contato sem nome"}</span> : null}
        <span className="sector" style={{ "--dot": SECTOR_COLOR[item.sector] } as CSSProperties}>
          {SECTOR_LABEL[item.sector]}
        </span>
      </p>
      <div className="event-panel-actions">
        {canEdit && item.status === "proposed" ? (
          <button type="button" className="btn btn-primary" disabled={busy} onClick={() => onStatus("confirmed")}>
            Confirmar
          </button>
        ) : null}
        {canEdit && item.status !== "cancelled" ? (
          <button type="button" className="btn" disabled={busy} onClick={() => onStatus("cancelled")}>
            Cancelar
          </button>
        ) : null}
        <button type="button" className="btn" onClick={onOpenCase}>
          Abrir o caso
        </button>
        {item.contact ? (
          <Link className="btn" to={"/contatos/" + item.contact.id + "/conversa"}>
            Ver a conversa
          </Link>
        ) : null}
      </div>
    </section>
  );
}
