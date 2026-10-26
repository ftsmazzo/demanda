import type { CSSProperties, ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import type { Appointment, Card } from "../../api/types";
import { useCurrentUser } from "../../components/AppShell";
import { Icon } from "../../components/Icon";
import { usePatchAppointment, useToday } from "../../hooks/queries";
import { whenLabel } from "../../lib/agenda";
import { saveErrorMessage } from "../../lib/errors";
import { idleBadge, idleLevel } from "../../lib/format";
import { SECTOR_COLOR, SECTOR_LABEL } from "../../lib/sectors";

const AGE_COLOR = ["var(--age-0)", "var(--age-1)", "var(--age-2)"];

function reviewLabel(reason: string | null): string {
  if (reason?.includes("agrupamento")) return "Pode pertencer a outro caso";
  if (reason?.includes("remarcacao")) return "Possível remarcação";
  if (reason?.includes("triagem")) return "Aberto sem a triagem da IA";
  return "Confira o setor e o resumo";
}

function voice(decisions: number, attention: number): string {
  if (decisions > 0) {
    return decisions + (decisions === 1 ? " item espera" : " itens esperam") + " a sua decisão.";
  }
  if (attention > 0) {
    return "Nada para decidir. " + attention + (attention === 1 ? " item pede" : " itens pedem") + " atenção.";
  }
  return "Tudo em ordem por aqui.";
}

function Row({ card, note, onOpen }: { card: Card; note: string; onOpen: (card: Card) => void }) {
  const level = idleLevel(card.idle_hours);
  return (
    <button type="button" className="today-row" onClick={() => onOpen(card)}>
      <span className="today-age" style={{ "--age-color": AGE_COLOR[level] } as CSSProperties} aria-hidden="true" />
      <span className="today-main">
        <span className="today-title">{card.title}</span>
        <span className="today-note">
          {card.contact?.name ?? "Contato sem nome"} · {note}
        </span>
      </span>
      <span className="today-tags">
        {card.contact?.priority ? <span className="vip-tag">Prioritário</span> : null}
        <span className="sector" style={{ "--dot": SECTOR_COLOR[card.sector] } as CSSProperties}>
          {SECTOR_LABEL[card.sector]}
        </span>
      </span>
    </button>
  );
}

function Block({ title, count, children }: { title: string; count: number; children: ReactNode }) {
  return (
    <section className="today-block" aria-label={title}>
      <h2 className="today-block-title">
        {title} <span>{count}</span>
      </h2>
      {children}
    </section>
  );
}

function ConfirmRow({ item, canEdit }: { item: Appointment; canEdit: boolean }) {
  const patch = usePatchAppointment();
  return (
    <div className="today-confirm">
      <span className="today-main">
        <span className="today-title">{item.title}</span>
        <span className="today-note">
          {whenLabel(item.starts_at, item.all_day)}
          {item.contact?.name ? " · " + item.contact.name : ""}
        </span>
        {patch.isError ? <span className="form-error">{saveErrorMessage(patch.error)}</span> : null}
      </span>
      {canEdit ? (
        <span className="agenda-actions">
          <button
            type="button"
            className="btn btn-primary"
            disabled={patch.isPending}
            onClick={() => patch.mutate({ id: item.id, status: "confirmed" })}
          >
            Confirmar
          </button>
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
    </div>
  );
}

export function TodayPage() {
  const me = useCurrentUser();
  const today = useToday();
  const [params, setParams] = useSearchParams();
  const canEdit = me.role !== "colaborador";

  if (today.isPending) {
    return (
      <p role="status" className="loading">
        Carregando o dia…
      </p>
    );
  }
  if (!today.data) {
    return (
      <div role="alert" className="loading">
        <p>Não foi possível carregar o dia.</p>
        <button className="btn" type="button" onClick={() => void today.refetch()}>
          Tentar de novo
        </button>
      </div>
    );
  }

  const { needs_review, to_confirm, attention, waiting_triage, counts } = today.data;

  function open(card: Card) {
    const next = new URLSearchParams(params);
    next.set("demanda", card.id);
    setParams(next);
  }

  const quiet = !needs_review.length && !to_confirm.length && !attention.length && !waiting_triage;
  return (
    <>
      <div className="view-head">
        <div>
          <h1 className="view-title">Hoje</h1>
          <p className="voice">{voice(needs_review.length + to_confirm.length, attention.length)}</p>
        </div>
        <p className="today-counts num">
          <span>{counts.open} abertos</span>
          <span>{counts.meetings_today} compromissos hoje</span>
        </p>
      </div>

      {waiting_triage > 0 && canEdit ? (
        <Link className="triage-banner" to="/conversas?triagem=1">
          <Icon name="chat" size={18} />
          <span>{waiting_triage + (waiting_triage === 1 ? " mensagem na triagem" : " mensagens na triagem")}</span>
          <span className="triage-hint">A IA ainda vai transformar em item. Ver conversas</span>
        </Link>
      ) : null}

      {quiet ? <p className="hint today-quiet">Nada esperando por você.</p> : null}

      <div className="today-grid">
        <div className="today-col">
          {to_confirm.length ? (
            <Block title="Compromissos para confirmar" count={to_confirm.length}>
              {to_confirm.map((item) => (
                <ConfirmRow key={item.id} item={item} canEdit={canEdit} />
              ))}
            </Block>
          ) : null}
          {needs_review.length ? (
            <Block title="A IA ficou em dúvida" count={needs_review.length}>
              {needs_review.map((card) => (
                <Row key={card.id} card={card} note={reviewLabel(card.review_reason)} onOpen={open} />
              ))}
            </Block>
          ) : null}
        </div>
        <div className="today-col">
          {attention.length ? (
            <Block title="Pedem atenção" count={attention.length}>
              {attention.map((card) => (
                <Row key={card.id} card={card} note={idleBadge(card)} onOpen={open} />
              ))}
            </Block>
          ) : null}
        </div>
      </div>
    </>
  );
}
