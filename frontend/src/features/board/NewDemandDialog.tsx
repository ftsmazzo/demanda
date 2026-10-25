import { useEffect, useRef, useState, type FormEvent } from "react";
import type { Me, Sector, Urgency, UserOut } from "../../api/types";
import { useCreateDemand } from "../../hooks/demand";
import { saveErrorMessage } from "../../lib/errors";
import { SECTORS, SECTOR_LABEL, URGENCY_LABEL } from "../../lib/sectors";

interface Props {
  me: Me;
  users: UserOut[];
  onClose: () => void;
  onCreated: (id: string) => void;
}

const URGENCIES = Object.keys(URGENCY_LABEL) as Urgency[];

export function sectorsFor(me: Me): Sector[] {
  if (me.role === "socio") return SECTORS.filter((sector) => sector !== "triagem");
  return SECTORS.filter((sector) => me.sectors.includes(sector));
}

export function NewDemandDialog({ me, users, onClose, onCreated }: Props) {
  const sectors = sectorsFor(me);
  const create = useCreateDemand();
  const titleField = useRef<HTMLInputElement>(null);
  const [title, setTitle] = useState("");
  const [sector, setSector] = useState<Sector>(sectors[0] ?? "fiscal");
  const [urgency, setUrgency] = useState<Urgency>("normal");
  const [assignee, setAssignee] = useState("");
  const [due, setDue] = useState("");
  const [missingTitle, setMissingTitle] = useState(false);

  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null;
    titleField.current?.focus({ preventScroll: true });
    return () => {
      if (opener?.isConnected) opener.focus({ preventScroll: true });
    };
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  function submit(event: FormEvent) {
    event.preventDefault();
    const trimmed = title.trim();
    if (!trimmed) {
      setMissingTitle(true);
      return;
    }
    create.mutate(
      { title: trimmed, sector, urgency, assignee_id: assignee || null, due_date: due || null },
      { onSuccess: (detail) => onCreated(detail.id) },
    );
  }

  return (
    <div className="modal-scrim" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <form className="modal" role="dialog" aria-modal="true" aria-labelledby="new-demand-title" onSubmit={submit} noValidate>
        <h2 className="modal-title" id="new-demand-title">
          Nova demanda
        </h2>
        <label className="field">
          O que precisa ser feito
          <input
            ref={titleField}
            className="input"
            value={title}
            maxLength={200}
            aria-invalid={missingTitle}
            onChange={(event) => {
              setTitle(event.target.value);
              setMissingTitle(false);
            }}
          />
          {missingTitle ? <span className="form-error">Escreva o que precisa ser feito.</span> : null}
        </label>
        <div className="modal-row">
          <label className="field">
            Setor
            <select className="input" value={sector} onChange={(event) => setSector(event.target.value as Sector)}>
              {sectors.map((item) => (
                <option key={item} value={item}>
                  {SECTOR_LABEL[item]}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            Responsável
            <select className="input" value={assignee} onChange={(event) => setAssignee(event.target.value)}>
              <option value="">Sem responsável</option>
              {users.map((user) => (
                <option key={user.id} value={user.id}>
                  {user.name}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="modal-row">
          <div className="field" role="group" aria-label="Urgência">
            Urgência
            <div className="segmented">
              {URGENCIES.map((item) => (
                <button key={item} type="button" aria-pressed={urgency === item} onClick={() => setUrgency(item)}>
                  {URGENCY_LABEL[item]}
                </button>
              ))}
            </div>
          </div>
          <label className="field">
            Prazo
            <input className="input" type="date" value={due} onChange={(event) => setDue(event.target.value)} />
          </label>
        </div>
        {create.isError ? (
          <p role="alert" className="form-error">
            {saveErrorMessage(create.error)}
          </p>
        ) : null}
        <div className="modal-actions">
          <button className="btn" type="button" onClick={onClose}>
            Cancelar
          </button>
          <button className="btn btn-primary" type="submit" disabled={create.isPending}>
            Criar demanda
          </button>
        </div>
      </form>
    </div>
  );
}
