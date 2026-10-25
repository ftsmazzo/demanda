import { useChannelHealth } from "../hooks/queries";
import { spanText } from "../lib/format";
import type { Me } from "../api/types";

/** Aviso fixo no topo quando a escuta do WhatsApp parou: sem ela, mensagens novas nao chegam. */
export function ChannelAlert({ me }: { me: Me }) {
  const health = useChannelHealth(me.role !== "colaborador");
  const down = (health.data ?? []).filter((channel) => !channel.healthy);
  if (down.length === 0) return null;

  return (
    <div role="alert" className="channel-alert">
      {down.map((channel) => {
        const since = channel.changed_at
          ? ` há ${spanText((Date.now() - Date.parse(channel.changed_at)) / 3_600_000)}`
          : "";
        return (
          <p key={channel.id}>
            <strong>{`O WhatsApp “${channel.name}” está desconectado${since}.`}</strong> Mensagens recebidas
            nesse período podem não aparecer até a conexão voltar. Reconecte a instância na Evolution.
          </p>
        );
      })}
    </div>
  );
}
