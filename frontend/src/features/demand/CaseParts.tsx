import { Link, useSearchParams } from "react-router-dom";
import type { AppointmentBrief, CaseEvent, Detail, Me } from "../../api/types";
import { useMergeDemand, usePatchDemand } from "../../hooks/demand";
import { usePatchAppointment } from "../../hooks/queries";
import { whenLabel } from "../../lib/agenda";
import { saveErrorMessage } from "../../lib/errors";
import { actorLabel, describeEvent } from "../../lib/events";
import { formatMessageTime } from "../../lib/format";

const STATE_LABEL: Record<AppointmentBrief["status"], string> = {
  proposed: "Proposto",
  confirmed: "Confirmado",
  cancelled: "Cancelado",
};

export function CaseSummary({ demand }: { demand: Detail }) {
  if (!demand.summary && !demand.next_step) return null;
  return (
    <section className="case-summary" aria-label="Resumo do caso">
      {demand.summary ? <p className="case-text">{demand.summary}</p> : null}
      {demand.next_step ? (
        <p className="case-next">
          <span>Próximo passo</span>
          {demand.next_step}
        </p>
      ) : null}
    </section>
  );
}

const lastOf = (events: CaseEvent[], kind: CaseEvent["kind"]) =>
  [...events].reverse().find((event) => event.kind === kind);

export function ReviewNotice({ demand, me }: { demand: Detail; me: Me }) {
  const patch = usePatchDemand(demand.id);
  const merge = useMergeDemand();
  const appointment = usePatchAppointment();
  const [, setParams] = useSearchParams();
  if (!demand.needs_review) return null;

  const canAct = me.role !== "colaborador";
  const reason = demand.review_reason ?? "";
  const candidate = lastOf(demand.events, "review")?.data.candidate as string | undefined;
  const proposal = lastOf(demand.events, "proposal")?.data;
  const proposed = proposal?.proposed as { starts_at: string; all_day: boolean } | undefined;
  const clear = () => patch.mutate({ needs_review: false });
  const busy = patch.isPending || merge.isPending || appointment.isPending;
  const error = patch.error ?? merge.error ?? appointment.error;

  function joinEarlier() {
    if (!candidate) return;
    merge.mutate(
      { id: demand.id, into: candidate },
      {
        onSuccess: (target) =>
          setParams((current) => {
            const next = new URLSearchParams(current);
            next.set("demanda", target.id);
            return next;
          }),
      },
    );
  }

  function applyTime() {
    if (!proposal || !proposed) return;
    appointment.mutate(
      {
        id: proposal.appointment_id as string,
        starts_at: proposed.starts_at,
        all_day: proposed.all_day,
        status: "proposed",
      },
      { onSuccess: clear },
    );
  }

  let message = "A IA ficou em dúvida sobre este caso. Confira o setor e o resumo.";
  let actions = [{ label: "Está certo", run: clear, primary: true }];
  if (reason.includes("agrupamento")) {
    message = "A IA não teve certeza se esta mensagem pertence a outro caso deste contato.";
    actions = [
      ...(candidate ? [{ label: "Juntar ao caso anterior", run: joinEarlier, primary: true }] : []),
      { label: "É um caso separado", run: clear, primary: !candidate },
    ];
  } else if (reason.includes("remarcacao")) {
    const when = proposed ? whenLabel(proposed.starts_at, proposed.all_day) : "um novo horário";
    message = `A IA entendeu ${when}, mas não mexeu no compromisso.`;
    actions = [
      ...(proposed ? [{ label: "Aplicar o novo horário", run: applyTime, primary: true }] : []),
      { label: "Manter o horário atual", run: clear, primary: !proposed },
    ];
  }

  return (
    <div className="review-notice" role="alert">
      <p>{message}</p>
      {canAct ? (
        <div className="review-actions">
          {actions.map((action) => (
            <button
              key={action.label}
              type="button"
              className={action.primary ? "btn btn-primary" : "btn"}
              disabled={busy}
              onClick={action.run}
            >
              {action.label}
            </button>
          ))}
        </div>
      ) : null}
      {error ? <p className="form-error">{saveErrorMessage(error)}</p> : null}
    </div>
  );
}

export function CaseAppointments({ appointments }: { appointments: AppointmentBrief[] }) {
  if (appointments.length === 0) return null;
  return (
    <section aria-labelledby="case-appointments">
      <h3 className="section-title" id="case-appointments">
        Compromissos <span>{appointments.length}</span>
      </h3>
      <ul className="case-appointments">
        {appointments.map((item) => (
          <li key={item.id} data-status={item.status}>
            <span>{whenLabel(item.starts_at, item.all_day)}</span>
            <span className="agenda-state">{STATE_LABEL[item.status]}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function CaseHistory({ events }: { events: CaseEvent[] }) {
  if (events.length === 0) return null;
  return (
    <section aria-labelledby="case-history">
      <h3 className="section-title" id="case-history">
        Histórico <span>{events.length}</span>
      </h3>
      <ul className="case-history">
        {events.map((event) => (
          <li key={event.id}>
            <span className="case-actor">{actorLabel(event.actor)}</span>
            <span>{describeEvent(event)}</span>
            <time dateTime={event.created_at}>{formatMessageTime(event.created_at)}</time>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function ConversationLink({ demand }: { demand: Detail }) {
  if (!demand.contact) return null;
  return (
    <Link className="link-btn" to={`/contatos/${demand.contact.id}/conversa`}>
      Ver a conversa inteira
    </Link>
  );
}
