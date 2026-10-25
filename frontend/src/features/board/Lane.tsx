import type { CSSProperties } from "react";
import type { Card, Column } from "../../api/types";
import { ageFill, idleLevel } from "../../lib/format";
import { STATUS_LABEL } from "../../lib/sectors";
import { DemandCard } from "./DemandCard";

const AGE_COLOR = ["var(--age-0)", "var(--age-1)", "var(--age-2)"];

interface Props {
  column: Column;
  selectedId: string | null;
  onOpen: (card: Card) => void;
}

export function Lane({ column, selectedId, onOpen }: Props) {
  const open = column.status !== "concluido";
  const oldest = open && column.demands.length ? Math.max(...column.demands.map((card) => card.idle_hours)) : 0;
  const heat = {
    "--heat": AGE_COLOR[idleLevel(oldest)],
    "--heat-fill": open ? `${ageFill(oldest)}%` : "0%",
  } as CSSProperties;
  const name = STATUS_LABEL[column.status];

  return (
    <section className={`lane${open ? "" : " lane-done"}`} aria-label={name}>
      <div className="lane-head">
        <h2 className="lane-name">{name}</h2>
        <span className="lane-count num">{column.count}</span>
      </div>
      <div className="lane-heat" style={heat} />
      {column.demands.length ? (
        <div className="cards">
          {column.demands.map((card, index) => (
            <DemandCard key={card.id} card={card} index={index} selected={card.id === selectedId} onOpen={onOpen} />
          ))}
        </div>
      ) : (
        <p className="empty-lane">Nada por aqui. Quando uma demanda mudar de situação, ela aparece nesta coluna.</p>
      )}
    </section>
  );
}
