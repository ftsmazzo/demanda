import { useEffect, useRef } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { ApiError } from "../../api/client";
import type { Card } from "../../api/types";
import { useConversation } from "../../hooks/queries";
import { dayLabel } from "../../lib/agenda";
import { formatMessageTime, formatPhone } from "../../lib/format";
import { STATUS_SINGULAR } from "../../lib/sectors";

export function ConversationPage() {
  const { contactId } = useParams();
  const query = useConversation(contactId);
  const [params, setParams] = useSearchParams();
  const thread = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (thread.current) thread.current.scrollTop = thread.current.scrollHeight;
  }, [query.data?.messages.length]);

  if (query.isPending) {
    return (
      <p role="status" className="loading">
        Carregando a conversa…
      </p>
    );
  }
  if (!query.data) {
    const gone = query.error instanceof ApiError && (query.error.status === 404 || query.error.status === 403);
    return (
      <div role="alert" className="loading">
        <p>{gone ? "Esta conversa não existe ou você não tem acesso a ela." : "Não foi possível carregar a conversa."}</p>
        <Link className="btn" to="/contatos">
          Voltar para os contatos
        </Link>
      </div>
    );
  }

  const { contact, cases, messages } = query.data;
  const byId = new Map<string, Card>(cases.map((item) => [item.id, item]));

  function open(item: Card) {
    const next = new URLSearchParams(params);
    next.set("demanda", item.id);
    setParams(next);
  }

  return (
    <>
      <div className="view-head">
        <div>
          <h1 className="view-title">{contact.name ?? "Contato sem nome"}</h1>
          <p className="voice">{formatPhone(contact.phone)}</p>
        </div>
        <div className="toolbar">
          <Link className="btn" to="/contatos">
            Voltar para os contatos
          </Link>
        </div>
      </div>
      <div className="conversation-layout">
        <div className="thread thread-full" role="log" aria-label="Conversa" ref={thread}>
          {messages.map((message, index) => {
            const previous = messages[index - 1];
            const date = new Date(message.sent_at);
            const newDay = !previous || new Date(previous.sent_at).toDateString() !== date.toDateString();
            const newCase = !previous || previous.demand_id !== message.demand_id;
            const caseTitle = message.demand_id ? (byId.get(message.demand_id)?.title ?? "Outro caso") : "Sem caso";
            return (
              <div key={message.id} className="thread-item">
                {newDay ? <p className="thread-day">{dayLabel(date)}</p> : null}
                {newCase ? <p className="thread-case">{caseTitle}</p> : null}
                <div className={`msg${message.direction === "out" ? " out" : ""}`}>
                  {message.text ?? <em className="media">Mídia sem texto</em>}
                  <time dateTime={message.sent_at}>{formatMessageTime(message.sent_at)}</time>
                </div>
              </div>
            );
          })}
        </div>
        <section aria-label="Casos deste contato" className="case-list">
          <h2 className="section-title">
            Casos <span>{cases.length}</span>
          </h2>
          {cases.length === 0 ? <p className="hint">Nenhum caso aberto para este contato.</p> : null}
          {cases.map((item) => (
            <button key={item.id} type="button" className="case-row" onClick={() => open(item)}>
              <span className="case-row-title">{item.title}</span>
              {item.summary ? <span className="case-row-summary">{item.summary}</span> : null}
              <span className="case-row-state">{STATUS_SINGULAR[item.status]}</span>
            </button>
          ))}
        </section>
      </div>
    </>
  );
}
