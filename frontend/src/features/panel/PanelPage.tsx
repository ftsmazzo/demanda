import type { CSSProperties } from "react";
import { useSearchParams } from "react-router-dom";
import type { Card } from "../../api/types";
import { useBoard } from "../../hooks/queries";
import { idleLevel, spanText } from "../../lib/format";
import { stuckCards, teamLoad, type LoadRow } from "../../lib/panel";
import { Avatar } from "../board/DemandCard";

const AGE_COLOR = ["var(--age-0)", "var(--age-1)", "var(--age-2)"];
const SEGMENTS = [
  { status: "novo", label: "Novas", color: "var(--ink-3)" },
  { status: "em_andamento", label: "Em andamento", color: "var(--azinhavre)" },
  { status: "aguardando", label: "Aguardando", color: "var(--age-1)" },
] as const;
const STUCK_LIMIT = 6;

function Age({ hours }: { hours: number }) {
  const days = hours >= 24;
  const value = days ? Math.floor(hours / 24) : Math.max(1, Math.floor(hours));
  const unit = days ? (value === 1 ? "dia" : "dias") : "h";
  return (
    <span className="stuck-age num" style={{ "--age-color": AGE_COLOR[idleLevel(hours)] } as CSSProperties}>
      {value}
      <small>{unit}</small>
    </span>
  );
}

function StuckRow({ card, onOpen }: { card: Card; onOpen: (card: Card) => void }) {
  return (
    <button type="button" className="stuck-row" onClick={() => onOpen(card)}>
      <Age hours={card.idle_hours} />
      <span>
        <span className="stuck-title">{card.title}</span>
        <br />
        <span className="stuck-who">{card.contact?.name ?? "Contato sem nome"}</span>
      </span>
      <Avatar name={card.assignee?.name ?? null} />
    </button>
  );
}

function LoadLine({ row, scale }: { row: LoadRow; scale: number }) {
  const label = `${row.name}: ${row.total} ${row.total === 1 ? "demanda aberta" : "demandas abertas"}`;
  return (
    <div className="load">
      <span>{row.name.split(" ")[0]}</span>
      <span className="load-bar" role="img" aria-label={label}>
        {SEGMENTS.map(({ status, color }) => (
          <i key={status} style={{ width: `${(100 * row.byStatus[status]) / scale}%`, background: color }} />
        ))}
      </span>
      <span className="num load-total">{row.total}</span>
    </div>
  );
}

export function PanelPage() {
  const board = useBoard({});
  const [params, setParams] = useSearchParams();

  if (board.isPending) {
    return (
      <p role="status" className="loading">
        Carregando o painel…
      </p>
    );
  }
  if (board.isError || !board.data) {
    return (
      <div role="alert" className="loading">
        <p>Não foi possível carregar o painel.</p>
        <button className="btn" type="button" onClick={() => void board.refetch()}>
          Tentar de novo
        </button>
      </div>
    );
  }

  const cards = board.data.columns.flatMap((column) => column.demands);
  const stuck = stuckCards(cards, STUCK_LIMIT);
  const load = teamLoad(cards);
  const scale = Math.max(5, ...load.map((row) => row.total));

  function open(card: Card) {
    const next = new URLSearchParams(params);
    next.set("demanda", card.id);
    setParams(next);
  }

  return (
    <>
      <div className="view-head">
        <div>
          <h1 className="view-title">Painel do sócio</h1>
          <p className="voice">
            {stuck.length
              ? `A demanda mais esquecida está parada há ${spanText(stuck[0].idle_hours)}: ${stuck[0].title}.`
              : "Nenhuma demanda aberta. Tudo em dia."}
          </p>
        </div>
      </div>
      {stuck.length ? (
        <div className="panel-grid">
          <section aria-labelledby="stuck-title">
            <h2 className="section-title panel-first" id="stuck-title">
              Paradas há mais tempo
            </h2>
            {stuck.map((card) => (
              <StuckRow key={card.id} card={card} onOpen={open} />
            ))}
          </section>
          <section aria-labelledby="load-title">
            <h2 className="section-title panel-first" id="load-title">
              Carga da equipe
            </h2>
            {load.map((row) => (
              <LoadLine key={row.id ?? "none"} row={row} scale={scale} />
            ))}
            <div className="legend">
              {SEGMENTS.map(({ status, label, color }) => (
                <span key={status} style={{ "--c": color } as CSSProperties}>
                  {label}
                </span>
              ))}
            </div>
          </section>
        </div>
      ) : null}
    </>
  );
}
