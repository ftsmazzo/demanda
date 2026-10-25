import { useEffect, useState, type FormEvent, type KeyboardEvent } from "react";
import type { ContactKind, ContactRef } from "../../api/types";
import { useContacts, usePatchContact } from "../../hooks/queries";
import { saveErrorMessage } from "../../lib/errors";
import { formatPhone } from "../../lib/format";

const KIND_LABEL: Record<ContactKind, string> = {
  cliente: "Cliente",
  fornecedor: "Fornecedor",
  colaborador: "Colaborador",
  desconhecido: "Sem classificar",
};
const KINDS = Object.keys(KIND_LABEL) as ContactKind[];

const labelOf = (contact: ContactRef) => contact.name ?? `contato sem nome (final ${contact.phone.slice(-4)})`;

function NameEditor({ contact, onDone }: { contact: ContactRef; onDone: () => void }) {
  const patch = usePatchContact();
  const [value, setValue] = useState(contact.name ?? "");

  function save(event: FormEvent) {
    event.preventDefault();
    const name = value.trim();
    if (!name || name === contact.name) {
      onDone();
      return;
    }
    patch.mutate({ id: contact.id, patch: { name } }, { onSuccess: onDone });
  }

  function onKey(event: KeyboardEvent) {
    if (event.key === "Escape") {
      event.stopPropagation();
      onDone();
    }
  }

  return (
    <form className="name-edit" onSubmit={save}>
      <input
        className="input input-compact"
        aria-label="Nome do contato"
        value={value}
        maxLength={120}
        autoFocus
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={onKey}
      />
      <button className="btn btn-primary" type="submit" disabled={patch.isPending}>
        Salvar
      </button>
      <button className="btn" type="button" onClick={onDone}>
        Cancelar
      </button>
      {patch.isError ? (
        <span role="alert" className="form-error">
          {saveErrorMessage(patch.error)}
        </span>
      ) : null}
    </form>
  );
}

function ContactRow({ contact, onError }: { contact: ContactRef; onError: (error: unknown) => void }) {
  const patch = usePatchContact();
  const [editing, setEditing] = useState(false);
  const label = labelOf(contact);

  return (
    <li className="contact-row">
      <div className="contact-main">
        {editing ? (
          <NameEditor contact={contact} onDone={() => setEditing(false)} />
        ) : (
          <>
            <span className={contact.name ? "contact-name" : "contact-name muted"}>{contact.name ?? "Sem nome"}</span>
            <button
              type="button"
              className="link-btn"
              aria-label={contact.name ? `Renomear ${contact.name}` : `Dar nome a ${label}`}
              onClick={() => setEditing(true)}
            >
              {contact.name ? "Renomear" : "Dar nome"}
            </button>
          </>
        )}
      </div>
      <span className="contact-phone num">{formatPhone(contact.phone)}</span>
      <select
        className="select"
        aria-label={`Tipo de ${label}`}
        value={contact.kind}
        disabled={patch.isPending}
        onChange={(event) =>
          patch.mutate(
            { id: contact.id, patch: { kind: event.target.value as ContactKind } },
            { onSuccess: () => onError(null), onError },
          )
        }
      >
        {KINDS.map((kind) => (
          <option key={kind} value={kind}>
            {KIND_LABEL[kind]}
          </option>
        ))}
      </select>
    </li>
  );
}

export function ContactsPage() {
  const [text, setText] = useState("");
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState<ContactKind | "">("");
  const [failure, setFailure] = useState<unknown>(null);
  const contacts = useContacts(query, kind);

  useEffect(() => {
    const timer = setTimeout(() => setQuery(text.trim()), 250);
    return () => clearTimeout(timer);
  }, [text]);

  return (
    <>
      <div className="view-head">
        <div>
          <h1 className="view-title">Contatos</h1>
          <p className="voice">Quem fala com o escritório, e o que cada número é.</p>
        </div>
        <div className="toolbar">
          <input
            className="input input-search"
            type="search"
            aria-label="Buscar contato"
            placeholder="Nome ou telefone"
            value={text}
            onChange={(event) => setText(event.target.value)}
          />
          <select
            className="select"
            aria-label="Filtrar por tipo"
            value={kind}
            onChange={(event) => setKind(event.target.value as ContactKind | "")}
          >
            <option value="">Todos os tipos</option>
            {KINDS.map((item) => (
              <option key={item} value={item}>
                {KIND_LABEL[item]}
              </option>
            ))}
          </select>
        </div>
      </div>
      {failure ? (
        <p role="alert" className="form-error board-alert">
          {saveErrorMessage(failure)}
        </p>
      ) : null}
      {contacts.isPending ? (
        <p role="status" className="loading">
          Carregando os contatos…
        </p>
      ) : !contacts.data ? (
        <div role="alert" className="loading">
          <p>Não foi possível carregar os contatos.</p>
          <button className="btn" type="button" onClick={() => void contacts.refetch()}>
            Tentar de novo
          </button>
        </div>
      ) : contacts.data.length === 0 ? (
        <p className="hint">Nenhum contato encontrado.</p>
      ) : (
        <ul className="contact-list">
          {contacts.data.map((contact) => (
            <ContactRow key={contact.id} contact={contact} onError={setFailure} />
          ))}
        </ul>
      )}
    </>
  );
}
