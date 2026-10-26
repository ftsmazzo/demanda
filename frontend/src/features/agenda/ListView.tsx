import type { Appointment } from "../../api/types";
import { groupByDay, timeLabel } from "../../lib/agenda";

interface Props {
  items: Appointment[];
  selectedId: string | null;
  onSelect: (item: Appointment) => void;
}

export function ListView({ items, selectedId, onSelect }: Props) {
  const groups = groupByDay(items);
  if (groups.length === 0) return <p className="hint">Nenhum compromisso nos próximos 30 dias.</p>;
  return (
    <>
      {groups.map((group) => (
        <section key={group.key} className="agenda-day" aria-label={group.label}>
          <h2 className="section-title">{group.label}</h2>
          <ul className="agenda-list">
            {group.items.map((item) => (
              <li key={item.id} className="agenda-row" data-status={item.status} data-selected={item.id === selectedId}>
                <span className="agenda-time num">{timeLabel(item)}</span>
                <div className="agenda-main">
                  <button type="button" className="agenda-title" onClick={() => onSelect(item)}>
                    {item.title}
                  </button>
                  {item.contact ? <span className="agenda-meta">{item.contact.name ?? "Contato sem nome"}</span> : null}
                </div>
                <span className="agenda-state">{item.status === "confirmed" ? "Confirmado" : "Proposto"}</span>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </>
  );
}
