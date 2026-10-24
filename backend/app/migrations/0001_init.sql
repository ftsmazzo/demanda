-- Demanda: schema inicial (tenants, canais, mensagens) com isolamento por RLS.

CREATE TABLE tenants (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug       text NOT NULL UNIQUE,
    name       text NOT NULL,
    timezone   text NOT NULL DEFAULT 'America/Sao_Paulo',
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE channels (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           uuid NOT NULL REFERENCES tenants (id),
    name                text NOT NULL,
    provider            text NOT NULL DEFAULT 'evolution' CHECK (provider IN ('evolution')),
    instance_name       text NOT NULL,
    webhook_secret_hash text NOT NULL,
    listen_groups       boolean NOT NULL DEFAULT false,
    active              boolean NOT NULL DEFAULT true,
    created_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, instance_name),
    UNIQUE (id, tenant_id)
);

CREATE TABLE messages (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           uuid NOT NULL REFERENCES tenants (id),
    channel_id          uuid NOT NULL,
    provider_message_id text NOT NULL,
    direction           text NOT NULL CHECK (direction IN ('in', 'out')),
    remote_jid          text NOT NULL,
    contact_phone       text NOT NULL,
    push_name           text,
    message_type        text NOT NULL,
    text                text,
    media               jsonb,
    provider_timestamp  timestamptz NOT NULL,
    raw                 jsonb NOT NULL,
    received_at         timestamptz NOT NULL DEFAULT now(),
    -- idempotencia: a mesma mensagem do provedor so entra uma vez por canal
    UNIQUE (channel_id, provider_message_id),
    -- a mensagem so pode apontar para um canal do mesmo tenant
    FOREIGN KEY (channel_id, tenant_id) REFERENCES channels (id, tenant_id)
);

CREATE INDEX messages_tenant_time_idx ON messages (tenant_id, provider_timestamp DESC);
CREATE INDEX messages_contact_idx ON messages (tenant_id, contact_phone, provider_timestamp DESC);

-- Papel restrito usado pela aplicacao em runtime (SET ROLE apos conectar).
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'demanda_app') THEN
        CREATE ROLE demanda_app NOLOGIN;
    END IF;
END
$$;

GRANT USAGE ON SCHEMA public TO demanda_app;
GRANT SELECT ON tenants, channels TO demanda_app;
GRANT SELECT, INSERT ON messages TO demanda_app;

CREATE FUNCTION app_tenant_id() RETURNS uuid
    LANGUAGE sql STABLE
    AS $$ SELECT nullif(current_setting('app.tenant_id', true), '')::uuid $$;

ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE channels ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages FORCE ROW LEVEL SECURITY;

-- (SELECT ...) faz o Postgres avaliar a funcao uma vez por consulta, nao por linha.
-- Sem FORCE em tenants e channels de proposito: auth_channel (SECURITY DEFINER, dono do
-- schema) precisa ler channels fora do contexto de tenant. Nao adicione FORCE ali sem
-- trocar o dono da funcao por um papel com BYPASSRLS.
CREATE POLICY tenants_isolation ON tenants USING (id = (SELECT app_tenant_id()));
CREATE POLICY channels_isolation ON channels USING (tenant_id = (SELECT app_tenant_id()));
CREATE POLICY messages_isolation ON messages
    USING (tenant_id = (SELECT app_tenant_id()))
    WITH CHECK (tenant_id = (SELECT app_tenant_id()));

-- Unico acesso entre tenants: autenticar o webhook antes de saber o tenant.
CREATE FUNCTION auth_channel(p_channel_id uuid)
    RETURNS TABLE (tenant_id uuid, webhook_secret_hash text, listen_groups boolean)
    LANGUAGE sql STABLE SECURITY DEFINER
    SET search_path = public, pg_temp
    AS $$
        SELECT c.tenant_id, c.webhook_secret_hash, c.listen_groups
        FROM channels c
        WHERE c.id = p_channel_id AND c.active
    $$;

REVOKE ALL ON FUNCTION auth_channel(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION auth_channel(uuid) TO demanda_app;
