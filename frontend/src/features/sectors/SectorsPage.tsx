import { useEffect, useState, type FormEvent } from "react";
import { ApiError } from "../../api/client";
import type { SectorInfo } from "../../api/types";
import { useCreateSector, usePatchSector, useSectors } from "../../hooks/queries";
import { SAVE_FAILED } from "../../lib/errors";

function failure(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 409) return "Já existe um setor com esse nome.";
    if (error.status === 422) return "Use um nome com letras ou números (até 40 caracteres).";
    if (error.status === 403) return "Só sócios mudam os setores.";
  }
  return SAVE_FAILED;
}

interface RowProps {
  item: SectorInfo;
  busy: boolean;
  onChange: (change: { label?: string; color?: string; active?: boolean }) => void;
}

function Row({ item, busy, onChange }: RowProps) {
  const [name, setName] = useState(item.label);
  useEffect(() => setName(item.label), [item.label]);

  function commitName() {
    const next = name.trim();
    if (next && next !== item.label) onChange({ label: next });
    else setName(item.label);
  }

  return (
    <li className="sector-row" data-active={item.active}>
      <input
        className="sector-color"
        type="color"
        aria-label={"Cor de " + item.label}
        value={item.color}
        onChange={(event) => onChange({ color: event.target.value })}
      />
      <input
        className="input sector-name"
        aria-label={"Nome de " + item.label}
        value={name}
        maxLength={40}
        onChange={(event) => setName(event.target.value)}
        onBlur={commitName}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            commitName();
          }
        }}
      />
      <span className="sector-state">
        {item.system ? <span className="count-tag">Do sistema</span> : null}
        {item.active ? null : <span className="review-tag">Desligado</span>}
      </span>
      {item.system ? null : (
        <button
          type="button"
          className="btn"
          disabled={busy}
          aria-label={(item.active ? "Desligar " : "Ligar ") + item.label}
          onClick={() => onChange({ active: !item.active })}
        >
          {item.active ? "Desligar" : "Ligar"}
        </button>
      )}
    </li>
  );
}

export function SectorsPage() {
  const list = useSectors();
  const create = useCreateSector();
  const patch = usePatchSector();
  const [label, setLabel] = useState("");
  const [missing, setMissing] = useState(false);
  const error = create.error ?? patch.error;

  function submit(event: FormEvent) {
    event.preventDefault();
    const name = label.trim();
    if (!name) {
      setMissing(true);
      return;
    }
    setMissing(false);
    create.mutate({ label: name }, { onSuccess: () => setLabel("") });
  }

  return (
    <>
      <div className="view-head">
        <div>
          <h1 className="view-title">Setores</h1>
          <p className="voice">
            Cada escritório organiza o trabalho do seu jeito. Itens novos só entram em setores ligados; o que já existe
            continua onde está.
          </p>
        </div>
      </div>
      <form className="sector-add" onSubmit={submit} noValidate>
        <input
          className="input"
          aria-label="Nome do novo setor"
          placeholder="Ex.: Jurídico"
          maxLength={40}
          value={label}
          onChange={(event) => {
            setLabel(event.target.value);
            setMissing(false);
          }}
        />
        <button type="submit" className="btn btn-primary" disabled={create.isPending}>
          Adicionar setor
        </button>
      </form>
      {missing ? <p className="form-error">Escreva o nome do setor.</p> : null}
      {error ? (
        <p role="alert" className="form-error">
          {failure(error)}
        </p>
      ) : null}
      {list.isPending ? (
        <p role="status" className="loading">
          Carregando os setores…
        </p>
      ) : !list.data ? (
        <div role="alert" className="loading">
          <p>Não foi possível carregar os setores.</p>
          <button className="btn" type="button" onClick={() => void list.refetch()}>
            Tentar de novo
          </button>
        </div>
      ) : (
        <ul className="sector-list" aria-label="Setores">
          {list.data.map((item) => (
            <Row
              key={item.slug}
              item={item}
              busy={patch.isPending}
              onChange={(change) => patch.mutate({ slug: item.slug, ...change })}
            />
          ))}
        </ul>
      )}
    </>
  );
}
