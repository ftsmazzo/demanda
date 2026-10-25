import { useSearchParams } from "react-router-dom";
import type { Card, Me, Sector } from "../../api/types";
import { useCurrentUser } from "../../components/AppShell";
import { useBoard, useUsers } from "../../hooks/queries";
import { voiceSentence } from "../../lib/format";
import { SECTORS, SECTOR_LABEL } from "../../lib/sectors";
import { Lane } from "./Lane";

const canSeeHr = (me: Me) => me.role === "socio" || me.sectors.includes("rh-interno");

export function BoardPage() {
  const me = useCurrentUser();
  const [params, setParams] = useSearchParams();
  const sector = (params.get("setor") ?? "") as Sector | "";
  const person = params.get("pessoa") ?? "";
  const selectedId = params.get("demanda");
  const manager = me.role !== "colaborador";

  const board = useBoard({ sector, assignee: person });
  const users = useUsers(manager);

  function update(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  }

  function open(card: Card) {
    const next = new URLSearchParams(params);
    next.set("demanda", card.id);
    setParams(next);
  }

  if (board.isPending) {
    return (
      <p role="status" className="loading">
        Carregando o quadro…
      </p>
    );
  }
  if (board.isError || !board.data) {
    return (
      <div role="alert" className="loading">
        <p>Não foi possível carregar o quadro.</p>
        <button className="btn" type="button" onClick={() => void board.refetch()}>
          Tentar de novo
        </button>
      </div>
    );
  }

  const cards = board.data.columns.flatMap((column) => column.demands);
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
          {manager ? (
            <button className="btn btn-primary" type="button">
              Nova demanda
            </button>
          ) : null}
        </div>
      </div>
      <div className="board">
        {board.data.columns.map((column) => (
          <Lane key={column.status} column={column} selectedId={selectedId} onOpen={open} />
        ))}
      </div>
    </>
  );
}
