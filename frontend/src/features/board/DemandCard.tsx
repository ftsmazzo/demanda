import { useDraggable } from "@dnd-kit/core";
import type { CSSProperties } from "react";
import type { Card } from "../../api/types";
import { Icon } from "../../components/Icon";
import { ageFill, idleBadge, idleLevel, initials } from "../../lib/format";
import { kindTag } from "../../lib/kinds";
import { useSectorBook } from "../../hooks/useSectorBook";

const AGE_COLOR = ["var(--age-0)", "var(--age-1)", "var(--age-2)"];
const MAX_SEGMENTS = 8;

function Steps({ card }: { card: Card }) {
  const { done, total } = card.progress;
  if (total === 0) return <span className="steps-text">Sem etapas</span>;
  const segments = Math.min(total, MAX_SEGMENTS);
  const filled = Math.round((done / total) * segments);
  return (
    <span className="steps-wrap">
      <span className="steps" aria-hidden="true">
        {Array.from({ length: segments }, (_, index) => (
          <i key={index} className={index < filled ? "on" : ""} />
        ))}
      </span>
      <span className="steps-text num">{`${done} de ${total}`}</span>
    </span>
  );
}

export function Avatar({ name }: { name: string | null }) {
  if (!name) {
    return (
      <span className="avatar empty" role="img" aria-label="Sem responsável" title="Sem responsável">
        ?
      </span>
    );
  }
  return (
    <span className="avatar" role="img" aria-label={name} title={name}>
      {initials(name)}
    </span>
  );
}

/** O conteudo visual do card, sem comportamento: serve ao card e ao "fantasma" do arrastar. */
export function CardBody({ card, index }: { card: Card; index: number }) {
  const sectors = useSectorBook();
  const closed = card.status === "concluido";
  const level = idleLevel(card.idle_hours);
  const flagged = !closed && card.urgency !== "normal";
  const gaugeStyle = {
    "--age": `${closed ? 100 : ageFill(card.idle_hours)}%`,
    "--age-color": closed ? "var(--age-0)" : AGE_COLOR[level],
    "--i": index,
  } as CSSProperties;

  return (
    <>
      <span className="gauge" aria-hidden="true">
        <span className="gauge-fill" style={gaugeStyle} />
      </span>
      <span className="card-title">{card.title}</span>
      <span className="card-who">{card.contact?.name ?? "Contato sem nome"}</span>
      {card.summary ? <span className="card-summary">{card.summary}</span> : null}
      <span className="card-meta">
        <span className="card-tags">
          <span className="sector" style={{ "--dot": sectors.color(card.sector) } as CSSProperties}>
            {sectors.label(card.sector)}
          </span>
          {card.sector === "rh-interno" ? (
            <span role="img" aria-label="Acesso restrito" title="Acesso restrito" className="lock">
              <Icon name="lock" size={13} />
            </span>
          ) : null}
          {kindTag(card.kind) ? <span className="kind-tag">{kindTag(card.kind)}</span> : null}
          {card.contact?.priority ? <span className="vip-tag">Prioritário</span> : null}
          {card.needs_review ? <span className="review-tag">Confirmar</span> : null}
          {flagged ? (
            <span className="urgency" data-level={card.urgency}>
              {card.urgency === "critica" ? "Crítica" : "Alta"}
            </span>
          ) : null}
        </span>
        <span className="idle num" data-level={closed ? 0 : level}>
          {idleBadge(card)}
        </span>
      </span>
      <span className="card-foot">
        <Steps card={card} />
        <Avatar name={card.assignee?.name ?? null} />
      </span>
    </>
  );
}

interface Props {
  card: Card;
  index: number;
  selected: boolean;
  onOpen: (card: Card) => void;
}

export function DemandCard({ card, index, selected, onOpen }: Props) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({ id: card.id });
  const who = card.contact?.name ?? "Contato sem nome";

  return (
    <button
      type="button"
      ref={setNodeRef}
      className="card"
      data-dragging={isDragging}
      aria-current={selected ? "true" : undefined}
      data-card-id={card.id}
      aria-label={`${card.title}. ${who}. ${idleBadge(card)}.${card.contact?.priority ? " Cliente prioritário." : ""}${card.needs_review ? " Precisa de confirmação." : ""}`}
      onClick={() => onOpen(card)}
      {...listeners}
      {...attributes}
      aria-roledescription="demanda arrastável"
    >
      <CardBody card={card} index={index} />
    </button>
  );
}
