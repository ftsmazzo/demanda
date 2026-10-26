import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import type { ConversationSummary } from "../../api/types";
import { useConversations } from "../../hooks/queries";
import { formatMessageTime, formatPhone, initials } from "../../lib/format";

function Preview({ item }: { item: ConversationSummary }) {
  if (!item.last_text) return <span className="muted">Mensagem sem texto</span>;
  return <>{(item.last_direction === "out" ? "Você: " : "") + item.last_text}</>;
}

export function ConversationsPage() {
  const [params, setParams] = useSearchParams();
  const waiting = params.get("triagem") === "1";
  const [text, setText] = useState("");
  const [query, setQuery] = useState("");
  const list = useConversations(query, waiting);

  useEffect(() => {
    const timer = setTimeout(() => setQuery(text.trim()), 250);
    return () => clearTimeout(timer);
  }, [text]);

  function toggleWaiting() {
    const next = new URLSearchParams(params);
    if (waiting) next.delete("triagem");
    else next.set("triagem", "1");
    setParams(next, { replace: true });
  }

  return (
    <>
      <div className="view-head">
        <div>
          <h1 className="view-title">Conversas</h1>
          <p className="voice">Toda mensagem chega aqui primeiro. A IA decide o que vira tarefa, compromisso ou nota.</p>
        </div>
        <div className="toolbar">
          <input
            className="input input-search"
            type="search"
            aria-label="Buscar conversa"
            placeholder="Nome ou telefone"
            value={text}
            onChange={(event) => setText(event.target.value)}
          />
          <button type="button" className="chip" aria-pressed={waiting} onClick={toggleWaiting}>
            Na triagem
          </button>
        </div>
      </div>
      {list.isPending ? (
        <p role="status" className="loading">
          Carregando as conversas…
        </p>
      ) : !list.data ? (
        <div role="alert" className="loading">
          <p>Não foi possível carregar as conversas.</p>
          <button className="btn" type="button" onClick={() => void list.refetch()}>
            Tentar de novo
          </button>
        </div>
      ) : list.data.length === 0 ? (
        <p className="hint">
          {query || waiting
            ? "Nenhuma conversa encontrada."
            : "Nenhuma conversa ainda. Quando alguém escrever para o WhatsApp do escritório, ela aparece aqui."}
        </p>
      ) : (
        <ul className="inbox">
          {list.data.map((item) => (
            <li key={item.contact.id}>
              <Link className="inbox-row" to={"/contatos/" + item.contact.id + "/conversa"}>
                <span className="inbox-avatar" aria-hidden="true">
                  {initials(item.contact.name ?? "?")}
                </span>
                <span className="inbox-main">
                  <span className="inbox-name">
                    {item.contact.name ?? formatPhone(item.contact.phone)}
                    {item.contact.priority ? <span className="vip-tag">Prioritário</span> : null}
                  </span>
                  <span className="inbox-preview">
                    <Preview item={item} />
                  </span>
                </span>
                <span className="inbox-side">
                  <time dateTime={item.last_at}>{formatMessageTime(item.last_at)}</time>
                  <span className="inbox-badges">
                    {item.waiting > 0 ? <span className="review-tag">{item.waiting + " na triagem"}</span> : null}
                    {item.open_items > 0 ? (
                      <span className="count-tag">{item.open_items + (item.open_items === 1 ? " item aberto" : " itens abertos")}</span>
                    ) : null}
                  </span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
