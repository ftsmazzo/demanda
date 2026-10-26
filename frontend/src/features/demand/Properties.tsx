import type { Detail, Me, Sector, Status, Urgency } from "../../api/types";
import { useUsers } from "../../hooks/queries";
import { usePatchDemand } from "../../hooks/demand";
import { useSectorBook } from "../../hooks/useSectorBook";
import { STATUSES, STATUS_SINGULAR, URGENCY_LABEL } from "../../lib/sectors";
import { saveErrorMessage } from "../../lib/errors";

const URGENCIES = Object.keys(URGENCY_LABEL) as Urgency[];
const canSeeHr = (me: Me) => me.role === "socio" || me.sectors.includes("rh-interno");

export function Properties({ demand, me }: { demand: Detail; me: Me }) {
  const patch = usePatchDemand(demand.id);
  const manager = me.role !== "colaborador";
  const users = useUsers(manager);
  const save = (change: Parameters<typeof patch.mutate>[0]) => patch.mutate(change);
  const sectors = useSectorBook();
  // o setor atual entra mesmo se ja foi desligado, para o campo nao mentir
  const sectorSlugs = [...new Set([...sectors.active.map((item) => item.slug), demand.sector])].filter(
    (slug) => slug !== "rh-interno" || canSeeHr(me) || slug === demand.sector,
  );

  return (
    <>
      <dl className="props">
        <dt>Situação</dt>
        <dd>
          <div className="segmented" role="group" aria-label="Situação da demanda">
            {STATUSES.map((status: Status) => (
              <button
                key={status}
                type="button"
                aria-pressed={demand.status === status}
                disabled={patch.isPending}
                onClick={() => demand.status !== status && save({ status })}
              >
                {STATUS_SINGULAR[status]}
              </button>
            ))}
          </div>
        </dd>
        <dt>Responsável</dt>
        <dd>
          {manager ? (
            <select
              className="select"
              aria-label="Responsável"
              value={demand.assignee?.id ?? ""}
              onChange={(event) => save({ assignee_id: event.target.value || null })}
            >
              <option value="">Sem responsável</option>
              {(users.data ?? []).map((user) => (
                <option key={user.id} value={user.id}>
                  {user.name}
                </option>
              ))}
            </select>
          ) : (
            <span className="plain">{demand.assignee?.name ?? "Sem responsável"}</span>
          )}
        </dd>
        {manager ? (
          <>
            <dt>Setor</dt>
            <dd>
              <select
                className="select"
                aria-label="Setor"
                value={demand.sector}
                onChange={(event) => save({ sector: event.target.value as Sector })}
              >
                {sectorSlugs.map((sector) => (
                  <option key={sector} value={sector}>
                    {sectors.label(sector)}
                  </option>
                ))}
              </select>
            </dd>
          </>
        ) : null}
        <dt>Urgência</dt>
        <dd>
          {manager ? (
            <select
              className="select"
              aria-label="Urgência"
              value={demand.urgency}
              onChange={(event) => save({ urgency: event.target.value as Urgency })}
            >
              {URGENCIES.map((urgency) => (
                <option key={urgency} value={urgency}>
                  {URGENCY_LABEL[urgency]}
                </option>
              ))}
            </select>
          ) : (
            <span className="plain">{URGENCY_LABEL[demand.urgency]}</span>
          )}
        </dd>
        <dt>Prazo</dt>
        <dd>
          {manager ? (
            <input
              className="input-date"
              type="date"
              aria-label="Prazo"
              value={demand.due_date ?? ""}
              onChange={(event) => save({ due_date: event.target.value || null })}
            />
          ) : (
            <span className="plain">{demand.due_date ?? "Sem prazo"}</span>
          )}
        </dd>
      </dl>
      {patch.isError ? (
        <p role="alert" className="form-error">
          {saveErrorMessage(patch.error)}
        </p>
      ) : null}
    </>
  );
}
