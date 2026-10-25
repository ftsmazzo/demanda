-- Saude do canal: estado da instancia na Evolution e controle da reconciliacao de mensagens.
ALTER TABLE channels
    ADD COLUMN health_state       text,
    ADD COLUMN health_checked_at  timestamptz,
    ADD COLUMN health_changed_at  timestamptz,
    ADD COLUMN last_reconciled_at timestamptz;

GRANT UPDATE (health_state, health_checked_at, health_changed_at, last_reconciled_at)
    ON channels TO demanda_app;

-- O monitor roda sem tenant definido: precisa listar os canais de todos, como list_tenant_ids.
CREATE FUNCTION list_channels()
    RETURNS TABLE (id uuid, tenant_id uuid, instance_name text, listen_groups boolean,
                   health_state text, last_reconciled_at timestamptz)
    LANGUAGE sql STABLE SECURITY DEFINER
    SET search_path = public, pg_temp
    AS $$
        SELECT c.id, c.tenant_id, c.instance_name, c.listen_groups, c.health_state,
               c.last_reconciled_at
        FROM channels c
        WHERE c.active
        ORDER BY c.created_at, c.id
    $$;

REVOKE ALL ON FUNCTION list_channels() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION list_channels() TO demanda_app;
