import type { Message } from "../../api/types";
import { formatMessageTime } from "../../lib/format";

export function Conversation({ messages }: { messages: Message[] }) {
  return (
    <section aria-labelledby="conversation-title">
      <h3 className="section-title" id="conversation-title">
        Conversa <span>{messages.length}</span>
      </h3>
      {messages.length ? (
        <div className="thread">
          {messages.map((message) => (
            <div key={message.id} className={`msg${message.direction === "out" ? " out" : ""}`}>
              {message.text ?? <em className="media">Mídia sem texto</em>}
              <time dateTime={message.sent_at}>{formatMessageTime(message.sent_at)}</time>
            </div>
          ))}
        </div>
      ) : (
        <p className="hint">Esta demanda foi criada à mão, sem mensagens do WhatsApp.</p>
      )}
    </section>
  );
}
