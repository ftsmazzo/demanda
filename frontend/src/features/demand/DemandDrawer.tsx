import { useEffect, useRef, type CSSProperties } from "react";
import { ApiError } from "../../api/client";
import type { Me } from "../../api/types";
import { Icon } from "../../components/Icon";
import { useDemand } from "../../hooks/demand";
import { idleSentence } from "../../lib/format";
import { SECTOR_COLOR, SECTOR_LABEL } from "../../lib/sectors";
import { CaseAppointments, CaseHistory, CaseSummary, ConversationLink, ReviewNotice } from "./CaseParts";
import { Conversation } from "./Conversation";
import { Properties } from "./Properties";
import { Steps } from "./Steps";

interface Props {
  id: string;
  me: Me;
  onClose: () => void;
}

export function DemandDrawer({ id, me, onClose }: Props) {
  const { data, isPending, error, refetch } = useDemand(id);
  const closeButton = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null;
    closeButton.current?.focus({ preventScroll: true });
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

  const notFound = error instanceof ApiError && (error.status === 404 || error.status === 403);

  return (
    <aside className="drawer" role="dialog" aria-modal="false" aria-labelledby="drawer-title">
      <div className="drawer-head">
        <div className="drawer-top">
          {data ? (
            <span className="sector" style={{ "--dot": SECTOR_COLOR[data.sector] } as CSSProperties}>
              {SECTOR_LABEL[data.sector]}
            </span>
          ) : (
            <span />
          )}
          <button ref={closeButton} type="button" className="icon-btn" aria-label="Fechar detalhe" onClick={onClose}>
            <Icon name="close" />
          </button>
        </div>
        <h2 className="drawer-title" id="drawer-title">
          {data ? data.title : "Demanda"}
        </h2>
        {data ? (
          <p className="drawer-sub">
            {data.contact?.name ?? "Contato sem nome"}
            {data.contact ? ` (final ${data.contact.phone.slice(-4)})` : ""}. {idleSentence(data)}.
          </p>
        ) : null}
      </div>
      <div className="drawer-body">
        {isPending ? (
          <p role="status" className="hint">
            Carregando a demanda…
          </p>
        ) : null}
        {notFound ? <p className="hint">Esta demanda não existe ou você não tem acesso a ela.</p> : null}
        {error && !notFound ? (
          <div role="alert">
            <p className="form-error">Não foi possível carregar a demanda.</p>
            <button className="btn" type="button" onClick={() => void refetch()}>
              Tentar de novo
            </button>
          </div>
        ) : null}
        {data ? (
          <>
            <ReviewNotice demand={data} me={me} />
            <CaseSummary demand={data} />
            <Properties demand={data} me={me} />
            <CaseAppointments appointments={data.appointments} />
            <Conversation messages={data.messages} />
            <ConversationLink demand={data} />
            <Steps demand={data} />
            <CaseHistory events={data.events} />
          </>
        ) : null}
      </div>
    </aside>
  );
}
