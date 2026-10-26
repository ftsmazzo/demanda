-- O agente passa a responder aos socios. A resposta entra na mesma caixa de saida (kind
-- 'reply', chave = id da mensagem recebida, o que evita responder duas vezes a uma reentrega).
ALTER TABLE agent_notifications DROP CONSTRAINT agent_notifications_kind_check;
ALTER TABLE agent_notifications ADD CONSTRAINT agent_notifications_kind_check
    CHECK (kind IN ('appointment', 'daily_summary', 'stuck', 'reply'));

-- Quem escreveu para o numero do agente? So o telefone identifica o tenant, e o runtime nao le
-- a tabela sem tenant: esta funcao devolve apenas os ids dos destinatarios ativos.
CREATE FUNCTION agent_recipients_by_phone(p_phone text)
    RETURNS TABLE (id uuid, tenant_id uuid)
    LANGUAGE sql STABLE SECURITY DEFINER
    SET search_path = public, pg_temp
    AS $$
        SELECT r.id, r.tenant_id FROM agent_recipients r WHERE r.phone = p_phone AND r.active
    $$;

REVOKE ALL ON FUNCTION agent_recipients_by_phone(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION agent_recipients_by_phone(text) TO demanda_app;
