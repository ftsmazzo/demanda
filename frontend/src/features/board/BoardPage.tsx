import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  TouchSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { Card, Me, Sector, Status } from "../../api/types";
import { useCurrentUser } from "../../components/AppShell";
import { useMoveDemand } from "../../hooks/move";
import { useBoard, useUsers } from "../../hooks/queries";
import { moveErrorMessage } from "../../lib/errors";
import { voiceSentence } from "../../lib/format";
import { SECTORS, SECTOR_LABEL, STATUSES } from "../../lib/sectors";
import { laneKeyboardCoordinates } from "./keyboard";
import { CardBody } from "./DemandCard";
import { Lane } from "./Lane";
import { NewDemandDialog, sectorsFor } from "./NewDemandDialog";

const canSeeHr = (me: Me) => me.role === "socio" || me.sectors.includes("rh-interno");

export function BoardPage() {
  const me = useCurrentUser();
  const [params, setParams] = useSearchParams();
  const sector = (params.get("setor") ?? "") as Sector | "";
  const person = params.get("pessoa") ?? "";
  const onlyPriority = params.get("prioritarios") === "1";
  const selectedId = params.get("demanda");
  const manager = me.role !== "colaborador";

  const board = useBoard({ sector, assignee: person, priority: onlyPriority });
  const users = useUsers(manager);
  const move = useMoveDemand();
  const [dragging, setDragging] = useState<Card | null>(null);
  const [creating, setCreating] = useState(false);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 250, tolerance: 8 } }),
    // Enter abre a demanda (clique do botao); Espaco pega e solta o card; setas trocam de coluna
    useSensor(KeyboardSensor, {
      keyboardCodes: { start: ["Space"], cancel: ["Escape"], end: ["Space"] },
      coordinateGetter: laneKeyboardCoordinates,
    }),
  );

  function update(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  }

  function open(card: Card) {
    move.reset();
    const next = new URLSearchParams(params);
    next.set("demanda", card.id);
    setParams(next);
  }

  const cards = board.data?.columns.flatMap((column) => column.demands) ?? [];

  function onDragStart(event: DragStartEvent) {
    setDragging(cards.find((card) => card.id === event.active.id) ?? null);
  }

  function onDragEnd(event: DragEndEvent) {
    setDragging(null);
    requestAnimationFrame(() => {
      document.querySelector<HTMLElement>(`[data-card-id="${event.active.id}"]`)?.focus({ preventScroll: true });
    });
    const card = cards.find((item) => item.id === event.active.id);
    const target = event.over?.id as Status | undefined;
    if (!card || !target || !STATUSES.includes(target) || card.status === target) return;
    move.mutate({ id: card.id, to: target });
  }

  if (board.isPending) {
    return (
      <p role="status" className="loading">
        Carregando o quadro…
      </p>
    );
  }
  if (!board.data) {
    return (
      <div role="alert" className="loading">
        <p>Não foi possível carregar o quadro.</p>
        <button className="btn" type="button" onClick={() => void board.refetch()}>
          Tentar de novo
        </button>
      </div>
    );
  }

  return (
    <>
      <div className="view-head">
        <div>
          <h1 className="view-title">Quadro</h1>
          <p className="voice">{voiceSentence(cards)}</p>
        </div>
        <div className="toolbar">
          <select
            className="select"
            aria-label="Filtrar por setor"
            value={sector}
            onChange={(event) => update("setor", event.target.value)}
          >
            <option value="">Todos os setores</option>
            {SECTORS.filter((item) => item !== "rh-interno" || canSeeHr(me)).map((item) => (
              <option key={item} value={item}>
                {SECTOR_LABEL[item]}
              </option>
            ))}
          </select>
          <button
            type="button"
            className="chip"
            aria-pressed={onlyPriority}
            onClick={() => update("prioritarios", onlyPriority ? "" : "1")}
          >
            Só prioritários
          </button>
          {manager ? (
            <select
              className="select"
              aria-label="Filtrar por pessoa"
              value={person}
              onChange={(event) => update("pessoa", event.target.value)}
            >
              <option value="">Todas as pessoas</option>
              {(users.data ?? []).map((user) => (
                <option key={user.id} value={user.id}>
                  {user.name}
                </option>
              ))}
            </select>
          ) : null}
          {manager && sectorsFor(me).length > 0 ? (
            <button className="btn btn-primary" type="button" onClick={() => setCreating(true)}>
              Nova demanda
            </button>
          ) : null}
        </div>
      </div>
      {move.isError ? (
        <p role="alert" className="form-error board-alert">
          {moveErrorMessage(move.error)}
        </p>
      ) : null}
      <DndContext sensors={sensors} onDragStart={onDragStart} onDragEnd={onDragEnd} onDragCancel={() => setDragging(null)}>
        <div className="board">
          {board.data.columns.map((column) => (
            <Lane key={column.status} column={column} selectedId={selectedId} onOpen={open} />
          ))}
        </div>
        <DragOverlay>
          {dragging ? (
            <div className="card card-overlay">
              <CardBody card={dragging} index={0} />
            </div>
          ) : null}
        </DragOverlay>
      </DndContext>
      {creating ? (
        <NewDemandDialog
          me={me}
          users={users.data ?? []}
          onClose={() => setCreating(false)}
          onCreated={(id) => {
            setCreating(false);
            const next = new URLSearchParams(params);
            next.set("demanda", id);
            setParams(next);
          }}
        />
      ) : null}
    </>
  );
}
