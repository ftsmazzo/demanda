import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent as ReactKeyboardEvent } from "react";
import type { Me, Sector, SectorInfo, Urgency, UserOut } from "../../api/types";
import { useCreateDemand } from "../../hooks/demand";
import { saveErrorMessage } from "../../lib/errors";
import { useSectorBook } from "../../hooks/useSectorBook";
import { URGENCY_LABEL } from "../../lib/sectors";

interface Props {
  me: Me;
  users: UserOut[];
  onClose: () => void;
  onCreated: (id: string) => void;
}

const URGENCIES = Object.keys(URGENCY_LABEL) as Urgency[];

/** Setores em que a pessoa pode abrir demanda: socio em todos (menos a triagem), gestor nos seus. */
export function sectorsFor(me: Me, active: SectorInfo[]): Sector[] {
  const slugs = active.map((item) => item.slug);
  if (me.role === "socio") return slugs.filter((sector) => sector !== "triagem");
  return slugs.filter((sector) => me.sectors.includes(sector));
}

export function NewDemandDialog({ me, users, onClose, onCreated }: Props) {
  const book = useSectorBook();
  const sectors = sectorsFor(me, book.active);
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

  const busy = create.isPending;
  const close = () => {
    if (!busy) onClose();
  };

  useEffect(() => {
    // na captura, para o Escape fechar so este dialogo e nao tambem a gaveta que esta atras
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.stopPropagation();
      if (!busy) onClose();
    };
    document.addEventListener("keydown", onKey, true);
    return () => document.removeEventListener("keydown", onKey, true);
  }, [busy, onClose]);

  function trapTab(event: ReactKeyboardEvent<HTMLFormElement>) {
    if (event.key !== "Tab") return;
    const items = Array.from(
      event.currentTarget.querySelectorAll<HTMLElement>("input, select, button:not(:disabled)"),
    );
    const first = items[0];
    const last = items[items.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    const trimmed = title.trim();
    if (!trimmed) {
      setMissingTitle(true);
      titleField.current?.focus();
      return;
    }
    create.mutate(
      { title: trimmed, sector, urgency, assignee_id: assignee || null, due_date: due || null },
      { onSuccess: (detail) => onCreated(detail.id) },
    );
  }

  return (
    <div className="modal-scrim" onMouseDown={(event) => event.target === event.currentTarget && close()}>
      <form className="modal" role="dialog" aria-modal="true" aria-labelledby="new-demand-title" onSubmit={submit} onKeyDown={trapTab} noValidate>
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
            aria-describedby={missingTitle ? "new-demand-title-error" : undefined}
            onChange={(event) => {
              setTitle(event.target.value);
              setMissingTitle(false);
            }}
          />
          {missingTitle ? <span className="form-error" id="new-demand-title-error">Escreva o que precisa ser feito.</span> : null}
        </label>
        <div className="modal-row">
          <label className="field">
            Setor
            <select className="input" value={sector} onChange={(event) => setSector(event.target.value as Sector)}>
              {sectors.map((item) => (
                <option key={item} value={item}>
                  {book.label(item)}
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
          <button className="btn" type="button" onClick={close} disabled={busy}>
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
